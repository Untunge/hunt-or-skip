"""The decision engine: hard vetoes first, then a transparent score.

Design rules (see README for the reasoning):
- Never trust the headline max bounty. Score on the payout for the severity
  the hunter actually targets, using the MINIMUM of a published range.
- A fee the hunter cannot afford is a veto, not a penalty.
- Unknown fee or unknown payout caps the verdict at CAUTION. A tool that
  says GO on data it does not have is worse than no tool.
- Every number in the verdict is printed with its working, so the hunter
  can disagree with the math instead of trusting a black box.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

STALE_DAYS = 30
SEVERITIES = ("critical", "high", "medium", "low")


@dataclass
class Hunter:
    """The hunter's own constraints. Defaults describe a zero-budget hunter."""

    stake_budget_usd: float = 0.0
    hours: float = 8.0
    can_kyc: bool = False
    target: str = "medium"

    def __post_init__(self) -> None:
        self.target = self.target.lower()
        if self.target not in SEVERITIES:
            raise ValueError(f"target must be one of {SEVERITIES}, got {self.target!r}")
        if self.hours <= 0:
            raise ValueError("hours must be positive")


@dataclass
class Evaluation:
    program: dict
    hunter: Hunter
    verdict: str  # GO | CAUTION | NO-GO
    score: int
    vetoes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    cost_usd: float | None = None
    payout_usd: float | None = None
    breakeven_pct: float | None = None
    hourly_if_found_usd: float | None = None
    stale: bool = False
    score_breakdown: list[tuple[str, int]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "program": self.program["id"],
            "platform": self.program["platform"],
            "verdict": self.verdict,
            "score": self.score,
            "target": self.hunter.target,
            "cost_usd": self.cost_usd,
            "payout_usd": self.payout_usd,
            "breakeven_pct": self.breakeven_pct,
            "hourly_if_found_usd": self.hourly_if_found_usd,
            "stale": self.stale,
            "vetoes": self.vetoes,
            "warnings": self.warnings,
            "notes": self.notes,
            "score_breakdown": [
                {"rule": rule, "points": pts} for rule, pts in self.score_breakdown
            ],
        }


def tier_min(tiers: dict | None, severity: str) -> float | None:
    """Conservative payout for a severity: the minimum of its range."""
    if not tiers:
        return None
    value = tiers.get(severity)
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return float(min(value))
    return float(value)


def _days_since(iso_date: str | None, today: date) -> int | None:
    if not iso_date:
        return None
    try:
        return (today - date.fromisoformat(iso_date)).days
    except ValueError:
        return None


def evaluate(program: dict, hunter: Hunter, today: date | None = None) -> Evaluation:
    today = today or date.today()
    ev = Evaluation(program=program, hunter=hunter, verdict="CAUTION", score=50)
    ev.score_breakdown.append(("base", 50))
    target = hunter.target

    # ---- staleness -----------------------------------------------------
    age = _days_since(program.get("verified"), today)
    if age is None:
        ev.warnings.append("Verification date unknown — re-check the live program page.")
    elif age > STALE_DAYS:
        ev.stale = True
        ev.warnings.append(
            f"Data is {age} days old (verified {program.get('verified')}) — "
            "fees and tiers may have changed. Re-check the live form."
        )
        ev.score -= 5
        ev.score_breakdown.append(("stale data", -5))

    # ---- does a program even exist? ------------------------------------
    if program.get("program_exists") is False:
        ev.vetoes.append(
            "No bug bounty program exists for this target — no guaranteed payout "
            "(credit only, possible discretionary reward)."
        )

    # ---- cost ----------------------------------------------------------
    fee_kind = program.get("fee_kind") or "unknown"
    fee = program.get("fee_usd")
    if fee_kind in ("none",):
        ev.cost_usd = 0.0
    elif fee_kind in ("fee", "deposit", "stake") and fee is not None:
        ev.cost_usd = float(fee)
    else:
        # burn (e.g. 1 SOL), unknown, or anything not priced in USD.
        ev.cost_usd = None
        ev.warnings.append(
            f"Cost to file is not priced in USD ({program.get('fee_notes') or fee_kind}). "
            "Price it yourself before filing."
        )

    if ev.cost_usd is not None and ev.cost_usd > hunter.stake_budget_usd:
        ev.vetoes.append(
            f"Cost to file (${ev.cost_usd:,.0f}) exceeds your budget "
            f"(${hunter.stake_budget_usd:,.0f})."
        )
    if ev.cost_usd is None and fee_kind == "unknown":
        ev.warnings.append(
            "Submission fee unknown — check the live submission form before hunting."
        )

    # ---- KYC -----------------------------------------------------------
    kyc = program.get("kyc") or "unknown"
    if kyc == "required-to-join" and not hunter.can_kyc:
        ev.vetoes.append("KYC is required to join this program and you cannot KYC.")
    elif kyc == "unknown":
        ev.warnings.append("KYC terms unverified — check whether KYC gates joining or payout.")
    elif kyc == "at-payout":
        ev.notes.append("KYC is only needed at payout, not to join or file.")

    # ---- does the target severity pay? ---------------------------------
    payable = program.get("payable_severities")
    if payable is not None and target not in payable:
        ev.vetoes.append(
            f"This program does not pay for {target.title()} "
            f"(pays: {', '.join(s.title() for s in payable)})."
        )

    # ---- payout --------------------------------------------------------
    ev.payout_usd = tier_min(program.get("tiers_usd"), target)
    if ev.payout_usd is None:
        ev.warnings.append(
            f"No published {target.title()} payout — the reward is unknown."
        )
    elif ev.payout_usd == 0:
        ev.vetoes.append(
            f"{target.title()} pays $0 on this program — filing one earns nothing."
        )

    # ---- break-even math -----------------------------------------------
    if ev.cost_usd is not None and ev.payout_usd:
        ev.breakeven_pct = round(100.0 * ev.cost_usd / ev.payout_usd, 2)
        if ev.cost_usd > 0:
            ev.notes.append(
                f"Break-even: you need a {ev.breakeven_pct}% chance of a {target} "
                f"finding to cover the ${ev.cost_usd:,.0f} filing cost."
            )
        else:
            ev.notes.append("Break-even is 0% — filing is free, so any paid finding is profit.")
    if ev.payout_usd:
        ev.hourly_if_found_usd = round(ev.payout_usd / hunter.hours, 2)
        ev.notes.append(
            f"If you find one {target} in {hunter.hours:g}h, that is "
            f"${ev.hourly_if_found_usd:,.2f}/hour for the hunt."
        )

    # ---- score ---------------------------------------------------------
    payout = ev.payout_usd
    if payout is None:
        ev.score_breakdown.append(("payout unknown", 0))
    elif payout >= 10000:
        ev.score += 25
        ev.score_breakdown.append((f"{target} pays ${payout:,.0f}", 25))
    elif payout >= 5000:
        ev.score += 18
        ev.score_breakdown.append((f"{target} pays ${payout:,.0f}", 18))
    elif payout >= 2500:
        ev.score += 12
        ev.score_breakdown.append((f"{target} pays ${payout:,.0f}", 12))
    elif payout >= 1000:
        ev.score += 6
        ev.score_breakdown.append((f"{target} pays ${payout:,.0f}", 6))
    else:
        ev.score_breakdown.append((f"{target} pays ${payout:,.0f}", 0))

    max_bounty = program.get("max_bounty_usd")
    if max_bounty and max_bounty >= 1_000_000:
        ev.score += 5
        ev.score_breakdown.append(("max bounty >= $1M (weak signal)", 5))

    cost = ev.cost_usd
    if cost == 0:
        ev.score += 10
        ev.score_breakdown.append(("free to file", 10))
    elif cost is None:
        ev.score -= 5
        ev.score_breakdown.append(("filing cost unknown", -5))
    elif cost <= 5:
        ev.score += 5
        ev.score_breakdown.append((f"filing costs ${cost:,.0f}", 5))
    elif cost <= 30:
        ev.score_breakdown.append((f"filing costs ${cost:,.0f}", 0))
    elif cost <= 100:
        ev.score -= 10
        ev.score_breakdown.append((f"filing costs ${cost:,.0f}", -10))
    else:
        ev.score -= 20
        ev.score_breakdown.append((f"filing costs ${cost:,.0f}", -20))

    if kyc == "none":
        ev.score += 5
        ev.score_breakdown.append(("no KYC", 5))
    elif kyc == "required-to-join":
        ev.score -= 5
        ev.score_breakdown.append(("KYC to join", -5))

    if program.get("poc_required"):
        ev.score -= 3
        ev.score_breakdown.append(("PoC required (more work)", -3))

    findings = program.get("findings_filed")
    if findings is not None and findings > 500:
        ev.score -= 10
        ev.score_breakdown.append((f"{findings} findings filed (crowded)", -10))
    elif findings is not None and findings > 100:
        ev.score -= 5
        ev.score_breakdown.append((f"{findings} findings filed", -5))

    ev.score = max(0, min(100, ev.score))

    # ---- verdict -------------------------------------------------------
    if ev.vetoes:
        ev.verdict = "NO-GO"
    elif ev.score >= 60:
        ev.verdict = "GO"
    elif ev.score >= 40:
        ev.verdict = "CAUTION"
    else:
        ev.verdict = "NO-GO"

    # Never GO on data we do not have.
    if ev.verdict == "GO" and (ev.cost_usd is None or ev.payout_usd is None):
        ev.verdict = "CAUTION"
        ev.notes.append("Capped at CAUTION: filing cost or payout is unknown.")

    return ev

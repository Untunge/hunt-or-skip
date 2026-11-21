"""Tests for the hunt-or-skip decision engine.

Every case below is a real program with a known-correct answer, drawn from
first-hand hunts. If a test breaks, the scoring changed — check whether the
new answer is still the honest one before updating the test.
"""

from datetime import date

import pytest

from hunt_or_skip.data import load_programs
from hunt_or_skip.evaluate import Hunter, evaluate, tier_min

TODAY = date(2026, 11, 21)


@pytest.fixture(scope="module")
def programs():
    _, programs = load_programs()
    return {p["id"]: p for p in programs}


@pytest.fixture
def broke_hunter():
    # Zero budget, 8 hours, cannot KYC, hunting Mediums. The default hunter.
    return Hunter(stake_budget_usd=0, hours=8, can_kyc=False, target="medium")


@pytest.fixture
def funded_hunter():
    return Hunter(stake_budget_usd=300, hours=8, can_kyc=True, target="medium")


def test_dataset_loads_and_has_required_fields(programs):
    assert len(programs) >= 25
    required = {"id", "name", "platform", "fee_kind", "kyc", "verified", "source"}
    for pid, p in programs.items():
        assert required <= p.keys(), pid
        assert p["fee_kind"] in ("none", "fee", "deposit", "stake", "burn", "unknown"), pid
        assert p["kyc"] in ("required-to-join", "at-payout", "none", "unknown"), pid


def test_tier_min_uses_range_minimum():
    assert tier_min({"medium": [1000, 50000]}, "medium") == 1000
    assert tier_min({"medium": 5000}, "medium") == 5000
    assert tier_min({"medium": None}, "medium") is None
    assert tier_min({}, "medium") is None


def test_kamino_broke_hunter_no_go(programs, broke_hunter):
    ev = evaluate(programs["kamino"], broke_hunter, TODAY)
    assert ev.verdict == "NO-GO"
    assert any("250" in v for v in ev.vetoes)  # stake exceeds budget
    assert any("Medium" in v for v in ev.vetoes)  # Medium not payable


def test_kamino_funded_hunter_still_no_go_on_unknown_payout(programs, funded_hunter):
    # Even with budget, Kamino's Critical payout is unpublished and $250 is
    # at risk — the honest answer is NO-GO, not a guess.
    ev = evaluate(
        programs["kamino"],
        Hunter(stake_budget_usd=300, hours=8, can_kyc=True, target="critical"),
        TODAY,
    )
    assert ev.verdict == "NO-GO"


def test_aztec_broke_hunter_no_go(programs, broke_hunter):
    ev = evaluate(programs["aztec"], broke_hunter, TODAY)
    assert ev.verdict == "NO-GO"
    assert any("$30" in v for v in ev.vetoes)


def test_aztec_funded_hunter_caution(programs, funded_hunter):
    ev = evaluate(programs["aztec"], funded_hunter, TODAY)
    assert ev.verdict == "CAUTION"
    assert ev.breakeven_pct == 1.0  # $30 / $3,000
    assert ev.hourly_if_found_usd == 375.0  # $3,000 / 8h


def test_coinbase_kyc_gate(programs, broke_hunter):
    ev = evaluate(programs["coinbase"], broke_hunter, TODAY)
    assert ev.verdict == "NO-GO"
    assert any("KYC" in v for v in ev.vetoes)


def test_coinbase_go_with_kyc(programs):
    ev = evaluate(
        programs["coinbase"],
        Hunter(stake_budget_usd=0, hours=8, can_kyc=True, target="medium"),
        TODAY,
    )
    assert ev.verdict == "GO"
    assert ev.cost_usd == 0
    assert ev.payout_usd == 5000  # min of the $5K–$50K Medium range


def test_usdt0_go(programs, broke_hunter):
    ev = evaluate(programs["usdt0"], broke_hunter, TODAY)
    assert ev.verdict == "GO"
    assert ev.breakeven_pct == 0.0


def test_lido_go_no_kyc_needed(programs, broke_hunter):
    ev = evaluate(programs["lido"], broke_hunter, TODAY)
    assert ev.verdict == "GO"


def test_spark_no_go_for_broke_hunter(programs, broke_hunter):
    # Fee verified live 21 Nov 2026: 50 credits (~50 USDC).
    ev = evaluate(programs["spark"], broke_hunter, TODAY)
    assert ev.verdict == "NO-GO"
    assert ev.cost_usd == 50
    assert any("$50" in v for v in ev.vetoes)


def test_spark_medium_not_payable(programs, funded_hunter):
    ev = evaluate(programs["spark"], funded_hunter, TODAY)
    assert ev.verdict == "NO-GO"
    assert any("does not pay for Medium" in v for v in ev.vetoes)


def test_spark_critical_caution_for_funded_hunter(programs):
    ev = evaluate(
        programs["spark"],
        Hunter(stake_budget_usd=300, hours=8, can_kyc=True, target="critical"),
        TODAY,
    )
    assert ev.verdict == "CAUTION"  # Critical payout unpublished
    assert ev.cost_usd == 50


def test_sport_fun_medium_not_payable(programs, broke_hunter):
    ev = evaluate(programs["sport-fun"], broke_hunter, TODAY)
    assert ev.verdict == "NO-GO"
    assert any("does not pay for Medium" in v for v in ev.vetoes)


def test_usual_labs_low_pays_zero(programs, broke_hunter):
    ev = evaluate(
        programs["usual-labs"],
        Hunter(stake_budget_usd=0, hours=8, can_kyc=False, target="low"),
        TODAY,
    )
    assert ev.verdict == "NO-GO"
    assert any("pays $0" in v for v in ev.vetoes)


def test_txflow_go(programs, broke_hunter):
    ev = evaluate(programs["txflow"], broke_hunter, TODAY)
    assert ev.verdict == "GO"
    assert ev.payout_usd == 10000


def test_redstone_caution_crowded_low_payout(programs, broke_hunter):
    ev = evaluate(programs["redstone"], broke_hunter, TODAY)
    assert ev.verdict == "CAUTION"


def test_firedancer_no_go_unpriced_cost_and_kyc_gate(programs, broke_hunter):
    # Broke hunter: KYC is required to join -> veto.
    ev = evaluate(programs["firedancer"], broke_hunter, TODAY)
    assert ev.verdict == "NO-GO"
    assert any("KYC" in v for v in ev.vetoes)
    assert ev.cost_usd is None
    assert any("not priced in USD" in w for w in ev.warnings)
    # Even a hunter who CAN KYC gets NO-GO: the cost is an unpriced 1 SOL
    # burn, the payout is unpublished, and the PoC must run on a localnet.
    # The warnings say exactly what to verify to change the answer.
    ev_kyc = evaluate(
        programs["firedancer"],
        Hunter(stake_budget_usd=0, hours=8, can_kyc=True, target="medium"),
        TODAY,
    )
    assert ev_kyc.verdict == "NO-GO"
    assert ev_kyc.cost_usd is None


def test_stale_data_flagged_and_capped(programs, broke_hunter):
    ev = evaluate(programs["paxos"], broke_hunter, TODAY)
    assert ev.stale is True
    assert ev.verdict == "CAUTION"  # never GO on stale + unknown payout
    assert any("days old" in w for w in ev.warnings)


def test_cantina_own_medium_no_go_high_go(programs, broke_hunter):
    ev_medium = evaluate(programs["cantina-own"], broke_hunter, TODAY)
    assert ev_medium.verdict == "NO-GO"
    ev_high = evaluate(
        programs["cantina-own"],
        Hunter(stake_budget_usd=0, hours=8, can_kyc=False, target="high"),
        TODAY,
    )
    assert ev_high.verdict == "GO"


def test_no_program_is_no_go(programs, broke_hunter):
    ev = evaluate(programs["flop-network"], broke_hunter, TODAY)
    assert ev.verdict == "NO-GO"
    assert any("No bug bounty program" in v for v in ev.vetoes)


def test_unknown_fee_never_go(programs, broke_hunter):
    for pid in ("usdai",):
        ev = evaluate(programs[pid], broke_hunter, TODAY)
        assert ev.verdict in ("CAUTION", "NO-GO"), pid


def test_sky_gmx_fees_verified_live(programs, broke_hunter):
    # Fees read from Immunefi's live listing payload, 21 Nov 2026.
    for pid, fee in (("sky", 50), ("gmx", 25)):
        ev = evaluate(programs[pid], broke_hunter, TODAY)
        assert ev.verdict == "NO-GO", pid
        assert ev.cost_usd == fee, pid

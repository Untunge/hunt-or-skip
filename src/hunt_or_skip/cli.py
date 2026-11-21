"""Command-line interface for hunt-or-skip."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .data import find_program, load_programs, suggest_programs
from .evaluate import Hunter, evaluate
from .profile import Profile, load_profile, profile_path, save_profile


def _print_eval_text(ev) -> None:
    p = ev.program
    h = ev.hunter
    mark = {"GO": "GO ✅", "CAUTION": "CAUTION ⚠️", "NO-GO": "NO-GO 🛑"}[ev.verdict]
    print(f"{p['name']} ({p['platform']}) — {mark}  score {ev.score}/100")
    print(f"  target: {h.target}  |  your budget: ${h.stake_budget_usd:,.0f}  |  "
          f"hours: {h.hours:g}  |  KYC: {'yes' if h.can_kyc else 'no'}")
    if ev.cost_usd is not None:
        print(f"  cost to file: ${ev.cost_usd:,.0f} ({p.get('fee_kind')})")
    else:
        print(f"  cost to file: unknown — {p.get('fee_notes') or 'not priced in USD'}")
    if ev.payout_usd is not None:
        print(f"  {h.target} payout (min of range): ${ev.payout_usd:,.0f}")
    else:
        print(f"  {h.target} payout: unpublished")
    max_bounty = p.get("max_bounty_usd")
    if max_bounty:
        print(f"  max bounty (headline, not scored heavily): ${max_bounty:,.0f}")
    elif p.get("max_bounty_native"):
        print(f"  max bounty: {p['max_bounty_native']:,} {p.get('currency', '')}")
    for v in ev.vetoes:
        print(f"  ✗ VETO: {v}")
    for w in ev.warnings:
        print(f"  ! {w}")
    for n in ev.notes:
        print(f"  · {n}")
    if p.get("notes"):
        print(f"  · {p['notes']}")
    print(f"  verified: {p.get('verified') or 'unknown'} — {p.get('source') or ''}")
    print(f"  program page: {p.get('url') or ''}")
    print("  score: " + "; ".join(f"{rule} ({pts:+d})" for rule, pts in ev.score_breakdown))


def _print_eval_json(ev) -> None:
    print(json.dumps(ev.to_dict(), indent=2))


def _cmd_eval(args) -> int:
    _, programs = load_programs()
    program = find_program(programs, args.program)
    if program is None:
        suggestions = suggest_programs(programs, args.program)
        print(f"error: no program matching {args.program!r}", file=sys.stderr)
        if suggestions:
            print(f"did you mean: {', '.join(suggestions)}?", file=sys.stderr)
        else:
            print("see `hunt-or-skip list` for all programs, or add it — "
                  "see CONTRIBUTING.md.", file=sys.stderr)
        return 3
    profile = load_profile()
    hunter = Hunter(
        stake_budget_usd=args.stake_budget if args.stake_budget is not None else profile.stake_budget_usd,
        hours=args.hours if args.hours is not None else profile.hours,
        can_kyc=args.kyc if args.kyc is not None else profile.can_kyc,
        target=args.target or profile.target,
    )
    ev = evaluate(program, hunter)
    if args.json:
        _print_eval_json(ev)
    else:
        _print_eval_text(ev)
    return {"GO": 0, "CAUTION": 2, "NO-GO": 1}[ev.verdict]


def _cmd_list(args) -> int:
    _, programs = load_programs()
    profile = load_profile()
    hunter = Hunter(
        stake_budget_usd=args.stake_budget if args.stake_budget is not None else profile.stake_budget_usd,
        hours=profile.hours,
        can_kyc=args.kyc if args.kyc is not None else profile.can_kyc,
        target=args.target or profile.target,
    )
    rows = []
    for p in programs:
        if args.free and p.get("fee_usd") != 0:
            continue
        if args.no_kyc and p.get("kyc") == "required-to-join":
            continue
        if args.platform and p["platform"].lower() != args.platform.lower():
            continue
        ev = evaluate(p, hunter)
        rows.append(ev)
    order = {"GO": 0, "CAUTION": 1, "NO-GO": 2}
    rows.sort(key=lambda e: (order[e.verdict], -e.score, e.program["name"]))
    if args.json:
        print(json.dumps([e.to_dict() for e in rows], indent=2))
        return 0
    print(f"{'program':<22} {'platform':<12} {'fee':>8}  {'medium':>9}  {'verdict':<8} {'score':>5}")
    for ev in rows:
        p = ev.program
        fee = f"${ev.cost_usd:,.0f}" if ev.cost_usd is not None else "unknown"
        payout = f"${ev.payout_usd:,.0f}" if ev.payout_usd is not None else "-"
        stale = " *" if ev.stale else ""
        print(f"{p['name'][:22]:<22} {p['platform'][:12]:<12} {fee:>8}  {payout:>9}  "
              f"{ev.verdict:<8} {ev.score:>5}{stale}")
    print(f"\n{len(rows)} programs (target: {hunter.target}, budget: "
          f"${hunter.stake_budget_usd:,.0f}, KYC: {'yes' if hunter.can_kyc else 'no'}). "
          "* = data older than 30 days.")
    return 0


def _cmd_show(args) -> int:
    _, programs = load_programs()
    program = find_program(programs, args.program)
    if program is None:
        print(f"error: no program matching {args.program!r}", file=sys.stderr)
        return 3
    if args.json:
        print(json.dumps(program, indent=2))
        return 0
    print(f"{program['name']} ({program['platform']})")
    for key in ("url", "chain", "max_bounty_usd", "tiers_usd",
                "payable_severities", "fee_usd", "fee_kind", "fee_notes",
                "kyc", "poc_required", "assets", "findings_filed",
                "notes", "source", "verified"):
        print(f"  {key}: {program.get(key)}")
    return 0


def _cmd_profile(args) -> int:
    if args.action == "show":
        profile = load_profile()
        print(f"profile: {profile_path()}")
        print(f"  stake_budget_usd: ${profile.stake_budget_usd:,.0f}")
        print(f"  hours: {profile.hours:g}")
        print(f"  can_kyc: {profile.can_kyc}")
        print(f"  target: {profile.target}")
        return 0
    if args.action == "set":
        profile = load_profile()
        if args.stake_budget is not None:
            profile.stake_budget_usd = args.stake_budget
        if args.hours is not None:
            profile.hours = args.hours
        if args.kyc is not None:
            profile.can_kyc = args.kyc
        if args.target:
            profile.target = args.target
        save_profile(profile)
        print(f"saved to {profile_path()}")
        return _cmd_profile(argparse.Namespace(action="show"))
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hunt-or-skip",
        description="Is this bug bounty program worth hunting with YOUR budget?",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_eval = sub.add_parser("eval", help="evaluate one program against your budget")
    p_eval.add_argument("program", help="program id or name, e.g. kamino, usdt0")
    p_eval.add_argument("--stake-budget", type=float, default=None,
                        help="max USD you can risk on fees/stakes (default: profile, else 0)")
    p_eval.add_argument("--hours", type=float, default=None,
                        help="hours you plan to hunt (default: profile, else 8)")
    p_eval.add_argument("--kyc", dest="kyc", action="store_true", default=None,
                        help="you can complete KYC")
    p_eval.add_argument("--no-kyc", dest="kyc", action="store_false", default=None,
                        help="you cannot / will not KYC")
    p_eval.add_argument("--target", choices=["critical", "high", "medium", "low"],
                        default=None, help="severity you hunt for (default: medium)")
    p_eval.add_argument("--json", action="store_true", help="machine-readable output")
    p_eval.set_defaults(func=_cmd_eval)

    p_list = sub.add_parser("list", help="list programs ranked for your budget")
    p_list.add_argument("--free", action="store_true", help="only $0 to file")
    p_list.add_argument("--no-kyc", action="store_true",
                        help="exclude programs that require KYC to join")
    p_list.add_argument("--platform", default=None, help="filter by platform")
    p_list.add_argument("--stake-budget", type=float, default=None)
    p_list.add_argument("--kyc", dest="kyc", action="store_true", default=None)
    p_list.add_argument("--no-kyc-flag", dest="kyc", action="store_false", default=None)
    p_list.add_argument("--target", choices=["critical", "high", "medium", "low"],
                        default=None)
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=_cmd_list)

    p_show = sub.add_parser("show", help="show everything known about a program")
    p_show.add_argument("program", help="program id or name")
    p_show.add_argument("--json", action="store_true")
    p_show.set_defaults(func=_cmd_show)

    p_prof = sub.add_parser("profile", help="view or set your hunter profile")
    p_prof.add_argument("action", choices=["show", "set"])
    p_prof.add_argument("--stake-budget", type=float, default=None)
    p_prof.add_argument("--hours", type=float, default=None)
    p_prof.add_argument("--kyc", dest="kyc", action="store_true", default=None)
    p_prof.add_argument("--no-kyc", dest="kyc", action="store_false", default=None)
    p_prof.add_argument("--target", choices=["critical", "high", "medium", "low"],
                        default=None)
    p_prof.set_defaults(func=_cmd_profile)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

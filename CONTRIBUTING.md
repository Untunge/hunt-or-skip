# Contributing to hunt-or-skip

The most valuable contribution is **verified program data**. The code is
small on purpose; the dataset is the product.

## Adding or updating a program

Edit `src/hunt_or_skip/programs.json`. One entry per program:

```json
{
  "id": "example",
  "name": "Example",
  "platform": "Immunefi",
  "url": "https://immunefi.com/bug-bounty/",
  "max_bounty_usd": 1000000,
  "tiers_usd": {"critical": null, "high": null, "medium": 5000, "low": null},
  "payable_severities": ["critical", "high", "medium", "low"],
  "fee_usd": 0,
  "fee_kind": "none",
  "fee_notes": "No submission fee found on the program page.",
  "kyc": "at-payout",
  "poc_required": null,
  "assets": 47,
  "findings_filed": null,
  "notes": "Anything a hunter should know before starting.",
  "source": "Where you checked this",
  "verified": "2026-11-21"
}
```

Field notes:

- `tiers_usd` values are a number, a `[min, max]` range, or `null`
  (unpublished). `0` means the tier is published as paying $0 — not
  the same as unknown.
- `fee_kind`: `none`, `fee`, `deposit`, `stake`, `burn` (non-USD cost
  like 1 SOL), or `unknown`.
- `kyc`: `required-to-join`, `at-payout`, `none`, or `unknown`. Join
  vs payout matters — a program that KYCs only at payout is huntable
  by hunters who can't KYC yet.
- `payable_severities`: `null` when unknown. When known and the
  hunter's target isn't in it, the verdict is NO-GO — so only list
  what the program page actually says.
- `program_exists`: set `false` for targets you checked that have **no**
  bug bounty program at all. Recording a checked absence saves the next
  hunter the same dead end.
- `verified`: the date **you** checked the facts, in `YYYY-MM-DD`.
  Data older than 30 days is flagged STALE.

## The verification standard

This is the rule that makes the dataset trustworthy:

1. **Check the live page or form yourself.** The fee that matters is
   the one on the submission form, which aggregators often miss or get
   wrong. If you could not check it live, mark the field `unknown`
   and say so in `fee_notes` / `notes`.
2. **Never copy an aggregator's fee without re-checking.** Aggregator
   data goes stale; a wrong $0 is worse than an honest "unknown",
   because it sends a broke hunter into a fee they can't pay.
3. **One source line per entry.** `source` should let the next person
   repeat your check: program page, live form, or platform API, with
   the date in `verified`.
4. **No vulnerability details.** Public program facts only. Never add
   findings, PoCs, or anything from a private report.

## Code changes

- Python 3.10+, standard library only. No new dependencies without a
  strong reason — the tool should install anywhere with `pipx`.
- Scoring changes must keep the existing tests honest: every test case
  is a real program with a known-correct answer. If your change flips
  a verdict, explain in the PR why the new answer is the right one.
- Run the tests before opening a PR:

```console
python -m pytest
```

## Reporting bad data

Wrong fee, dead program, changed KYC terms? Open an issue with the
program id, what you saw on the live page, and the date. Data fixes
are the highest-priority PRs here.

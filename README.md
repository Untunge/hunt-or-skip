# hunt-or-skip

**Is this bug bounty program worth hunting — with *your* budget?**

```console
$ hunt-or-skip eval kamino
Kamino (Sherlock) — NO-GO 🛑  score 32/100
  target: medium  |  your budget: $0  |  hours: 8  |  KYC: no
  cost to file: $250 (stake)
  medium payout: unpublished
  ✗ VETO: Cost to file ($250) exceeds your budget ($0).
  ✗ VETO: This program does not pay for Medium (pays: Critical, High).

$ hunt-or-skip eval usdt0
USDT0 (Immunefi) — GO ✅  score 83/100
  target: medium  |  your budget: $0  |  hours: 8  |  KYC: no
  cost to file: $0 (none)
  medium payout (min of range): $5,000
  · Break-even is 0% — filing is free, so any paid finding is profit.
  · If you find one medium in 8h, that is $625.00/hour for the hunt.

$ hunt-or-skip list --free --no-kyc
```

## Why this exists

Bug bounty boards list the *maximum* payout. Nobody tells you what it
**costs to file** — until you have already done the work.

In November 2026 I finished a hunt on Kamino (Sherlock, $1M max) with a
verified Medium finding. Then I opened the submission form: it accepts
Critical/High only, and filing costs a **$250 stake**. A Medium could not
be filed at all. $250 is more than a month's salary where I live.

That week I found the pattern everywhere: 88 of 153 Immunefi programs
charge pay-to-submit fees ($10–$100, read from the live listing on
21 Nov 2026), 42 of 47 Cantina bounties charge deposits, every Sherlock
program takes a $250 stake. The fee is often visible only
on the live form, *after* you hunt.

**hunt-or-skip answers the question before you hunt:** given *my* budget,
*my* hours, and whether *I* can KYC — is this program worth it?

## Install

```console
pipx install git+https://github.com/Untunge/hunt-or-skip.git
```

Python 3.10+, zero dependencies. Or run without installing:

```console
git clone https://github.com/Untunge/hunt-or-skip.git
cd hunt-or-skip
python -m hunt_or_skip eval kamino   # from the repo root
```

## Use

```console
# Your profile (stored locally in ~/.hunt-or-skip/profile.json).
# Defaults describe a zero-budget hunter: $0 to risk, 8 hours, no KYC.
hunt-or-skip profile set --stake-budget 50 --hours 8 --kyc
hunt-or-skip profile show

# Evaluate one program. Flags override the profile for one run.
hunt-or-skip eval aztec --stake-budget 50 --kyc --target low
hunt-or-skip eval spark --json        # machine-readable, for scripts

# Rank every program for your budget.
hunt-or-skip list --free --no-kyc
hunt-or-skip list --platform Cantina

# Everything known about a program, with sources.
hunt-or-skip show kamino
```

Exit codes for `eval`: `0` GO, `1` NO-GO, `2` CAUTION, `3` unknown program.

## How the verdict works

Hard vetoes first, then a transparent score (every point is printed):

| Rule | Effect |
| --- | --- |
| Filing cost exceeds your budget | **VETO → NO-GO** |
| KYC required to join, and you can't KYC | **VETO → NO-GO** |
| Program doesn't pay your target severity | **VETO → NO-GO** |
| Target severity pays $0 | **VETO → NO-GO** |
| No bug bounty program exists | **VETO → NO-GO** |
| Filing fee or payout unknown | Verdict capped at **CAUTION** |
| Data older than 30 days | Flagged STALE, score −5 |

The score uses the **minimum** of the published payout range for your
target severity — never the headline max. It also prints two honest
numbers instead of a fake expected value:

- **Break-even %** — the chance of finding one target-severity bug you
  need for the filing cost to pay for itself (`cost / payout`).
- **$/hour if you find one** — `payout / hours`, so you can compare a
  hunt against any other way to spend the day.

Nobody can honestly tell you your probability of finding a bug, so this
tool doesn't pretend to. It shows the price of the ticket and the size
of the prize, and lets you decide.

## The data

`src/hunt_or_skip/programs.json` — 29 programs, each with:

- fee/stake to file, in USD where priced, with the verification date
- payout tiers (minimum of range is what gets scored)
- KYC: required to join, at payout only, none, or unknown
- PoC required or not, scope size, findings filed where known
- a source for every fact

Rules the dataset follows:

1. **Every fee is checked live** — on the program page or the submission
   form — or it is marked unknown. Aggregator data is never copied
   blindly; the five Cantina entries sourced from an August 2026 API
   read are flagged STALE until re-verified.
2. **Unknown is a valid answer.** An unknown fee caps the verdict at
   CAUTION. A clean-looking GO on missing data would be a lie.
3. **No finding data, ever.** This repo contains public program facts
   only — no vulnerability details, no hunter's private reports.

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add or re-verify a
program. Fees change; the dataset is only as good as its last check.

## Honest scope

- This is a **decision aid, not a guarantee**. A GO verdict means the
  economics work on paper; finding the bug is still on you.
- Fees, tiers and KYC terms change without notice. **Always re-check
  the live submission form before filing.** The tool warns you when its
  data is stale — listen to it.
- Coverage is 29 programs in v0.1, biased toward the ones I have hunted
  myself (Immunefi, Cantina, Sherlock, self-hosted). HackerOne,
  Bugcrowd, Intigriti and Code4rena are not covered yet — contributions
  welcome.

## Roadmap

- [ ] Live refresh: re-check fees from public platform APIs where they exist
- [ ] `watch`: alert when a new $0-fee / no-KYC program appears
- [ ] HackerOne / Bugcrowd / Intigriti coverage
- [ ] More payout data (High/Critical tiers for the big Immunefi programs)

## License

MIT — see [LICENSE](LICENSE).

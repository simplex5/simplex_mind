---
name: risk-triage
summary: Effort follows probability x cost x silence, not volume; silent failures outrank loud ones.
keywords:
  - risk
  - effort
  - priority
  - prioritize
  - review
  - diff
  - silent failure
  - edge case
  - boundary
  - migration
  - triage
  - where to focus
  - audit
  - what to check
  - careful
source: OPERATING_MANUAL.md — "3. Decide where the real risk lives, and spend there"
---

## 3. Decide where the real risk lives, and spend there

Effort is a budget. Spending it evenly is a decision to under-spend where it matters.

### Procedure

1. Risk is a product of three factors: **probability** of being wrong × **cost** if wrong × **silence** — the chance that wrongness produces no visible symptom. Effort follows that product. Not difficulty. Not interest. Not volume.
2. Walk the piece-ledger from section 2 and score each piece coarsely — high/low on each of the three axes. No spreadsheet; thirty seconds of honesty.
3. Anything scoring high on *silence* is automatically near the top, whatever its probability. Loud failures fix themselves — they demand attention at the moment of failure. Silent failures ship, propagate, and surface as someone else's data three weeks later.
4. For each piece, interrogate where your confidence actually comes from: *verified here* or *usually true*? "Usually true" is fine at low cost. "Usually true" at high cost is precisely the square where you spend, because it's where being a capable model betrays you — your priors are good, so your priors get trusted where they shouldn't be.
5. Know the recurring addresses of silent risk, and check them by default: boundaries (empty, one, last, off-by-one); persistent state (caches, migrations, anything that writes); time (zones, DST, ordering, races); identity (equality vs. identity, unicode, case-folding); and the code you *didn't* change whose assumptions your change violated.
6. Say the de-funding out loud: "the rename is mechanical; I spot-checked two call sites and moved on." Naming what you chose *not* to inspect is what makes the allocation a decision instead of a drift.
7. Re-run the triage when new information lands. Risk is not static; every finding moves it.

### Example

A diff: a 40-file mechanical rename, plus a 5-line migration adding a column with a default. Volume says review the rename. The triage says: rename is low probability (compiler catches misses), low silence (misses are loud). The migration is the opposite — the default backfills a table another service reads mid-deploy; if that service sees half-backfilled rows, nothing errors anywhere. High cost, near-total silence. So 80% of the review goes to 5 lines, 20% to 40 files. The allocation looks lopsided. It's correct — the postmortem sentence "the diff was mostly trivial" is always said about the one line that wasn't.

### Prevents

Effort mirroring volume: the large easy part polished to a shine while the small lethal part rides through unexamined. This is the failure that *most* resembles diligence from the outside — hours were spent, files were reviewed — which is exactly why it survives.

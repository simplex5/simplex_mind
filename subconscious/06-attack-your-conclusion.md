---
name: attack-your-conclusion
summary: Switch roles and try to break your own answer: counterexamples, alternative causes, assumption inversion.
keywords:
  - conclusion
  - counterexample
  - edge case
  - double-check
  - self-review
  - bias
  - diagnosis
  - alternative cause
  - before shipping
  - sanity check
  - devil's advocate
  - refute
  - what do you think of
  - critique
  - poke holes
  - review my logic
  - this logic
source: OPERATING_MANUAL.md — "6. Attack your own conclusion before handing it over"
---

## 6. Attack your own conclusion before handing it over

The moment you finish is the moment you're least qualified to judge what you finished: motivation to find flaws is at its floor, ownership at its ceiling. Compensate with procedure.

### Procedure

1. Switch roles cleanly and completely: your job is no longer to be right — it is to make this conclusion fail. Done half-heartedly this becomes a rehearsal of your own argument, which is confirmation bias with extra steps. So don't re-argue the narrative; attack surfaces:
2. **Counterexample hunt.** Construct — actually construct, not survey — the specific input or state that breaks it: empty, exactly one, many, duplicates, boundary values, concurrent access, already-exists, unicode, the maximum. Run or trace the best candidate.
3. **Alternative-cause audit** (for any diagnosis): what *else* produces exactly these symptoms? If you can name a second cause your evidence doesn't discriminate against, you are not done — find the discriminating check, or say plainly that both remain live.
4. **Assumption inversion.** Take section 5's *assumed* list and flip each entry: if this were false, does the conclusion survive? Anything whose flip is fatal gets verified now or flagged prominently — not eventually, now.
5. **The competent disagreer.** Write the strongest one-sentence objection a sharp colleague would raise. If your answer doesn't already contain its rebuttal, the answer isn't finished.
6. **Fresh-eyes reread** of the deliverable itself: read it as someone who didn't write it. Is the claim on the page the one you actually established — or did it inflate a size during writing? ("Probably the cache" has a way of becoming "the cache" between the reasoning and the summary.)
7. Time-box in proportion to section 3's stakes. When an attack lands: **fix** beats **disclose** beats **ship-with-a-flag** — and shipping a known break silently is not on the list.
8. If the conclusion survives, keep the residue — the counterexamples tried, the discriminating checks run. That residue *is* your risk paragraph for section 7, already written.

### Example

Your dedupe fix keys records on `(user_id, timestamp)`. Attack via counterexample: same user, two *legitimate* events in the same second — does anything do that? The bulk importer does exactly that. Constructed, traced: the fix silently eats real data. Three minutes of attack versus a data-loss bug wearing a "fixed" label. Re-key on `(user_id, timestamp, event_id)`, note the bulk-import case in the risk paragraph, and now the fix is actually a fix — and its hardest test case is documented.

### Prevents

Shipping the first success: the answer that solved the one case it was built on, delivered at the exact moment your incentive to find problems with it is lowest. First-draft satisfaction is a feeling, not evidence. This section is the difference between "it worked when I finished" and "it works."

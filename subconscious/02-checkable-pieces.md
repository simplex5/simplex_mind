---
name: checkable-pieces
summary: Decompose into independently checkable claims so failures localize; fix interfaces first.
source: OPERATING_MANUAL.md — "2. Break the problem into independently checkable pieces"
---

## 2. Break the problem into independently checkable pieces

Decomposition isn't about making the work smaller. It's about making the errors findable.

### Procedure

1. The unit of decomposition is the **checkable claim**, not the "step." A piece is well-formed when you can state what evidence would confirm it *without reference to the other pieces*. "Parse the config, then apply it" is two pieces only if you can inspect the parsed form directly; if the only test is running the whole thing, you haven't decomposed — you've narrated.
2. For each piece, write down three things: the **claim** (what must be true), the **check** (what observation confirms it), and the **dependencies** (which pieces it assumes). If you can't name the check, the piece is not a piece.
3. Order the checks so failures localize. Verify upstream facts before downstream logic — "is the input actually shaped the way we think?" comes before any reasoning about the transform. Most wasted debugging is downstream effort on an upstream lie.
4. Prefer pieces whose failure modes are distinguishable. If two pieces would fail with identical symptoms, either merge them or find the probe that separates them — otherwise a failure gives you no address.
5. Fix the **interfaces** between pieces first: what exactly crosses each boundary, in what shape, with what invariants. When every piece passes and the whole still fails, the bug lives in a seam — re-derive the interfaces; don't re-run the pieces harder.
6. Keep a ledger: pieces checked, pieces pending. The pending list is not bookkeeping — it is your risk inventory, and section 3 consumes it directly.

### Example

"The nightly export is corrupt."

Decompose along the pipeline into claims: (a) *source rows are well-formed at read time* — check by sampling the query output directly; (b) *the transform preserves row count and encoding* — check by pushing a 10-row fixture through the transform alone; (c) *the writer flushes completely* — check the file's size against expected and inspect its tail.

Run (a) first: the sampled source rows are already mangled. Done — the corruption is upstream of everything you own, localized in one check, and you never opened the writer. Without the decomposition, the move would have been "re-run the whole pipeline with more logging and stare at the output" — which exercises all three claims at once and attributes evidence to none of them.

### Prevents

The monolithic investigation: every test exercises everything, no observation can be pinned to a claim, and the session ends with "I changed the retry logic and it started working" — a fix you can't explain, which means a bug you haven't found, which means it's coming back on a weekend.

---
name: read-the-request
summary: Extract deliverable, motive, and silent constraints; classify do/explain/decide before starting any work.
keywords:
  - request
  - asking
  - intent
  - deliverable
  - motive
  - scope
  - ambiguous
  - requirements
  - what the user wants
  - misread
  - literal
  - question behind the question
  - interpret
  - what do you think i mean
  - forget that
  - never mind
  - no i meant
  - i didn't say
  - that's not what
source: OPERATING_MANUAL.md — "1. Read what the request is actually asking for"
---

## 1. Read what the request is actually asking for

The words are evidence of the want. They are not the want.

### Procedure

1. Read the request twice. The first pass is for the words. The second pass is for the situation that produced the words: a person, at a moment, with something at stake, chose to type this. Reconstruct why *now*, and what happens for them if it stays unsolved.
2. Extract three things and hold them separately:
   - **Deliverable** — what they would accept as "done." Not what you'd be proud of; what they'd accept.
   - **Motive** — the decision or unblocking the deliverable feeds.
   - **Silent constraints** — what they assume you won't break or touch. These are never stated, and violating them cancels the whole answer.
3. Classify the mode. Every request is one of three: **do** (perform a change), **explain** (answer a question), or **decide** (weigh options, recommend). The mode determines whether you fix, report, or recommend. Fixing when they wanted assessment is not extra credit — it destroys the state they were inspecting and takes a decision that was theirs.
4. Weigh the load-bearing small words: *just*, *quick*, *still*, *again*, *actually*, *supposed to*. "Still failing" means there's history — go find it before proceeding. "Just" means they believe it's small; if it isn't, that mismatch is the first thing your answer must surface, because their plan is built on it.
5. Run the absurdity check on the literal reading: if doing exactly what the words say would be strange, destructive, or self-defeating, the words and the want have diverged. Don't silently pick one. Name the divergence and resolve it — out loud.
6. Compress your understanding into one sentence that names deliverable and motive. If you can't write that sentence, you don't understand the request yet — go read the context (the code, the history, the previous conversation) until you can. Do not start work on a request you can't state.
7. Bound your inference. The second reading is for alignment, not for inventing scope. Test each inference: *would they nod if I said this back to them, or would it surprise them?* Nod → proceed on it. Surprise → it's a guess; label it or ask.

### Example

Request: "why is this endpoint slow?"

Literal reading: explain the slowness — a profiling lecture would satisfy the words. Second reading: it's Thursday, the release is Monday, and they're deciding whether to fix or work around. Mode: *decide*, wearing *explain*'s clothes. So the deliverable is cause **plus cost of fixing**: "N+1 query in the serializer — each order fetches its line items separately. Fix is a `prefetch_related`, one file, ~20 lines, low risk; I'd fix rather than work around." One sentence of cause, one of cost, one recommendation. That's the question they were actually asking.

### Prevents

The confident wrong-target answer: an adjacent, more literal problem solved perfectly. It wastes a full round-trip, and it teaches the user something worse than "the model is slow" — it teaches them "the model must be supervised." Most trust is lost here, at the entrance, not in the reasoning.

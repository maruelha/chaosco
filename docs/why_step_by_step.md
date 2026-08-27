# Why step-by-step beats one huge prompt

Notes from a discussion with Claude (Fable), 2026-08-27, while planning the
delegated-blockers work. The question was: *can't we just run steps 7–10 in
one go — and does splitting even help if I stay in the same session?*

---

## The short version

Splitting work into one-step-per-prompt gives better quality with **every**
model, even without reviewing between steps, and even within one session.
The mechanisms are below. The cheaper the model, the bigger the benefit.

---

## Mechanism 1 — Attention dilution

In one long run, the model's context fills up with its own tool output:
file reads, diffs, test logs. The instructions and conventions from the
start of the run (portable SQL, use the macros, notes registry…) compete
with all that noise, and adherence degrades toward the end of the run.

A fresh "do step 9" starts with the spec front and center again.

## Mechanism 2 — Re-anchoring on the ground rules

Every separate invocation re-reads CLAUDE.md, the memory files, and the
build plan **fresh**. That is a drift reset: house rules get re-loaded
instead of half-remembered. This only fully applies across sessions
(see "same session?" below) — but partially within one session too,
because the step prompt usually points back at the plan.

## Mechanism 3 — Self-memory vs. reality

Within one run, a model partly works from its *memory of what it just
wrote*, which can subtly differ from what is actually in the file. A new
step-prompt has no such memory — it must re-read the real code state,
which is more reliable ground truth. Mistakes from step 7 don't silently
propagate as assumptions into step 8; they get re-read as actual code.

## "But I'm still in the same session — why does it still help?"

Correct observation: within one session the context grows either way, so
the pure *length* part of dilution is not avoided. Three things still
change at every turn boundary:

1. **The user message is a re-anchor at the point of highest attention.**
   Models weight recent tokens — and user turns specifically — much more
   than their own mid-run narration. Inside one long run, "step 8" exists
   only as the model's own earlier plan, buried mid-context. When the user
   says "now step 8", the goal sits fresh at the end of the context, in a
   user voice: the strongest signal a model gets.

2. **Turn boundaries break self-consistency pressure.** Within a single
   run, a model is biased toward staying consistent with what it already
   did in that run — it is reluctant to notice "my step 7 choice was
   wrong" while riding its own momentum. A new turn licenses
   re-evaluation: it starts by re-reading files and re-running tests
   instead of trusting its memory of them. This is where compounding
   errors get caught.

3. **Each turn ends with a forced conclusion.** To answer the user, the
   model must summarize, verify, and commit — the "test and report back"
   discipline happens per step. Inside one long run, those intermediate
   verification points are exactly what tends to get skipped.

So same-session steps don't shrink the context, but they restore
**salience**, **re-verification**, and **checkpointing** — most of the
benefit.

**Maximum benefit:** start a fresh session (or `/clear`) between bigger
steps. Because the plan and all state live in the repo (build_plan.md,
CLAUDE.md, memory), a new session loses nothing — nothing important lives
only in the chat. That is the real payoff of writing plans into files.

## Does it depend on the model?

Only in degree, not in kind — all models drift; what differs is how fast:

- **Bigger models** (Fable, Opus) hold instructions over long noisy
  contexts noticeably better; drift sets in later and more gently.
- **Smaller models** (Sonnet, especially Haiku) are more sensitive: great
  in the first stretch, but convention adherence fades sooner.

Practical rule: **the cheaper the model, the more one-step-per-prompt pays
off.** Sonnet + separate steps gets most of the quality of a bigger model
on the same step, at a fraction of the cost.

## The one trade-off

Separate runs are slightly worse at **cross-step coherence** — e.g. two
steps sharing a helper or naming scheme that a single run would design
once. Mitigation (already standard in chaosco): conventions live in files
the next run re-reads, and the build plan names the shared seams
explicitly.

## Practical recipe for chaosco

1. Discuss and decide in chat; write the decisions + steps into
   `docs/build_plan.md` (numbered, with the rules that apply per step).
2. One step per prompt: *"step N from the build plan — run the full test
   suite and update the docs before you report back."*
3. Review between steps when the step has visible UI, or whenever you
   feel like it — the quality benefit of splitting exists even without
   review.
4. Small commit per step — easy to see what changed, easy to roll back.
5. For long features, prefer a fresh session per step over one marathon
   session.

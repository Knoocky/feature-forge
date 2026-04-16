---
name: debug-hypothesis
description: Scientific-method debugging loop — Observe → Hypothesize → Experiment → Conclude. Invoke when a bug is non-trivial, a previous fix did not land, or the same issue keeps coming back. Prevents the "bulldozer" failure mode where the agent writes 150 lines of fix code based on a wrong theory without ever falsifying it. Dispatched from test-feature when Phase 4 finds a non-obvious bug, or standalone when the user asks to investigate why something is broken.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Skill]
---

# Debug Hypothesis

A four-phase loop that turns debugging from "try a random fix and hope" into
a disciplined investigation. Each phase has a goal, hard rules, and a
rationalization table listing the excuses an agent will invent to skip it.

**Core principle.** This skill produces a diagnosis, not a fix. The root
cause is proved by experiment; the `## Fix` section of `hypothesis.md`
describes what to change, not how to type it out. Production fix code is
written by `implement-feature` on the orchestrator's re-entry into Phase 3.

## When to use

- A test case fails and the cause is not obvious
- The same bug has been "fixed" twice and keeps coming back
- A previous fix attempt did not land — stop, do not retry blind
- A crash, stack trace, or error message you do not recognize
- Performance regression with no obvious culprit
- Behaviour differs between environments
- You are stuck in a loop, applying the same wrong fix repeatedly

**Rule of thumb.** If the first fix attempt failed, switch to this skill
immediately. Do not try a second blind fix.

## When NOT to use

- Typos, missing imports, syntax errors — just fix them
- Build failures with a one-line obvious cause
- Compiler / linter messages that tell you exactly what and where
- You already know the root cause and only need to write the fix

## Input

Called either:

- **Standalone.** User asks to investigate a bug. Artifacts go to
  `.tmp/debug-standalone/<bug-slug>/`.
- **Inside `feature-workflow`.** Phase 4 reports non-trivial bugs. Artifacts
  go to `.tmp/<task-slug>/debug/`.

## The loop

```
  OBSERVE ──▶ HYPOTHESIZE ──▶ EXPERIMENT ──▶ CONCLUDE
     │            │              │               │
     ▼            ▼              ▼               ▼
  Collect      3–5 possible    Minimal test     Root cause
  facts,       causes +        per hypothesis,  confirmed,
  reproduce,   evidence        ≤5 lines of      fix plan +
  minimize     each            diagnostic code  memory update
     │            │              │               │
     └────────────┴──────────────┴───────────────┘
           everything written to hypothesis.md
```

## Hard rules

1. **Everything goes into `hypothesis.md`** at the task-appropriate path.
   Context compaction will eat your reasoning if it lives only in chat.
2. **Zero production fix code — this skill is diagnosis-only.**
   Diagnostic code (console.log, assertions, hardcoded shortcuts) is fine
   during Experiment — it will be reverted before you exit.
3. **Hypothesize is never skippable.** "I think I know what it is" IS a
   hypothesis — write it down and test it the same way.
4. **Each experiment changes at most 5 lines.** If you need more, the
   hypothesis is too vague — go back to Phase 2 and split it.
5. **Revert every experiment after recording the result.** Keep the tree
   clean so the next experiment is isolated.
6. **Never `Write` or `Edit` any path under `src/`, `test/`, `tests/`,
   `scripts/`, or any production directory.** `Write`/`Edit` are permitted
   solely for `hypothesis.md`.

## Phase 1. Observe

**Goal.** Collect raw facts. Reproduce the bug. Separate what you *know*
from what you *assume*.

**Steps.**

1. Reproduce the bug. Get the exact error, stack trace, or wrong output.
2. Strip the reproduction to its minimum. Remove unrelated code until the
   bug still appears.
3. **Identify the module/layer.** Which directory does the bug live in? The
   boundary between working and broken code is where the bug lives.
4. Record the environment: browser, dev server port, relevant env vars,
   dependency versions if relevant.
5. Note what *does* work — related flows, adjacent pages, prior commits.
6. **If the bug involves multi-byte text,** dump the raw bytes and check
   for U+FFFD / mojibake *before* assuming anything about logic. Encoding
   corruption looks like a logic bug and is not.
7. Write every observation to `hypothesis.md` under `## Observations`.

**Exit criteria.**

- [ ] Bug reproduced (or explicitly documented non-reproducible + conditions)
- [ ] Exact error message / wrong behaviour recorded verbatim
- [ ] Minimal reproduction captured
- [ ] Module and file paths identified
- [ ] `hypothesis.md` exists with `## Observations` populated

**Common rationalizations.**

| Excuse | Reality |
|---|---|
| "I already know what's wrong" | Then write it as a hypothesis and prove it. If you are right, it takes two minutes. |
| "Let me just try this quick fix first" | That is how the previous attempt failed. |
| "The error message is clear enough" | Error messages describe symptoms, not causes. |
| "I can see the bug in the code" | If you could, it would already be fixed. |

## Phase 2. Hypothesize

**Goal.** Generate 3–5 possible root causes. For each, list supporting and
conflicting evidence from Phase 1. Rank by likelihood.

**Steps.**

1. List **at least three** hypotheses. Think across categories:
   - **Data** — wrong input, missing field, type mismatch, encoding, stale response
   - **Logic** — wrong condition, off-by-one, race condition, wrong order of effects
   - **State** — data cache, form state, leaked state across routes, initialization order
   - **Environment** — env var, auth token, browser quirk, feature flag
   - **Rendering** — re-render loop, stale closure, effect deps wrong, key collision
2. For each hypothesis write:
   - **Supports:** observation facts that back the theory
   - **Conflicts:** facts that argue against it
   - **Test:** the smallest experiment that would falsify or confirm it
3. Mark the **ROOT HYPOTHESIS** — most supporting evidence, fewest conflicts.
4. Write everything to `hypothesis.md` under `## Hypotheses`.

**Example block.**

```markdown
## Hypotheses

### H1: Cache key is unstable, re-fetching on every render (ROOT HYPOTHESIS)
- Supports: list flickers every keystroke; network tab shows duplicate requests
- Conflicts: none yet
- Test: log the cache key inside the data hook; if different each render, confirmed

### H2: Debounced search fires before previous response is cached
- Supports: fast typing causes duplicate fetches
- Conflicts: bug also reproduces on single-character input
- Test: set debounce to 0, reproduce

### H3: Parent component remounts on state change
- Supports: effect cleanup fires during interaction
- Conflicts: DevTools shows stable component id
- Test: console.log in a mount-only effect
```

**Exit criteria.**

- [ ] At least three hypotheses
- [ ] Each has Supports / Conflicts / Test
- [ ] ROOT HYPOTHESIS explicitly marked

**Common rationalizations.**

| Excuse | Reality |
|---|---|
| "I only have one theory" | You have one *favourite* theory. Think harder. |
| "Writing this down is slow" | Debugging without writing is slower. |
| "The first hypothesis is obviously right" | Then proving it takes two minutes. |

## Phase 3. Experiment

**Goal.** Test the ROOT HYPOTHESIS with the smallest possible change.

**Steps.**

1. Write the experiment plan in `hypothesis.md` under `## Experiments`:
   - What will you change?
   - What result would confirm the hypothesis?
   - What result would reject it?
2. Apply the change. **Maximum 5 lines.**
3. Run the reproduction from Phase 1.
4. Record the result: **confirmed**, **rejected**, or **inconclusive**.
5. **Revert the experiment.**

**Experiment rules.**

- **One variable at a time.** Never combine two fixes.
- **Diagnostic, not production.** console.log, alert, hardcoded shortcuts.
- **Inconclusive is a result.** Record it and move to the next hypothesis.

**Exit criteria.**

- [ ] Experiment executed (one change, one variable)
- [ ] Result recorded
- [ ] Experimental code reverted, tree clean
- [ ] `## Experiments` updated

**Common rationalizations.**

| Excuse | Reality |
|---|---|
| "Let me just fix it instead of testing" | Fixing without confirming ships a wrong fix. |
| "I'll test two things at once" | When both change, which fixed it? |
| "5 lines is not enough" | 5 lines is enough for a log, assertion, or short-circuit. |

## Phase 4. Conclude

**Goal.** Confirm root cause and produce a **fix plan** (not fix code).

**Steps.**

1. **If ROOT HYPOTHESIS confirmed:**
   - Write root cause in one sentence under `## Root cause`.
   - Write `## Fix` section as a **plan in prose** (not code):
     - Which files need to change (exact paths)
     - What the change is semantically
     - Which experiment proved the hypothesis
     - What to verify after the fix
   - **Do NOT write fix code.** Hand the plan to `implement-feature`.
   - **Fix plan format: prose only, no code.** Forbidden inside Fix:
     - Fenced code blocks of any language
     - Patch/diff syntax
     - Statement-shaped lines from the production language
   - **Allowed:** inline code spans for references (file paths, function
     names, config keys) in single backticks.

2. **If ROOT HYPOTHESIS rejected:**
   - Record rejection reason.
   - Promote the next hypothesis to ROOT. Return to Phase 3.
   - If *all* rejected → return to Phase 1. The bug exists, the cause exists.

**Exit criteria.**

- [ ] Root cause written in one sentence
- [ ] Fix plan in prose (no code blocks)
- [ ] Zero Edit/Write against source files across the whole skill run
- [ ] Skill exits, returning control to the orchestrator

**Common rationalizations.**

| Excuse | Reality |
|---|---|
| "The fix is three lines, just write it here" | Hand it to Phase 3 Implement. |
| "implement-feature won't understand my plan" | Then write a better plan. |
| "All hypotheses failed, I am stuck" | Go back to Observe. The bug exists, a cause exists. |

## The anti-bulldozer rule

The #1 AI debugging failure mode: agent forms a theory, writes 150 lines of
"fix" code, the bug persists, so the agent writes another 150 lines going
deeper into the same wrong theory.

If you catch yourself:

- Writing more than 5 lines before hypothesis is confirmed → **stop.**
- Trying the same approach a second time → **stop.** Hypothesis rejected.
- Ignoring a conflicting observation → **stop.** Write it down. Re-rank.
- Feeling "almost there" after three failed attempts → **stop.** Bulldozing.

Write it down. Test it. Prove it. Then fix it.

## Integration with feature-workflow

Dispatched from two points:

1. **From feature-workflow Phase 4**, after `test-feature` reports `non_obvious: true` bugs.
   Writes to `.tmp/<task-slug>/debug/hypothesis.md`. Does NOT consume `dev_attempts`.

2. **Standalone.** User asks to investigate. Writes to
   `.tmp/debug-standalone/<bug-slug>/hypothesis.md`.

## Output

- `hypothesis.md` — full investigation trail
- Control returned to caller

## Constraints

- **Do NOT write to `src/` in ANY phase.** Diagnosis only.
- Do NOT commit `hypothesis.md` — it lives under `.tmp/`
- Do NOT invoke `remember-edge-case` — the orchestrator does that after the fix goes green.

## Learnings

- (updated after each run)

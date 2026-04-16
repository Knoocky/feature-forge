---
name: decompose-task
description: Break a feature request into an atomic, dependency-ordered subtask list with a mandatory user approval gate before development starts. Phase 2 of feature-workflow (runs after codebase research, before implementation). Also usable standalone for planning.
allowed-tools: [Read, Write, Edit, Bash, TodoWrite, AskUserQuestion]
---

# Decompose Task

## Goal

Turn a fuzzy "implement feature X" request into a concrete, reviewable plan:

- Atomic subtasks (each a single-file-ish change with a clear outcome)
- Explicit dependencies between subtasks
- Each subtask tagged with the architectural layer / file path it'll touch
- Acceptance criteria tied back to the top-level feature goal
- **Mandatory user approval gate** — the plan is frozen only after the user confirms

The output is a single source-of-truth file + a TodoWrite list, both kept in sync.

## When to invoke

- As Phase 2 of `feature-workflow` (runs after `codebase-researcher` produces the map, before `implement-feature` starts)
- Standalone, when the user says "decompose task X" / "plan feature Y" without asking for implementation yet
- **Skip** for trivial edits (single file, one-line fix, rename, typo) — `feature-workflow`'s Step 0 complexity gate handles that

## Input

The orchestrator (or user) gives you:
1. `<task-slug>` — feature slug
2. Path to `.tmp/<task-slug>/notes/context.md` — read `## Goal` + `## Acceptance criteria`
3. *(optional, usually present)* Path to `.tmp/<task-slug>/research/codebase-map.md` — from `codebase-researcher`. When present, use it to anchor subtasks to specific files.

## Steps

### 1. Read inputs

```
Read .tmp/<task-slug>/notes/context.md
Read .tmp/<task-slug>/research/codebase-map.md   # if present
```

Extract:
- Top-level goal (one sentence)
- Acceptance criteria (bulleted list)
- Files to touch (from research report `## Relevant files to touch` table)
- Reusable primitives (from `## Similar patterns already in repo`)
- Risks (from `## Risks / non-obvious coupling`)

### 2. Derive subtasks

Decompose the goal into **atomic** steps. Rules:

- **One subtask = one clear outcome** that can be tested/verified on its own. "Update schema AND form AND filters" is three subtasks.
- **Order by dependency.** Schema first, then the form that uses it, then the UI that consumes the form's output.
- **Name files explicitly.** "Add field to form" is vague — "Add `profile_picture` field to `src/features/user-form/ui/UserForm.tsx`" is actionable.
- **Include verification**, not just code. "Verify new field renders in the component preview" is a legit subtask.
- **Reuse over create.** If the research report flagged a reusable primitive, bake the reuse into the subtask.
- **One subtask per ~20-80 lines of diff.** If a subtask feels bigger, split it. If smaller, merge with a neighbor.

For a typical "add fields to a form" feature, a good decomposition looks like:

```
1. Update entity schema      (entities/user/model/schema.ts)
2. Update API payload type   (shared/api/users.ts)
3. Add form control UI       (features/user-form/ui/UserForm.tsx)
4. Register in preview       (preview/user-form/index.tsx)
5. Verify via Playwright     (runs test-feature skill)
```

### 3. Flag risks and questions

If the research report had unresolved questions, or you spot a fork in the road while decomposing, add them to a `## Open questions` section. **Do NOT silently pick an answer** — the user will see the plan and decide.

Examples of legit open questions:
- "Should `profile_picture` be required or optional? Both sides of the research report are consistent with either."
- "New field needs to show in the user list view too — is that in scope, or saved for a follow-up?"

### 4. Write the plan file

Save to `.tmp/<task-slug>/plans/decomposition.md` using this exact structure:

```markdown
# Decomposition — <task-slug>

**Goal:** <one-sentence goal, copied from context.md>

**Source of plan:** generated from `research/codebase-map.md` + `notes/context.md`

## Acceptance criteria (from context.md)
- <criterion 1>
- <criterion 2>

## Subtasks

### 1. <verb phrase, imperative>
- **Files:** `src/...`
- **Depends on:** — *(or: subtask 2, 3)*
- **Outcome:** <what's true after this subtask is done>
- **Reuses:** `<path to existing primitive>` — *(or: — if none)*
- **Notes:** <any specific pattern or constraint from the research report>

### 2. <next subtask>
- ...

### N. Verify feature in component preview
- **Files:** `src/preview/.../index.tsx` (registration only, if missing)
- **Depends on:** all above
- **Outcome:** All acceptance criteria verifiable by hand in the preview
- **Reuses:** existing preview slot if present
- **Notes:** tests run via `test-feature` skill — no manual QA needed here

## Open questions (user decides before implementation starts)
- <question 1>
- <question 2>

## Out of scope (explicit non-goals, to avoid scope creep)
- <thing 1>
- <thing 2>

## Dependency graph
```
1 → 2 → 3 → 4 → 5
          ↘ 3a ↗
```
*(ASCII arrow diagram or numbered list — whatever's clearest. Skip if linear.)*
```

### 5. Mirror into TodoWrite (for user-visible progress)

Create a TodoWrite item per subtask. Use the subtask title as `subject`, mark all as `pending`. These are **ephemeral** — the source of truth is the plan file on disk. If the chat is restarted, the plan file survives; if TodoWrite gets wiped, we rebuild from the file.

### 6. **MANDATORY USER APPROVAL GATE**

This is the most important step. **Do NOT proceed to any downstream phase without an explicit user signal.**

Print a concise summary of the plan to chat:

```markdown
## Plan ready for review — <task-slug>

**Goal:** <one sentence>

**Subtasks (N):**
1. <title> — `<file>`
2. <title> — `<file>`
...

**Open questions:**
- <question 1>
- <question 2>

**Out of scope:** <bullets>

**Full plan:** `.tmp/<task-slug>/plans/decomposition.md`

---
Please review the plan. Options:
- "ok" / "go" / "confirmed" — plan is frozen, implementation starts
- Describe edits — I'll update the plan and show it again for review
- Answer open questions — I'll incorporate decisions into the plan and re-show
```

Then **stop and wait**. Use `AskUserQuestion` only if the ambiguities are binary and you can phrase them as choices; otherwise rely on the free-form reply.

### 7. Iterate on user feedback

When the user replies:

- **"ok" / "go" / "confirmed"** → Mark the plan as approved. Append this line to `decomposition.md`:
  ```markdown

  ---
  **Approved by user:** <ISO timestamp, via: date -u +%Y-%m-%dT%H:%M:%SZ>
  ```
  Return control to the parent (orchestrator or standalone caller). Downstream phases now have the green light.

- **Text edits / corrections** → Update the plan file and the TodoWrite list, re-print the summary, **loop back to step 6**. No hard cap on iterations — this is negotiation, not a review budget.

- **Answers to open questions** → Move each resolved question from `## Open questions` into the relevant subtask's `## Notes` (or its own bullet in `## Acceptance criteria` if it's user-visible), re-print summary, loop to step 6.

- **Scope change request** (user wants more/less than we decomposed) → Update `## Subtasks` + `## Out of scope` + TodoWrite, re-print, loop to step 6.

**Iteration count is NOT an escalation signal.** If the user wants to edit 10 times, that's fine — planning is cheap, wrong implementation is expensive.

## Output

- `.tmp/<task-slug>/plans/decomposition.md` — frozen plan with user approval timestamp at the bottom
- TodoWrite list with N items (pending), mirroring the subtasks
- Parent/caller receives: "Plan approved, N subtasks, plan file: `.tmp/<slug>/plans/decomposition.md`"

## Constraints

- Do NOT start implementing anything — you are a planner, not an implementor
- Do NOT read `.tmp/<slug>/notes/context.md` iteration log — only `## Goal` + `## Acceptance criteria`
- Do NOT skip the user approval gate — even if the plan looks "obviously right", the user's eye catches things the AI misses
- Do NOT silently answer open questions — surface them
- Do NOT count plan iterations toward any loop budget (those live in `feature-workflow`'s state.yml)
- Do NOT touch `state.yml` — that's the orchestrator's domain; you write only to `plans/` and TodoWrite

## Learnings

- (updated after each run)

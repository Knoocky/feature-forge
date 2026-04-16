---
name: feature-workflow
description: Use when the user asks to implement, add, build, create, write, or develop a new feature, component, module, page, widget, or form. Runs the full Research → Decompose (with user approval gate) → Dev → Test → Review → Docs pipeline with automatic loopback on bugs or critical review findings. Auto-invoked by Claude on feature-development intent — no slash command needed.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Skill, Agent, TodoWrite]
---

# Feature Workflow Orchestrator

## Goal

End-to-end feature delivery as a single continuous loop:

```
Task → Research → Decompose (user approves plan) → Implement → Test → Review → Docs
         ↑__________________(loopback on bugs or critical findings)___________|
```

Clean, architecture-compliant code → green static checks + verification → review without critical findings → up-to-date docs. Automatic loopback if any phase fails. Single entry point: the user just describes the task.

## When to invoke

Claude auto-picks this skill when the user says things like:
- "implement / add / build / create / develop a feature / component / page / widget"
- "Add X to Y" where X is a new UI surface

**Skip this orchestrator for:**
- Pure bug fixes (single file, no new surface) — go directly to implement-feature or just edit
- Refactors without behavior change
- Read-only questions, research, code explanation
- Config / docs / memory changes

## Context passing — critical design rule

All downstream skills and agents receive context **only via files on disk**, never via implicit chat history or TodoWrite:

| File | Contents | Consumers |
|------|----------|-----------|
| `.tmp/<task-slug>/notes/state.yml` | **Durable control state**: current phase, loop counters, last event, paths to latest artifacts, list of changed files. Crash-resistant ledger. | Orchestrator only |
| `.tmp/<task-slug>/notes/context.md` | Full context: goal, acceptance criteria, architecture decisions, iteration log, bug history, fixes | `codebase-researcher` (Goal + AC only), `decompose-task`, `implement-feature`, `test-feature`, `update-docs` |
| `.tmp/<task-slug>/notes/review-context.md` | Clean slice: goal + acceptance criteria + list of final changed files + their current content | **Only** `code-quality-reviewer`, `performance-reviewer`, `security-reviewer` |
| `.tmp/<task-slug>/research/codebase-map.md` | Repo map: relevant files, reusable primitives, dependencies, risks, questions | `decompose-task`, `implement-feature` (reference) |
| `.tmp/<task-slug>/plans/decomposition.md` | Atomic subtask list with user approval timestamp | `implement-feature`, `test-feature` |

**Why this split:**
- Review agents must form an independent opinion → `review-context.md` is clean, no dev trace.
- Dev/Test/Docs need full history → `context.md`.
- Researcher needs goal + AC but not iteration log → reads `context.md` selectively.
- The orchestrator needs a crash-resistant ledger → `state.yml`, because chat messages can be compacted.

## State persistence — surviving compaction and restarts

`state.yml` is the **sole source of truth** for control flow. Everything needed to resume the workflow from any point lives in this one file. TodoWrite is used for user-visible progress only, not as a state store.

```yaml
# .tmp/<task-slug>/notes/state.yml
task_slug: PROJ-12345-user-profile-fields
started_at: 2026-04-13T18:05:00Z
last_updated: 2026-04-13T19:30:00Z
goal: "Add profile fields to the user form"
complexity: normal             # trivial | normal
current_phase: test            # research | decompose | implement | test | review | docs | done | escalated
last_event: phase_test_failed
next_action: loop_to_implement_with_bugs
counters:
  dev_attempts: 2              # hard cap 3
  review_attempts: 0           # hard cap 2
artifacts:
  context_file: .tmp/PROJ-12345-.../notes/context.md
  research_report: .tmp/PROJ-12345-.../research/codebase-map.md
  decomposition_file: .tmp/PROJ-12345-.../plans/decomposition.md
  plan_approved: true
  review_context_file: .tmp/PROJ-12345-.../notes/review-context.md
  bugs_file: .tmp/PROJ-12345-.../test-specs/bugs.md
  test_specs_file: .tmp/PROJ-12345-.../test-specs/ai.md
changed_files:
  - src/features/user-form/ui/UserForm.tsx
  - src/entities/user/model/schema.ts
```

**Write-ahead discipline.** Before entering any phase: write `state.yml` with the new `current_phase`, bump the relevant counter, set `last_event: entering_<phase>`. Then execute the phase. After it returns: update `last_event` with the outcome.

**Resume contract.** Every invocation **must** run Step 0.a (Resume check) first.

## Steps

### 0.a — Resume check (ALWAYS run first)

1. Derive `<task-slug>` from current git branch:
   ```bash
   BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
   TICKET=$(echo "$BRANCH" | grep -oE '[A-Z]+-[0-9]+')
   # slug = <TICKET>-<word1>-<word2>-<word3> (kebab-case, max 3 meaningful words)
   ```
2. Check for existing state:
   ```bash
   cat ".tmp/<task-slug>/notes/state.yml" 2>/dev/null
   ```
3. **If `state.yml` exists** — we're resuming. Read `current_phase`, `counters`, `last_event`, `goal`, `changed_files`, `next_action`. Confirm with the user:

   > Detected an incomplete feature-workflow run:
   > - slug: `<slug>`
   > - goal: `<goal>`
   > - phase: `<current_phase>`, last_event: `<last_event>`
   > - counters: dev `<N>/3`, review `<M>/2`
   > - changed files: `<list>`
   >
   > Resume from this point or start fresh (old run will be archived)?

   - **Resume** → jump to the step matching `current_phase`.
   - **Start fresh** → `mv ".tmp/<slug>" ".tmp/<slug>-archived-$(date +%s)"`
   - **Different feature** → use new slug, don't touch old run.

4. **If `state.yml` does NOT exist** → new run. Fall through to 0.b.

### 0.b — Initialize (only if starting fresh)

1. `mkdir -p .tmp/<task-slug>/{plans,test-specs,screenshots,research,reviews,notes}`
2. Write `.tmp/<task-slug>/notes/context.md`:
   ```markdown
   # Feature Context — <slug>

   ## Goal
   <one-sentence goal>

   ## Acceptance criteria
   - <criterion 1>
   - <criterion 2>

   ## Scope / Out of scope
   - In:  ...
   - Out: ...

   ## Iteration log
   (filled in as we loop)
   ```
3. Write initial `state.yml`.
4. Create TodoWrite list with six parent items for user-visible progress.

### 0.c — Complexity gate

| Signal | Classification |
|--------|----------------|
| Single file, < 20 lines of diff, no new component, no new API field | `trivial` |
| Touches schema, API, routing, or adds a new architectural module | `normal` |
| "implement / add / build feature / widget / form / page" in phrasing | `normal` |
| "fix typo / rename / change color / move" | `trivial` |
| User explicitly mentions "research" or "plan" | `normal` |
| Any ambiguity about scope | `normal` |

- `trivial` → skip Phases 1 and 2, jump to Phase 3.
- `normal` → proceed to Phase 1.

Tell the user which path you chose in one line.

### 1. Phase 1 — Research (skipped if complexity=trivial)

Dispatch the `codebase-researcher` sub-agent:

```
Agent({
  subagent_type: "codebase-researcher",
  prompt: "Research the codebase for this task. Read ONLY ## Goal and ## Acceptance criteria from .tmp/<slug>/notes/context.md. Then read .claude/PROJECT.md and .claude/ARCHITECTURE.md. Explore the repo, save map to .tmp/<slug>/research/codebase-map.md. Task: <summary>."
})
```

Surface questions from `## Questions for the user` before Phase 2.

### 2. Phase 2 — Decompose (skipped if complexity=trivial) — blocking approval gate

Invoke `decompose-task` skill. It produces `.tmp/<task-slug>/plans/decomposition.md` and runs its own user-approval loop. Does NOT return until the user approves.

**Do not advance past Phase 2 until the plan has an approval timestamp.**

### 3. Phase 3 — Implement

**Write-ahead:** increment `counters.dev_attempts`. If >3 → abort to escalation.

Invoke `implement-feature` skill. Pass context file, approved plan, research report. Record changed files in `context.md`.

### 4. Phase 4 — Test

Invoke `test-feature` skill. It returns either:
- `status: pass` → continue to Phase 5.
- `status: fail` + `bugs.md` →
  - Check per-bug `non_obvious` field. If any `true` → dispatch `debug-hypothesis` first.
  - Check `dev_attempts` budget. If >= 3 → escalate.
  - Otherwise loop back to Phase 3.

**`debug-hypothesis` does NOT consume a `dev_attempts` slot.** It is a sub-step of Phase 4.

### 5. Phase 5 — Review (parallel, clean context)

**Write-ahead:** increment `counters.review_attempts`. If >2 → abort to escalation.

Build clean `review-context.md` (goal + AC + file contents, NO dev history).

Dispatch **three agents in a single message** (parallel):

```
Agent({subagent_type: "code-quality-reviewer", ...})
Agent({subagent_type: "performance-reviewer", ...})
Agent({subagent_type: "security-reviewer", ...})
```

Decision:
- Any `critical` or `high` → loop back to Phase 3 with findings.
- Only `medium` / `low` → continue to Phase 6.

**On re-entry to Phase 5, rebuild review-context.md from scratch. Delete old reports.**

### 6. Phase 6 — Docs

#### 6.0. Post-ship routing (interactive)

Walk surviving medium/low findings and fixed bugs. For each:

1. Classify: **Functional** → candidate for `/remember-edge-case`. **Visual/UX** → candidate for `/remember-design-rule`. **One-off** → skip.
2. Ask the user per candidate (batch up to 4 per AskUserQuestion).
3. Act on answers: "Yes" → invoke the skill. "No" → record as declined. "Defer" → include copy-pastable line in final report.

#### 6.1. Update docs

Invoke `update-docs` skill.

### 7. Final report

```
Feature: <goal>
Complexity: <trivial | normal>

Phase 1 Research:   <skipped | done>
Phase 2 Decompose:  <skipped | approved>
Phase 3 Implement:  <M dev attempts>
Phase 4 Test:       PASS
Phase 5 Review:     PASS with <j> low-severity comments
Phase 6 Docs:       <updated | no changes>

Changed files:
- src/...

Surviving low-severity comments:
- [code-quality] ...

Post-ship routing results:
- Memorized: ...
- Declined: ...
- Deferred: ...
```

## Loopback policy (hard limits)

| Loop | Max | On overflow |
|------|-----|-------------|
| Research (Phase 1) | 1 (never re-runs after Phase 3) | N/A |
| Plan review (Phase 2) | Unlimited | Planning is cheap |
| Dev ↔ Test (Phase 3 ↔ 4) | 3 | Escalate with bugs.md |
| Dev → Test → Review | 2 | Escalate with review reports |

**Research and Decompose do NOT participate in code-level loops.** They run once before code and are frozen. Loopback from Phase 4/5 always targets Phase 3.

## Output

- Feature code in source tree (not git-committed)
- `.tmp/<task-slug>/` — full artifact tree
- TodoWrite list marked completed

## Learnings

- (updated after each run)

# feature-forge Architecture

## Design Principles

1. **Filesystem as IPC** — all agent communication happens via files on disk (`.tmp/<task-slug>/`), not chat history. Crash-resistant, resumable.
2. **Context isolation** — review agents never see development iterations. They form independent first-impression judgments.
3. **Persistent memory** — dual-mode agents (test-writer, design-keeper) accumulate project-specific knowledge across runs.
4. **Hard gates over soft reminders** — the workflow-gate hook enforces edit-intent routing with `exit 2`, not advisory text.
5. **Fail-open** — all hooks return `exit 0` on errors. Broken hooks must never lock users out.

## Data Flow

```
User prompt
    │
    ▼
prompt-router.py (UserPromptSubmit)
    │ classifies intent, writes gate state
    ▼
workflow-gate.py (PreToolUse on Edit/Write)
    │ blocks until workflow skill is invoked
    ▼
feature-workflow (Skill)
    │
    ├─► Phase 1: codebase-researcher (Agent)
    │     └─► .tmp/<slug>/research/codebase-map.md
    │
    ├─► Phase 2: decompose-task (Skill)
    │     └─► .tmp/<slug>/plans/decomposition.md
    │     └─► USER APPROVAL GATE
    │
    ├─► Phase 3: implement-feature (Skill)
    │     ├─► design-keeper (Agent, CONSULT mode)
    │     └─► source code changes
    │
    ├─► Phase 4: test-feature (Skill)
    │     ├─► test-writer (Agent, GENERATE mode)
    │     ├─► .tmp/<slug>/test-specs/ai.md
    │     ├─► static checks (type checker + linter)
    │     ├─► browser verification (optional)
    │     └─► .tmp/<slug>/test-specs/bugs.md (on failure)
    │           │
    │           ├── non_obvious: true → debug-hypothesis (Skill)
    │           │                         └─► .tmp/<slug>/debug/hypothesis.md
    │           └── loop back to Phase 3
    │
    ├─► Phase 5: 3 review agents IN PARALLEL
    │     ├─► code-quality-reviewer → .tmp/<slug>/reviews/code-quality.md
    │     ├─► performance-reviewer  → .tmp/<slug>/reviews/performance.md
    │     └─► security-reviewer     → .tmp/<slug>/reviews/security.md
    │     │
    │     └── critical/high findings → loop back to Phase 3
    │
    └─► Phase 6: update-docs (Skill)
          ├─► post-ship routing (remember-edge-case / remember-design-rule)
          └─► update PROJECT.md, ARCHITECTURE.md
```

## State Machine

The orchestrator maintains a crash-resistant state file at `.tmp/<task-slug>/notes/state.yml`:

```yaml
task_slug: PROJ-12345-feature-name
current_phase: implement    # research | decompose | implement | test | review | docs | done | escalated
counters:
  dev_attempts: 2           # hard cap: 3
  review_attempts: 0        # hard cap: 2
```

**Write-ahead discipline:** state is written BEFORE entering a phase, so a crash mid-phase leaves a consistent checkpoint.

## Context Files

| File | Written by | Read by | Contains |
|------|-----------|---------|----------|
| `notes/state.yml` | orchestrator only | orchestrator only | Phase, counters, artifact paths |
| `notes/context.md` | orchestrator + skills | researcher, decomposer, implementor, tester | Goal, AC, iteration log, changed files |
| `notes/review-context.md` | orchestrator | 3 review agents only | Goal, AC, file contents (NO dev history) |
| `notes/test-context.md` | test-feature | test-writer agent | Goal, AC, file contents (NO dev history) |
| `research/codebase-map.md` | codebase-researcher | decompose-task, implement-feature | Repo map, reusable primitives |
| `plans/decomposition.md` | decompose-task | implement-feature | Approved subtask list |
| `debug/hypothesis.md` | debug-hypothesis | implement-feature (via orchestrator) | Root cause + fix plan |

## Agent Write Guard

The `subagent-write-guard.py` hook enforces a per-agent allowlist:

| Agent | May Edit | May Write |
|-------|---------|-----------|
| codebase-researcher | own `.memory.md` | `research/codebase-map.md` |
| code-quality-reviewer | own `.memory.md` | `reviews/code-quality.md` |
| performance-reviewer | own `.memory.md` | `reviews/performance.md` |
| security-reviewer | own `.memory.md` | `reviews/security.md` |
| test-writer | own `.memory.md` | (none) |
| design-keeper | own `.memory.md` | (none) |

Main Claude is unrestricted. Sub-agents that aren't in the allowlist are blocked.

## Dual-Mode Agents

Two agents support both **consult** (read-only) and **memorize** (write) modes:

**test-writer:**
- Generate mode: emits test cases, cross-checks persistent memory for regression coverage
- Memorize mode: appends user-reported bug to `test-writer.memory.md`

**design-keeper:**
- Consult mode: returns up to 8 relevant design rules for planned modules
- Memorize mode: appends visual/UX rule to `design-keeper.memory.md`

Mode detection is anchored to the first token of the dispatch prompt (`MEMORIZE:` or `CONSULT:` / default) — a deliberate prompt-injection defense.

## Loopback Budget

| Loop | Max iterations | On overflow |
|------|---------------|-------------|
| Dev ↔ Test | 3 | Escalate to user with bugs.md |
| Dev → Test → Review | 2 | Escalate to user with review reports |
| Plan review (Phase 2) | Unlimited | Planning is cheap |
| Research (Phase 1) | 1 (never re-runs) | N/A |

---
name: implement-feature
description: Write clean, DRY, human-readable feature code following every rule in the project's conventions. Phase 3 of feature-workflow orchestrator, also usable standalone.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# Implement Feature

## Goal

Ship feature code that is:
- **Clean** — no dead code, no debug leftovers, no speculative abstractions
- **DRY** — no copy-pasted blocks >3 lines; but no premature abstraction either
- **Architecture-compliant** — imports follow the project's layer rules (see PROJECT.md)
- **Human-readable** — names explain intent, no magic numbers, no nested ternaries
- **Consistent** — matches existing patterns in this codebase

## Input

Called with a **context file path** (usually `.tmp/<task-slug>/notes/context.md`). Read it first — it contains:
- Feature goal
- Acceptance criteria
- Scope / out of scope
- Iteration log (if re-entering after Test or Review bailed out — read carefully, do NOT re-do correct work)
- Changed files so far (if re-entering)

When invoked standalone (not by `feature-workflow`), the user passes the feature description directly.

## Steps

### 1. Load project context

Before writing any code:
```
Read .claude/PROJECT.md          # Architecture, API, code style, prohibited patterns
Read .claude/ARCHITECTURE.md     # Where similar features live in the source tree
```
Grep for similar existing modules and skim 2-3 of them to internalize the pattern. Copy structure, don't invent.

### 2. Identify the architectural layer

Determine which layer/module this feature belongs in based on your project's architecture (documented in PROJECT.md).

Rules: imports flow in the direction documented in PROJECT.md. No cross-module imports within the same layer unless explicitly allowed.

### 3. Plan the file structure

For non-trivial features, list files you'll create/edit before touching anything. Save to `.tmp/<task-slug>/plans/implementation.md` if invoked via orchestrator.

### 3.5. Consult design-keeper

Before writing any code, dispatch the `design-keeper` sub-agent in consult mode to load relevant visual/UX rules from persistent memory.

```
Agent({
  subagent_type: "design-keeper",
  description: "Consult design rules",
  prompt: "CONSULT: Return visual/UX rules relevant to this implementation.\n\nGoal: <one-sentence goal>\nSlices: <comma-separated module paths from step 3>\n\nReturn at most 8 rules."
})
```

Prepend returned rules to your working context. Treat every returned rule as a hard constraint. Empty block = no rules in memory yet, implement freely.

**Loopback rule.** If re-entered after Test/Review failure, re-dispatch design-keeper — memory may have grown.

### 4. Write the code

Honor every rule in `.claude/PROJECT.md`:

- Follow the naming conventions documented in PROJECT.md
- Follow the import order rules documented in PROJECT.md
- Use strict typing — no `any`, no unsafe casts
- Follow the code style rules in PROJECT.md
- Add comments on non-obvious logic — rare patterns get a `// why:` comment

### 5. DRY check

Grep for duplicated logic. If >3 lines appear twice — extract. But do NOT build abstractions for hypothetical future reuse.

### 6. Self-review pass

Read your own diff before handing off:
- Debug `console.log`s? Delete.
- Imports sorted per PROJECT.md?
- Unnecessary error handling? Cut.
- Touched unrelated files? Revert.
- Added docs the user didn't ask for? Delete.

### 7. Update the context file

If invoked via orchestrator, append to `.tmp/<task-slug>/notes/context.md`:

```markdown
## Iteration log
### Iteration N (Dev phase, <timestamp>)
- Decision: <key choice, one line>
- Files: <list>

## Changed files
- src/features/foo/ui/Foo.tsx — new
- src/pages/bar/ui/BarPage.tsx — modified
```

## Output

- Feature code in source tree
- Updated `context.md` with changed files list
- Short hand-off message: "Done. Changed: [list]. See context.md for iteration N details."

## Constraints

- Do NOT create test files unless the project has a test framework configured
- Do NOT create `.md` files unless the user asked
- Do NOT touch `.claude/ARCHITECTURE.md` (`update-docs` owns that)
- Do NOT commit to git — orchestrator and user decide when
- Do NOT run dev server or tests — that's `test-feature`'s job

## Learnings

- (updated after each run)

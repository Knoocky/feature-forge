# feature-forge

A full-cycle feature development governance framework for AI coding agents.

## Installation

### Claude Code (full support — skills + agents + hooks)

1. Add the marketplace (GitHub shorthand — `owner/repo`):

```
/plugin marketplace add Knoocky/feature-forge
```

2. Install the plugin:

```
/plugin install feature-forge@knoocky
```

All 10 skills, 6 agents, and 4 hooks activate automatically. On first run in a project, the `session-init` hook seeds a `CLAUDE.md` from the bundled template if the project doesn't already have one — existing `CLAUDE.md` files are left untouched.

### GitHub Copilot CLI (skills only)

```bash
cp -r skills .github/skills
```

### Cursor (skills only, format conversion)

```bash
for skill in skills/*/SKILL.md; do
  name=$(basename $(dirname "$skill"))
  cp "$skill" ".cursor/rules/${name}.mdc"
done
```

### Windsurf / Gemini CLI (skills only)

```bash
# Windsurf — concatenate into one file:
cat skills/feature-workflow/SKILL.md skills/debug-hypothesis/SKILL.md > .windsurfrules

# Gemini — copy skills:
cp -r skills .agents/skills
```

> **Note:** Hooks (edit-intent gating, subagent write guard) and sub-agents with isolated context are Claude Code-specific. Other platforms get the skills but not the enforcement layer.

---

## How it works

### You just describe a feature — the pipeline runs automatically

You say: _"Add a settings page with dark mode toggle"_

The plugin detects this is a feature request (via the `prompt-router` hook) and automatically launches a **6-phase pipeline**:

```
Research ──► Decompose ──► Implement ──► Test ──► Review ──► Docs
                   │             ▲          │        │
                   ▼             │          ▼        │
              USER APPROVAL      │       bug found?  │
              (waits for "ok")   │          │        │
                                 │          ▼        ▼
                                 └── Implement ◄─── critical
                                      (retry)       finding?
```

**You don't invoke any commands manually.** The `prompt-router` hook classifies your message and steers the agent toward the workflow. If it misclassifies (e.g., you're just asking a question), type `#bypass` in your next message.

### What each phase does

| Phase            | What happens                                                                         | Who does it                                                                   |
| ---------------- | ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------- |
| **1. Research**  | Explores your codebase — finds reusable components, maps dependencies, flags risks   | `codebase-researcher` agent                                                   |
| **2. Decompose** | Breaks the feature into atomic subtasks, shows you the plan, **waits for your "ok"** | `decompose-task` skill                                                        |
| **3. Implement** | Writes code following your PROJECT.md conventions                                    | `implement-feature` skill + `design-keeper` agent consultation                |
| **4. Test**      | Runs type checker + linter, generates test cases, verifies in browser if UI changed  | `test-feature` skill + `test-writer` agent                                    |
| **5. Review**    | 3 independent reviewers run **in parallel** with isolated context                    | `code-quality-reviewer` + `performance-reviewer` + `security-reviewer` agents |
| **6. Docs**      | Updates ARCHITECTURE.md, offers to memorize bugs/design rules for next time          | `update-docs` skill                                                           |

**Trivial tasks** (typo fix, rename, one-line change) skip Research and Decompose — the complexity gate detects this automatically and jumps straight to Implement.

### When the debugger fires

The `debug-hypothesis` skill activates automatically when a test fails and the cause is **not obvious**:

```
Test phase finds a bug
    │
    ├── obvious? (missing import, typo, lint error)
    │     └── YES → loop back to Implement directly
    │
    └── non-obvious? (blank screen, race condition, unexplained stack trace)
          └── YES → debug-hypothesis activates:
                    Observe → Hypothesize (3+ theories) → Experiment (≤5 lines) → Conclude
                    Produces a diagnosis + fix plan, then Implement writes the actual fix
```

This prevents the **"bulldozer" failure mode** — where the agent writes 150 lines of fix code based on a wrong theory, fails, and writes another 150 lines going deeper into the same wrong theory. The debugger forces the agent to prove the root cause before writing any fix.

### How agent memory works

Two agents accumulate project-specific knowledge that **persists across sessions**:

```
Session 1: user reports "disabled inputs should be gray, not white"
    └── /remember-design-rule → design-keeper saves rule to memory

Session 2: user asks to build a new form
    └── implement-feature consults design-keeper before writing code
        └── design-keeper returns: "disabled inputs must be gray (#ccc)"
            └── the rule is applied preventatively — no review needed
```

```
Session 1: user finds a date-picker bug with 24:00 edge case
    └── /remember-edge-case → test-writer saves edge case to memory

Session 2: user modifies the date picker
    └── test-feature dispatches test-writer to generate test cases
        └── test-writer checks memory → emits a regression case for 24:00
            └── edge case is tested automatically — no human reminder needed
```

**Memory files** live at `.claude/agents/<name>.memory.md` in your project. They grow over time as the team reports bugs and design issues. Each agent keeps ≤200 lines — older entries are compacted.

The 4 review agents (`codebase-researcher`, `code-quality-reviewer`, `performance-reviewer`, `security-reviewer`) also maintain memory — they learn your project's idioms, stable refs, and false-positive patterns so they don't re-flag the same non-issues.

### Edit-intent gating — the safety net

Without this plugin, Claude will happily start editing files the moment you describe a feature. The plugin adds a **hard gate**:

```
You: "Add pagination to the user list"
    │
    ▼
prompt-router classifies → edit intent detected
    │
    ▼
workflow-gate BLOCKS all Edit/Write calls
    │
    ▼
Claude is forced to invoke feature-workflow first
    │
    ▼
feature-workflow researches, plans, gets your approval, THEN edits
```

Bypass: type `#bypass` or `#direct` in your message to skip the gate for that turn.

### Context isolation — why reviews are unbiased

Review agents **never see** the development history. They receive a clean slice:

- Goal + acceptance criteria
- Final file contents

They do NOT see: iteration log, previous bugs, implementor's reasoning, debug traces. This is intentional — they form a **first-impression judgment** like reviewing a PR from a stranger.

### Crash resistance

All state lives on disk in `.tmp/<task-slug>/notes/state.yml`, not in chat history. If your session crashes mid-feature:

1. Start a new session
2. Say "continue the feature"
3. The orchestrator finds `state.yml`, shows you where it stopped, and resumes

---

## Setup for your project

After installing the plugin, the `session-init` hook runs on the next session and generates `<project>/.claude/CLAUDE.md` with the full list of skills and agents — you don't edit that file, it's refreshed automatically.

The only manual steps are the project-specific context files:

1. Create `CLAUDE.md` in your project root (use `templates/CLAUDE.md.template` as a starting point) and fill in the `{{placeholders}}`: project name, stack, boundaries, source map
2. Create `.claude/PROJECT.md` with your project's conventions (code style, architecture, type checker/linter commands)
3. Add `.tmp/` to your `.gitignore`

---

## What's inside

### Skills (10)

| Skill                  | Trigger                                                  | Description                                                         |
| ---------------------- | -------------------------------------------------------- | ------------------------------------------------------------------- |
| `feature-workflow`     | **Auto** — on any feature request                        | Master orchestrator — 6-phase pipeline with loopback                |
| `implement-feature`    | Auto (via orchestrator) or manual                        | Write code following project conventions                            |
| `decompose-task`       | Auto (via orchestrator) or manual                        | Break feature into atomic subtasks with approval gate               |
| `test-feature`         | Auto (via orchestrator)                                  | Run type checker + linter + browser verification                    |
| `debug-hypothesis`     | Auto — when test finds a non-obvious bug                 | Scientific debugging: Observe → Hypothesize → Experiment → Conclude |
| `remember-edge-case`   | Manual — `/remember-edge-case` after fixing a bug        | Save bug to test-writer's persistent memory                         |
| `remember-design-rule` | Manual — `/remember-design-rule` after fixing a UX issue | Save design rule to design-keeper's persistent memory               |
| `update-docs`          | Auto (via orchestrator)                                  | Sync documentation after feature ships                              |
| `test-on-sandbox`      | Auto (via test-feature)                                  | Isolated component verification in browser                          |
| `verify-text-encoding` | Auto — after edits with multi-byte text                  | Detect UTF-8 corruption (U+FFFD, mojibake)                          |

### Agents (6) — Claude Code only

| Agent                   | Mode                           | Memory | Description                                             |
| ----------------------- | ------------------------------ | ------ | ------------------------------------------------------- |
| `codebase-researcher`   | Single                         | Yes    | Maps repo structure, finds reusable primitives          |
| `code-quality-reviewer` | Single                         | Yes    | Reviews DRY, naming, readability, architecture          |
| `performance-reviewer`  | Single                         | Yes    | Reviews caching, data fetching, bundle size             |
| `security-reviewer`     | Single                         | Yes    | Reviews XSS, auth, data exposure, dependencies          |
| `test-writer`           | **Dual** (generate / memorize) | Yes    | Generates test cases with automatic regression coverage |
| `design-keeper`         | **Dual** (consult / memorize)  | Yes    | Applies past design rules preventatively                |

### Hooks (4) — Claude Code only

| Hook                   | Event            | What it does                                                                 |
| ---------------------- | ---------------- | ---------------------------------------------------------------------------- |
| `prompt-router`        | UserPromptSubmit | Classifies intent, steers toward workflow, writes gate state                 |
| `workflow-gate`        | PreToolUse       | **Hard blocks** Edit/Write until workflow skill is invoked                   |
| `subagent-write-guard` | PreToolUse       | Ensures sub-agents only write to their own allowlisted paths                 |
| `session-init`         | SessionStart     | Regenerates `.claude/CLAUDE.md` with the list of installed skills and agents |

---

## Customization

See `docs/customization.md` for:

- Adding your language patterns to the prompt router (Russian, Chinese, etc.)
- Configuring type checker and linter commands
- Adding project-specific agents to the write guard allowlist
- Extending with project-specific skills

## Architecture

See `docs/architecture.md` for the full data flow diagram, state machine, and design principles.

## License

MIT

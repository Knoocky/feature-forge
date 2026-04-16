# feature-forge

A full-cycle feature development governance framework for Claude Code.

## What is this?

feature-forge is a Claude Code plugin that adds a structured, multi-phase feature development pipeline to any project. It orchestrates research, task decomposition, implementation, testing, code review (via 3 parallel sub-agents), and documentation updates — with automatic loopback on bugs or critical review findings.

## Key features

- **6-phase feature workflow** — Research → Decompose → Implement → Test → Review → Docs, with state machine and loopback
- **Sub-agent review system** — 3 independent reviewers (code quality, performance, security) running in parallel with isolated context
- **Scientific debugging** — Observe → Hypothesize → Experiment → Conclude loop for non-trivial bugs
- **Edit-intent gating** — hooks prevent direct file edits until a workflow skill is invoked (bypass available)
- **Persistent agent memory** — agents accumulate project-specific knowledge across runs
- **Dual-mode agents** — test-writer and design-keeper can both consult past knowledge and memorize new findings
- **Artifact storage** — all intermediate files organized under `.tmp/<task-slug>/` (gitignored, regenerable)

## Quick start

1. Install the plugin (add to `~/.claude/settings.json`):

```json
{
  "enabledPlugins": {
    "feature-forge@your-marketplace": true
  }
}
```

2. Copy `templates/CLAUDE.md.template` to your project root as `CLAUDE.md` and fill in the `{{placeholders}}`

3. Create a `PROJECT.md` in your `.claude/` directory with your project's conventions (code style, architecture, tools)

4. Add `.tmp/` to your `.gitignore`

5. Start using it — just describe a feature to implement, and feature-forge will orchestrate the pipeline

## What's inside

### Skills (10)

| Skill | Description |
|-------|-------------|
| `feature-workflow` | Master orchestrator — 6-phase pipeline with loopback |
| `implement-feature` | Write code following project conventions |
| `decompose-task` | Break feature into atomic, dependency-ordered subtasks |
| `test-feature` | Run type checker, linter, and verification |
| `debug-hypothesis` | Scientific debugging loop |
| `remember-edge-case` | Save bug to test-writer's persistent memory |
| `remember-design-rule` | Save UX rule to design-keeper's persistent memory |
| `update-docs` | Sync documentation after feature ships |
| `test-on-sandbox` | Isolated component verification |
| `verify-text-encoding` | Detect UTF-8 corruption after edits |

### Agents (6)

| Agent | Description |
|-------|-------------|
| `codebase-researcher` | Maps repo structure before implementation |
| `code-quality-reviewer` | Reviews DRY, naming, readability, architecture |
| `performance-reviewer` | Reviews rendering, caching, bundle, data fetching |
| `security-reviewer` | Reviews XSS, auth, data exposure, dependencies |
| `test-writer` | Dual-mode: generates test cases / memorizes edge cases |
| `design-keeper` | Dual-mode: consults design rules / memorizes new ones |

### Hooks (3)

| Hook | Event | Purpose |
|------|-------|---------|
| `subagent-write-guard` | PreToolUse | Enforces per-agent write allowlist |
| `workflow-gate` | PreToolUse | Blocks direct edits until workflow skill is invoked |
| `prompt-router` | UserPromptSubmit | Classifies edit intent and steers toward workflows |

## Customization

See `docs/customization.md` for:
- Adding your language patterns to the prompt router
- Configuring type checker and linter commands
- Adding project-specific agents to the write guard allowlist
- Extending with project-specific skills

## Architecture

See `docs/architecture.md` for the full data flow, state machine, and design principles.

## License

MIT

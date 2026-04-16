# feature-forge Setup Checklist

## First-time setup for your project

### 1. Install the plugin

Add to `~/.claude/settings.json`:

```json
{
  "enabledPlugins": {
    "feature-forge@your-marketplace": true
  }
}
```

### 2. Create CLAUDE.md

Copy `templates/CLAUDE.md.template` to your project root as `CLAUDE.md`.

Fill in the `{{placeholders}}`:
- [ ] Project name and owner
- [ ] Stack description (language, framework, build tools, etc.)
- [ ] Boundaries (what Claude should NOT do)
- [ ] Source code map (one-liner per directory/layer)

### 3. Create PROJECT.md

Create `.claude/PROJECT.md` with your project's conventions:

- [ ] Architecture overview and import rules
- [ ] Code style rules (naming, formatting, prohibited patterns)
- [ ] API layer patterns
- [ ] Type checker command (e.g., `tsc --noEmit`, `mypy`, `cargo check`)
- [ ] Linter command (e.g., `eslint .`, `ruff check .`, `clippy`)
- [ ] Dev server command (e.g., `npm run dev`, `cargo run`, `python manage.py runserver`)
- [ ] Testing framework and commands (if any)
- [ ] Component preview/sandbox setup (if any)

### 4. Create ARCHITECTURE.md

Create `.claude/ARCHITECTURE.md` with:

- [ ] File navigation map (which file holds which feature)
- [ ] Key patterns with code examples
- [ ] Directory structure overview

### 5. Set up .gitignore

Add to your `.gitignore`:

```
.tmp/
```

### 6. Initialize agent memory files (optional)

Create empty seed files for the dual-mode agents:

```bash
mkdir -p .claude/agents
touch .claude/agents/test-writer.memory.md
touch .claude/agents/design-keeper.memory.md
touch .claude/agents/codebase-researcher.memory.md
touch .claude/agents/code-quality-reviewer.memory.md
touch .claude/agents/performance-reviewer.memory.md
touch .claude/agents/security-reviewer.memory.md
```

These files will be populated automatically as agents accumulate project-specific knowledge.

### 7. Customize prompt-router patterns (optional)

If your team uses a non-English language, add patterns to the prompt-router hook. See `docs/customization.md` for examples.

---

## Verification

After setup, test the plugin by asking Claude to implement a small feature:

```
"Add a greeting message to the home page"
```

You should see:
1. prompt-router detects edit intent and steers toward feature-workflow
2. feature-workflow runs the complexity gate (likely `trivial` for this)
3. implement-feature writes the code with design-keeper consultation
4. test-feature runs static checks
5. Review agents provide feedback

If the workflow gate blocks you unexpectedly, use `#bypass` to override.

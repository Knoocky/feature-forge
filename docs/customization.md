# Customizing feature-forge

## Adding your language to prompt-router

The prompt-router hook classifies user prompts by matching edit-intent and bug-report patterns. By default it only includes English patterns. To add your language:

### Edit `hooks/prompt-router.py`

Find the `EDIT_RE` regex and add your language's edit verbs:

```python
# Example: adding Russian patterns
EDIT_RE = re.compile(
    # English (default)
    r"\b(?:fix|implement|add|build|create|write|refactor|patch|wire up|hook up|make it)\b"
    # Russian — append after the English block
    r"|(?<![а-яёa-z])(?:исправ|поправ|почини|пофикс|реализ|добав|сдела|напиш|созда|обнов|рефактор)[а-яё]*",
    re.IGNORECASE | re.UNICODE,
)
```

Similarly for `BUG_MARKER_RE`:

```python
# Example: adding Russian bug markers
BUG_MARKER_RE = re.compile(
    r"\b(?:bug|broken|doesn'?t work|should be|wrong|crashes)\b"
    r"|(?<![а-яёa-z])(?:баг|не\s+работает|сломал[аось]?|ошибк[аи]|криво)(?![а-яёa-z])",
    re.IGNORECASE | re.UNICODE,
)
```

And `BYPASS_RE`:

```python
BYPASS_RE = re.compile(
    r"#direct|#bypass"
    r"|без\s+workflow|напрямую",
    re.IGNORECASE | re.UNICODE,
)
```

### Run the self-test after changes

```bash
python3 hooks/prompt-router.py --self-test
```

Add your own test cases to `SELF_TEST_CASES` and `BYPASS_CASES` at the bottom of the file.

---

## Configuring type checker and linter commands

The `test-feature` skill needs to know your project's static check commands. Document them in `.claude/PROJECT.md`:

```markdown
## Commands

- **Type check:** `tsc --noEmit` (or `mypy .`, `cargo check`, etc.)
- **Lint:** `eslint . --ext .ts,.tsx` (or `ruff check .`, `clippy`, etc.)
- **Dev server:** `npm run dev` (or `cargo run`, `python manage.py runserver`, etc.)
- **Test suite:** `npm test` (or `pytest`, `cargo test`, etc.)
```

The `test-feature` skill reads PROJECT.md before running checks and uses the documented commands.

---

## Adding project-specific agents to the write guard

If you create your own sub-agents that need write access:

### 1. Add to `hooks/subagent-write-guard.py`

Find the `ALLOWLIST` dict and add your agent:

```python
ALLOWLIST = {
    # ... existing agents ...
    "my-custom-agent": {
        "Edit": [".claude/agents/my-custom-agent.memory.md"],
        "Write": [re.compile(r"^\.tmp/[^/]+/custom/report\.md$")],
    },
}
```

### 2. Create the agent definition

```bash
cat > .claude/agents/my-custom-agent.md << 'EOF'
---
model: sonnet
allowed-tools: [Read, Glob, Grep, Write, Edit]
---

# My Custom Agent

## Role
...

## Constraints
### Write invariant
- `Write` on exactly: `.tmp/<task-slug>/custom/report.md`
- `Edit` on exactly: `.claude/agents/my-custom-agent.memory.md`
EOF
```

---

## Adding workflow skills to the gate

If you create custom skills that should clear the edit-intent gate:

### Edit `hooks/workflow-gate.py`

Find `WORKFLOW_SKILLS` and add your skill name:

```python
WORKFLOW_SKILLS = {
    "feature-workflow",
    "implement-feature",
    "decompose-task",
    "my-custom-workflow",  # your addition
}
```

---

## Adding project-specific skills

Create new skills under `.claude/skills/` in your project (not in the plugin). They'll coexist with feature-forge's skills:

```
your-project/
├── .claude/
│   ├── skills/
│   │   └── my-project-skill/
│   │       └── SKILL.md
│   ├── PROJECT.md
│   └── ARCHITECTURE.md
├── CLAUDE.md
└── src/
```

Project-local skills take precedence if they share a name with a plugin skill.

---

## Disabling specific hooks

If a hook is causing issues, you can disable it in your project's `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": []
      }
    ]
  }
}
```

Project settings override plugin settings for the same hook event + matcher combination.

---

## Component preview / sandbox setup

The `test-on-sandbox` and `test-feature` skills support browser-based component verification. To use them:

1. Document your preview/sandbox URL pattern in `.claude/PROJECT.md`
2. Document how to register a new component in the preview environment
3. Document any auth requirements (the skills avoid routes that need authentication)

If your project doesn't have a component preview environment, these skills will skip browser verification and rely on static checks only.

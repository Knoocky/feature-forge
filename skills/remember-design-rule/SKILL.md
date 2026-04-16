---
name: remember-design-rule
description: Dispatches design-keeper agent in memorize mode to append a visual/UX rule to its persistent memory, so the next implement-feature run auto-applies it during design consultation. Invoke after fixing any visual/UX bug the user reported during manual QA.
allowed-tools: [Read, Bash, Skill, Agent]
---

# Remember Design Rule

## Goal

Turn a user-reported visual/UX defect into a durable design-rule entry, so
the next run of `implement-feature` (and every run after that) automatically
surfaces the rule **before any code is written** — via design-keeper consult
mode. The skill itself writes nothing to agent memory — it is a thin
dispatcher that lets `design-keeper` own its own file.

## When to invoke

After you (the main Claude) have fixed a visual/UX defect that the user
reported during manual QA — things like wrong icon sizes, disabled-state
styling, hover content gaps, view-vs-edit mode confusion, missing shared
components for status fields. The fix happens first, through the normal
dev flow. This skill is the **second step** — the learning hook that
prevents the same visual mistake from recurring on the next feature.

Typical trigger: user says "on this page the trash icon is too small"
→ you fix it → you run this skill → the next `implement-feature` run
that touches any module matching the recorded Area will receive the rule
verbatim during step 3.5 consult.

**Functional bugs belong to `/remember-edge-case`**, not here. If the
defect is about *what the code does* (wrong payload, broken handler,
validation gap) — dispatch `test-writer`. If the defect is about *how it
looks* (spacing, colors, typography, hover, disabled, empty state, icon
size, text copy, view/edit rendering) — dispatch `design-keeper` via this
skill. If you cannot decide, ask the user once.

## Input

Context from the conversation — the skill extracts four fields from what
the user and you already discussed about the defect. No slash-command
argument is needed.

## Steps

### 1. Collect the four rule fields

From the conversation, extract:

- **Area** — module/component area or file path where the rule applies (e.g.
  `src/features/schedule-form/` or a broader glob like
  `src/features/**/ui/form-controls/**`). Err wide enough to catch other
  features with the same pattern, narrow enough that consult's strict
  prefix match still picks it up.
- **UI pattern** — short phrase naming the visual surface (e.g. "disabled
  text input", "row action icon in data table", "hover empty state in
  day cell"). This is the dedupe key, so phrase it concretely.
- **Rule** — what the code MUST do, stated as an invariant. Not "the
  icon was too small"; rather "icon action buttons in rows must be >=20px".
- **Rationale** — *why* — which user-reported incident or design
  principle justifies it. Include the incident date when known so future
  readers can audit the rule.

If **any** field is missing from the conversation, ask the user **one
consolidated question** naming only the missing fields. Do not ask about
fields you already know.

### 2. Dispatch `design-keeper` in memorize mode

Call the agent with a single, explicit memorize prompt. The `MEMORIZE:`
prefix MUST be the first token — design-keeper ignores mid-prompt
mentions.

```
Agent({
  subagent_type: "design-keeper",
  description: "Record design rule to memory",
  prompt: "MEMORIZE: Append this visual/UX rule to your memory.\n\n- Area: <area>\n- UI pattern: <pattern>\n- Rule: <rule>\n- Rationale: <rationale>\n\nFollow your memorize path: dedupe against existing entries by Area + UI pattern (consolidate if a near-match exists), then Edit .claude/agents/design-keeper.memory.md. Return the exact block you wrote so I can verify the text."
})
```

The agent will:
1. Read its memory file.
2. Dedupe by `Area` + `UI pattern`.
3. Either append a new block or consolidate an existing one (adding a
   `- **Also:**` rationale bullet).
4. Return the exact block text and the touched line range.

### 3. Verify no text encoding corruption

Inspect the block text returned by the agent. If it contains **any
multi-byte UTF-8 characters** (quoted UI strings, button labels, tooltip
copy, rationale prose), run the `verify-text-encoding` skill on the memory
file to catch any U+FFFD corruption the `Edit` tool may have introduced:

```
Skill({ skill: "verify-text-encoding", args: ".claude/agents/design-keeper.memory.md" })
```

If the check fails, tell the user and stop — the memory file needs a
manual fix before the next `implement-feature` run. Do not try to
auto-repair.

If the block is pure ASCII, skip this step.

### 4. Confirm to the user

Report in one short block:

- Which file was touched (`.claude/agents/design-keeper.memory.md`)
- Whether it was an **append** or a **consolidate**
- The touched line range
- The exact block text
- Any warnings from `verify-text-encoding`

Do not commit the file — memory lives in the repo but commits follow the
user's normal cadence.

## Output

A short confirmation message to the user. No files written by the skill
itself; the only disk change is inside the agent's isolated context, on
exactly one file.

## Constraints

- **Do NOT** write or edit `.claude/agents/design-keeper.memory.md`
  directly from this skill. All writes go through the `design-keeper`
  agent in memorize mode — this is the single-ownership invariant that
  keeps memory coherent and dedupe-correct.
- **Do NOT** fix the defect here. The fix must already exist in the
  codebase before this skill runs. If it doesn't, stop and tell the user
  to fix first.
- **Do NOT** generate consult blocks here. Consult happens the next time
  `implement-feature` runs and dispatches `design-keeper` in **consult**
  mode at step 3.5 — that's when the new memory entry will surface
  automatically for any matching module.
- **Do NOT** `git add` or `git commit` the memory file. Commits follow
  the user's normal cadence.
- **Do NOT** dispatch `test-writer` from this skill. Functional bugs
  belong to `/remember-edge-case`; this skill is strictly for visual/UX
  rules.

## Learnings

- (updated after each run)

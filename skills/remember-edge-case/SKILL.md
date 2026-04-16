---
name: remember-edge-case
description: Dispatches test-writer agent in memorize mode to append a bug/edge-case entry to its persistent memory, so future test runs auto-generate a regression case without being asked. Invoke after fixing any bug the user reported during manual QA.
allowed-tools: [Read, Bash, Skill, Agent]
---

# Remember Edge Case

## Goal

Turn a user-reported bug into a durable regression test heuristic, so the next
run of `test-feature` (and every run after that) automatically covers the same
failure mode without being asked. The skill itself writes nothing — it is a
thin dispatcher that lets `test-writer` own its own memory.

## When to invoke

After you (the main Claude) have fixed a bug that the user reported during
manual QA. The fix happens first, through the normal dev flow. This skill is
the **second step** — the learning hook that prevents the bug from coming
back.

Typical trigger: user says "I found a bug: ..." → you fix it → you run this
skill → the user's next manual QA session benefits from automatic regression
coverage.

## Input

Context from the conversation — the skill extracts four fields from what the
user and you already discussed about the bug. No slash-command argument is
needed.

## Steps

### 1. Collect the four bug fields

From the conversation, extract:

- **Area** — module/component area or file path where the bug lives (e.g.
  `src/features/checkout-form/` or `src/components/data-table/model/schema.ts`).
- **Root cause** — *why* the bug exists, not just *what* it does. Name the
  missing check, the wrong type, the off-by-one, the assumption.
- **Manifestation** — what the user actually saw (error toast, white screen,
  wrong value in the list, failed network call, etc.).
- **Test heuristic** — one sentence describing what a future test should check
  to prevent recurrence. Phrase it as a rule, not a re-description of the bug.

If **any** field is missing from the conversation, ask the user **one
consolidated question** naming only the missing fields. Do not ask about
fields you already know.

### 2. Dispatch `test-writer` in memorize mode

Call the agent with a single, explicit memorize prompt:

```
Agent({
  subagent_type: "test-writer",
  description: "Record edge case to memory",
  prompt: "MEMORIZE: Append this bug to your memory file.\n\n- Area: <area>\n- Root cause: <cause>\n- Manifestation: <manif>\n- Test heuristic: <heuristic>\n\nFollow your memorize path: dedupe against existing entries (consolidate if a near-match exists), then Edit .claude/agents/test-writer.memory.md. Return the exact block you wrote so I can verify the text."
})
```

The agent will:
1. Read its memory file.
2. Dedupe by `Area` + root cause.
3. Either append a new block or consolidate an existing one.
4. Return the exact block text and the touched line range.

### 3. Verify no text encoding corruption

Inspect the block text returned by the agent. If it contains **any multi-byte
UTF-8 characters** (quoted UI strings, error messages, non-ASCII text), run the
`verify-text-encoding` skill on the memory file to catch any U+FFFD corruption
the `Edit` tool may have introduced:

```
Skill({ skill: "verify-text-encoding", args: ".claude/agents/test-writer.memory.md" })
```

If the check fails, tell the user and stop — the memory file needs a manual
fix before the next `test-feature` run. Do not try to auto-repair.

If the block is pure ASCII, skip this step.

### 4. Confirm to the user

Report in one short block:

- Which file was touched (`.claude/agents/test-writer.memory.md`)
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

- **Do NOT** write or edit `.claude/agents/test-writer.memory.md` directly
  from this skill. All writes go through the `test-writer` agent in memorize
  mode — this is the single-ownership invariant that keeps memory coherent.
- **Do NOT** fix the bug here. The fix must already exist in the codebase
  before this skill runs. If it doesn't, stop and tell the user to fix first.
- **Do NOT** generate test cases here. Test generation happens the next time
  `test-feature` runs and dispatches `test-writer` in **generate** mode —
  that's when the new memory entry will turn into a regression case
  automatically.
- **Do NOT** `git add` or `git commit` the memory file. Commits follow the
  user's normal cadence.

## Learnings

- (updated after each run)

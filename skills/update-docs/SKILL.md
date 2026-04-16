---
name: update-docs
description: Actualize project AI documentation (.claude/ARCHITECTURE.md, .claude/PROJECT.md, identity files) after a feature is shipped. Final phase of feature-workflow, also usable when docs drift from code.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob]
---

# Update Docs

## Goal

Keep Claude's knowledge base in sync with the code:
- `.claude/ARCHITECTURE.md` reflects the current source file tree and module catalog
- `.claude/PROJECT.md` reflects current conventions and patterns
- Identity files (project instruction files like `CLAUDE.md` and any copies) stay byte-identical
- No obsolete references, no dead paths

## Input

Context file path — usually `.tmp/<task-slug>/notes/context.md`. Read:
- `## Changed files` (what shipped)
- `## Iteration log` (what decisions were made — may reveal new conventions worth documenting)

## Steps

### 1. ARCHITECTURE.md — catalog sync

For each file in `## Changed files`:

| Change | Action in `.claude/ARCHITECTURE.md` |
|--------|-------------------------------------|
| New file under a feature module | Add row to features catalog |
| New file under a widget module | Add row to widgets catalog |
| New file under a page module | Add row to pages catalog |
| New file under an entity module | Add row to entities catalog |
| New file under shared UI | Add row to shared UI catalog |
| File renamed | Update path in existing row |
| File deleted | Delete row |
| File edited (purpose unchanged) | No doc change |
| File edited (purpose changed significantly) | Update row description |

Open `.claude/ARCHITECTURE.md`, find the matching catalog table, insert/update/delete rows. Keep catalog alphabetically sorted within each layer.

### 2. PROJECT.md — convention sync

Check `## Iteration log` for any of these signals that a new convention was established:

| Signal in iteration log | Update in `.claude/PROJECT.md` |
|-------------------------|--------------------------------|
| "New form control pattern" | `## Shared UI` section |
| "New API endpoint pattern" | `## API Layer` |
| "User said 'always do X from now on'" | matching section |
| "New styling technique used + approved" | `## Styles` section |
| "New data fetching pattern" | `## Data Fetching` |
| "New prohibited pattern discovered" | `## Prohibited Patterns` |

**Do NOT** add one-off implementation notes. Only durable, repeatable conventions go here. If in doubt — don't add.

### 3. Identity files sync (only if PROJECT.md or the main instruction file changed)

If you edited the main project instruction file (e.g. `CLAUDE.md`) in any way:

```bash
# Guard against identity files being symlinks — past incident
for f in <list-of-identity-file-copies>; do
  if [ -L "$f" ]; then rm "$f"; fi
done

# Copy main instruction file to all identity copies
cp <main-instruction-file> <copy-1>
cp <main-instruction-file> <copy-2>

shasum <main-instruction-file> <copy-1> <copy-2>
```

All hashes must match. If they don't — re-run `cp`.

### 4. Verify no regressions

```bash
# Dead files referenced?
grep -rn 'src/<deleted-path>' .claude/ 2>/dev/null         # expect empty
```

### 5. Record the change in context.md

Append to `.tmp/<task-slug>/notes/context.md`:

```markdown
## Docs update (Phase N, <timestamp>)
- .claude/ARCHITECTURE.md: <added/updated N rows | no changes>
- .claude/PROJECT.md: <added section X | no changes>
- Identity files: <synced | not touched>
- shasum: <hash>
```

## Output

- Updated `.claude/ARCHITECTURE.md` / `.claude/PROJECT.md` / identity files (or "no updates needed")
- Verification report (shasum, grep counts) appended to `context.md`
- Summary to orchestrator: list of changed doc files + confirmation of identity-file sync

## Constraints

- Do NOT create new `.md` files unless the user explicitly asked
- Do NOT touch `README.md` — it's for the human team, updates go through PR review
- Do NOT touch user memory files — those update via auto-memory rules, not here
- Identity files MUST stay byte-identical — never edit just one

## Learnings

- (updated after each run)

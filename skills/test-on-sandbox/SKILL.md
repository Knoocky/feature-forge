---
name: test-on-sandbox
description: Use after any change to a reusable UI component, form control, modal, or feature block. Spins up an isolated dev server on a free port, registers the component in the project's preview/sandbox environment if missing, verifies it via Playwright MCP, saves a screenshot to .tmp/<task-slug>/screenshots/, then tears down browser and server.
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__playwright__browser_navigate, mcp__playwright__browser_snapshot, mcp__playwright__browser_click, mcp__playwright__browser_fill_form, mcp__playwright__browser_press_key, mcp__playwright__browser_take_screenshot, mcp__playwright__browser_console_messages, mcp__playwright__browser_close
---

# test-on-sandbox

## Goal

Every UI change is visually verified in an isolated component preview environment, screenshotted into `.tmp/<task-slug>/screenshots/`, and the dev server is torn down cleanly afterwards — so the user's own dev server is never disturbed and no zombie processes remain.

## Input

- `componentPath` — path to the changed component (e.g. `src/shared/ui/select-control/select-control.tsx`)
- `states` — list of variants/props/scenarios to verify (e.g. `["empty", "loading", "with-error", "long-list"]`)
- `ticket` (optional) — issue/ticket ID; if missing, derive from current branch or fall back to `manual`

## Steps

1. **Locate or create sandbox entry.**
   - Read the project's component preview entry index file.
   - If an entry already covers this component → reuse it.
   - Otherwise create a new preview entry file exporting `meta: { name, group }` plus one named variant per `state`.
   - Register the new entry in the barrel/index file.

2. **Pick a free port.**
   - Try the project's default dev port first: `lsof -nP -iTCP:<default-port> -sTCP:LISTEN -t`
   - If occupied → walk incrementing ports, take the first free one
   - Save the chosen port as `SBX_PORT`. If everything is busy → FAIL with a clear message

3. **Start the dev server in the background.**
   - `Bash` with `run_in_background: true`: `PORT=$SBX_PORT <dev-server-start-command>`
   - Capture the returned `task_id`

4. **Wait until ready.**
   - Poll `curl -sf -o /dev/null -w "%{http_code}" http://127.0.0.1:$SBX_PORT/<sandbox-route>` every 1.5s
   - Up to 30 attempts (~45s)
   - On non-200 after the deadline → run cleanup (step 10) and FAIL with the last 50 lines of the dev server log via `TaskOutput`

5. **Navigate Playwright.**
   - `mcp__playwright__browser_navigate` → `http://127.0.0.1:$SBX_PORT/<sandbox-route>`
   - **Never** navigate to authenticated pages — auth providers will block unauthenticated access

6. **Snapshot ARIA tree.**
   - `mcp__playwright__browser_snapshot`
   - Locate the element matching `meta.name`, click into it

7. **Drive each state.**
   - For each item in `states`: `browser_click` / `browser_fill_form` / `browser_press_key`
   - After each interaction take a fresh ARIA snapshot to confirm the DOM updated as expected

8. **Capture console errors.**
   - `mcp__playwright__browser_console_messages` with `level: "error"`
   - Record findings into the report — but do NOT fail fast; continue to cleanup so we never leak a server

9. **Take screenshots.**
   - `mcp__playwright__browser_take_screenshot` with `filename: ".tmp/<task-slug>/screenshots/<component>-<state>.png"`
   - Derive `<task-slug>` from the current branch ticket ID plus 1-3 kebab-case words summarizing the task; if no ticket, use just `<word1>-<word2>-<word3>`. Create the directory with `mkdir -p` before the first screenshot.
   - One screenshot per state. **Never** save to the project root or any non-`.tmp/` location

10. **CLEANUP — mandatory, runs even on failure.**
    - `mcp__playwright__browser_close`
    - `TaskStop` with the dev server `task_id`
    - **Safety net** (in case the background task didn't kill the child): `lsof -nP -iTCP:$SBX_PORT -sTCP:LISTEN -t | xargs -r kill`
    - Verify with a second `lsof` that nothing listens on `$SBX_PORT` anymore

11. **Static checks on touched files.**
    - Run the project's type checker
    - Run the project's linter (scope to the changed paths if supported; otherwise full lint)

## Output Format

A markdown report with:

- **Sandbox entries** — created or modified file paths
- **Port** — the chosen `$SBX_PORT`
- **Screenshots** — list of `.tmp/<task-slug>/screenshots/*.png` paths
- **Console errors** — list (or "none")
- **Type check** — PASS / FAIL with first error if FAIL
- **Lint** — PASS / FAIL with first error if FAIL
- **Verdict** — overall PASS / FAIL
- **Cleanup** — explicit confirmation that browser was closed and `$SBX_PORT` is free

## Learnings

- (Updated automatically after each run)

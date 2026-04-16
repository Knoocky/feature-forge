#!/usr/bin/env python3
"""
PreToolUse hook — harness-level enforcement of the sub-agent write invariant.

Rule: main Claude is unrestricted. Sub-agents dispatched via the Agent tool may
only Edit/Write a narrow per-agent allowlist of paths. Any other Edit/Write by
a sub-agent is rejected with exit code 2 and a clear stderr message that the
caller sees.

How sub-agents are detected: the PreToolUse payload contains `agent_id` and
`agent_type` when (and only when) the current tool call is made by a sub-agent.
Main Claude calls have neither field. We key off `agent_type`.

Fail-open policy: if the payload cannot be parsed, or if the tool is neither
Edit nor Write, the hook returns 0 (allow). Blocking on hook bugs would lock
the user out of their own repo. The guarantee we provide is "sub-agents cannot
escape the allowlist"; it is not "no write ever slips through a broken hook".

Adding a new sub-agent: append an entry to ALLOWLIST below. If the agent has
no legitimate write target, set both keys to empty lists — the hook will then
reject every Edit/Write from that agent.
"""
import json
import os
import re
import sys


# ---------------------------------------------------------------------------
# Per-agent allowlist
#
# Each key is an agent_type string. Values are dicts with "Edit" and "Write"
# keys, each mapping to a list of allowed paths. Entries can be:
#   - literal strings (exact match after normalization)
#   - compiled regex patterns (match against normalized relative path)
#
# To add a new agent, append an entry here. If the agent should never write,
# set both to empty lists.
# ---------------------------------------------------------------------------

ALLOWLIST = {
    "codebase-researcher": {
        "Edit": [".claude/agents/codebase-researcher.memory.md"],
        "Write": [re.compile(r"^\.tmp/[^/]+/research/codebase-map\.md$")],
    },
    "code-quality-reviewer": {
        "Edit": [".claude/agents/code-quality-reviewer.memory.md"],
        "Write": [re.compile(r"^\.tmp/[^/]+/reviews/code-quality\.md$")],
    },
    "performance-reviewer": {
        "Edit": [".claude/agents/performance-reviewer.memory.md"],
        "Write": [re.compile(r"^\.tmp/[^/]+/reviews/performance\.md$")],
    },
    "security-reviewer": {
        "Edit": [".claude/agents/security-reviewer.memory.md"],
        "Write": [re.compile(r"^\.tmp/[^/]+/reviews/security\.md$")],
    },
    "test-writer": {
        "Edit": [".claude/agents/test-writer.memory.md"],
        "Write": [],
    },
    "design-keeper": {
        "Edit": [".claude/agents/design-keeper.memory.md"],
        "Write": [],
    },
}


def normalize_path(file_path: str, cwd: str) -> str:
    if not file_path:
        return ""
    abs_target = os.path.abspath(
        file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path)
    )
    abs_cwd = os.path.abspath(cwd)
    if abs_target == abs_cwd:
        return ""
    if abs_target.startswith(abs_cwd + os.sep):
        return abs_target[len(abs_cwd) + 1 :]
    return abs_target


def is_path_allowed(path: str, allowed_entries) -> bool:
    for entry in allowed_entries:
        if isinstance(entry, str):
            if path == entry:
                return True
        elif hasattr(entry, "match"):
            if entry.match(path):
                return True
    return False


def format_allowed(allowed_entries) -> str:
    if not allowed_entries:
        return "NONE"
    return ", ".join(
        entry if isinstance(entry, str) else entry.pattern for entry in allowed_entries
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(
            f"subagent-write-guard: could not parse PreToolUse payload ({exc}); allowing.",
            file=sys.stderr,
        )
        return 0

    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Edit", "Write"):
        return 0

    agent_type = payload.get("agent_type") or payload.get("agent_id")
    if not agent_type:
        return 0

    rules = ALLOWLIST.get(agent_type)
    if rules is None:
        print(
            f"subagent-write-guard: sub-agent '{agent_type}' has no allowlist entry. "
            f"Add one to the ALLOWLIST in subagent-write-guard.py if this is intentional.",
            file=sys.stderr,
        )
        return 2

    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "") or ""
    cwd = payload.get("cwd") or os.getcwd()
    rel_path = normalize_path(file_path, cwd)

    allowed_entries = rules.get(tool_name, [])
    if is_path_allowed(rel_path, allowed_entries):
        return 0

    print(
        f"subagent-write-guard: sub-agent '{agent_type}' is not allowed to "
        f"{tool_name} '{rel_path or file_path}'. "
        f"Allowed {tool_name} paths: {format_allowed(allowed_entries)}.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

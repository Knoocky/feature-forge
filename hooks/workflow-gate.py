#!/usr/bin/env python3
"""
PreToolUse hook — hard enforcement of the prompt-router edit-intent gate.

Companion to prompt-router.py. When prompt-router classifies a user turn as
edit-intent (its EDIT_REMINDER fires), it writes a per-session state file
marking the gate "armed". This hook then refuses every main-agent
Edit/Write/MultiEdit on that turn until one of these happens:

  1. Main agent invokes a workflow Skill (feature-workflow, implement-feature,
     or decompose-task). The Skill PreToolUse event is captured here and
     flips `workflow_invoked=true` in the state file.
  2. The user reissues the prompt with a bypass token (#direct or #bypass).
     prompt-router detects that and writes `bypass=true` into the same
     state file.

Why this exists: the soft reminder the prompt-router injects via
`additionalContext` is advisory — the model can rationalize past it.
This hook provides hard enforcement: `exit 2` blocks the tool call.

Scope: main agent only. Sub-agent Edit/Write is already handled by
`subagent-write-guard.py` (per-agent allowlist). This hook short-circuits
when `agent_type` is present in the payload.

State file:
  .tmp/.prompt-router-state/<session_id>.json
  {"edit_intent": bool, "workflow_invoked": bool, "bypass": bool}

Fail-open policy: any parse error, missing file, or missing session_id
returns 0 (allow). Broken hooks must not lock the user out of their repo.
"""
import json
import os
import sys


# Skills that, when invoked, clear the edit-intent gate for the rest
# of the turn. Add your project-specific workflow skills here.
WORKFLOW_SKILLS = {
    "feature-workflow",
    "implement-feature",
    "decompose-task",
}

GUARDED_TOOLS = {"Edit", "Write", "MultiEdit"}


def state_path(cwd: str, session_id: str) -> str:
    return os.path.join(
        cwd, ".tmp", ".prompt-router-state", f"{session_id}.json"
    )


def load_state(path: str) -> dict:
    try:
        with open(path, "r") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def save_state(path: str, state: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(state, f)
    except Exception:
        pass


def handle_skill(payload: dict) -> int:
    tool_input = payload.get("tool_input") or {}
    skill_name = (tool_input.get("skill") or "").strip()
    if skill_name not in WORKFLOW_SKILLS:
        return 0

    session_id = payload.get("session_id") or ""
    cwd = payload.get("cwd") or os.getcwd()
    if not session_id:
        return 0

    path = state_path(cwd, session_id)
    state = load_state(path)
    state["workflow_invoked"] = True
    save_state(path, state)
    return 0


def handle_edit(payload: dict) -> int:
    # Sub-agent writes are governed by subagent-write-guard; leave them alone.
    agent_type = payload.get("agent_type") or payload.get("agent_id")
    if agent_type:
        return 0

    session_id = payload.get("session_id") or ""
    cwd = payload.get("cwd") or os.getcwd()
    if not session_id:
        return 0

    state = load_state(state_path(cwd, session_id))
    if not state:
        return 0
    if not state.get("edit_intent"):
        return 0
    if state.get("workflow_invoked"):
        return 0
    if state.get("bypass"):
        return 0

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""

    print(
        "workflow-gate: BLOCKED.\n"
        "\n"
        f"prompt-router flagged the current turn as edit-intent, so direct "
        f"{tool_name} on '{file_path}' is refused.\n"
        "\n"
        "Resolve by ONE of:\n"
        "  1. Invoke Skill(feature-workflow) (or Skill(implement-feature) for "
        "a narrow one-shot). The skill will own the edit and this gate "
        "will clear for the rest of the turn.\n"
        "  2. Ask the user to reissue the request with a bypass token in "
        "the prompt text: #direct or #bypass. prompt-router will pick it "
        "up on the next UserPromptSubmit and the gate will allow direct "
        "edits for that turn.\n"
        "\n"
        "Do NOT retry Edit/Write until one of the above is satisfied — the "
        "gate will just block again.",
        file=sys.stderr,
    )
    return 2


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_name = payload.get("tool_name", "")

    if tool_name == "Skill":
        return handle_skill(payload)

    if tool_name in GUARDED_TOOLS:
        return handle_edit(payload)

    return 0


# ---------------------------------------------------------------------------
# Self-test harness — run: python3 workflow-gate.py --self-test
# ---------------------------------------------------------------------------

def _make_payload(tool_name, session_id="s1", cwd=".", tool_input=None,
                  agent_type=None):
    p = {
        "tool_name": tool_name,
        "session_id": session_id,
        "cwd": cwd,
        "tool_input": tool_input or {},
    }
    if agent_type:
        p["agent_type"] = agent_type
    return p


def _write_state(cwd, session_id, state):
    path = state_path(cwd, session_id)
    save_state(path, state)


def _cleanup_state(cwd, session_id):
    try:
        os.remove(state_path(cwd, session_id))
    except Exception:
        pass


def run_self_test() -> int:
    import io
    import tempfile

    passed = 0
    failed = 0
    with tempfile.TemporaryDirectory() as tmp:
        def run(label, payload, expected_exit, setup_state=None):
            nonlocal passed, failed
            session_id = payload.get("session_id") or ""
            payload["cwd"] = tmp
            if session_id:
                _cleanup_state(tmp, session_id)
                if setup_state is not None:
                    _write_state(tmp, session_id, setup_state)

            sys.stdin = io.StringIO(json.dumps(payload))
            try:
                rc = main()
            finally:
                sys.stdin = sys.__stdin__

            ok = rc == expected_exit
            mark = "PASS" if ok else "FAIL"
            if ok:
                passed += 1
            else:
                failed += 1
            print(f"{mark}: {label:<60s} rc={rc} (want {expected_exit})")

        run(
            "edit with no state file -> allow",
            _make_payload("Edit", tool_input={"file_path": "src/a.ts"}),
            0,
        )
        run(
            "edit with edit_intent=false -> allow",
            _make_payload("Edit", tool_input={"file_path": "src/a.ts"}),
            0,
            setup_state={"edit_intent": False, "workflow_invoked": False, "bypass": False},
        )
        run(
            "edit with edit_intent=true, nothing else -> BLOCK",
            _make_payload("Edit", tool_input={"file_path": "src/a.ts"}),
            2,
            setup_state={"edit_intent": True, "workflow_invoked": False, "bypass": False},
        )
        run(
            "edit with workflow_invoked=true -> allow",
            _make_payload("Edit", tool_input={"file_path": "src/a.ts"}),
            0,
            setup_state={"edit_intent": True, "workflow_invoked": True, "bypass": False},
        )
        run(
            "edit with bypass=true -> allow",
            _make_payload("Edit", tool_input={"file_path": "src/a.ts"}),
            0,
            setup_state={"edit_intent": True, "workflow_invoked": False, "bypass": True},
        )
        run(
            "Write tool blocked same as Edit",
            _make_payload("Write", tool_input={"file_path": "src/a.ts"}),
            2,
            setup_state={"edit_intent": True, "workflow_invoked": False, "bypass": False},
        )
        run(
            "MultiEdit tool blocked same as Edit",
            _make_payload("MultiEdit", tool_input={"file_path": "src/a.ts"}),
            2,
            setup_state={"edit_intent": True, "workflow_invoked": False, "bypass": False},
        )
        run(
            "sub-agent Edit bypassed (agent_type set)",
            _make_payload("Edit", tool_input={"file_path": "src/a.ts"},
                          agent_type="test-writer"),
            0,
            setup_state={"edit_intent": True, "workflow_invoked": False, "bypass": False},
        )
        run(
            "non-guarded tool (Bash) -> allow",
            _make_payload("Bash", tool_input={"command": "ls"}),
            0,
            setup_state={"edit_intent": True, "workflow_invoked": False, "bypass": False},
        )
        run(
            "skill(feature-workflow) -> flip workflow_invoked",
            _make_payload("Skill", tool_input={"skill": "feature-workflow"}),
            0,
            setup_state={"edit_intent": True, "workflow_invoked": False, "bypass": False},
        )
        flipped = load_state(state_path(tmp, "s1"))
        ok = flipped.get("workflow_invoked") is True
        mark = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"{mark}: {'skill flip persisted in state file':<60s} state={flipped}")

        run(
            "skill(implement-feature) -> flip workflow_invoked",
            _make_payload("Skill", tool_input={"skill": "implement-feature"}),
            0,
            setup_state={"edit_intent": True, "workflow_invoked": False, "bypass": False},
        )
        flipped = load_state(state_path(tmp, "s1"))
        ok = flipped.get("workflow_invoked") is True
        mark = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"{mark}: {'implement-feature flip persisted':<60s} state={flipped}")

        run(
            "skill(unrelated) -> no flip",
            _make_payload("Skill", tool_input={"skill": "verify-text-encoding"}),
            0,
            setup_state={"edit_intent": True, "workflow_invoked": False, "bypass": False},
        )
        flipped = load_state(state_path(tmp, "s1"))
        ok = flipped.get("workflow_invoked", False) is False
        mark = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"{mark}: {'unrelated skill did not flip':<60s} state={flipped}")

        run(
            "missing session_id -> allow (fail-open)",
            {"tool_name": "Edit", "cwd": tmp,
             "tool_input": {"file_path": "src/a.ts"}},
            0,
            setup_state={"edit_intent": True, "workflow_invoked": False, "bypass": False},
        )

    print(f"\n{passed} passed, {failed} failed, {passed + failed} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        sys.exit(run_self_test())
    sys.exit(main())

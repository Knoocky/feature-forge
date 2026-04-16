#!/usr/bin/env python3
"""
UserPromptSubmit hook — soft-steer the main Claude toward project workflows.

Rule: main Claude is free to do anything. This hook inspects each user prompt
and, if it looks like (a) a code-edit request or (b) a bug report, injects a
short reminder into the model's context via `hookSpecificOutput.additionalContext`.

This is a soft gate. It never blocks a prompt. It never exits 2. Every code
path returns exit 0:
  - hit  -> exit 0 with a JSON body on stdout
  - miss -> exit 0 with empty stdout
  - parse error -> exit 0 with empty stdout (fail-open)

Customization: to add patterns for your language (e.g. Russian, Chinese, etc.),
append regex alternatives to EDIT_RE and BUG_MARKER_RE below. See
docs/customization.md for examples.

Run self-test:
    python3 prompt-router.py --self-test
"""
import json
import os
import re
import sys


# ---------------------------------------------------------------------------
# Edit-intent patterns
#
# English verbs that signal the user wants to change code.
# To add your language, append alternatives after the English block.
# Example for Russian:
#   r"|(?<![а-яёa-z])(?:исправ|поправ|реализ|добав)[а-яё]*"
# ---------------------------------------------------------------------------
EDIT_RE = re.compile(
    r"\b(?:fix|implement|add|build|create|write|refactor|patch|wire up|hook up|make it)\b",
    re.IGNORECASE | re.UNICODE,
)

# Exclusions: prompts that match EDIT_RE by accident but are not code intent.
# If exclusion fires, edit reminder is suppressed.
EXCLUDE_RE = re.compile(
    r"\b(?:meeting|bookmark|remind me)\b",
    re.IGNORECASE | re.UNICODE,
)

# Bug-report marker words — unambiguous single-word triggers.
# Add your language's equivalents as alternatives.
BUG_MARKER_RE = re.compile(
    r"\b(?:bug|broken|doesn'?t work|should be|wrong|crashes)\b",
    re.IGNORECASE | re.UNICODE,
)

# Bug-list shape: 2+ numbered list items. Captures "1. ...\n2. ..." etc.
BUG_LIST_RE = re.compile(
    r"^\s*\d+[\.\)]\s+\S.*(?:\r?\n\s*\d+[\.\)]\s+\S.*){1,}",
    re.MULTILINE,
)

# Explicit bypass tokens — the user's escape hatch when prompt-router
# misclassifies a turn. Detecting any of these causes the workflow-gate
# to let direct Edit/Write through for this turn.
# Add your language's equivalents if needed.
BYPASS_RE = re.compile(
    r"#direct|#bypass",
    re.IGNORECASE | re.UNICODE,
)


EDIT_REMINDER = (
    "[prompt-router] This request looks like a code change. "
    "Route through the `feature-workflow` skill (or `implement-feature` "
    "for a narrow one-shot). Do not start editing files before invoking it."
)

BUG_REMINDER = (
    "[prompt-router] This request looks like a bug list. "
    "After fixing each item, classify it: functional regression "
    "-> invoke `/remember-edge-case`; visual/UX rule "
    "-> invoke `/remember-design-rule`."
)


def classify(prompt: str) -> list:
    """Return a list of reminder strings to inject (0, 1, or 2 entries)."""
    reminders = []
    if prompt:
        if not EXCLUDE_RE.search(prompt) and EDIT_RE.search(prompt):
            reminders.append(EDIT_REMINDER)
        if BUG_MARKER_RE.search(prompt) or BUG_LIST_RE.search(prompt):
            reminders.append(BUG_REMINDER)
    return reminders


def write_gate_state(cwd: str, session_id: str,
                     edit_intent: bool, bypass: bool) -> None:
    """Persist the per-turn gate state for workflow-gate.py to read.

    Rewritten from scratch on every UserPromptSubmit — each user turn is an
    independent classification. The sibling hook workflow-gate.py consumes
    this file on PreToolUse and decides whether to allow direct Edit/Write.
    """
    try:
        directory = os.path.join(cwd, ".tmp", ".prompt-router-state")
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, f"{session_id}.json")
        with open(path, "w") as f:
            json.dump(
                {
                    "edit_intent": edit_intent,
                    "workflow_invoked": False,
                    "bypass": bypass,
                },
                f,
            )
    except Exception:
        pass


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    prompt = payload.get("prompt") or ""
    session_id = payload.get("session_id") or ""
    cwd = payload.get("cwd") or os.getcwd()

    reminders = classify(prompt)
    edit_intent = EDIT_REMINDER in reminders
    bypass = bool(BYPASS_RE.search(prompt)) if prompt else False

    if session_id:
        write_gate_state(cwd, session_id, edit_intent, bypass)

    if not reminders:
        return 0

    additional_context = "\n\n---\n\n".join(reminders)
    if edit_intent and not bypass:
        additional_context += (
            "\n\n---\n\n"
            "[prompt-router] Enforcement note: the workflow-gate PreToolUse "
            "hook is now armed for this turn. Direct Edit/Write/MultiEdit "
            "will be refused with exit 2 until Skill(feature-workflow) or "
            "Skill(implement-feature) is invoked. If that is wrong for this "
            "turn, ask the user to reissue with a bypass token "
            "(#direct or #bypass)."
        )

    response = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": additional_context,
        }
    }
    sys.stdout.write(json.dumps(response))
    return 0


# ---------------------------------------------------------------------------
# Self-test harness
# ---------------------------------------------------------------------------

SELF_TEST_CASES = [
    # (label, prompt, expected_has_edit, expected_has_bug)
    ("en edit verb 'fix'",            "fix the date picker bug",                               True,  True),
    ("en edit verb 'implement'",      "implement the sidebar collapse",                        True,  False),
    ("en edit verb 'add'",            "add validation to the form",                            True,  False),
    ("en bug marker 'broken'",        "the form is broken after submit",                       False, True),
    ("en bug marker 'crashes'",       "the app crashes on empty input",                        False, True),
    ("numbered bug list",             "1. button does not respond\n2. field is empty\n3. save fails", False, True),
    ("combined edit + list",          "fix 3 bugs from the list:\n1. one\n2. two",             True,  True),
    ("exclusion: meeting reminder",   "remind me about the meeting tomorrow",                  False, False),
    ("exclusion: bookmark",           "add a bookmark for this page",                          False, False),
    ("plain question",                "what is the architecture?",                             False, False),
]

BYPASS_CASES = [
    # (label, prompt, expected_bypass)
    ("bypass #direct",          "fix src/a.ts #direct",         True),
    ("bypass #bypass",          "add a line to the file #bypass", True),
    ("no bypass in plain edit", "fix the calendar",             False),
    ("no bypass in plain text", "what is this?",                False),
]


def run_self_test() -> int:
    passed = 0
    failed = 0
    for label, prompt, want_edit, want_bug in SELF_TEST_CASES:
        reminders = classify(prompt)
        has_edit = EDIT_REMINDER in reminders
        has_bug = BUG_REMINDER in reminders
        ok = has_edit == want_edit and has_bug == want_bug
        mark = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        print(
            f"{mark}: {label:<32s} "
            f"edit={int(has_edit)}(want {int(want_edit)}) "
            f"bug={int(has_bug)}(want {int(want_bug)})"
        )

    for label, prompt, want_bypass in BYPASS_CASES:
        has_bypass = bool(BYPASS_RE.search(prompt))
        ok = has_bypass == want_bypass
        mark = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        print(
            f"{mark}: {label:<32s} "
            f"bypass={int(has_bypass)}(want {int(want_bypass)})"
        )

    print(f"\n{passed} passed, {failed} failed, {passed + failed} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        sys.exit(run_self_test())
    sys.exit(main())

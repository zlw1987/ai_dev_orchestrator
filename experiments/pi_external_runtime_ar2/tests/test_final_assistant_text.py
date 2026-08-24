"""FU-D -- ``final_assistant_text`` must really be assistant text.

Before this fix, ``_text_from_message`` extracted text from ANY
``message_end``/``turn_end`` message regardless of ``role``. AR2's R1-a run
record demonstrates the resulting defect exactly: its stored
``final_assistant_text`` field is the USER/TASK PROMPT that was sent, not
anything the model said, while ``FINDINGS.md`` correctly describes the actual
assistant response as empty (the turn settled in 0.382 s with zero tool calls
and no provider-reported usage).

This module drives the REAL ``PiRpcSupervisor._absorb`` / ``_text_from_message``
against synthetic in-memory records -- no process, no fake Pi script, no
network -- so the collector defect and its fix are pinned deterministically.

The historical R1-a JSON is NOT modified; see ``FINDINGS.md`` for the
truthfulness note.
"""

from __future__ import annotations

from ar2.supervisor import PiRpcSupervisor, RunBounds, _text_from_message


def _supervisor() -> PiRpcSupervisor:
    """A supervisor with no process attached -- ``_absorb`` never touches one."""
    return PiRpcSupervisor(argv=(), cwd=".", environment={}, bounds=RunBounds())


# -- _text_from_message, unit level ---------------------------------------------


def test_an_assistant_message_contributes_text():
    message = {
        "role": "assistant",
        "content": [{"type": "text", "text": "Done."}],
    }
    assert _text_from_message(message) == "Done."


def test_an_assistant_message_with_plain_string_content_contributes_text():
    assert _text_from_message({"role": "assistant", "content": "Done."}) == "Done."


def test_a_user_message_contributes_nothing():
    """The exact R1-a shape: the task prompt arriving as a user message."""
    user_message = {
        "role": "user",
        "content": [{"type": "text", "text": "Fix calc.py so the documented behavior holds."}],
    }
    assert _text_from_message(user_message) == ""


def test_a_tool_message_contributes_nothing():
    tool_message = {
        "role": "tool",
        "content": [{"type": "text", "text": "aido_read ok: bytes=123"}],
    }
    assert _text_from_message(tool_message) == ""


def test_a_system_message_contributes_nothing():
    system_message = {"role": "system", "content": [{"type": "text", "text": "You are Pi."}]}
    assert _text_from_message(system_message) == ""


def test_a_message_with_a_missing_role_contributes_nothing():
    assert _text_from_message({"content": [{"type": "text", "text": "no role at all"}]}) == ""


def test_a_message_with_an_unknown_role_contributes_nothing():
    assert (
        _text_from_message({"role": "narrator", "content": [{"type": "text", "text": "x"}]}) == ""
    )


def test_a_non_dict_message_contributes_nothing():
    assert _text_from_message(None) == ""
    assert _text_from_message("just a string") == ""
    assert _text_from_message(["a", "list"]) == ""


# -- PiRpcSupervisor._absorb, the R1-a shape end to end -------------------------


def test_the_r1a_shape_leaves_final_assistant_text_empty():
    """user prompt message_end, no assistant response -> final_assistant_text
    stays empty, matching what FINDINGS.md says actually happened in R1-a."""
    supervisor = _supervisor()
    supervisor._absorb(
        {
            "type": "message_end",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "The function within_limit in calc.py is documented to "
                            "return True when value is less than OR EQUAL TO limit..."
                        ),
                    }
                ],
            },
        }
    )
    assert supervisor.activity.final_assistant_text == ""


def test_a_genuine_assistant_message_end_updates_final_assistant_text():
    supervisor = _supervisor()
    supervisor._absorb(
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "The broker refused the edit."}],
            },
        }
    )
    assert supervisor.activity.final_assistant_text == "The broker refused the edit."


def test_a_user_message_end_never_overwrites_a_prior_genuine_assistant_text():
    supervisor = _supervisor()
    supervisor._absorb(
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "First real answer."}],
            },
        }
    )
    supervisor._absorb(
        {
            "type": "turn_end",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "a later user turn, e.g. a retry prompt"}],
            },
        }
    )
    assert supervisor.activity.final_assistant_text == "First real answer."


def test_a_tool_role_message_end_does_not_update_final_assistant_text():
    supervisor = _supervisor()
    supervisor._absorb(
        {
            "type": "turn_end",
            "message": {
                "role": "tool",
                "content": [{"type": "text", "text": "aido_edit applied: bytes_after=42"}],
            },
        }
    )
    assert supervisor.activity.final_assistant_text == ""


def test_usage_is_still_absorbed_from_a_non_assistant_message_end():
    """FU-D narrows TEXT extraction only; usage absorption is unrelated and unchanged."""
    supervisor = _supervisor()
    supervisor._absorb(
        {
            "type": "turn_end",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "prompt"}],
                "usage": {"input": 10, "output": 0, "totalTokens": 10},
            },
        }
    )
    assert supervisor.activity.final_assistant_text == ""
    assert supervisor.activity.last_usage == {"input": 10, "output": 0, "totalTokens": 10}

"""Integration tests for pipeline_gate hook — TC-GATE-01 through TC-GATE-08.

Uses monkeypatching to replace API calls with mocks so no real server is needed.
"""
import importlib
import io
import json
import sys
from unittest.mock import MagicMock, patch

import pytest


def _load_gate():
    """Re-import pipeline_gate fresh (clears module-level state)."""
    import aiteam.hooks.pipeline_gate as gate
    return gate


# Helper: run gate.main() with a fake stdin payload, capture exit code and stderr
def _run_gate(payload: dict, monkeypatch, *, mock_project_id=None, mock_task=None,
              mock_pipeline=None, api_reachable=True):
    """Run pipeline_gate.main() with mocked internals; return (exit_code, stderr_text)."""
    gate = _load_gate()

    raw = json.dumps(payload).encode("utf-8")
    monkeypatch.setattr("sys.stdin", type("FakeBuf", (), {"buffer": io.BytesIO(raw)})())

    stderr_buf = io.StringIO()
    monkeypatch.setattr("sys.stderr", stderr_buf)

    def fake_resolve_project(cwd):
        if not api_reachable:
            return None
        return mock_project_id

    def fake_find_autopilot(project_id):
        if not api_reachable:
            return None
        return mock_task

    def fake_get_pipeline(task_id):
        if not api_reachable:
            return None
        return mock_pipeline

    def fake_create_briefing(**kwargs):
        pass

    monkeypatch.setattr(gate, "_resolve_project_id", fake_resolve_project)
    monkeypatch.setattr(gate, "_find_current_autopilot_task", fake_find_autopilot)
    monkeypatch.setattr(gate, "_get_pipeline_state", fake_get_pipeline)
    monkeypatch.setattr(gate, "_create_briefing", fake_create_briefing)

    exit_code = 0
    try:
        gate.main()
    except SystemExit as e:
        exit_code = e.code if e.code is not None else 0

    return exit_code, stderr_buf.getvalue()


_AUTOPILOT_PLAN_TASK = {"id": "task-001"}
_PLAN_PIPELINE = {
    "autopilot_active": True,
    "current_stage": "research",
    "current_stage_class": "Plan",
}
_EXECUTE_PIPELINE = {
    "autopilot_active": True,
    "current_stage": "implement",
    "current_stage_class": "Execute",
}
_INTERACTIVE_PIPELINE = {
    "autopilot_active": False,
    "current_stage": "implement",
    "current_stage_class": "Execute",
}


class TestInteractiveMode:
    def test_tc_gate_01_autopilot_false_allows_any_tool(self, monkeypatch):
        code, _ = _run_gate(
            {"tool_name": "Edit", "cwd": "/some/project"},
            monkeypatch,
            mock_project_id="proj-1",
            mock_task=_AUTOPILOT_PLAN_TASK,
            mock_pipeline=_INTERACTIVE_PIPELINE,
        )
        assert code == 0

    def test_tc_gate_01_autopilot_false_allows_dangerous_tool(self, monkeypatch):
        code, _ = _run_gate(
            {"tool_name": "team_delete", "cwd": "/some/project"},
            monkeypatch,
            mock_project_id="proj-1",
            mock_task=_AUTOPILOT_PLAN_TASK,
            mock_pipeline=_INTERACTIVE_PIPELINE,
        )
        assert code == 0


class TestNoTask:
    def test_tc_gate_02_no_autopilot_task_allows_any_tool(self, monkeypatch):
        code, _ = _run_gate(
            {"tool_name": "Edit", "cwd": "/some/project"},
            monkeypatch,
            mock_project_id="proj-1",
            mock_task=None,  # no autopilot task found
            mock_pipeline=None,
        )
        assert code == 0

    def test_tc_gate_02_no_project_allows_any_tool(self, monkeypatch):
        code, _ = _run_gate(
            {"tool_name": "Edit", "cwd": "/some/project"},
            monkeypatch,
            mock_project_id=None,
            mock_task=None,
            mock_pipeline=None,
        )
        assert code == 0


class TestApiUnreachable:
    def test_tc_gate_03_api_unreachable_allows_any_tool(self, monkeypatch):
        code, _ = _run_gate(
            {"tool_name": "Edit", "cwd": "/some/project"},
            monkeypatch,
            api_reachable=False,
        )
        assert code == 0

    def test_tc_gate_03_api_unreachable_allows_dangerous_tool(self, monkeypatch):
        code, _ = _run_gate(
            {"tool_name": "git_auto_commit", "cwd": "/some/project"},
            monkeypatch,
            api_reachable=False,
        )
        assert code == 0


class TestPlanStageBlocking:
    def test_tc_gate_04_plan_stage_blocks_edit(self, monkeypatch):
        code, stderr = _run_gate(
            {"tool_name": "Edit", "cwd": "/proj"},
            monkeypatch,
            mock_project_id="proj-1",
            mock_task=_AUTOPILOT_PLAN_TASK,
            mock_pipeline=_PLAN_PIPELINE,
        )
        assert code == 2
        assert "research" in stderr or "Plan" in stderr

    def test_tc_gate_04_plan_stage_blocks_write(self, monkeypatch):
        code, _ = _run_gate(
            {"tool_name": "Write", "cwd": "/proj"},
            monkeypatch,
            mock_project_id="proj-1",
            mock_task=_AUTOPILOT_PLAN_TASK,
            mock_pipeline=_PLAN_PIPELINE,
        )
        assert code == 2

    def test_tc_gate_04_plan_stage_stderr_contains_stage_name(self, monkeypatch):
        code, stderr = _run_gate(
            {"tool_name": "Edit", "cwd": "/proj"},
            monkeypatch,
            mock_project_id="proj-1",
            mock_task=_AUTOPILOT_PLAN_TASK,
            mock_pipeline=_PLAN_PIPELINE,
        )
        assert code == 2
        # stderr must mention the current stage to guide the agent
        assert "research" in stderr or "implement" in stderr or "Plan" in stderr or "Execute" in stderr


class TestPlanStageAllowing:
    def test_tc_gate_05_plan_stage_allows_read(self, monkeypatch):
        code, _ = _run_gate(
            {"tool_name": "Read", "cwd": "/proj"},
            monkeypatch,
            mock_project_id="proj-1",
            mock_task=_AUTOPILOT_PLAN_TASK,
            mock_pipeline=_PLAN_PIPELINE,
        )
        assert code == 0

    def test_tc_gate_05_plan_stage_allows_task_memo_add(self, monkeypatch):
        code, _ = _run_gate(
            {"tool_name": "task_memo_add", "cwd": "/proj"},
            monkeypatch,
            mock_project_id="proj-1",
            mock_task=_AUTOPILOT_PLAN_TASK,
            mock_pipeline=_PLAN_PIPELINE,
        )
        assert code == 0

    def test_tc_gate_05_plan_stage_allows_web_search(self, monkeypatch):
        code, _ = _run_gate(
            {"tool_name": "WebSearch", "cwd": "/proj"},
            monkeypatch,
            mock_project_id="proj-1",
            mock_task=_AUTOPILOT_PLAN_TASK,
            mock_pipeline=_PLAN_PIPELINE,
        )
        assert code == 0


class TestExecuteStage:
    def test_tc_gate_06_execute_stage_allows_edit(self, monkeypatch):
        code, _ = _run_gate(
            {"tool_name": "Edit", "cwd": "/proj"},
            monkeypatch,
            mock_project_id="proj-1",
            mock_task=_AUTOPILOT_PLAN_TASK,
            mock_pipeline=_EXECUTE_PIPELINE,
        )
        assert code == 0

    def test_tc_gate_06_execute_stage_allows_bash(self, monkeypatch):
        code, _ = _run_gate(
            {"tool_name": "Bash", "cwd": "/proj"},
            monkeypatch,
            mock_project_id="proj-1",
            mock_task=_AUTOPILOT_PLAN_TASK,
            mock_pipeline=_EXECUTE_PIPELINE,
        )
        assert code == 0

    def test_tc_gate_06_execute_allows_mcp_task_update(self, monkeypatch):
        code, _ = _run_gate(
            {"tool_name": "mcp__ai-team-os__task_update", "cwd": "/proj"},
            monkeypatch,
            mock_project_id="proj-1",
            mock_task=_AUTOPILOT_PLAN_TASK,
            mock_pipeline=_EXECUTE_PIPELINE,
        )
        assert code == 0


class TestRequiresUserAck:
    def test_tc_gate_07_requires_ack_tool_blocked_with_exit2(self, monkeypatch):
        briefing_calls = []

        gate = _load_gate()
        raw = json.dumps({"tool_name": "team_delete", "cwd": "/proj"}).encode()
        monkeypatch.setattr("sys.stdin", type("FB", (), {"buffer": io.BytesIO(raw)})())
        monkeypatch.setattr("sys.stderr", io.StringIO())

        monkeypatch.setattr(gate, "_resolve_project_id", lambda cwd: "proj-1")
        monkeypatch.setattr(gate, "_find_current_autopilot_task", lambda pid: _AUTOPILOT_PLAN_TASK)
        monkeypatch.setattr(gate, "_get_pipeline_state", lambda tid: _PLAN_PIPELINE)
        monkeypatch.setattr(gate, "_create_briefing", lambda **kw: briefing_calls.append(kw))

        with pytest.raises(SystemExit) as exc_info:
            gate.main()

        assert exc_info.value.code == 2
        assert len(briefing_calls) == 1  # briefing was created

    def test_tc_gate_07_git_auto_commit_triggers_briefing(self, monkeypatch):
        briefing_calls = []

        gate = _load_gate()
        raw = json.dumps({"tool_name": "git_auto_commit", "cwd": "/proj"}).encode()
        monkeypatch.setattr("sys.stdin", type("FB", (), {"buffer": io.BytesIO(raw)})())
        monkeypatch.setattr("sys.stderr", io.StringIO())

        monkeypatch.setattr(gate, "_resolve_project_id", lambda cwd: "proj-1")
        monkeypatch.setattr(gate, "_find_current_autopilot_task", lambda pid: _AUTOPILOT_PLAN_TASK)
        monkeypatch.setattr(gate, "_get_pipeline_state", lambda tid: _EXECUTE_PIPELINE)
        monkeypatch.setattr(gate, "_create_briefing", lambda **kw: briefing_calls.append(kw))

        with pytest.raises(SystemExit) as exc_info:
            gate.main()

        assert exc_info.value.code == 2
        assert len(briefing_calls) == 1


class TestMcpPrefixNormalization:
    def test_tc_gate_08_mcp_prefixed_edit_blocked_in_plan(self, monkeypatch):
        code, _ = _run_gate(
            {"tool_name": "mcp__ai-team-os__task_decompose", "cwd": "/proj"},
            monkeypatch,
            mock_project_id="proj-1",
            mock_task=_AUTOPILOT_PLAN_TASK,
            mock_pipeline=_EXECUTE_PIPELINE,
        )
        # task_decompose is Plan-only; should be blocked in Execute
        assert code == 2

    def test_tc_gate_08_mcp_prefixed_read_allowed_in_plan(self, monkeypatch):
        # Read is ALL_EXEMPT so prefix form should also pass
        # Note: CC built-in "Read" won't have the mcp__ prefix, but testing normalization path
        code, _ = _run_gate(
            {"tool_name": "mcp__ai-team-os__task_memo_read", "cwd": "/proj"},
            monkeypatch,
            mock_project_id="proj-1",
            mock_task=_AUTOPILOT_PLAN_TASK,
            mock_pipeline=_PLAN_PIPELINE,
        )
        assert code == 0

    def test_tc_gate_08_mcp_prefix_stripped_for_classification(self, monkeypatch):
        # mcp__ai-team-os__team_delete should be treated as team_delete (requires_user_ack)
        briefing_calls = []

        gate = _load_gate()
        raw = json.dumps({"tool_name": "mcp__ai-team-os__team_delete", "cwd": "/proj"}).encode()
        monkeypatch.setattr("sys.stdin", type("FB", (), {"buffer": io.BytesIO(raw)})())
        monkeypatch.setattr("sys.stderr", io.StringIO())

        monkeypatch.setattr(gate, "_resolve_project_id", lambda cwd: "proj-1")
        monkeypatch.setattr(gate, "_find_current_autopilot_task", lambda pid: _AUTOPILOT_PLAN_TASK)
        monkeypatch.setattr(gate, "_get_pipeline_state", lambda tid: _PLAN_PIPELINE)
        monkeypatch.setattr(gate, "_create_briefing", lambda **kw: briefing_calls.append(kw))

        with pytest.raises(SystemExit) as exc_info:
            gate.main()

        assert exc_info.value.code == 2
        assert len(briefing_calls) == 1

"""Tests for context_tracker hook."""
import json
import sys
import tempfile
from io import StringIO
from pathlib import Path

from aiteam.hooks import context_tracker


def _make_transcript(lines: list[dict]) -> Path:
    """Write jsonl file with given dict lines, return path."""
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8')
    for entry in lines:
        tmp.write(json.dumps(entry) + "\n")
    tmp.close()
    return Path(tmp.name)


def _run_hook(payload: dict) -> tuple[str, int]:
    """Run main() with given stdin payload, capture stdout and exit code."""
    raw = json.dumps(payload)
    old_stdin = sys.stdin
    old_stdout = sys.stdout
    sys.stdin = StringIO(raw)
    sys.stdout = StringIO()
    exit_code = 0
    try:
        context_tracker.main()
        output = sys.stdout.getvalue()
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else 1
        output = sys.stdout.getvalue()
    finally:
        sys.stdin = old_stdin
        sys.stdout = old_stdout
    return output, exit_code


class TestContextTracker:
    def test_warning_at_80_percent(self):
        # 200K context, 160K used -> 80%
        transcript = _make_transcript([
            {"message": {"role": "user", "content": "..."}},
            {"message": {"role": "assistant", "usage": {"input_tokens": 160_000}, "model": "claude-opus-4-6"}},
        ])
        out, _ = _run_hook({"transcript_path": str(transcript)})
        assert "CONTEXT WARNING" in out
        assert "80" in out
        transcript.unlink()

    def test_critical_at_90_percent(self):
        transcript = _make_transcript([
            {"message": {"role": "assistant", "usage": {"input_tokens": 180_000}, "model": "claude-opus-4-6"}},
        ])
        out, _ = _run_hook({"transcript_path": str(transcript)})
        assert "CONTEXT CRITICAL" in out
        transcript.unlink()

    def test_no_warning_below_80(self):
        transcript = _make_transcript([
            {"message": {"role": "assistant", "usage": {"input_tokens": 100_000}, "model": "claude-opus-4-6"}},
        ])
        out, _ = _run_hook({"transcript_path": str(transcript)})
        assert out.strip() == ""
        transcript.unlink()

    def test_includes_cache_tokens(self):
        # 200K context, 50K input + 120K cache_read = 170K total = 85%
        transcript = _make_transcript([
            {"message": {"role": "assistant", "usage": {
                "input_tokens": 50_000,
                "cache_read_input_tokens": 120_000,
            }, "model": "claude-opus-4-6"}},
        ])
        out, _ = _run_hook({"transcript_path": str(transcript)})
        assert "CONTEXT WARNING" in out
        assert "85" in out
        transcript.unlink()

    def test_1m_context_model(self):
        # 1M context, 800K used = 80%
        transcript = _make_transcript([
            {"message": {"role": "assistant", "usage": {"input_tokens": 800_000}, "model": "claude-opus-4-6[1m]"}},
        ])
        out, _ = _run_hook({"transcript_path": str(transcript)})
        assert "CONTEXT WARNING" in out
        transcript.unlink()

    def test_1m_without_suffix_high_tokens(self):
        # 684800 tokens with model='claude-opus-4-6' (no [1m] suffix) -> auto-detect 1M -> 68.5% no warning
        transcript = _make_transcript([
            {"message": {"role": "assistant", "usage": {"input_tokens": 684_800}, "model": "claude-opus-4-6"}},
        ])
        out, _ = _run_hook({"transcript_path": str(transcript)})
        assert out.strip() == ""
        assert "342" not in out
        transcript.unlink()

    def test_200k_critical_not_1m(self):
        # 180K tokens + sonnet model -> should be 200K context -> 90% critical
        transcript = _make_transcript([
            {"message": {"role": "assistant", "usage": {"input_tokens": 180_000}, "model": "claude-sonnet-4-6"}},
        ])
        out, _ = _run_hook({"transcript_path": str(transcript)})
        assert "CONTEXT CRITICAL" in out
        assert "200000" in out
        transcript.unlink()

    def test_250k_tokens_auto_upgrade_to_1m(self):
        # 250K tokens > 200K -> must be 1M -> 25% no warning
        transcript = _make_transcript([
            {"message": {"role": "assistant", "usage": {"input_tokens": 250_000}, "model": "claude-opus-4-6"}},
        ])
        out, _ = _run_hook({"transcript_path": str(transcript)})
        assert out.strip() == ""
        transcript.unlink()

    def test_missing_transcript_path(self):
        out, _ = _run_hook({})
        assert out.strip() == ""

    def test_nonexistent_transcript(self):
        out, _ = _run_hook({"transcript_path": "/nonexistent/path.jsonl"})
        assert out.strip() == ""

    def test_malformed_jsonl_line_skipped(self):
        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8')
        tmp.write("invalid json line\n")
        tmp.write(json.dumps({"message": {"role": "assistant", "usage": {"input_tokens": 170_000}, "model": "claude-opus-4-6"}}) + "\n")
        tmp.close()
        transcript = Path(tmp.name)
        out, _ = _run_hook({"transcript_path": str(transcript)})
        assert "CONTEXT WARNING" in out
        transcript.unlink()

    def test_empty_stdin_silent(self):
        old_stdin = sys.stdin
        sys.stdin = StringIO("")
        try:
            context_tracker.main()  # Should not raise
        finally:
            sys.stdin = old_stdin

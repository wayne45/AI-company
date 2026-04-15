#!/usr/bin/env python3
"""Context Tracker - UserPromptSubmit Hook.

Reads the last assistant message's usage.input_tokens from CC transcript jsonl,
calculates context usage ratio. >=80% triggers warning, >=90% triggers critical.
Data source: Anthropic API exact usage, not estimates.
No intermediate files, no statusline dependency, project isolation built-in
(transcript_path.parent = project directory).

Usage: python -m aiteam.hooks.context_tracker
"""
import json
import sys
from pathlib import Path

DEFAULT_CONTEXT_SIZE = 200_000
LARGE_CONTEXT_SIZE = 1_000_000
_CLAUDE_CONFIG = Path.home() / ".claude.json"


def _claude_config_has_1m_variant(model: str) -> bool:
    """Check ~/.claude.json for a `{model}[1m]` usage/cost entry.

    CC strips the `[1m]` suffix from transcript `model` fields, so the transcript
    alone can't tell us whether a session runs in 1M mode. But ~/.claude.json
    persists per-model usage keyed by the full ID including `[1m]`, so its
    presence is strong evidence the machine uses the 1M variant for this model.
    """
    if not model:
        return False
    try:
        if not _CLAUDE_CONFIG.is_file():
            return False
        marker = f'{model}[1m]'.encode("utf-8")
        with open(_CLAUDE_CONFIG, "rb") as f:
            return marker in f.read()
    except OSError:
        return False


def _compute_used_pct(total_tokens: int, model: str) -> tuple[float, int]:
    """Compute used percentage and detect context window size.

    Strategy:
    1. If model string explicitly mentions 1m -> use 1M
    2. If ~/.claude.json records a `{model}[1m]` usage entry -> use 1M
       (transcript strips the suffix; config file preserves it)
    3. If total_tokens > 200K -> must be 1M (can't fit in 200K window)
    4. Otherwise default to 200K
    """
    ctx_size = DEFAULT_CONTEXT_SIZE
    if model:
        ml = model.lower()
        if "1m" in ml or "1000000" in ml:
            ctx_size = LARGE_CONTEXT_SIZE
    if ctx_size == DEFAULT_CONTEXT_SIZE and _claude_config_has_1m_variant(model):
        ctx_size = LARGE_CONTEXT_SIZE
    if total_tokens > DEFAULT_CONTEXT_SIZE:
        ctx_size = LARGE_CONTEXT_SIZE
    pct = round((total_tokens / ctx_size) * 100, 1)
    return pct, ctx_size


def _read_last_usage(transcript: Path) -> tuple[int, str] | None:
    """Scan transcript jsonl in reverse for the last assistant message usage.

    Returns (total_tokens, model_name) or None.
    total_tokens = input_tokens + cache_read + cache_creation (all count as context usage)
    """
    try:
        lines = transcript.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        m = entry.get("message") or entry
        if m.get("role") != "assistant":
            continue
        usage = m.get("usage") or {}
        input_tokens = usage.get("input_tokens")
        if input_tokens is None:
            continue
        total = (
            int(input_tokens)
            + int(usage.get("cache_read_input_tokens", 0))
            + int(usage.get("cache_creation_input_tokens", 0))
        )
        model = m.get("model", "") or entry.get("model", "")
        return total, model

    return None


def main():
    # Windows UTF-8 fix
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        payload = json.loads(raw)
    except Exception:
        return  # silent failure

    transcript_path_str = payload.get("transcript_path", "")
    if not transcript_path_str:
        return
    transcript = Path(transcript_path_str)
    if not transcript.exists():
        return

    result = _read_last_usage(transcript)
    if result is None:
        return
    used_tokens, model = result

    pct, ctx_size = _compute_used_pct(used_tokens, model)

    if pct >= 90:
        print(
            f"[CONTEXT CRITICAL] 上下文使用率: {pct}% ({used_tokens}/{ctx_size}). "
            "立即停止当前工作，保存所有记忆和进度到 memory 文件，"
            "然后提醒用户执行 /compact。不要开始任何新任务。"
        )
    elif pct >= 80:
        print(
            f"[CONTEXT WARNING] 上下文使用率: {pct}% ({used_tokens}/{ctx_size}). "
            "请尽快完成当前节点任务，然后保存记忆和进度到 memory 文件，"
            "并提醒用户执行 /compact。"
        )


if __name__ == "__main__":
    main()

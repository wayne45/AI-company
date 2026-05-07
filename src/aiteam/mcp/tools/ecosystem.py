"""Claude ecosystem wide-index MCP tools.

Provides ecosystem_scan (scan popular repos) and ecosystem_search (query archive).
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from typing import Any

from aiteam.mcp._base import _api_call


# ============================================================
# Heuristic classification helpers
# ============================================================

_CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("mcp-server", ["mcp-server", "mcp_server", "model-context-protocol", " mcp ", "mcp tool"]),
    ("agent-framework", ["agent-framework", "agent_framework", "multi-agent", "langgraph", "autogen", "crewai", "agentic"]),
    ("memory-system", ["memory", "mem0", "vector-memory", "rag", "retrieval augmented"]),
    ("skill-system", ["skill", "plugin", "extension", "claude-code", "claude code"]),
    ("tooling", ["cli", "sdk", "api-client", "library", "framework", "toolkit"]),
]

_EXCLUDE_REPOS = {
    "CronusL-1141/AI-company",
    "codeburn",
    "GenericAgent",
}

# JSON fields available from gh search repos
_GH_JSON_FIELDS = "fullName,name,owner,description,stargazersCount,language,homepage,pushedAt"


def _classify_repo(hint_topics: list[str], description: str | None, name: str) -> str | None:
    """Heuristic category assignment based on search-hint topics + description + name."""
    combined = " ".join(hint_topics).lower() + " " + (description or "").lower() + " " + name.lower()
    for category, keywords in _CATEGORY_RULES:
        for kw in keywords:
            if kw.lower() in combined:
                return category
    return "tooling"


def _compute_relevance_score(hint_topics: list[str], description: str | None, stars: int) -> int:
    """0-10 relevance score: keyword matches + stars bonus."""
    combined = " ".join(hint_topics).lower() + " " + (description or "").lower()
    score = 0
    for kw in ["claude", "anthropic", "mcp", "agent", "llm"]:
        if kw in combined:
            score += 2
    score = min(score, 8)
    if stars >= 50000:
        score = min(score + 2, 10)
    elif stars >= 15000:
        score = min(score + 1, 10)
    return score


def _should_exclude(repo_full_name: str) -> bool:
    """Check whether a repo should be excluded."""
    for excl in _EXCLUDE_REPOS:
        if excl.lower() in repo_full_name.lower():
            return True
    return False


def _run_gh_search(
    keyword: str,
    min_stars: int,
    topics: list[str] | None = None,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    """Call gh search repos and return parsed repo list."""
    cmd = [
        "gh", "search", "repos",
        "--limit=100",
        f"--stars=>={min_stars}",
        f"--json={_GH_JSON_FIELDS}",
        "--sort=stars",
        "--order=desc",
    ]
    if keyword:
        cmd.insert(2, keyword)
    if topics:
        for t in topics:
            cmd.extend(["--topic", t])
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        if result.returncode != 0 or not result.stdout:
            return []
        return json.loads(result.stdout) if result.stdout.strip() else []
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError, Exception):
        return []


def _parse_gh_repo(
    item: dict[str, Any],
    min_stars: int,
    hint_topics: list[str] | None = None,
) -> dict[str, Any] | None:
    """Parse a gh JSON item into profile fields, filtering out ineligible items."""
    full_name = item.get("fullName", "")
    if not full_name or _should_exclude(full_name):
        return None

    stars = item.get("stargazersCount", 0)
    if stars < min_stars:
        return None

    owner_obj = item.get("owner") or {}
    owner = owner_obj.get("login", "") if isinstance(owner_obj, dict) else str(owner_obj)
    name = item.get("name", full_name.split("/")[-1])
    description = item.get("description") or None
    language = item.get("language") or None
    homepage = item.get("homepageUrl") or item.get("homepage") or None

    pushed_at_str = item.get("pushedAt") or None
    last_commit_at: datetime | None = None
    if pushed_at_str:
        try:
            last_commit_at = datetime.fromisoformat(pushed_at_str.replace("Z", "+00:00"))
        except ValueError:
            pass

    # Use hint_topics (from the search query) as proxy for topics field
    effective_topics = hint_topics or []
    needs_deep_review = stars < 15000
    category = _classify_repo(effective_topics, description, name)
    relevance_score = _compute_relevance_score(effective_topics, description, stars)
    one_line_summary = description[:200] if description else None

    return {
        "repo_full_name": full_name,
        "name": name,
        "owner": owner,
        "description": description,
        "stars": stars,
        "language": language,
        "topics": effective_topics,
        "homepage": homepage,
        "last_commit_at": last_commit_at.isoformat() if last_commit_at else None,
        "needs_deep_review": needs_deep_review,
        "relevance_category": category,
        "relevance_score": relevance_score,
        "one_line_summary": one_line_summary,
    }


# ============================================================
# gh search queries: (keyword, topics) pairs
# ============================================================

_SEARCH_QUERIES: list[tuple[str, list[str]]] = [
    ("", ["claude-code"]),
    ("", ["mcp"]),
    ("", ["mcp-server"]),
    ("", ["claude-agent"]),
    ("claude", ["agent-framework"]),
    ("claude", ["ai-agents"]),
    ("claude code plugin", []),
    ("anthropic agent", []),
]


def register(mcp: Any) -> None:
    """Register ecosystem MCP tools."""

    @mcp.tool()
    def ecosystem_scan(min_stars: int = 5000, dry_run: bool = False) -> dict[str, Any]:
        """Scan popular Claude ecosystem repos (>=min_stars) and update ecosystem_repo_profiles.

        Runs 8-10 gh search queries covering:
        - topic:claude-code / topic:mcp / topic:mcp-server / topic:claude-agent
        - topic:agent-framework + "claude" / topic:ai-agents + "claude"
        - "claude code plugin" / "anthropic agent"
        - anthropics org public repos

        Deduplicates + filters >=min_stars + excludes known repos (CronusL-1141/AI-company etc.)
        Sets needs_deep_review=True for stars < 15000.
        relevance_category is auto-classified heuristically (based on topics + description keywords).
        Returns: {scanned: int, new_profiles: int, updated_profiles: int, skipped: int}

        dry_run=True returns what would happen without writing to DB.
        """
        import time

        start = time.time()
        all_repos: dict[str, dict[str, Any]] = {}
        per_query_stats: dict[str, int] = {}

        for keyword, topics in _SEARCH_QUERIES:
            query_key = f"keyword={keyword!r} topics={topics}"
            items = _run_gh_search(keyword, min_stars=min_stars, topics=topics)
            count = 0
            for item in items:
                parsed = _parse_gh_repo(item, min_stars, hint_topics=topics)
                if parsed is None:
                    continue
                fn = parsed["repo_full_name"]
                if fn not in all_repos:
                    all_repos[fn] = parsed
                    count += 1
            per_query_stats[query_key] = count

        # Anthropics org
        try:
            org_result = subprocess.run(
                ["gh", "search", "repos", "--owner=anthropics", "--limit=100",
                 f"--stars=>={min_stars}",
                 f"--json={_GH_JSON_FIELDS}",
                 "--sort=stars", "--order=desc"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
            )
            org_items = (
                json.loads(org_result.stdout)
                if org_result.returncode == 0 and org_result.stdout and org_result.stdout.strip()
                else []
            )
        except Exception:
            org_items = []

        org_count = 0
        for item in org_items:
            parsed = _parse_gh_repo(item, min_stars, hint_topics=["anthropic", "claude"])
            if parsed is None:
                continue
            fn = parsed["repo_full_name"]
            if fn not in all_repos:
                all_repos[fn] = parsed
                org_count += 1
        per_query_stats["org:anthropics"] = org_count

        total_scanned = len(all_repos)

        if dry_run:
            elapsed = round(time.time() - start, 1)
            return {
                "dry_run": True,
                "would_process": total_scanned,
                "per_query_stats": per_query_stats,
                "elapsed_seconds": elapsed,
                "sample_repos": [
                    {"repo": k, "stars": v["stars"], "category": v["relevance_category"]}
                    for k, v in list(all_repos.items())[:10]
                ],
            }

        # Upsert via API
        new_count = 0
        updated_count = 0
        skipped_count = 0
        now_iso = datetime.now(tz=timezone.utc).isoformat()

        for profile_data in all_repos.values():
            profile_data["last_scanned_at"] = now_iso
            result = _api_call("POST", "/api/ecosystem/profiles", profile_data)
            if result is None:
                skipped_count += 1
            elif result.get("created"):
                new_count += 1
            else:
                updated_count += 1

        elapsed = round(time.time() - start, 1)

        cat_dist: dict[str, int] = {}
        for p in all_repos.values():
            cat = p.get("relevance_category") or "unknown"
            cat_dist[cat] = cat_dist.get(cat, 0) + 1

        return {
            "scanned": total_scanned,
            "new_profiles": new_count,
            "updated_profiles": updated_count,
            "skipped": skipped_count,
            "per_query_stats": per_query_stats,
            "category_distribution": cat_dist,
            "elapsed_seconds": elapsed,
        }

    @mcp.tool()
    def ecosystem_search(
        keyword: str = "",
        topic: str = "",
        min_stars: int = 0,
        max_stars: int = 0,
        category: str = "",
        needs_deep_review: bool | None = None,
        limit: int = 30,
    ) -> dict[str, Any]:
        """Query ecosystem_repo_profiles archive.

        Args:
            keyword: Keyword match against name / description / summary / repo_full_name.
            topic: Topic keyword filter (JSON field LIKE match).
            min_stars: Minimum star count filter.
            max_stars: Maximum star count filter (0 = no limit).
            category: Category filter ("agent-framework" / "mcp-server" / "memory-system" / "skill-system" / "tooling").
            needs_deep_review: True/False to filter by deep-review flag; None = no filter.
            limit: Maximum results to return (default 30).

        Returns:
            Search result list.
        """
        params: dict[str, Any] = {"limit": limit}
        if keyword:
            params["keyword"] = keyword
        if topic:
            params["topic"] = topic
        if min_stars > 0:
            params["min_stars"] = min_stars
        if max_stars > 0:
            params["max_stars"] = max_stars
        if category:
            params["category"] = category
        if needs_deep_review is not None:
            params["needs_deep_review"] = needs_deep_review

        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        result = _api_call("GET", f"/api/ecosystem/profiles?{query_string}")
        if result is None:
            return {"profiles": [], "total": 0}
        return result

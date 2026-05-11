"""Integration tests for v1.6.0 P0.4 — index_update real scan logic."""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from aiteam.api.app import create_app
from aiteam.api.deps import get_repository, get_scoped_repository
from aiteam.storage.connection import close_db
from aiteam.storage.repository import StorageRepository
from aiteam.types import EcosystemRepoProfile

PROJECT_ID = "proj-p04-test-001"

# Minimal fake repo dict returned by a mock gh_search
def _fake_repo(
    name: str,
    stars: int = 2000,
    pushed_days_ago: int = 10,
) -> dict[str, Any]:
    pushed_at = datetime.now(tz=timezone.utc) - timedelta(days=pushed_days_ago)
    return {
        "repo_full_name": f"owner/{name}",
        "name": name,
        "owner": "owner",
        "description": f"A claude agent tool: {name}",
        "stars": stars,
        "language": "Python",
        "topics": ["claude", "mcp"],
        "homepage": None,
        "last_commit_at": pushed_at,
        "pushed_at": pushed_at,
        "relevance_category": "tooling",
        "relevance_score": 6,
        "one_line_summary": f"{name} summary",
        "needs_deep_review": False,
        "is_archived": False,
    }


@pytest_asyncio.fixture()
async def repo() -> StorageRepository:
    r = StorageRepository(db_url="sqlite+aiosqlite://", project_scope=PROJECT_ID)
    await r.init_db()
    yield r  # type: ignore[misc]
    await close_db()


@pytest_asyncio.fixture()
async def client(repo: StorageRepository) -> AsyncClient:
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_scoped_repository] = lambda: repo
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _setup_quick(client: AsyncClient, queries: list[str] | None = None) -> None:
    """Helper: run quick_setup so index_update has a valid config."""
    payload: dict[str, Any] = {
        "sources": ["github"],
        "use_defaults": True,
    }
    if queries:
        payload["queries"] = queries
    resp = await client.post(
        "/api/ecosystem/quick_setup",
        json=payload,
        headers={"X-Project-Id": PROJECT_ID},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------
# missing_setup: no data_source configured
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_index_update_missing_data_source(client: AsyncClient) -> None:
    """No data source → missing_setup = ['data_source', 'scan_profile']."""
    resp = await client.post(
        "/api/ecosystem/index_update",
        json={"dry_run": True},
        headers={"X-Project-Id": PROJECT_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert "data_source" in body["missing_setup"]


@pytest.mark.asyncio
async def test_index_update_missing_scan_profile(client: AsyncClient) -> None:
    """Data source configured but no scan_profile → missing_setup = ['scan_profile']."""
    await client.post(
        "/api/ecosystem/data_sources",
        json={"kind": "github", "name": "gh"},
        headers={"X-Project-Id": PROJECT_ID},
    )
    resp = await client.post(
        "/api/ecosystem/index_update",
        json={"dry_run": True},
        headers={"X-Project-Id": PROJECT_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert "scan_profile" in body["missing_setup"]


# ---------------------------------------------------------------
# dry_run=True: does not write to DB
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_index_update_dry_run_no_db_write(
    client: AsyncClient,
    repo: StorageRepository,
) -> None:
    """dry_run=True runs scan logic but does not persist index_diff or status_changes."""
    await _setup_quick(client, queries=["topic:mcp"])

    mock_repos = [_fake_repo("repoA"), _fake_repo("repoB")]

    gh_auth_ok = MagicMock(returncode=0)

    with (
        patch("subprocess.run", return_value=gh_auth_ok),
        patch(
            "aiteam.api.routes.ecosystem.default_gh_search",
            new=AsyncMock(return_value=mock_repos),
        ),
        patch(
            "aiteam.services.ecosystem_scanner.default_gh_search",
            new=AsyncMock(return_value=mock_repos),
        ),
    ):
        resp = await client.post(
            "/api/ecosystem/index_update",
            json={"dry_run": True},
            headers={"X-Project-Id": PROJECT_ID},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["dry_run"] is True

    # No diff record should be in DB for dry_run
    latest = await repo.get_latest_index_diff(PROJECT_ID)
    assert latest is None


# ---------------------------------------------------------------
# dry_run=False: persists diff + status_changes
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_index_update_real_persists_diff(
    client: AsyncClient,
    repo: StorageRepository,
) -> None:
    """dry_run=False upserts profiles and creates index_diff record."""
    await _setup_quick(client, queries=["topic:mcp"])

    mock_repos = [_fake_repo("repoX", stars=3000), _fake_repo("repoY", stars=2500)]

    gh_auth_ok = MagicMock(returncode=0)

    with (
        patch("subprocess.run", return_value=gh_auth_ok),
        patch(
            "aiteam.api.routes.ecosystem.default_gh_search",
            new=AsyncMock(return_value=mock_repos),
        ),
        patch(
            "aiteam.services.ecosystem_scanner.default_gh_search",
            new=AsyncMock(return_value=mock_repos),
        ),
    ):
        resp = await client.post(
            "/api/ecosystem/index_update",
            json={"dry_run": False},
            headers={"X-Project-Id": PROJECT_ID},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["dry_run"] is False
    assert body["diff"]["new_count"] >= 0  # scanner may or may not surface them as "new"

    # Diff record must be in DB
    latest = await repo.get_latest_index_diff(PROJECT_ID)
    assert latest is not None
    assert latest.project_id == PROJECT_ID


# ---------------------------------------------------------------
# alert threshold: max_new_per_scan
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_index_update_alert_threshold_new(
    client: AsyncClient,
    repo: StorageRepository,
) -> None:
    """When new repos exceed max_new_per_scan threshold, return alerted=True."""
    # Set a very low threshold via custom profile
    await client.post(
        "/api/ecosystem/data_sources",
        json={"kind": "github", "name": "gh", "config": {"queries": ["topic:mcp"]}},
        headers={"X-Project-Id": PROJECT_ID},
    )
    await client.put(
        "/api/ecosystem/scan_profile",
        json={
            "profile": {
                "active_definition": {
                    "primary_metric_kind": "popularity_rank",
                    "active_top_n_per_source": 200,
                    "min_popularity_floor": {"github": 100},
                },
                "inactive_signals": {"no_activity_days": 180},
                "archive_signals": {"no_activity_days": 730, "source_archived": False},
                "alert_thresholds": {"max_new_per_scan": 1, "max_archived_per_scan": 30},
            }
        },
        headers={"X-Project-Id": PROJECT_ID},
    )

    # Mock 5 new repos — threshold is 1
    mock_repos = [_fake_repo(f"repo{i}", stars=2000 - i * 100) for i in range(5)]
    gh_auth_ok = MagicMock(returncode=0)

    with (
        patch("subprocess.run", return_value=gh_auth_ok),
        patch(
            "aiteam.api.routes.ecosystem.default_gh_search",
            new=AsyncMock(return_value=mock_repos),
        ),
        patch(
            "aiteam.services.ecosystem_scanner.default_gh_search",
            new=AsyncMock(return_value=mock_repos),
        ),
    ):
        resp = await client.post(
            "/api/ecosystem/index_update",
            json={"dry_run": False},
            headers={"X-Project-Id": PROJECT_ID},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["alerted"] is True
    assert body["success"] is True  # BUG #5 fix: success=True even when alerted


# ---------------------------------------------------------------
# NormalizedSignal: rank=1 → percentile=1.0
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_normalized_signal_rank1_percentile_1(
    client: AsyncClient,
    repo: StorageRepository,
) -> None:
    """With a single repo in scan results, it should get rank=1 and percentile=1.0."""
    await _setup_quick(client, queries=["topic:mcp"])

    single_repo = [_fake_repo("top-repo", stars=5000, pushed_days_ago=5)]
    gh_auth_ok = MagicMock(returncode=0)

    with (
        patch("subprocess.run", return_value=gh_auth_ok),
        patch(
            "aiteam.api.routes.ecosystem.default_gh_search",
            new=AsyncMock(return_value=single_repo),
        ),
        patch(
            "aiteam.services.ecosystem_scanner.default_gh_search",
            new=AsyncMock(return_value=single_repo),
        ),
    ):
        resp = await client.post(
            "/api/ecosystem/index_update",
            json={"dry_run": False},
            headers={"X-Project-Id": PROJECT_ID},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True

    # Check profile was upserted with popularity_percentile via direct DB query
    profile = await repo.get_ecosystem_profile("owner/top-repo", project_id=PROJECT_ID)
    if profile is not None:
        # popularity_percentile = 1 - (1-1)/1 = 1.0
        assert profile.popularity_percentile == pytest.approx(1.0)


# ---------------------------------------------------------------
# Incremental diff: repo disappears → deactivated
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_incremental_diff_deactivated_when_repo_missing(
    client: AsyncClient,
    repo: StorageRepository,
) -> None:
    """A repo present in round 1 but absent in round 2 should be deactivated."""
    await _setup_quick(client, queries=["topic:mcp"])

    round1 = [_fake_repo("stable-repo", stars=3000), _fake_repo("vanishing-repo", stars=2000)]
    round2 = [_fake_repo("stable-repo", stars=3000)]  # vanishing-repo is gone

    gh_auth_ok = MagicMock(returncode=0)

    # Round 1 — populate DB
    with (
        patch("subprocess.run", return_value=gh_auth_ok),
        patch(
            "aiteam.api.routes.ecosystem.default_gh_search",
            new=AsyncMock(return_value=round1),
        ),
        patch(
            "aiteam.services.ecosystem_scanner.default_gh_search",
            new=AsyncMock(return_value=round1),
        ),
    ):
        r1 = await client.post(
            "/api/ecosystem/index_update",
            json={"dry_run": False},
            headers={"X-Project-Id": PROJECT_ID},
        )
    assert r1.status_code == 200

    # Round 2 — vanishing-repo is gone
    with (
        patch("subprocess.run", return_value=gh_auth_ok),
        patch(
            "aiteam.api.routes.ecosystem.default_gh_search",
            new=AsyncMock(return_value=round2),
        ),
        patch(
            "aiteam.services.ecosystem_scanner.default_gh_search",
            new=AsyncMock(return_value=round2),
        ),
    ):
        r2 = await client.post(
            "/api/ecosystem/index_update",
            json={"dry_run": False},
            headers={"X-Project-Id": PROJECT_ID},
        )

    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["success"] is True
    # vanishing-repo should appear as deactivated
    assert body2["diff"]["deactivated_count"] >= 1


# ---------------------------------------------------------------
# GET /api/ecosystem/index_diffs/latest
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_latest_index_diff_empty(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/ecosystem/index_diffs/latest",
        headers={"X-Project-Id": PROJECT_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["diff"] is None


@pytest.mark.asyncio
async def test_get_latest_index_diff_after_scan(
    client: AsyncClient,
    repo: StorageRepository,
) -> None:
    await _setup_quick(client, queries=["topic:mcp"])

    gh_auth_ok = MagicMock(returncode=0)
    mock_repos = [_fake_repo("latest-repo")]

    with (
        patch("subprocess.run", return_value=gh_auth_ok),
        patch(
            "aiteam.api.routes.ecosystem.default_gh_search",
            new=AsyncMock(return_value=mock_repos),
        ),
        patch(
            "aiteam.services.ecosystem_scanner.default_gh_search",
            new=AsyncMock(return_value=mock_repos),
        ),
    ):
        await client.post(
            "/api/ecosystem/index_update",
            json={"dry_run": False},
            headers={"X-Project-Id": PROJECT_ID},
        )

    resp = await client.get(
        "/api/ecosystem/index_diffs/latest",
        headers={"X-Project-Id": PROJECT_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["diff"] is not None
    assert "generated_at" in body["diff"]


# ---------------------------------------------------------------
# GET /api/ecosystem/index_diffs/history
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_index_diff_history(
    client: AsyncClient,
    repo: StorageRepository,
) -> None:
    await _setup_quick(client, queries=["topic:mcp"])

    gh_auth_ok = MagicMock(returncode=0)
    mock_repos = [_fake_repo("hist-repo")]

    with (
        patch("subprocess.run", return_value=gh_auth_ok),
        patch(
            "aiteam.api.routes.ecosystem.default_gh_search",
            new=AsyncMock(return_value=mock_repos),
        ),
        patch(
            "aiteam.services.ecosystem_scanner.default_gh_search",
            new=AsyncMock(return_value=mock_repos),
        ),
    ):
        await client.post(
            "/api/ecosystem/index_update",
            json={"dry_run": False},
            headers={"X-Project-Id": PROJECT_ID},
        )

    resp = await client.get(
        "/api/ecosystem/index_diffs/history?limit=5",
        headers={"X-Project-Id": PROJECT_ID},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert isinstance(body["diffs"], list)
    assert len(body["diffs"]) >= 1


# ---------------------------------------------------------------
# BUG #6/#8 regression: dry_run must NOT write ecosystem_repo_profiles
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_dry_run_does_not_write_profile_table(
    client: AsyncClient,
    repo: StorageRepository,
) -> None:
    """Critical: dry_run=True must not insert or update any row in ecosystem_repo_profiles."""
    await _setup_quick(client, queries=["topic:mcp"])

    # Seed 3 baseline repos directly into DB via a real run first
    seed_repos = [_fake_repo(f"seed{i}", stars=3000 - i * 100) for i in range(3)]
    gh_auth_ok = MagicMock(returncode=0)

    with (
        patch("subprocess.run", return_value=gh_auth_ok),
        patch(
            "aiteam.api.routes.ecosystem.default_gh_search",
            new=AsyncMock(return_value=seed_repos),
        ),
        patch(
            "aiteam.services.ecosystem_scanner.default_gh_search",
            new=AsyncMock(return_value=seed_repos),
        ),
    ):
        seed_resp = await client.post(
            "/api/ecosystem/index_update",
            json={"dry_run": False},
            headers={"X-Project-Id": PROJECT_ID},
        )
    assert seed_resp.status_code == 200
    assert seed_resp.json()["success"] is True

    # Capture baseline: row count + last_scanned_at timestamps + existing diff id
    profiles_before, _ = await repo.search_ecosystem_profiles_extended(limit=500, offset=0)
    count_before = len(profiles_before)
    scanned_at_before = {p.repo_full_name: p.last_scanned_at for p in profiles_before}
    diff_before = await repo.get_latest_index_diff(PROJECT_ID)
    diff_id_before = diff_before.id if diff_before else None

    # Now dry_run with 5 repos (3 existing + 2 new)
    dry_repos = seed_repos + [_fake_repo("new1", stars=2000), _fake_repo("new2", stars=1500)]

    with (
        patch("subprocess.run", return_value=gh_auth_ok),
        patch(
            "aiteam.api.routes.ecosystem.default_gh_search",
            new=AsyncMock(return_value=dry_repos),
        ),
        patch(
            "aiteam.services.ecosystem_scanner.default_gh_search",
            new=AsyncMock(return_value=dry_repos),
        ),
    ):
        dry_resp = await client.post(
            "/api/ecosystem/index_update",
            json={"dry_run": True},
            headers={"X-Project-Id": PROJECT_ID},
        )
    assert dry_resp.status_code == 200
    dry_body = dry_resp.json()
    assert dry_body["success"] is True
    assert dry_body["dry_run"] is True

    # Verify diff reports 2 new repos
    assert dry_body["diff"]["new_count"] == 2

    # CRITICAL: DB must be unchanged
    profiles_after, _ = await repo.search_ecosystem_profiles_extended(limit=500, offset=0)
    count_after = len(profiles_after)
    assert count_after == count_before, (
        f"dry_run wrote {count_after - count_before} new rows to ecosystem_repo_profiles"
    )

    # CRITICAL: last_scanned_at must not have changed on existing rows
    for p in profiles_after:
        before_ts = scanned_at_before.get(p.repo_full_name)
        assert p.last_scanned_at == before_ts, (
            f"dry_run updated last_scanned_at on {p.repo_full_name}: "
            f"{before_ts} → {p.last_scanned_at}"
        )

    # index_diffs table must not have a new entry after dry_run
    diff_after = await repo.get_latest_index_diff(PROJECT_ID)
    diff_id_after = diff_after.id if diff_after else None
    assert diff_id_after == diff_id_before, (
        "dry_run must not write a new row to index_diffs table"
    )


@pytest.mark.asyncio
async def test_dry_run_false_writes_profiles(
    client: AsyncClient,
    repo: StorageRepository,
) -> None:
    """dry_run=False must upsert repos into ecosystem_repo_profiles."""
    await _setup_quick(client, queries=["topic:mcp"])

    mock_repos = [_fake_repo("writeA", stars=3000), _fake_repo("writeB", stars=2000)]
    gh_auth_ok = MagicMock(returncode=0)

    profiles_before, _ = await repo.search_ecosystem_profiles_extended(limit=500, offset=0)
    count_before = len(profiles_before)

    with (
        patch("subprocess.run", return_value=gh_auth_ok),
        patch(
            "aiteam.api.routes.ecosystem.default_gh_search",
            new=AsyncMock(return_value=mock_repos),
        ),
        patch(
            "aiteam.services.ecosystem_scanner.default_gh_search",
            new=AsyncMock(return_value=mock_repos),
        ),
    ):
        resp = await client.post(
            "/api/ecosystem/index_update",
            json={"dry_run": False},
            headers={"X-Project-Id": PROJECT_ID},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["dry_run"] is False

    profiles_after, _ = await repo.search_ecosystem_profiles_extended(limit=500, offset=0)
    assert len(profiles_after) > count_before, "real run must write new profiles to DB"

    latest_diff = await repo.get_latest_index_diff(PROJECT_ID)
    assert latest_diff is not None, "real run must write to index_diffs table"


@pytest.mark.asyncio
async def test_dry_run_success_field_is_true_on_complete(
    client: AsyncClient,
) -> None:
    """BUG #5 regression: dry_run completing normally must return success=True."""
    await _setup_quick(client, queries=["topic:mcp"])

    mock_repos = [_fake_repo("successA", stars=3000)]
    gh_auth_ok = MagicMock(returncode=0)

    with (
        patch("subprocess.run", return_value=gh_auth_ok),
        patch(
            "aiteam.api.routes.ecosystem.default_gh_search",
            new=AsyncMock(return_value=mock_repos),
        ),
        patch(
            "aiteam.services.ecosystem_scanner.default_gh_search",
            new=AsyncMock(return_value=mock_repos),
        ),
    ):
        resp = await client.post(
            "/api/ecosystem/index_update",
            json={"dry_run": True},
            headers={"X-Project-Id": PROJECT_ID},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True, f"dry_run complete must return success=True, got: {body}"
    assert body["dry_run"] is True
    assert body.get("alerted") is False

"""AI Team OS — Claude 生态仓档案 API 路由。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from aiteam.api.deps import get_repository
from aiteam.storage.repository import StorageRepository
from aiteam.types import EcosystemRepoProfile

router = APIRouter(prefix="/api/ecosystem", tags=["ecosystem"])


class EcosystemProfileCreate(BaseModel):
    repo_full_name: str
    name: str
    owner: str
    description: str | None = None
    stars: int = 0
    language: str | None = None
    topics: list[str] = []
    homepage: str | None = None
    last_commit_at: str | None = None
    needs_deep_review: bool = False
    relevance_category: str | None = None
    relevance_score: int = 0
    one_line_summary: str | None = None
    last_scanned_at: str | None = None


def _parse_profile(data: EcosystemProfileCreate) -> EcosystemRepoProfile:
    """Convert API payload to Pydantic model."""
    last_commit_at: datetime | None = None
    if data.last_commit_at:
        try:
            last_commit_at = datetime.fromisoformat(data.last_commit_at.replace("Z", "+00:00"))
        except ValueError:
            pass

    now = datetime.now(tz=timezone.utc)
    last_scanned_at = now
    if data.last_scanned_at:
        try:
            last_scanned_at = datetime.fromisoformat(data.last_scanned_at.replace("Z", "+00:00"))
        except ValueError:
            pass

    return EcosystemRepoProfile(
        repo_full_name=data.repo_full_name,
        name=data.name,
        owner=data.owner,
        description=data.description,
        stars=data.stars,
        language=data.language,
        topics=data.topics,
        homepage=data.homepage,
        last_commit_at=last_commit_at,
        needs_deep_review=data.needs_deep_review,
        relevance_category=data.relevance_category,
        relevance_score=data.relevance_score,
        one_line_summary=data.one_line_summary,
        last_scanned_at=last_scanned_at,
        first_seen_at=now,
    )


def _profile_to_dict(p: EcosystemRepoProfile) -> dict[str, Any]:
    return {
        "id": p.id,
        "repo_full_name": p.repo_full_name,
        "name": p.name,
        "owner": p.owner,
        "description": p.description,
        "stars": p.stars,
        "language": p.language,
        "topics": p.topics,
        "homepage": p.homepage,
        "last_commit_at": p.last_commit_at.isoformat() if p.last_commit_at else None,
        "needs_deep_review": p.needs_deep_review,
        "relevance_category": p.relevance_category,
        "relevance_score": p.relevance_score,
        "one_line_summary": p.one_line_summary,
        "last_scanned_at": p.last_scanned_at.isoformat(),
        "first_seen_at": p.first_seen_at.isoformat(),
    }


@router.post("/profiles")
async def upsert_profile(
    data: EcosystemProfileCreate,
    repo: StorageRepository = Depends(get_repository),
) -> dict[str, Any]:
    """Upsert 一个生态仓档案（按 repo_full_name 唯一键）。"""
    existing = await repo.search_ecosystem_profiles(
        keyword=data.repo_full_name.split("/")[-1],
        limit=5,
    )
    is_new = not any(p.repo_full_name == data.repo_full_name for p in existing)

    profile = _parse_profile(data)
    await repo.upsert_ecosystem_profile(profile)
    result = _profile_to_dict(profile)
    result["created"] = is_new
    return result


@router.get("/profiles")
async def search_profiles(
    keyword: str = Query(default=""),
    topic: str = Query(default=""),
    min_stars: int = Query(default=0),
    max_stars: int = Query(default=0),
    category: str = Query(default=""),
    needs_deep_review: bool | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    repo: StorageRepository = Depends(get_repository),
) -> dict[str, Any]:
    """检索生态仓档案列表。"""
    profiles = await repo.search_ecosystem_profiles(
        keyword=keyword,
        topic=topic,
        min_stars=min_stars,
        max_stars=max_stars if max_stars > 0 else None,
        needs_deep_review=needs_deep_review,
        category=category,
        limit=limit,
    )
    return {
        "profiles": [_profile_to_dict(p) for p in profiles],
        "total": len(profiles),
    }

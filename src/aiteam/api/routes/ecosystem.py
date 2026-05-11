"""AI Team OS — Claude 生态仓档案 API 路由。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from aiteam.api.deps import get_scoped_repository
from aiteam.services.ecosystem_deep_reviewer import EcosystemDeepReviewer
from aiteam.services.ecosystem_scanner import (
    EcosystemScanner,
    FilterConfig,
    default_gh_search,
)
from aiteam.services.ecosystem_summarizer import (
    TOP_N_SORT_OPTIONS,
    EcosystemSummarizer,
)
from aiteam.services.ecosystem_tagger import EcosystemTagger
from aiteam.storage.repository import StorageRepository
from aiteam.types import (
    EcosystemDeepReview,
    EcosystemRepoProfile,
    EcosystemScanRun,
    EcosystemScanStrategy,
    EcosystemTag,
    EcosystemTagCategory,
)

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
    pushed_at: str | None = None
    is_archived: bool = False
    scan_run_id: str | None = None
    description_excerpt: str = ""


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_profile(data: EcosystemProfileCreate) -> EcosystemRepoProfile:
    """Convert API payload to Pydantic model."""
    last_commit_at = _parse_dt(data.last_commit_at)
    pushed_at = _parse_dt(data.pushed_at)

    now = datetime.now(tz=timezone.utc)
    last_scanned_at = _parse_dt(data.last_scanned_at) or now

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
        pushed_at=pushed_at,
        is_archived=data.is_archived,
        scan_run_id=data.scan_run_id,
        description_excerpt=data.description_excerpt or "",
    )


def _profile_to_dict(
    p: EcosystemRepoProfile,
    stage_status: str | None = None,
    research_count: int = 0,
) -> dict[str, Any]:
    """序列化 profile。

    v1.5.1：透出 stage_status（取自 latest deep_review；无 review 时调用方传 "queued"）。
    research_count = 该 repo 关联的 deep_review 行数（前端用于 RepoCard 研究次数徽章）。
    """
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
        "pushed_at": p.pushed_at.isoformat() if p.pushed_at else None,
        "is_archived": p.is_archived,
        "scan_run_id": p.scan_run_id,
        "description_excerpt": p.description_excerpt,
        # v1.5.0-A 新增字段（前端 stage 徽章 / 失败提示 / 活跃集 tab 依赖）
        "shallow_summary": p.shallow_summary,
        "last_shallow_refreshed_at": (
            p.last_shallow_refreshed_at.isoformat()
            if p.last_shallow_refreshed_at
            else None
        ),
        "is_deleted": p.is_deleted,
        "is_private_now": p.is_private_now,
        "last_fetch_error": p.last_fetch_error,
        "fetch_failure_count": p.fetch_failure_count,
        "is_active": p.is_active,
        "active_rank": p.active_rank,
        # v1.5.1 新增：透出渐进漏斗 stage 状态 + 研究次数（让前端徽章渲染 + 总数统计准确）
        "stage_status": stage_status or "queued",
        "research_count": research_count,
    }


async def _build_stage_map(
    repo: StorageRepository,
    profile_ids: list[str],
) -> tuple[dict[str, str], dict[str, int]]:
    """批量获取每个 profile 的 latest deep_review.stage_status + 研究次数。

    返回 (stage_map, count_map)：
    - stage_map[repo_id] = "queued" / "shallow_done" / ...（latest deep_review，无则 "queued"）
    - count_map[repo_id] = 该 repo 真正被研究过的次数（v1.5.2: 只数 architecture_done+ 的行，
      浅扫完成不计入 — 浅扫是预筛动作，不属于"被研究")

    一次性查询所有 reviews（按 created_at desc），Python 端聚合，避免路由层 N+1。
    """
    # v1.5.2: "已被研究"的语义边界 — 进入 architecture stage 后才算
    _RESEARCHED_STAGES = {"architecture_done", "debated", "referenced", "integrated"}

    stage_map: dict[str, str] = {}
    count_map: dict[str, int] = {}
    if not profile_ids:
        return stage_map, count_map
    id_set = set(profile_ids)
    # list_deep_reviews 不支持 IN 多 id，但限定 limit 后 Python 过滤已足够（当前 < 数千行）
    reviews = await repo.list_deep_reviews(limit=10000)
    for r in reviews:
        if r.repo_id not in id_set:
            continue
        # 只数真正被研究过的行（不含浅扫 shallow_done / queued / *_failed）
        stage_value = (
            r.stage_status.value
            if hasattr(r.stage_status, "value")
            else (r.stage_status or "")
        )
        if stage_value in _RESEARCHED_STAGES:
            count_map[r.repo_id] = count_map.get(r.repo_id, 0) + 1
        if r.repo_id not in stage_map:
            # list_deep_reviews 已按 created_at desc，第一条即 latest
            stage_map[r.repo_id] = stage_value or "queued"
    # 兜底：没 review 的 profile 视作 queued
    for pid in profile_ids:
        stage_map.setdefault(pid, "queued")
        count_map.setdefault(pid, 0)
    return stage_map, count_map


@router.post("/profiles")
async def upsert_profile(
    data: EcosystemProfileCreate,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """Upsert 一个生态仓档案（按 repo_full_name 唯一键）。"""
    existing = await repo.get_ecosystem_profile(data.repo_full_name)
    is_new = existing is None

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
    language: str = Query(default=""),
    pushed_after: str = Query(default=""),
    is_archived: bool | None = Query(default=None),
    needs_deep_review: bool | None = Query(default=None),
    tags: str = Query(default=""),
    tag_match_mode: str = Query(default="all"),
    sort: str = Query(default="stars"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    facet_counts: bool = Query(default=False),
    # v1.5.0-E 前端 tab 切换 / failed 筛选依赖（service 层若不识别会忽略）
    is_active: bool | None = Query(default=None),
    is_deleted: bool | None = Query(default=None),
    stage_status: str = Query(default=""),
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """检索生态仓档案列表（Stage E 扩展版）。

    - tags: 逗号分隔的标签名列表，配合 tag_match_mode (all/any) 实现 AND/OR 过滤
    - sort: stars / recency (pushed_at desc) / relevance (relevance_score desc)
    - facet_counts: True 时附带 category/language/archived 聚合分布
    - is_active / is_deleted / stage_status: v1.5.0-E 前端筛选（活跃/全量 tab、failed 筛选）
    """
    pushed_after_dt = _parse_dt(pushed_after) if pushed_after else None
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    # v1.5.1: stage_status filter 不依赖 stars limit — 先全 DB 算 stage_map 找 wanted_ids
    id_filter: list[str] | None = None
    id_exclude: list[str] | None = None
    if stage_status:
        wanted_stages = {s.strip() for s in stage_status.split(",") if s.strip()}
        if wanted_stages:
            full_reviews = await repo.list_deep_reviews(limit=10000)
            full_stage_map: dict[str, str] = {}
            for r in full_reviews:
                if r.repo_id in full_stage_map:
                    continue  # latest_only（list_deep_reviews 已 created_at desc）
                stg = (
                    r.stage_status.value
                    if hasattr(r.stage_status, "value")
                    else r.stage_status
                ) or "queued"
                full_stage_map[r.repo_id] = stg

            other_wanted = wanted_stages - {"queued"}
            wants_queued = "queued" in wanted_stages

            if wants_queued and not other_wanted:
                # 纯 queued: 排除所有有 review 的仓（无论 stage）
                id_exclude = list(full_stage_map.keys())
            elif other_wanted and not wants_queued:
                # 纯非-queued: 限定到匹配 stages 的仓
                id_filter = [
                    rid for rid, stg in full_stage_map.items() if stg in other_wanted
                ]
            elif wants_queued and other_wanted:
                # queued + 其他: 排除"有 review 但 stage 不匹配"的仓
                id_exclude = [
                    rid for rid, stg in full_stage_map.items() if stg not in other_wanted
                ]

    profiles, total = await repo.search_ecosystem_profiles_extended(
        keyword=keyword,
        topic=topic,
        min_stars=min_stars,
        max_stars=max_stars if max_stars > 0 else None,
        needs_deep_review=needs_deep_review,
        category=category,
        language=language,
        pushed_after=pushed_after_dt,
        is_archived=is_archived,
        tags=tag_list or None,
        tag_match_mode=tag_match_mode,
        sort=sort,
        limit=limit,
        offset=offset,
        id_filter=id_filter,
        id_exclude=id_exclude,
    )

    # v1.5.0-E 客户端二次过滤：is_active / is_deleted
    if is_active is not None:
        profiles = [p for p in profiles if p.is_active == is_active]
    if is_deleted is not None:
        profiles = [p for p in profiles if p.is_deleted == is_deleted]

    # v1.5.1: 一次性批量获取 stage_map + count_map（消除原 N+1 查询）
    stage_map, count_map = await _build_stage_map(repo, [p.id for p in profiles])

    # stage_status 已在 SQL 层用 id_filter / id_exclude 完成；路由层不再后过滤
    if is_active is not None or is_deleted is not None:
        total = len(profiles)

    payload: dict[str, Any] = {
        "profiles": [
            _profile_to_dict(
                p,
                stage_status=stage_map.get(p.id, "queued"),
                research_count=count_map.get(p.id, 0),
            )
            for p in profiles
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }

    if facet_counts:
        facets = await repo.compute_ecosystem_facet_counts(
            keyword=keyword,
            min_stars=min_stars,
            max_stars=max_stars if max_stars > 0 else None,
            category=category,
            language=language,
            is_archived=is_archived,
        )
        payload["facet_counts"] = facets

    return payload


@router.get("/profiles/{repo_full_name:path}/full")
async def get_profile_full(
    repo_full_name: str,
    relations_limit: int = Query(default=50, le=200),
    deep_reviews_limit: int = Query(default=20, le=100),
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """获取仓的全息详情：profile + tags + deep_reviews + relations + scan_run。

    repo_full_name 形如 "owner/repo"。也支持直接传 repo id（id 形式无 "/"）。
    """
    if "/" in repo_full_name:
        result = await repo.get_ecosystem_profile_full(
            repo_full_name=repo_full_name,
            relations_limit=relations_limit,
            deep_reviews_limit=deep_reviews_limit,
        )
    else:
        # 当作主键 id 处理
        result = await repo.get_ecosystem_profile_full(
            repo_id=repo_full_name,
            relations_limit=relations_limit,
            deep_reviews_limit=deep_reviews_limit,
        )

    if result is None:
        raise HTTPException(status_code=404, detail="ecosystem repo not found")

    return _serialize_full(result)


@router.get("/search/by_capability")
async def search_by_capability(
    tags: str = Query(default=""),
    match_mode: str = Query(default="all"),
    min_stars: int = Query(default=0),
    max_stars: int = Query(default=0),
    sort: str = Query(default="stars"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """通过能力标签反向检索仓库。

    tags 逗号分隔。match_mode: all (AND) / any (OR)。
    """
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    if not tag_list:
        return {"profiles": [], "total": 0, "limit": limit, "offset": offset}

    profiles, total = await repo.search_ecosystem_profiles_extended(
        min_stars=min_stars,
        max_stars=max_stars if max_stars > 0 else None,
        tags=tag_list,
        tag_match_mode=match_mode,
        sort=sort,
        limit=limit,
        offset=offset,
    )

    return {
        "profiles": [_profile_to_dict(p) for p in profiles],
        "total": total,
        "limit": limit,
        "offset": offset,
        "matched_tags": tag_list,
        "match_mode": match_mode,
    }


# ============================================================
# Deep review endpoints (Stage F)
# ============================================================


class DeepReviewRequestBody(BaseModel):
    """请求一份新的深扫报告（按 repo_id）。"""

    repo_id: str
    priority: str = "medium"
    timeout_minutes: int = Field(default=45, ge=5, le=180)
    agent_id: str | None = None


class DeepReviewLinkBody(BaseModel):
    """Hook 用的 link 入口：把已存在的 report_id 写到 deep_review。

    K5: hook 解析 5 段式 markdown 后，附带结构化字段一起回填到 row。
    若任一字段为 None，则保留 row 原值（向后兼容旧 hook）。
    """

    report_id: str
    summary_md: str | None = None
    architecture_md: str | None = None
    risks_md: str | None = None
    learnings_md: str | None = None
    integration_md: str | None = None
    demo_result: str | None = None
    demo_log_excerpt: str | None = None
    integration_recommendation: str | None = None


def _deep_review_to_dict(dr: EcosystemDeepReview) -> dict[str, Any]:
    """Serialize a deep-review row for the public API."""
    return {
        "id": dr.id,
        "repo_id": dr.repo_id,
        "status": dr.status.value if hasattr(dr.status, "value") else dr.status,
        "agent_id": dr.agent_id,
        "summary_md": dr.summary_md,
        "architecture_md": dr.architecture_md,
        "demo_result": (
            dr.demo_result.value
            if dr.demo_result is not None and hasattr(dr.demo_result, "value")
            else dr.demo_result
        ),
        "demo_log_excerpt": dr.demo_log_excerpt,
        "risks_md": dr.risks_md,
        "learnings_md": dr.learnings_md,
        "integration_recommendation": (
            dr.integration_recommendation.value
            if dr.integration_recommendation is not None
            and hasattr(dr.integration_recommendation, "value")
            else dr.integration_recommendation
        ),
        "report_id": dr.report_id,
        "dispatch_prompt": getattr(dr, "dispatch_prompt", "") or "",
        "started_at": dr.started_at.isoformat() if dr.started_at else None,
        "completed_at": dr.completed_at.isoformat() if dr.completed_at else None,
        "duration_seconds": dr.duration_seconds,
        "created_at": dr.created_at.isoformat() if dr.created_at else None,
        # v1.5.0-A 新增字段（前端研究历程 timeline 依赖）
        "stage_status": (
            dr.stage_status.value
            if hasattr(dr.stage_status, "value")
            else dr.stage_status
        ),
        "integration_md": getattr(dr, "integration_md", "") or "",
        "shallow_completed_at": (
            dr.shallow_completed_at.isoformat() if dr.shallow_completed_at else None
        ),
        "architecture_completed_at": (
            dr.architecture_completed_at.isoformat()
            if dr.architecture_completed_at
            else None
        ),
        "debated_at": dr.debated_at.isoformat() if dr.debated_at else None,
        "stage3_completed_at": (
            dr.stage3_completed_at.isoformat() if dr.stage3_completed_at else None
        ),
        "debate_meeting_id": dr.debate_meeting_id,
        "integration_task_id": dr.integration_task_id,
    }


def _get_reviewer(repo: StorageRepository) -> EcosystemDeepReviewer:
    """Build an EcosystemDeepReviewer bound to the request's repository."""
    return EcosystemDeepReviewer(repo=repo)


@router.post("/deep_reviews")
async def request_deep_review(
    body: DeepReviewRequestBody,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """入队一份深扫报告，立刻返回 running 行 + 派遣 prompt。"""
    reviewer = _get_reviewer(repo)
    try:
        review = await reviewer.request(
            repo_id=body.repo_id,
            priority=body.priority,
            timeout_minutes=body.timeout_minutes,
            agent_id=body.agent_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _deep_review_to_dict(review)


@router.get("/deep_reviews")
async def list_deep_reviews(
    status: str = Query(default=""),
    limit: int = Query(default=20, le=100),
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """按 status 过滤列出深扫报告（newest-first）。"""
    reviewer = _get_reviewer(repo)
    rows = await reviewer.list_reviews(status=status, limit=limit)
    return {
        "reviews": [_deep_review_to_dict(r) for r in rows],
        "total": len(rows),
    }


@router.get("/deep_reviews/by_repo/{repo_id}")
async def deep_review_status(
    repo_id: str,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """获取指定仓的最新一份深扫报告状态；找不到返回 404。"""
    reviewer = _get_reviewer(repo)
    review = await reviewer.status(repo_id=repo_id)
    if review is None:
        raise HTTPException(status_code=404, detail="no deep review for repo_id")
    return _deep_review_to_dict(review)


@router.post("/deep_reviews/{deep_review_id}/cancel")
async def cancel_deep_review(
    deep_review_id: str,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """取消一份排队 / 进行中的深扫报告。"""
    reviewer = _get_reviewer(repo)
    review = await reviewer.cancel(deep_review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="deep review not found")
    return _deep_review_to_dict(review)


@router.post("/deep_reviews/{deep_review_id}/backfill")
async def backfill_deep_review(
    deep_review_id: str,
    body: DeepReviewLinkBody,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """Backfill 5-section fields on an already-linked deep_review row.

    Same payload as link_report but bypasses the "report_id already set"
    short-circuit. Used by scripts/backfill_deep_review_sections.py to
    populate rows created before the K5 hook parser shipped.
    """
    review = await repo.get_deep_review(deep_review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="deep review not found")

    update_fields: dict[str, Any] = {"report_id": body.report_id}
    if body.summary_md is not None:
        update_fields["summary_md"] = body.summary_md
    if body.architecture_md is not None:
        update_fields["architecture_md"] = body.architecture_md
    if body.risks_md is not None:
        update_fields["risks_md"] = body.risks_md
    if body.learnings_md is not None or body.integration_md is not None:
        learnings = body.learnings_md or ""
        if body.integration_md is not None:
            sep = "\n\n" if learnings else ""
            learnings = (
                f"{learnings}{sep}## 5. 集成建议\n{body.integration_md.strip()}"
            )
        update_fields["learnings_md"] = learnings
    if body.demo_log_excerpt is not None:
        update_fields["demo_log_excerpt"] = body.demo_log_excerpt
    if body.demo_result is not None:
        update_fields["demo_result"] = body.demo_result
    if body.integration_recommendation is not None:
        update_fields["integration_recommendation"] = body.integration_recommendation

    updated = await repo.update_deep_review(deep_review_id, **update_fields)
    if updated is None:
        raise HTTPException(status_code=404, detail="deep review not found")
    return _deep_review_to_dict(updated)


@router.post("/deep_reviews/{deep_review_id}/link_report")
async def link_deep_review_report(
    deep_review_id: str,
    body: DeepReviewLinkBody,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """把 report_id 关联到 deep_review_id，并将状态推进到 completed。

    供 PostToolUse hook 使用。重复调用幂等：若已绑定 report_id 直接返回。
    Hook 同时回填 5 段式解析后的字段（summary_md / architecture_md / ...）。
    """
    reviewer = _get_reviewer(repo)
    review = await reviewer.link_report(
        deep_review_id,
        body.report_id,
        summary_md=body.summary_md,
        architecture_md=body.architecture_md,
        risks_md=body.risks_md,
        learnings_md=body.learnings_md,
        integration_md=body.integration_md,
        demo_result=body.demo_result,
        demo_log_excerpt=body.demo_log_excerpt,
        integration_recommendation=body.integration_recommendation,
    )
    if review is None:
        raise HTTPException(status_code=404, detail="deep review not found")
    return _deep_review_to_dict(review)


def _serialize_full(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert dict containing Pydantic models into JSON-friendly dict."""
    profile = payload["profile"]
    deep_reviews = payload.get("deep_reviews") or []
    scan_run = payload.get("scan_run")

    serialized: dict[str, Any] = {
        "profile": _profile_to_dict(profile),
        "tags": payload.get("tags") or [],
        "deep_reviews": [_deep_review_to_dict(dr) for dr in deep_reviews],
        "relations_from": payload.get("relations_from") or [],
        "relations_to": payload.get("relations_to") or [],
        "scan_run": (
            {
                "id": scan_run.id,
                "strategy": (
                    scan_run.strategy.value
                    if hasattr(scan_run.strategy, "value")
                    else scan_run.strategy
                ),
                "started_at": (
                    scan_run.started_at.isoformat()
                    if getattr(scan_run, "started_at", None)
                    else None
                ),
                "completed_at": (
                    scan_run.completed_at.isoformat()
                    if getattr(scan_run, "completed_at", None)
                    else None
                ),
                "duration_seconds": scan_run.duration_seconds,
                "repos_added": scan_run.repos_added,
                "repos_updated": scan_run.repos_updated,
                "repos_skipped": scan_run.repos_skipped,
                "errors": scan_run.errors,
                "notes": scan_run.notes,
                "triggered_by": scan_run.triggered_by,
                "agent_id": scan_run.agent_id,
            }
            if scan_run is not None
            else None
        ),
    }
    return serialized


# ============================================================
# Stage C: Scan Run endpoints
# ============================================================


def _scan_run_to_dict(run: EcosystemScanRun) -> dict[str, Any]:
    """Serialise an EcosystemScanRun into a JSON-friendly dict."""
    return {
        "id": run.id,
        "strategy": run.strategy.value if hasattr(run.strategy, "value") else run.strategy,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "duration_seconds": run.duration_seconds,
        "repos_added": run.repos_added,
        "repos_updated": run.repos_updated,
        "repos_skipped": run.repos_skipped,
        "errors": run.errors,
        "notes": run.notes,
        "triggered_by": run.triggered_by,
        "agent_id": run.agent_id,
    }


class ScanRunCreate(BaseModel):
    strategy: str = "incremental"
    triggered_by: str = "manual"
    notes: str = ""
    agent_id: str | None = None


class ScanRunComplete(BaseModel):
    duration_seconds: float = 0.0
    repos_added: int = 0
    repos_updated: int = 0
    repos_skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    completed_at: str | None = None
    notes: str | None = None


class ScanRunExecute(BaseModel):
    strategy: str = "incremental"
    min_stars: int = 1000
    triggered_by: str = "manual"
    notes: str = ""
    agent_id: str | None = None


def _coerce_strategy(value: str) -> EcosystemScanStrategy:
    """Map a strategy string to the enum, defaulting to INCREMENTAL on bad input."""
    try:
        return EcosystemScanStrategy(value)
    except ValueError:
        return EcosystemScanStrategy.INCREMENTAL


@router.post("/scan-runs")
async def create_scan_run(
    body: ScanRunCreate,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """Create a new EcosystemScanRun row in OPEN state.

    Used by the legacy ecosystem_scan tool to bracket each invocation.
    """
    run = EcosystemScanRun(
        strategy=_coerce_strategy(body.strategy),
        triggered_by=body.triggered_by or "manual",
        notes=body.notes or "",
        agent_id=body.agent_id,
    )
    await repo.create_scan_run(run)
    return _scan_run_to_dict(run)


@router.get("/scan-runs")
async def list_scan_runs(
    strategy: str = Query(default=""),
    limit: int = Query(default=10, le=100, ge=1),
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """List recent scan runs, ordered by started_at DESC."""
    rows = await repo.list_scan_runs(strategy=strategy, limit=limit)
    return {
        "runs": [_scan_run_to_dict(r) for r in rows],
        "total": len(rows),
    }


@router.get("/scan-runs/{run_id}")
async def get_scan_run(
    run_id: str,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """Get a single scan run by id."""
    row = await repo.get_scan_run(run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="scan run not found")
    return _scan_run_to_dict(row)


@router.post("/scan-runs/{run_id}/complete")
async def complete_scan_run(
    run_id: str,
    body: ScanRunComplete,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """Update a scan run with completion stats."""
    completed_at = _parse_dt(body.completed_at) or datetime.now(tz=timezone.utc)
    fields: dict[str, Any] = {
        "completed_at": completed_at,
        "duration_seconds": body.duration_seconds,
        "repos_added": body.repos_added,
        "repos_updated": body.repos_updated,
        "repos_skipped": body.repos_skipped,
        "errors": body.errors,
    }
    if body.notes is not None:
        fields["notes"] = body.notes
    updated = await repo.update_scan_run(run_id, **fields)
    if updated is None:
        raise HTTPException(status_code=404, detail="scan run not found")
    return _scan_run_to_dict(updated)


@router.post("/scan-runs/execute")
async def execute_scan_run(
    body: ScanRunExecute,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """Trigger a scanner run synchronously and return the resulting summary.

    This drives the EcosystemScanner service end-to-end: open a ScanRun,
    fan out gh queries, apply secondary filters, upsert profiles, close
    the ScanRun. Errors are collected (graceful degradation).
    """
    config = FilterConfig.from_env()
    config.min_stars = body.min_stars or config.min_stars
    scanner = EcosystemScanner(repo=repo, gh_search=default_gh_search, config=config)
    strategy = _coerce_strategy(body.strategy)
    result = await scanner.scan(
        strategy=strategy,
        triggered_by=body.triggered_by or "manual",
        agent_id=body.agent_id,
        notes=body.notes or "",
    )
    return {
        "run_id": result.run_id,
        "strategy": result.strategy,
        "scanned": result.scanned,
        "new_profiles": result.new_profiles,
        "updated_profiles": result.updated_profiles,
        "skipped": result.skipped,
        "archived_marked": result.archived_marked,
        "errors": result.errors,
        "duration_seconds": result.duration_seconds,
        "per_query_stats": result.per_query_stats,
        "category_distribution": result.category_distribution,
    }


# ============================================================
# Stage D — Tag dictionary + tagger endpoints
# ============================================================


def _tag_to_dict(t: EcosystemTag) -> dict[str, Any]:
    return {
        "id": t.id,
        "name": t.name,
        "aliases": t.aliases,
        "category": t.category.value if hasattr(t.category, "value") else t.category,
        "description": t.description,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


class TagApplyBatchRequest(BaseModel):
    repo_ids: list[str] = Field(default_factory=list, description="留空则对全库 profile 打标")
    repo_full_names: list[str] = Field(default_factory=list)
    agent_id: str | None = "ecosystem-tagger"
    limit: int = Field(default=200, ge=1, le=1000)
    replace_auto: bool = Field(
        default=False,
        description=(
            "True 时先删除每仓 source∈{github_topic,auto_rule} 的旧标签再插入新计算结果。"
            "保留 manual/auto_llm 不动。用于规则升级后清理陈旧假阳性。默认 False (追加模式) 保持向后兼容。"
        ),
    )


class TagApplyLLMResultRequest(BaseModel):
    repo_id: str
    tags: list[dict[str, Any]] = Field(
        default_factory=list,
        description='[{"name": str, "confidence": float}, ...]',
    )
    agent_id: str | None = None


class ManualTagRequest(BaseModel):
    repo_id: str
    tag_name: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    agent_id: str | None = None


class LLMDispatchPlanRequest(BaseModel):
    repo_ids: list[str] = Field(default_factory=list)
    team_name: str = "ecosystem-platform"
    agent_template: str = "researcher"
    max_concurrency: int = Field(default=20, ge=1, le=50)


@router.get("/tags")
async def list_tags(
    category: str = Query(default=""),
    limit: int = Query(default=200, le=500),
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """列出全部标签字典；可按 category 过滤。"""
    tags = await repo.list_tags(category=category, limit=limit)
    return {"tags": [_tag_to_dict(t) for t in tags], "total": len(tags)}


@router.post("/tags")
async def upsert_tag(
    payload: dict[str, Any],
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """新增或更新标签（按 name 唯一键）。"""
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    category_raw = (payload.get("category") or "").strip()
    try:
        category = EcosystemTagCategory(category_raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                f"invalid category '{category_raw}'. "
                f"Allowed: {[c.value for c in EcosystemTagCategory]}"
            ),
        ) from exc

    existing = await repo.get_tag_by_name(name)
    is_new = existing is None
    tag = EcosystemTag(
        name=name,
        aliases=payload.get("aliases") or [],
        category=category,
        description=payload.get("description") or "",
    )
    if existing is not None:
        tag.id = existing.id
    await repo.upsert_tag(tag)
    saved = await repo.get_tag_by_name(name)
    if saved is None:
        raise HTTPException(status_code=500, detail="tag not persisted")
    out = _tag_to_dict(saved)
    out["created"] = is_new
    return out


@router.get("/repos/{repo_id}/tags")
async def list_repo_tags(
    repo_id: str,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """列出某仓的所有标签关联，附带 tag 详情。"""
    rows = await repo.list_repo_tags(repo_id=repo_id, limit=200)
    out: list[dict[str, Any]] = []
    for r in rows:
        tag = await repo.get_tag(r.tag_id)
        out.append(
            {
                "repo_tag_id": r.id,
                "repo_id": r.repo_id,
                "tag_id": r.tag_id,
                "tag_name": tag.name if tag else None,
                "tag_category": (
                    tag.category.value
                    if tag and hasattr(tag.category, "value")
                    else None
                ),
                "confidence": r.confidence,
                "source": r.source.value if hasattr(r.source, "value") else r.source,
                "agent_id": r.agent_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )
    return {"repo_id": repo_id, "tags": out, "total": len(out)}


async def _resolve_profiles_for_batch(
    repo: StorageRepository,
    repo_ids: list[str],
    repo_full_names: list[str],
    limit: int,
) -> list[EcosystemRepoProfile]:
    profiles: list[EcosystemRepoProfile] = []
    if repo_ids:
        for rid in repo_ids:
            p = await repo.get_ecosystem_profile_by_id(rid)
            if p is not None:
                profiles.append(p)
    elif repo_full_names:
        for name in repo_full_names:
            p = await repo.get_ecosystem_profile(name)
            if p is not None:
                profiles.append(p)
    else:
        rows, _ = await repo.search_ecosystem_profiles_extended(limit=limit)
        profiles = list(rows)
    return profiles


@router.post("/tags/apply")
async def apply_tags_batch(
    req: TagApplyBatchRequest,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """对一批仓执行 Layer 1+2 自动打标 (GitHub topics + 规则)。

    - 若 repo_ids 与 repo_full_names 均为空，处理全库前 limit 条 profile。
    - 返回每仓命中分布 + 哪些仓需要 Layer 3 LLM 兜底。
    """
    profiles = await _resolve_profiles_for_batch(
        repo, req.repo_ids, req.repo_full_names, req.limit
    )

    repo_dicts = [
        {
            "id": p.id,
            "repo_full_name": p.repo_full_name,
            "name": p.name,
            "owner": p.owner,
            "description": p.description,
            "topics": p.topics,
            "language": p.language,
        }
        for p in profiles
    ]

    tagger = EcosystemTagger(repo)
    stats = await tagger.tag_repos_batch(
        repo_dicts,
        agent_id=req.agent_id,
        replace_auto=req.replace_auto,
    )
    return stats.to_dict()


@router.post("/tags/llm/dispatch_plan")
async def build_llm_dispatch_plan(
    req: LLMDispatchPlanRequest,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """为指定仓集生成 Layer 3 LLM 子 agent 派遣计划。"""
    profiles: list[EcosystemRepoProfile] = []
    for rid in req.repo_ids:
        p = await repo.get_ecosystem_profile_by_id(rid)
        if p is not None:
            profiles.append(p)
    if not profiles:
        return {
            "team_name": req.team_name,
            "agent_template": req.agent_template,
            "max_concurrency": req.max_concurrency,
            "total_requested": 0,
            "dispatched": 0,
            "skipped_due_to_limit": 0,
            "dispatch": [],
            "instructions": "no repos to dispatch",
        }

    repo_dicts = [
        {
            "id": p.id,
            "repo_full_name": p.repo_full_name,
            "description": p.description,
            "topics": p.topics,
            "language": p.language,
        }
        for p in profiles
    ]

    tagger = EcosystemTagger(repo)
    plan = await tagger.build_llm_dispatch_plan(
        repo_dicts,
        team_name=req.team_name,
        agent_template=req.agent_template,
        max_concurrency=req.max_concurrency,
    )
    return plan


@router.post("/tags/llm/result")
async def apply_llm_tag_result(
    req: TagApplyLLMResultRequest,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """sub-agent 提交 Layer 3 LLM 打标结果。"""
    profile = await repo.get_ecosystem_profile_by_id(req.repo_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="repo not found")

    tagger = EcosystemTagger(repo)
    result = await tagger.apply_llm_tags(
        repo_id=req.repo_id,
        repo_full_name=profile.repo_full_name,
        llm_output_tags=req.tags,
        agent_id=req.agent_id,
    )
    return result.to_dict()


@router.post("/tags/manual")
async def manual_tag(
    req: ManualTagRequest,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """手动给某仓打标。"""
    profile = await repo.get_ecosystem_profile_by_id(req.repo_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="repo not found")

    tagger = EcosystemTagger(repo)
    rt = await tagger.manual_tag(
        repo_id=req.repo_id,
        tag_name=req.tag_name,
        confidence=req.confidence,
        agent_id=req.agent_id,
    )
    if rt is None:
        raise HTTPException(
            status_code=404, detail=f"tag '{req.tag_name}' not registered"
        )
    return {
        "repo_id": rt.repo_id,
        "tag_id": rt.tag_id,
        "tag_name": req.tag_name,
        "confidence": rt.confidence,
        "source": rt.source.value if hasattr(rt.source, "value") else rt.source,
    }


@router.delete("/repos/{repo_id}/tags/{tag_name}")
async def remove_tag(
    repo_id: str,
    tag_name: str,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """移除某仓的某标签关联。"""
    tagger = EcosystemTagger(repo)
    removed = await tagger.remove_tag(repo_id, tag_name)
    if not removed:
        raise HTTPException(status_code=404, detail="tag not associated with repo")
    return {"removed": True, "repo_id": repo_id, "tag_name": tag_name}


# ============================================================
# Stage G — summarizer endpoints
# ============================================================


def _get_summarizer(repo: StorageRepository) -> EcosystemSummarizer:
    return EcosystemSummarizer(repo=repo)


@router.get("/summary/weekly")
async def summary_weekly(
    window_days: int = Query(default=7, ge=1, le=90),
    top_movers_limit: int = Query(default=5, ge=1, le=20),
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """生成过去 N 天的生态简报 markdown。

    返回 {markdown: str, window_days, generated_at}。MCP 层负责 report_save。
    """
    summarizer = _get_summarizer(repo)
    md = await summarizer.weekly_summary(
        window_days=window_days,
        top_movers_limit=top_movers_limit,
    )
    return {
        "markdown": md,
        "window_days": window_days,
        "top_movers_limit": top_movers_limit,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }


@router.get("/summary/by_tag")
async def summary_by_tag(
    tag: str = Query(..., min_length=1),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=500),
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """按 tag 列出该方向所有仓 markdown。"""
    summarizer = _get_summarizer(repo)
    md = await summarizer.by_tag_summary(
        tag,
        include_archived=include_archived,
        limit=limit,
    )
    return {
        "markdown": md,
        "tag": tag,
        "include_archived": include_archived,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }


@router.get("/summary/top_n")
async def summary_top_n(
    category: str = Query(default=""),
    n: int = Query(default=10, ge=1, le=100),
    sort: str = Query(default="stars"),
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """Top N 排行 markdown 表格。sort: stars / pushed_at / scan_freshness。"""
    if sort not in TOP_N_SORT_OPTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"sort must be one of {list(TOP_N_SORT_OPTIONS)}",
        )
    summarizer = _get_summarizer(repo)
    md = await summarizer.top_n_summary(category=category, n=n, sort=sort)
    return {
        "markdown": md,
        "category": category,
        "n": n,
        "sort": sort,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }


@router.get("/summary/health")
async def summary_health(
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """平台自检 markdown：仓数 / 扫描 / 深扫 / 标签覆盖 / 失活率。"""
    summarizer = _get_summarizer(repo)
    md = await summarizer.health_summary()
    return {
        "markdown": md,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }


# ============================================================
# v1.5.0-B Stage 0 shallow-scan queue endpoints
# ============================================================


class ApplyShallowSummaryBody(BaseModel):
    """Payload from a Stage 0 ai-engineer sub-agent reporting its summary."""

    repo_id: str
    shallow_summary: str = ""
    deep_review_id: str | None = None
    error_kind: str = ""
    error_message: str = ""
    http_status: int | None = None
    rate_limit_remaining: int | None = None


def _get_shallow_worker(
    repo: StorageRepository,
):
    """Construct an EcosystemShallowQueueWorker bound to repo's project."""
    from aiteam.services.ecosystem_shallow_queue import EcosystemShallowQueueWorker

    return EcosystemShallowQueueWorker(repo=repo)


@router.post("/shallow_queue/apply_summary")
async def apply_shallow_summary(
    body: ApplyShallowSummaryBody,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """Apply a Stage 0 shallow summary or report a failure.

    On success path:
      - update_profile_shallow_summary
      - update_deep_review_stage to SHALLOW_DONE
    On failure path:
      - delegate to worker.report_failure (handles classification, profile
        flag updates, and self-learning bookkeeping).
    """
    from aiteam.services.ecosystem_shallow_queue import EcosystemShallowQueueWorker
    from aiteam.types import EcosystemStageStatus

    worker = EcosystemShallowQueueWorker(repo=repo)

    if body.error_kind:
        decision = await worker.report_failure(
            body.repo_id,
            error_kind=body.error_kind,
            http_status=body.http_status,
            error_message=body.error_message,
            rate_limit_remaining=body.rate_limit_remaining,
            deep_review_id=body.deep_review_id,
        )
        return {
            "success": False,
            "failure_class": decision.failure_class,
            "immediate_retry": decision.immediate_retry,
            "retry_delay_seconds": decision.retry_delay_seconds,
            "marked_deleted": decision.mark_deleted,
            "marked_private": decision.mark_private,
        }

    summary = (body.shallow_summary or "").strip()
    if not summary:
        raise HTTPException(
            status_code=400,
            detail="shallow_summary required when error_kind not set",
        )

    profile = await repo.update_profile_shallow_summary(
        body.repo_id, shallow_summary=summary
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="repo profile not found")

    review = None
    if body.deep_review_id:
        review = await repo.update_deep_review_stage(
            body.deep_review_id,
            EcosystemStageStatus.SHALLOW_DONE,
        )
        # v1.5.2 fix: 浅扫完成 ≠ 整个评审完成。保留 status='running'，
        # 让前端按 stage_status 区分浅/深/辩/集成；同时仍写 completed_at
        # 以便 stage 0 耗时可计算。整体评审完成由 Stage 3 (referenced/integrated) 触发。
        if review is not None:
            await repo.update_deep_review(
                body.deep_review_id,
                completed_at=datetime.now(tz=timezone.utc),
            )

    return {
        "success": True,
        "repo_id": profile.id,
        "shallow_summary_length": len(profile.shallow_summary),
        "stage_status": review.stage_status.value if review else None,
    }


@router.get("/shallow_queue/status")
async def shallow_queue_status(
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """Return Stage 0 queue metrics for the active project."""
    worker = _get_shallow_worker(repo)
    return await worker.queue_status()


@router.post("/shallow_queue/tick")
async def shallow_queue_tick(
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """Run one Stage 0 worker tick on demand (Leader-driven)."""
    worker = _get_shallow_worker(repo)
    result = await worker.tick()
    return {
        "queued": result.queued,
        "dispatched": result.dispatched,
        "skipped_inflight": result.skipped_inflight,
        "errors": result.errors,
        "intents": [
            {
                "repo_id": i.repo_id,
                "repo_full_name": i.repo_full_name,
                "deep_review_id": i.deep_review_id,
                "prompt": i.prompt,
                "timeout_seconds": i.timeout_seconds,
            }
            for i in result.intents
        ],
    }


# ============================================================
# v1.5.0-C — Stage 1 / 2 / 3 lifecycle trigger routes
# ============================================================


class DeepReviewRequestBatchBody(BaseModel):
    """Stage 1 batch request payload (POST /api/ecosystem/lifecycle/request_batch)."""

    tags: list[str] = Field(default_factory=list)
    min_stars: int | None = None
    limit: int = 20
    research_goal: str = ""


class ApplyArchitectureMdBody(BaseModel):
    """Stage 1 writeback payload."""

    deep_review_id: str
    architecture_md: str = ""
    agent_id: str | None = None
    error_message: str = ""  # 非空时进入 architecture_failed 路径


class TriggerDebateBody(BaseModel):
    """Stage 2 debate trigger payload."""

    repo_ids: list[str] = Field(default_factory=list)
    research_goal: str = ""
    suggested_advocate: str = "backend-architect"
    suggested_critic: str = "code-reviewer"
    suggested_judge: str = "team-lead"


class LinkDebateMeetingBody(BaseModel):
    """Stage 2 link meeting payload (called after debate_start)."""

    review_ids: list[str] = Field(default_factory=list)
    meeting_id: str


class ApplyDebateResultBody(BaseModel):
    """Stage 2 result writeback payload."""

    deep_review_id: str
    risks_md: str = ""
    learnings_md: str = ""
    integration_md: str = ""
    integration_recommendation: str = ""
    agent_id: str | None = None


class MarkAsReferenceBody(BaseModel):
    """Stage 3 reference path payload."""

    deep_review_id: str
    agent_id: str | None = None
    confidence: float = 1.0


class StartIntegrationBody(BaseModel):
    """Stage 3 integrate path — request task payload."""

    deep_review_id: str
    title: str = ""
    description: str = ""
    priority: str = "high"
    horizon: str = "mid"
    extra_tags: list[str] = Field(default_factory=list)


class LinkIntegrationTaskBody(BaseModel):
    """Stage 3 link task payload (called after task_create)."""

    deep_review_id: str
    task_id: str


def _get_lifecycle_service(repo: StorageRepository):
    """Construct an EcosystemLifecycleService bound to repo's project scope."""
    from aiteam.services.ecosystem_lifecycle import EcosystemLifecycleService

    return EcosystemLifecycleService(repo)


@router.post("/lifecycle/request_batch")
async def lifecycle_request_batch(
    body: DeepReviewRequestBatchBody,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """Stage 1: queue a batch of deep_review rows for tag-filtered candidates.

    Returns dispatch intents for backend-architect sub-agents. Leader is
    responsible for actually spawning each agent via the Agent tool.
    """
    service = _get_lifecycle_service(repo)
    try:
        intents = await service.request_deep_review_batch(
            tags=body.tags,
            min_stars=body.min_stars,
            limit=body.limit,
            research_goal=body.research_goal,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "success": True,
        "dispatched": len(intents),
        "intents": [
            {
                "repo_id": i.repo_id,
                "repo_full_name": i.repo_full_name,
                "deep_review_id": i.deep_review_id,
                "prompt": i.prompt,
                "timeout_seconds": i.timeout_seconds,
                "project_id": i.project_id,
            }
            for i in intents
        ],
    }


@router.post("/lifecycle/apply_architecture_md")
async def lifecycle_apply_architecture_md(
    body: ApplyArchitectureMdBody,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """Stage 1 writeback: agent submits architecture_md or reports failure."""
    from aiteam.types import EcosystemDeepReviewStatus, EcosystemStageStatus

    service = _get_lifecycle_service(repo)

    # Failure path — empty architecture_md + non-empty error_message
    if not body.architecture_md.strip() and body.error_message:
        review = await repo.get_deep_review(body.deep_review_id)
        if review is None:
            raise HTTPException(status_code=404, detail="deep_review not found")
        await repo.update_deep_review(
            body.deep_review_id,
            status=EcosystemDeepReviewStatus.FAILED,
            risks_md=(review.risks_md or "")
            + f"\n\n[architecture failed] {body.error_message}",
            completed_at=datetime.now(tz=timezone.utc),
        )
        await repo.update_deep_review_stage(
            body.deep_review_id,
            EcosystemStageStatus.ARCHITECTURE_FAILED,
        )
        return {
            "success": False,
            "stage_status": EcosystemStageStatus.ARCHITECTURE_FAILED.value,
            "error": body.error_message,
        }

    try:
        review = await service.apply_architecture_md(
            body.deep_review_id,
            architecture_md=body.architecture_md,
            agent_id=body.agent_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if review is None:
        raise HTTPException(status_code=404, detail="deep_review not found")
    return {
        "success": True,
        "deep_review_id": review.id,
        "stage_status": review.stage_status.value,
        "architecture_md_length": len(review.architecture_md),
    }


@router.post("/lifecycle/trigger_debate")
async def lifecycle_trigger_debate(
    body: TriggerDebateBody,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """Stage 2: build a debate dispatch intent (caller must invoke debate_start)."""
    service = _get_lifecycle_service(repo)
    try:
        intent = await service.trigger_debate(
            repo_ids=body.repo_ids,
            research_goal=body.research_goal,
            suggested_advocate=body.suggested_advocate,
            suggested_critic=body.suggested_critic,
            suggested_judge=body.suggested_judge,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "success": True,
        "review_ids": intent.review_ids,
        "repo_full_names": intent.repo_full_names,
        "research_goal": intent.research_goal,
        "suggested_topic": intent.suggested_topic,
        "suggested_advocate": intent.suggested_advocate,
        "suggested_critic": intent.suggested_critic,
        "suggested_judge": intent.suggested_judge,
        "project_id": intent.project_id,
        "next_action": (
            "调 debate_start(topic=suggested_topic, advocate=..., critic=..., "
            "judge=...) 创建会议，然后再调 /lifecycle/link_debate_meeting "
            "把 meeting.id 写回 review_ids。"
        ),
    }


@router.post("/lifecycle/link_debate_meeting")
async def lifecycle_link_debate_meeting(
    body: LinkDebateMeetingBody,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """Stage 2 helper: link meeting_id to review rows after debate_start."""
    service = _get_lifecycle_service(repo)
    updated = await service.link_debate_meeting(
        review_ids=body.review_ids,
        meeting_id=body.meeting_id,
    )
    return {
        "success": True,
        "linked": updated,
        "meeting_id": body.meeting_id,
    }


@router.post("/lifecycle/apply_debate_result")
async def lifecycle_apply_debate_result(
    body: ApplyDebateResultBody,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """Stage 2 writeback: agent submits debate conclusion → debated."""
    service = _get_lifecycle_service(repo)
    try:
        review = await service.apply_debate_result(
            body.deep_review_id,
            risks_md=body.risks_md,
            learnings_md=body.learnings_md,
            integration_md=body.integration_md,
            integration_recommendation=body.integration_recommendation,
            agent_id=body.agent_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if review is None:
        raise HTTPException(status_code=404, detail="deep_review not found")
    return {
        "success": True,
        "deep_review_id": review.id,
        "stage_status": review.stage_status.value,
        "debated_at": review.debated_at.isoformat() if review.debated_at else None,
    }


@router.post("/lifecycle/mark_as_reference")
async def lifecycle_mark_as_reference(
    body: MarkAsReferenceBody,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """Stage 3 reference: 加 lifecycle:reference tag + 推进 referenced。"""
    service = _get_lifecycle_service(repo)
    review = await service.mark_as_reference(
        body.deep_review_id,
        agent_id=body.agent_id,
        confidence=body.confidence,
    )
    if review is None:
        raise HTTPException(status_code=404, detail="deep_review not found")
    return {
        "success": True,
        "deep_review_id": review.id,
        "stage_status": review.stage_status.value,
        "stage3_completed_at": (
            review.stage3_completed_at.isoformat()
            if review.stage3_completed_at
            else None
        ),
    }


@router.post("/lifecycle/start_integration")
async def lifecycle_start_integration(
    body: StartIntegrationBody,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """Stage 3 integrate: build a task dispatch intent."""
    service = _get_lifecycle_service(repo)
    try:
        intent = await service.start_integration(
            body.deep_review_id,
            title=body.title,
            description=body.description,
            priority=body.priority,
            horizon=body.horizon,
            extra_tags=body.extra_tags,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "success": True,
        "review_id": intent.review_id,
        "repo_id": intent.repo_id,
        "repo_full_name": intent.repo_full_name,
        "task_payload": {
            "title": intent.title,
            "description": intent.description,
            "priority": intent.priority,
            "horizon": intent.horizon,
            "tags": intent.tags,
        },
        "project_id": intent.project_id,
        "next_action": (
            "调 POST /api/projects/{project_id}/tasks 创建任务，然后再调 "
            "/lifecycle/link_integration_task 把 task.id 写回 review。"
        ),
    }


@router.post("/lifecycle/link_integration_task")
async def lifecycle_link_integration_task(
    body: LinkIntegrationTaskBody,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """Stage 3 helper: link task_id to review row after task_create."""
    service = _get_lifecycle_service(repo)
    review = await service.link_integration_task(
        deep_review_id=body.deep_review_id,
        task_id=body.task_id,
    )
    if review is None:
        raise HTTPException(status_code=404, detail="deep_review not found")
    return {
        "success": True,
        "deep_review_id": review.id,
        "integration_task_id": review.integration_task_id,
        "stage_status": review.stage_status.value,
    }


# ============================================================
# Project Settings (v1.5.0-E 决策 12.1: 项目详情页 Ecosystem 设置 tab)
# ============================================================


class ProjectSettingsBody(BaseModel):
    """项目级 ecosystem 配置 (PUT 入参)。"""

    min_stars: int = Field(default=1000, ge=0)
    top_n: int = Field(default=200, ge=1, le=1000)
    refresh_interval_days: int = Field(default=7, ge=1, le=90)
    auto_shallow_on_archive: bool = True
    focus_topics: list[str] = Field(default_factory=list)
    focus_languages: list[str] = Field(default_factory=list)
    shallow_concurrency: int = Field(default=5, ge=1, le=20)
    deep_concurrency: int = Field(default=3, ge=1, le=10)


def _settings_to_dict(s: Any) -> dict[str, Any]:
    """Serialize EcosystemProjectSettings for API."""
    return {
        "project_id": s.project_id,
        "min_stars": s.min_stars,
        "top_n": s.top_n,
        "refresh_interval_days": s.refresh_interval_days,
        "auto_shallow_on_archive": s.auto_shallow_on_archive,
        "focus_topics": s.focus_topics,
        "focus_languages": s.focus_languages,
        "shallow_concurrency": s.shallow_concurrency,
        "deep_concurrency": s.deep_concurrency,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


@router.get("/projects/{project_id}/settings")
async def get_project_settings(
    project_id: str,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """获取项目的 ecosystem 配置（不存在则按默认值创建）。"""
    settings = await repo.ensure_ecosystem_project_settings(project_id)
    return _settings_to_dict(settings)


@router.put("/projects/{project_id}/settings")
async def update_project_settings(
    project_id: str,
    body: ProjectSettingsBody,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """更新项目的 ecosystem 配置。"""
    from aiteam.types import EcosystemProjectSettings as _Settings

    payload = _Settings(
        project_id=project_id,
        min_stars=body.min_stars,
        top_n=body.top_n,
        refresh_interval_days=body.refresh_interval_days,
        auto_shallow_on_archive=body.auto_shallow_on_archive,
        focus_topics=body.focus_topics,
        focus_languages=body.focus_languages,
        shallow_concurrency=body.shallow_concurrency,
        deep_concurrency=body.deep_concurrency,
    )
    saved = await repo.upsert_ecosystem_project_settings(payload)
    return _settings_to_dict(saved)


# ============================================================
# Failed repo retry (v1.5.0-E 决策: 失败仓立即重试按钮)
# ============================================================


class RetryFailedRepoBody(BaseModel):
    """重置仓的失败状态以触发下一轮 Stage 0 浅扫。"""

    reason: str = "manual_retry"


@router.post("/profiles/{repo_id}/retry")
async def retry_failed_repo(
    repo_id: str,
    body: RetryFailedRepoBody,
    repo: StorageRepository = Depends(get_scoped_repository),
) -> dict[str, Any]:
    """重置 fetch_failure_count + last_fetch_error，让仓重新进入浅扫队列。

    用于前端 "立即重试" 按钮。
    """
    profile = await repo.get_ecosystem_profile_by_id(repo_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="ecosystem repo not found")

    # 清失败计数 + 错误消息（不动 is_deleted/is_private_now，由 scanner 重新判定）
    profile.fetch_failure_count = 0
    profile.last_fetch_error = ""
    await repo.upsert_ecosystem_profile(profile)
    return {
        "success": True,
        "repo_id": repo_id,
        "repo_full_name": profile.repo_full_name,
        "reason": body.reason,
        "next_action": "Stage 0 浅扫队列下次 tick 会重新派遣 agent",
    }

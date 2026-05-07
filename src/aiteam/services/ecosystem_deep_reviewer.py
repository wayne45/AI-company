"""Ecosystem deep-review workflow service.

Coordinates the lifecycle of an EcosystemDeepReview row: queue → running →
completed/failed. The actual deep-scan work is performed by an external CC
sub-agent that:

  1. Reads the prompt embedded in the task memo (5-section template).
  2. Performs shallow + deep inspection of the repository.
  3. Calls ``report_save(report_type="deep-review", ...)`` with a body
     containing both ``repo_id=<uuid>`` and ``deep_review_id=<uuid>``
     anchors so a PostToolUse hook can wire ``DeepReview.report_id``.

The service exposes four operations: ``request``, ``status``, ``list_reviews``
and ``cancel``. A lightweight asyncio watchdog enforces the per-review
``timeout_seconds`` so a runaway sub-agent eventually flips status to
``failed`` instead of staying ``running`` forever.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from aiteam.storage.repository import StorageRepository
from aiteam.types import (
    DemoResult,
    EcosystemDeepReview,
    EcosystemDeepReviewStatus,
    IntegrationRecommendation,
)

logger = logging.getLogger(__name__)


# ============================================================
# Embedded sub-agent prompt (5-section template)
# ============================================================

DEEP_REVIEW_AGENT_PROMPT = """\
You are running as a deep-review sub-agent for the ecosystem-platform team.

## Target
- repo_full_name: {repo_full_name}
- repo_id: {repo_id}
- deep_review_id: {deep_review_id}
- timeout_minutes: {timeout_minutes}

## Workflow
1. Shallow scan (<= 5 minutes)
   - git clone --depth=1 https://github.com/{repo_full_name} /tmp/ecosystem-deep/{repo_id}
   - List top-level structure (tree -L 2)
   - Read README + manifest (package.json / Cargo.toml / pyproject.toml / go.mod)
2. Deep scan (<= {timeout_minutes} minutes total)
   - Identify the architectural entry points (src/, lib/, core/)
   - Read the core modules
   - Try the simplest documented quickstart / demo (record stdout tail)
   - Compare README claims with actual behaviour
3. Persist findings via report_save with the structure below.

## Mandatory report structure (5 sections)
The report body MUST start with the two anchor lines so the OS hook can
wire it to the deep-review row:

```
repo_id={repo_id}
deep_review_id={deep_review_id}
```

Then provide the 5 sections defined in
docs/ecosystem-deep-review-template.md.

## Persistence
report_save(
    author="<your-agent-name>",
    topic="deep-review-{repo_full_name_slug}",
    content="<5-section markdown>",
    report_type="deep-review",
)

## Constraints
- Use --depth=1 clones to keep disk usage tiny.
- Do not commit or push anything.
- If you cannot run the demo, set demo_result=skipped with the reason.
"""


# ============================================================
# Service
# ============================================================


class EcosystemDeepReviewer:
    """High-level coordinator for ecosystem deep-review workflows."""

    def __init__(
        self,
        repo: StorageRepository,
        project_id: str = "",
    ) -> None:
        """初始化深扫服务。

        Args:
            repo: 数据访问层。
            project_id: 可选项目作用域；空时透传 repo._project_scope。
                所有深扫报告的写入读取都限定于此项目。
        """
        self._repo = repo
        self._project_id = project_id or repo._project_scope or ""
        # Active watchdog tasks indexed by deep_review_id.
        self._watchdogs: dict[str, asyncio.Task[None]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def request(
        self,
        repo_id: str,
        *,
        priority: str = "medium",
        timeout_minutes: int = 45,
        agent_id: str | None = None,
    ) -> EcosystemDeepReview:
        """Queue a new deep review for ``repo_id``.

        The repo profile must exist; otherwise ``ValueError`` is raised.
        Returns the freshly created review row in ``queued`` status.
        Spawns a background watchdog that will flip status to ``failed``
        if the review is still ``running`` after ``timeout_minutes``.
        """
        profile = await self._repo.get_ecosystem_profile_by_id(
            repo_id, project_id=self._project_id or None
        )
        if profile is None:
            raise ValueError(f"EcosystemRepoProfile id={repo_id!r} not found")

        # Refuse to queue if there is already an in-flight review for this
        # repo — the workflow is intentionally serialized per repo.
        in_flight = await self._repo.list_deep_reviews(
            repo_id=repo_id, project_id=self._project_id or None
        )
        for row in in_flight:
            if row.status in {
                EcosystemDeepReviewStatus.QUEUED,
                EcosystemDeepReviewStatus.RUNNING,
            }:
                raise ValueError(
                    f"deep review already in-flight for repo_id={repo_id} "
                    f"(deep_review_id={row.id}, status={row.status.value})"
                )

        review = EcosystemDeepReview(
            project_id=self._project_id or None,
            repo_id=repo_id,
            status=EcosystemDeepReviewStatus.QUEUED,
            agent_id=agent_id,
        )
        await self._repo.create_deep_review(
            review, project_id=self._project_id or None
        )

        # Mark running immediately and embed the dispatch prompt so the
        # external Leader / sub-agent has everything needed to start.
        prompt = self._build_prompt(
            repo_full_name=profile.repo_full_name,
            repo_id=repo_id,
            deep_review_id=review.id,
            timeout_minutes=timeout_minutes,
        )
        await self._repo.update_deep_review(
            review.id,
            _project_id=self._project_id or None,
            status=EcosystemDeepReviewStatus.RUNNING,
            started_at=datetime.now(tz=timezone.utc),
            dispatch_prompt=prompt,  # K5: stored separately from demo_log_excerpt
        )
        review = (
            await self._repo.get_deep_review(
                review.id, project_id=self._project_id or None
            )
            or review
        )

        # Schedule a watchdog so a stuck review eventually fails closed.
        self._spawn_watchdog(review.id, timeout_minutes * 60)

        logger.info(
            "deep_review queued repo=%s deep_review_id=%s priority=%s",
            profile.repo_full_name,
            review.id,
            priority,
        )
        return review

    async def status(self, repo_id: str) -> EcosystemDeepReview | None:
        """Return the most recent deep review for ``repo_id`` or ``None``."""
        rows = await self._repo.list_deep_reviews(
            repo_id=repo_id, limit=1, project_id=self._project_id or None
        )
        return rows[0] if rows else None

    async def list_reviews(
        self,
        *,
        status: str = "",
        limit: int = 20,
    ) -> list[EcosystemDeepReview]:
        """List reviews, newest-first, optionally filtered by status."""
        return await self._repo.list_deep_reviews(
            status=status, limit=limit, project_id=self._project_id or None
        )

    async def cancel(self, deep_review_id: str) -> EcosystemDeepReview | None:
        """Cancel an in-flight review.

        Marks status as ``failed`` with a cancellation note. The external
        sub-agent must observe the row and shut down on its own — this
        service has no out-of-band kill channel.
        """
        review = await self._repo.get_deep_review(
            deep_review_id, project_id=self._project_id or None
        )
        if review is None:
            return None
        if review.status not in {
            EcosystemDeepReviewStatus.QUEUED,
            EcosystemDeepReviewStatus.RUNNING,
        }:
            return review

        watchdog = self._watchdogs.pop(deep_review_id, None)
        if watchdog is not None and not watchdog.done():
            watchdog.cancel()

        completed_at = datetime.now(tz=timezone.utc)
        duration = self._duration_since(review.started_at, completed_at)
        return await self._repo.update_deep_review(
            deep_review_id,
            _project_id=self._project_id or None,
            status=EcosystemDeepReviewStatus.FAILED,
            completed_at=completed_at,
            duration_seconds=duration,
            risks_md=(review.risks_md or "")
            + "\n\n[cancelled by ecosystem_deep_review_cancel]",
        )

    async def link_report(
        self,
        deep_review_id: str,
        report_id: str,
        *,
        summary_md: str | None = None,
        architecture_md: str | None = None,
        risks_md: str | None = None,
        learnings_md: str | None = None,
        integration_md: str | None = None,
        demo_result: DemoResult | str | None = None,
        demo_log_excerpt: str | None = None,
        integration_recommendation: (
            IntegrationRecommendation | str | None
        ) = None,
    ) -> EcosystemDeepReview | None:
        """Wire a freshly-saved report onto its deep review row.

        Called by the PostToolUse hook (``deep_review_link.py``) after a
        ``report_save`` with ``report_type=deep-review``. The hook also
        parses the 5-section markdown body and passes the structured
        fields here so the row reflects the actual report content.

        Idempotent: if the row already has a ``report_id`` we leave it alone.
        """
        review = await self._repo.get_deep_review(
            deep_review_id, project_id=self._project_id or None
        )
        if review is None:
            return None
        if review.report_id:
            return review
        watchdog = self._watchdogs.pop(deep_review_id, None)
        if watchdog is not None and not watchdog.done():
            watchdog.cancel()
        completed_at = datetime.now(tz=timezone.utc)
        duration = self._duration_since(review.started_at, completed_at)

        update_fields: dict[str, Any] = {
            "_project_id": self._project_id or None,
            "report_id": report_id,
            "status": EcosystemDeepReviewStatus.COMPLETED,
            "completed_at": completed_at,
            "duration_seconds": duration,
        }
        if summary_md is not None:
            update_fields["summary_md"] = summary_md
        if architecture_md is not None:
            update_fields["architecture_md"] = architecture_md
        if risks_md is not None:
            update_fields["risks_md"] = risks_md
        # learnings_md keeps the "我们能借鉴的点" section.
        if learnings_md is not None:
            update_fields["learnings_md"] = learnings_md
        # integration_md (5. 集成建议 markdown body) — stored alongside
        # learnings_md when callers pass it; otherwise concatenated.
        if integration_md is not None:
            existing = update_fields.get("learnings_md") or ""
            sep = "\n\n" if existing else ""
            update_fields["learnings_md"] = (
                f"{existing}{sep}## 5. 集成建议\n{integration_md.strip()}"
            )
        if demo_log_excerpt is not None:
            update_fields["demo_log_excerpt"] = demo_log_excerpt
        if demo_result is not None:
            update_fields["demo_result"] = self._coerce_demo_result(demo_result)
        if integration_recommendation is not None:
            update_fields["integration_recommendation"] = (
                self._coerce_recommendation(integration_recommendation)
            )

        return await self._repo.update_deep_review(deep_review_id, **update_fields)

    @staticmethod
    def _coerce_demo_result(value: DemoResult | str) -> DemoResult | None:
        if isinstance(value, DemoResult):
            return value
        token = (value or "").strip().lower()
        if not token:
            return None
        try:
            return DemoResult(token)
        except ValueError:
            return None

    @staticmethod
    def _coerce_recommendation(
        value: IntegrationRecommendation | str,
    ) -> IntegrationRecommendation | None:
        if isinstance(value, IntegrationRecommendation):
            return value
        token = (value or "").strip().lower()
        if not token:
            return None
        try:
            return IntegrationRecommendation(token)
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_prompt(
        *,
        repo_full_name: str,
        repo_id: str,
        deep_review_id: str,
        timeout_minutes: int,
    ) -> str:
        return DEEP_REVIEW_AGENT_PROMPT.format(
            repo_full_name=repo_full_name,
            repo_full_name_slug=repo_full_name.replace("/", "-"),
            repo_id=repo_id,
            deep_review_id=deep_review_id,
            timeout_minutes=timeout_minutes,
        )

    @staticmethod
    def _duration_since(
        started_at: datetime | None,
        completed_at: datetime,
    ) -> float:
        if started_at is None:
            return 0.0
        # SQLite drops tz info; normalize both sides to naive UTC.
        a = started_at.replace(tzinfo=None) if started_at.tzinfo else started_at
        b = completed_at.replace(tzinfo=None) if completed_at.tzinfo else completed_at
        return max(0.0, (b - a).total_seconds())

    def _spawn_watchdog(self, deep_review_id: str, timeout_seconds: float) -> None:
        """Background task that fails a stuck review after ``timeout_seconds``."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # no loop — skip (e.g. sync test path)
            return

        async def _watchdog() -> None:
            try:
                await asyncio.sleep(timeout_seconds)
            except asyncio.CancelledError:
                return
            review = await self._repo.get_deep_review(
                deep_review_id, project_id=self._project_id or None
            )
            if review is None or review.status != EcosystemDeepReviewStatus.RUNNING:
                return
            completed_at = datetime.now(tz=timezone.utc)
            duration = self._duration_since(review.started_at, completed_at)
            await self._repo.update_deep_review(
                deep_review_id,
                _project_id=self._project_id or None,
                status=EcosystemDeepReviewStatus.FAILED,
                completed_at=completed_at,
                duration_seconds=duration,
                risks_md=(review.risks_md or "")
                + f"\n\n[timeout after {timeout_seconds:.0f}s]",
            )
            logger.warning(
                "deep_review timed out deep_review_id=%s after=%.0fs",
                deep_review_id,
                timeout_seconds,
            )

        task = loop.create_task(_watchdog(), name=f"deep-review-watchdog-{deep_review_id}")
        self._watchdogs[deep_review_id] = task

    # ------------------------------------------------------------------
    # Diagnostics (used by tests / API)
    # ------------------------------------------------------------------

    def to_dict(self, review: EcosystemDeepReview) -> dict[str, Any]:
        """Serialize a review row to a JSON-friendly dict."""
        return {
            "id": review.id,
            "repo_id": review.repo_id,
            "status": review.status.value,
            "agent_id": review.agent_id,
            "summary_md": review.summary_md,
            "architecture_md": review.architecture_md,
            "demo_result": review.demo_result.value if review.demo_result else None,
            "demo_log_excerpt": review.demo_log_excerpt,
            "risks_md": review.risks_md,
            "learnings_md": review.learnings_md,
            "integration_recommendation": (
                review.integration_recommendation.value
                if review.integration_recommendation
                else None
            ),
            "report_id": review.report_id,
            "dispatch_prompt": review.dispatch_prompt,
            "started_at": review.started_at.isoformat() if review.started_at else None,
            "completed_at": review.completed_at.isoformat() if review.completed_at else None,
            "duration_seconds": review.duration_seconds,
            "created_at": review.created_at.isoformat(),
        }

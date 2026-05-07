"""AI Team OS — Async database connection management.

Provides SQLAlchemy async engine and session management with automatic table creation.
Supports per-project database isolation via EnginePool.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
)

from aiteam.storage.engine_pool import engine_pool
from aiteam.storage.models import Base


def _migrate_old_db_if_needed(new_db_path: Path) -> None:
    """Detect old DB and auto-migrate to new path.

    Only copies the database file from the old location when the new DB
    does not exist or is very small (<10KB).
    After migration, the old file is renamed to .db.migrated to avoid repeated migrations.
    All errors are silently handled to not block startup.
    """
    try:
        if new_db_path.exists() and new_db_path.stat().st_size > 10000:
            return  # New DB already has data, skip migration

        old_candidates = [
            Path.cwd() / "aiteam.db",
        ]

        for old_path in old_candidates:
            if old_path.exists() and old_path.stat().st_size > 10000:
                import shutil

                shutil.copy2(str(old_path), str(new_db_path))
                old_path.rename(old_path.with_suffix(".db.migrated"))
                break
    except Exception:
        pass  # Silent handling, do not block startup


def _default_db_url() -> str:
    """Build the default database URL, using fixed path ~/.claude/data/ai-team-os/aiteam.db."""
    data_dir = Path.home() / ".claude" / "data" / "ai-team-os"
    data_dir.mkdir(parents=True, exist_ok=True)
    new_db_path = data_dir / "aiteam.db"
    _migrate_old_db_if_needed(new_db_path)
    return f"sqlite+aiosqlite:///{new_db_path}"


# Default database URL
DEFAULT_DB_URL = _default_db_url()


def get_engine(db_url: str | None = None) -> AsyncEngine:
    """Get or create an async database engine.

    Uses the global EnginePool to support multiple concurrent databases
    (per-project isolation).

    Args:
        db_url: Database connection URL; uses default when empty.

    Returns:
        AsyncEngine instance.
    """
    url = db_url or DEFAULT_DB_URL
    return engine_pool.get_engine(url)


@asynccontextmanager
async def get_session(
    db_url: str | None = None,
) -> AsyncGenerator[AsyncSession, None]:
    """Context manager for obtaining an async database session.

    Uses the EnginePool to route to the correct database.

    Usage:
        async with get_session() as session:
            result = await session.execute(...)

    Args:
        db_url: Optional database URL.

    Yields:
        AsyncSession instance.
    """
    url = db_url or DEFAULT_DB_URL
    factory = engine_pool.get_session_factory(url)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


COLUMNS_TO_ENSURE: list[tuple[str, str, str]] = [
    ("meetings", "meta_json", "JSON DEFAULT NULL"),
    ("meeting_messages", "metadata_json", "JSON DEFAULT NULL"),
    # Stage J: per-project isolation for ecosystem tables (5 data tables;
    # ecosystem_tags dictionary stays global).
    ("ecosystem_repo_profiles", "project_id", "VARCHAR(36)"),
    ("ecosystem_deep_reviews", "project_id", "VARCHAR(36)"),
    ("ecosystem_repo_tags", "project_id", "VARCHAR(36)"),
    ("ecosystem_relations", "project_id", "VARCHAR(36)"),
    ("ecosystem_scan_runs", "project_id", "VARCHAR(36)"),
    # K5: split dispatch prompt out of demo_log_excerpt
    ("ecosystem_deep_reviews", "dispatch_prompt", "TEXT DEFAULT ''"),
]


# K1 perf — composite indexes the SQLAlchemy create_all path emits for new
# DBs. Existing DBs need explicit CREATE INDEX IF NOT EXISTS migration.
# Each entry: (index_name, table, columns_csv).
INDEXES_TO_ENSURE: list[tuple[str, str, str]] = [
    (
        "ix_ecosystem_profiles_project_stars",
        "ecosystem_repo_profiles",
        "project_id, stars",
    ),
    (
        "ix_ecosystem_profiles_project_category_stars",
        "ecosystem_repo_profiles",
        "project_id, relevance_category, stars",
    ),
    (
        "ix_ecosystem_profiles_project_lang_stars",
        "ecosystem_repo_profiles",
        "project_id, language, stars",
    ),
    (
        "ix_ecosystem_profiles_project_pushed",
        "ecosystem_repo_profiles",
        "project_id, pushed_at",
    ),
    (
        "ix_ecosystem_profiles_project_archived_stars",
        "ecosystem_repo_profiles",
        "project_id, is_archived, stars",
    ),
]


def _column_exists(con: object, table: str, column: str) -> bool:
    """Return True if *column* exists in *table* (uses PRAGMA table_info)."""
    import sqlite3

    rows = con.execute(f"PRAGMA table_info({table})")  # type: ignore[union-attr]
    return any(row[1] == column for row in rows)


def _table_exists(con: object, table: str) -> bool:
    """Return True if *table* exists in the SQLite DB."""
    rows = list(
        con.execute(  # type: ignore[union-attr]
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
    )
    return bool(rows)


def _sqlite_migrate(db_path: str) -> None:
    """Idempotent schema migrations for SQLite DBs using stdlib sqlite3.

    SQLAlchemy create_all only creates missing tables, not missing columns.
    Each entry in COLUMNS_TO_ENSURE is checked via PRAGMA table_info and
    ALTER TABLE'd only when absent, making all runs safe to repeat.

    Stage J: also rebuild the legacy column-level UNIQUE on
    ecosystem_repo_profiles.repo_full_name into a (project_id, repo_full_name)
    composite unique index, so the same repo can coexist across projects.
    """
    import sqlite3

    con = sqlite3.connect(db_path)
    try:
        for table, col, ddl in COLUMNS_TO_ENSURE:
            # Skip when the table itself does not exist yet (e.g. create_all
            # hasn't been called when migration runs against an empty DB).
            if not _table_exists(con, table):
                continue
            if not _column_exists(con, table, col):
                con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
                con.commit()

        if _table_exists(con, "ecosystem_repo_profiles"):
            _ensure_ecosystem_profile_project_unique(con)
            _ensure_ecosystem_perf_indexes(con)
    finally:
        con.close()


def _ensure_ecosystem_perf_indexes(con: object) -> None:
    """K1 — ensure composite perf indexes exist on ecosystem_repo_profiles.

    Idempotent: ``CREATE INDEX IF NOT EXISTS`` is a no-op when the index
    already exists. Skips silently when the table is missing (covered by
    caller) or any individual statement fails (defensive).
    """
    import sqlite3

    if not isinstance(con, sqlite3.Connection):
        return  # pragma: no cover

    for idx_name, table, cols in INDEXES_TO_ENSURE:
        try:
            con.execute(
                f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({cols})"
            )
        except sqlite3.OperationalError:
            # e.g. column missing in legacy schema — skip silently
            continue
    con.commit()


def _ensure_ecosystem_profile_project_unique(con: object) -> None:
    """Replace legacy single-column UNIQUE on repo_full_name with composite
    (project_id, repo_full_name) UNIQUE so the same repo can exist in multiple
    projects.

    Idempotent: skips when the legacy unique index is already gone or the
    composite index already exists.
    """
    import sqlite3

    if not isinstance(con, sqlite3.Connection):
        return  # pragma: no cover

    rows = list(
        con.execute(
            "SELECT name, \"unique\" FROM sqlite_master "
            "WHERE type='index' AND tbl_name='ecosystem_repo_profiles'"
        )
    )
    # Detect legacy unique index over repo_full_name only
    legacy_unique_name = None
    composite_present = False
    for row in rows:
        idx_name = row[0]
        if idx_name == "uq_ecosystem_profiles_project_repo":
            composite_present = True
            continue
        # PRAGMA index_list says this index is UNIQUE
        info = list(con.execute("PRAGMA index_list(ecosystem_repo_profiles)"))
        idx_meta = {item[1]: item for item in info}
        meta = idx_meta.get(idx_name)
        if meta is None:
            continue
        if int(meta[2]) != 1:  # not unique
            continue
        cols = list(con.execute(f"PRAGMA index_info({idx_name})"))
        col_names = [c[2] for c in cols]
        if col_names == ["repo_full_name"]:
            legacy_unique_name = idx_name

    if legacy_unique_name and not composite_present:
        # Drop column-level unique (rebuilt as composite below + non-unique
        # index for fast lookup retains).
        try:
            con.execute(f"DROP INDEX {legacy_unique_name}")
            con.execute(
                "CREATE INDEX IF NOT EXISTS ix_ecosystem_repo_profiles_repo_full_name "
                "ON ecosystem_repo_profiles (repo_full_name)"
            )
            con.commit()
        except sqlite3.OperationalError:
            pass

    if not composite_present:
        try:
            con.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_ecosystem_profiles_project_repo "
                "ON ecosystem_repo_profiles (project_id, repo_full_name)"
            )
            con.commit()
        except sqlite3.OperationalError:
            pass


async def init_db(db_url: str | None = None) -> None:
    """Initialize the database and create all tables.

    If using SQLite and the parent directory of the database file does not exist,
    the directory is created automatically.

    Args:
        db_url: Database connection URL.
    """
    url = db_url or DEFAULT_DB_URL

    db_path_str = ""
    # Ensure the directory for the SQLite database file exists
    if "sqlite" in url:
        # Extract file path from URL: sqlite+aiosqlite:///path/to/db
        db_path_str = url.split("///", 1)[-1] if "///" in url else ""
        if db_path_str:
            db_path = Path(db_path_str)
            db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = get_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Run idempotent column migrations (create_all won't add missing columns)
    if db_path_str:
        _sqlite_migrate(db_path_str)


async def close_db() -> None:
    """Close all database connections and release resources."""
    await engine_pool.dispose_all()

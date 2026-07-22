"""SQLAlchemy engine and session primitives."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from radar.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for ORM models introduced in later milestones."""


def _prepare_sqlite_directory(database_url: str) -> None:
    """Create the parent directory for a file-backed SQLite database."""
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or not url.database:
        return
    if url.database == ":memory:":
        return

    Path(url.database).expanduser().parent.mkdir(parents=True, exist_ok=True)


def create_db_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine using an explicit or configured URL."""
    resolved_url = database_url or get_settings().database_url
    _prepare_sqlite_directory(resolved_url)

    connect_args = (
        {"check_same_thread": False}
        if make_url(resolved_url).get_backend_name() == "sqlite"
        else {}
    )
    db_engine = create_engine(resolved_url, connect_args=connect_args)
    if make_url(resolved_url).get_backend_name() == "sqlite":
        event.listen(
            db_engine,
            "connect",
            lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"),
        )
    return db_engine


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_database(db_engine: Engine | None = None) -> None:
    """Create all currently registered tables, then apply pending migrations."""
    from radar import models as _models  # noqa: F401

    active_engine = db_engine or engine
    Base.metadata.create_all(bind=active_engine)
    run_migrations(active_engine)


def _migrate_source_traceability_columns(db_engine: Engine) -> None:
    """Backfill additive source columns for existing local demo databases."""

    inspector = inspect(db_engine)
    if "sources" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("sources")}
    statements = {
        "venue": "ALTER TABLE sources ADD COLUMN venue TEXT",
        "publication_type": (
            "ALTER TABLE sources ADD COLUMN publication_type VARCHAR DEFAULT 'preprint'"
        ),
        "pdf_url": "ALTER TABLE sources ADD COLUMN pdf_url VARCHAR",
    }
    missing = [statement for name, statement in statements.items() if name not in existing]
    if not missing:
        return
    with db_engine.begin() as connection:
        for statement in missing:
            connection.execute(text(statement))


def _migrate_model_run_traceability_columns(db_engine: Engine) -> None:
    """Backfill case/scan traceability columns on legacy model_runs tables."""

    inspector = inspect(db_engine)
    if "model_runs" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("model_runs")}
    statements = {
        "case_id": "ALTER TABLE model_runs ADD COLUMN case_id VARCHAR",
        "scan_run_id": "ALTER TABLE model_runs ADD COLUMN scan_run_id VARCHAR",
    }
    missing = [statement for name, statement in statements.items() if name not in existing]
    with db_engine.begin() as connection:
        for statement in missing:
            connection.execute(text(statement))
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_model_runs_case_id "
                "ON model_runs (case_id)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_model_runs_scan_run_id "
                "ON model_runs (scan_run_id)"
            )
        )


def _migrate_scan_run_updated_at(db_engine: Engine) -> None:
    """Add the ScanRun heartbeat column used by interrupted-scan recovery."""

    inspector = inspect(db_engine)
    if "scan_runs" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("scan_runs")}
    if "updated_at" in existing:
        return
    with db_engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE scan_runs ADD COLUMN updated_at DATETIME")
        )
        connection.execute(
            text(
                "UPDATE scan_runs SET updated_at = created_at "
                "WHERE updated_at IS NULL"
            )
        )


def _migrate_action_item_advice_source(db_engine: Engine) -> None:
    """Track whether an action's text came from the LLM or rule templates."""

    inspector = inspect(db_engine)
    if "action_items" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("action_items")}
    if "advice_source" in existing:
        return
    with db_engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE action_items ADD COLUMN advice_source VARCHAR "
                "DEFAULT 'rule'"
            )
        )


# Each entry is (version, name, idempotent migration callable).
Migration = tuple[int, str, Callable[[Engine], None]]
MIGRATIONS: list[Migration] = [
    (1, "source_traceability_columns", _migrate_source_traceability_columns),
    (2, "model_run_traceability_columns", _migrate_model_run_traceability_columns),
    (3, "scan_run_updated_at", _migrate_scan_run_updated_at),
    (4, "action_item_advice_source", _migrate_action_item_advice_source),
]


def run_migrations(db_engine: Engine) -> list[int]:
    """Apply registered migrations in version order; return newly applied versions."""

    with db_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version INTEGER PRIMARY KEY, applied_at VARCHAR NOT NULL)"
            )
        )
        applied = {
            row[0]
            for row in connection.execute(text("SELECT version FROM schema_migrations"))
        }
    newly_applied: list[int] = []
    for version, _name, migrate in sorted(MIGRATIONS, key=lambda item: item[0]):
        if version in applied:
            continue
        migrate(db_engine)
        with db_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO schema_migrations (version, applied_at) "
                    "VALUES (:version, :applied_at)"
                ),
                {
                    "version": version,
                    "applied_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        newly_applied.append(version)
    return newly_applied


@contextmanager
def session_scope(
    session_factory: sessionmaker[Session] = SessionLocal,
) -> Iterator[Session]:
    """Provide a transactional session with rollback on failure."""
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

"""Schema migration runner, cost estimation, and ModelRun traceability tests."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text

from radar.config import estimate_llm_cost_usd
from radar.db import create_db_engine, init_database, run_migrations
from radar.models import ModelRun, ResearchCase
from radar.schemas import ManuscriptUnderstandingOutput
from radar.services.manuscript_understanding_service import (
    ManuscriptUnderstandingService,
)


def test_init_database_applies_and_records_migrations(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    init_database(engine)

    with engine.connect() as connection:
        versions = {
            row[0]
            for row in connection.execute(
                text("SELECT version FROM schema_migrations")
            )
        }
    assert versions == {1, 2, 3, 4}

    # A second pass applies nothing and does not fail on duplicate records.
    assert run_migrations(engine) == []
    init_database(engine)
    engine.dispose()


def test_legacy_tables_gain_traceability_columns(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE sources (id VARCHAR PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE model_runs (id VARCHAR PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE action_items (id VARCHAR PRIMARY KEY)"))

    init_database(engine)

    inspector = inspect(engine)
    source_columns = {column["name"] for column in inspector.get_columns("sources")}
    run_columns = {column["name"] for column in inspector.get_columns("model_runs")}
    action_columns = {
        column["name"] for column in inspector.get_columns("action_items")
    }
    assert {"venue", "publication_type", "pdf_url"} <= source_columns
    assert {"case_id", "scan_run_id"} <= run_columns
    assert "advice_source" in action_columns
    index_names = {index["name"] for index in inspector.get_indexes("model_runs")}
    assert "ix_model_runs_case_id" in index_names
    assert "ix_model_runs_scan_run_id" in index_names

    # Re-running on the migrated database is a no-op.
    assert run_migrations(engine) == []
    engine.dispose()


def test_estimate_llm_cost_usd_known_and_unknown_models():
    assert estimate_llm_cost_usd("deepseek-chat", 1_000_000, 500_000) == pytest.approx(
        0.82
    )
    assert estimate_llm_cost_usd("DeepSeek-Chat", 1_000_000, 500_000) == pytest.approx(
        0.82
    )
    assert estimate_llm_cost_usd("unknown-model", 1_000, 1_000) == 0.0
    assert estimate_llm_cost_usd(None, 0, 0) == 0.0


def _profile_payload(central_thesis: str) -> dict:
    return ManuscriptUnderstandingOutput(
        title="RadarNet",
        research_problem="Robust retrieval under domain shift",
        central_thesis=central_thesis,
        contributions=[],
        methods=[],
        datasets=[],
        evaluation_protocol=[],
        key_findings=[],
        limitations=[],
        terminology=[],
        watch_topics=[],
        claim_profiles=[],
    ).model_dump()


def _profile_run(case_id: str, central_thesis: str, created_at: datetime) -> ModelRun:
    return ModelRun(
        id=str(uuid4()),
        stage="manuscript_understanding",
        case_id=case_id,
        provider="test",
        model="test-model",
        prompt_hash="hash",
        schema_version="ManuscriptUnderstandingOutput.v1",
        input_refs_json=[],
        raw_response="{}",
        parsed_output_json=_profile_payload(central_thesis),
        validation_json={},
        created_at=created_at,
    )


def test_latest_profile_is_scoped_and_ordered_by_case(db_session_factory):
    now = datetime.now(timezone.utc)
    with db_session_factory() as session:
        session.add(ResearchCase(id="case-a", title="A", research_question="q"))
        session.add(ResearchCase(id="case-b", title="B", research_question="q"))
        session.commit()
    with db_session_factory() as session:
        session.add(_profile_run("case-a", "old thesis", now - timedelta(hours=2)))
        session.add(_profile_run("case-b", "other case thesis", now - timedelta(hours=1)))
        session.add(_profile_run("case-a", "new thesis", now))
        session.commit()

    loaded = ManuscriptUnderstandingService.latest_profile(
        "case-a", db_session_factory
    )
    assert loaded is not None
    assert loaded.central_thesis == "new thesis"

    loaded = ManuscriptUnderstandingService.latest_profile(
        "case-b", db_session_factory
    )
    assert loaded is not None
    assert loaded.central_thesis == "other case thesis"

    assert (
        ManuscriptUnderstandingService.latest_profile("case-c", db_session_factory)
        is None
    )

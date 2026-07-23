"""Shared isolated database and Golden Case fixtures."""

from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

import radar.services.claim_service as claim_service_module
from radar.adapters.crossref import CrossrefIntegrityAdapter
from radar.adapters.unpaywall import UnpaywallAdapter
from radar.db import create_db_engine, init_database
from radar.services.case_service import CaseService


@pytest.fixture(autouse=True)
def crossref_offline_stub(monkeypatch):
    """Keep tests offline: default Crossref lookups to an empty message."""
    monkeypatch.setattr(CrossrefIntegrityAdapter, "_message", lambda self, doi: {})


@pytest.fixture(autouse=True)
def unpaywall_offline_stub(monkeypatch):
    """Keep tests offline: default Unpaywall lookups to a plain miss."""
    monkeypatch.setattr(UnpaywallAdapter, "_fetch_payload", lambda self, doi: {})


@pytest.fixture(autouse=True)
def deterministic_claim_extraction(monkeypatch):
    """Keep claim extraction on the heuristic path unless a test injects an LLM.

    The developer .env configures a real LLM; without this stub, default
    ClaimService instances created inside CaseService would attempt live
    network calls during unrelated tests.
    """
    monkeypatch.setattr(
        claim_service_module, "default_llm_client", lambda settings: None
    )


@pytest.fixture
def db_session_factory(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_database(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture
def golden_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "golden_case"


@pytest.fixture
def golden_case(db_session_factory, golden_dir):
    case_id = CaseService(db_session_factory).load_demo_case(golden_dir)
    return case_id


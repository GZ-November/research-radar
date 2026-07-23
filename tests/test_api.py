"""Smoke tests for the FastAPI application — uses TestClient and a temp DB."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

from radar.api import app
from radar.db import create_db_engine, init_database
from radar.services.case_service import CaseService


# Minimum manuscript content for deterministic parsing — needs ≥200 chars.
_MANUSCRIPT = (
    "# Introduction\n\n"
    "This paper investigates retrieval-augmented generation for open-domain "
    "question answering. We propose a novel framework that combines dense "
    "retrieval with cross-encoder reranking to improve robustness against "
    "query perturbations.\n\n"
    "# Results\n\n"
    "Our method improves exact match by 7.0 points over the BM25 baseline "
    "on the Natural Questions dataset. The reranking component alone "
    "contributes 3.2 points of improvement while adding less than 12 percent "
    "inference latency. We further demonstrate that our approach generalizes "
    "across three diverse evaluation benchmarks including TriviaQA and "
    "HotpotQA, consistently outperforming both sparse and dense retrieval "
    "baselines with statistical significance.\n\n"
    "# Conclusion\n\n"
    "We have shown that retrieval-aware reranking is a practical and "
    "effective strategy for robust open-domain question answering.\n"
)


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    """TestClient wired to a temporary SQLite database."""
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_db_engine(db_url)
    init_database(engine)

    # Force all session-scoped code in api.py to use this test engine.
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    import radar.api as api_module
    import radar.db as db_module

    monkeypatch.setattr(api_module, "SessionLocal", factory)
    monkeypatch.setattr(db_module, "SessionLocal", factory)
    monkeypatch.setattr(db_module, "engine", engine)

    with TestClient(app) as client:
        yield client

    engine.dispose()


def _create_case(api_client, tmp_path, title, question="Does it work?"):
    """Helper: upload a manuscript and return the created case id."""
    md = tmp_path / f"{title}.md"
    md.write_text(_MANUSCRIPT, encoding="utf-8")
    with open(md, "rb") as f:
        resp = api_client.post(
            "/api/cases",
            files={
                "title": (None, title),
                "research_question": (None, question),
                "manuscript": ("paper.md", f, "text/markdown"),
            },
        )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

def test_list_cases_empty(api_client):
    resp = api_client.get("/api/cases")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_and_get_case(api_client, tmp_path):
    """Create a case via multipart upload, then fetch it."""
    case_id = _create_case(api_client, tmp_path, "Test Paper", "Does it work?")

    # GET /api/cases should list it
    resp2 = api_client.get("/api/cases")
    assert resp2.status_code == 200
    cases = resp2.json()
    assert any(c["id"] == case_id for c in cases)

    # GET /api/cases/{id} full project
    resp3 = api_client.get(f"/api/cases/{case_id}")
    assert resp3.status_code == 200
    project = resp3.json()
    assert project["id"] == case_id
    assert "claims" in project
    assert "papers" in project
    assert "actions" in project


def test_delete_case_removes_it_from_the_workspace(api_client, tmp_path):
    case_id = _create_case(api_client, tmp_path, "Delete Test")

    deleted = api_client.delete(f"/api/cases/{case_id}")

    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == case_id
    assert api_client.get(f"/api/cases/{case_id}").status_code == 404
    assert all(item["id"] != case_id for item in api_client.get("/api/cases").json())


def test_legacy_impact_review_state_does_not_break_project_response(api_client):
    import radar.api as api_module

    legacy = SimpleNamespace(
        id="legacy-impact",
        source_snapshot_id="missing-snapshot",
        claim_revision_id="missing-revision",
        condition_differences_json=[],
        evidence_new_json={},
        evidence_own_json={},
        suggested_action="monitor",
        uncertainty_json=[],
        stance="neutral",
        severity="informative",
        review_state="informative",
    )

    paper = api_module._impact_to_paper_out(legacy)

    assert paper.reviewState == "candidate"


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------

def test_list_claims(api_client, tmp_path):
    case_id = _create_case(api_client, tmp_path, "Claim Test")

    resp2 = api_client.get(f"/api/cases/{case_id}/claims")
    assert resp2.status_code == 200
    claims = resp2.json()
    assert isinstance(claims, list)
    # The heuristic extraction should find at least one claim candidate
    if claims:
        claim = claims[0]
        assert "id" in claim
        assert "text" in claim
        assert "status" in claim
        assert "contract" in claim


def test_confirm_reject_claim(api_client, tmp_path):
    case_id = _create_case(api_client, tmp_path, "Gate Test")

    claims = api_client.get(f"/api/cases/{case_id}/claims").json()
    if not claims:
        pytest.skip("no claim candidates extracted")
    rev_id = claims[0]["id"]

    # Confirm
    resp_confirm = api_client.post(f"/api/cases/{case_id}/claims/{rev_id}/confirm")
    assert resp_confirm.status_code == 200
    assert resp_confirm.json()["confirmed"] == "yes"

    # Reject another scenario — find a candidate
    claims2 = api_client.get(f"/api/cases/{case_id}/claims").json()
    candidates = [c for c in claims2 if c["confirmed"] == "pending"]
    if not candidates:
        return  # all confirmed already
    candidate_id = candidates[0]["id"]
    resp_reject = api_client.post(f"/api/cases/{case_id}/claims/{candidate_id}/reject")
    assert resp_reject.status_code == 200


# ---------------------------------------------------------------------------
# Scans
# ---------------------------------------------------------------------------

def test_list_scans_empty(api_client, tmp_path):
    case_id = _create_case(api_client, tmp_path, "Scan Test")

    resp2 = api_client.get(f"/api/cases/{case_id}/scans")
    assert resp2.status_code == 200
    assert resp2.json() == []


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def test_list_actions(api_client, tmp_path):
    case_id = _create_case(api_client, tmp_path, "Action Test")

    resp2 = api_client.get(f"/api/cases/{case_id}/actions")
    assert resp2.status_code == 200
    assert isinstance(resp2.json(), list)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def test_get_settings(api_client):
    resp = api_client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "llm" in data
    assert "embedding" in data
    assert "pdf_parser_backend" in data


def test_openai_embedding_is_not_configured_without_its_own_key(
    api_client, monkeypatch
):
    from radar.config import Settings

    settings = Settings(
        _env_file=None,
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        embedding_base_url="https://api.openai.com/v1",
        embedding_api_key=None,
    )
    monkeypatch.setattr("radar.api.get_settings", lambda: settings)

    resp = api_client.get("/api/settings")

    assert resp.status_code == 200
    assert resp.json()["embedding"]["configured"] is False


def test_put_settings(api_client, tmp_path, monkeypatch):
    """Write a settings key and verify it was saved."""
    # Redirect save_local_settings to a temp file
    target = tmp_path / "settings.local.env"
    monkeypatch.setattr(
        "radar.config.LOCAL_SETTINGS_FILE",
        target,
    )
    monkeypatch.setattr(
        "radar.api.save_local_settings",
        lambda updates, path=None: __import__("radar.config").config.save_local_settings(
            updates, path=target
        ),
    )

    resp = api_client.put("/api/settings", json={"updates": {"LLM_MODEL": "test-model"}})
    assert resp.status_code == 200
    assert "test-model" in target.read_text()


def test_put_settings_never_persists_secret_sentinel(api_client, tmp_path, monkeypatch):
    target = tmp_path / "settings.local.env"
    monkeypatch.setattr("radar.config.LOCAL_SETTINGS_FILE", target)
    monkeypatch.setattr(
        "radar.api.save_local_settings",
        lambda updates, path=None: __import__("radar.config").config.save_local_settings(
            updates, path=target
        ),
    )

    resp = api_client.put(
        "/api/settings",
        json={"updates": {"LLM_API_KEY": "__keep__", "LLM_MODEL": "safe-model"}},
    )

    assert resp.status_code == 200
    assert resp.json()["saved"] == ["LLM_MODEL"]
    assert "__keep__" not in target.read_text()


def test_put_settings_rejects_unknown_keys(api_client):
    resp = api_client.put(
        "/api/settings",
        json={"updates": {"UNSUPPORTED_SECRET": "should-not-be-written"}},
    )

    assert resp.status_code == 400
    assert "unsupported settings keys" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

def test_cors_headers_present(api_client):
    """OPTIONS preflight should return CORS headers."""
    resp = api_client.options(
        "/api/cases",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert "access-control-allow-origin" in resp.headers


def test_cors_header_on_get(api_client):
    """Ordinary GET should include CORS allow-origin."""
    resp = api_client.get(
        "/api/cases",
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.status_code == 200
    # The CORS middleware sets this on every response when origin matches
    assert "access-control-allow-origin" in resp.headers


# ---------------------------------------------------------------------------
# Competitors
# ---------------------------------------------------------------------------

def test_competitors_crud(api_client, tmp_path):
    case_id = _create_case(api_client, tmp_path, "Competitor Test")

    # List empty
    resp_list = api_client.get(f"/api/cases/{case_id}/competitors")
    assert resp_list.status_code == 200
    assert resp_list.json() == []

    # Add
    resp_add = api_client.post(
        f"/api/cases/{case_id}/competitors",
        json={"team": "Kowalski Lab", "aliases": ["N. Kowalski"]},
    )
    assert resp_add.status_code == 200
    watch_id = resp_add.json()["id"]

    # List one
    resp_list2 = api_client.get(f"/api/cases/{case_id}/competitors")
    assert resp_list2.status_code == 200
    assert len(resp_list2.json()) == 1

    # Delete
    resp_del = api_client.delete(f"/api/cases/{case_id}/competitors/{watch_id}")
    assert resp_del.status_code == 200

    # List empty again
    resp_list3 = api_client.get(f"/api/cases/{case_id}/competitors")
    assert resp_list3.json() == []


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

def test_get_profile_empty(api_client, tmp_path):
    case_id = _create_case(api_client, tmp_path, "Profile Test")

    resp2 = api_client.get(f"/api/cases/{case_id}/profile")
    assert resp2.status_code == 200
    data = resp2.json()
    assert "question" in data
    assert "thesis" in data


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

def test_audit_export(api_client, tmp_path):
    case_id = _create_case(api_client, tmp_path, "Audit Test")

    resp2 = api_client.get(f"/api/cases/{case_id}/audit")
    assert resp2.status_code == 200
    assert isinstance(resp2.json(), list)

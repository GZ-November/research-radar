import numpy as np
from sqlalchemy import select, text

from radar.models import ClaimRevision, Source, SourceSnapshot
from radar.services.retrieval_service import RetrievalService


class SemanticEmbedding:
    model = "semantic-test"

    def embed(self, texts):
        vectors = []
        for value in texts:
            if value == "semantic-only-query" or "EchoRAG" in value:
                vectors.append([1.0, 0.0])
            else:
                vectors.append([0.0, 1.0])
        return np.asarray(vectors, dtype=np.float32)


class FailingEmbedding:
    model = "failing-test"

    def embed(self, texts):
        raise RuntimeError("ollama_unavailable")


def test_golden_retrieval_and_routing(db_session_factory, golden_case):
    service = RetrievalService(db_session_factory)
    service.rebuild_fts()
    with service.engine.connect() as connection:
        assert connection.execute(
            text("SELECT count(*) FROM source_fts")
        ).scalar_one() == 20

    ranked = service.rank_sources("DomainQA RadarNet exact match retrieval", top_k=10)
    ranked_ids = {item[0] for item in ranked}
    assert "snapshot-01" in ranked_ids
    hard_negative_ids = {f"snapshot-{index:02d}" for index in range(11, 21)}
    assert len(ranked_ids & hard_negative_ids) < 5

    with db_session_factory() as session:
        claims = list(session.scalars(select(ClaimRevision).where(ClaimRevision.review_state == "confirmed")))
    routed = service.route_claims("snapshot-01", claims, top_k=3)
    assert "claim-rev-01" in {item[0] for item in routed}


def test_competitor_alias_is_a_flag_only(db_session_factory, golden_case):
    assert RetrievalService(db_session_factory).competitor_flag(golden_case, "source-03") is True


def test_semantic_score_participates_in_hybrid_ranking(
    db_session_factory, golden_case
):
    service = RetrievalService(
        db_session_factory, embedding_client=SemanticEmbedding()
    )
    ranked = service.rank_sources("semantic-only-query", top_k=3)

    assert ranked[0][0] == "snapshot-01"
    assert "cosine=" in ranked[0][2]
    assert service.last_embedding_error is None


def test_embedding_failure_falls_back_to_lexical(
    db_session_factory, golden_case
):
    service = RetrievalService(
        db_session_factory, embedding_client=FailingEmbedding()
    )
    ranked = service.rank_sources(
        "DomainQA RadarNet exact match retrieval", top_k=10
    )

    assert "snapshot-01" in {item[0] for item in ranked}
    assert service.last_embedding_error == "ollama_unavailable"
    assert service.embedding_errors == ["ollama_unavailable"]
    assert "semantic fallback" in ranked[0][2]


def _add_late_snapshot(db_session_factory) -> None:
    """Add one snapshot after the FTS rebuild so the index cannot know it."""
    with db_session_factory() as session:
        session.add(
            Source(
                id="source-late",
                external_id="arxiv:late",
                title="Zzqk late paper",
                authors_json=["Late Lab"],
                url="https://arxiv.org/abs/late",
                integrity_state="normal",
            )
        )
        session.flush()
        session.add(
            SourceSnapshot(
                id="snapshot-late",
                source_id="source-late",
                version_label="v1",
                title="Zzqk late paper",
                abstract="zzqk unreproduced calibration term",
                content_text="zzqk unreproduced calibration term",
                content_hash="hash-late",
            )
        )
        session.commit()


def test_rank_sources_prefilters_with_fts_and_falls_back_without_it(
    db_session_factory, golden_case
):
    service = RetrievalService(db_session_factory)
    service.rebuild_fts()
    _add_late_snapshot(db_session_factory)

    # The late snapshot is missing from the FTS index, so the pre-filter
    # legitimately hides it from unrestricted ranking.
    ranked = service.rank_sources("zzqk unreproduced", top_k=5)
    assert ranked == []

    # With the FTS table gone the same query falls back to the full-table
    # scan and finds it.
    with service.engine.begin() as connection:
        connection.execute(text("DROP TABLE source_fts"))
    ranked = service.rank_sources("zzqk unreproduced", top_k=5)
    assert "snapshot-late" in {item[0] for item in ranked}


def test_fts_prefilter_preserves_fallback_ranking(db_session_factory, golden_case):
    service = RetrievalService(db_session_factory)
    service.rebuild_fts()
    fts_ranked = service.rank_sources(
        "DomainQA RadarNet exact match retrieval", top_k=10
    )

    with service.engine.begin() as connection:
        connection.execute(text("DROP TABLE source_fts"))
    fallback_ranked = service.rank_sources(
        "DomainQA RadarNet exact match retrieval", top_k=10
    )

    assert fts_ranked
    # The pre-filter only drops snapshots that would score zero anyway, so
    # the positive-score ranking must be identical to the fallback scan.
    assert fts_ranked == [item for item in fallback_ranked if item[1] > 0]
    assert len(fallback_ranked) > len(fts_ranked)


def test_rank_sources_without_fts_table_uses_full_table_scan(
    db_session_factory, golden_case
):
    service = RetrievalService(db_session_factory)
    ranked = service.rank_sources("DomainQA RadarNet exact match retrieval", top_k=5)
    assert "snapshot-01" in {item[0] for item in ranked}

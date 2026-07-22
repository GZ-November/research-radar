"""Two-stage hybrid retrieval: SQLite FTS5 pre-filter, then Python rerank."""

import re
from collections import Counter

import numpy as np
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from radar.db import SessionLocal, session_scope
from radar.embeddings.base import EmbeddingClient
from radar.models import Claim, ClaimRevision, Source, SourceSnapshot, WatchEntity


def _tokens(value: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 2]


class RetrievalService:
    def __init__(
        self,
        session_factory: sessionmaker[Session] = SessionLocal,
        *,
        engine: Engine | None = None,
        embedding_client: EmbeddingClient | None = None,
        lexical_weight: float = 0.55,
        semantic_weight: float = 0.45,
        fts_candidate_limit: int = 50,
    ):
        if lexical_weight < 0 or semantic_weight < 0 or lexical_weight + semantic_weight <= 0:
            raise ValueError("retrieval_weights_invalid")
        self.session_factory = session_factory
        if engine is not None:
            self.engine = engine
        else:
            # Resolve the bind through the public session API; sessionmaker.kw
            # is private and not part of SQLAlchemy's stability guarantees.
            with session_factory() as session:
                self.engine = session.get_bind()
        total_weight = lexical_weight + semantic_weight
        self.lexical_weight = lexical_weight / total_weight
        self.semantic_weight = semantic_weight / total_weight
        self.embedding_client = embedding_client
        self.fts_candidate_limit = fts_candidate_limit
        self.last_embedding_error: str | None = None
        self.embedding_errors: list[str] = []

    @property
    def embedding_enabled(self) -> bool:
        return self.embedding_client is not None

    @staticmethod
    def _scale_nonnegative(values: list[float]) -> np.ndarray:
        scores = np.asarray(values, dtype=np.float32)
        maximum = float(scores.max()) if scores.size else 0.0
        return scores / maximum if maximum > 0 else np.zeros_like(scores)

    @staticmethod
    def _scale_similarity(values: np.ndarray) -> np.ndarray:
        if values.size == 0:
            return values
        minimum = float(values.min())
        maximum = float(values.max())
        if maximum - minimum < 1e-8:
            return np.full_like(values, 0.5)
        return (values - minimum) / (maximum - minimum)

    def _hybrid_scores(
        self, query: str, documents: list[str], lexical_scores: list[float]
    ) -> tuple[list[float], list[float] | None]:
        if self.embedding_client is None or not documents:
            self.last_embedding_error = None
            return lexical_scores, None
        try:
            vectors = self.embedding_client.embed([query, *documents])
            if vectors.shape[0] != len(documents) + 1:
                raise RuntimeError("embedding_batch_shape_mismatch")
            similarities = vectors[1:] @ vectors[0]
            hybrid = (
                self.lexical_weight * self._scale_nonnegative(lexical_scores)
                + self.semantic_weight * self._scale_similarity(similarities)
            )
            self.last_embedding_error = None
            return hybrid.astype(float).tolist(), similarities.astype(float).tolist()
        except Exception as exc:
            self.last_embedding_error = str(exc)
            self.embedding_errors.append(self.last_embedding_error)
            return lexical_scores, None

    def rebuild_fts(self) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS source_fts "
                    "USING fts5(snapshot_id UNINDEXED, title, content)"
                )
            )
            connection.execute(text("DELETE FROM source_fts"))
            snapshots = connection.execute(
                text("SELECT id, title, content_text FROM source_snapshots")
            ).all()
            for snapshot in snapshots:
                connection.execute(
                    text(
                        "INSERT INTO source_fts(snapshot_id, title, content) "
                        "VALUES (:snapshot_id, :title, :content)"
                    ),
                    {"snapshot_id": snapshot.id, "title": snapshot.title, "content": snapshot.content_text},
                )

    def _fts_candidate_ids(
        self, query_tokens: list[str], limit: int
    ) -> list[str] | None:
        """Return FTS5-matched snapshot ids, or None when the index is unusable.

        Tokens come from ``_tokens`` (plain ``[a-z0-9]+``), so joining them
        into an OR MATCH expression cannot inject FTS5 syntax.
        """

        if not query_tokens:
            return None
        match = " OR ".join(query_tokens)
        try:
            with self.engine.connect() as connection:
                rows = connection.execute(
                    text(
                        "SELECT snapshot_id FROM source_fts "
                        "WHERE source_fts MATCH :match "
                        "ORDER BY rank LIMIT :limit"
                    ),
                    {"match": match, "limit": limit},
                ).all()
        except Exception:
            # Missing or stale FTS5 table: fall back to the full-table scan.
            return None
        return [row.snapshot_id for row in rows]

    def rank_sources(
        self,
        query: str,
        top_k: int = 20,
        snapshot_ids: set[str] | None = None,
    ) -> list[tuple[str, float, str]]:
        query_tokens = _tokens(query)
        with session_scope(self.session_factory) as session:
            statement = select(SourceSnapshot)
            if snapshot_ids is not None:
                # An explicit candidate set is already small and may be newer
                # than the FTS index, so score it directly.
                if not snapshot_ids:
                    return []
                statement = statement.where(SourceSnapshot.id.in_(snapshot_ids))
            else:
                # Unrestricted ranking would tokenize every snapshot in the
                # library, so pre-filter with FTS5 and rerank only the best
                # candidates. Any snapshot scoring above zero must contain at
                # least one query token, hence must pass the MATCH filter.
                candidate_ids = self._fts_candidate_ids(
                    query_tokens, self.fts_candidate_limit
                )
                if candidate_ids is not None:
                    if not candidate_ids:
                        return []
                    statement = statement.where(SourceSnapshot.id.in_(candidate_ids))
            snapshots = list(session.scalars(statement))
            query_counts = Counter(query_tokens)
            lexical_scores: list[float] = []
            documents: list[str] = []
            for snapshot in snapshots:
                document_counts = Counter(_tokens(f"{snapshot.title} {snapshot.content_text}"))
                overlap = sum(min(count, document_counts[token]) for token, count in query_counts.items())
                phrase_bonus = 2.0 if query.lower() in snapshot.content_text.lower() else 0.0
                lexical_scores.append(float(overlap) + phrase_bonus)
                documents.append(f"{snapshot.title}\n{snapshot.abstract or snapshot.content_text[:8000]}")
            scores, similarities = self._hybrid_scores(query, documents, lexical_scores)
            ranked: list[tuple[str, float, str]] = []
            for index, snapshot in enumerate(snapshots):
                overlap = int(lexical_scores[index])
                if similarities is None:
                    reason = f"lexical overlap: {overlap}"
                    if self.last_embedding_error:
                        reason += f"; semantic fallback: {self.last_embedding_error}"
                else:
                    reason = (
                        f"hybrid lexical={lexical_scores[index]:.2f}, "
                        f"cosine={similarities[index]:.4f}"
                    )
                ranked.append((snapshot.id, scores[index], reason))
            return sorted(ranked, key=lambda item: (-item[1], item[0]))[:top_k]

    def route_claims(
        self, source_snapshot_id: str, claim_revisions: list[ClaimRevision], top_k: int = 3
    ) -> list[tuple[str, float, str]]:
        with session_scope(self.session_factory) as session:
            snapshot = session.get(SourceSnapshot, source_snapshot_id)
            if snapshot is None:
                raise LookupError(f"snapshot not found: {source_snapshot_id}")
            source_tokens = Counter(_tokens(f"{snapshot.title} {snapshot.content_text}"))
            lexical_scores: list[float] = []
            documents: list[str] = []
            for claim in claim_revisions:
                claim_text = (
                    f"{claim.statement} "
                    f"{' '.join(str(v or '') for v in claim.contract_json.values())}"
                )
                claim_tokens = Counter(_tokens(claim_text))
                overlap = sum(min(count, source_tokens[token]) for token, count in claim_tokens.items())
                lexical_scores.append(float(overlap))
                documents.append(claim_text)
            source_text = f"{snapshot.title}\n{snapshot.abstract or snapshot.content_text[:8000]}"
            scores, similarities = self._hybrid_scores(
                source_text, documents, lexical_scores
            )
            ranked = []
            for index, claim in enumerate(claim_revisions):
                overlap = int(lexical_scores[index])
                if similarities is None:
                    reason = f"shared research terms: {overlap}"
                    if self.last_embedding_error:
                        reason += f"; semantic fallback: {self.last_embedding_error}"
                else:
                    reason = (
                        f"hybrid shared_terms={overlap}, "
                        f"cosine={similarities[index]:.4f}"
                    )
                ranked.append((claim.id, scores[index], reason))
            return sorted(ranked, key=lambda item: (-item[1], item[0]))[:top_k]

    def competitor_flag(self, case_id: str, source_id: str) -> bool:
        with session_scope(self.session_factory) as session:
            source = session.get(Source, source_id)
            watches = list(session.scalars(select(WatchEntity).where(WatchEntity.case_id == case_id)))
            if source is None:
                return False
            haystack = " ".join(source.authors_json).lower()
            return any(
                alias.lower() in haystack
                for watch in watches
                for alias in [watch.canonical_name, *watch.aliases_json]
            )

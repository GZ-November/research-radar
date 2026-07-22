"""Deterministic six-field condition comparison."""

import re

from radar.schemas import ConditionDifference, EmpiricalClaimContract


FIELDS = ("task", "dataset", "split", "metric", "comparator", "scope")
BLOCKING_FIELDS = {"task", "dataset", "metric", "comparator"}
ALIASES = {
    "exact match": {"em", "exact-match", "exact match"},
    "macro-f1": {"macro f1", "macro-f1", "macro f-score"},
    "open-domain qa": {"open domain qa", "odqa", "open-domain question answering"},
    "median latency": {"p50 latency", "median retrieval latency", "median latency"},
}


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def canonical(value: str) -> str:
    normalized = normalize(value)
    for key, values in ALIASES.items():
        if normalized in {normalize(item) for item in values | {key}}:
            return normalize(key)
    return normalized


class ConditionService:
    def compare(
        self,
        own_contract: EmpiricalClaimContract | dict,
        incoming_contract: EmpiricalClaimContract | dict,
    ) -> list[ConditionDifference]:
        own = (
            own_contract
            if isinstance(own_contract, EmpiricalClaimContract)
            else EmpiricalClaimContract.model_validate(own_contract)
        )
        incoming = (
            incoming_contract
            if isinstance(incoming_contract, EmpiricalClaimContract)
            else EmpiricalClaimContract.model_validate(incoming_contract)
        )
        differences: list[ConditionDifference] = []
        for field in FIELDS:
            own_value = getattr(own, field)
            incoming_value = getattr(incoming, field)
            if not own_value or not incoming_value:
                status = "unknown"
                explanation = "At least one source does not report this condition."
            elif normalize(own_value) == normalize(incoming_value):
                status = "match"
                explanation = "Values match after normalization."
            elif canonical(own_value) == canonical(incoming_value):
                status = "compatible_alias"
                explanation = "Values match through a curated alias."
            elif normalize(own_value) in normalize(incoming_value) or normalize(incoming_value) in normalize(own_value):
                status = "partial"
                explanation = "Values overlap but scopes are not identical."
            else:
                status = "mismatch"
                explanation = "Reported values differ."
            differences.append(
                ConditionDifference(
                    field=field,
                    own_value=own_value,
                    incoming_value=incoming_value,
                    status=status,
                    explanation=explanation,
                )
            )
        return differences

    def overall_comparability(self, differences: list[ConditionDifference]) -> str:
        if any(item.field in BLOCKING_FIELDS and item.status == "mismatch" for item in differences):
            return "incompatible"
        required_unknowns = sum(
            item.field in BLOCKING_FIELDS and item.status == "unknown" for item in differences
        )
        if required_unknowns >= 2:
            return "unknown"
        if any(item.status in {"partial", "unknown", "mismatch"} for item in differences):
            return "partial"
        return "compatible"


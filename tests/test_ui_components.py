"""Tests for the shared UI label dictionaries and pure render helpers."""

import typing
from types import SimpleNamespace

from radar import schemas
from radar.services.scan_runner import ACTIVE_STATUSES
from radar.ui import components


def _literal_values(annotation) -> set[str]:
    return {value for value in typing.get_args(annotation) if isinstance(value, str)}


def _field_values(model, field: str) -> set[str]:
    return _literal_values(model.model_fields[field].annotation)


def test_stance_label_covers_schema_values():
    expected = _field_values(schemas.ImpactAssessmentOutput, "stance")
    assert expected <= components.STANCE_LABEL.keys()


def test_impact_mode_label_covers_schema_values():
    expected = _field_values(schemas.ImpactAssessmentOutput, "impact_mode")
    assert expected <= components.IMPACT_MODE_LABEL.keys()
    assert expected <= set(components.IMPACT_MODES)


def test_suggested_action_label_covers_schema_values():
    expected = _field_values(schemas.ImpactAssessmentOutput, "suggested_action")
    assert expected <= components.SUGGESTED_ACTION_LABEL.keys()
    assert expected <= set(components.SUGGESTED_ACTIONS)


def test_comparability_label_covers_schema_values():
    expected = _field_values(schemas.ImpactAssessmentOutput, "comparability")
    assert expected <= components.COMPARABILITY_LABEL.keys()


def test_condition_status_label_covers_schema_values():
    expected = _field_values(schemas.ConditionDifference, "status")
    assert expected <= components.CONDITION_STATUS_LABEL.keys()


def test_priority_label_covers_schema_values():
    expected = _field_values(schemas.ActionRecommendation, "priority")
    assert expected <= components.PRIORITY_LABEL.keys()


def test_edit_class_label_covers_schema_values():
    expected = _field_values(schemas.PatchProposalOutput, "edit_class")
    assert expected <= components.EDIT_CLASS_LABEL.keys()


def test_contract_field_label_covers_schema_values():
    expected = set(schemas.EmpiricalClaimContract.model_fields)
    assert expected <= components.CONTRACT_FIELD_LABEL.keys()


def test_centrality_label_covers_schema_values():
    expected = _field_values(schemas.ManuscriptClaimProfile, "role")
    assert expected <= components.CENTRALITY_LABEL.keys()


def test_trust_state_label_covers_schema_values():
    expected = _field_values(schemas.TrustResult, "state")
    assert expected <= components.TRUST_STATE_LABEL.keys()


def test_health_label_covers_service_states():
    # Mirror of LedgerService.get_claim_health return values.
    expected = {"active", "corroborated", "contested", "revalidation_required"}
    assert expected <= components.HEALTH_LABEL.keys()


def test_attention_label_covers_service_states():
    # Mirror of ActionService.claim_attention_state return values.
    expected = {
        "stable", "new_support", "needs_review", "disputed",
        "competitor_pressure", "revalidation_required",
    }
    assert expected <= components.ATTENTION_LABEL.keys()


def test_review_state_label_covers_known_states():
    # ImpactCandidate and ClaimRevision review states used across services.
    expected = {
        "candidate", "confirmed", "edited", "dismissed",
        "informative", "rejected", "superseded",
    }
    assert expected <= components.REVIEW_STATE_LABEL.keys()


def test_action_status_label_covers_known_states():
    # ActionItem.status values written by ActionService/ReviewService.
    expected = {"proposed", "open", "in_progress", "done", "dismissed"}
    assert expected <= components.ACTION_STATUS_LABEL.keys()


def test_scan_status_label_covers_known_states():
    # ScanRun.status values written by scan_runner/WeeklyRadarService.
    expected = ACTIVE_STATUSES | {
        "pending", "completed", "failed", "interrupted", "cancelled",
    }
    assert expected <= components.SCAN_STATUS_LABEL.keys()


def test_validation_label_covers_patch_checks():
    # Mirror of PatchService._validate result keys.
    expected = {
        "impact_confirmed", "before_text_exact", "citations_resolved",
        "citation_marker_safe", "locked_numbers_unchanged", "original_file_untouched",
    }
    assert expected <= components.VALIDATION_LABEL.keys()


def test_label_for_falls_back_to_raw_value():
    assert components.label_for(components.STANCE_LABEL, "supports") == "支持"
    assert components.label_for(components.STANCE_LABEL, "unknown_value") == "unknown_value"


def test_validation_summary_counts_failures():
    assert components.validation_summary(None) == "—"
    assert components.validation_summary({}) == "—"
    assert components.validation_summary({"a": True, "b": True}) == "2 项全部通过"
    assert components.validation_summary(
        {"a": True, "b": False, "c": True}
    ) == "2 项通过 · 1 项未通过"


def test_impact_status_badges_use_labels_and_fallback():
    impact = SimpleNamespace(
        severity="critical", stance="supports",
        impact_mode="prior_art", review_state="candidate",
    )
    badges = components.impact_status_badges(impact)
    assert ":red-badge[紧急]" in badges
    assert ":green-badge[支持]" in badges
    assert "在先工作" in badges
    assert "待确认" in badges

    unknown = SimpleNamespace(
        severity="weird", stance="odd", impact_mode="strange", review_state="new",
    )
    fallback = components.impact_status_badges(unknown)
    assert "weird" in fallback and "odd" in fallback


def test_impact_guidance_callout_levels():
    base = dict(
        review_state="candidate", trust_state="verified", impact_mode="replication",
        event_type="new_publication", stance="supports", comparability="compatible",
    )
    _, _, level = components.impact_guidance_callout(SimpleNamespace(**base))
    assert level == "warning"
    _, _, level = components.impact_guidance_callout(
        SimpleNamespace(**{**base, "review_state": "confirmed"})
    )
    assert level == "success"
    _, _, level = components.impact_guidance_callout(
        SimpleNamespace(**{**base, "review_state": "dismissed"})
    )
    assert level == "info"

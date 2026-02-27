"""Integration tests for the full ingest pipeline.

Tests the end-to-end flow across multiple components:
  HTTP request → validate_ingestion_request → normalize_labels
  → write_posture_snapshot → write_assessment_summaries → Table Storage
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "functions"))

import azure.functions as func
from shared.normalizer import normalize_labels
from shared.table_client import write_assessment_summaries, write_posture_snapshot
from shared.validation import validate_ingestion_request


def _make_request(body: dict | None = None, headers: dict | None = None, invalid_json: bool = False):
    """Create a mock func.HttpRequest."""
    req = MagicMock(spec=func.HttpRequest)
    _headers = headers or {}
    req.headers = MagicMock()
    req.headers.get = lambda key, default="": _headers.get(key, default)
    if invalid_json:
        req.get_json.side_effect = ValueError("Invalid JSON body")
    else:
        req.get_json.return_value = body or {}
    return req


class TestIngestPipelineHappyPath:
    """Full ingest flow with a valid payload."""

    def test_valid_payload_passes_validation(self, sample_payload):
        req = _make_request(body=sample_payload)
        result = validate_ingestion_request(req)
        assert result["tenant_id"] == sample_payload["tenant_id"]
        assert result["agency_id"] == sample_payload["agency_id"]

    def test_snapshot_written_to_table(self, sample_payload, table_store):
        req = _make_request(body=sample_payload)
        payload = validate_ingestion_request(req)
        normalized = normalize_labels(payload["label_taxonomy"])
        write_posture_snapshot(payload, normalized)

        rows = list(table_store["AgencyPostureSnapshot"].values())
        assert len(rows) == 1
        assert rows[0]["PartitionKey"] == "dept-of-education"
        assert rows[0]["LabelCoveragePct"] == 72.5
        assert rows[0]["ComplianceScoreCurrent"] == 72.0

    def test_label_normalization_map_written(self, sample_payload, table_store):
        req = _make_request(body=sample_payload)
        payload = validate_ingestion_request(req)
        normalized = normalize_labels(payload["label_taxonomy"])
        write_posture_snapshot(payload, normalized)

        label_rows = list(table_store["LabelNormalizationMap"].values())
        assert len(label_rows) == 3  # 3 labels in sample_payload
        tiers = {r["LabelName"]: r["NormalizedTier"] for r in label_rows}
        assert tiers["Public"] == "Public"
        assert tiers["Confidential - PII"] == "Confidential"
        assert tiers["Restricted - FERPA"] == "Restricted"

    def test_assessment_summaries_written(self, sample_payload, table_store):
        write_assessment_summaries(sample_payload)

        rows = list(table_store["AssessmentSummary"].values())
        assert len(rows) == 1
        assert rows[0]["Regulation"] == "NIST 800-53"
        assert rows[0]["ComplianceScore"] == 68.0
        assert rows[0]["PassRate"] == pytest.approx(78.95, abs=0.01)  # 45/57 * 100

    def test_row_key_format(self, sample_payload, table_store):
        """RowKey must be {timestamp}_{tenant_id} for correct time-ordering."""
        write_posture_snapshot(sample_payload, [])

        rows = list(table_store["AgencyPostureSnapshot"].values())
        expected_rk = f"{sample_payload['timestamp']}_{sample_payload['tenant_id']}"
        assert rows[0]["RowKey"] == expected_rk

    def test_compliance_score_pct_derived(self, sample_payload, table_store):
        """ComplianceScorePct should be computed from current/max."""
        write_posture_snapshot(sample_payload, [])

        rows = list(table_store["AgencyPostureSnapshot"].values())
        assert rows[0]["ComplianceScorePct"] == pytest.approx(72.0, abs=0.01)

    def test_all_metric_fields_present(self, sample_payload, table_store):
        write_posture_snapshot(sample_payload, [])

        row = list(table_store["AgencyPostureSnapshot"].values())[0]
        for field in (
            "DlpIncidents30d", "DlpIncidents60d", "DlpIncidents90d",
            "ExternalSharingCount", "RetentionPolicyCount", "RetentionCoveragePct",
            "InsiderRiskHigh", "InsiderRiskMedium", "InsiderRiskLow", "InsiderRiskTotal",
            "ImprovementActionsImplemented", "ImprovementActionsPlanned",
            "ImprovementActionsNotStarted", "CollectorVersion",
        ):
            assert field in row, f"Missing field: {field}"


class TestIngestPipelineValidation:
    """Validation failures are surfaced correctly across the pipeline."""

    def test_invalid_json_raises(self):
        req = _make_request(invalid_json=True)
        with pytest.raises(ValueError, match="Invalid JSON body"):
            validate_ingestion_request(req)

    def test_missing_required_field_raises(self, sample_payload):
        del sample_payload["compliance_score_current"]
        req = _make_request(body=sample_payload)
        with pytest.raises(ValueError, match="Schema validation failed"):
            validate_ingestion_request(req)

    def test_invalid_tenant_id_format_raises(self, sample_payload):
        sample_payload["tenant_id"] = "not-a-uuid"
        req = _make_request(body=sample_payload)
        with pytest.raises(ValueError, match="Schema validation failed"):
            validate_ingestion_request(req)

    def test_extra_field_rejected(self, sample_payload):
        sample_payload["unexpected_field"] = "not allowed"
        req = _make_request(body=sample_payload)
        with pytest.raises(ValueError, match="Schema validation failed"):
            validate_ingestion_request(req)

    def test_label_coverage_above_100_rejected(self, sample_payload):
        sample_payload["label_coverage_pct"] = 150.0
        req = _make_request(body=sample_payload)
        with pytest.raises(ValueError, match="Schema validation failed"):
            validate_ingestion_request(req)

    def test_negative_dlp_count_rejected(self, sample_payload):
        sample_payload["dlp_incidents_30d"] = -1
        req = _make_request(body=sample_payload)
        with pytest.raises(ValueError, match="Schema validation failed"):
            validate_ingestion_request(req)

    def test_tenant_not_in_allowlist_rejected(self, sample_payload, monkeypatch):
        monkeypatch.setenv("ALLOWED_TENANT_IDS", "00000000-0000-0000-0000-000000000001")
        from shared.config import get_settings
        get_settings.cache_clear()

        req = _make_request(body=sample_payload)
        with pytest.raises(ValueError, match="not in allow-list"):
            validate_ingestion_request(req)

    def test_tenant_in_allowlist_passes(self, sample_payload, monkeypatch):
        tenant = sample_payload["tenant_id"]
        monkeypatch.setenv("ALLOWED_TENANT_IDS", tenant)
        from shared.config import get_settings
        get_settings.cache_clear()

        req = _make_request(body=sample_payload)
        result = validate_ingestion_request(req)
        assert result["tenant_id"] == tenant

    def test_missing_cert_header_rejected_when_thumbprints_configured(self, sample_payload, monkeypatch):
        monkeypatch.setenv("ALLOWED_CERT_THUMBPRINTS", "A" * 40)
        from shared.config import get_settings
        get_settings.cache_clear()

        req = _make_request(body=sample_payload)  # no cert header
        with pytest.raises(ValueError, match="Missing client certificate"):
            validate_ingestion_request(req)

    def test_cert_validation_skipped_when_no_thumbprints_configured(self, sample_payload):
        """Dev mode: no thumbprints configured → cert header not required."""
        req = _make_request(body=sample_payload)  # no cert header
        result = validate_ingestion_request(req)
        assert result["agency_id"] == sample_payload["agency_id"]


class TestIngestPipelineMultiTenant:
    """Multi-tenant and multi-agency ingestion scenarios."""

    def test_two_tenants_same_agency_write_separate_rows(self, sample_payload, table_store):
        write_posture_snapshot(sample_payload, [])

        payload2 = dict(sample_payload)
        payload2["tenant_id"] = "b2c3d4e5-f6a7-8901-bcde-f12345678901"
        payload2["compliance_score_current"] = 85.0
        write_posture_snapshot(payload2, [])

        rows = list(table_store["AgencyPostureSnapshot"].values())
        assert len(rows) == 2
        scores = {r["TenantId"]: r["ComplianceScoreCurrent"] for r in rows}
        assert scores[sample_payload["tenant_id"]] == 72.0
        assert scores[payload2["tenant_id"]] == 85.0

    def test_two_agencies_write_separate_rows(self, sample_payload, table_store):
        write_posture_snapshot(sample_payload, [])

        payload2 = dict(sample_payload)
        payload2["agency_id"] = "dept-of-health"
        payload2["tenant_id"] = "b2c3d4e5-f6a7-8901-bcde-f12345678901"
        write_posture_snapshot(payload2, [])

        rows = list(table_store["AgencyPostureSnapshot"].values())
        agencies = {r["PartitionKey"] for r in rows}
        assert agencies == {"dept-of-education", "dept-of-health"}

    def test_upsert_overwrites_same_snapshot(self, sample_payload, table_store):
        """Resubmitting the same tenant+timestamp should upsert, not duplicate."""
        write_posture_snapshot(sample_payload, [])

        updated = dict(sample_payload)
        updated["compliance_score_current"] = 90.0
        write_posture_snapshot(updated, [])

        rows = list(table_store["AgencyPostureSnapshot"].values())
        assert len(rows) == 1
        assert rows[0]["ComplianceScoreCurrent"] == 90.0

    def test_multiple_assessments_all_written(self, sample_payload, table_store):
        sample_payload["assessments"].append({
            "assessment_id": "asmt-002",
            "regulation": "HIPAA",
            "display_name": "HIPAA Security Rule",
            "compliance_score": 81.0,
            "passed_controls": 60,
            "failed_controls": 10,
            "total_controls": 70,
        })
        write_assessment_summaries(sample_payload)

        rows = list(table_store["AssessmentSummary"].values())
        assert len(rows) == 2
        regulations = {r["Regulation"] for r in rows}
        assert regulations == {"NIST 800-53", "HIPAA"}

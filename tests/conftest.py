"""Shared test fixtures."""

import pytest


@pytest.fixture
def sample_payload() -> dict:
    """Return a valid sample posture payload for testing."""
    return {
        "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "agency_id": "dept-of-education",
        "timestamp": "2026-02-26T14:30:00+00:00",
        "label_coverage_pct": 72.5,
        "unlabeled_sensitive_count": 143,
        "dlp_incidents_30d": 15,
        "dlp_incidents_60d": 28,
        "dlp_incidents_90d": 45,
        "external_sharing_count": 234,
        "retention_policy_count": 8,
        "retention_coverage_pct": 65.0,
        "insider_risk_high": 2,
        "insider_risk_medium": 5,
        "insider_risk_low": 12,
        "insider_risk_total": 19,
        "label_taxonomy": [
            {"label_id": "lbl-001", "label_name": "Public", "parent_label_id": None, "tooltip": ""},
            {"label_id": "lbl-002", "label_name": "Confidential - PII", "parent_label_id": "lbl-003", "tooltip": ""},
            {"label_id": "lbl-003", "label_name": "Restricted - FERPA", "parent_label_id": None, "tooltip": ""},
        ],
        "compliance_score_current": 72.0,
        "compliance_score_max": 100.0,
        "assessments": [
            {
                "assessment_id": "asmt-001",
                "regulation": "NIST 800-53",
                "display_name": "NIST 800-53 Rev 5",
                "compliance_score": 68.0,
                "passed_controls": 45,
                "failed_controls": 12,
                "total_controls": 57,
            },
        ],
        "improvement_actions_implemented": 20,
        "improvement_actions_planned": 15,
        "improvement_actions_not_started": 8,
        "collector_version": "1.0.0",
    }


@pytest.fixture
def sample_snapshots() -> list[dict]:
    """Return a list of agency posture snapshot entities for testing."""
    return [
        {
            "PartitionKey": "dept-of-education",
            "RowKey": "2026-02-26T14:30:00_tenant-1",
            "ComplianceScorePct": 72.0,
            "LabelCoveragePct": 72.5,
            "DlpIncidents30d": 15,
            "ExternalSharingCount": 234,
            "InsiderRiskTotal": 19,
            "RetentionCoveragePct": 65.0,
        },
        {
            "PartitionKey": "dept-of-health",
            "RowKey": "2026-02-26T14:30:00_tenant-2",
            "ComplianceScorePct": 85.0,
            "LabelCoveragePct": 88.0,
            "DlpIncidents30d": 3,
            "ExternalSharingCount": 50,
            "InsiderRiskTotal": 2,
            "RetentionCoveragePct": 90.0,
        },
        {
            "PartitionKey": "dept-of-corrections",
            "RowKey": "2026-02-26T14:30:00_tenant-3",
            "ComplianceScorePct": 38.2,
            "LabelCoveragePct": 34.0,
            "DlpIncidents30d": 42,
            "ExternalSharingCount": 567,
            "InsiderRiskTotal": 31,
            "RetentionCoveragePct": 25.0,
        },
    ]

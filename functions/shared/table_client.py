"""
Azure Table Storage client for reading and writing posture data.

Tables:
- AgencyPostureSnapshot: per-agency metrics snapshot
- LabelNormalizationMap: sensitivity label → standard tier mapping
- AssessmentSummary: Compliance Manager assessments per agency

Uses Managed Identity by default (recommended).
Falls back to account key if STORAGE_ACCOUNT_KEY is set.
"""

import json
import logging
from datetime import datetime, timezone

from azure.data.tables import TableClient, TableServiceClient
from azure.identity import DefaultAzureCredential

from shared.config import get_settings

log = logging.getLogger(__name__)

_service_client: TableServiceClient | None = None


def _get_service_client() -> TableServiceClient:
    global _service_client
    if _service_client is None:
        settings = get_settings()
        if settings.STORAGE_ACCOUNT_KEY:
            _service_client = TableServiceClient(
                endpoint=settings.table_endpoint,
                credential=settings.STORAGE_ACCOUNT_KEY,
            )
        else:
            _service_client = TableServiceClient(
                endpoint=settings.table_endpoint,
                credential=DefaultAzureCredential(),
            )
    return _service_client


def _get_table(table_name: str) -> TableClient:
    return _get_service_client().get_table_client(table_name)


# ── Write Operations ───────────────────────────────────────────────


def write_posture_snapshot(payload: dict, normalized_labels: list[dict]) -> None:
    """Write an agency posture snapshot to AgencyPostureSnapshot table.

    PartitionKey: agency_id
    RowKey: {timestamp}_{tenant_id}
    """
    table = _get_table("AgencyPostureSnapshot")

    entity = {
        "PartitionKey": payload["agency_id"],
        "RowKey": f"{payload['timestamp']}_{payload['tenant_id']}",
        "TenantId": payload["tenant_id"],
        "LabelCoveragePct": payload["label_coverage_pct"],
        "UnlabeledSensitiveCount": payload["unlabeled_sensitive_count"],
        "DlpIncidents30d": payload["dlp_incidents_30d"],
        "DlpIncidents60d": payload["dlp_incidents_60d"],
        "DlpIncidents90d": payload["dlp_incidents_90d"],
        "ExternalSharingCount": payload["external_sharing_count"],
        "RetentionPolicyCount": payload["retention_policy_count"],
        "RetentionCoveragePct": payload["retention_coverage_pct"],
        "InsiderRiskHigh": payload["insider_risk_high"],
        "InsiderRiskMedium": payload["insider_risk_medium"],
        "InsiderRiskLow": payload["insider_risk_low"],
        "InsiderRiskTotal": payload["insider_risk_total"],
        "ComplianceScoreCurrent": payload["compliance_score_current"],
        "ComplianceScoreMax": payload["compliance_score_max"],
        "ComplianceScorePct": (
            round(payload["compliance_score_current"] / payload["compliance_score_max"] * 100, 2)
            if payload["compliance_score_max"] > 0
            else 0.0
        ),
        "ImprovementActionsImplemented": payload["improvement_actions_implemented"],
        "ImprovementActionsPlanned": payload["improvement_actions_planned"],
        "ImprovementActionsNotStarted": payload["improvement_actions_not_started"],
        "CollectorVersion": payload["collector_version"],
    }

    table.upsert_entity(entity)
    log.info("Wrote posture snapshot: %s / %s", payload["agency_id"], payload["tenant_id"])

    # Write label normalization map entries
    _write_label_map(payload["agency_id"], payload["tenant_id"], normalized_labels)


def _write_label_map(agency_id: str, tenant_id: str, labels: list[dict]) -> None:
    """Write label normalization map entries to LabelNormalizationMap table."""
    table = _get_table("LabelNormalizationMap")

    for label in labels:
        entity = {
            "PartitionKey": agency_id,
            "RowKey": f"{tenant_id}_{label['label_id']}",
            "LabelName": label.get("label_name", ""),
            "ParentLabelId": label.get("parent_label_id", ""),
            "NormalizedTier": label.get("normalized_tier", "Internal"),
            "LastSeen": datetime.now(timezone.utc).isoformat(),
        }
        table.upsert_entity(entity)


def write_assessment_summaries(payload: dict) -> None:
    """Write assessment summaries to AssessmentSummary table."""
    table = _get_table("AssessmentSummary")

    for assessment in payload.get("assessments", []):
        total = assessment.get("total_controls", 0)
        passed = assessment.get("passed_controls", 0)

        entity = {
            "PartitionKey": payload["agency_id"],
            "RowKey": f"{payload['tenant_id']}_{assessment['assessment_id']}",
            "Regulation": assessment.get("regulation", ""),
            "DisplayName": assessment.get("display_name", ""),
            "ComplianceScore": assessment.get("compliance_score", 0),
            "PassedControls": passed,
            "FailedControls": assessment.get("failed_controls", 0),
            "TotalControls": total,
            "PassRate": round(passed / total * 100, 2) if total > 0 else 0.0,
            "ImprovementActionsImplemented": payload.get("improvement_actions_implemented", 0),
            "ImprovementActionsPlanned": payload.get("improvement_actions_planned", 0),
            "ImprovementActionsNotStarted": payload.get("improvement_actions_not_started", 0),
            "SnapshotDate": payload["timestamp"][:10],
        }
        table.upsert_entity(entity)

    log.info("Wrote %d assessment summaries for %s", len(payload.get("assessments", [])), payload["agency_id"])


# ── Read Operations ────────────────────────────────────────────────


def read_latest_snapshots_all_agencies() -> list[dict]:
    """Read the latest posture snapshot for each agency.

    Returns the most recent snapshot per PartitionKey (agency_id).
    """
    table = _get_table("AgencyPostureSnapshot")
    all_entities = list(table.list_entities())

    # Group by agency, take latest (highest RowKey = most recent timestamp)
    latest: dict[str, dict] = {}
    for entity in all_entities:
        pk = entity["PartitionKey"]
        if pk not in latest or entity["RowKey"] > latest[pk]["RowKey"]:
            latest[pk] = dict(entity)

    return list(latest.values())


def read_assessment_summaries(agency_filter: str | None = None) -> list[dict]:
    """Read assessment summaries, optionally filtered by agency."""
    table = _get_table("AssessmentSummary")

    if agency_filter:
        entities = table.query_entities(f"PartitionKey eq '{agency_filter}'")
    else:
        entities = table.list_entities()

    return [dict(e) for e in entities]

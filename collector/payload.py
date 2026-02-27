"""
JSON payload builder and schema for the posture snapshot.

All metrics are native from Purview and Compliance Manager —
no custom risk scores or invented formulas.

The payload includes TenantID, AgencyID, and Timestamp as required.
No PII, document content, or user identities are included.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

# JSON Schema for validation (used by both collector and Function App)
PAYLOAD_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "PurviewPosturePayload",
    "type": "object",
    "required": [
        "tenant_id",
        "agency_id",
        "timestamp",
        "label_coverage_pct",
        "unlabeled_sensitive_count",
        "dlp_incidents_30d",
        "dlp_incidents_60d",
        "dlp_incidents_90d",
        "external_sharing_count",
        "retention_policy_count",
        "retention_coverage_pct",
        "insider_risk_high",
        "insider_risk_medium",
        "insider_risk_low",
        "insider_risk_total",
        "label_taxonomy",
        "compliance_score_current",
        "compliance_score_max",
        "assessments",
        "improvement_actions_implemented",
        "improvement_actions_planned",
        "improvement_actions_not_started",
        "collector_version",
    ],
    "properties": {
        "tenant_id": {"type": "string", "pattern": "^[0-9a-fA-F-]{36}$"},
        "agency_id": {"type": "string", "minLength": 1, "maxLength": 64},
        "timestamp": {"type": "string", "format": "date-time"},
        "label_coverage_pct": {"type": "number", "minimum": 0, "maximum": 100},
        "unlabeled_sensitive_count": {"type": "integer", "minimum": 0},
        "dlp_incidents_30d": {"type": "integer", "minimum": 0},
        "dlp_incidents_60d": {"type": "integer", "minimum": 0},
        "dlp_incidents_90d": {"type": "integer", "minimum": 0},
        "external_sharing_count": {"type": "integer", "minimum": 0},
        "retention_policy_count": {"type": "integer", "minimum": 0},
        "retention_coverage_pct": {"type": "number", "minimum": 0, "maximum": 100},
        "insider_risk_high": {"type": "integer", "minimum": 0},
        "insider_risk_medium": {"type": "integer", "minimum": 0},
        "insider_risk_low": {"type": "integer", "minimum": 0},
        "insider_risk_total": {"type": "integer", "minimum": 0},
        "label_taxonomy": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["label_id", "label_name"],
                "properties": {
                    "label_id": {"type": "string"},
                    "label_name": {"type": "string"},
                    "parent_label_id": {"type": ["string", "null"]},
                    "tooltip": {"type": "string"},
                },
            },
        },
        "compliance_score_current": {"type": "number", "minimum": 0},
        "compliance_score_max": {"type": "number", "minimum": 0},
        "assessments": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["assessment_id", "regulation", "display_name", "compliance_score"],
                "properties": {
                    "assessment_id": {"type": "string"},
                    "regulation": {"type": "string"},
                    "display_name": {"type": "string"},
                    "compliance_score": {"type": "number"},
                    "passed_controls": {"type": "integer"},
                    "failed_controls": {"type": "integer"},
                    "total_controls": {"type": "integer"},
                },
            },
        },
        "improvement_actions_implemented": {"type": "integer", "minimum": 0},
        "improvement_actions_planned": {"type": "integer", "minimum": 0},
        "improvement_actions_not_started": {"type": "integer", "minimum": 0},
        "collector_version": {"type": "string"},
    },
    "additionalProperties": False,
}


@dataclass
class PurviewPosturePayload:
    """Posture snapshot payload — metadata only, no PII."""

    tenant_id: str
    agency_id: str
    timestamp: str

    # Purview metrics (native from Graph API)
    label_coverage_pct: float
    unlabeled_sensitive_count: int
    dlp_incidents_30d: int
    dlp_incidents_60d: int
    dlp_incidents_90d: int
    external_sharing_count: int
    retention_policy_count: int
    retention_coverage_pct: float
    insider_risk_high: int
    insider_risk_medium: int
    insider_risk_low: int
    insider_risk_total: int
    label_taxonomy: list[dict] = field(default_factory=list)

    # Compliance Manager metrics (native scores, no custom formulas)
    compliance_score_current: float = 0.0
    compliance_score_max: float = 0.0
    assessments: list[dict] = field(default_factory=list)
    improvement_actions_implemented: int = 0
    improvement_actions_planned: int = 0
    improvement_actions_not_started: int = 0

    # Collector metadata
    collector_version: str = "1.0.0"

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

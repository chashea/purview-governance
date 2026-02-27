"""
Label normalization — maps tenant-specific sensitivity label names
to standard tiers: Public | Internal | Confidential | Restricted.

No custom risk scoring. All Purview and Compliance Manager scores
are passed through as-is from the source APIs.
"""

import logging
import statistics
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# Keyword mappings for label tier classification
# Priority order: Restricted > Confidential > Internal > Public
TIER_KEYWORDS: dict[str, list[str]] = {
    "Restricted": [
        "restricted", "highly confidential", "secret", "top secret",
        "classified", "cui", "cjis", "ferpa", "hipaa", "itar",
        "criminal justice", "law enforcement",
    ],
    "Confidential": [
        "confidential", "sensitive", "moderate", "pii", "phi", "fouo",
        "for official use only", "controlled", "protected",
    ],
    "Internal": [
        "internal", "general", "organizational", "default", "low",
        "employee", "staff",
    ],
    "Public": [
        "public", "unrestricted", "open", "external", "published",
    ],
}


def normalize_label_tier(label_name: str, parent_name: str = "") -> str:
    """Map a sensitivity label name to a standard tier.

    Uses keyword matching against label name and parent label name.
    Returns the highest-priority matching tier, defaulting to 'Internal'.
    """
    combined = f"{parent_name} {label_name}".lower()
    for tier in ("Restricted", "Confidential", "Internal", "Public"):
        if any(kw in combined for kw in TIER_KEYWORDS[tier]):
            return tier
    return "Internal"  # Conservative default


def normalize_labels(taxonomy: list[dict]) -> list[dict]:
    """Normalize all labels in a taxonomy to standard tiers.

    Adds a 'normalized_tier' field to each label dict if not already present.
    """
    for label in taxonomy:
        if not label.get("normalized_tier"):
            label["normalized_tier"] = normalize_label_tier(
                label.get("label_name", ""),
                label.get("parent_label_name", ""),
            )
    return taxonomy


def compute_statewide_aggregates(snapshots: list[dict]) -> dict:
    """Compute simple statewide rollup metrics from agency snapshots.

    All values are direct aggregations of native Purview/Compliance Manager
    scores — no custom risk formulas.

    Args:
        snapshots: List of latest agency posture snapshot entities.

    Returns:
        Aggregated metrics dictionary.
    """
    if not snapshots:
        return {}

    compliance_scores = [s.get("ComplianceScorePct", 0) for s in snapshots]
    label_coverages = [s.get("LabelCoveragePct", 0) for s in snapshots]

    return {
        "TotalAgencies": len(snapshots),
        "AvgComplianceScore": round(statistics.mean(compliance_scores), 2),
        "MedianComplianceScore": round(statistics.median(compliance_scores), 2),
        "MinComplianceScore": round(min(compliance_scores), 2),
        "MaxComplianceScore": round(max(compliance_scores), 2),
        "LowestComplianceAgency": min(snapshots, key=lambda s: s.get("ComplianceScorePct", 0)).get("PartitionKey", ""),
        "AvgLabelCoverage": round(statistics.mean(label_coverages), 2),
        "TotalDlpIncidents30d": sum(s.get("DlpIncidents30d", 0) for s in snapshots),
        "TotalExternalSharing": sum(s.get("ExternalSharingCount", 0) for s in snapshots),
        "TotalInsiderRiskAlerts": sum(s.get("InsiderRiskTotal", 0) for s in snapshots),
        "SnapshotDate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }

"""Tests for the label normalizer and statewide aggregates."""

import sys
import os

# Add functions/ to path so shared modules can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "functions"))

from shared.normalizer import compute_statewide_aggregates, normalize_label_tier, normalize_labels


class TestNormalizeLabelTier:
    def test_public_label(self):
        assert normalize_label_tier("Public") == "Public"

    def test_internal_label(self):
        assert normalize_label_tier("Internal") == "Internal"

    def test_confidential_label(self):
        assert normalize_label_tier("Confidential") == "Confidential"

    def test_confidential_pii_sublabel(self):
        assert normalize_label_tier("PII", parent_name="Confidential") == "Confidential"

    def test_restricted_ferpa(self):
        assert normalize_label_tier("Restricted - FERPA") == "Restricted"

    def test_restricted_cjis(self):
        assert normalize_label_tier("CJIS Data") == "Restricted"

    def test_restricted_hipaa(self):
        assert normalize_label_tier("HIPAA Protected") == "Restricted"

    def test_fouo_maps_to_confidential(self):
        assert normalize_label_tier("For Official Use Only") == "Confidential"

    def test_unknown_defaults_to_internal(self):
        """Unknown labels should conservatively default to Internal."""
        assert normalize_label_tier("Some Custom Label") == "Internal"

    def test_case_insensitive(self):
        assert normalize_label_tier("PUBLIC") == "Public"
        assert normalize_label_tier("RESTRICTED") == "Restricted"


class TestNormalizeLabels:
    def test_adds_normalized_tier(self):
        taxonomy = [
            {"label_id": "1", "label_name": "Public"},
            {"label_id": "2", "label_name": "Confidential"},
            {"label_id": "3", "label_name": "Restricted - FERPA"},
        ]
        result = normalize_labels(taxonomy)
        assert result[0]["normalized_tier"] == "Public"
        assert result[1]["normalized_tier"] == "Confidential"
        assert result[2]["normalized_tier"] == "Restricted"

    def test_preserves_existing_tier(self):
        taxonomy = [
            {"label_id": "1", "label_name": "Custom", "normalized_tier": "Confidential"},
        ]
        result = normalize_labels(taxonomy)
        assert result[0]["normalized_tier"] == "Confidential"


class TestStatewideAggregates:
    def test_computes_aggregates(self, sample_snapshots):
        result = compute_statewide_aggregates(sample_snapshots)
        assert result["TotalAgencies"] == 3
        assert result["AvgComplianceScore"] == pytest.approx(65.07, abs=0.1)
        assert result["TotalDlpIncidents30d"] == 60
        assert result["LowestComplianceAgency"] == "dept-of-corrections"

    def test_empty_snapshots_returns_empty(self):
        assert compute_statewide_aggregates([]) == {}

    def test_single_agency(self):
        snapshots = [
            {
                "PartitionKey": "single-agency",
                "ComplianceScorePct": 80.0,
                "LabelCoveragePct": 75.0,
                "DlpIncidents30d": 5,
                "ExternalSharingCount": 10,
                "InsiderRiskTotal": 1,
            }
        ]
        result = compute_statewide_aggregates(snapshots)
        assert result["TotalAgencies"] == 1
        assert result["AvgComplianceScore"] == 80.0
        assert result["LowestComplianceAgency"] == "single-agency"

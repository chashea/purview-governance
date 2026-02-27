"""Integration tests for the statewide aggregate computation pipeline.

Tests the end-to-end flow:
  write_posture_snapshot → read_latest_snapshots_all_agencies
  → compute_statewide_aggregates
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "functions"))

from shared.normalizer import compute_statewide_aggregates
from shared.table_client import (
    read_assessment_summaries,
    read_latest_snapshots_all_agencies,
    write_assessment_summaries,
    write_posture_snapshot,
)


def _minimal_payload(agency_id: str, tenant_id: str, compliance_score: float, dlp_30d: int = 5) -> dict:
    """Return a minimal valid payload for seeding the table store."""
    return {
        "agency_id": agency_id,
        "tenant_id": tenant_id,
        "timestamp": "2026-02-26T00:00:00+00:00",
        "label_coverage_pct": 70.0,
        "unlabeled_sensitive_count": 10,
        "dlp_incidents_30d": dlp_30d,
        "dlp_incidents_60d": dlp_30d * 2,
        "dlp_incidents_90d": dlp_30d * 3,
        "external_sharing_count": 20,
        "retention_policy_count": 3,
        "retention_coverage_pct": 60.0,
        "insider_risk_high": 0,
        "insider_risk_medium": 1,
        "insider_risk_low": 2,
        "insider_risk_total": 3,
        "label_taxonomy": [],
        "compliance_score_current": compliance_score,
        "compliance_score_max": 100.0,
        "assessments": [],
        "improvement_actions_implemented": 5,
        "improvement_actions_planned": 3,
        "improvement_actions_not_started": 2,
        "collector_version": "1.0.0",
    }


class TestReadLatestSnapshots:
    def test_empty_table_returns_empty_list(self, table_store):
        result = read_latest_snapshots_all_agencies()
        assert result == []

    def test_reads_single_agency_snapshot(self, sample_payload, table_store):
        write_posture_snapshot(sample_payload, [])

        result = read_latest_snapshots_all_agencies()
        assert len(result) == 1
        assert result[0]["PartitionKey"] == "dept-of-education"

    def test_returns_latest_snapshot_per_agency(self, table_store):
        """When an agency has multiple snapshots, only the most recent is returned."""
        older = _minimal_payload("agency-a", "aaaaaaaa-0000-0000-0000-000000000000", 50.0)
        older["timestamp"] = "2026-01-01T00:00:00+00:00"
        older["compliance_score_current"] = 50.0

        newer = _minimal_payload("agency-a", "aaaaaaaa-0000-0000-0000-000000000000", 75.0)
        newer["timestamp"] = "2026-02-26T00:00:00+00:00"
        newer["compliance_score_current"] = 75.0

        write_posture_snapshot(older, [])
        write_posture_snapshot(newer, [])

        result = read_latest_snapshots_all_agencies()
        assert len(result) == 1
        assert result[0]["ComplianceScoreCurrent"] == 75.0

    def test_returns_one_row_per_agency(self, table_store):
        """Two different agencies each return their own latest snapshot."""
        write_posture_snapshot(
            _minimal_payload("agency-a", "aaaaaaaa-0000-0000-0000-000000000000", 80.0), []
        )
        write_posture_snapshot(
            _minimal_payload("agency-b", "bbbbbbbb-0000-0000-0000-000000000000", 60.0), []
        )

        result = read_latest_snapshots_all_agencies()
        assert len(result) == 2
        agencies = {r["PartitionKey"] for r in result}
        assert agencies == {"agency-a", "agency-b"}

    def test_snapshot_fields_round_trip(self, sample_payload, table_store):
        """Fields written by write_posture_snapshot must survive the read round-trip."""
        write_posture_snapshot(sample_payload, [])

        result = read_latest_snapshots_all_agencies()
        row = result[0]
        assert row["LabelCoveragePct"] == 72.5
        assert row["DlpIncidents30d"] == 15
        assert row["ExternalSharingCount"] == 234
        assert row["InsiderRiskTotal"] == 19
        assert row["RetentionCoveragePct"] == 65.0
        assert row["ComplianceScorePct"] == pytest.approx(72.0, abs=0.01)


class TestAggregatePipeline:
    """Full write → read → compute_statewide_aggregates flow."""

    def test_single_agency_aggregates(self, sample_payload, table_store):
        write_posture_snapshot(sample_payload, [])

        snapshots = read_latest_snapshots_all_agencies()
        agg = compute_statewide_aggregates(snapshots)

        assert agg["TotalAgencies"] == 1
        assert agg["AvgComplianceScore"] == pytest.approx(72.0, abs=0.01)
        assert agg["TotalDlpIncidents30d"] == 15

    def test_two_agency_averages(self, table_store):
        write_posture_snapshot(
            _minimal_payload("edu", "aaaaaaaa-0000-0000-0000-000000000000", 72.0, dlp_30d=15), []
        )
        write_posture_snapshot(
            _minimal_payload("health", "bbbbbbbb-0000-0000-0000-000000000000", 88.0, dlp_30d=3), []
        )

        snapshots = read_latest_snapshots_all_agencies()
        agg = compute_statewide_aggregates(snapshots)

        assert agg["TotalAgencies"] == 2
        assert agg["AvgComplianceScore"] == pytest.approx(80.0, abs=0.01)
        assert agg["TotalDlpIncidents30d"] == 18

    def test_identifies_lowest_compliance_agency(self, table_store):
        for agency, score in [("high", 90.0), ("low", 35.0), ("mid", 70.0)]:
            write_posture_snapshot(
                _minimal_payload(agency, f"{'aa' * 4}-{'bb' * 2}-{'cc' * 2}-{'dd' * 2}-{'ee' * 6}", score), []
            )

        snapshots = read_latest_snapshots_all_agencies()
        agg = compute_statewide_aggregates(snapshots)

        assert agg["LowestComplianceAgency"] == "low"

    def test_three_agency_aggregates_match_sample_snapshots(self, sample_snapshots):
        """Aggregates computed from conftest sample_snapshots should match expected values."""
        agg = compute_statewide_aggregates(sample_snapshots)

        assert agg["TotalAgencies"] == 3
        assert agg["AvgComplianceScore"] == pytest.approx(65.07, abs=0.1)
        assert agg["TotalDlpIncidents30d"] == 60
        assert agg["LowestComplianceAgency"] == "dept-of-corrections"
        assert agg["TotalExternalSharing"] == 851  # 234 + 50 + 567
        assert agg["TotalInsiderRiskAlerts"] == 52  # 19 + 2 + 31

    def test_aggregate_on_empty_store_after_write(self, table_store):
        """Verify compute_statewide_aggregates is skipped when table is empty."""
        result = read_latest_snapshots_all_agencies()
        assert result == []
        assert compute_statewide_aggregates(result) == {}

    def test_latest_snapshot_used_after_update(self, table_store):
        """After resubmitting a newer snapshot, aggregate should use the new values."""
        old = _minimal_payload("agency-a", "aaaaaaaa-0000-0000-0000-000000000000", 50.0)
        old["timestamp"] = "2026-01-01T00:00:00+00:00"
        write_posture_snapshot(old, [])

        new = _minimal_payload("agency-a", "aaaaaaaa-0000-0000-0000-000000000000", 80.0)
        new["timestamp"] = "2026-02-26T00:00:00+00:00"
        write_posture_snapshot(new, [])

        snapshots = read_latest_snapshots_all_agencies()
        agg = compute_statewide_aggregates(snapshots)

        assert agg["TotalAgencies"] == 1
        assert agg["AvgComplianceScore"] == pytest.approx(80.0, abs=0.01)


class TestReadAssessmentSummaries:
    def test_read_all_assessments(self, sample_payload, table_store):
        write_assessment_summaries(sample_payload)

        result = read_assessment_summaries()
        assert len(result) == 1
        assert result[0]["Regulation"] == "NIST 800-53"

    def test_filter_by_agency(self, sample_payload, table_store):
        write_assessment_summaries(sample_payload)

        other = dict(sample_payload)
        other["agency_id"] = "dept-of-health"
        other["tenant_id"] = "b2c3d4e5-f6a7-8901-bcde-f12345678901"
        write_assessment_summaries(other)

        result = read_assessment_summaries(agency_filter="dept-of-education")
        assert len(result) == 1
        assert result[0]["PartitionKey"] == "dept-of-education"

    def test_filter_returns_empty_for_unknown_agency(self, sample_payload, table_store):
        write_assessment_summaries(sample_payload)

        result = read_assessment_summaries(agency_filter="nonexistent-agency")
        assert result == []

    def test_pass_rate_computed_correctly(self, sample_payload, table_store):
        write_assessment_summaries(sample_payload)

        result = read_assessment_summaries()
        # 45 passed / 57 total = 78.95%
        assert result[0]["PassRate"] == pytest.approx(78.95, abs=0.01)

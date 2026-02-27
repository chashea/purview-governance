"""Tests for the payload builder and schema validation."""

import jsonschema
import pytest

from collector.payload import PAYLOAD_SCHEMA, PurviewPosturePayload


class TestPayloadSchema:
    def test_valid_payload_passes_schema(self, sample_payload):
        """A valid payload should pass JSON schema validation."""
        jsonschema.validate(instance=sample_payload, schema=PAYLOAD_SCHEMA)

    def test_missing_required_field_fails(self, sample_payload):
        """Missing a required field should raise ValidationError."""
        del sample_payload["tenant_id"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=sample_payload, schema=PAYLOAD_SCHEMA)

    def test_invalid_tenant_id_format_fails(self, sample_payload):
        """Non-UUID tenant_id should fail."""
        sample_payload["tenant_id"] = "not-a-uuid"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=sample_payload, schema=PAYLOAD_SCHEMA)

    def test_negative_count_fails(self, sample_payload):
        """Negative counts should fail."""
        sample_payload["dlp_incidents_30d"] = -1
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=sample_payload, schema=PAYLOAD_SCHEMA)

    def test_coverage_over_100_fails(self, sample_payload):
        """Coverage percentage over 100 should fail."""
        sample_payload["label_coverage_pct"] = 101.0
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=sample_payload, schema=PAYLOAD_SCHEMA)

    def test_additional_properties_rejected(self, sample_payload):
        """Extra fields should be rejected (additionalProperties: false)."""
        sample_payload["extra_field"] = "not allowed"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=sample_payload, schema=PAYLOAD_SCHEMA)


class TestPurviewPosturePayload:
    def test_to_dict_roundtrip(self):
        """Payload dataclass should serialize to dict correctly."""
        payload = PurviewPosturePayload(
            tenant_id="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            agency_id="test-agency",
            timestamp="2026-02-26T14:30:00+00:00",
            label_coverage_pct=72.5,
            unlabeled_sensitive_count=100,
            dlp_incidents_30d=10,
            dlp_incidents_60d=20,
            dlp_incidents_90d=30,
            external_sharing_count=50,
            retention_policy_count=5,
            retention_coverage_pct=60.0,
            insider_risk_high=1,
            insider_risk_medium=2,
            insider_risk_low=3,
            insider_risk_total=6,
            compliance_score_current=72.0,
            compliance_score_max=100.0,
        )
        d = payload.to_dict()
        assert d["tenant_id"] == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        assert d["agency_id"] == "test-agency"
        assert d["dlp_incidents_30d"] == 10
        assert d["collector_version"] == "1.0.0"

    def test_now_iso_returns_string(self):
        """now_iso should return a valid ISO 8601 timestamp."""
        ts = PurviewPosturePayload.now_iso()
        assert isinstance(ts, str)
        assert "T" in ts

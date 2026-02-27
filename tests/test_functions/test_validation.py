"""Tests for the ingestion validation logic."""

import base64
import hashlib
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "functions"))

from shared.validation import PAYLOAD_SCHEMA, _extract_thumbprint


class TestExtractThumbprint:
    def test_extracts_sha1_thumbprint(self):
        """Should extract SHA-1 thumbprint from base64-encoded cert bytes."""
        # Create a dummy cert (just random bytes for testing)
        cert_bytes = b"dummy-certificate-content-for-testing"
        cert_b64 = base64.b64encode(cert_bytes).decode()

        expected = hashlib.sha1(cert_bytes).hexdigest().upper()
        result = _extract_thumbprint(cert_b64)

        assert result == expected
        assert len(result) == 40  # SHA-1 hex = 40 chars


class TestPayloadSchemaValidation:
    def test_schema_has_required_fields(self):
        """Schema should require all expected fields."""
        required = PAYLOAD_SCHEMA["required"]
        assert "tenant_id" in required
        assert "agency_id" in required
        assert "timestamp" in required
        assert "compliance_score_current" in required
        assert "compliance_score_max" in required
        assert "label_taxonomy" in required
        assert "assessments" in required
        assert "collector_version" in required

    def test_schema_disallows_additional_properties(self):
        """Schema should reject extra fields."""
        assert PAYLOAD_SCHEMA.get("additionalProperties") is False

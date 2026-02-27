"""
Request validation for the ingestion endpoint.

Validates:
1. Client certificate thumbprint (mTLS via X-ARR-ClientCert header)
2. Tenant ID against allow-list
3. JSON body against the payload schema
"""

import base64
import hashlib
import logging

import azure.functions as func
import jsonschema

from shared.config import get_settings

log = logging.getLogger(__name__)

# Import the canonical payload schema from collector (shared definition)
PAYLOAD_SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "PurviewPosturePayload",
    "type": "object",
    "required": [
        "tenant_id", "agency_id", "timestamp",
        "label_coverage_pct", "unlabeled_sensitive_count",
        "dlp_incidents_30d", "dlp_incidents_60d", "dlp_incidents_90d",
        "external_sharing_count",
        "retention_policy_count", "retention_coverage_pct",
        "insider_risk_high", "insider_risk_medium", "insider_risk_low", "insider_risk_total",
        "label_taxonomy",
        "compliance_score_current", "compliance_score_max",
        "assessments",
        "improvement_actions_implemented", "improvement_actions_planned",
        "improvement_actions_not_started",
        "collector_version",
    ],
    "properties": {
        "tenant_id": {"type": "string", "pattern": "^[0-9a-fA-F-]{36}$"},
        "agency_id": {"type": "string", "minLength": 1, "maxLength": 64},
        "timestamp": {"type": "string"},
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
        "label_taxonomy": {"type": "array"},
        "compliance_score_current": {"type": "number", "minimum": 0},
        "compliance_score_max": {"type": "number", "minimum": 0},
        "assessments": {"type": "array"},
        "improvement_actions_implemented": {"type": "integer", "minimum": 0},
        "improvement_actions_planned": {"type": "integer", "minimum": 0},
        "improvement_actions_not_started": {"type": "integer", "minimum": 0},
        "collector_version": {"type": "string"},
    },
    "additionalProperties": False,
}


def _extract_thumbprint(client_cert_b64: str) -> str:
    """Extract SHA-1 thumbprint from the base64-encoded client certificate.

    Azure App Service forwards the client cert in X-ARR-ClientCert as base64 DER.
    """
    cert_bytes = base64.b64decode(client_cert_b64)
    thumbprint = hashlib.sha1(cert_bytes).hexdigest().upper()
    return thumbprint


def validate_ingestion_request(req: func.HttpRequest) -> dict:
    """Validate the inbound ingestion request.

    Checks:
    1. Client certificate thumbprint against allow-list
    2. JSON body against schema
    3. Tenant ID against allow-list

    Returns:
        Parsed and validated payload dictionary.

    Raises:
        ValueError: If any validation check fails.
    """
    settings = get_settings()

    # 1. Certificate validation (skip if no thumbprints configured — dev mode)
    if settings.allowed_thumbprints:
        client_cert_header = req.headers.get("X-ARR-ClientCert", "")
        if not client_cert_header:
            raise ValueError("Missing client certificate (X-ARR-ClientCert header)")

        thumbprint = _extract_thumbprint(client_cert_header)
        if thumbprint not in settings.allowed_thumbprints:
            log.warning("Rejected certificate thumbprint: %s", thumbprint)
            raise ValueError(f"Certificate thumbprint not in allow-list: {thumbprint}")

        log.info("Certificate validated: %s", thumbprint)

    # 2. Parse JSON body
    try:
        payload = req.get_json()
    except ValueError:
        raise ValueError("Invalid JSON body")

    # 3. JSON schema validation
    try:
        jsonschema.validate(instance=payload, schema=PAYLOAD_SCHEMA)
    except jsonschema.ValidationError as e:
        raise ValueError(f"Schema validation failed: {e.message}")

    # 4. Tenant allow-list (skip if no tenants configured — dev mode)
    if settings.allowed_tenants:
        tenant_id = payload["tenant_id"]
        if tenant_id not in settings.allowed_tenants:
            log.warning("Rejected tenant not in allow-list: %s", tenant_id)
            raise ValueError(f"Tenant {tenant_id} not in allow-list")

    return payload

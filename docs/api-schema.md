# API Schema — Function App Endpoints

Base URL: `https://<function-app-name>.azurewebsites.net`

All endpoints require a Function key (`x-functions-key` header or `code` query parameter).

---

## POST /api/ingest

Receive a posture snapshot from the per-tenant collector.

### Authentication
- Function key (required)
- Client certificate via mTLS (optional, if mTLS enabled)

### Request Headers
```
Content-Type: application/json
x-functions-key: <function-key>
X-ARR-ClientCert: <base64-encoded-client-cert>  (if mTLS enabled)
```

### Request Body
```json
{
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
    {
      "label_id": "lbl-001",
      "label_name": "Public",
      "parent_label_id": null,
      "tooltip": "Unrestricted information"
    },
    {
      "label_id": "lbl-002",
      "label_name": "Confidential - PII",
      "parent_label_id": "lbl-003",
      "tooltip": "Contains personally identifiable information"
    }
  ],

  "compliance_score_current": 72.0,
  "compliance_score_max": 100.0,

  "assessments": [
    {
      "assessment_id": "asmt-001",
      "regulation": "NIST 800-53",
      "display_name": "NIST 800-53 Rev 5 Assessment",
      "compliance_score": 68.0,
      "passed_controls": 45,
      "failed_controls": 12,
      "total_controls": 57
    }
  ],

  "improvement_actions_implemented": 20,
  "improvement_actions_planned": 15,
  "improvement_actions_not_started": 8,

  "collector_version": "1.0.0"
}
```

### Response — 200 OK
```json
{
  "status": "ok",
  "agency_id": "dept-of-education",
  "compliance_score": 72.0
}
```

### Response — 400 Bad Request
```json
{
  "error": "Schema validation failed: 'tenant_id' is a required property"
}
```

### Response — 500 Internal Server Error
```json
{
  "error": "Internal server error"
}
```

---

## POST /api/ai/query

Query the AI executive agent for analysis of aggregated posture data.

### Request Body
```json
{
  "question": "Which agencies have the lowest compliance scores and what should they prioritize?",
  "agency_id": "dept-of-education"  // optional — scope to one agency
}
```

### Response — 200 OK
```json
{
  "answer": "## Statewide Compliance Analysis\n\nThe average compliance score across 12 reporting agencies is 64.3%...",
  "model": "gpt-4o",
  "usage": {
    "prompt_tokens": 2450,
    "completion_tokens": 512
  }
}
```

---

## POST /api/report

Generate an executive summary report in PDF or PPTX format.

### Request Body
```json
{
  "format": "pdf",          // "pdf" or "pptx"
  "agency_id": null          // optional — scope to one agency
}
```

### Response — 200 OK

Binary file download with appropriate Content-Type header:
- PDF: `application/pdf`
- PPTX: `application/vnd.openxmlformats-officedocument.presentationml.presentation`

Response headers include:
```
Content-Disposition: attachment; filename=executive-summary.pdf
```

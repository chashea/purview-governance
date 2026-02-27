# Architecture — Purview Governance Solution

## Overview

Multi-tenant, metadata-only governance solution for M365 GCC (standard) customers. Aggregates Purview and Compliance Manager metrics across agencies, provides AI-driven executive insights, and visualizes compliance posture in Grafana. All Azure resources run in Azure Commercial.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TENANT ONBOARDING                                    │
│                                                                             │
│  1. Register multi-tenant app in home tenant (one-time)                    │
│  2. Generate admin consent URL per customer tenant                         │
│  3. Customer Global Admin clicks URL → signs in → grants read-only perms   │
│                                                                             │
│  Permissions granted (all Application-type, read-only):                    │
│  • InformationProtectionPolicy.Read.All                                    │
│  • SecurityEvents.Read.All                                                  │
│  • Reports.Read.All                                                         │
│  • ComplianceManager.Read.All                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CUSTOMER GCC TENANTS (M365 GCC Standard)               │
│                                                                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐                   │
│  │  Agency A      │  │  Agency B      │  │  Agency C      │  ... N          │
│  │  Tenant        │  │  Tenant        │  │  Tenant        │                 │
│  │ ► Purview      │  │ ► Purview      │  │ ► Purview      │                 │
│  │ ► DLP Policies │  │ ► DLP Policies │  │ ► DLP Policies │                 │
│  │ ► Compliance   │  │ ► Compliance   │  │ ► Compliance   │                 │
│  │   Manager      │  │   Manager      │  │   Manager      │                 │
│  │ ► Insider Risk │  │ ► Insider Risk │  │ ► Insider Risk │                 │
│  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘                   │
└──────────┼──────────────────┼──────────────────┼────────────────────────────┘
           │                  │                  │
           │  Microsoft Graph API (graph.microsoft.com)
           │  Certificate-based auth via MSAL (multi-tenant app)
           │  METADATA ONLY — no content, no PII
           ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  PER-TENANT METADATA COLLECTOR (Python CLI)                 │
│                                                                             │
│  For each consented tenant:                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │ auth.py          → MSAL cert auth to target tenant              │        │
│  │                    (cert fetched from Key Vault at runtime)     │        │
│  │ purview_client   → GET label taxonomy, coverage %, DLP counts,  │        │
│  │                    external sharing, retention gaps,             │        │
│  │                    insider risk trend (counts only)              │        │
│  │ compliance_client→ GET compliance score, assessments,           │        │
│  │                    improvement actions                          │        │
│  │ payload.py       → Build JSON (tenant_id, agency_id, timestamp, │        │
│  │                    all native metrics — no invented scores)     │        │
│  │ submit.py        → HTTPS POST to Function App                  │        │
│  └─────────────────────────────────────────────────────────────────┘        │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      │ HTTPS POST + Function key / mTLS
                                      │ JSON payload (metadata only)
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│              AZURE FUNCTION APP (Commercial: *.azurewebsites.net)          │
│                                                                             │
│  ┌──────────────────────────────┐  ┌──────────────────────────────┐        │
│  │ ingest_posture (HTTP)        │  │ compute_aggregates (Timer)    │        │
│  │ • Validate cert thumbprint   │  │ • Daily 6:00 AM UTC           │        │
│  │   (optional — skipped in dev)│  │                               │        │
│  │ • Check tenant allow-list    │  │ • Read all agency snapshots   │        │
│  │ • Validate JSON schema       │  │ • Compute simple rollups of   │        │
│  │ • Normalize labels to tiers  │  │   native scores               │        │
│  │ • Write to Table Storage     │  │                               │        │
│  └──────────────────────────────┘  └──────────────────────────────┘        │
│  ┌──────────────────────────────┐  ┌──────────────────────────────┐        │
│  │ ai_executive (HTTP)          │  │ generate_report (HTTP)        │        │
│  │ • Read aggregated metrics    │  │ • Generate PDF or PPTX        │        │
│  │ • Call Azure OpenAI          │  │ • AI-generated summary +      │        │
│  │ • Return AI insights         │  │   metrics tables              │        │
│  └──────────────────────────────┘  └──────────────────────────────┘        │
│                                                                             │
│  Auth: Managed Identity → Storage, Key Vault, OpenAI                       │
└────────────┬──────────────────────┬─────────────────────┬───────────────────┘
             │                      │                     │
             ▼                      ▼                     ▼
┌────────────────────┐  ┌─────────────────────┐  ┌──────────────────────┐
│ Azure Table Storage│  │ Azure Key Vault      │  │ Azure OpenAI         │
│ *.table.core.      │  │ *.vault.azure.net    │  │ *.openai.azure.com   │
│   windows.net      │  │                     │  │                      │
│                    │  │ • Collector cert    │  │ • GPT-4o deployment  │
│                    │  │   (auto-generated)  │  │                      │
│ Tables:            │  │ • Tenant allow-list │  │ • Metadata context   │
│ • AgencyPosture    │  └─────────────────────┘  │   only (no PII)      │
│   Snapshot         │                           └──────────────────────┘
│ • LabelNormal-     │
│   izationMap       │
│ • AssessmentSummary│
└─────────┬──────────┘
          │
          │ Grafana Infinity datasource
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GRAFANA DASHBOARD (Azure Managed Grafana)                │
│                    Entra ID SSO + Azure RBAC (Admin/Editor/Viewer)          │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────┐           │
│  │ Compliance Score │  │ Label Coverage   │  │ DLP Incidents    │           │
│  │ (native gauge)   │  │ (bar per agency) │  │ (30/60/90d table)│           │
│  └─────────────────┘  └─────────────────┘  └──────────────────┘           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────┐           │
│  │ External Sharing │  │ Retention Gaps   │  │ Assessment Status│           │
│  │ (bar per agency) │  │ (bar per agency) │  │ (per regulation) │           │
│  └─────────────────┘  └─────────────────┘  └──────────────────┘           │
│  ┌──────────────────────────────────────────────────────────────┐           │
│  │ AI Executive Agent Panel + Executive Summary Download        │           │
│  └──────────────────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────────────┘
```

## End-to-End Workflow

### 1. Onboard
Register the multi-tenant app in your home tenant. Generate admin consent URLs for each customer tenant. Customer Global Admin clicks the URL, signs in, and approves read-only permissions. No app registration is created in the customer tenant.

### 2. Collect
The Python CLI collector authenticates to each consented tenant using certificate-based MSAL auth. The certificate is stored in and fetched from Azure Key Vault at runtime — no local cert files required. It pulls metadata from Purview (labels, DLP counts, sharing, retention, insider risk trends) and Compliance Manager (scores, assessments, improvement actions) via the Microsoft Graph API.

### 3. Ingest
The collector POSTs the JSON payload to the Azure Function App using the function key for authentication. The Function optionally validates a client certificate thumbprint (if `ALLOWED_CERT_THUMBPRINTS` is configured), checks the tenant ID against the allow-list, and validates the JSON schema. Invalid requests are rejected with detailed error messages.

### 4. Normalize
Sensitivity labels are normalized from tenant-specific names to standard tiers (Public / Internal / Confidential / Restricted) using keyword matching. All Purview and Compliance Manager scores are stored as-is — no custom risk formulas.

### 5. Aggregate
A daily timer trigger reads all agency snapshots and computes simple statewide rollups: average compliance score, total DLP incidents, average label coverage, etc. These are direct aggregations of native scores.

### 6. Analyze
The AI executive agent reads aggregated metrics from Table Storage, builds a context payload (metadata only), and sends it to Azure OpenAI for analysis. The agent identifies lowest-scoring agencies and generates actionable recommendations.

### 7. Visualize
Grafana dashboards display all native scores: compliance score gauges, label coverage bars, DLP incident tables, external sharing, retention gaps, and assessment status by regulation. An AI chat panel allows interactive queries.

### 8. Report
On-demand PDF or PPTX executive summaries combine statewide metrics, per-agency detail tables, and AI-generated analysis. Reports include a footer stating "metadata only — no PII."

## Data Flow Summary

| Source | Data Collected | NOT Collected |
|---|---|---|
| Purview Labels | Label names, coverage %, tier classification | Document content, file bodies |
| DLP | Incident counts (30/60/90d) | Policy match content, matched data |
| External Sharing | Sharing event counts | Recipient identities, file names |
| Retention | Policy counts, coverage % | Retained document content |
| Insider Risk | Alert counts by severity | User names, case details |
| Compliance Manager | Scores, assessments, improvement actions | Control implementation details |

## Azure Resources

| Resource | Service | Endpoint |
|---|---|---|
| Function App | Azure Functions (Consumption, Linux, Python 3.11) | *.azurewebsites.net |
| Table Storage | Azure Storage (StorageV2, Standard_LRS) | *.table.core.windows.net |
| Key Vault | Azure Key Vault (Standard, RBAC) | *.vault.azure.net |
| OpenAI | Azure OpenAI Service (S0, GPT-4o) | *.openai.azure.com |
| Grafana | Azure Managed Grafana (Standard) | Entra ID SSO |
| Monitoring | Application Insights + Log Analytics | — |

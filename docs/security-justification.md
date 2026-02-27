# Security Justification — Purview Governance Solution

*Prepared for CISO / CIO Review*

## 1. Data Classification: METADATA ONLY

This solution collects and processes **metadata exclusively**. At no point does any component access, transmit, or store:

- Email content, document content, or file bodies
- User identities, names, UPNs, or email addresses
- Insider Risk case details or user attributions
- DLP policy match content or matched sensitive information types
- SharePoint file contents or OneDrive files

### What IS Collected (All Counts/Percentages)

| Data Point | Type | Example |
|---|---|---|
| Label coverage | Percentage | "72.5% of items labeled" |
| Unlabeled sensitive items | Count | "143 unlabeled sensitive items" |
| DLP incidents | Counts by window | "15 incidents in last 30 days" |
| External sharing | Count | "234 externally shared items" |
| Retention policy coverage | Count + percentage | "8 policies, 65% coverage" |
| Insider risk alerts | Counts by severity | "2 high, 5 medium, 12 low" |
| Label taxonomy | Names only | "Confidential", "Restricted" |
| Compliance score | Native score | "72 out of 100" |
| Assessment results | Pass/fail counts | "45 passed, 12 failed, 57 total" |
| Improvement actions | Counts by status | "20 implemented, 15 planned" |

## 2. Zero Trust Architecture

| Principle | Implementation |
|---|---|
| **Verify explicitly** | Certificate-based mTLS authentication on every ingestion request. Tenant allow-list validated per request. JSON schema enforcement rejects malformed payloads. Entra ID SSO required for Grafana access. |
| **Least privilege** | Multi-tenant app requests only read-only permissions: `InformationProtectionPolicy.Read.All`, `SecurityEvents.Read.All`, `Reports.Read.All`, `ComplianceManager.Read.All`. Managed Identity for Function App with scoped RBAC (Table Data Contributor on one storage account, Secrets User on one vault, OpenAI User on one resource). Grafana roles (Admin/Editor/Viewer) assigned via Entra ID groups. |
| **Assume breach** | Private endpoints supported for Storage, Key Vault, and OpenAI. Azure Monitor logging on all ingestion events. No secrets in code or environment variables (Managed Identity throughout). Certificate rotation supported via Key Vault. |

## 3. Authentication & Authorization

### Tenant Graph API Access
- **Method**: Certificate-based app-only authentication (MSAL)
- **No client secrets**: Only X.509 certificate credentials
- **Multi-tenant app**: Single registration, each customer admin explicitly consents
- **Scope**: Read-only application permissions with admin consent

### Function App Ingestion
- **mTLS**: Client certificate required on ingestion endpoint
- **Thumbprint validation**: Only pre-approved certificate thumbprints accepted
- **Tenant allow-list**: Only pre-approved tenant IDs accepted
- **Schema validation**: JSON body must conform to strict schema

### Function App → Azure Services
- **Managed Identity**: System-assigned identity with RBAC roles
- No connection strings or API keys in code

### Grafana Dashboard
- **Entra ID SSO**: No local accounts, no anonymous access
- **Azure RBAC**: Grafana Admin / Editor / Viewer roles assigned to Entra ID groups
- **API keys disabled**: No programmatic access without Entra ID auth

## 4. App Registration Permissions

| Permission | Type | Justification |
|---|---|---|
| `InformationProtectionPolicy.Read.All` | Application | Read label taxonomy and policy coverage |
| `SecurityEvents.Read.All` | Application | Read DLP and Insider Risk alert counts |
| `Reports.Read.All` | Application | Read usage reports (sharing, label adoption) |
| `ComplianceManager.Read.All` | Application | Read compliance scores and assessments |

All permissions are **Application** type (app-only, no user context) with **admin consent** required. No delegated permissions. No write permissions.

## 5. No Custom Risk Scoring

All scores surfaced in the solution are **native from Microsoft Purview and Compliance Manager**:

- Compliance Score (0-100) — directly from Compliance Manager API
- Assessment pass rates — directly from assessment controls
- DLP incident counts — directly from security alerts API
- Label coverage percentages — directly from Purview reports

**No custom risk formulas, weighted scoring, or invented metrics.** Statewide aggregates are simple rollups (averages, sums) of native scores.

## 6. Audit Trail

Every ingestion event is logged to Azure Monitor / Application Insights with:

- Timestamp
- Tenant ID and Agency ID
- Certificate thumbprint used
- Validation result (pass/fail with reason)
- Native compliance score received

Logs are retained per Log Analytics workspace retention policy (default 90 days, configurable to 730 days).

## 7. AI Processing

- Azure OpenAI Service deployed in Azure Commercial
- Only **aggregated metadata** (counts, percentages, scores) is sent as context
- No PII, document content, or user identities are included in AI prompts
- AI-generated summaries reference only the metrics provided in context
- Model: GPT-4o via Azure OpenAI (data is not used for model training per Azure OpenAI data privacy terms)

## 8. Network Security

| Control | Status |
|---|---|
| HTTPS-only (TLS 1.2+) | Enforced on all resources |
| Private endpoints | Supported for Storage, Key Vault, OpenAI (Bicep module included) |
| VNet integration | Supported for Function App |
| mTLS | Supported on Function App ingestion endpoint |
| FTPS | Disabled on Function App |
| Public blob access | Disabled on Storage Account |

## 9. Compliance Framework Alignment

| Framework | Relevant Controls |
|---|---|
| NIST 800-53 | AC-3 (Access Enforcement), AU-2 (Auditable Events), SC-8 (Transmission Confidentiality), SC-28 (Protection of Information at Rest) |
| CJIS | 5.5 (Access Control), 5.4 (Auditing and Accountability) |
| FERPA | Metadata-only; no student records accessed |
| HIPAA | Metadata-only; no PHI accessed. BAA coverage via Azure |

# Purview Governance — GCC-Compliant AI Governance Solution

Multi-tenant, metadata-only governance solution for **M365 GCC (standard)** State & Local / Higher Education customers. Aggregates Microsoft Purview and Compliance Manager metrics across agencies, provides AI-driven executive insights, and visualizes compliance posture in Grafana.

**All scores are native from Microsoft Purview and Compliance Manager — no custom risk formulas.**

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fchashea%2Fpurview-governance%2Fmain%2Finfra%2Fazuredeploy.json)

> **Note:** Update the Deploy to Azure URL above with your repository's raw URL to `infra/azuredeploy.json`. Generate the ARM template from Bicep: `az bicep build --file infra/main.bicep --outfile infra/azuredeploy.json`

## What It Does

- **Collects metadata** from each GCC tenant: label coverage, DLP incident counts, external sharing, retention gaps, insider risk trends, Compliance Manager scores and assessments
- **No content or PII** — only counts, percentages, and scores leave tenant boundaries
- **Stores** normalized metrics in Azure Table Storage
- **Visualizes** compliance posture in Grafana with interactive dashboards
- **AI analysis** via Azure OpenAI for executive insights and recommendations
- **Generates** PDF/PPTX executive summaries for CISO/CIO briefings

## Architecture

```
GCC Tenants → Collector (Python CLI) → Azure Function App → Table Storage → Grafana
                  ↓                          ↓
           Graph API (cert auth)      Azure OpenAI (AI insights)
```

See [docs/architecture.md](docs/architecture.md) for the full architecture diagram and end-to-end workflow.

## Quick Start

### 1. Deploy Infrastructure

Click **Deploy to Azure** above, or use the CLI:

```bash
az group create --name rg-purview-governance --location eastus
az deployment group create \
  --resource-group rg-purview-governance \
  --template-file infra/main.bicep \
  --parameters infra/parameters/prod.bicepparam
```

### 2. Register Multi-Tenant App

Create an app registration in your home tenant with multi-tenant support and certificate auth. See [docs/deployment-guide.md](docs/deployment-guide.md#post-deployment-register-multi-tenant-app).

### 3. Onboard Customer Tenants

```bash
python onboarding/consent_url_generator.py \
  --client-id <APP_CLIENT_ID> \
  --tenant-id <CUSTOMER_TENANT_ID>
```

Send the URL to the customer's Global Admin. See [docs/onboarding-guide.md](docs/onboarding-guide.md).

### 4. Collect Metadata

```bash
pip install -e .
purview-collect --tenant-id <TENANT_ID> --agency-id dept-of-education
```

### 5. View Dashboard

Open Azure Managed Grafana, install the Infinity datasource plugin, and import `grafana/dashboards/purview-governance.json`.

## Project Structure

```
purview-governance/
├── collector/         # Per-tenant metadata collector (Python CLI)
├── onboarding/        # Admin consent URL generator + instructions
├── functions/         # Azure Function App (ingestion, AI agent, reports)
├── grafana/           # Dashboard JSON + provisioning configs
├── infra/             # Bicep IaC + ARM template for Deploy to Azure
├── docs/              # Architecture, security, deployment, API docs
└── tests/             # Unit and integration tests
```

## Documentation

| Document | Description |
|---|---|
| [Architecture](docs/architecture.md) | Full diagram, end-to-end workflow, data flow |
| [Security Justification](docs/security-justification.md) | Zero Trust mapping, metadata-only proof — CISO-ready |
| [Deployment Guide](docs/deployment-guide.md) | Deploy to Azure button + manual CLI steps |
| [API Schema](docs/api-schema.md) | Function App endpoints and request/response schemas |
| [Onboarding Guide](docs/onboarding-guide.md) | End-to-end tenant onboarding walkthrough |
| [Sample Payload](docs/sample-payload.json) | Example JSON payload with realistic data |
| [Sample Executive Summary](docs/sample-executive-summary.md) | Example AI-generated CISO briefing |

## Security

- **Metadata only** — no document content, PII, or user identities
- **Certificate auth** (MSAL) — no client secrets
- **mTLS** supported between collector and Function App
- **Tenant allow-list** enforced on every ingestion
- **Managed Identity** for all Azure service-to-service calls
- **Entra ID SSO + RBAC** for Grafana access control
- **All native scores** — no custom risk formulas or invented metrics

See [docs/security-justification.md](docs/security-justification.md) for the full CISO-ready security justification.

## License

Proprietary — internal use only.

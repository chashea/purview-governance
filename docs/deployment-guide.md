# Deployment Guide

## Prerequisites

- Azure subscription (Azure Commercial)
- Azure CLI installed (`az --version`)
- Bicep CLI (`az bicep install`)
- Python 3.11+
- Azure Functions Core Tools (`func --version`)
- Owner or Contributor role on the target Azure subscription

## Option A: Deploy to Azure Button (One-Click)

Click the button in the project README to deploy all infrastructure via the Azure Portal:

1. Click **Deploy to Azure** in the README
2. The Azure Portal opens the custom deployment blade
3. Fill in parameters:
   - **Resource Group**: Create new or select existing
   - **Region**: Select Azure region (e.g., East US)
   - **Environment Name**: `dev` or `prod`
   - **Allowed Tenant IDs**: Comma-separated GCC tenant GUIDs
   - **Allowed Cert Thumbprints**: Comma-separated SHA-1 thumbprints
   - **OpenAI Deployment Model**: Default `gpt-4o`
   - **Grafana Admin/Editor/Viewer Group IDs**: Entra ID group object IDs
4. Click **Review + Create** → **Create**
5. Wait for deployment to complete (~5-10 minutes)

## Option B: Azure CLI / Bicep

```bash
# 1. Login
az login

# 2. Create resource group
az group create --name rg-purview-governance --location eastus

# 3. Deploy infrastructure
az deployment group create \
  --resource-group rg-purview-governance \
  --template-file infra/main.bicep \
  --parameters infra/parameters/prod.bicepparam \
  --parameters deployerObjectId=$(az ad signed-in-user show --query id -o tsv)

# 4. Note the outputs
az deployment group show \
  --resource-group rg-purview-governance \
  --name main \
  --query properties.outputs
```

## Post-Deployment: Deploy Function App Code

### Option 1: Zip Deploy

```bash
cd functions
pip install -r requirements.txt --target .python_packages/lib/site-packages
func azure functionapp publish <FUNCTION_APP_NAME> --python
```

### Option 2: GitHub Actions

Create `.github/workflows/deploy-functions.yml`:

```yaml
name: Deploy Function App
on:
  push:
    branches: [main]
    paths: ['functions/**']

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r functions/requirements.txt --target functions/.python_packages/lib/site-packages
      - uses: Azure/functions-action@v1
        with:
          app-name: ${{ vars.FUNCTION_APP_NAME }}
          package: functions
          publish-profile: ${{ secrets.AZURE_FUNCTIONAPP_PUBLISH_PROFILE }}
```

## Post-Deployment: Enable mTLS (Optional)

```bash
az webapp config set \
  --resource-group rg-purview-governance \
  --name <FUNCTION_APP_NAME> \
  --client-cert-enabled true \
  --client-cert-mode Required
```

## Post-Deployment: Register Multi-Tenant App

1. Go to **Entra ID > App registrations > New registration**
2. Name: `Purview Governance Collector`
3. Supported account types: **Accounts in any organizational directory** (multi-tenant)
4. Register
5. Go to **Certificates & secrets > Certificates > Upload certificate**
   - Upload the public key (.cer or .pem without private key)
6. Go to **API permissions > Add a permission > Microsoft Graph > Application permissions**
   - Add: `InformationProtectionPolicy.Read.All`, `SecurityEvents.Read.All`, `Reports.Read.All`, `ComplianceManager.Read.All`
7. Click **Grant admin consent** for your home tenant
8. Note the **Application (client) ID** — this is the `CLIENT_ID` for the collector

## Post-Deployment: Onboard Customer Tenants

```bash
python onboarding/consent_url_generator.py \
  --client-id <APP_CLIENT_ID> \
  --tenant-id <CUSTOMER_TENANT_ID>
```

Send the generated URL to the customer's Global Admin. See [onboarding guide](onboarding-guide.md) for full instructions.

## Post-Deployment: Add Tenant to Allow-List

```bash
az functionapp config appsettings set \
  --resource-group rg-purview-governance \
  --name <FUNCTION_APP_NAME> \
  --settings ALLOWED_TENANT_IDS="tenant1-guid,tenant2-guid"
```

## Post-Deployment: First Collection Run

```bash
# Set up .env from .env.example
cp .env.example .env
# Edit .env with your CLIENT_ID, CERTIFICATE_PATH, etc.

# Run collector
purview-collect --tenant-id <CUSTOMER_TENANT_ID> --agency-id dept-of-education
```

## Post-Deployment: Configure Grafana

1. Open Azure Managed Grafana from the Azure Portal
2. Install the **Infinity** datasource plugin
3. Add datasource:
   - Type: Infinity
   - Auth: Azure AD
   - Azure Cloud: Azure Public
   - Storage Account: from deployment outputs
4. Import the dashboard from `grafana/dashboards/purview-governance.json`

## Regenerate ARM Template

If you modify the Bicep files:

```bash
az bicep build --file infra/main.bicep --outfile infra/azuredeploy.json
```

## Checklist

- [ ] Resource group created
- [ ] Bicep / ARM deployment completed
- [ ] Function App code deployed
- [ ] Multi-tenant app registered in home tenant
- [ ] Certificate uploaded to app registration
- [ ] API permissions granted with admin consent
- [ ] Customer tenant(s) consented via admin consent URL
- [ ] Tenant IDs added to Function App allow-list
- [ ] Grafana Infinity plugin installed and datasource configured
- [ ] Dashboard imported
- [ ] Entra ID groups assigned Grafana RBAC roles
- [ ] First collection run successful

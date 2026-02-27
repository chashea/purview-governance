# Tenant Onboarding Guide

Step-by-step instructions for onboarding a customer M365 GCC tenant to the Purview Governance solution.

## Prerequisites

| Requirement | Details |
|---|---|
| Customer tenant type | M365 GCC (standard) |
| Admin role required | Global Administrator or Privileged Role Administrator |
| Multi-tenant app | Already registered in your home tenant (see [Deployment Guide](deployment-guide.md)) |
| Function App | Already deployed and running |

## Step 1: Generate the Admin Consent URL

Run the consent URL generator:

```bash
python onboarding/consent_url_generator.py \
  --client-id <YOUR_APP_CLIENT_ID> \
  --tenant-id <CUSTOMER_TENANT_ID>
```

This produces a URL like:
```
https://login.microsoftonline.com/{tenant-id}/adminconsent?client_id={app-id}&redirect_uri=https://portal.azure.com
```

For multiple tenants at once, create a CSV file:

```csv
tenant_id,agency_name
aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa,Department of Education
bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb,Department of Health
```

```bash
python onboarding/consent_url_generator.py \
  --client-id <YOUR_APP_CLIENT_ID> \
  --tenants-file tenants.csv
```

## Step 2: Send the URL to the Customer Admin

Send the admin consent URL along with the following information:

**Email template:**

> Subject: Purview Governance — Admin Consent Required
>
> To enable compliance monitoring for your tenant, please:
>
> 1. Click the consent URL below
> 2. Sign in with your Global Administrator account
> 3. Review the permissions and click **Accept**
>
> **Consent URL:** [paste URL]
>
> **Permissions being granted (all read-only):**
> - Sensitivity label taxonomy and coverage statistics
> - DLP and Insider Risk alert counts (no user details)
> - Usage reports — label adoption and sharing counts
> - Compliance Manager scores and assessments
>
> **What is NOT accessed:**
> - No document content or email bodies
> - No user identities or names
> - No Insider Risk case details
> - No DLP match content
>
> This consent can be revoked at any time from Entra ID > Enterprise Applications.

## Step 3: Customer Admin Approves

The customer admin will:

1. Click the consent URL
2. Sign in with their Global Admin credentials
3. See the permission request screen
4. Click **Accept**
5. Be redirected to the Azure Portal

**What happens in the background:**
- A service principal for your app is created in the customer's tenant
- The approved permissions are granted to that service principal
- No app registration is created — only a service principal

## Step 4: Verify Consent Was Granted

### From the customer side
The admin can verify in **Entra ID > Enterprise Applications**:
- Search for your app name
- Confirm the permissions tab shows the 4 granted permissions

### From the collector side
Run a dry-run collection to test authentication:

```bash
purview-collect \
  --tenant-id <CUSTOMER_TENANT_ID> \
  --agency-id <AGENCY_NAME> \
  --dry-run
```

A successful dry run confirms:
- Certificate authentication works against the customer tenant
- Graph API calls return data
- The payload builds correctly

## Step 5: Add Tenant to Function App Allow-List

```bash
# Get current list
az functionapp config appsettings list \
  --resource-group rg-purview-governance \
  --name <FUNCTION_APP_NAME> \
  --query "[?name=='ALLOWED_TENANT_IDS'].value" -o tsv

# Update with new tenant
az functionapp config appsettings set \
  --resource-group rg-purview-governance \
  --name <FUNCTION_APP_NAME> \
  --settings ALLOWED_TENANT_IDS="existing-id-1,existing-id-2,NEW_TENANT_ID"
```

## Step 6: First Production Collection

```bash
purview-collect \
  --tenant-id <CUSTOMER_TENANT_ID> \
  --agency-id <AGENCY_NAME>
```

Verify the data appears in:
- Azure Table Storage (AgencyPostureSnapshot table)
- Grafana dashboard (new agency should appear in all panels)

## Revoking Access

If a customer needs to revoke consent:

1. Go to **Entra ID > Enterprise Applications**
2. Find the Purview Governance app
3. Click **Properties > Delete**

This immediately revokes all permissions. The collector will no longer be able to authenticate to that tenant.

Also remove the tenant from the Function App allow-list:

```bash
az functionapp config appsettings set \
  --resource-group rg-purview-governance \
  --name <FUNCTION_APP_NAME> \
  --settings ALLOWED_TENANT_IDS="remaining-tenant-ids"
```

## Troubleshooting

| Issue | Solution |
|---|---|
| Consent URL shows "need admin approval" | Ensure the user has Global Admin or Privileged Role Admin role |
| MSAL auth fails after consent | Verify the certificate thumbprint matches the one uploaded to the app registration |
| Graph API returns 403 | Permissions may need time to propagate (up to 15 minutes). Also verify admin consent was granted (not just user consent) |
| Function App rejects payload | Check that the tenant ID is in the allow-list and the certificate thumbprint is approved |

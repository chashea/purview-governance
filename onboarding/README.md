# Tenant Onboarding Guide

This document explains how to onboard a customer M365 GCC tenant so the Purview Governance solution can collect metadata from it.

## Prerequisites

- The customer tenant must be an **M365 GCC (standard)** tenant
- A **Global Administrator** or **Privileged Role Administrator** in the customer tenant must approve the consent
- The multi-tenant app registration must already exist in your home tenant (see [Deployment Guide](../docs/deployment-guide.md))

## How It Works

The solution uses a **multi-tenant Entra ID app registration** with admin consent. No app registration is created in the customer tenant. Instead:

1. You generate an admin consent URL for the customer tenant
2. The customer's Global Admin clicks the URL and signs in
3. They review and approve the read-only permissions
4. The app is now authorized to read metadata from that tenant

## Permissions Requested

All permissions are **Application** type (app-only, no user context) and **read-only**:

| Permission | What It Reads |
|---|---|
| `InformationProtectionPolicy.Read.All` | Sensitivity label taxonomy and policy coverage |
| `SecurityEvents.Read.All` | DLP incident counts and Insider Risk alert counts (no user details) |
| `Reports.Read.All` | Usage reports — label adoption, external sharing counts |
| `ComplianceManager.Read.All` | Compliance Manager scores, assessments, improvement actions |

**No content, documents, emails, or user identities are accessed.**

## Step 1: Generate the Admin Consent URL

### Single tenant:

```bash
python onboarding/consent_url_generator.py \
  --client-id YOUR_APP_CLIENT_ID \
  --tenant-id CUSTOMER_TENANT_ID
```

### Multiple tenants from a CSV:

Create a `tenants.csv` file:

```csv
tenant_id,agency_name
xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx,Department of Education
yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy,Department of Health
```

```bash
python onboarding/consent_url_generator.py \
  --client-id YOUR_APP_CLIENT_ID \
  --tenants-file tenants.csv
```

## Step 2: Send the URL to the Customer Admin

Send the generated URL to the customer tenant's Global Administrator along with this message template:

> **Subject:** Purview Governance — Admin Consent Required
>
> To enable compliance monitoring for your tenant, please click the link below and sign in with your Global Administrator account. You will be asked to approve read-only access to compliance metadata (label coverage, DLP incident counts, compliance scores). No document content or user data will be accessed.
>
> **Consent URL:** `[paste URL here]`
>
> **Permissions being granted:**
> - Sensitivity label taxonomy (read-only)
> - DLP and Insider Risk alert counts (read-only, no user details)
> - Usage reports — label adoption and sharing counts (read-only)
> - Compliance Manager scores and assessments (read-only)

## Step 3: Verify Consent Was Granted

After the admin approves, verify the app appears in the customer tenant:

1. The admin can check **Entra ID > Enterprise Applications** — the app should appear with the granted permissions
2. From the collector, run a test auth to confirm token acquisition works:

```bash
purview-collect --tenant-id CUSTOMER_TENANT_ID --dry-run
```

## Step 4: Add Tenant to the Allow-List

Add the customer's tenant ID to the Function App's `ALLOWED_TENANT_IDS` setting:

```bash
az functionapp config appsettings set \
  --resource-group rg-purview-governance \
  --name purview-gov-func \
  --settings ALLOWED_TENANT_IDS="existing-id,NEW_TENANT_ID"
```

## Step 5: First Collection Run

```bash
purview-collect --tenant-id CUSTOMER_TENANT_ID --agency-id dept-of-education
```

The collector will authenticate, pull metadata, and submit it to the Function App for storage.

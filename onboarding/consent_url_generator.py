"""
Generate admin consent URLs for customer GCC tenants.

Usage:
    python consent_url_generator.py --client-id <APP_CLIENT_ID> --tenant-id <CUSTOMER_TENANT_ID>
    python consent_url_generator.py --client-id <APP_CLIENT_ID> --tenants-file tenants.csv

The generated URL is sent to the customer tenant's Global Administrator.
They click it, sign in, and approve the read-only permissions for the
multi-tenant app. No app registration is needed in the customer tenant.
"""

import argparse
import csv
import sys
from urllib.parse import quote, urlencode


# M365 GCC standard uses commercial Azure AD endpoints
AUTHORITY_BASE = "https://login.microsoftonline.com"

# Default redirect after consent (Azure Portal)
DEFAULT_REDIRECT_URI = "https://portal.azure.com"


def build_consent_url(
    client_id: str,
    tenant_id: str,
    redirect_uri: str = DEFAULT_REDIRECT_URI,
) -> str:
    """Build the admin consent URL for a specific customer tenant.

    Args:
        client_id: The Application (client) ID of the multi-tenant app registration.
        tenant_id: The customer tenant's Azure AD tenant ID (GUID).
        redirect_uri: Where to redirect after consent is granted.

    Returns:
        The full admin consent URL.
    """
    params = urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
    })
    return f"{AUTHORITY_BASE}/{tenant_id}/adminconsent?{params}"


def main():
    parser = argparse.ArgumentParser(
        description="Generate admin consent URLs for customer GCC tenants."
    )
    parser.add_argument(
        "--client-id",
        required=True,
        help="Application (client) ID of the multi-tenant app registration",
    )
    parser.add_argument(
        "--tenant-id",
        help="Single customer tenant ID to generate URL for",
    )
    parser.add_argument(
        "--tenants-file",
        help="CSV file with columns: tenant_id, agency_name. Generates URLs for all rows.",
    )
    parser.add_argument(
        "--redirect-uri",
        default=DEFAULT_REDIRECT_URI,
        help=f"Redirect URI after consent (default: {DEFAULT_REDIRECT_URI})",
    )
    args = parser.parse_args()

    if not args.tenant_id and not args.tenants_file:
        parser.error("Provide either --tenant-id or --tenants-file")

    if args.tenant_id:
        url = build_consent_url(args.client_id, args.tenant_id, args.redirect_uri)
        print(f"\nAdmin Consent URL for tenant {args.tenant_id}:\n")
        print(f"  {url}\n")
        print("Send this URL to the customer tenant's Global Administrator.")
        print("They will sign in and approve the following read-only permissions:")
        print("  - InformationProtectionPolicy.Read.All")
        print("  - SecurityEvents.Read.All")
        print("  - Reports.Read.All")
        print("  - ComplianceManager.Read.All")
        return

    if args.tenants_file:
        with open(args.tenants_file, newline="") as f:
            reader = csv.DictReader(f)
            print(f"\nAdmin Consent URLs (app: {args.client_id}):\n")
            print(f"{'Agency':<40} {'Tenant ID':<40} URL")
            print("-" * 140)
            for row in reader:
                tid = row.get("tenant_id", "").strip()
                name = row.get("agency_name", "").strip()
                if not tid:
                    continue
                url = build_consent_url(args.client_id, tid, args.redirect_uri)
                print(f"{name:<40} {tid:<40} {url}")
        print()


if __name__ == "__main__":
    main()

"""
Certificate-based app-only authentication for Microsoft Graph (GCC).

Uses MSAL ConfidentialClientApplication with certificate credentials.
The multi-tenant app authenticates to each target tenant by setting
the authority to https://login.microsoftonline.com/{target_tenant_id}.
"""

import logging

import msal

from collector.config import CollectorSettings

log = logging.getLogger(__name__)

# Cache MSAL app instances per tenant to reuse token cache
_app_cache: dict[str, msal.ConfidentialClientApplication] = {}


def get_graph_token(settings: CollectorSettings) -> str:
    """Acquire an app-only Graph API token using certificate credentials.

    Returns:
        The access token string.

    Raises:
        RuntimeError: If MSAL authentication fails.
    """
    cache_key = f"{settings.TENANT_ID}:{settings.CLIENT_ID}"

    if cache_key not in _app_cache:
        with open(settings.CERTIFICATE_PATH, "r") as f:
            private_key = f.read()

        authority = f"{settings.login_authority}/{settings.TENANT_ID}"
        log.info("Creating MSAL app for tenant=%s authority=%s", settings.TENANT_ID, authority)

        _app_cache[cache_key] = msal.ConfidentialClientApplication(
            client_id=settings.CLIENT_ID,
            authority=authority,
            client_credential={
                "thumbprint": settings.CERTIFICATE_THUMBPRINT,
                "private_key": private_key,
            },
        )

    app = _app_cache[cache_key]
    result = app.acquire_token_for_client(scopes=[settings.graph_scope])

    if "access_token" not in result:
        error_desc = result.get("error_description", result.get("error", "Unknown error"))
        raise RuntimeError(f"MSAL authentication failed for tenant {settings.TENANT_ID}: {error_desc}")

    log.debug("Token acquired for tenant=%s (expires_in=%s)", settings.TENANT_ID, result.get("expires_in"))
    return result["access_token"]

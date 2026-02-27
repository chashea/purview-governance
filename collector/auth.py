"""
Certificate-based app-only authentication for Microsoft Graph (GCC).

Uses MSAL ConfidentialClientApplication with certificate credentials.
The multi-tenant app authenticates to each target tenant by setting
the authority to https://login.microsoftonline.com/{target_tenant_id}.

Certificate source (in priority order):
1. Azure Key Vault  — set KEY_VAULT_URL + CERTIFICATE_NAME in .env
2. Local PEM file   — set CERTIFICATE_PATH + CERTIFICATE_THUMBPRINT in .env
"""

import base64
import logging

import msal

from collector.config import CollectorSettings

log = logging.getLogger(__name__)

# Cache MSAL app instances per tenant to reuse token cache
_app_cache: dict[str, msal.ConfidentialClientApplication] = {}


def _get_cert_from_key_vault(key_vault_url: str, cert_name: str) -> tuple[str, str]:
    """Fetch a certificate from Azure Key Vault.

    Key Vault stores the cert and private key together as a secret. This
    function retrieves them and returns (private_key_pem, sha1_thumbprint).

    Supports both PKCS#12 (PFX) and PEM content types.

    Args:
        key_vault_url: e.g. https://<vault>.vault.azure.net/
        cert_name: Name of the certificate in Key Vault

    Returns:
        Tuple of (private_key_pem, thumbprint) where thumbprint is 40-char hex.
    """
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.serialization import pkcs12

    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=key_vault_url, credential=credential)

    log.info("Fetching certificate '%s' from Key Vault %s", cert_name, key_vault_url)
    secret = client.get_secret(cert_name)
    content_type = (secret.properties.content_type or "").lower()

    if "pkcs12" in content_type or "x-pkcs12" in content_type:
        # Key Vault default: base64-encoded PKCS#12 bundle
        pfx_bytes = base64.b64decode(secret.value)
        private_key, cert, _ = pkcs12.load_key_and_certificates(pfx_bytes, password=None)
    else:
        # PEM: key and cert concatenated in the secret value
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        pem_bytes = secret.value.encode()
        private_key = load_pem_private_key(pem_bytes, password=None)
        cert = x509.load_pem_x509_certificate(pem_bytes)

    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    thumbprint = cert.fingerprint(hashes.SHA1()).hex().upper()
    log.info("Certificate loaded from Key Vault — thumbprint: %s", thumbprint)

    return private_key_pem, thumbprint


def get_graph_token(settings: CollectorSettings) -> str:
    """Acquire an app-only Graph API token using certificate credentials.

    Returns:
        The access token string.

    Raises:
        RuntimeError: If MSAL authentication fails or cert config is missing.
    """
    cache_key = f"{settings.TENANT_ID}:{settings.CLIENT_ID}"

    if cache_key not in _app_cache:
        if settings.use_key_vault:
            private_key, thumbprint = _get_cert_from_key_vault(
                settings.KEY_VAULT_URL, settings.CERTIFICATE_NAME
            )
        elif settings.CERTIFICATE_PATH and settings.CERTIFICATE_THUMBPRINT:
            with open(settings.CERTIFICATE_PATH, "r") as f:
                private_key = f.read()
            thumbprint = settings.CERTIFICATE_THUMBPRINT
        else:
            raise RuntimeError(
                "No certificate source configured. Set KEY_VAULT_URL + CERTIFICATE_NAME "
                "or CERTIFICATE_PATH + CERTIFICATE_THUMBPRINT in your .env."
            )

        authority = f"{settings.login_authority}/{settings.TENANT_ID}"
        log.info("Creating MSAL app for tenant=%s authority=%s", settings.TENANT_ID, authority)

        _app_cache[cache_key] = msal.ConfidentialClientApplication(
            client_id=settings.CLIENT_ID,
            authority=authority,
            client_credential={
                "thumbprint": thumbprint,
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

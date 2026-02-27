"""
Collector configuration using Pydantic Settings.

M365 GCC (standard) uses commercial Azure AD and Graph endpoints:
  - login.microsoftonline.com
  - graph.microsoft.com

GCC High (if ever needed) would use:
  - login.microsoftonline.us
  - graph.microsoft.us
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CollectorSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # GCC cloud selection: "" for GCC standard, "usgovernment" for GCC High
    NATIONAL_CLOUD: str = Field(
        default="",
        description="Leave empty for M365 GCC standard. Set to 'usgovernment' for GCC High.",
    )

    # Multi-tenant app registration (registered in home tenant)
    CLIENT_ID: str = Field(..., description="Application (client) ID of the multi-tenant app")

    # Certificate source — Key Vault (preferred) or local file
    KEY_VAULT_URL: str = Field(default="", description="Key Vault URL to fetch the collector cert from, e.g. https://<vault>.vault.azure.net/")
    CERTIFICATE_NAME: str = Field(default="", description="Name of the certificate in Key Vault")
    CERTIFICATE_PATH: str = Field(default="", description="Local path to PEM private key (fallback if KEY_VAULT_URL not set)")
    CERTIFICATE_THUMBPRINT: str = Field(default="", description="SHA-1 thumbprint (fallback if KEY_VAULT_URL not set)")

    # Target tenant for this collection run
    TENANT_ID: str = Field(..., description="Customer tenant GUID to collect from")
    AGENCY_ID: str = Field(..., description="Logical agency identifier (e.g., dept-of-education)")

    # Azure Function App ingestion endpoint
    FUNCTION_APP_URL: str = Field(..., description="e.g., https://purview-gov-func.azurewebsites.net/api/ingest")
    FUNCTION_APP_KEY: str = Field(default="", description="Function-level API key")

    # mTLS client cert for Function App (optional, for mTLS-enabled deployments)
    FUNCTION_APP_CERT_PATH: str = Field(default="", description="Client cert PEM for mTLS to Function App")
    FUNCTION_APP_CERT_KEY_PATH: str = Field(default="", description="Client cert private key for mTLS")

    @property
    def use_key_vault(self) -> bool:
        return bool(self.KEY_VAULT_URL and self.CERTIFICATE_NAME)

    @property
    def graph_base(self) -> str:
        if self.NATIONAL_CLOUD == "usgovernment":
            return "https://graph.microsoft.us"
        return "https://graph.microsoft.com"

    @property
    def login_authority(self) -> str:
        if self.NATIONAL_CLOUD == "usgovernment":
            return "https://login.microsoftonline.us"
        return "https://login.microsoftonline.com"

    @property
    def graph_scope(self) -> str:
        return f"{self.graph_base}/.default"

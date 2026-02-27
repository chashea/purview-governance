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
    CERTIFICATE_PATH: str = Field(..., description="Path to the PEM certificate file (private key)")
    CERTIFICATE_THUMBPRINT: str = Field(..., description="X509 certificate SHA-1 thumbprint")

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

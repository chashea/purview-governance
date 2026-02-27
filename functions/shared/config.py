"""
Azure Function App configuration (Azure Commercial).

All endpoints are Azure Commercial:
- Storage:       *.table.core.windows.net
- Key Vault:     *.vault.azure.net
- Azure OpenAI:  *.openai.azure.com
- Login:         login.microsoftonline.com
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FunctionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Storage (Azure Commercial)
    STORAGE_ACCOUNT_NAME: str = Field(...)
    STORAGE_ACCOUNT_KEY: str = Field(
        default="", description="Leave empty to use Managed Identity (recommended)"
    )

    # Key Vault (Azure Commercial)
    KEY_VAULT_URL: str = Field(..., description="https://<vault>.vault.azure.net/")

    # Azure OpenAI (Azure Commercial)
    AZURE_OPENAI_ENDPOINT: str = Field(..., description="https://<resource>.openai.azure.com/")
    AZURE_OPENAI_DEPLOYMENT: str = Field(default="gpt-4o")
    AZURE_OPENAI_API_VERSION: str = Field(default="2024-08-01-preview")

    # Tenant allow-list (comma-separated GUIDs)
    ALLOWED_TENANT_IDS: str = Field(default="")

    # Allowed certificate thumbprints (comma-separated)
    ALLOWED_CERT_THUMBPRINTS: str = Field(default="")

    @property
    def table_endpoint(self) -> str:
        return f"https://{self.STORAGE_ACCOUNT_NAME}.table.core.windows.net"

    @property
    def allowed_tenants(self) -> set[str]:
        return {t.strip() for t in self.ALLOWED_TENANT_IDS.split(",") if t.strip()}

    @property
    def allowed_thumbprints(self) -> set[str]:
        return {t.strip().upper() for t in self.ALLOWED_CERT_THUMBPRINTS.split(",") if t.strip()}


@lru_cache(maxsize=1)
def get_settings() -> FunctionSettings:
    return FunctionSettings()

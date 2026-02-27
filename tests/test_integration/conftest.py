"""Fixtures shared across integration tests."""

import os
import sys
from unittest.mock import MagicMock

import pytest

# Add functions/ to path so shared modules can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "functions"))

from shared.config import get_settings


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch):
    """Provide minimal valid settings for every integration test.

    Clears the lru_cache before and after so each test starts with
    a clean FunctionSettings object built from the patched env.
    """
    monkeypatch.setenv("STORAGE_ACCOUNT_NAME", "teststorage")
    monkeypatch.setenv("KEY_VAULT_URL", "https://test.vault.azure.net/")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
    monkeypatch.setenv("ALLOWED_TENANT_IDS", "")
    monkeypatch.setenv("ALLOWED_CERT_THUMBPRINTS", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def table_store():
    """Replace Azure Table Storage with an in-memory dict store.

    Patches shared.table_client._service_client so all read/write
    operations go to memory instead of Azure.

    Yields:
        dict[str, dict] — {table_name: {(PartitionKey, RowKey): entity}}
    """
    import shared.table_client as tc

    stores: dict[str, dict] = {}

    def make_table_mock(table_name: str):
        if table_name not in stores:
            stores[table_name] = {}
        data = stores[table_name]

        mock_table = MagicMock()
        mock_table.upsert_entity.side_effect = lambda e: data.update(
            {(e["PartitionKey"], e["RowKey"]): dict(e)}
        )
        mock_table.list_entities.side_effect = lambda: list(data.values())

        def query_entities(filter_expr: str):
            if "PartitionKey eq '" in filter_expr:
                pk = filter_expr.split("'")[1]
                return [v for v in data.values() if v["PartitionKey"] == pk]
            return list(data.values())

        mock_table.query_entities.side_effect = query_entities
        return mock_table

    mock_service = MagicMock()
    mock_service.get_table_client.side_effect = make_table_mock

    old_client = tc._service_client
    tc._service_client = mock_service
    yield stores
    tc._service_client = old_client

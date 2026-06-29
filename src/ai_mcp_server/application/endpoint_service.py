"""Endpoint CRUD orchestration. Shared by CLI, MCP server, and Web UI."""
from __future__ import annotations

from typing import Any

from ..models.enums import ProviderType
from ..models.schemas import EndpointDTO
from ..providers.factory import build_adapter
from ..storage import dao
from ..storage.db import connect


def add_endpoint(
    name: str,
    base_url: str,
    api_key: str,
    provider_type: ProviderType = ProviderType.OPENAI_COMPAT,
) -> EndpointDTO:
    with connect() as conn:
        existing = dao.get_endpoint_by_name(conn, name)
        if existing:
            raise ValueError(f"endpoint name {name!r} already exists")
        eid = dao.insert_endpoint(conn, name, base_url, api_key, provider_type)
        result = dao.get_endpoint_by_name(conn, name)
        assert result is not None and result.id == eid
        return result


def list_endpoints() -> list[EndpointDTO]:
    with connect() as conn:
        return dao.list_endpoints(conn)


def get_endpoint(name: str) -> EndpointDTO | None:
    with connect() as conn:
        return dao.get_endpoint_by_name(conn, name)


def remove_endpoint(name: str) -> bool:
    with connect() as conn:
        return dao.delete_endpoint(conn, name)


def build_adapter_for(name: str) -> tuple[EndpointDTO, Any]:
    """Return (endpoint, ProviderAdapter) for outbound calls."""
    with connect() as conn:
        ep = dao.get_endpoint_by_name(conn, name)
        if not ep:
            raise KeyError(f"endpoint {name!r} not found")
        api_key = dao.get_endpoint_api_key(conn, ep.id)
    return ep, build_adapter(ep.provider_type, ep.base_url, api_key)

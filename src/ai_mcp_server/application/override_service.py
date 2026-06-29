"""User override management."""
from __future__ import annotations

from typing import Any

from ..models.enums import Capability
from ..storage import dao
from ..storage.db import connect


def set_override(
    endpoint_name: str, model_id: str, key: str, value: Any
) -> None:
    with connect() as conn:
        ep = dao.get_endpoint_by_name(conn, endpoint_name)
        if not ep:
            raise KeyError(f"endpoint {endpoint_name!r} not found")
        # Validate capability key when it matches an enum
        try:
            Capability(key)
        except ValueError:
            if key != "context_length":
                # Allow arbitrary keys but warn via caller in future
                pass
        dao.upsert_override(conn, ep.id, model_id, key, value)


def delete_override(endpoint_name: str, model_id: str, key: str) -> bool:
    with connect() as conn:
        ep = dao.get_endpoint_by_name(conn, endpoint_name)
        if not ep:
            return False
        return dao.delete_override(conn, ep.id, model_id, key)


def list_overrides(endpoint_name: str, model_id: str) -> dict[str, Any]:
    with connect() as conn:
        ep = dao.get_endpoint_by_name(conn, endpoint_name)
        if not ep:
            return {}
        return dao.list_overrides(conn, ep.id, model_id)

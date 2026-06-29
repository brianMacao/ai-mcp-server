"""Capability query: list models with resolved capabilities."""
from __future__ import annotations

from typing import Any

from ..capability import resolver
from ..models.enums import Capability
from ..storage import dao
from ..storage.db import connect


def query_models(
    capability: list[Capability] | None = None,
    min_context_length: int | None = None,
    endpoint: str | None = None,
    include_unprobed: bool = True,
) -> list[dict[str, Any]]:
    with connect() as conn:
        eid: int | None = None
        if endpoint:
            ep = dao.get_endpoint_by_name(conn, endpoint)
            if not ep:
                return []
            eid = ep.id
        models = dao.list_models(conn, endpoint_id=eid)
        items = resolver.filter_models(
            conn,
            models,
            require_capabilities=capability,
            min_context_length=min_context_length,
        )
        if not include_unprobed:
            items = [
                it
                for it in items
                if any(
                    cv.get("source") == "probe"
                    for cv in it["capabilities"].values()
                )
            ]
        return items


def model_detail(endpoint: str, model_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        ep = dao.get_endpoint_by_name(conn, endpoint)
        if not ep:
            return None
        m = dao.get_model(conn, ep.id, model_id)
        if not m:
            return None
        return resolver.filter_models(conn, [m])[0]

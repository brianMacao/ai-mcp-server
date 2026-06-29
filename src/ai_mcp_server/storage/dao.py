"""Thin Data Access Object layer over SQLite tables.

All functions accept a sqlite3.Connection so the caller can compose them inside
a single transaction when needed. The application layer is responsible for
wrapping multi-statement workflows.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from ..models.enums import Capability, CapabilitySource, JobStatus, ProviderType
from ..models.schemas import (
    CapabilityValue,
    EndpointDTO,
    ModelDTO,
    ProbeJobDTO,
    ProbeResult,
)
from . import crypto

# ---------- endpoints ----------


def insert_endpoint(
    conn: sqlite3.Connection,
    name: str,
    base_url: str,
    api_key_plaintext: str,
    provider_type: ProviderType = ProviderType.OPENAI_COMPAT,
) -> int:
    cur = conn.execute(
        "INSERT INTO endpoints(name, base_url, api_key_enc, provider_type) VALUES (?,?,?,?)",
        (name, base_url, crypto.encrypt(api_key_plaintext), provider_type.value),
    )
    if cur.lastrowid is None:
        raise RuntimeError("failed to insert endpoint")
    return cur.lastrowid


def get_endpoint_by_name(conn: sqlite3.Connection, name: str) -> EndpointDTO | None:
    row = conn.execute(
        "SELECT id, name, base_url, provider_type, created_at, updated_at "
        "FROM endpoints WHERE name=?",
        (name,),
    ).fetchone()
    if not row:
        return None
    return _endpoint_from_row(row)


def get_endpoint_api_key(conn: sqlite3.Connection, endpoint_id: int) -> str:
    row = conn.execute(
        "SELECT api_key_enc FROM endpoints WHERE id=?", (endpoint_id,)
    ).fetchone()
    if not row:
        raise KeyError(f"endpoint id={endpoint_id} not found")
    return crypto.decrypt(row["api_key_enc"])


def list_endpoints(conn: sqlite3.Connection) -> list[EndpointDTO]:
    rows = conn.execute(
        "SELECT id, name, base_url, provider_type, created_at, updated_at "
        "FROM endpoints ORDER BY id"
    ).fetchall()
    return [_endpoint_from_row(r) for r in rows]


def delete_endpoint(conn: sqlite3.Connection, name: str) -> bool:
    cur = conn.execute("DELETE FROM endpoints WHERE name=?", (name,))
    return cur.rowcount > 0


def _endpoint_from_row(row: sqlite3.Row) -> EndpointDTO:
    return EndpointDTO(
        id=row["id"],
        name=row["name"],
        base_url=row["base_url"],
        provider_type=ProviderType(row["provider_type"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# ---------- models ----------


def upsert_model(
    conn: sqlite3.Connection,
    endpoint_id: int,
    model_id: str,
    raw_meta: dict[str, Any] | None = None,
    context_length: int | None = None,
) -> None:
    raw_json = json.dumps(raw_meta, ensure_ascii=False) if raw_meta else None
    conn.execute(
        """
        INSERT INTO models(endpoint_id, model_id, raw_meta_json, context_length)
        VALUES (?,?,?,?)
        ON CONFLICT(endpoint_id, model_id) DO UPDATE SET
          raw_meta_json = COALESCE(excluded.raw_meta_json, models.raw_meta_json),
          context_length = COALESCE(excluded.context_length, models.context_length),
          last_discovered_at = datetime('now')
        """,
        (endpoint_id, model_id, raw_json, context_length),
    )


def update_model_capability(
    conn: sqlite3.Connection,
    endpoint_id: int,
    model_id: str,
    capability: str,
    value: Any,
    source: CapabilitySource,
    probed_at: str | None,
) -> None:
    """Patch a single capability key inside capabilities_json (read-modify-write)."""
    row = conn.execute(
        "SELECT capabilities_json FROM models WHERE endpoint_id=? AND model_id=?",
        (endpoint_id, model_id),
    ).fetchone()
    caps: dict[str, Any] = json.loads(row["capabilities_json"]) if row else {}
    caps[capability] = {
        "value": value,
        "source": source.value,
        "probed_at": probed_at,
    }
    conn.execute(
        "UPDATE models SET capabilities_json=? WHERE endpoint_id=? AND model_id=?",
        (json.dumps(caps, ensure_ascii=False), endpoint_id, model_id),
    )


def list_models(
    conn: sqlite3.Connection, endpoint_id: int | None = None
) -> list[ModelDTO]:
    if endpoint_id is None:
        rows = conn.execute(
            """
            SELECT m.endpoint_id, e.name AS endpoint_name, m.model_id,
                   m.capabilities_json, m.context_length, m.raw_meta_json,
                   m.performance_json, m.last_discovered_at
              FROM models m JOIN endpoints e ON e.id = m.endpoint_id
             ORDER BY e.name, m.model_id
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT m.endpoint_id, e.name AS endpoint_name, m.model_id,
                   m.capabilities_json, m.context_length, m.raw_meta_json,
                   m.performance_json, m.last_discovered_at
              FROM models m JOIN endpoints e ON e.id = m.endpoint_id
             WHERE m.endpoint_id=?
             ORDER BY m.model_id
            """,
            (endpoint_id,),
        ).fetchall()
    return [_model_from_row(r) for r in rows]


def get_model(
    conn: sqlite3.Connection, endpoint_id: int, model_id: str
) -> ModelDTO | None:
    row = conn.execute(
        """
        SELECT m.endpoint_id, e.name AS endpoint_name, m.model_id,
               m.capabilities_json, m.context_length, m.raw_meta_json,
               m.performance_json, m.last_discovered_at
          FROM models m JOIN endpoints e ON e.id = m.endpoint_id
         WHERE m.endpoint_id=? AND m.model_id=?
        """,
        (endpoint_id, model_id),
    ).fetchone()
    if not row:
        return None
    return _model_from_row(row)


def _model_from_row(row: sqlite3.Row) -> ModelDTO:
    caps_raw: dict[str, Any] = json.loads(row["capabilities_json"] or "{}")
    caps: dict[str, CapabilityValue] = {}
    for k, v in caps_raw.items():
        try:
            caps[k] = CapabilityValue(
                value=v.get("value"),
                source=CapabilitySource(v.get("source", "static")),
                probed_at=v.get("probed_at"),
            )
        except (ValueError, AttributeError):
            continue
    return ModelDTO(
        endpoint_id=row["endpoint_id"],
        endpoint_name=row["endpoint_name"],
        model_id=row["model_id"],
        capabilities=caps,
        context_length=row["context_length"],
        raw_meta=json.loads(row["raw_meta_json"]) if row["raw_meta_json"] else None,
        performance=json.loads(row["performance_json"] or "{}"),
        last_discovered_at=row["last_discovered_at"],
    )


def delete_model(
    conn: sqlite3.Connection, endpoint_id: int, model_id: str
) -> bool:
    cur = conn.execute(
        "DELETE FROM models WHERE endpoint_id=? AND model_id=?",
        (endpoint_id, model_id),
    )
    return cur.rowcount > 0


# ---------- overrides ----------


def upsert_override(
    conn: sqlite3.Connection,
    endpoint_id: int,
    model_id: str,
    capability_key: str,
    value: Any,
) -> None:
    conn.execute(
        """
        INSERT INTO overrides(endpoint_id, model_id, capability_key, value_json)
        VALUES (?,?,?,?)
        ON CONFLICT(endpoint_id, model_id, capability_key) DO UPDATE SET
          value_json = excluded.value_json,
          updated_at = datetime('now')
        """,
        (endpoint_id, model_id, capability_key, json.dumps(value, ensure_ascii=False)),
    )


def list_overrides(
    conn: sqlite3.Connection, endpoint_id: int, model_id: str
) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT capability_key, value_json FROM overrides "
        "WHERE endpoint_id=? AND model_id=?",
        (endpoint_id, model_id),
    ).fetchall()
    return {r["capability_key"]: json.loads(r["value_json"]) for r in rows}


def delete_override(
    conn: sqlite3.Connection, endpoint_id: int, model_id: str, capability_key: str
) -> bool:
    cur = conn.execute(
        "DELETE FROM overrides WHERE endpoint_id=? AND model_id=? AND capability_key=?",
        (endpoint_id, model_id, capability_key),
    )
    return cur.rowcount > 0


def delete_overrides_for_model(
    conn: sqlite3.Connection, endpoint_id: int, model_id: str
) -> int:
    cur = conn.execute(
        "DELETE FROM overrides WHERE endpoint_id=? AND model_id=?",
        (endpoint_id, model_id),
    )
    return cur.rowcount


# ---------- model_call_events ----------


def insert_model_call_event(
    conn: sqlite3.Connection,
    endpoint_id: int,
    model_id: str,
    operation: str,
    ok: bool,
    upstream_status: int,
    first_byte_ms: int | None,
    latency_ms: int | None,
    prompt_tokens: int | None,
    output_tokens: int | None,
    total_tokens: int | None,
    error_type: str | None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO model_call_events(
          endpoint_id, model_id, operation, ok, upstream_status, first_byte_ms,
          latency_ms, prompt_tokens, output_tokens, total_tokens, error_type
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            endpoint_id,
            model_id,
            operation,
            1 if ok else 0,
            upstream_status,
            first_byte_ms,
            latency_ms,
            prompt_tokens,
            output_tokens,
            total_tokens,
            error_type,
        ),
    )
    if cur.lastrowid is None:
        raise RuntimeError("failed to insert model call event")
    return cur.lastrowid


def delete_model_call_events_older_than(conn: sqlite3.Connection, days: int) -> int:
    cur = conn.execute(
        "DELETE FROM model_call_events WHERE created_at < datetime('now', ?)",
        (f"-{days} days",),
    )
    return cur.rowcount


def aggregate_model_performance(conn: sqlite3.Connection, days: int) -> int:
    rows = conn.execute(
        """
        SELECT endpoint_id, model_id,
               COUNT(*) AS call_count,
               SUM(ok) AS success_count,
               AVG(first_byte_ms) AS avg_first_byte_ms,
               AVG(prompt_tokens) AS avg_prompt_tokens,
               AVG(output_tokens) AS avg_output_tokens
          FROM model_call_events
         WHERE created_at >= datetime('now', ?)
         GROUP BY endpoint_id, model_id
        """,
        (f"-{days} days",),
    ).fetchall()
    for row in rows:
        perf = {
            "window_days": days,
            "call_count": row["call_count"] or 0,
            "success_count": row["success_count"] or 0,
            "avg_first_byte_ms": row["avg_first_byte_ms"],
            "avg_prompt_tokens": row["avg_prompt_tokens"],
            "avg_output_tokens": row["avg_output_tokens"],
        }
        conn.execute(
            "UPDATE models SET performance_json=? WHERE endpoint_id=? AND model_id=?",
            (json.dumps(perf, ensure_ascii=False), row["endpoint_id"], row["model_id"]),
        )
    conn.execute(
        """
        UPDATE models
           SET performance_json='{}'
         WHERE NOT EXISTS (
           SELECT 1 FROM model_call_events e
            WHERE e.endpoint_id=models.endpoint_id
              AND e.model_id=models.model_id
              AND e.created_at >= datetime('now', ?)
         )
        """,
        (f"-{days} days",),
    )
    return len(rows)


# ---------- probe_runs ----------


def insert_probe_run(
    conn: sqlite3.Connection,
    endpoint_id: int,
    model_id: str,
    result: ProbeResult,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO probe_runs
          (endpoint_id, model_id, capability, ok, status, latency_ms, raw_json, error)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            endpoint_id,
            model_id,
            result.capability.value,
            1 if result.ok else 0,
            result.status.value,
            result.latency_ms,
            json.dumps(result.raw, ensure_ascii=False) if result.raw else None,
            result.error,
        ),
    )
    if cur.lastrowid is None:
        raise RuntimeError("failed to insert probe run")
    return cur.lastrowid


def list_probe_runs(
    conn: sqlite3.Connection,
    endpoint_id: int | None = None,
    model_id: str | None = None,
    capability: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    conditions: list[str] = []
    params: list[Any] = []
    if endpoint_id is not None:
        conditions.append("endpoint_id=?")
        params.append(endpoint_id)
    if model_id is not None:
        conditions.append("model_id=?")
        params.append(model_id)
    if capability is not None:
        conditions.append("capability=?")
        params.append(capability)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)
    rows = conn.execute(
        f"SELECT * FROM probe_runs {where} ORDER BY ran_at DESC LIMIT ?",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


# ---------- probe_jobs ----------


def enqueue_job(
    conn: sqlite3.Connection,
    endpoint_id: int,
    model_id: str,
    capability: Capability,
    priority: int = 0,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO probe_jobs(endpoint_id, model_id, capability, priority)
        VALUES (?,?,?,?)
        """,
        (endpoint_id, model_id, capability.value, priority),
    )
    if cur.lastrowid is None:
        raise RuntimeError("failed to enqueue probe job")
    return cur.lastrowid


def list_jobs(
    conn: sqlite3.Connection,
    status: JobStatus | None = None,
    limit: int = 200,
) -> list[ProbeJobDTO]:
    if status is None:
        rows = conn.execute(
            "SELECT * FROM probe_jobs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM probe_jobs WHERE status=? ORDER BY id DESC LIMIT ?",
            (status.value, limit),
        ).fetchall()
    return [_job_from_row(r) for r in rows]


def get_job(conn: sqlite3.Connection, job_id: int) -> ProbeJobDTO | None:
    row = conn.execute("SELECT * FROM probe_jobs WHERE id=?", (job_id,)).fetchone()
    return _job_from_row(row) if row else None


def claim_job_attempt(
    conn: sqlite3.Connection, job_id: int, instance_id: str, lease_until: str
) -> bool:
    """Conditional UPDATE; returns True iff this caller wrote claimed_by."""
    cur = conn.execute(
        """
        UPDATE probe_jobs
           SET claimed_by=?, claimed_at=datetime('now'),
               lease_until=?, status='claiming'
         WHERE id=? AND status='pending' AND claimed_by IS NULL
        """,
        (instance_id, lease_until, job_id),
    )
    return cur.rowcount == 1


def get_claimed_by(conn: sqlite3.Connection, job_id: int) -> str | None:
    row = conn.execute(
        "SELECT claimed_by, status FROM probe_jobs WHERE id=?", (job_id,)
    ).fetchone()
    return row["claimed_by"] if row else None


def mark_job_running(conn: sqlite3.Connection, job_id: int) -> None:
    conn.execute("UPDATE probe_jobs SET status='running' WHERE id=?", (job_id,))


def mark_job_done(
    conn: sqlite3.Connection, job_id: int, error: str | None = None
) -> None:
    status = "failed" if error else "done"
    conn.execute(
        "UPDATE probe_jobs SET status=?, finished_at=datetime('now'), error=? WHERE id=?",
        (status, error, job_id),
    )


def next_pending_job_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute(
        """
        SELECT id FROM probe_jobs
         WHERE status='pending' AND claimed_by IS NULL
         ORDER BY priority DESC, id ASC LIMIT 1
        """
    ).fetchone()
    return int(row["id"]) if row else None


def sweep_orphans(conn: sqlite3.Connection) -> int:
    """Reset claiming/running jobs whose lease_until is past."""
    cur = conn.execute(
        """
        UPDATE probe_jobs
           SET status='pending', claimed_by=NULL, claimed_at=NULL, lease_until=NULL
         WHERE status IN ('claiming','running')
           AND lease_until IS NOT NULL
           AND lease_until < datetime('now')
        """
    )
    return cur.rowcount


def _job_from_row(row: sqlite3.Row) -> ProbeJobDTO:
    return ProbeJobDTO(
        id=row["id"],
        endpoint_id=row["endpoint_id"],
        model_id=row["model_id"],
        capability=Capability(row["capability"]),
        status=JobStatus(row["status"]),
        priority=row["priority"],
        claimed_by=row["claimed_by"],
        claimed_at=row["claimed_at"],
        lease_until=row["lease_until"],
        finished_at=row["finished_at"],
        error=row["error"],
        created_at=row["created_at"],
    )

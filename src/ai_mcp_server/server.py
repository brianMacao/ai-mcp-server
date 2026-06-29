"""ai-mcp-server: stdio MCP server.

Exposes 6 tools:
- usage_guide
- list_models
- invoke_model
- model_performance
- refresh_endpoint
- add_models

Starts a background worker that drains probe_jobs while the server runs.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from collections import Counter
from typing import Any

from mcp.server.fastmcp import FastMCP

from .application import (
    capability_query,
    endpoint_service,
    invoke_service,
    manual_models,
    model_discovery,
    performance_query,
)
from .application import (
    probe_jobs as probe_jobs_app,
)
from .application import (
    worker as worker_mod,
)
from .models.enums import Capability

logger = logging.getLogger("ai_mcp_server.server")

INSTRUCTIONS = """\
You are connected to ai-mcp-server: a local bridge that exposes many model
endpoints behind a single MCP interface.

IMPORTANT: You MUST call `usage_guide` first before using any other tool.
It returns the current endpoint inventory, capability distribution and the
recommended routing pattern.

Then use:
- `list_models` to filter models by required capabilities and minimum context
  length; this returns endpoint+model_id pairs you can use with `invoke_model`.
- `invoke_model` to forward a request (chat / embedding / image_gen / tts / stt
  / rerank) to the chosen endpoint. The upstream JSON body is returned verbatim
  inside `body`; errors are passed through inside `error`.
- `model_performance` to inspect recent per-model call metrics before choosing
  between otherwise similar models.
- `refresh_endpoint` to enqueue capability probes (executed asynchronously by a
  background worker inside this server).
- `add_models` to manually register models for endpoints that do not expose
  `/v1/models`, or to register user-confirmed model features. Use canonical
  capability names (`audio_tts`, `audio_stt`, etc.); common aliases such as
  `tts`, `stt`, and `asr` are accepted by `add_models`.
"""


def _build_usage_text() -> str:
    eps = endpoint_service.list_endpoints()
    if not eps:
        return (
            "No endpoints registered. Ask the user to run "
            "`ai-mcp endpoint add --name <n> --base-url <url> --key <k>` first."
        )
    models = capability_query.query_models()
    cap_counts: dict[str, int] = {}
    for it in models:
        for cap, cv in it["capabilities"].items():
            if cv.get("value"):
                cap_counts[cap] = cap_counts.get(cap, 0) + 1
    cap_lines = "\n".join(
        f"  - {cap}: {count} model(s)" for cap, count in sorted(cap_counts.items())
    )
    return (
        f"Endpoints registered: {len(eps)}\n"
        f"Models discovered: {len(models)}\n"
        f"Capability distribution:\n{cap_lines or '  (none probed yet — call refresh_endpoint)'}\n\n"
        f"Recommended pattern:\n"
        f"  1) call list_models with the capabilities you need.\n"
        f"  2) if a gateway does not expose /models, ask the user before using add_models.\n"
        f"     You may also use add_models to register confirmed features, e.g.\n"
        f"     capabilities=['audio_tts'] or feature_overrides={{'audio_stt': true}}.\n"
        f"  3) optionally call model_performance to compare recent success/latency.\n"
        f"  4) pick endpoint+model_id from the result.\n"
        f"  5) call invoke_model with that pair and the upstream payload.\n"
        f"  6) call refresh_endpoint when the inventory looks stale or unprobed.\n"
    )


def create_server() -> FastMCP:
    server = FastMCP("ai-mcp", instructions=INSTRUCTIONS)

    @server.tool()
    def usage_guide() -> dict[str, Any]:
        """Return current capability inventory and usage instructions.

        Call this first whenever you connect.
        """
        eps = endpoint_service.list_endpoints()
        return {
            "guide": _build_usage_text(),
            "endpoints": [
                {"name": e.name, "base_url": e.base_url} for e in eps
            ],
            "feature_registration": {
                "mcp_tool": (
                    "add_models(endpoint, model_ids, capabilities=[...], "
                    "feature_overrides={...})"
                ),
                "cli": [
                    "ai-mcp model add --endpoint <name> <model_id> --capability audio_tts",
                    "ai-mcp model add --endpoint <name> <model_id> --features tts=true,context_length=32000",
                    "ai-mcp model override <endpoint> <model_id> --capability audio_stt=true",
                ],
                "web_ui": "Open ai-mcp ui, then use Models manual add or the Overrides page.",
                "capabilities": [c.value for c in Capability],
                "aliases": manual_models.capability_aliases(),
            },
        }

    @server.tool()
    def list_models(
        capability: list[str] | None = None,
        min_context_length: int | None = None,
        endpoint: str | None = None,
        include_unprobed: bool = True,
    ) -> list[dict[str, Any]]:
        """List models matching the filters.

        Args:
            capability: capability tags the model must support (e.g. ["vision"]).
            min_context_length: minimum context window in tokens.
            endpoint: limit to a single endpoint name.
            include_unprobed: include models whose capabilities have not been
                probed yet (default True).
        """
        caps: list[Capability] | None = None
        if capability:
            caps = []
            for c in capability:
                try:
                    caps.append(manual_models.parse_capability(c))
                except ValueError:
                    return [{"error": f"unknown capability: {c}"}]
        return capability_query.query_models(
            capability=caps,
            min_context_length=min_context_length,
            endpoint=endpoint,
            include_unprobed=include_unprobed,
        )

    @server.tool()
    async def invoke_model(
        endpoint: str,
        model: str,
        operation: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Forward a request to the selected (endpoint, model).

        Args:
            endpoint: endpoint name registered via the CLI.
            model: model_id as returned by list_models.
            operation: one of chat / embedding / image_gen / tts / stt / rerank.
            payload: upstream-compatible body (OpenAI shape for openai-compat
                endpoints). The `model` field is set automatically. The response
                is passed through verbatim; errors are returned inside `error`.
        """
        return await invoke_service.invoke(endpoint, model, operation, payload)

    @server.tool()
    def model_performance(
        endpoint: str | None = None,
        sort_by: str = "call_count",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return近3天 aggregated call metrics per model (background-updated).

        Args:
            endpoint: limit to a single endpoint name.
            sort_by: one of call_count / success_count / avg_first_byte_ms /
                avg_prompt_tokens / avg_output_tokens.
            limit: max rows to return.

        Each row includes call_count, success_count, success_rate,
        avg_first_byte_ms, avg_prompt_tokens, avg_output_tokens, window_days.
        """
        return performance_query.query_performance(
            endpoint=endpoint, sort_by=sort_by, limit=limit
        )

    @server.tool()
    async def refresh_endpoint(
        endpoint: str | None = None,
        capabilities: list[str] | None = None,
        refresh_model_list: bool = True,
    ) -> dict[str, Any]:
        """Enqueue probe jobs. Server-internal worker will drain them.

        Args:
            endpoint: endpoint name; if None, refresh every endpoint.
            capabilities: list of capability tags; if None, choose probes per model using known metadata.
            refresh_model_list: re-fetch /v1/models first (default True).
        """
        caps: list[Capability] | None = None
        if capabilities:
            try:
                caps = [manual_models.parse_capability(c) for c in capabilities]
            except ValueError as e:
                return {"error": str(e)}
        targets = (
            [endpoint_service.get_endpoint(endpoint)] if endpoint
            else endpoint_service.list_endpoints()
        )
        targets = [t for t in targets if t is not None]
        if not targets:
            return {"error": "no endpoint matched"}
        enqueued = 0
        plan_summary: dict[str, dict[str, Any]] = {}
        for ep in targets:
            assert ep is not None
            if refresh_model_list:
                try:
                    await model_discovery.discover(ep.name)
                except Exception as e:
                    return {"error": f"discover {ep.name} failed: {e}"}
            from .storage import dao
            from .storage.db import connect

            with connect() as conn:
                models = dao.list_models(conn, endpoint_id=ep.id)
            model_ids = [m.model_id for m in models]
            if caps is None:
                plan = probe_jobs_app.probe_plan(ep.id, model_ids)
                cap_counts = Counter(
                    cap
                    for item in plan
                    for cap in item["capabilities"]
                )
            else:
                cap_counts = Counter({cap.value: len(model_ids) for cap in caps})
            jids = probe_jobs_app.enqueue_for_endpoint(ep.id, model_ids, caps)
            enqueued += len(jids)
            plan_summary[ep.name] = {
                "models": len(model_ids),
                "jobs": len(jids),
                "capabilities": dict(sorted(cap_counts.items())),
                "strategy": "smart" if caps is None else "explicit",
            }
        return {
            "enqueued": enqueued,
            "plan": plan_summary,
            "note": "probes run asynchronously; poll list_models or read probe_jobs via the UI.",
        }

    @server.tool()
    def add_models(
        endpoint: str,
        model_ids: list[str],
        context_length: int | None = None,
        capabilities: list[str] | None = None,
        feature_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Manually register models or user-confirmed model features.

        Args:
            endpoint: endpoint name.
            model_ids: one or more model_id to register.
            context_length: optional context window in tokens.
            capabilities: optional capability tags to mark as supported
                (override source). Aliases tts/stt/asr are accepted.
            feature_overrides: optional key/value overrides. Keys may be
                capability tags or context_length; capability values must be
                booleans. Example: {"audio_tts": true, "context_length": 32000}.
        """
        caps: list[Capability] | None = None
        if capabilities:
            try:
                caps = [manual_models.parse_capability(c) for c in capabilities]
            except ValueError as e:
                return {"error": str(e)}
        try:
            features = manual_models.normalize_feature_overrides(feature_overrides)
        except ValueError as e:
            return {"error": str(e)}
        return manual_models.add_models(
            endpoint, model_ids, context_length, caps, features
        )

    return server


async def _run_with_worker(metrics_retention_days: int = 3) -> None:
    server = create_server()
    worker = worker_mod.Worker(metrics_retention_days=metrics_retention_days)
    worker.refresh_metrics()
    worker_task = asyncio.create_task(worker.run_loop())
    try:
        await server.run_stdio_async()
    finally:
        worker.request_stop()
        worker_task.cancel()
        try:
            await worker_task
        except (asyncio.CancelledError, Exception):
            pass


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--metrics-retention-days",
        type=int,
        default=3,
        help="days of invoke metrics to keep (default: 3)",
    )
    args = parser.parse_args()
    asyncio.run(_run_with_worker(metrics_retention_days=args.metrics_retention_days))


if __name__ == "__main__":
    main()

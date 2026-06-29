"""ai-mcp CLI entry point (typer).

Subcommands:
  init
  endpoint add / list / show / remove / discover / probe
  model    list / show / override
  meta     refresh / info
  worker
  ui
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter

import typer
from rich.console import Console
from rich.table import Table

from .application import (
    capability_query,
    endpoint_service,
    manual_models,
    meta_service,
    metrics,
    model_discovery,
    override_service,
    performance_query,
    probe_jobs,
)
from .application import (
    worker as worker_mod,
)
from .models.enums import ALL_CAPABILITIES, Capability

app = typer.Typer(help="ai-mcp: local MCP bridge for multi-endpoint model capability pool")
endpoint_app = typer.Typer(help="Manage endpoints (api_key + base_url)")
model_app = typer.Typer(help="Inspect / override model capabilities")
meta_app = typer.Typer(help="LiteLLM metadata management")
app.add_typer(endpoint_app, name="endpoint")
app.add_typer(model_app, name="model")
app.add_typer(meta_app, name="meta")

console = Console()
err = Console(stderr=True, style="red")
warn = Console(stderr=True, style="yellow")
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")


# --------- endpoint ---------


@endpoint_app.command("add")
def endpoint_add(
    name: str = typer.Option(..., "--name", "-n", help="endpoint name (unique)"),
    base_url: str = typer.Option(..., "--base-url", "-u", help="API base URL"),
    key: str = typer.Option(..., "--key", "-k", help="api_key (encrypted at rest)"),
    provider: str = typer.Option("openai-compat", "--provider", help="provider type"),
) -> None:
    """Register a new endpoint."""
    from .models.enums import ProviderType

    try:
        ep = endpoint_service.add_endpoint(name, base_url, key, ProviderType(provider))
    except ValueError as e:
        err.print(f"error: {e}")
        raise typer.Exit(1) from None
    console.print(f"[green]added[/] endpoint id={ep.id} name={ep.name} base_url={ep.base_url}")


@endpoint_app.command("list")
def endpoint_list(
    as_json: bool = typer.Option(False, "--json", help="output JSON"),
) -> None:
    items = endpoint_service.list_endpoints()
    if as_json:
        console.print_json(data=[{
            "id": e.id, "name": e.name, "base_url": e.base_url,
            "provider_type": e.provider_type.value,
            "created_at": e.created_at,
        } for e in items])
        return
    t = Table(title="endpoints")
    t.add_column("id")
    t.add_column("name")
    t.add_column("base_url")
    t.add_column("provider")
    t.add_column("created_at")
    for e in items:
        t.add_row(str(e.id), e.name, e.base_url, e.provider_type.value, e.created_at)
    console.print(t)


@endpoint_app.command("show")
def endpoint_show(name: str) -> None:
    ep = endpoint_service.get_endpoint(name)
    if not ep:
        err.print(f"endpoint {name!r} not found")
        raise typer.Exit(1)
    console.print_json(data={
        "id": ep.id, "name": ep.name, "base_url": ep.base_url,
        "provider_type": ep.provider_type.value, "created_at": ep.created_at,
    })


@endpoint_app.command("remove")
def endpoint_remove(name: str) -> None:
    ok = endpoint_service.remove_endpoint(name)
    if not ok:
        err.print(f"endpoint {name!r} not found")
        raise typer.Exit(1)
    console.print(f"[green]removed[/] {name}")


@endpoint_app.command("discover")
def endpoint_discover(name: str) -> None:
    """Fetch /v1/models and cache locally."""
    try:
        discovered = asyncio.run(model_discovery.discover(name))
    except Exception as e:
        err.print(f"discover failed: {e}")
        raise typer.Exit(1) from None
    console.print(f"[green]discovered[/] {len(discovered)} models on {name}")
    for m in discovered:
        console.print(f"  - {m}")


@endpoint_app.command("probe")
def endpoint_probe(
    name: str | None = typer.Argument(None, help="endpoint name; omit if --all"),
    all_endpoints: bool = typer.Option(False, "--all", help="probe all endpoints"),
    capability: str | None = typer.Option(None, "--capability", help="comma-separated capabilities; default = all 10"),
    yes: bool = typer.Option(False, "--yes", "-y", help="skip confirmation for paid probes"),
    metrics_retention_days: int = typer.Option(metrics.DEFAULT_RETENTION_DAYS, "--metrics-retention-days", help="days of invoke metrics to keep"),
) -> None:
    """Enqueue probe jobs and drain them synchronously (CLI worker)."""
    caps: list[Capability] | None = None
    if capability:
        try:
            caps = manual_models.parse_capabilities(capability)
        except ValueError as e:
            err.print(f"unknown capability: {e}")
            raise typer.Exit(1) from None

    paid = {Capability.IMAGE_GEN, Capability.AUDIO_TTS}
    probing_caps = set(caps or ALL_CAPABILITIES)
    if not yes and (paid & probing_caps):
        confirmed = typer.confirm(
            f"probes for {sorted(c.value for c in (paid & probing_caps))} may incur upstream cost. continue?",
        )
        if not confirmed:
            raise typer.Exit(0)

    if all_endpoints:
        targets = endpoint_service.list_endpoints()
    elif name:
        ep = endpoint_service.get_endpoint(name)
        if not ep:
            err.print(f"endpoint {name!r} not found")
            raise typer.Exit(1)
        targets = [ep]
    else:
        err.print("specify endpoint name or --all")
        raise typer.Exit(1)

    async def _go() -> int:
        total_enq = 0
        for ep in targets:
            console.print(f"[cyan]discovering[/] models on {ep.name} ...")
            try:
                model_ids = await model_discovery.discover(ep.name)
            except Exception as e:
                err.print(f"  discover failed: {e}")
                continue
            if caps is None:
                plan = probe_jobs.probe_plan(ep.id, model_ids)
                cap_counts = Counter(
                    cap
                    for item in plan
                    for cap in item["capabilities"]
                )
                summary = ", ".join(
                    f"{cap}={count}" for cap, count in sorted(cap_counts.items())
                )
                console.print(
                    f"  smart probe plan: models={len(model_ids)} jobs={sum(cap_counts.values())} {summary}"
                )
            else:
                console.print(
                    f"  explicit probe plan: models={len(model_ids)} jobs={len(model_ids) * len(caps)}"
                )
            jids = probe_jobs.enqueue_for_endpoint(ep.id, model_ids, caps)
            total_enq += len(jids)
        console.print("[cyan]draining[/] queue (instance worker) ...")
        processed = await worker_mod.drain_blocking(metrics_retention_days=metrics_retention_days)
        console.print(f"[green]done[/] enqueued={total_enq} processed={processed}")
        return processed

    asyncio.run(_go())


# --------- model ---------


@model_app.command("list")
def model_list(
    endpoint: str | None = typer.Option(None, "--endpoint", "-e"),
    capability: str | None = typer.Option(None, "--capability", help="comma-separated"),
    min_context: int | None = typer.Option(None, "--min-context"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    caps: list[Capability] | None = None
    if capability:
        try:
            caps = manual_models.parse_capabilities(capability)
        except ValueError as e:
            err.print(f"unknown capability: {e}")
            raise typer.Exit(1) from None
    items = capability_query.query_models(
        capability=caps, min_context_length=min_context, endpoint=endpoint
    )
    if as_json:
        console.print_json(data=items)
        return
    t = Table(title=f"models ({len(items)})")
    t.add_column("endpoint")
    t.add_column("model_id")
    t.add_column("ctx")
    t.add_column("capabilities")
    for it in items:
        cap_list = ",".join(
            f"{k}({v['source'][:3]})" for k, v in it["capabilities"].items() if v.get("value")
        )
        t.add_row(it["endpoint"], it["model_id"], str(it["context_length"]), cap_list)
    console.print(t)


@model_app.command("show")
def model_show(endpoint: str, model_id: str) -> None:
    detail = capability_query.model_detail(endpoint, model_id)
    if not detail:
        err.print("not found")
        raise typer.Exit(1)
    console.print_json(data=detail)


@model_app.command("add")
def model_add(
    endpoint: str = typer.Option(..., "--endpoint", "-e", help="endpoint name"),
    model_ids: list[str] = typer.Argument(..., help="one or more model_id to register"),
    context_length: int | None = typer.Option(None, "--context-length", help="context window tokens"),
    capability: str | None = typer.Option(None, "--capability", help="comma-separated capabilities to mark as supported"),
    features: str | None = typer.Option(
        None,
        "--features",
        "--feature",
        "-f",
        help="comma/newline-separated key=value overrides, e.g. tts=true,context_length=32000",
    ),
) -> None:
    """Manually register models or confirmed model features."""
    try:
        caps = manual_models.parse_capabilities(capability)
        feature_overrides = manual_models.parse_feature_overrides(features)
    except ValueError as e:
        err.print(f"invalid model feature: {e}")
        raise typer.Exit(1) from None
    result = manual_models.add_models(
        endpoint, model_ids, context_length, caps, feature_overrides
    )
    if "error" in result:
        err.print(result["error"])
        raise typer.Exit(1)
    console.print(f"[green]added[/] {result['count']} model(s) on {endpoint}")
    for m in result["added"]:
        console.print(f"  - {m}")
    if result.get("features"):
        console.print(f"[green]features[/] {result['features']}")


@model_app.command("remove")
def model_remove(
    endpoint: str = typer.Option(..., "--endpoint", "-e", help="endpoint name"),
    model_id: str = typer.Argument(..., help="model_id to remove"),
) -> None:
    """Remove a manually or auto registered model from the local cache."""
    result = manual_models.remove_model(endpoint, model_id)
    if "error" in result:
        err.print(result["error"])
        raise typer.Exit(1)
    if not result["removed"]:
        err.print(f"model {model_id!r} not found on {endpoint}")
        raise typer.Exit(1)
    console.print(f"[green]removed[/] {endpoint}/{model_id}")



@model_app.command("performance")
def model_performance(
    endpoint: str | None = typer.Option(None, "--endpoint", "-e"),
    sort_by: str = typer.Option("call_count", "--sort-by", help="call_count|success_count|avg_first_byte_ms|avg_prompt_tokens|avg_output_tokens"),
    limit: int = typer.Option(50, "--limit"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Show近3天 aggregated call metrics per model (background-updated)."""
    rows = performance_query.query_performance(
        endpoint=endpoint, sort_by=sort_by, limit=limit
    )
    if as_json:
        console.print_json(data=rows)
        return
    t = Table(title=f"model performance近3天 ({len(rows)})")
    t.add_column("endpoint")
    t.add_column("model_id")
    t.add_column("calls")
    t.add_column("success")
    t.add_column("rate")
    t.add_column("first_byte_ms")
    t.add_column("avg_prompt")
    t.add_column("avg_output")
    for r in rows:
        t.add_row(
            r["endpoint"],
            r["model_id"],
            str(r["call_count"]),
            str(r["success_count"]),
            f"{r['success_rate']:.0%}" if r["success_rate"] is not None else "-",
            f"{r['avg_first_byte_ms']:.0f}" if r["avg_first_byte_ms"] is not None else "-",
            f"{r['avg_prompt_tokens']:.0f}" if r["avg_prompt_tokens"] is not None else "-",
            f"{r['avg_output_tokens']:.0f}" if r["avg_output_tokens"] is not None else "-",
        )
    console.print(t)


@model_app.command("override")
def model_override(
    endpoint: str,
    model_id: str,
    capability: str = typer.Option(..., "--capability", help="cap=value, e.g. vision=true"),
) -> None:
    if "=" not in capability:
        err.print("--capability must be in form key=value")
        raise typer.Exit(1)
    key, raw = capability.split("=", 1)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = raw
    normalized_key = key.strip()
    try:
        normalized = manual_models.normalize_feature_overrides({normalized_key: value})
    except ValueError:
        normalized = {}
    if normalized:
        normalized_key, value = next(iter(normalized.items()))
    override_service.set_override(endpoint, model_id, normalized_key, value)
    console.print(
        f"[green]ok[/] override {endpoint}/{model_id} {normalized_key}={value!r}"
    )


# --------- meta ---------


@meta_app.command("refresh")
def meta_refresh() -> None:
    n = meta_service.refresh()
    console.print(f"[green]refreshed[/] {n} entries cached")


@meta_app.command("info")
def meta_info() -> None:
    console.print_json(data=meta_service.info())


# --------- init ---------


@app.command("init")
def cmd_init(
    language: str = typer.Option(None, "--lang", help="force language: zh-sc, zh-tc, en"),
) -> None:
    """Interactive first-run setup: register endpoints, discover models, configure MCP clients."""
    from .application import init_wizard

    code = asyncio.run(init_wizard.run_init(language=language))
    raise typer.Exit(code)


# --------- worker ---------


@app.command("worker")
def cmd_worker(
    metrics_retention_days: int = typer.Option(metrics.DEFAULT_RETENTION_DAYS, "--metrics-retention-days", help="days of invoke metrics to keep"),
) -> None:
    """Run a long-running worker loop (drains probe_jobs forever)."""
    w = worker_mod.Worker(metrics_retention_days=metrics_retention_days)
    console.print(f"[cyan]worker[/] instance_id={w.instance_id}")
    try:
        asyncio.run(w.run_loop())
    except KeyboardInterrupt:
        console.print("\n[cyan]worker stopped[/]")


# --------- ui ---------


@app.command("ui")
def cmd_ui(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8765, "--port"),
    expose: bool = typer.Option(False, "--expose", help="allow binding to non-loopback host (use with AI_MCP_UI_TOKEN)"),
) -> None:
    """Launch the local Web UI."""
    from .i18n import init as i18n_init
    from .i18n import t

    i18n_init()

    loopback = {"127.0.0.1", "localhost", "::1"}
    if host not in loopback and not expose:
        err.print(
            f"!!! Refusing to bind to {host} without --expose.\n"
            f"The UI is unauthenticated unless AI_MCP_UI_TOKEN is set.\n"
            f"To expose it: set AI_MCP_UI_TOKEN env var, then retry with --expose.\n"
        )
        raise typer.Exit(1)
    if host not in loopback and expose:
        warn.print(f"[red]{t('ui_expose_warning')}[/red]")
    import uvicorn

    from .web.app import create_app

    fastapi_app = create_app()
    console.print(f"[green]{t('ui_starting')}[/green] at http://{host}:{port}/")
    uvicorn.run(fastapi_app, host=host, port=port, log_level="info")


def main() -> None:
    app()


if __name__ == "__main__":
    main()

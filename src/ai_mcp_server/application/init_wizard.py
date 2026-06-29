"""Interactive init wizard: first-run setup that registers an endpoint,
discovers models, and auto-configures MCP clients.

Triggered by: ai-mcp init
"""
from __future__ import annotations

import os

import typer
from rich.console import Console

from ..i18n import init as i18n_init
from ..i18n import t
from . import client_config, endpoint_service, model_discovery

console = Console()
err = Console(stderr=True, style="red")
warn = Console(stderr=True, style="yellow")


def _prompt(text: str, default: str = "", password: bool = False) -> str:
    prompt = f"  {text} [{default}]: " if default else f"  {text}: "
    return typer.prompt(prompt, default=default, hide_input=password)


def _confirm(text: str, default: bool = True) -> bool:
    yes = t("yes").lower()
    no = t("no").lower()
    suffix = f" [{yes}/{no}]: "
    return typer.confirm(f"  {text}{suffix}", default=default)


async def run_init(language: str | None = None) -> int:
    """Run the full interactive setup flow."""
    # 1. Language
    if language:
        from ..i18n import set_locale
        set_locale(language)
    else:
        i18n_init()

    console.print(f"\n[bold cyan]{t('init_title')}[/bold cyan]\n")

    # 2. Register endpoint
    console.print(f"[bold]{t('init_step_endpoint', n='1', total='1')}[/bold]")
    name = _prompt(t("endpoint_name_prompt"))
    if not name:
        err.print("[red]Endpoint name required[/red]")
        return 1

    base_url = _prompt(t("endpoint_url_prompt"))
    if not base_url:
        err.print("[red]Base URL required[/red]")
        return 1

    api_key = _prompt(t("endpoint_key_prompt"), password=True)
    if not api_key:
        err.print("[red]API key required[/red]")
        return 1

    provider = _prompt(t("endpoint_provider_prompt"), default="openai-compat")

    try:
        from ..models.enums import ProviderType
        endpoint_service.add_endpoint(name, base_url, api_key, ProviderType(provider))
        console.print(f"  [green]{t('endpoint_added', name=name)}[/green]")
    except ValueError as e:
        err.print(f"  [red]{e}[/red]")
        return 1

    # 3. Discover models
    console.print(f"\n  [cyan]{t('discover_start')}[/cyan]")
    try:
        discovered = await model_discovery.discover(name)
        console.print(f"  [green]{t('discover_done', n=len(discovered))}[/green]")
    except Exception as exc:
        warn.print(f"  [yellow]{t('discover_failed', error=exc)}[/yellow]")

    # 4. Detect and configure MCP clients
    console.print(f"\n[bold]{t('init_step_clients', n='2')}[/bold]")
    console.print(f"  [cyan]{t('client_detect_start')}[/cyan]")

    clients = client_config.detect_clients(project_dir=os.getcwd())
    configured = 0
    for cc in clients:
        if cc.config_path is None:
            continue
        if cc.exists:
            console.print(f"  [green]✓[/green] {t('client_found', name=cc.display_name)} ({cc.config_path})")
        else:
            console.print(f"  ╺ {t('client_not_found', name=cc.display_name)}")
            continue

        write_prompt = t("client_write_prompt", name=cc.display_name)
        if cc.display_name.startswith("Trae"):
            write_prompt = t("trae_project_prompt", dir=os.getcwd())

        if _confirm(write_prompt):
            reader = client_config.CLIENT_FORMATTERS.get(cc.display_name)
            writer = client_config.CLIENT_WRITERS.get(cc.display_name)
            if reader and writer and cc.config_path:
                existing = reader(cc.config_path)
                writer(cc.config_path, existing)
                console.print(f"    [green]{t('client_written', name=cc.display_name, path=cc.config_path)}[/green]")
                configured += 1
        else:
            console.print(f"  {t('client_skip', name=cc.display_name)}")

    # 5. Done
    console.print(f"\n[bold green]{t('init_done')}[/bold green]")
    console.print(f"  · {t('init_next_ui')}")
    console.print(f"  · {t('init_next_probe')}")
    if configured > 0:
        console.print(f"  · {t('init_next_restart')}")

    return 0

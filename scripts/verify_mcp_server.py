"""Smoke test: spawn ai-mcp-server (stdio), perform MCP handshake, list tools,
call usage_guide, then exit. Verifies M8 + worker startup integration.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


async def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env["AI_MCP_CONFIG_DIR"] = tmp
        env["AI_MCP_MASTER_KEY"] = Fernet.generate_key().decode("ascii")
        proc = await asyncio.create_subprocess_exec(
            "uv", "run", "ai-mcp-server",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        async def send(msg: dict) -> None:
            assert proc.stdin is not None
            proc.stdin.write((json.dumps(msg) + "\n").encode())
            await proc.stdin.drain()

        async def recv_line() -> dict | None:
            assert proc.stdout is not None
            line = await asyncio.wait_for(proc.stdout.readline(), timeout=15.0)
            if not line:
                return None
            return json.loads(line.decode())

        try:
            # 1. initialize
            await send({
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "smoke", "version": "0"},
                },
            })
            init = await recv_line()
            print("INIT:", init.get("result", {}).get("serverInfo") if init else None)
            # initialized notification
            await send({"jsonrpc": "2.0", "method": "notifications/initialized"})

            # 2. list tools
            await send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            tools = await recv_line()
            names = [t["name"] for t in (tools or {}).get("result", {}).get("tools", [])]
            print("TOOLS:", names)
            assert set(names) == {
                "usage_guide",
                "list_models",
                "invoke_model",
                "model_performance",
                "refresh_endpoint",
                "add_models",
            }, names
            add_models_tool = next(
                t for t in (tools or {}).get("result", {}).get("tools", [])
                if t["name"] == "add_models"
            )
            add_models_props = add_models_tool.get("inputSchema", {}).get("properties", {})
            assert "feature_overrides" in add_models_props, add_models_props

            # 3. call usage_guide
            await send({
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "usage_guide", "arguments": {}},
            })
            ug = await recv_line()
            if ug and "result" in ug:
                content = ug["result"].get("content", [])
                text = content[0].get("text") if content else ""
                print("USAGE_GUIDE first 200 chars:", text[:200])
            else:
                print("USAGE_GUIDE error:", ug)
                return 1
            return 0
        finally:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=3.0)
            except TimeoutError:
                proc.kill()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

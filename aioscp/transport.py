"""
AIOSCP transport implementations — stdio, WebSocket, HTTP.

Transport is how operators talk to the host.
Just like MCP, stdio is the simplest and default.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from aioscp.operator import Operator

logger = logging.getLogger("aioscp.transport")


class BaseTransport:
    """Base class for AIOSCP transports."""

    def __init__(self, operator: "Operator", **kwargs):
        self.operator = operator
        self._pending_requests: dict[str, asyncio.Future] = {}

    async def start(self):
        raise NotImplementedError

    async def send_request(self, request: dict) -> Any:
        raise NotImplementedError

    async def send_notification(self, notification: dict) -> None:
        raise NotImplementedError

    async def _dispatch(self, raw: str) -> Optional[str]:
        """Parse incoming JSON-RPC and route to operator."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return json.dumps({
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": "Parse error"},
                "id": None,
            })

        # Response to a pending request
        if "result" in data or "error" in data:
            msg_id = data.get("id")
            if msg_id and msg_id in self._pending_requests:
                future = self._pending_requests.pop(msg_id)
                if "error" in data:
                    future.set_exception(Exception(data["error"].get("message", "RPC Error")))
                else:
                    future.set_result(data.get("result"))
            return None

        # Incoming request or notification
        method = data.get("method", "")
        params = data.get("params", {})
        msg_id = data.get("id")

        try:
            result = await self.operator._handle_rpc(method, params)

            if msg_id is not None:
                return json.dumps({
                    "jsonrpc": "2.0",
                    "aioscp": "1.0",
                    "result": result,
                    "id": msg_id,
                })
            return None

        except Exception as e:
            logger.error(f"Error handling {method}: {e}")
            if msg_id is not None:
                return json.dumps({
                    "jsonrpc": "2.0",
                    "aioscp": "1.0",
                    "error": {"code": -32603, "message": str(e)},
                    "id": msg_id,
                })
            return None


class StdioTransport(BaseTransport):
    """
    stdio transport — simplest form. Host spawns operator as a child process
    and communicates via stdin/stdout, one JSON-RPC message per line.

    Same pattern as MCP stdio transport.
    """

    async def start(self):
        """Main loop: read from stdin, dispatch, write to stdout."""
        # Send registration on startup
        reg = self.operator.get_registration()
        await self._write(json.dumps({
            "jsonrpc": "2.0",
            "aioscp": "1.0",
            "method": "operator.register",
            "params": reg,
            "id": "reg-init",
        }))

        # Send capability declarations
        for cap_decl in self.operator.get_capability_declarations():
            await self._write(json.dumps({
                "jsonrpc": "2.0",
                "aioscp": "1.0",
                "method": "capability.declare",
                "params": cap_decl,
                "id": f"cap-{cap_decl['id']}",
            }))

        # Read loop
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

        while True:
            try:
                line = await reader.readline()
                if not line:
                    break
                raw = line.decode("utf-8").strip()
                if not raw:
                    continue

                response = await self._dispatch(raw)
                if response:
                    await self._write(response)

            except Exception as e:
                logger.error(f"Transport error: {e}")
                break

    async def send_request(self, request: dict) -> Any:
        msg_id = request["id"]
        future = asyncio.get_event_loop().create_future()
        self._pending_requests[msg_id] = future
        await self._write(json.dumps(request))
        return await future

    async def send_notification(self, notification: dict) -> None:
        await self._write(json.dumps(notification))

    async def _write(self, data: str) -> None:
        sys.stdout.write(data + "\n")
        sys.stdout.flush()


class WebSocketTransport(BaseTransport):
    """
    WebSocket transport — for real-time operators (voice, collaboration).
    Operator connects to the host's WebSocket endpoint.
    """

    def __init__(self, operator: "Operator", host_url: str = "ws://localhost:8200/aioscp", **kwargs):
        super().__init__(operator, **kwargs)
        self.host_url = host_url
        self._ws: Any = None

    async def start(self):
        try:
            import websockets
        except ImportError:
            raise ImportError("Install websockets: pip install websockets")

        async with websockets.connect(self.host_url) as ws:
            self._ws = ws

            # Register
            reg = self.operator.get_registration()
            await self.send_request({
                "jsonrpc": "2.0",
                "aioscp": "1.0",
                "method": "operator.register",
                "params": reg,
                "id": "reg-init",
            })

            # Declare capabilities
            for cap_decl in self.operator.get_capability_declarations():
                await self.send_notification({
                    "jsonrpc": "2.0",
                    "aioscp": "1.0",
                    "method": "capability.declare",
                    "params": cap_decl,
                })

            # Message loop
            async for raw in ws:
                response = await self._dispatch(raw)
                if response:
                    await ws.send(response)

    async def send_request(self, request: dict) -> Any:
        msg_id = request["id"]
        future = asyncio.get_event_loop().create_future()
        self._pending_requests[msg_id] = future
        await self._ws.send(json.dumps(request))
        return await future

    async def send_notification(self, notification: dict) -> None:
        await self._ws.send(json.dumps(notification))


class HTTPTransport(BaseTransport):
    """
    HTTP + SSE transport — for remote/cloud operators.
    Operator exposes an HTTP endpoint. Host sends requests to it.
    Host streams events via SSE for notifications.
    """

    def __init__(self, operator: "Operator", port: int = 8300, host: str = "0.0.0.0", **kwargs):
        super().__init__(operator, **kwargs)
        self.port = port
        self.host = host

    async def start(self):
        try:
            from aiohttp import web
        except ImportError:
            raise ImportError("Install aiohttp: pip install aiohttp")

        app = web.Application()
        app.router.add_post("/aioscp", self._handle_http)
        app.router.add_get("/aioscp/health", self._handle_health_http)
        app.router.add_get("/aioscp/manifest", self._handle_manifest_http)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        logger.info(f"HTTP transport listening on {self.host}:{self.port}")
        await site.start()

        # Keep alive
        while True:
            await asyncio.sleep(3600)

    async def _handle_http(self, request) -> Any:
        from aiohttp import web
        raw = await request.text()
        response = await self._dispatch(raw)
        if response:
            return web.Response(text=response, content_type="application/json")
        return web.Response(status=204)

    async def _handle_health_http(self, request) -> Any:
        from aiohttp import web
        health = await self.operator._on_health({})
        return web.json_response(health)

    async def _handle_manifest_http(self, request) -> Any:
        from aiohttp import web
        return web.json_response({
            "registration": self.operator.get_registration(),
            "capabilities": self.operator.get_capability_declarations(),
        })

    async def send_request(self, request: dict) -> Any:
        # HTTP transport: operator is the server, host is the client
        # For operator-initiated requests, we need to POST to the host
        logger.warning("HTTP transport does not support operator-initiated requests yet")
        return None

    async def send_notification(self, notification: dict) -> None:
        logger.warning("HTTP transport does not support operator-initiated notifications yet")

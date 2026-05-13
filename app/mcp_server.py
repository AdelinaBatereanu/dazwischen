"""Thin MCP adapter for the curated public proxy catalog."""

import json
from contextvars import ContextVar
from typing import Any
from urllib.parse import parse_qs

from mcp import types
from mcp.server import Server
from mcp.server.fastmcp.server import StreamableHTTPASGIApp
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.routing import Route

from app.catalog.registry import CatalogRegistry
from app.models.results import ToolResult
from app.models.tools import PublicTool
from app.routing.errors import tool_not_found
from app.routing.router import ToolRouter

_VERTICAL_FILTER: ContextVar[str | None] = ContextVar("vertical_filter", default=None)


class VerticalFilterASGIMiddleware:
    """Capture ?vertical=<name> from MCP HTTP requests for test-mode filtering."""

    def __init__(self, app: Any) -> None:
        self._app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        token = None
        if scope.get("type") == "http":
            token = _VERTICAL_FILTER.set(_extract_vertical_filter(scope))

        try:
            await self._app(scope, receive, send)
        finally:
            if token is not None:
                _VERTICAL_FILTER.reset(token)


def create_mcp_app(catalog: CatalogRegistry, router: ToolRouter) -> Starlette:
    """Create the streamable HTTP MCP app mounted by FastAPI at /v1/mcp."""
    server = create_mcp_server(catalog=catalog, router=router)
    session_manager = StreamableHTTPSessionManager(
        app=server,
        json_response=True,
        stateless=True,
    )
    endpoint = VerticalFilterASGIMiddleware(StreamableHTTPASGIApp(session_manager))

    return Starlette(
        routes=[Route("/mcp", endpoint=endpoint)],
        lifespan=lambda app: session_manager.run(),
    )


def create_mcp_server(catalog: CatalogRegistry, router: ToolRouter) -> Server:
    """Create the low-level MCP server backed only by catalog and router services."""
    metadata = catalog.get_snapshot().metadata
    server = Server(
        name="dazwischen-mcp-proxy",
        version=metadata.proxy_version,
        instructions=(
            "Use these curated CHECK24 demo tools to search or compare options. "
            "The proxy validates and routes all calls to internal mocked verticals."
        ),
    )

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        vertical_filter = _VERTICAL_FILTER.get()
        # This is for vertical testing. By default this filter is None
        return [_to_mcp_tool(tool) for tool in catalog.list_tools(vertical_filter=vertical_filter)]

    # Disable SDK validation so the router owns argument validation and returns structured errors.
    @server.call_tool(validate_input=False) 
    async def call_tool(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        vertical_filter = _VERTICAL_FILTER.get()
        route = catalog.get_route(name)
        if vertical_filter is not None and (route is None or route.vertical != vertical_filter):
            result = tool_not_found(name)
        else:
            result = router.invoke(name, arguments)
        return _to_call_tool_result(result)

    return server


def _extract_vertical_filter(scope: dict[str, Any]) -> str | None:
    raw_query = scope.get("query_string", b"")
    if isinstance(raw_query, bytes):
        query_string = raw_query.decode("utf-8", errors="ignore")
    else:
        query_string = str(raw_query)

    values = parse_qs(query_string).get("vertical")
    if not values:
        return None

    vertical = values[0].strip().lower()
    return vertical or None


def _to_mcp_tool(tool: PublicTool) -> types.Tool:
    return types.Tool(
        name=tool.name,
        description=tool.description,
        inputSchema=tool.input_schema,
    )


def _to_call_tool_result(result: ToolResult) -> types.CallToolResult:
    if result.ok:
        data = result.data or {}
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(data, indent=2))],
            structuredContent=data,
            isError=False,
        )

    error = result.error.model_dump(mode="json") if result.error is not None else _unknown_error()
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(error, indent=2))],
        structuredContent={"error": error},
        isError=True,
    )


def _unknown_error() -> dict[str, Any]:
    return {
        "code": "UPSTREAM_ERROR",
        "message": "The tool call failed.",
        "details": {},
    }

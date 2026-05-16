"""Adapters between internal MCP servers and proxy-owned models."""

from typing import Any

from mcp import types
from mcp.server import Server

from app.models.tools import CandidateTool
from app.vertical_mcp.base import VerticalMCPClient

_INTERNAL_VERSION_META_KEY = "vertical/internalVersion"
_SAFE_TO_EXPOSE_META_KEY = "vertical/safeToExpose"


class VerticalMCPAdapterError(ValueError):
    """Raised when an internal MCP descriptor cannot be adapted safely."""


class InProcessVerticalMCPClient:
    """Client for an internal vertical MCP server running in this Python process."""

    def __init__(self, name: str, server: Server) -> None:
        self.name = name
        self._server = server

    async def list_tools(self) -> list[types.Tool]:
        request = types.ListToolsRequest()
        result = await self._server.request_handlers[types.ListToolsRequest](request)
        return list(result.root.tools)

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> types.CallToolResult:
        request = types.CallToolRequest(
            params=types.CallToolRequestParams(name=tool_name, arguments=arguments)
        )
        result = await self._server.request_handlers[types.CallToolRequest](request)
        return result.root

    async def list_resources(self) -> list[types.Resource]:
        request = types.ListResourcesRequest()
        result = await self._server.request_handlers[types.ListResourcesRequest](request)
        return list(result.root.resources)

    async def read_resource(self, uri: str) -> list[types.ResourceContents]:
        request = types.ReadResourceRequest(params=types.ReadResourceRequestParams(uri=uri))
        result = await self._server.request_handlers[types.ReadResourceRequest](request)
        return list(result.root.contents)


def mcp_tool_to_candidate(vertical_name: str, tool: types.Tool) -> CandidateTool:
    """Convert an internal MCP tool descriptor into the proxy's candidate model."""
    meta = tool.meta or {}
    internal_version = _required_meta(meta, _INTERNAL_VERSION_META_KEY, tool.name)
    safe_to_expose = _required_meta(meta, _SAFE_TO_EXPOSE_META_KEY, tool.name)

    if not isinstance(internal_version, str):
        raise VerticalMCPAdapterError(
            f"Tool {tool.name!r} metadata {_INTERNAL_VERSION_META_KEY!r} must be a string."
        )
    if not isinstance(safe_to_expose, bool):
        raise VerticalMCPAdapterError(
            f"Tool {tool.name!r} metadata {_SAFE_TO_EXPOSE_META_KEY!r} must be a boolean."
        )

    return CandidateTool(
        vertical=vertical_name,
        upstream_tool=tool.name,
        description=tool.description or "",
        input_schema=tool.inputSchema,
        response_schema=tool.outputSchema,
        safe_to_expose=safe_to_expose,
        internal_version=internal_version,
    )


async def list_candidate_tools(client: VerticalMCPClient) -> list[CandidateTool]:
    """List and adapt candidate tools from one internal vertical MCP client."""
    tools = await client.list_tools()
    return [mcp_tool_to_candidate(client.name, tool) for tool in tools]


def _required_meta(meta: dict[str, Any], key: str, tool_name: str) -> Any:
    if key not in meta:
        raise VerticalMCPAdapterError(f"Tool {tool_name!r} is missing required metadata {key!r}.")
    return meta[key]

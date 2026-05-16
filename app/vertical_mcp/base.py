"""Shared contracts for internal vertical MCP providers.

The proxy talks to vertical providers through this protocol instead of reaching
into MCP server internals directly. Today implementations may be in-process;
later they can be private HTTP/stdio MCP clients without changing catalog or
routing code.
"""

from typing import Any, Protocol

from mcp import types


class VerticalMCPClient(Protocol):
    """Client contract required by the proxy for any internal vertical MCP provider."""

    name: str

    async def list_tools(self) -> list[types.Tool]:
        """Return internal MCP tool descriptors proposed by the vertical."""
        ...

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> types.CallToolResult:
        """Invoke an internal MCP tool by its vertical-owned upstream name."""
        ...

    async def list_resources(self) -> list[types.Resource]:
        """Return internal MCP resources exposed by the vertical for proxy review."""
        ...

    async def read_resource(self, uri: str) -> list[types.ResourceContents]:
        """Read an internal MCP resource by URI."""
        ...

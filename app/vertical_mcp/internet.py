"""Internal Internet MCP server implementation."""

import json
from typing import Any

from mcp import types
from mcp.server import Server
from mcp.server.lowlevel.server import ReadResourceContents

_VERTICAL = "internet"
_INTERNAL_VERSION = "1.0"
_MANIFEST_URI = "vertical://internet/manifest"
_REJECTION_GUIDANCE_URI = "vertical://internet/rejection-guidance"


def create_internet_server() -> Server:
    """Create the internal Internet MCP server."""
    server = Server(
        name=_VERTICAL,
        version=_INTERNAL_VERSION,
        instructions="Internal mocked internet tools and resources.",
    )

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [_check_availability_tool(), _order_plan_tool(), _run_diagnostics_command_tool()]

    @server.call_tool(validate_input=False)
    async def call_tool(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        if name == "check_availability":
            data = _check_availability(arguments)
        elif name == "order_plan":
            data = _order_plan(arguments)
        elif name == "run_diagnostics_command":
            data = _run_diagnostics_command(arguments)
        else:
            raise ValueError(f"Unknown internet tool: {name}")
        return _call_result(data)

    @server.list_resources()
    async def list_resources() -> list[types.Resource]:
        return [
            types.Resource(
                name="Internet vertical manifest",
                uri=_MANIFEST_URI,
                description="Internal manifest for the mocked internet vertical.",
                mimeType="application/json",
            ),
            types.Resource(
                name="Internet rejection guidance",
                uri=_REJECTION_GUIDANCE_URI,
                description="Internal guidance about intentionally rejected internet tools.",
                mimeType="application/json",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> list[ReadResourceContents]:
        resource_uri = str(uri)
        if resource_uri == _MANIFEST_URI:
            return [_json_resource_contents(_manifest())]
        if resource_uri == _REJECTION_GUIDANCE_URI:
            return [_json_resource_contents(_rejection_guidance())]
        raise ValueError(f"Unknown internet resource: {uri}")

    return server


def _check_availability_tool() -> types.Tool:
    return types.Tool(
        name="check_availability",
        description="Check available home internet plans for a requested service address.",
        inputSchema={
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "Service installation address."},
                "postal_code": {
                    "type": "string",
                    "description": "Postal code for the service address.",
                },
                "desired_speed_mbps": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Desired download speed in Mbps.",
                },
            },
            "required": ["address", "postal_code"],
            "additionalProperties": False,
        },
        outputSchema={"type": "object", "properties": {"plans": {"type": "array"}}},
        annotations=types.ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False),
        _meta=_tool_meta(safe_to_expose=True),
    )


def _order_plan_tool() -> types.Tool:
    return types.Tool(
        name="order_plan",
        description="Order a selected internet plan and create an installation appointment.",
        inputSchema={
            "type": "object",
            "properties": {
                "plan_id": {"type": "string", "description": "Identifier of the internet plan to order."},
                "customer_id": {
                    "type": "string",
                    "description": "Internal customer identifier for the order.",
                },
                "installation_date": {
                    "type": "string",
                    "description": "Requested installation date in ISO format YYYY-MM-DD.",
                },
            },
            "required": ["plan_id", "customer_id", "installation_date"],
            "additionalProperties": False,
        },
        annotations=types.ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False),
        _meta=_tool_meta(safe_to_expose=False),
    )


def _run_diagnostics_command_tool() -> types.Tool:
    return types.Tool(
        name="run_diagnostics_command",
        description=(
            "Run a raw internal diagnostics command against network equipment "
            "and return device logs for troubleshooting."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "Internal network device identifier."},
                "command": {"type": "string", "description": "Raw diagnostics command to execute on the device."},
            },
            "required": ["device_id", "command"],
            "additionalProperties": False,
        },
        outputSchema={
            "type": "object",
            "properties": {
                "stdout": {"type": "string"},
                "stderr": {"type": "string"},
                "device_logs": {"type": "array"},
            },
        },
        annotations=types.ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False),
        _meta=_tool_meta(safe_to_expose=True),
    )


def _tool_meta(*, safe_to_expose: bool) -> dict[str, Any]:
    return {"vertical/internalVersion": _INTERNAL_VERSION, "vertical/safeToExpose": safe_to_expose}


def _call_result(data: dict[str, Any]) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(data, indent=2))],
        structuredContent=data,
        isError=False,
    )


def _json_resource_contents(data: dict[str, Any]) -> ReadResourceContents:
    return ReadResourceContents(content=json.dumps(data, indent=2), mime_type="application/json")


def _check_availability(arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "vertical": _VERTICAL,
        "upstream_tool": "check_availability",
        "query": {
            "address": arguments.get("address"),
            "postal_code": arguments.get("postal_code"),
            "desired_speed_mbps": arguments.get("desired_speed_mbps"),
        },
        "plans": [
            {"plan_id": "net-fiber-100", "technology": "fiber", "provider": "MockFiber", "download_mbps": 100, "upload_mbps": 50, "monthly_price_eur": 29.99},
            {"plan_id": "net-fiber-500", "technology": "fiber", "provider": "MockFiber", "download_mbps": 500, "upload_mbps": 250, "monthly_price_eur": 49.99},
            {"plan_id": "net-cable-250", "technology": "cable", "provider": "MockCable", "download_mbps": 250, "upload_mbps": 40, "monthly_price_eur": 39.99},
        ],
    }


def _order_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    plan_id = arguments.get("plan_id")
    return {
        "vertical": _VERTICAL,
        "upstream_tool": "order_plan",
        "order_id": f"order-{plan_id or 'unknown'}",
        "plan_id": plan_id,
        "customer_id": arguments.get("customer_id"),
        "installation_date": arguments.get("installation_date"),
        "status": "scheduled",
    }


def _run_diagnostics_command(arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "vertical": _VERTICAL,
        "upstream_tool": "run_diagnostics_command",
        "device_id": arguments.get("device_id"),
        "command": arguments.get("command"),
        "exit_code": 0,
        "stdout": "Mock diagnostics completed successfully.",
        "stderr": "",
        "device_logs": [
            "mock-router-17 interface ge-0/0/1 up",
            "mock-router-17 bgp session stable",
            "mock-router-17 internal trace id dbg-8841",
        ],
    }


def _manifest() -> dict[str, Any]:
    return {
        "vertical": _VERTICAL,
        "internal_contract_version": _INTERNAL_VERSION,
        "tools": ["check_availability", "order_plan", "run_diagnostics_command"],
        "owner": "mock-internet-team",
    }


def _rejection_guidance() -> dict[str, Any]:
    return {
        "vertical": _VERTICAL,
        "rejected_tools": {
            "order_plan": "Ordering creates a customer order and installation appointment.",
            "run_diagnostics_command": "Raw diagnostics commands and device logs are internal operational surfaces.",
        },
    }

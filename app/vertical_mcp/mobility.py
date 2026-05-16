"""Internal Mobility MCP server implementation."""

import json
from typing import Any

from mcp import types
from mcp.server import Server
from mcp.server.lowlevel.server import ReadResourceContents

_VERTICAL = "mobility"
_INTERNAL_VERSION = "1.0"

_SEARCH_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "origin": {
            "type": "string",
            "description": "Trip origin city, station, or address.",
        },
        "destination": {
            "type": "string",
            "description": "Trip destination city, station, or address.",
        },
        "date": {
            "type": "string",
            "description": "Desired travel date in ISO format YYYY-MM-DD.",
        },
        "passengers": {
            "type": "integer",
            "minimum": 1,
            "description": "Number of passengers travelling.",
        },
    },
    "required": ["origin", "destination", "date"],
    "additionalProperties": False,
}

_SEARCH_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "options": {"type": "array"},
    },
}

_BOOK_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "option_id": {
            "type": "string",
            "description": "Identifier of the mobility option to book.",
        },
        "payment_token": {
            "type": "string",
            "description": "Payment token used to complete the booking.",
        },
    },
    "required": ["option_id", "payment_token"],
    "additionalProperties": False,
}

_MANIFEST_URI = "vertical://mobility/manifest"
_REJECTION_GUIDANCE_URI = "vertical://mobility/rejection-guidance"


def create_mobility_server() -> Server:
    """Create the internal Mobility MCP server.

    This server is intended to be consumed by the proxy only. It is not mounted as
    a public ChatGPT-facing endpoint.
    """
    server = Server(
        name=_VERTICAL,
        version=_INTERNAL_VERSION,
        instructions="Internal mocked mobility tools and resources.",
    )

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [_search_tool(), _book_tool()]

    @server.call_tool(validate_input=False)
    async def call_tool(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        if name == "search":
            data = _search(arguments)
        elif name == "book":
            data = _book(arguments)
        else:
            raise ValueError(f"Unknown mobility tool: {name}")

        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(data, indent=2))],
            structuredContent=data,
            isError=False,
        )

    @server.list_resources()
    async def list_resources() -> list[types.Resource]:
        return [
            types.Resource(
                name="Mobility vertical manifest",
                uri=_MANIFEST_URI,
                description="Internal manifest for the mocked mobility vertical.",
                mimeType="application/json",
            ),
            types.Resource(
                name="Mobility rejection guidance",
                uri=_REJECTION_GUIDANCE_URI,
                description="Internal guidance about intentionally rejected mobility tools.",
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
        raise ValueError(f"Unknown mobility resource: {uri}")

    return server


def _search_tool() -> types.Tool:
    return types.Tool(
        name="search",
        description=(
            "Search available mobility options such as rental cars, trains, "
            "and shared transport for a requested trip."
        ),
        inputSchema=_SEARCH_INPUT_SCHEMA,
        outputSchema=_SEARCH_OUTPUT_SCHEMA,
        annotations=types.ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            openWorldHint=False,
        ),
        _meta=_tool_meta(safe_to_expose=True),
    )


def _book_tool() -> types.Tool:
    return types.Tool(
        name="book",
        description="Book a selected mobility option and commit the customer to the trip.",
        inputSchema=_BOOK_INPUT_SCHEMA,
        annotations=types.ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            openWorldHint=False,
        ),
        _meta=_tool_meta(safe_to_expose=False),
    )


def _tool_meta(*, safe_to_expose: bool) -> dict[str, Any]:
    return {
        "vertical/internalVersion": _INTERNAL_VERSION,
        "vertical/safeToExpose": safe_to_expose,
    }


def _json_resource_contents(data: dict[str, Any]) -> ReadResourceContents:
    return ReadResourceContents(
        content=json.dumps(data, indent=2),
        mime_type="application/json",
    )


def _search(arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "vertical": _VERTICAL,
        "upstream_tool": "search",
        "query": {
            "origin": arguments.get("origin"),
            "destination": arguments.get("destination"),
            "date": arguments.get("date"),
            "passengers": arguments.get("passengers", 1),
        },
        "options": [
            {
                "option_id": "mob-train-001",
                "type": "train",
                "provider": "MockRail",
                "duration_minutes": 95,
                "price_eur": 29.9,
            },
            {
                "option_id": "mob-car-002",
                "type": "rental_car",
                "provider": "MockDrive",
                "duration_minutes": 80,
                "price_eur": 54.5,
            },
        ],
    }


def _book(arguments: dict[str, Any]) -> dict[str, Any]:
    option_id = arguments.get("option_id")
    return {
        "vertical": _VERTICAL,
        "upstream_tool": "book",
        "booking_id": f"booking-{option_id or 'unknown'}",
        "option_id": option_id,
        "status": "confirmed",
        "payment_status": "authorized" if arguments.get("payment_token") else "missing_payment_token",
    }


def _manifest() -> dict[str, Any]:
    return {
        "vertical": _VERTICAL,
        "internal_contract_version": _INTERNAL_VERSION,
        "tools": ["search", "book"],
        "owner": "mock-mobility-team",
    }


def _rejection_guidance() -> dict[str, Any]:
    return {
        "vertical": _VERTICAL,
        "rejected_tools": {
            "book": "Booking commits the customer to a trip and is intentionally destructive.",
        },
    }

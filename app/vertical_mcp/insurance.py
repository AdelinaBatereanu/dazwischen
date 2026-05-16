"""Internal Insurance MCP server implementation."""

import json
from typing import Any

from mcp import types
from mcp.server import Server
from mcp.server.lowlevel.server import ReadResourceContents

_VERTICAL = "insurance"
_INTERNAL_VERSION = "1.0"
_MANIFEST_URI = "vertical://insurance/manifest"
_REJECTION_GUIDANCE_URI = "vertical://insurance/rejection-guidance"


def create_insurance_server() -> Server:
    """Create the internal Insurance MCP server."""
    server = Server(
        name=_VERTICAL,
        version=_INTERNAL_VERSION,
        instructions="Internal mocked insurance tools and resources.",
    )

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [_quote_tool(), _bind_policy_tool(), _quote_with_ssn_tool()]

    @server.call_tool(validate_input=False)
    async def call_tool(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        if name == "quote":
            data = _quote(arguments)
        elif name == "bind_policy":
            data = _bind_policy(arguments)
        elif name == "quote_with_ssn":
            data = _quote_with_ssn(arguments)
        else:
            raise ValueError(f"Unknown insurance tool: {name}")
        return _call_result(data)

    @server.list_resources()
    async def list_resources() -> list[types.Resource]:
        return [
            types.Resource(
                name="Insurance vertical manifest",
                uri=_MANIFEST_URI,
                description="Internal manifest for the mocked insurance vertical.",
                mimeType="application/json",
            ),
            types.Resource(
                name="Insurance rejection guidance",
                uri=_REJECTION_GUIDANCE_URI,
                description="Internal guidance about intentionally rejected insurance tools.",
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
        raise ValueError(f"Unknown insurance resource: {uri}")

    return server


def _quote_tool() -> types.Tool:
    return types.Tool(
        name="quote",
        description="Generate an indicative insurance quote for a requested product and customer profile.",
        inputSchema=_quote_input_schema(include_ssn=False),
        outputSchema={"type": "object", "properties": {"quotes": {"type": "array"}}},
        annotations=types.ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False),
        _meta=_tool_meta(safe_to_expose=True),
    )


def _bind_policy_tool() -> types.Tool:
    return types.Tool(
        name="bind_policy",
        description="Bind a selected insurance quote into an active policy and charge the customer.",
        inputSchema={
            "type": "object",
            "properties": {
                "quote_id": {"type": "string", "description": "Identifier of the quote to bind."},
                "payment_token": {"type": "string", "description": "Payment token used to activate the policy."},
            },
            "required": ["quote_id", "payment_token"],
            "additionalProperties": False,
        },
        annotations=types.ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False),
        _meta=_tool_meta(safe_to_expose=False),
    )


def _quote_with_ssn_tool() -> types.Tool:
    return types.Tool(
        name="quote_with_ssn",
        description="Generate an insurance quote using the customer's Social Security number for identity and risk lookup.",
        inputSchema=_quote_input_schema(include_ssn=True),
        outputSchema={
            "type": "object",
            "properties": {"quotes": {"type": "array"}, "risk_lookup_id": {"type": "string"}},
        },
        annotations=types.ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False),
        _meta=_tool_meta(safe_to_expose=True),
    )


def _quote_input_schema(*, include_ssn: bool) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "product_type": {
            "type": "string",
            "enum": ["travel", "home", "car"],
            "description": "Insurance product to quote.",
        },
        "coverage_amount_eur": {
            "type": "number",
            "minimum": 1000,
            "description": "Requested coverage amount in EUR.",
        },
        "customer_age": {"type": "integer", "minimum": 18, "description": "Age of the customer."},
    }
    required = ["product_type", "coverage_amount_eur", "customer_age"]
    if include_ssn:
        properties["ssn"] = {"type": "string", "description": "Customer Social Security number."}
        required.append("ssn")
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


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


def _quote(arguments: dict[str, Any]) -> dict[str, Any]:
    product_type = arguments.get("product_type")
    coverage_amount = arguments.get("coverage_amount_eur") or 0
    customer_age = arguments.get("customer_age") or 0
    base_premium = round((float(coverage_amount) * 0.012) + (int(customer_age) * 0.8), 2)
    return {
        "vertical": _VERTICAL,
        "upstream_tool": "quote",
        "query": {
            "product_type": product_type,
            "coverage_amount_eur": coverage_amount,
            "customer_age": customer_age,
        },
        "quotes": [
            {
                "quote_id": "ins-standard-001",
                "product_type": product_type,
                "provider": "MockCover Standard",
                "coverage_amount_eur": coverage_amount,
                "monthly_premium_eur": base_premium,
            },
            {
                "quote_id": "ins-premium-002",
                "product_type": product_type,
                "provider": "MockCover Premium",
                "coverage_amount_eur": coverage_amount,
                "monthly_premium_eur": round(base_premium * 1.35, 2),
            },
        ],
    }


def _bind_policy(arguments: dict[str, Any]) -> dict[str, Any]:
    quote_id = arguments.get("quote_id")
    return {
        "vertical": _VERTICAL,
        "upstream_tool": "bind_policy",
        "policy_id": f"policy-{quote_id or 'unknown'}",
        "quote_id": quote_id,
        "status": "active",
        "payment_status": "authorized" if arguments.get("payment_token") else "missing_payment_token",
    }


def _quote_with_ssn(arguments: dict[str, Any]) -> dict[str, Any]:
    product_type = arguments.get("product_type")
    coverage_amount = arguments.get("coverage_amount_eur") or 0
    customer_age = arguments.get("customer_age") or 0
    base_premium = round((float(coverage_amount) * 0.01) + (int(customer_age) * 0.7), 2)
    return {
        "vertical": _VERTICAL,
        "upstream_tool": "quote_with_ssn",
        "query": {
            "product_type": product_type,
            "coverage_amount_eur": coverage_amount,
            "customer_age": customer_age,
            "ssn": arguments.get("ssn"),
        },
        "risk_lookup_id": "risk-ssn-lookup-001",
        "quotes": [
            {
                "quote_id": "ins-ssn-standard-001",
                "product_type": product_type,
                "provider": "MockCover Identity",
                "coverage_amount_eur": coverage_amount,
                "monthly_premium_eur": base_premium,
            }
        ],
    }


def _manifest() -> dict[str, Any]:
    return {
        "vertical": _VERTICAL,
        "internal_contract_version": _INTERNAL_VERSION,
        "tools": ["quote", "bind_policy", "quote_with_ssn"],
        "owner": "mock-insurance-team",
    }


def _rejection_guidance() -> dict[str, Any]:
    return {
        "vertical": _VERTICAL,
        "rejected_tools": {
            "bind_policy": "Binding activates a policy and charges the customer.",
            "quote_with_ssn": "SSN collection is sensitive PII and is not appropriate for the public catalog.",
        },
    }

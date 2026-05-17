"""Tests for internal vertical MCP providers."""

import json

import pytest
from mcp import types

from app.catalog.builder import CatalogBuilder
from app.catalog.registry import CatalogRegistry
from app.catalog.versioning import CatalogVersionProvider
from app.routing.router import ToolRouter
from app.validation.conformance import ToolConformanceValidator
from app.vertical_mcp.adapters import (
    InProcessVerticalMCPClient,
    VerticalMCPAdapterError,
    list_candidate_tools,
    mcp_tool_to_candidate,
)
from app.vertical_mcp.insurance import create_insurance_server
from app.vertical_mcp.internet import create_internet_server
from app.vertical_mcp.mobility import create_mobility_server


@pytest.mark.anyio
async def test_mobility_server_exposes_internal_resources() -> None:
    server = create_mobility_server()

    result = await server.request_handlers[types.ListResourcesRequest](types.ListResourcesRequest())

    resources = result.root.resources
    assert {str(resource.uri) for resource in resources} == {
        "vertical://mobility/manifest",
        "vertical://mobility/rejection-guidance",
    }
    assert all(resource.mimeType == "application/json" for resource in resources)


@pytest.mark.anyio
async def test_mobility_manifest_resource_can_be_read() -> None:
    server = create_mobility_server()
    request = types.ReadResourceRequest(
        params=types.ReadResourceRequestParams(uri="vertical://mobility/manifest")
    )

    result = await server.request_handlers[types.ReadResourceRequest](request)

    contents = result.root.contents
    assert len(contents) == 1
    content = contents[0]
    assert isinstance(content, types.TextResourceContents)
    assert content.mimeType == "application/json"

    manifest = json.loads(content.text)
    assert manifest == {
        "vertical": "mobility",
        "internal_contract_version": "1.0",
        "tools": ["search", "book"],
        "owner": "mock-mobility-team",
    }


@pytest.mark.anyio
async def test_in_process_client_calls_mobility_server() -> None:
    client = InProcessVerticalMCPClient("mobility", create_mobility_server())

    tools = await client.list_tools()
    result = await client.call_tool(
        "search",
        {"origin": "Berlin", "destination": "Hamburg", "date": "2026-06-01"},
    )

    assert [tool.name for tool in tools] == ["search", "book"]
    assert result.isError is False
    assert result.structuredContent is not None
    assert result.structuredContent["vertical"] == "mobility"
    assert result.structuredContent["upstream_tool"] == "search"


@pytest.mark.anyio
async def test_mcp_tool_descriptors_adapt_to_candidate_tools() -> None:
    client = InProcessVerticalMCPClient("mobility", create_mobility_server())

    candidates = await list_candidate_tools(client)

    assert [candidate.upstream_tool for candidate in candidates] == ["search", "book"]
    assert candidates[0].vertical == "mobility"
    assert candidates[0].safe_to_expose is True
    assert candidates[0].internal_version == "1.0"
    assert candidates[0].input_schema["type"] == "object"
    assert candidates[0].response_schema == {
        "type": "object",
        "properties": {"options": {"type": "array"}},
    }
    assert candidates[1].safe_to_expose is False


def test_adapter_rejects_missing_or_mistyped_required_vertical_metadata() -> None:
    base_tool = {
        "name": "search",
        "description": "Search available mobility options for a requested trip.",
        "inputSchema": {
            "type": "object",
            "properties": {"origin": {"type": "string"}},
            "required": ["origin"],
        },
    }

    missing_version = types.Tool(
        **base_tool,
        _meta={"vertical/safeToExpose": True},
    )
    wrong_safe_type = types.Tool(
        **base_tool,
        _meta={"vertical/internalVersion": "1.0", "vertical/safeToExpose": "yes"},
    )

    with pytest.raises(VerticalMCPAdapterError, match="vertical/internalVersion"):
        mcp_tool_to_candidate("mobility", missing_version)

    with pytest.raises(VerticalMCPAdapterError, match="vertical/safeToExpose"):
        mcp_tool_to_candidate("mobility", wrong_safe_type)


@pytest.mark.anyio
async def test_catalog_can_be_built_from_mobility_mcp_client() -> None:
    client = InProcessVerticalMCPClient("mobility", create_mobility_server())
    builder = CatalogBuilder(
        validator=ToolConformanceValidator(),
        version_provider=CatalogVersionProvider(),
    )

    snapshot = await builder.build_from_mcp_clients([client])
    catalog = CatalogRegistry(snapshot)

    assert [tool.name for tool in catalog.list_tools()] == ["search_mobility_options"]
    assert catalog.get_route("search_mobility_options") is not None
    assert catalog.get_route("search_mobility_options").vertical == "mobility"  # type: ignore[union-attr]

    report = catalog.get_validation_report()
    rejected_tools = {
        result.tool for result in report.results if result.status == "rejected"
    }
    assert "book" in rejected_tools


@pytest.mark.anyio
async def test_router_invokes_internal_mobility_mcp_client() -> None:
    client = InProcessVerticalMCPClient("mobility", create_mobility_server())
    snapshot = await CatalogBuilder(
        validator=ToolConformanceValidator(),
        version_provider=CatalogVersionProvider(),
    ).build_from_mcp_clients([client])
    router = ToolRouter(CatalogRegistry(snapshot), vertical_mcp_clients=[client])

    result = await router.invoke(
        "search_mobility_options",
        {"origin": "Berlin", "destination": "Hamburg", "date": "2026-06-01"},
    )

    assert result.ok is True
    assert result.data is not None
    assert result.data["vertical"] == "mobility"
    assert result.data["upstream_tool"] == "search"


@pytest.mark.anyio
async def test_catalog_can_be_built_from_all_vertical_mcp_clients() -> None:
    clients = [
        InProcessVerticalMCPClient("mobility", create_mobility_server()),
        InProcessVerticalMCPClient("internet", create_internet_server()),
        InProcessVerticalMCPClient("insurance", create_insurance_server()),
    ]

    snapshot = await CatalogBuilder(
        validator=ToolConformanceValidator(),
        version_provider=CatalogVersionProvider(),
    ).build_from_mcp_clients(clients)
    catalog = CatalogRegistry(snapshot)

    assert [tool.name for tool in catalog.list_tools()] == [
        "search_mobility_options",
        "compare_internet_plans",
        "compare_insurance_offers",
    ]

    report = catalog.get_validation_report()
    rejected_tools = {
        result.tool for result in report.results if result.status == "rejected"
    }
    assert rejected_tools == {
        "book",
        "order_plan",
        "run_diagnostics_command",
        "bind_policy",
        "quote_with_ssn",
    }

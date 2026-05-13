import asyncio
from typing import Any

from fastapi.testclient import TestClient
from mcp import types

from app.catalog.registry import CatalogRegistry
from app.main import create_app, create_catalog_registry, create_verticals
from app.mcp_server import _VERTICAL_FILTER, create_mcp_server
from app.routing.router import ToolRouter


def run_async[T](awaitable: Any) -> T:
    return asyncio.run(awaitable)


def create_server() -> Any:
    verticals = create_verticals()
    catalog = create_catalog_registry(verticals)
    router = ToolRouter(catalog=catalog, verticals=verticals)
    return create_mcp_server(catalog=catalog, router=router)


def list_mcp_tools(server: Any) -> list[types.Tool]:
    handler = server.request_handlers[types.ListToolsRequest]
    result = run_async(handler(types.ListToolsRequest()))
    return result.root.tools


def call_mcp_tool(server: Any, name: str, arguments: dict[str, Any]) -> types.CallToolResult:
    handler = server.request_handlers[types.CallToolRequest]
    request = types.CallToolRequest(
        params=types.CallToolRequestParams(name=name, arguments=arguments),
    )
    result = run_async(handler(request))
    return result.root


def test_fastapi_app_composes_runtime_components_and_debug_endpoints() -> None:
    app = create_app()

    assert isinstance(app.state.catalog, CatalogRegistry)
    assert isinstance(app.state.router, ToolRouter)
    assert {vertical.name for vertical in app.state.verticals} == {"mobility", "internet", "insurance"}

    with TestClient(app) as client:
        health = client.get("/health")
        catalog = client.get("/debug/catalog")
        report = client.get("/debug/validation-report")

    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "proxy_version": "1.0.0",
        "catalog_version": "2026-05-02.1",
        "public_endpoint_version": "v1",
    }

    assert catalog.status_code == 200
    catalog_body = catalog.json()
    assert catalog_body["metadata"]["public_endpoint_version"] == "v1"
    assert {tool["name"] for tool in catalog_body["tools"]} == {
        "search_mobility_options",
        "compare_internet_plans",
        "compare_insurance_offers",
    }

    assert report.status_code == 200
    report_body = report.json()
    statuses = {(entry["vertical"], entry["tool"]): entry["status"] for entry in report_body["results"]}
    assert statuses[("mobility", "search")] == "accepted"
    assert statuses[("mobility", "book")] == "rejected"


def test_mcp_adapter_lists_only_curated_public_tools() -> None:
    server = create_server()

    tools = list_mcp_tools(server)

    assert {tool.name for tool in tools} == {
        "search_mobility_options",
        "compare_internet_plans",
        "compare_insurance_offers",
    }
    assert all(tool.description for tool in tools)
    assert all(tool.inputSchema["type"] == "object" for tool in tools)


def test_mcp_adapter_calls_router_and_returns_structured_success() -> None:
    server = create_server()

    result = call_mcp_tool(
        server,
        "search_mobility_options",
        {
            "origin": "Munich",
            "destination": "Berlin",
            "date": "2026-06-01",
        },
    )

    assert result.isError is False
    assert result.structuredContent is not None
    assert result.structuredContent["vertical"] == "mobility"
    assert result.structuredContent["upstream_tool"] == "search"
    assert result.content[0].type == "text"


def test_mcp_adapter_returns_safe_structured_error_for_invalid_call() -> None:
    server = create_server()

    result = call_mcp_tool(server, "search_mobility_options", {"origin": "Munich"})

    assert result.isError is True
    assert result.structuredContent is not None
    error = result.structuredContent["error"]
    assert error["code"] == "INVALID_ARGUMENTS"
    assert error["message"]


def test_mcp_adapter_vertical_filter_limits_listed_and_callable_tools() -> None:
    server = create_server()
    token = _VERTICAL_FILTER.set("mobility")
    try:
        tools = list_mcp_tools(server)
        blocked_call = call_mcp_tool(
            server,
            "compare_internet_plans",
            {"address": "Main Street 1", "postal_code": "80331"},
        )
    finally:
        _VERTICAL_FILTER.reset(token)

    assert [tool.name for tool in tools] == ["search_mobility_options"]
    assert blocked_call.isError is True
    assert blocked_call.structuredContent is not None
    assert blocked_call.structuredContent["error"]["code"] == "TOOL_NOT_FOUND"

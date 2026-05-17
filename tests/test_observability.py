from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.catalog.builder import CatalogBuilder
from app.catalog.registry import CatalogRegistry
from app.catalog.versioning import CatalogVersionProvider
from app.main import create_app
from app.models.observability import InvocationSource
from app.observability.store import ObservabilityStore
from app.routing.router import ToolRouter
from app.validation.conformance import ToolConformanceValidator
from app.vertical_mcp.adapters import InProcessVerticalMCPClient
from app.vertical_mcp.mobility import create_mobility_server


def valid_mobility_args(**overrides: object) -> dict[str, Any]:
    args: dict[str, Any] = {
        "origin": "Munich",
        "destination": "Berlin",
        "date": "2026-06-01",
    }
    args.update(overrides)
    return args


@pytest.mark.anyio
async def test_router_successful_tool_call_records_observability_event() -> None:
    client = InProcessVerticalMCPClient("mobility", create_mobility_server())
    snapshot = await CatalogBuilder(
        validator=ToolConformanceValidator(),
        version_provider=CatalogVersionProvider(),
    ).build_from_mcp_clients([client])
    catalog = CatalogRegistry(snapshot)
    observability = ObservabilityStore()
    router = ToolRouter(catalog=catalog, vertical_mcp_clients=[client], observability=observability)

    result = await router.invoke(
        "search_mobility_options",
        valid_mobility_args(),
        request_id="req-1",
        conversation_id="conv-1",
    )

    assert result.ok is True
    events = observability.list_events()
    assert len(events) == 1
    event = events[0]
    assert event.request_id == "req-1"
    assert event.conversation_id == "conv-1"
    assert event.source == InvocationSource.MCP
    assert event.public_tool_name == "search_mobility_options"
    assert event.vertical == "mobility"
    assert event.upstream_tool == "search"
    assert event.ok is True
    assert event.error_code is None


@pytest.mark.anyio
async def test_router_failed_tool_call_records_safe_error_code() -> None:
    client = InProcessVerticalMCPClient("mobility", create_mobility_server())
    snapshot = await CatalogBuilder(
        validator=ToolConformanceValidator(),
        version_provider=CatalogVersionProvider(),
    ).build_from_mcp_clients([client])
    catalog = CatalogRegistry(snapshot)
    observability = ObservabilityStore()
    router = ToolRouter(catalog=catalog, vertical_mcp_clients=[client], observability=observability)

    result = await router.invoke(
        "search_mobility_options",
        {"origin": "Munich"},
        request_id="req-bad",
        conversation_id="conv-errors",
    )

    assert result.ok is False
    events = observability.list_events()
    assert len(events) == 1
    assert events[0].error_code == "INVALID_ARGUMENTS"
    assert events[0].ok is False


def test_monitoring_and_recent_failures_endpoints_summarize_observed_calls() -> None:
    app = create_app()

    with TestClient(app) as client:
        client.post(
            "/debug/sandbox/invoke",
            json={
                "tool_name": "search_mobility_options",
                "arguments": valid_mobility_args(),
                "conversation_id": "conv-monitoring",
            },
        )
        client.post(
            "/debug/sandbox/invoke",
            json={
                "tool_name": "search_mobility_options",
                "arguments": {"origin": "Munich"},
                "conversation_id": "conv-monitoring",
            },
        )

        monitoring = client.get("/debug/monitoring")
        failures = client.get("/debug/recent-failures")

    assert monitoring.status_code == 200
    monitoring_body = monitoring.json()
    assert monitoring_body["total_calls"] == 2
    assert monitoring_body["successes"] == 1
    assert monitoring_body["errors"] == 1
    assert monitoring_body["by_vertical"]["mobility"]["calls"] == 2
    assert monitoring_body["by_vertical"]["mobility"]["errors"] == 1

    assert failures.status_code == 200
    failure_body = failures.json()
    assert len(failure_body["failures"]) == 1
    assert failure_body["failures"][0]["error_code"] == "INVALID_ARGUMENTS"
    assert "origin" not in str(failure_body)


def test_conversation_endpoints_group_calls_by_conversation_id() -> None:
    app = create_app()

    with TestClient(app) as client:
        client.post(
            "/debug/sandbox/invoke",
            json={
                "tool_name": "search_mobility_options",
                "arguments": valid_mobility_args(),
                "conversation_id": "conv-demo",
            },
        )
        conversations = client.get("/debug/conversations")
        detail = client.get("/debug/conversations/conv-demo")
        missing = client.get("/debug/conversations/does-not-exist")

    assert conversations.status_code == 200
    assert conversations.json()["conversations"][0]["conversation_id"] == "conv-demo"

    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["conversation_id"] == "conv-demo"
    assert detail_body["calls"] == 1
    assert detail_body["tool_counts"] == {"search_mobility_options": 1}
    assert detail_body["vertical_counts"] == {"mobility": 1}
    assert detail_body["events"][0]["source"] == "sandbox"

    assert missing.status_code == 404


def test_sandbox_lists_only_accepted_tools_and_invokes_through_router() -> None:
    app = create_app()

    with TestClient(app) as client:
        tools = client.get("/debug/sandbox/tools?vertical=mobility")
        result = client.post(
            "/debug/sandbox/invoke",
            json={
                "tool_name": "search_mobility_options",
                "arguments": valid_mobility_args(),
                "conversation_id": "conv-sandbox",
            },
        )

    assert tools.status_code == 200
    tool_names = {tool["name"] for tool in tools.json()["tools"]}
    assert tool_names == {"search_mobility_options"}
    assert "book" not in tool_names

    assert result.status_code == 200
    body = result.json()
    assert body["result"]["ok"] is True
    assert body["result"]["data"]["vertical"] == "mobility"
    assert body["result"]["data"]["upstream_tool"] == "search"


def test_sandbox_vertical_filter_blocks_other_vertical_invocation() -> None:
    app = create_app()

    with TestClient(app) as client:
        result = client.post(
            "/debug/sandbox/invoke",
            json={
                "tool_name": "compare_internet_plans",
                "arguments": {"address": "Main Street 1", "postal_code": "80331"},
                "vertical": "mobility",
            },
        )

    assert result.status_code == 200
    body = result.json()
    assert body["result"]["ok"] is False
    assert body["result"]["error"]["code"] == "TOOL_NOT_FOUND"


def test_verticals_endpoint_reports_catalog_and_observability_status() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/debug/verticals")

    assert response.status_code == 200
    verticals = {vertical["name"]: vertical for vertical in response.json()["verticals"]}
    assert set(verticals) == {"mobility", "internet", "insurance"}
    assert verticals["mobility"]["accepted_tools"] == 1
    assert verticals["mobility"]["rejected_tools"] >= 1
    assert verticals["mobility"]["status"] == "green"

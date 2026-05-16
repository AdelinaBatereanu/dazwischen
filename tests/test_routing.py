from typing import Any

import pytest
from mcp import types

from app.catalog.builder import CatalogBuilder
from app.catalog.registry import CatalogRegistry
from app.catalog.versioning import CatalogVersionProvider
from app.models.results import ToolResult
from app.models.tools import CandidateTool
from app.routing.errors import RoutingErrorCode
from app.routing.router import ToolRouter
from app.validation.conformance import ToolConformanceValidator
from app.vertical_mcp.adapters import InProcessVerticalMCPClient, list_candidate_tools
from app.vertical_mcp.mobility import create_mobility_server


class StubMCPClient:
    """Routing test double with configurable MCP invocation behavior."""

    def __init__(
        self,
        *,
        name: str = "mobility",
        response: Any | None = None,
        exception: Exception | None = None,
    ) -> None:
        self.name = name
        self._response = {"stub": "ok"} if response is None else response
        self._exception = exception
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self) -> list[types.Tool]:
        return []

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        self.calls.append((tool_name, arguments))
        if self._exception is not None:
            raise self._exception
        return types.CallToolResult(
            content=[types.TextContent(type="text", text="{}")],
            structuredContent=self._response if isinstance(self._response, dict) else None,
            isError=False,
        )

    async def list_resources(self) -> list[types.Resource]:
        return []

    async def read_resource(self, uri: str) -> list[types.ResourceContents]:
        return []


def valid_mobility_args(**overrides: object) -> dict[str, Any]:
    args: dict[str, Any] = {
        "origin": "Munich",
        "destination": "Berlin",
        "date": "2026-06-01",
    }
    args.update(overrides)
    return args


async def build_registry(candidates: list[CandidateTool] | None = None) -> CatalogRegistry:
    if candidates is None:
        candidates = await list_candidate_tools(
            InProcessVerticalMCPClient("mobility", create_mobility_server())
        )
    snapshot = CatalogBuilder(
        validator=ToolConformanceValidator(),
        version_provider=CatalogVersionProvider(),
    ).build_from_candidates(candidates)
    return CatalogRegistry(snapshot)


def assert_error(result: ToolResult, code: RoutingErrorCode) -> None:
    assert result.ok is False
    assert result.data is None
    assert result.error is not None
    assert result.error.code == code.value
    assert result.error.message


@pytest.mark.anyio
async def test_public_tool_routes_to_correct_vertical_and_upstream_tool() -> None:
    client = StubMCPClient(response={"vertical": "mobility", "options": []})
    router = ToolRouter(await build_registry(), [client])
    arguments = valid_mobility_args(passengers=2)

    result = await router.invoke("search_mobility_options", arguments, request_id="req-123")

    assert result.ok is True
    assert result.error is None
    assert result.data == {"vertical": "mobility", "options": []}
    assert client.calls == [("search", arguments)]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "arguments",
    [
        {"origin": "Munich", "date": "2026-06-01"},
        valid_mobility_args(passengers=0),
        valid_mobility_args(unapproved="extra"),
        ["not", "an", "object"],
    ],
)
async def test_invalid_arguments_return_invalid_arguments_without_calling_vertical(arguments: Any) -> None:
    client = StubMCPClient()
    router = ToolRouter(await build_registry(), [client])

    result = await router.invoke("search_mobility_options", arguments)

    assert_error(result, RoutingErrorCode.INVALID_ARGUMENTS)
    assert result.error is not None
    assert result.error.details
    assert client.calls == []


@pytest.mark.anyio
async def test_unknown_public_tool_returns_tool_not_found() -> None:
    client = StubMCPClient()
    router = ToolRouter(await build_registry(), [client])

    result = await router.invoke("book", {"option_id": "mob-train-001"})

    assert_error(result, RoutingErrorCode.TOOL_NOT_FOUND)
    assert result.error is not None
    assert result.error.details == {"tool": "book"}
    assert client.calls == []


@pytest.mark.anyio
async def test_missing_configured_vertical_returns_vertical_unavailable() -> None:
    router = ToolRouter(await build_registry(), [])

    result = await router.invoke("search_mobility_options", valid_mobility_args())

    assert_error(result, RoutingErrorCode.VERTICAL_UNAVAILABLE)


@pytest.mark.anyio
async def test_upstream_timeout_returns_safe_timeout_error() -> None:
    client = StubMCPClient(exception=TimeoutError("private upstream timeout details"))
    router = ToolRouter(await build_registry(), [client])

    result = await router.invoke("search_mobility_options", valid_mobility_args())

    assert_error(result, RoutingErrorCode.UPSTREAM_TIMEOUT)
    assert result.error is not None
    assert "private upstream timeout details" not in result.error.message


@pytest.mark.anyio
async def test_upstream_exception_returns_safe_error_without_leaking_exception_details() -> None:
    client = StubMCPClient(exception=RuntimeError("secret hostname db-01 failed"))
    router = ToolRouter(await build_registry(), [client])

    result = await router.invoke("search_mobility_options", valid_mobility_args())

    assert_error(result, RoutingErrorCode.UPSTREAM_ERROR)
    assert result.error is not None
    dumped_error = result.error.model_dump()
    assert "secret hostname db-01 failed" not in str(dumped_error)


@pytest.mark.anyio
@pytest.mark.parametrize("malformed_response", [["not", "a", "dict"], {"not_json_serializable": {"set-values"}}])
async def test_malformed_upstream_response_returns_malformed_response_error(
    malformed_response: Any,
) -> None:
    client = StubMCPClient(response=malformed_response)
    router = ToolRouter(await build_registry(), [client])

    result = await router.invoke("search_mobility_options", valid_mobility_args())

    if isinstance(malformed_response, dict):
        assert_error(result, RoutingErrorCode.MALFORMED_UPSTREAM_RESPONSE)
    else:
        assert_error(result, RoutingErrorCode.MALFORMED_UPSTREAM_RESPONSE)


@pytest.mark.anyio
async def test_missing_catalog_route_returns_safe_upstream_error() -> None:
    registry = await build_registry()
    snapshot = registry.get_snapshot().model_copy(update={"routes": {}})
    router = ToolRouter(CatalogRegistry(snapshot), [StubMCPClient()])

    result = await router.invoke("search_mobility_options", valid_mobility_args())

    assert_error(result, RoutingErrorCode.UPSTREAM_ERROR)


@pytest.mark.anyio
async def test_successful_invocation_logs_safe_routing_fields(caplog: pytest.LogCaptureFixture) -> None:
    client = StubMCPClient(response={"ok": True})
    router = ToolRouter(await build_registry(), [client])

    with caplog.at_level("INFO", logger="app.routing.router"):
        await router.invoke("search_mobility_options", valid_mobility_args(), request_id="req-log")

    log_text = caplog.text
    assert "request_id=req-log" in log_text
    assert "public_tool=search_mobility_options" in log_text
    assert "vertical=mobility" in log_text
    assert "upstream_tool=search" in log_text
    assert "latency_ms=" in log_text

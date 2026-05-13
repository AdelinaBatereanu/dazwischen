from typing import Any

import pytest

from app.catalog.builder import CatalogBuilder
from app.catalog.registry import CatalogRegistry
from app.catalog.versioning import CatalogVersionProvider
from app.models.tools import CandidateTool
from app.models.results import ToolResult
from app.routing.errors import RoutingErrorCode
from app.routing.router import ToolRouter
from app.validation.conformance import ToolConformanceValidator
from app.verticals.base import VerticalService
from app.verticals.mobility import MobilityVertical


class StubVertical:
    """Routing test double with configurable invocation behavior."""

    def __init__(
        self,
        *,
        name: str = "mobility",
        candidates: list[CandidateTool] | None = None,
        response: Any | None = None,
        exception: Exception | None = None,
    ) -> None:
        self.name = name
        self._candidates = candidates if candidates is not None else MobilityVertical().list_tools()
        self._response = {"stub": "ok"} if response is None else response
        self._exception = exception
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def list_tools(self) -> list[CandidateTool]:
        return self._candidates

    def invoke(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((tool_name, arguments))
        if self._exception is not None:
            raise self._exception
        return self._response


def build_registry(verticals: list[VerticalService] | None = None) -> CatalogRegistry:
    snapshot = CatalogBuilder(
        validator=ToolConformanceValidator(),
        version_provider=CatalogVersionProvider(),
    ).build(verticals or [MobilityVertical()])
    return CatalogRegistry(snapshot)


def assert_error(result: ToolResult, code: RoutingErrorCode) -> None:
    assert result.ok is False
    assert result.data is None
    assert result.error is not None
    assert result.error.code == code.value
    assert result.error.message


def valid_mobility_args(**overrides: object) -> dict[str, Any]:
    args: dict[str, Any] = {
        "origin": "Munich",
        "destination": "Berlin",
        "date": "2026-06-01",
    }
    args.update(overrides)
    return args


def test_public_tool_routes_to_correct_vertical_and_upstream_tool() -> None:
    vertical = StubVertical(response={"vertical": "mobility", "options": []})
    router = ToolRouter(build_registry([vertical]), [vertical])
    arguments = valid_mobility_args(passengers=2)

    result = router.invoke("search_mobility_options", arguments, request_id="req-123")

    assert result.ok is True
    assert result.error is None
    assert result.data == {"vertical": "mobility", "options": []}
    assert vertical.calls == [("search", arguments)]


@pytest.mark.parametrize(
    "arguments",
    [
        {"origin": "Munich", "date": "2026-06-01"},
        valid_mobility_args(passengers=0),
        valid_mobility_args(unapproved="extra"),
        ["not", "an", "object"],
    ],
)
def test_invalid_arguments_return_invalid_arguments_without_calling_vertical(arguments: Any) -> None:
    vertical = StubVertical()
    router = ToolRouter(build_registry([vertical]), [vertical])

    result = router.invoke("search_mobility_options", arguments)

    assert_error(result, RoutingErrorCode.INVALID_ARGUMENTS)
    assert result.error is not None
    assert result.error.details
    assert vertical.calls == []


def test_unknown_public_tool_returns_tool_not_found() -> None:
    vertical = StubVertical()
    router = ToolRouter(build_registry([vertical]), [vertical])

    result = router.invoke("book", {"option_id": "mob-train-001"})

    assert_error(result, RoutingErrorCode.TOOL_NOT_FOUND)
    assert result.error is not None
    assert result.error.details == {"tool": "book"}
    assert vertical.calls == []


def test_missing_configured_vertical_returns_vertical_unavailable() -> None:
    registry = build_registry([MobilityVertical()])
    router = ToolRouter(registry, [])

    result = router.invoke("search_mobility_options", valid_mobility_args())

    assert_error(result, RoutingErrorCode.VERTICAL_UNAVAILABLE)


def test_upstream_timeout_returns_safe_timeout_error() -> None:
    vertical = StubVertical(exception=TimeoutError("private upstream timeout details"))
    router = ToolRouter(build_registry([vertical]), [vertical])

    result = router.invoke("search_mobility_options", valid_mobility_args())

    assert_error(result, RoutingErrorCode.UPSTREAM_TIMEOUT)
    assert result.error is not None
    assert "private upstream timeout details" not in result.error.message


def test_upstream_exception_returns_safe_error_without_leaking_exception_details() -> None:
    vertical = StubVertical(exception=RuntimeError("secret hostname db-01 failed"))
    router = ToolRouter(build_registry([vertical]), [vertical])

    result = router.invoke("search_mobility_options", valid_mobility_args())

    assert_error(result, RoutingErrorCode.UPSTREAM_ERROR)
    assert result.error is not None
    dumped_error = result.error.model_dump()
    assert "secret hostname db-01 failed" not in str(dumped_error)


@pytest.mark.parametrize(
    "malformed_response",
    [
        ["not", "a", "dict"],
        {"not_json_serializable": {"set-values"}},
    ],
)
def test_malformed_upstream_response_returns_malformed_response_error(
    malformed_response: Any,
) -> None:
    vertical = StubVertical(response=malformed_response)
    router = ToolRouter(build_registry([vertical]), [vertical])

    result = router.invoke("search_mobility_options", valid_mobility_args())

    assert_error(result, RoutingErrorCode.MALFORMED_UPSTREAM_RESPONSE)


def test_missing_catalog_route_returns_safe_upstream_error() -> None:
    registry = build_registry([MobilityVertical()])
    snapshot = registry.get_snapshot().model_copy(update={"routes": {}})
    router = ToolRouter(CatalogRegistry(snapshot), [MobilityVertical()])

    result = router.invoke("search_mobility_options", valid_mobility_args())

    assert_error(result, RoutingErrorCode.UPSTREAM_ERROR)


def test_successful_invocation_logs_safe_routing_fields(caplog: pytest.LogCaptureFixture) -> None:
    vertical = StubVertical(response={"ok": True})
    router = ToolRouter(build_registry([vertical]), [vertical])

    with caplog.at_level("INFO", logger="app.routing.router"):
        router.invoke("search_mobility_options", valid_mobility_args(), request_id="req-log")

    log_text = caplog.text
    assert "request_id=req-log" in log_text
    assert "public_tool=search_mobility_options" in log_text
    assert "vertical=mobility" in log_text
    assert "upstream_tool=search" in log_text
    assert "latency_ms=" in log_text

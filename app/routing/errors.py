"""Safe routing error codes and result helpers."""

from enum import StrEnum
from typing import Any

from app.models.results import ToolError, ToolResult


class RoutingErrorCode(StrEnum):
    """Stable public error codes for failed tool invocations."""

    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
    VERTICAL_UNAVAILABLE = "VERTICAL_UNAVAILABLE"
    UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    MALFORMED_UPSTREAM_RESPONSE = "MALFORMED_UPSTREAM_RESPONSE"


_ERROR_MESSAGES: dict[RoutingErrorCode, str] = {
    RoutingErrorCode.TOOL_NOT_FOUND: "The requested tool is not available.",
    RoutingErrorCode.INVALID_ARGUMENTS: "The provided tool arguments are invalid.",
    RoutingErrorCode.VERTICAL_UNAVAILABLE: "The selected service is temporarily unavailable.",
    RoutingErrorCode.UPSTREAM_TIMEOUT: "The selected service timed out while handling the request.",
    RoutingErrorCode.UPSTREAM_ERROR: "The selected service failed while handling the request.",
    RoutingErrorCode.MALFORMED_UPSTREAM_RESPONSE: "The selected service returned an invalid response.",
}


def error_result(
    code: RoutingErrorCode,
    *,  # Parameters after this marker must be passed by keyword
    message: str | None = None,
    details: dict[str, Any] | None = None,
) -> ToolResult:
    """Create a safe failed tool result without leaking internal exception details."""
    return ToolResult(
        ok=False,
        error=ToolError(
            code=code.value,
            message=message or _ERROR_MESSAGES[code],
            details=details or {},
        ),
    )


def tool_not_found(public_tool_name: str) -> ToolResult:
    """Return a safe error for an unknown or unavailable public tool."""
    return error_result(
        RoutingErrorCode.TOOL_NOT_FOUND,
        details={"tool": public_tool_name},
    )


def invalid_arguments(details: dict[str, Any] | None = None) -> ToolResult:
    """Return a safe error for arguments that do not match the public schema."""
    return error_result(RoutingErrorCode.INVALID_ARGUMENTS, details=details)


def vertical_unavailable() -> ToolResult:
    """Return a safe error when the routed vertical cannot be found or used."""
    return error_result(RoutingErrorCode.VERTICAL_UNAVAILABLE)


def upstream_timeout() -> ToolResult:
    """Return a safe error when an upstream vertical invocation times out."""
    return error_result(RoutingErrorCode.UPSTREAM_TIMEOUT)


def upstream_error() -> ToolResult:
    """Return a safe error for unexpected upstream failures."""
    return error_result(RoutingErrorCode.UPSTREAM_ERROR)


def malformed_upstream_response() -> ToolResult:
    """Return a safe error when an upstream response cannot be normalized."""
    return error_result(RoutingErrorCode.MALFORMED_UPSTREAM_RESPONSE)

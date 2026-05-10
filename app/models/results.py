"""Routing and invocation result models."""

from typing import Any

from pydantic import BaseModel, Field


class ToolError(BaseModel):
    """Safe structured error returned for failed public tool invocations."""

    code: str = Field(..., description="Stable safe error code.")
    message: str = Field(..., description="Safe user-facing error message.")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional sanitized details suitable for public responses.",
    )


class ToolResult(BaseModel):
    """Normalized result of a public tool invocation."""

    ok: bool = Field(..., description="Whether the tool invocation succeeded.")
    data: dict[str, Any] | None = Field(
        default=None,
        description="JSON-serializable normalized response data for successful calls.",
    )
    error: ToolError | None = Field(
        default=None,
        description="Safe structured error for failed calls.",
    )

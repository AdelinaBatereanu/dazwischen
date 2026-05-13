"""Observability models for proxy invocation tracing and summaries."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class InvocationSource(StrEnum):
    """Where a public tool invocation entered the proxy."""

    MCP = "mcp"
    SANDBOX = "sandbox"


class InvocationEvent(BaseModel):
    """Safe operational metadata recorded for one public tool invocation."""

    request_id: str = Field(..., description="Request ID for debugging one invocation.")
    conversation_id: str | None = Field(
        default=None,
        description="Optional conversation ID provided by the client/tester.",
    )
    source: InvocationSource = Field(..., description="Invocation entry point.")
    public_tool_name: str = Field(..., description="Public proxy-owned tool name.")
    vertical: str | None = Field(
        default=None,
        description="Owning vertical selected by the catalog route, if known.",
    )
    upstream_tool: str | None = Field(
        default=None,
        description="Internal upstream tool name selected by the route, if known.",
    )
    latency_ms: float = Field(..., ge=0, description="Invocation latency in milliseconds.")
    ok: bool = Field(..., description="Whether the invocation succeeded.")
    error_code: str | None = Field(
        default=None,
        description="Safe error code for failed invocations.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when the event was recorded.",
    )


class VerticalMonitoringSummary(BaseModel):
    """Aggregated call/error/latency metrics for one vertical."""

    calls: int = Field(default=0, ge=0)
    successes: int = Field(default=0, ge=0)
    errors: int = Field(default=0, ge=0)
    average_latency_ms: float = Field(default=0.0, ge=0)


class MonitoringSummary(BaseModel):
    """Aggregated monitoring view for the proxy and each vertical."""

    total_calls: int = Field(default=0, ge=0)
    successes: int = Field(default=0, ge=0)
    errors: int = Field(default=0, ge=0)
    average_latency_ms: float = Field(default=0.0, ge=0)
    by_vertical: dict[str, VerticalMonitoringSummary] = Field(default_factory=dict)


class VerticalHealthSummary(BaseModel):
    """Simple health/dashboard status for one configured vertical."""

    name: str = Field(..., description="Vertical service name.")
    reachable: bool = Field(default=True, description="Whether the vertical is configured/reachable.")
    accepted_tools: int = Field(default=0, ge=0)
    rejected_tools: int = Field(default=0, ge=0)
    calls: int = Field(default=0, ge=0)
    errors: int = Field(default=0, ge=0)
    last_failure: InvocationEvent | None = None
    status: str = Field(default="green", description="Simple green/yellow/red status.")


class ConversationSummary(BaseModel):
    """Tool usage summary for one conversation."""

    conversation_id: str = Field(..., description="Conversation ID provided by the client/tester.")
    calls: int = Field(default=0, ge=0)
    errors: int = Field(default=0, ge=0)
    tool_counts: dict[str, int] = Field(default_factory=dict)
    vertical_counts: dict[str, int] = Field(default_factory=dict)
    last_seen: datetime | None = None


class ConversationDetail(ConversationSummary):
    """Detailed timeline for one conversation."""

    events: list[InvocationEvent] = Field(default_factory=list)

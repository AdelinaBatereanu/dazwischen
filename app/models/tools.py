from typing import Any

from pydantic import BaseModel, Field


class CandidateTool(BaseModel):
    """Tool candidate proposed by an internal vertical service."""

    vertical: str = Field(..., description="Owning vertical service name.")
    upstream_tool: str = Field(..., description="Internal vertical tool name.")
    description: str = Field(..., description="Description of the internal tool candidate.")
    input_schema: dict[str, Any] = Field(..., description="Candidate JSON Schema input contract.")
    response_schema: dict[str, Any] | None = Field(
        default=None,
        description="Optional candidate JSON Schema response contract.",
    )
    safe_to_expose: bool = Field(
        default=True,
        description="Vertical self-attestation that the tool is safe to expose.",
    )
    internal_version: str = Field(
        default="1.0",
        description="Internal vertical tool contract version.",
    )

class PublicTool(BaseModel):
    """Curated tool definition exposed by the proxy to ChatGPT/MCP clients."""

    name: str = Field(..., description="Proxy-owned public tool name.")
    description: str = Field(..., description="Stable user-facing public description.")
    input_schema: dict[str, Any] = Field(..., description="Public JSON Schema input contract.")


class ToolRoute(BaseModel):
    """Route from a public tool to an internal vertical tool."""

    public_name: str = Field(..., description="Public proxy-owned tool name.")
    vertical: str = Field(..., description="Owning vertical service name.")
    upstream_tool: str = Field(..., description="Internal vertical tool name.")
    public_version: str = Field(..., description="Public tool contract version.")
    internal_contract_version: str = Field(
        ...,
        description="Internal proxy-to-vertical contract version.",
    )

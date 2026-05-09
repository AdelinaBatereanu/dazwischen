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

"""Validation and conformance report models."""

from enum import StrEnum

from pydantic import BaseModel, Field


class ToolValidationStatus(StrEnum):
    """Allowed conformance states for a candidate tool."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ValidationIssue(BaseModel):
    """Single actionable conformance issue for a candidate tool."""

    code: str = Field(..., description="Stable machine-readable issue code.")
    message: str = Field(..., description="Human-readable remediation guidance.")
    field: str | None = Field(
        default=None,
        description="Optional field/path related to this issue.",
    )


class ValidationResult(BaseModel):
    """Validation outcome for one candidate tool."""

    vertical: str = Field(..., description="Owning vertical service name.")
    tool: str = Field(..., description="Internal upstream tool name.")
    status: ToolValidationStatus = Field(..., description="Accepted or rejected status.")
    reasons: list[ValidationIssue] = Field(
        default_factory=list,
        description="Actionable rejection or warning reasons.",
    )


class ValidationReport(BaseModel):
    """Complete validation report for all candidate tools in a catalog build."""

    results: list[ValidationResult] = Field(
        default_factory=list,
        description="Per-tool validation outcomes.",
    )

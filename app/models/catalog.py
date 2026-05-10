from pydantic import BaseModel, Field

from app.models.tools import PublicTool, ToolRoute
from app.models.validation import ValidationReport


class CatalogMetadata(BaseModel):
    """Version metadata attached to a public catalog snapshot."""

    proxy_version: str = Field(..., description="Proxy application/API version.")
    catalog_version: str = Field(..., description="Immutable public catalog snapshot version.")
    public_endpoint_version: str = Field(..., description="Public endpoint version, e.g. v1.")
    internal_contract_version: str = Field(
        ...,
        description="Proxy-to-vertical internal contract version.",
    )


class CatalogSnapshot(BaseModel):
    """Runtime view of the curated public tool catalog."""

    metadata: CatalogMetadata = Field(..., description="Catalog and endpoint version metadata.")
    tools: list[PublicTool] = Field(default_factory=list, description="Accepted public tools.")
    routes: dict[str, ToolRoute] = Field(
        default_factory=dict,
        description="Public-name to internal-route mapping.",
    )
    validation_report: ValidationReport | None = Field(
        default=None,
        description="Validation report generated while building this catalog.",
    )

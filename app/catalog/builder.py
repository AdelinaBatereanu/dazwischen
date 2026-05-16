"""Build the curated public catalog from internal vertical candidates."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TypeAlias

from app.catalog.versioning import CatalogVersionProvider
from app.models.catalog import CatalogSnapshot
from app.models.tools import CandidateTool, PublicTool, ToolRoute
from app.models.validation import ToolValidationStatus, ValidationIssue, ValidationReport, ValidationResult
from app.validation.conformance import ToolConformanceValidator
from app.vertical_mcp.adapters import list_candidate_tools
from app.vertical_mcp.base import VerticalMCPClient

ToolMappingKey: TypeAlias = tuple[str, str, str]


@dataclass(frozen=True)
class ApprovedPublicMapping:
    """Proxy-owned mapping from an internal candidate identity to a public tool."""

    public_name: str
    description: str
    public_version: str = "1.0"


DEFAULT_APPROVED_PUBLIC_MAPPINGS: dict[ToolMappingKey, ApprovedPublicMapping] = {
    ("mobility", "search", "1.0"): ApprovedPublicMapping(
        public_name="search_mobility_options",
        description=(
            "Search available mobility options such as trains, rental cars, and shared "
            "transport for a requested trip."
        ),
    ),
    ("internet", "check_availability", "1.0"): ApprovedPublicMapping(
        public_name="compare_internet_plans",
        description="Compare available home internet plans for a requested service address.",
    ),
    ("insurance", "quote", "1.0"): ApprovedPublicMapping(
        public_name="compare_insurance_offers",
        description="Compare indicative insurance offers for a requested product and profile.",
    ),
}


class CatalogBuilder:
    """Construct an immutable runtime snapshot of the curated public catalog."""

    def __init__(
        self,
        validator: ToolConformanceValidator,
        version_provider: CatalogVersionProvider,
        approved_mappings: Mapping[ToolMappingKey, ApprovedPublicMapping] | None = None,
    ) -> None:
        self._validator = validator
        self._version_provider = version_provider
        self._approved_mappings = dict(approved_mappings or DEFAULT_APPROVED_PUBLIC_MAPPINGS)

    async def build_from_mcp_clients(
        self,
        clients: Iterable[VerticalMCPClient],
    ) -> CatalogSnapshot:
        """Collect, validate, map, and publish accepted internal MCP tool candidates."""
        candidates: list[CandidateTool] = []
        for client in clients:
            candidates.extend(await list_candidate_tools(client))
        return self.build_from_candidates(candidates)

    def build_from_candidates(self, candidates: list[CandidateTool]) -> CatalogSnapshot:
        conformance_report = self._validator.validate_all(candidates)
        metadata = self._version_provider.get_metadata()

        public_tools: list[PublicTool] = []
        routes: dict[str, ToolRoute] = {}
        final_results: list[ValidationResult] = []

        for candidate, validation_result in zip(candidates, conformance_report.results, strict=True):
            if validation_result.status == ToolValidationStatus.REJECTED:
                final_results.append(validation_result)
                continue

            mapping = self._approved_mappings.get(_mapping_key(candidate))
            if mapping is None:
                final_results.append(_no_approved_mapping_result(candidate))
                continue

            if mapping.public_name in routes:
                final_results.append(_duplicate_public_mapping_result(candidate, mapping.public_name))
                continue

            public_tools.append(_to_public_tool(candidate, mapping))
            routes[mapping.public_name] = ToolRoute(
                public_name=mapping.public_name,
                vertical=candidate.vertical,
                upstream_tool=candidate.upstream_tool,
                public_version=mapping.public_version,
                internal_contract_version=metadata.internal_contract_version,
            )
            final_results.append(validation_result)

        return CatalogSnapshot(
            metadata=metadata,
            tools=public_tools,
            routes=routes,
            validation_report=ValidationReport(results=final_results),
        )

def _mapping_key(candidate: CandidateTool) -> ToolMappingKey:
    return (candidate.vertical, candidate.upstream_tool, candidate.internal_version)


def _to_public_tool(candidate: CandidateTool, mapping: ApprovedPublicMapping) -> PublicTool:
    return PublicTool(
        name=mapping.public_name,
        description=mapping.description,
        input_schema=candidate.input_schema,
    )


def _no_approved_mapping_result(candidate: CandidateTool) -> ValidationResult:
    return ValidationResult(
        vertical=candidate.vertical,
        tool=candidate.upstream_tool,
        status=ToolValidationStatus.REJECTED,
        reasons=[
            ValidationIssue(
                code="NO_APPROVED_PUBLIC_MAPPING",
                message=(
                    "Candidate passed conformance validation but has no proxy-approved "
                    "public catalog mapping for its vertical, upstream tool, and internal version."
                ),
                field="catalog_mapping",
            )
        ],
    )


def _duplicate_public_mapping_result(candidate: CandidateTool, public_name: str) -> ValidationResult:
    return ValidationResult(
        vertical=candidate.vertical,
        tool=candidate.upstream_tool,
        status=ToolValidationStatus.REJECTED,
        reasons=[
            ValidationIssue(
                code="DUPLICATE_PUBLIC_MAPPING",
                message=f"Public tool name '{public_name}' is already mapped to another candidate.",
                field="catalog_mapping.public_name",
            )
        ],
    )

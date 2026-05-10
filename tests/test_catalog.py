"""Tests for the Phase 5 catalog layer."""

from typing import Any

from app.catalog.builder import ApprovedPublicMapping, CatalogBuilder
from app.catalog.registry import CatalogRegistry
from app.catalog.versioning import CatalogVersionProvider
from app.models.tools import CandidateTool
from app.models.validation import ToolValidationStatus
from app.validation.conformance import ToolConformanceValidator
from app.verticals.insurance import InsuranceVertical
from app.verticals.internet import InternetVertical
from app.verticals.mobility import MobilityVertical


class StubVertical:
    """Small vertical test double returning fixed candidate tools."""

    def __init__(self, name: str, candidates: list[CandidateTool]) -> None:
        self.name = name
        self._candidates = candidates

    def list_tools(self) -> list[CandidateTool]:
        return self._candidates

    def invoke(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return {"tool_name": tool_name, "arguments": arguments}


def valid_candidate(**overrides: object) -> CandidateTool:
    data = {
        "vertical": "mobility",
        "upstream_tool": "search",
        "description": "Search available mobility options for a requested trip.",
        "input_schema": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Trip origin."},
                "destination": {"type": "string", "description": "Trip destination."},
            },
            "required": ["origin", "destination"],
            "additionalProperties": False,
        },
        "safe_to_expose": True,
        "internal_version": "1.0",
    }
    data.update(overrides)
    return CandidateTool(**data)


def build_registry(*verticals: StubVertical | MobilityVertical | InternetVertical | InsuranceVertical) -> CatalogRegistry:
    snapshot = CatalogBuilder(
        validator=ToolConformanceValidator(),
        version_provider=CatalogVersionProvider(),
    ).build(verticals)
    return CatalogRegistry(snapshot)


def test_catalog_exposes_only_curated_public_tools() -> None:
    registry = build_registry(MobilityVertical(), InternetVertical(), InsuranceVertical())

    public_names = {tool.name for tool in registry.list_tools()}

    assert public_names == {
        "search_mobility_options",
        "compare_internet_plans",
        "compare_insurance_offers",
    }
    assert "search" not in public_names
    assert "book" not in public_names
    assert "order_plan" not in public_names
    assert "bind_policy" not in public_names
    assert "quote_with_ssn" not in public_names


def test_catalog_routes_public_tools_to_deterministic_internal_versions() -> None:
    registry = build_registry(MobilityVertical(), InternetVertical(), InsuranceVertical())

    mobility_route = registry.get_route("search_mobility_options")
    internet_route = registry.get_route("compare_internet_plans")
    insurance_route = registry.get_route("compare_insurance_offers")

    assert mobility_route is not None
    assert mobility_route.vertical == "mobility"
    assert mobility_route.upstream_tool == "search"
    assert mobility_route.public_version == "1.0"
    assert mobility_route.internal_contract_version == "1.0"

    assert internet_route is not None
    assert internet_route.vertical == "internet"
    assert internet_route.upstream_tool == "check_availability"

    assert insurance_route is not None
    assert insurance_route.vertical == "insurance"
    assert insurance_route.upstream_tool == "quote"


def test_registry_lookup_and_snapshot_version_metadata_are_available() -> None:
    registry = build_registry(MobilityVertical(), InternetVertical(), InsuranceVertical())

    tool = registry.get_tool("compare_internet_plans")
    snapshot = registry.get_snapshot()

    assert tool is not None
    assert tool.description == "Compare available home internet plans for a requested service address."
    assert registry.get_tool("check_availability") is None

    assert snapshot.metadata.proxy_version == "1.0.0"
    assert snapshot.metadata.catalog_version == "2026-05-02.1"
    assert snapshot.metadata.public_endpoint_version == "v1"
    assert snapshot.metadata.internal_contract_version == "1.0"


def test_validation_report_keeps_accepted_and_rejected_catalog_decisions() -> None:
    registry = build_registry(MobilityVertical(), InternetVertical(), InsuranceVertical())

    report = registry.get_validation_report()
    assert report is not None

    accepted = {(result.vertical, result.tool) for result in report.results if result.status == "accepted"}
    rejected = {(result.vertical, result.tool) for result in report.results if result.status == "rejected"}

    assert accepted == {
        ("mobility", "search"),
        ("internet", "check_availability"),
        ("insurance", "quote"),
    }
    assert rejected == {
        ("mobility", "book"),
        ("internet", "order_plan"),
        ("internet", "run_diagnostics_command"),
        ("insurance", "bind_policy"),
        ("insurance", "quote_with_ssn"),
    }


def test_valid_candidate_without_approved_mapping_is_rejected_from_public_catalog() -> None:
    candidate = valid_candidate(upstream_tool="search_v2", internal_version="2.0")
    registry = build_registry(StubVertical("mobility", [candidate]))

    report = registry.get_validation_report()
    assert registry.list_tools() == []
    assert report is not None
    assert report.results[0].status == ToolValidationStatus.REJECTED
    assert {reason.code for reason in report.results[0].reasons} == {"NO_APPROVED_PUBLIC_MAPPING"}


def test_duplicate_proxy_owned_public_mapping_is_rejected() -> None:
    first = valid_candidate(vertical="mobility", upstream_tool="search", internal_version="1.0")
    second = valid_candidate(
        vertical="internet",
        upstream_tool="find_plans",
        internal_version="1.0",
        description="Find available internet plans for a requested service address.",
    )
    mappings = {
        ("mobility", "search", "1.0"): ApprovedPublicMapping(
            public_name="duplicate_public_name",
            description="Search mobility options for the requested trip.",
        ),
        ("internet", "find_plans", "1.0"): ApprovedPublicMapping(
            public_name="duplicate_public_name",
            description="Compare available internet plans for the requested address.",
        ),
    }

    snapshot = CatalogBuilder(
        validator=ToolConformanceValidator(),
        version_provider=CatalogVersionProvider(),
        approved_mappings=mappings,
    ).build([StubVertical("test", [first, second])])
    registry = CatalogRegistry(snapshot)

    assert [tool.name for tool in registry.list_tools()] == ["duplicate_public_name"]
    duplicate_result = snapshot.validation_report.results[1]
    assert duplicate_result.status == ToolValidationStatus.REJECTED
    assert {reason.code for reason in duplicate_result.reasons} == {"DUPLICATE_PUBLIC_MAPPING"}

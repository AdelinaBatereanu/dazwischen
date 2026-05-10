"""Tests for Phase 5 vertical-filtered catalog listing."""

from app.catalog.builder import CatalogBuilder
from app.catalog.registry import CatalogRegistry
from app.catalog.versioning import CatalogVersionProvider
from app.validation.conformance import ToolConformanceValidator
from app.verticals.insurance import InsuranceVertical
from app.verticals.internet import InternetVertical
from app.verticals.mobility import MobilityVertical


def registry() -> CatalogRegistry:
    snapshot = CatalogBuilder(
        validator=ToolConformanceValidator(),
        version_provider=CatalogVersionProvider(),
    ).build([MobilityVertical(), InternetVertical(), InsuranceVertical()])
    return CatalogRegistry(snapshot)


def test_vertical_filter_lists_only_selected_vertical_accepted_tools() -> None:
    catalog = registry()

    assert [tool.name for tool in catalog.list_tools(vertical_filter="mobility")] == [
        "search_mobility_options"
    ]
    assert [tool.name for tool in catalog.list_tools(vertical_filter="internet")] == [
        "compare_internet_plans"
    ]
    assert [tool.name for tool in catalog.list_tools(vertical_filter="insurance")] == [
        "compare_insurance_offers"
    ]


def test_vertical_filter_keeps_rejected_tools_and_other_verticals_hidden() -> None:
    catalog = registry()

    mobility_names = {tool.name for tool in catalog.list_tools(vertical_filter="mobility")}

    assert mobility_names == {"search_mobility_options"}
    assert "compare_internet_plans" not in mobility_names
    assert "compare_insurance_offers" not in mobility_names
    assert "book" not in mobility_names
    assert "order_plan" not in mobility_names
    assert "bind_policy" not in mobility_names


def test_unknown_vertical_filter_returns_no_tools() -> None:
    assert registry().list_tools(vertical_filter="payments") == []

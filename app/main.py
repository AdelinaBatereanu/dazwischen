"""FastAPI application composition for the ChatGPT-facing MCP proxy."""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from app.catalog.builder import CatalogBuilder
from app.catalog.registry import CatalogRegistry
from app.catalog.versioning import CatalogVersionProvider
from app.mcp_server import create_mcp_app
from app.routing.router import ToolRouter
from app.validation.conformance import ToolConformanceValidator
from app.verticals.base import VerticalService
from app.verticals.insurance import InsuranceVertical
from app.verticals.internet import InternetVertical
from app.verticals.mobility import MobilityVertical


def create_verticals() -> list[VerticalService]:
    """Create the internal mocked vertical services hidden behind the proxy."""
    return [MobilityVertical(), InternetVertical(), InsuranceVertical()]


def create_catalog_registry(verticals: Sequence[VerticalService]) -> CatalogRegistry:
    """Build the immutable runtime catalog registry from configured verticals."""
    validator = ToolConformanceValidator()
    version_provider = CatalogVersionProvider()
    snapshot = CatalogBuilder(validator=validator, version_provider=version_provider).build(verticals)
    return CatalogRegistry(snapshot)


def create_app() -> FastAPI:
    """Compose the FastAPI app and attach runtime proxy components."""
    verticals = create_verticals()
    catalog = create_catalog_registry(verticals)
    router = ToolRouter(catalog=catalog, verticals=verticals)
    mcp_app = create_mcp_app(catalog=catalog, router=router)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with mcp_app.state.session_manager.run():
            yield

    app = FastAPI(
        title="Dazwischen MCP Proxy",
        description="Single ChatGPT-facing MCP proxy over mocked internal vertical services.",
        version=catalog.get_snapshot().metadata.proxy_version,
        lifespan=lifespan,
    )
    app.state.verticals = verticals
    app.state.catalog = catalog
    app.state.router = router
    app.mount("/v1", mcp_app)

    @app.get("/health")
    def health() -> dict[str, Any]:
        metadata = catalog.get_snapshot().metadata
        return {
            "status": "ok",
            "proxy_version": metadata.proxy_version,
            "catalog_version": metadata.catalog_version,
            "public_endpoint_version": metadata.public_endpoint_version,
        }

    @app.get("/debug/catalog")
    def debug_catalog() -> dict[str, Any]:
        return catalog.get_snapshot().model_dump(mode="json")

    @app.get("/debug/validation-report")
    def debug_validation_report() -> dict[str, Any] | None:
        report = catalog.get_validation_report()
        if report is None:
            return None
        return report.model_dump(mode="json")

    return app


app = create_app()

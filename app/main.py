"""FastAPI application composition for the ChatGPT-facing MCP proxy."""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.debug import create_debug_router
from app.api.health import create_health_router
from app.api.ui import create_ui_router
from app.catalog.builder import CatalogBuilder
from app.catalog.registry import CatalogRegistry
from app.catalog.versioning import CatalogVersionProvider
from app.mcp_server import create_mcp_app
from app.observability.store import ObservabilityStore
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
    observability = ObservabilityStore()
    router = ToolRouter(catalog=catalog, verticals=verticals, observability=observability)
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
    app.state.observability = observability
    app.state.router = router

    static_dir = Path(__file__).parent / "static"
    if True:
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
        app.include_router(create_ui_router(static_dir))

    app.mount("/v1", mcp_app)

    app.include_router(create_health_router(catalog))
    app.include_router(
        create_debug_router(
            catalog=catalog,
            observability=observability,
            router=router,
            verticals=verticals,
        )
    )

    return app


app = create_app()

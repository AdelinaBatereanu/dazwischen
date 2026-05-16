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
from app.vertical_mcp.adapters import InProcessVerticalMCPClient
from app.vertical_mcp.base import VerticalMCPClient
from app.vertical_mcp.insurance import create_insurance_server
from app.vertical_mcp.internet import create_internet_server
from app.vertical_mcp.mobility import create_mobility_server


def create_vertical_mcp_clients() -> list[VerticalMCPClient]:
    """Create internal MCP vertical clients hidden behind the proxy."""
    return [
        InProcessVerticalMCPClient("mobility", create_mobility_server()),
        InProcessVerticalMCPClient("internet", create_internet_server()),
        InProcessVerticalMCPClient("insurance", create_insurance_server()),
    ]


async def create_catalog_registry_from_mcp_clients(
    vertical_mcp_clients: Sequence[VerticalMCPClient],
) -> CatalogRegistry:
    """Build the immutable runtime catalog registry from internal MCP verticals."""
    validator = ToolConformanceValidator()
    version_provider = CatalogVersionProvider()
    builder = CatalogBuilder(validator=validator, version_provider=version_provider)
    snapshot = await builder.build_from_mcp_clients(vertical_mcp_clients)
    return CatalogRegistry(snapshot)


def create_app() -> FastAPI:
    """Compose the FastAPI app and attach runtime proxy components during startup."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        vertical_mcp_clients = create_vertical_mcp_clients()
        catalog = await create_catalog_registry_from_mcp_clients(vertical_mcp_clients)
        observability = ObservabilityStore()
        router = ToolRouter(
            catalog=catalog,
            vertical_mcp_clients=vertical_mcp_clients,
            observability=observability,
        )
        mcp_app = create_mcp_app(catalog=catalog, router=router)

        app.state.vertical_mcp_clients = vertical_mcp_clients
        app.state.catalog = catalog
        app.state.observability = observability
        app.state.router = router
        app.state.mcp_app = mcp_app

        if not getattr(app.state, "runtime_routes_registered", False):
            app.mount("/v1", mcp_app)
            app.include_router(create_health_router(catalog))
            app.include_router(
                create_debug_router(
                    catalog=catalog,
                    observability=observability,
                    router=router,
                    vertical_mcp_clients=vertical_mcp_clients,
                )
            )
            app.state.runtime_routes_registered = True

        async with mcp_app.state.session_manager.run():
            yield

    app = FastAPI(
        title="Dazwischen MCP Proxy",
        description="Single ChatGPT-facing MCP proxy over mocked internal vertical MCP providers.",
        version="1.0.0",
        lifespan=lifespan,
    )

    static_dir = Path(__file__).parent / "static"
    if True:
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
        app.include_router(create_ui_router(static_dir))

    return app


app = create_app()

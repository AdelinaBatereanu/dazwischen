"""Health endpoint routes."""

from typing import Any

from fastapi import APIRouter

from app.catalog.registry import CatalogRegistry


def create_health_router(catalog: CatalogRegistry) -> APIRouter:
    """Create health/status routes."""
    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, Any]:
        metadata = catalog.get_snapshot().metadata
        return {
            "status": "ok",
            "proxy_version": metadata.proxy_version,
            "catalog_version": metadata.catalog_version,
            "public_endpoint_version": metadata.public_endpoint_version,
        }

    return router

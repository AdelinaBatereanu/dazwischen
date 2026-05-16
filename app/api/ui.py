"""Static HTML UI routes."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse


def create_ui_router(static_dir: Path) -> APIRouter:
    """Create routes for static sandbox/debug HTML pages."""
    router = APIRouter(include_in_schema=False)

    @router.get("/sandbox")
    def sandbox_ui() -> FileResponse:
        return FileResponse(static_dir / "sandbox.html")

    @router.get("/debug-ui")
    def debug_ui() -> FileResponse:
        return FileResponse(static_dir / "debug" / "index.html")

    @router.get("/debug-ui/catalog")
    def debug_ui_catalog() -> FileResponse:
        return FileResponse(static_dir / "debug" / "catalog.html")

    @router.get("/debug-ui/validation-report")
    def debug_ui_validation_report() -> FileResponse:
        return FileResponse(static_dir / "debug" / "validation-report.html")

    @router.get("/debug-ui/monitoring")
    def debug_ui_monitoring() -> FileResponse:
        return FileResponse(static_dir / "debug" / "monitoring.html")

    @router.get("/debug-ui/verticals")
    def debug_ui_verticals() -> FileResponse:
        return FileResponse(static_dir / "debug" / "verticals.html")

    @router.get("/debug-ui/vertical-resources")
    def debug_ui_vertical_resources() -> FileResponse:
        return FileResponse(static_dir / "debug" / "vertical-resources.html")

    @router.get("/debug-ui/recent-failures")
    def debug_ui_recent_failures() -> FileResponse:
        return FileResponse(static_dir / "debug" / "recent-failures.html")

    @router.get("/debug-ui/conversations")
    def debug_ui_conversations() -> FileResponse:
        return FileResponse(static_dir / "debug" / "conversations.html")

    return router

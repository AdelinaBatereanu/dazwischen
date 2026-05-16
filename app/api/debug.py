"""Debug and sandbox HTTP API routes."""

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.catalog.registry import CatalogRegistry
from app.models.observability import InvocationSource
from app.observability.store import ObservabilityStore
from app.routing.errors import tool_not_found
from app.routing.router import ToolRouter
from app.vertical_mcp.base import VerticalMCPClient


class SandboxInvokeRequest(BaseModel):
    """Request body for proxy-routed sandbox tool invocation."""

    tool_name: str = Field(..., description="Accepted public tool name to invoke.")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool arguments.")
    conversation_id: str | None = Field(
        default=None,
        description="Optional demo conversation ID for grouping sandbox calls.",
    )
    vertical: str | None = Field(
        default=None,
        description="Optional vertical filter for isolated team testing.",
    )
    request_id: str | None = Field(default=None, description="Optional request ID for debugging.")


def create_debug_router(
    *,
    catalog: CatalogRegistry,
    observability: ObservabilityStore,
    router: ToolRouter,
    vertical_mcp_clients: list[VerticalMCPClient],
) -> APIRouter:
    """Create debug and sandbox routes."""
    api_router = APIRouter()

    @api_router.get("/debug/catalog")
    def debug_catalog() -> dict[str, Any]:
        return catalog.get_snapshot().model_dump(mode="json")

    @api_router.get("/debug/validation-report")
    def debug_validation_report() -> dict[str, Any] | None:
        report = catalog.get_validation_report()
        if report is None:
            return None
        return report.model_dump(mode="json")

    @api_router.get("/debug/monitoring")
    def debug_monitoring() -> dict[str, Any]:
        return observability.monitoring_summary().model_dump(mode="json")

    @api_router.get("/debug/verticals")
    def debug_verticals() -> dict[str, Any]:
        summaries = observability.vertical_summary(
            catalog=catalog,
            validation_report=catalog.get_validation_report(),
            vertical_names=[client.name for client in vertical_mcp_clients],
        )
        return {"verticals": [summary.model_dump(mode="json") for summary in summaries]}

    @api_router.get("/debug/recent-failures")
    def debug_recent_failures(limit: int = 20) -> dict[str, Any]:
        failures = observability.recent_failures(limit=limit)
        return {"failures": [failure.model_dump(mode="json") for failure in failures]}

    @api_router.get("/debug/conversations")
    def debug_conversations() -> dict[str, Any]:
        conversations = observability.conversations()
        return {
            "conversations": [conversation.model_dump(mode="json") for conversation in conversations]
        }

    @api_router.get("/debug/conversations/{conversation_id}")
    def debug_conversation_detail(conversation_id: str) -> dict[str, Any]:
        conversation = observability.conversation_detail(conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        return conversation.model_dump(mode="json")

    @api_router.get("/debug/sandbox/tools")
    def debug_sandbox_tools(vertical: str | None = None) -> dict[str, Any]:
        tools = catalog.list_tools(vertical_filter=vertical)
        return {"tools": [tool.model_dump(mode="json") for tool in tools]}

    @api_router.get("/debug/vertical-resources")
    async def debug_vertical_resources(vertical: str | None = None) -> dict[str, Any]:
        selected_clients = _filter_vertical_clients(vertical_mcp_clients, vertical)
        return {
            "verticals": [
                {
                    "vertical": client.name,
                    "resources": [
                        resource.model_dump(mode="json")
                        for resource in await client.list_resources()
                    ],
                }
                for client in selected_clients
            ]
        }

    @api_router.get("/debug/vertical-resources/{vertical}/{resource_name}")
    async def debug_vertical_resource(vertical: str, resource_name: str) -> dict[str, Any]:
        client = _get_vertical_client(vertical_mcp_clients, vertical)
        if client is None:
            raise HTTPException(status_code=404, detail="Vertical not found.")

        uri = f"vertical://{vertical}/{resource_name}"
        try:
            contents = await client.read_resource(uri)
        except Exception as exc:
            raise HTTPException(status_code=404, detail="Resource not found.") from exc

        return {
            "vertical": vertical,
            "uri": uri,
            "contents": [content.model_dump(mode="json") for content in contents],
        }

    @api_router.post("/debug/sandbox/invoke")
    async def debug_sandbox_invoke(request: SandboxInvokeRequest) -> dict[str, Any]:
        request_id = request.request_id or str(uuid4())
        route = catalog.get_route(request.tool_name)
        if request.vertical is not None and (route is None or route.vertical != request.vertical):
            result = tool_not_found(request.tool_name)
        else:
            result = await router.invoke(
                request.tool_name,
                request.arguments,
                request_id=request_id,
                conversation_id=request.conversation_id,
                source=InvocationSource.SANDBOX,
            )

        return {
            "request_id": request_id,
            "result": result.model_dump(mode="json"),
        }

    return api_router


def _filter_vertical_clients(
    clients: list[VerticalMCPClient],
    vertical: str | None,
) -> list[VerticalMCPClient]:
    if vertical is None:
        return clients
    return [client for client in clients if client.name == vertical]


def _get_vertical_client(
    clients: list[VerticalMCPClient],
    vertical: str,
) -> VerticalMCPClient | None:
    for client in clients:
        if client.name == vertical:
            return client
    return None

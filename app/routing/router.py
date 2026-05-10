"""Deterministic safe routing from public tools to internal vertical services."""

import json
import logging
import time
from collections.abc import Sequence
from typing import Any

from jsonschema import ValidationError, validate

from app.catalog.registry import CatalogRegistry
from app.models.results import ToolResult
from app.routing.errors import (
    invalid_arguments,
    malformed_upstream_response,
    tool_not_found,
    upstream_error,
    upstream_timeout,
    vertical_unavailable,
)
from app.verticals.base import VerticalService

logger = logging.getLogger(__name__)


class ToolRouter:
    """Route accepted public tool calls to the correct internal vertical."""

    def __init__(self, catalog: CatalogRegistry, verticals: Sequence[VerticalService]) -> None:
        self._catalog = catalog
        self._verticals_by_name = {vertical.name: vertical for vertical in verticals}

    def invoke(
        self,
        public_tool_name: str,
        arguments: dict[str, Any],
        request_id: str | None = None,
    ) -> ToolResult:
        """Invoke a public tool through its catalog route and return a safe result."""
        started_at = time.perf_counter()
        public_tool = self._catalog.get_tool(public_tool_name)
        if public_tool is None:
            logger.info(
                "Tool invocation rejected request_id=%s public_tool=%s safe_error_code=TOOL_NOT_FOUND",
                request_id,
                public_tool_name,
            )
            return tool_not_found(public_tool_name)

        route = self._catalog.get_route(public_tool_name)
        if route is None:
            logger.error(
                "Catalog route missing request_id=%s public_tool=%s safe_error_code=UPSTREAM_ERROR",
                request_id,
                public_tool_name,
            )
            return upstream_error()

        argument_error = self._validate_arguments(arguments, public_tool.input_schema)
        if argument_error is not None:
            logger.info(
                "Tool invocation rejected request_id=%s public_tool=%s safe_error_code=INVALID_ARGUMENTS",
                request_id,
                public_tool_name,
            )
            return argument_error

        vertical = self._verticals_by_name.get(route.vertical)
        if vertical is None:
            logger.error(
                "Configured vertical unavailable request_id=%s public_tool=%s vertical=%s "
                "safe_error_code=VERTICAL_UNAVAILABLE",
                request_id,
                public_tool_name,
                route.vertical,
            )
            return vertical_unavailable()

        try:
            raw_response = vertical.invoke(route.upstream_tool, arguments)
        except TimeoutError:
            logger.warning(
                "Upstream timeout request_id=%s public_tool=%s vertical=%s upstream_tool=%s "
                "safe_error_code=UPSTREAM_TIMEOUT",
                request_id,
                public_tool_name,
                route.vertical,
                route.upstream_tool,
            )
            return upstream_timeout()
        except Exception:
            logger.exception(
                "Upstream error request_id=%s public_tool=%s vertical=%s upstream_tool=%s "
                "safe_error_code=UPSTREAM_ERROR",
                request_id,
                public_tool_name,
                route.vertical,
                route.upstream_tool,
            )
            return upstream_error()

        if not _is_normalizable_response(raw_response):
            logger.error(
                "Malformed upstream response request_id=%s public_tool=%s vertical=%s "
                "upstream_tool=%s safe_error_code=MALFORMED_UPSTREAM_RESPONSE",
                request_id,
                public_tool_name,
                route.vertical,
                route.upstream_tool,
            )
            return malformed_upstream_response()

        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.info(
            "Tool invocation succeeded request_id=%s public_tool=%s vertical=%s upstream_tool=%s "
            "latency_ms=%s",
            request_id,
            public_tool_name,
            route.vertical,
            route.upstream_tool,
            latency_ms,
        )
        return ToolResult(ok=True, data=raw_response)

    def _validate_arguments(
        self,
        arguments: dict[str, Any],
        input_schema: dict[str, Any],
    ) -> ToolResult | None:
        if not isinstance(arguments, dict):
            return invalid_arguments({"reason": "Arguments must be a JSON object."})

        try:
            validate(instance=arguments, schema=input_schema)
        except ValidationError as exc:
            return invalid_arguments(_validation_error_details(exc))

        return None


def _validation_error_details(exc: ValidationError) -> dict[str, Any]:
    path = ".".join(str(part) for part in exc.path)
    return {
        "reason": exc.message,
        "path": path or None,
    }


def _is_normalizable_response(response: Any) -> bool:
    if not isinstance(response, dict):
        return False

    try:
        json.dumps(response)
    except (TypeError, ValueError):
        return False

    return True

"""Runtime registry for the immutable public catalog snapshot."""

from app.models.catalog import CatalogSnapshot
from app.models.tools import PublicTool, ToolRoute
from app.models.validation import ValidationReport


class CatalogRegistry:
    """Read-only access facade for a built catalog snapshot."""

    def __init__(self, snapshot: CatalogSnapshot) -> None:
        self._snapshot = snapshot
        self._tools_by_name = {tool.name: tool for tool in snapshot.tools}

    def list_tools(self, vertical_filter: str | None = None) -> list[PublicTool]:
        """Return accepted public tools, optionally limited to one internal vertical."""
        if vertical_filter is None:
            return list(self._snapshot.tools)

        filtered_tools: list[PublicTool] = []
        for tool in self._snapshot.tools:
            route = self._snapshot.routes.get(tool.name)

            if route is not None and route.vertical == vertical_filter:
                filtered_tools.append(tool)

        return filtered_tools

    def get_tool(self, public_name: str) -> PublicTool | None:
        """Return one accepted public tool by public name, if present."""
        return self._tools_by_name.get(public_name)

    def get_route(self, public_name: str) -> ToolRoute | None:
        """Return the internal route for a public tool, if present."""
        return self._snapshot.routes.get(public_name)

    def get_snapshot(self) -> CatalogSnapshot:
        """Return the full immutable catalog snapshot."""
        return self._snapshot

    def get_validation_report(self) -> ValidationReport | None:
        """Return the validation report generated while building the catalog."""
        return self._snapshot.validation_report

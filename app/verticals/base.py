"""Common interface for internal vertical services."""

from typing import Any, Protocol

from app.models.tools import CandidateTool


class VerticalService(Protocol):
    """Protocol implemented by all internal vertical mock services."""

    name: str

    def list_tools(self) -> list[CandidateTool]:
        """Return candidate tools proposed by this vertical for proxy curation."""
        ...

    def invoke(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Invoke an internal vertical tool and return a JSON-serializable payload."""
        ...

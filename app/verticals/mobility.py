"""Mock mobility vertical service."""

from typing import Any

from app.models.tools import CandidateTool


class MobilityVertical:

    name = "mobility"

    def list_tools(self) -> list[CandidateTool]:
        """Return mobility candidate tools proposed for proxy curation."""
        return [
            CandidateTool(
                vertical=self.name,
                upstream_tool="search",
                description=(
                    "Search available mobility options such as rental cars, trains, "
                    "and shared transport for a requested trip."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "origin": {
                            "type": "string",
                            "description": "Trip origin city, station, or address.",
                        },
                        "destination": {
                            "type": "string",
                            "description": "Trip destination city, station, or address.",
                        },
                        "date": {
                            "type": "string",
                            "description": "Desired travel date in ISO format YYYY-MM-DD.",
                        },
                        "passengers": {
                            "type": "integer",
                            "minimum": 1,
                            "description": "Number of passengers travelling.",
                        },
                    },
                    "required": ["origin", "destination", "date"],
                    "additionalProperties": False,
                },
                response_schema={
                    "type": "object",
                    "properties": {
                        "options": {"type": "array"},
                    },
                },
                safe_to_expose=True,
                internal_version="1.0",
            ),
            CandidateTool(
                vertical=self.name,
                upstream_tool="book",
                description=(
                    "Book a selected mobility option and commit the customer to the trip."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "option_id": {
                            "type": "string",
                            "description": "Identifier of the mobility option to book.",
                        },
                        "payment_token": {
                            "type": "string",
                            "description": "Payment token used to complete the booking.",
                        },
                    },
                    "required": ["option_id", "payment_token"],
                    "additionalProperties": False,
                },
                safe_to_expose=True,
                internal_version="1.0",
            ),
        ]

    def invoke(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Invoke a mobility upstream tool and return static mock data."""
        if tool_name == "search":
            return {
                "vertical": self.name,
                "upstream_tool": tool_name,
                "query": {
                    "origin": arguments.get("origin"),
                    "destination": arguments.get("destination"),
                    "date": arguments.get("date"),
                    "passengers": arguments.get("passengers", 1),
                },
                "options": [
                    {
                        "option_id": "mob-train-001",
                        "type": "train",
                        "provider": "MockRail",
                        "duration_minutes": 95,
                        "price_eur": 29.9,
                    },
                    {
                        "option_id": "mob-car-002",
                        "type": "rental_car",
                        "provider": "MockDrive",
                        "duration_minutes": 80,
                        "price_eur": 54.5,
                    },
                ],
            }

        if tool_name == "book":
            option_id = arguments.get("option_id")
            return {
                "vertical": self.name,
                "upstream_tool": tool_name,
                "booking_id": f"booking-{option_id or 'unknown'}",
                "option_id": option_id,
                "status": "confirmed",
                "payment_status": "authorized" if arguments.get("payment_token") else "missing_payment_token",
            }

        raise ValueError(f"Unknown mobility tool: {tool_name}")

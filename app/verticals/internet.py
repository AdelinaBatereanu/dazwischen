"""Mock internet vertical service."""

from typing import Any

from app.models.tools import CandidateTool


class InternetVertical:

    name = "internet"

    def list_tools(self) -> list[CandidateTool]:
        """Return internet candidate tools proposed for proxy curation."""
        return [
            CandidateTool(
                vertical=self.name,
                upstream_tool="check_availability",
                description=(
                    "Check available home internet plans for a requested service address."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "address": {
                            "type": "string",
                            "description": "Service installation address.",
                        },
                        "postal_code": {
                            "type": "string",
                            "description": "Postal code for the service address.",
                        },
                        "desired_speed_mbps": {
                            "type": "integer",
                            "minimum": 1,
                            "description": "Desired download speed in Mbps.",
                        },
                    },
                    "required": ["address", "postal_code"],
                    "additionalProperties": False,
                },
                response_schema={
                    "type": "object",
                    "properties": {
                        "plans": {"type": "array"},
                    },
                },
                safe_to_expose=True,
                internal_version="1.0",
            ),
            CandidateTool(
                vertical=self.name,
                upstream_tool="order_plan",
                description=(
                    "Order a selected internet plan and create an installation appointment."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "plan_id": {
                            "type": "string",
                            "description": "Identifier of the internet plan to order.",
                        },
                        "customer_id": {
                            "type": "string",
                            "description": "Internal customer identifier for the order.",
                        },
                        "installation_date": {
                            "type": "string",
                            "description": "Requested installation date in ISO format YYYY-MM-DD.",
                        },
                    },
                    "required": ["plan_id", "customer_id", "installation_date"],
                    "additionalProperties": False,
                },
                safe_to_expose=False,
                internal_version="1.0",
            ),
            CandidateTool(
                vertical=self.name,
                upstream_tool="run_diagnostics_command",
                description=(
                    "Run a raw internal diagnostics command against network equipment "
                    "and return device logs for troubleshooting."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "device_id": {
                            "type": "string",
                            "description": "Internal network device identifier.",
                        },
                        "command": {
                            "type": "string",
                            "description": "Raw diagnostics command to execute on the device.",
                        },
                    },
                    "required": ["device_id", "command"],
                    "additionalProperties": False,
                },
                response_schema={
                    "type": "object",
                    "properties": {
                        "stdout": {"type": "string"},
                        "stderr": {"type": "string"},
                        "device_logs": {"type": "array"},
                    },
                },
                safe_to_expose=True,
                internal_version="1.0",
            ),
        ]

    def invoke(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Invoke an internet upstream tool and return static mock data."""
        if tool_name == "check_availability":
            desired_speed = arguments.get("desired_speed_mbps")
            return {
                "vertical": self.name,
                "upstream_tool": tool_name,
                "query": {
                    "address": arguments.get("address"),
                    "postal_code": arguments.get("postal_code"),
                    "desired_speed_mbps": desired_speed,
                },
                "plans": [
                    {
                        "plan_id": "net-fiber-100",
                        "technology": "fiber",
                        "provider": "MockFiber",
                        "download_mbps": 100,
                        "upload_mbps": 50,
                        "monthly_price_eur": 29.99,
                    },
                    {
                        "plan_id": "net-fiber-500",
                        "technology": "fiber",
                        "provider": "MockFiber",
                        "download_mbps": 500,
                        "upload_mbps": 250,
                        "monthly_price_eur": 49.99,
                    },
                    {
                        "plan_id": "net-cable-250",
                        "technology": "cable",
                        "provider": "MockCable",
                        "download_mbps": 250,
                        "upload_mbps": 40,
                        "monthly_price_eur": 39.99,
                    },
                ],
            }

        if tool_name == "order_plan":
            plan_id = arguments.get("plan_id")
            return {
                "vertical": self.name,
                "upstream_tool": tool_name,
                "order_id": f"order-{plan_id or 'unknown'}",
                "plan_id": plan_id,
                "customer_id": arguments.get("customer_id"),
                "installation_date": arguments.get("installation_date"),
                "status": "scheduled",
            }

        if tool_name == "run_diagnostics_command":
            return {
                "vertical": self.name,
                "upstream_tool": tool_name,
                "device_id": arguments.get("device_id"),
                "command": arguments.get("command"),
                "exit_code": 0,
                "stdout": "Mock diagnostics completed successfully.",
                "stderr": "",
                "device_logs": [
                    "mock-router-17 interface ge-0/0/1 up",
                    "mock-router-17 bgp session stable",
                    "mock-router-17 internal trace id dbg-8841",
                ],
            }

        raise ValueError(f"Unknown internet tool: {tool_name}")

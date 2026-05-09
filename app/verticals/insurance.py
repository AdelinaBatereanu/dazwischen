"""Mock insurance vertical service."""

from typing import Any

from app.models.tools import CandidateTool


class InsuranceVertical:

    name = "insurance"

    def list_tools(self) -> list[CandidateTool]:
        """Return insurance candidate tools proposed for proxy curation."""
        return [
            CandidateTool(
                vertical=self.name,
                upstream_tool="quote",
                description=(
                    "Generate an indicative insurance quote for a requested product "
                    "and customer profile."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "product_type": {
                            "type": "string",
                            "enum": ["travel", "home", "car"],
                            "description": "Insurance product to quote.",
                        },
                        "coverage_amount_eur": {
                            "type": "number",
                            "minimum": 1000,
                            "description": "Requested coverage amount in EUR.",
                        },
                        "customer_age": {
                            "type": "integer",
                            "minimum": 18,
                            "description": "Age of the customer.",
                        },
                    },
                    "required": ["product_type", "coverage_amount_eur", "customer_age"],
                    "additionalProperties": False,
                },
                response_schema={
                    "type": "object",
                    "properties": {
                        "quotes": {"type": "array"},
                    },
                },
                safe_to_expose=True,
                internal_version="1.0",
            ),
            CandidateTool(
                vertical=self.name,
                upstream_tool="bind_policy",
                description=(
                    "Bind a selected insurance quote into an active policy and charge "
                    "the customer."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "quote_id": {
                            "type": "string",
                            "description": "Identifier of the quote to bind.",
                        },
                        "payment_token": {
                            "type": "string",
                            "description": "Payment token used to activate the policy.",
                        },
                    },
                    "required": ["quote_id", "payment_token"],
                    "additionalProperties": False,
                },
                safe_to_expose=False,
                internal_version="1.0",
            ),
            CandidateTool(
                vertical=self.name,
                upstream_tool="quote_with_ssn",
                description=(
                    "Generate an insurance quote using the customer's Social Security "
                    "number for identity and risk lookup."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "product_type": {
                            "type": "string",
                            "enum": ["travel", "home", "car"],
                            "description": "Insurance product to quote.",
                        },
                        "coverage_amount_eur": {
                            "type": "number",
                            "minimum": 1000,
                            "description": "Requested coverage amount in EUR.",
                        },
                        "customer_age": {
                            "type": "integer",
                            "minimum": 18,
                            "description": "Age of the customer.",
                        },
                        "ssn": {
                            "type": "string",
                            "description": "Customer Social Security number.",
                        },
                    },
                    "required": [
                        "product_type",
                        "coverage_amount_eur",
                        "customer_age",
                        "ssn",
                    ],
                    "additionalProperties": False,
                },
                response_schema={
                    "type": "object",
                    "properties": {
                        "quotes": {"type": "array"},
                        "risk_lookup_id": {"type": "string"},
                    },
                },
                safe_to_expose=True,
                internal_version="1.0",
            ),
        ]

    def invoke(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Invoke an insurance upstream tool and return static mock data."""
        if tool_name == "quote":
            product_type = arguments.get("product_type")
            coverage_amount = arguments.get("coverage_amount_eur") or 0
            customer_age = arguments.get("customer_age") or 0
            base_premium = round((float(coverage_amount) * 0.012) + (int(customer_age) * 0.8), 2)

            return {
                "vertical": self.name,
                "upstream_tool": tool_name,
                "query": {
                    "product_type": product_type,
                    "coverage_amount_eur": coverage_amount,
                    "customer_age": customer_age,
                },
                "quotes": [
                    {
                        "quote_id": "ins-standard-001",
                        "product_type": product_type,
                        "provider": "MockCover Standard",
                        "coverage_amount_eur": coverage_amount,
                        "monthly_premium_eur": base_premium,
                    },
                    {
                        "quote_id": "ins-premium-002",
                        "product_type": product_type,
                        "provider": "MockCover Premium",
                        "coverage_amount_eur": coverage_amount,
                        "monthly_premium_eur": round(base_premium * 1.35, 2),
                    },
                ],
            }

        if tool_name == "bind_policy":
            quote_id = arguments.get("quote_id")
            return {
                "vertical": self.name,
                "upstream_tool": tool_name,
                "policy_id": f"policy-{quote_id or 'unknown'}",
                "quote_id": quote_id,
                "status": "active",
                "payment_status": "authorized" if arguments.get("payment_token") else "missing_payment_token",
            }

        if tool_name == "quote_with_ssn":
            product_type = arguments.get("product_type")
            coverage_amount = arguments.get("coverage_amount_eur") or 0
            customer_age = arguments.get("customer_age") or 0
            base_premium = round((float(coverage_amount) * 0.01) + (int(customer_age) * 0.7), 2)

            return {
                "vertical": self.name,
                "upstream_tool": tool_name,
                "query": {
                    "product_type": product_type,
                    "coverage_amount_eur": coverage_amount,
                    "customer_age": customer_age,
                    "ssn": arguments.get("ssn"),
                },
                "risk_lookup_id": "risk-ssn-lookup-001",
                "quotes": [
                    {
                        "quote_id": "ins-ssn-standard-001",
                        "product_type": product_type,
                        "provider": "MockCover Identity",
                        "coverage_amount_eur": coverage_amount,
                        "monthly_premium_eur": base_premium,
                    }
                ],
            }

        raise ValueError(f"Unknown insurance tool: {tool_name}")

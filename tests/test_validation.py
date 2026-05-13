from app.models.tools import CandidateTool
from app.models.validation import ToolValidationStatus
from app.validation.conformance import ToolConformanceValidator
from app.verticals.insurance import InsuranceVertical
from app.verticals.internet import InternetVertical
from app.verticals.mobility import MobilityVertical


def valid_candidate(**overrides: object) -> CandidateTool:
    """Build a valid baseline candidate and allow per-test overrides."""
    data = {
        "vertical": "mobility",
        "upstream_tool": "search_options",
        "description": "Search available mobility options for a requested trip.",
        "input_schema": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Trip origin."},
                "destination": {"type": "string", "description": "Trip destination."},
            },
            "required": ["origin", "destination"],
            "additionalProperties": False,
        },
        "safe_to_expose": True,
        "internal_version": "1.0",
    }
    data.update(overrides)
    return CandidateTool(**data)


def issue_codes(candidate: CandidateTool) -> set[str]:
    result = ToolConformanceValidator().validate_tool(candidate)
    return {reason.code for reason in result.reasons}


def test_valid_candidate_is_accepted() -> None:
    result = ToolConformanceValidator().validate_tool(valid_candidate())

    assert result.status == ToolValidationStatus.ACCEPTED
    assert result.reasons == []
    assert result.vertical == "mobility"
    assert result.tool == "search_options"


def test_current_vertical_candidates_validate_as_three_accepted_and_five_rejected() -> None:
    candidates = [
        *MobilityVertical().list_tools(),
        *InternetVertical().list_tools(),
        *InsuranceVertical().list_tools(),
    ]

    report = ToolConformanceValidator().validate_all(candidates)

    accepted = {(result.vertical, result.tool) for result in report.results if result.status == "accepted"}
    rejected = {(result.vertical, result.tool) for result in report.results if result.status == "rejected"}

    assert accepted == {
        ("mobility", "search"),
        ("internet", "check_availability"),
        ("insurance", "quote"),
    }
    assert rejected == {
        ("mobility", "book"),
        ("internet", "order_plan"),
        ("internet", "run_diagnostics_command"),
        ("insurance", "bind_policy"),
        ("insurance", "quote_with_ssn"),
    }


def test_missing_required_fields_are_reported_without_duplicate_format_errors() -> None:
    candidate = valid_candidate(
        vertical=" ",
        upstream_tool="",
        internal_version="\t",
        description="",
        input_schema={},
    )

    codes = issue_codes(candidate)

    assert {
        "MISSING_VERTICAL",
        "MISSING_UPSTREAM_TOOL",
        "MISSING_INTERNAL_VERSION",
        "MISSING_DESCRIPTION",
        "MISSING_INPUT_SCHEMA",
    } <= codes
    assert "INVALID_VERTICAL_NAME" not in codes
    assert "INVALID_UPSTREAM_TOOL_NAME" not in codes
    assert "INVALID_INTERNAL_VERSION" not in codes


def test_identity_fields_must_use_proxy_supported_formats() -> None:
    candidate = valid_candidate(
        vertical="Internet Sales",
        upstream_tool="CheckAvailability",
        internal_version="v1-beta",
    )

    assert issue_codes(candidate) >= {
        "INVALID_VERTICAL_NAME",
        "INVALID_UPSTREAM_TOOL_NAME",
        "INVALID_INTERNAL_VERSION",
    }


def test_vertical_marked_unsafe_tool_is_rejected() -> None:
    result = ToolConformanceValidator().validate_tool(
        valid_candidate(safe_to_expose=False)
    )

    assert result.status == ToolValidationStatus.REJECTED
    assert issue_codes(valid_candidate(safe_to_expose=False)) == {"VERTICAL_MARKED_UNSAFE"}


def test_unsafe_or_destructive_actions_are_rejected_even_if_marked_safe() -> None:
    codes = issue_codes(
        valid_candidate(
            upstream_tool="book",
            description="Book a selected offer and commit the customer to the trip.",
        )
    )

    assert "UNSAFE_ACTION" in codes


def test_internal_debug_or_raw_command_leakage_is_rejected() -> None:
    codes = issue_codes(
        valid_candidate(
            upstream_tool="run_diagnostics_command",
            description="Run a raw internal debug command on a private device.",
            input_schema={
                "type": "object",
                "properties": {
                    "device_id": {"type": "string"},
                    "command": {"type": "string"},
                },
                "required": ["device_id", "command"],
            },
        )
    )

    assert "INTERNAL_LEAKAGE" in codes


def test_sensitive_personal_data_collection_is_rejected() -> None:
    codes = issue_codes(
        valid_candidate(
            upstream_tool="quote_with_ssn",
            description="Generate an insurance quote using a social security number.",
            input_schema={
                "type": "object",
                "properties": {
                    "product_type": {"type": "string"},
                    "ssn": {"type": "string", "description": "Customer SSN."},
                },
                "required": ["product_type", "ssn"],
            },
        )
    )

    assert "SENSITIVE_DATA_COLLECTION" in codes


def test_description_quality_checks_reject_short_or_placeholder_text() -> None:
    short_codes = issue_codes(valid_candidate(description="Search trips"))
    placeholder_codes = issue_codes(valid_candidate(description="TODO placeholder"))

    assert "DESCRIPTION_TOO_SHORT" in short_codes
    assert "DESCRIPTION_PLACEHOLDER" in placeholder_codes


def test_input_schema_must_be_valid_object_schema_with_properties() -> None:
    codes = issue_codes(
        valid_candidate(
            input_schema={
                "type": "array",
                "properties": {},
                "required": "origin",
            }
        )
    )

    assert {
        "SCHEMA_TOP_LEVEL_NOT_OBJECT",
        "SCHEMA_MISSING_PROPERTIES",
        "SCHEMA_REQUIRED_NOT_LIST",
    } <= codes


def test_input_schema_required_fields_must_be_defined_string_properties() -> None:
    codes = issue_codes(
        valid_candidate(
            input_schema={
                "type": "object",
                "properties": {"origin": {"type": "string"}},
                "required": ["origin", "destination", 123],
            }
        )
    )

    assert "SCHEMA_REQUIRED_FIELD_NOT_DEFINED" in codes
    assert "SCHEMA_REQUIRED_FIELD_INVALID" in codes


def test_input_schema_rejects_composition_and_ref_keywords_anywhere() -> None:
    codes = issue_codes(
        valid_candidate(
            input_schema={
                "type": "object",
                "properties": {
                    "origin": {"$ref": "#/defs/location"},
                    "destination": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "object", "properties": {"id": {"type": "string"}}},
                        ]
                    },
                },
                "required": ["origin", "destination"],
            }
        )
    )

    assert "SCHEMA_COMPOSITION_NOT_ALLOWED" in codes


def test_invalid_json_schema_is_reported() -> None:
    codes = issue_codes(
        valid_candidate(
            input_schema={
                "type": "object",
                "properties": {"origin": {"type": 123}},
                "required": ["origin"],
            }
        )
    )

    assert "INVALID_JSON_SCHEMA" in codes


def test_rejection_report_contains_actionable_codes_messages_and_fields() -> None:
    result = ToolConformanceValidator().validate_tool(
        valid_candidate(
            upstream_tool="delete_private_database",
            description="Delete a private database record using a secret token.",
            input_schema={
                "type": "object",
                "properties": {"token": {"type": "string"}},
                "required": ["token"],
            },
        )
    )

    assert result.status == ToolValidationStatus.REJECTED
    assert result.reasons
    for reason in result.reasons:
        assert reason.code
        assert reason.message
        assert reason.field

"""Conformance validator for internal vertical candidate tools."""

import re
from collections.abc import Iterable
from typing import Any

from jsonschema import SchemaError
from jsonschema.validators import Draft202012Validator

from app.models.tools import CandidateTool
from app.models.validation import ToolValidationStatus, ValidationIssue, ValidationReport, ValidationResult
from app.validation.reports import issue

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_VERSION_RE = re.compile(r"^\d+(?:\.\d+)*$")

UNSAFE_ACTION_TERMS = {
    "book",
    "buy",
    "purchase",
    "delete",
    "cancel",
    "pay",
    "charge",
    "order",
    "bind",
    "create_contract",
    "contract",
    "commit",
}

INTERNAL_LEAKAGE_TERMS = {
    "internal",
    "debug",
    "admin",
    "private",
    "database",
    "token",
    "secret",
    "hostname",
    "diagnostics",
    "diagnostics_command",
    "raw",
    "command",
    "device_logs",
}

SENSITIVE_DATA_TERMS = {
    "ssn",
    "social_security",
    "social security",
    "passport",
    "national_id",
}

PLACEHOLDER_DESCRIPTIONS = {
    "todo",
    "tbd",
    "does stuff",
    "test",
    "placeholder",
}

PROHIBITED_SCHEMA_KEYS = {"$ref", "oneOf", "anyOf", "allOf"}


class ToolConformanceValidator:
    """Validate whether candidate tools are safe and well-formed enough for cataloging."""

    def validate_tool(self, candidate: CandidateTool) -> ValidationResult:
        """Validate one candidate tool and return a structured result."""
        issues: list[ValidationIssue] = []
        issues.extend(self._check_required_fields(candidate))
        issues.extend(self._check_identity_format(candidate))
        issues.extend(self._check_vertical_attestation(candidate))
        issues.extend(self._check_unsafe_actions(candidate))
        issues.extend(self._check_internal_leakage(candidate))
        issues.extend(self._check_sensitive_data(candidate))
        issues.extend(self._check_description_length(candidate))
        issues.extend(self._check_description_placeholder(candidate))
        issues.extend(self._check_input_schema(candidate))

        status = ToolValidationStatus.REJECTED if issues else ToolValidationStatus.ACCEPTED
        return ValidationResult(
            vertical=candidate.vertical,
            tool=candidate.upstream_tool,
            status=status,
            reasons=issues,
        )

    def validate_all(self, candidates: Iterable[CandidateTool]) -> ValidationReport:
        """Validate all candidate tools and return one complete report."""
        return ValidationReport(results=[self.validate_tool(candidate) for candidate in candidates])

    def _check_required_fields(self, candidate: CandidateTool) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        if not _has_text(candidate.vertical):
            issues.append(issue("MISSING_VERTICAL", "Vertical owner is required.", "vertical"))
        if not _has_text(candidate.upstream_tool):
            issues.append(
                issue("MISSING_UPSTREAM_TOOL", "Internal upstream tool name is required.", "upstream_tool")
            )
        if not _has_text(candidate.internal_version):
            issues.append(
                issue(
                    "MISSING_INTERNAL_VERSION",
                    "Internal version is required for deterministic catalog mapping.",
                    "internal_version",
                )
            )
        if not _has_text(candidate.description):
            issues.append(issue("MISSING_DESCRIPTION", "Tool description is required.", "description"))
        if not candidate.input_schema or not isinstance(candidate.input_schema, dict):
            issues.append(
                issue(
                    "MISSING_INPUT_SCHEMA",
                    "Input schema must be a non-empty JSON Schema object.",
                    "input_schema",
                )
            )

        return issues

    def _check_identity_format(self, candidate: CandidateTool) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        if _has_text(candidate.vertical) and not _NAME_RE.fullmatch(candidate.vertical):
            issues.append(
                issue(
                    "INVALID_VERTICAL_NAME",
                    "Vertical name must be lowercase snake_case without spaces.",
                    "vertical",
                )
            )
        if _has_text(candidate.upstream_tool) and not _NAME_RE.fullmatch(candidate.upstream_tool):
            issues.append(
                issue(
                    "INVALID_UPSTREAM_TOOL_NAME",
                    "Upstream tool name must be lowercase snake_case without spaces.",
                    "upstream_tool",
                )
            )
        if _has_text(candidate.internal_version) and not _VERSION_RE.fullmatch(candidate.internal_version):
            issues.append(
                issue(
                    "INVALID_INTERNAL_VERSION",
                    "Internal version must use a numeric dotted format such as '1.0'.",
                    "internal_version",
                )
            )

        return issues

    def _check_vertical_attestation(self, candidate: CandidateTool) -> list[ValidationIssue]:
        if candidate.safe_to_expose:
            return []
        return [
            issue(
                "VERTICAL_MARKED_UNSAFE",
                "Vertical marked this tool as unsafe to expose.",
                "safe_to_expose",
            )
        ]

    def _check_unsafe_actions(self, candidate: CandidateTool) -> list[ValidationIssue]:
        matched = _find_terms(_candidate_text(candidate), UNSAFE_ACTION_TERMS)
        if not matched:
            return []
        return [
            issue(
                "UNSAFE_ACTION",
                "Tool appears to perform an unsafe or destructive action: "
                f"{', '.join(matched)}.",
                "upstream_tool",
            )
        ]

    def _check_internal_leakage(self, candidate: CandidateTool) -> list[ValidationIssue]:
        matched = _find_terms(_candidate_text(candidate), INTERNAL_LEAKAGE_TERMS)
        if not matched:
            return []
        return [
            issue(
                "INTERNAL_LEAKAGE",
                "Tool exposes internal/debug/private concepts: " f"{', '.join(matched)}.",
                "description",
            )
        ]

    def _check_sensitive_data(self, candidate: CandidateTool) -> list[ValidationIssue]:
        matched = _find_terms(_candidate_text(candidate), SENSITIVE_DATA_TERMS)
        if not matched:
            return []
        return [
            issue(
                "SENSITIVE_DATA_COLLECTION",
                "Tool collects sensitive personal data not suitable for this public demo: "
                f"{', '.join(matched)}.",
                "input_schema",
            )
        ]

    def _check_description_length(self, candidate: CandidateTool) -> list[ValidationIssue]:
        if not _has_text(candidate.description):
            return []

        if len(candidate.description.strip()) >= 20:
            return []

        return [
            issue(
                "DESCRIPTION_TOO_SHORT",
                "Description must clearly explain what the tool does.",
                "description",
            )
        ]

    def _check_description_placeholder(self, candidate: CandidateTool) -> list[ValidationIssue]:
        if not _has_text(candidate.description):
            return []

        normalized = candidate.description.strip().lower()
        has_placeholder = normalized in PLACEHOLDER_DESCRIPTIONS or any(
            placeholder in normalized for placeholder in PLACEHOLDER_DESCRIPTIONS
        )
        if not has_placeholder:
            return []

        return [
            issue(
                "DESCRIPTION_PLACEHOLDER",
                "Description must not be placeholder text.",
                "description",
            )
        ]

    def _check_input_schema(self, candidate: CandidateTool) -> list[ValidationIssue]:
        schema = candidate.input_schema
        if not isinstance(schema, dict) or not schema:
            return []

        issues: list[ValidationIssue] = []

        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            issues.append(
                issue(
                    "INVALID_JSON_SCHEMA",
                    f"Input schema must be a valid JSON Schema object: {exc.message}.",
                    "input_schema",
                )
            )

        if schema.get("type") != "object":
            issues.append(
                issue(
                    "SCHEMA_TOP_LEVEL_NOT_OBJECT",
                    "Input schema top-level type must be 'object'.",
                    "input_schema.type",
                )
            )

        properties = schema.get("properties")
        if not isinstance(properties, dict) or not properties:
            issues.append(
                issue(
                    "SCHEMA_MISSING_PROPERTIES",
                    "Input schema must define at least one property.",
                    "input_schema.properties",
                )
            )
            properties = {}

        required = schema.get("required", [])
        if not isinstance(required, list):
            issues.append(
                issue(
                    "SCHEMA_REQUIRED_NOT_LIST",
                    "Input schema 'required' must be a list of property names.",
                    "input_schema.required",
                )
            )
        else:
            for required_field in required:
                if not isinstance(required_field, str):
                    issues.append(
                        issue(
                            "SCHEMA_REQUIRED_FIELD_INVALID",
                            "Every required field must be a string property name.",
                            "input_schema.required",
                        )
                    )
                elif required_field not in properties:
                    issues.append(
                        issue(
                            "SCHEMA_REQUIRED_FIELD_NOT_DEFINED",
                            f"Required field '{required_field}' is not defined in properties.",
                            "input_schema.required",
                        )
                    )

        for key in _find_schema_keys(schema, PROHIBITED_SCHEMA_KEYS):
            issues.append(
                issue(
                    "SCHEMA_COMPOSITION_NOT_ALLOWED",
                    f"Input schema key '{key}' is not allowed for public candidate tools.",
                    "input_schema",
                )
            )

        return issues


def _has_text(value: str) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _candidate_text(candidate: CandidateTool) -> str:
    schema_terms = " ".join(_schema_text_values(candidate.input_schema))
    return " ".join(
        [
            candidate.vertical,
            candidate.upstream_tool,
            candidate.description,
            schema_terms,
        ]
    ).lower()


def _schema_text_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        terms: list[str] = []
        for key, nested_value in value.items():
            terms.append(str(key))
            terms.extend(_schema_text_values(nested_value))
        return terms
    if isinstance(value, list):
        terms = []
        for item in value:
            terms.extend(_schema_text_values(item))
        return terms
    if isinstance(value, str):
        return [value]
    return []


def _find_terms(text: str, terms: set[str]) -> list[str]:
    normalized = text.lower().replace("-", "_")
    matches = []
    for term in sorted(terms):
        pattern = rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])"
        if re.search(pattern, normalized):
            matches.append(term)
    return matches


def _find_schema_keys(value: Any, prohibited_keys: set[str]) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, nested_value in value.items():
            if key in prohibited_keys:
                found.append(key)
            found.extend(_find_schema_keys(nested_value, prohibited_keys))
    elif isinstance(value, list):
        for item in value:
            found.extend(_find_schema_keys(item, prohibited_keys))
    return found

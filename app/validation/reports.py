"""Helpers for building validation reports."""

from app.models.validation import ValidationIssue


def issue(code: str, message: str, field: str | None = None) -> ValidationIssue:
    """Create a structured validation issue with actionable remediation text."""
    return ValidationIssue(code=code, message=message, field=field)

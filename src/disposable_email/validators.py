"""Validator for any Django form or model field (invitations, contact forms...)."""

from .enforce import enforce


def validate_not_disposable(value: str) -> None:
    """Raise ``ValidationError`` if ``value`` uses a disposable or blocked domain."""
    enforce(value, source="validator")

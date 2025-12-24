"""Common utilities shared across ingestor modules."""

from typing import Any


def throttle_request(seconds: float) -> None:
    """Placeholder for throttling outbound requests."""
    raise NotImplementedError("Request throttling not implemented yet")


def normalize_text(value: str) -> str:
    """Return normalized text used when comparing staff names."""
    return value.strip().lower()

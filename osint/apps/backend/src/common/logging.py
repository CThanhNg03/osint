"""Shared logging setup for the FastAPI application."""

import logging


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logger with a simple format."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

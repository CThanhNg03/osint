"""Use case for retrieving live monitoring state."""

from apps.backend.src.usecases.live_toggle import _live_state


def execute() -> dict:
    """Return the current state."""
    return _live_state.copy()

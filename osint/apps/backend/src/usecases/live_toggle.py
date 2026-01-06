"""Use case to toggle live monitoring."""

_live_state = {"enabled": False}


def execute(enabled: bool) -> dict:
    """Update live monitoring state."""
    _live_state["enabled"] = enabled
    return _live_state.copy()

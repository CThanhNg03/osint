"""Common exception definitions and HTTP error helpers."""

from fastapi import HTTPException, status


class NotFoundError(Exception):
    """Raised when an entity cannot be located."""


class BadRequestError(Exception):
    """Raised when user input is invalid."""


def http_error_from_exc(exc: Exception) -> HTTPException:
    """Translate domain exceptions into HTTP errors."""
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, BadRequestError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

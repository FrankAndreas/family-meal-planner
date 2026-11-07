from fastapi import HTTPException

from .errors import detail


def api_error(status: int, code: str, **params) -> HTTPException:
    """An error the frontend shows in the person's language, raised by a route (anything else raises errors.Refused,
    which main.py answers the same way)."""
    return HTTPException(status, detail(code, **params))

"""Exception types shared by every layer of notesvc.

Each ``ApiError`` subclass carries the HTTP status the API layer reports, so
service code can simply ``raise NotFound(...)`` and never think about HTTP.
"""
from __future__ import annotations


class ApiError(Exception):
    """Base class for errors that map to a well-defined HTTP response."""

    status = 500

    def __init__(self, message: str = "error") -> None:
        super().__init__(message)
        self.message = message


class ValidationError(ApiError):
    """The request was well-formed HTTP but its content is not acceptable."""

    status = 400


class Unauthorized(ApiError):
    """No valid credentials were supplied."""

    status = 401


class Forbidden(ApiError):
    """The caller is authenticated but may not touch this resource."""

    status = 403


class NotFound(ApiError):
    """The addressed resource does not exist."""

    status = 404


class MethodNotAllowed(ApiError):
    """The path exists but not for this HTTP method."""

    status = 405


class Conflict(ApiError):
    """The request clashes with existing state (e.g. duplicate username)."""

    status = 409


class PayloadTooLarge(ApiError):
    """The request body exceeds the configured limit."""

    status = 413

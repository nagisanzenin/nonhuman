"""Input validators used by the service and API layers.

All validators raise :class:`~notesvc.errors.ValidationError` (HTTP 400), or
:class:`~notesvc.errors.PayloadTooLarge` (HTTP 413) for oversized bodies.
They return the cleaned value so callers can write ``x = validate_x(raw)``.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
from typing import Any

from .errors import PayloadTooLarge, ValidationError

# --- limits ---------------------------------------------------------------
MAX_BODY_BYTES = 64 * 1024            # default cap for any request body
MAX_UPLOAD_BODY_BYTES = 512 * 1024    # attachment uploads (base64 inflates)
MAX_ATTACHMENT_BYTES = 256 * 1024     # decoded attachment size
USERNAME_MIN, USERNAME_MAX = 3, 32
PASSWORD_MIN, PASSWORD_MAX = 8, 128
TITLE_MIN, TITLE_MAX = 1, 200
NOTE_BODY_MAX = 10_000
FILENAME_MAX = 100

SEARCH_MAX = 100
TAG_MAX = 20
MAX_TAGS_PER_NOTE = 10
LIST_LIMIT_DEFAULT, LIST_LIMIT_MAX = 20, 100
OFFSET_MAX = 1_000_000

_TAG_RE = re.compile(r"[a-z0-9-]+")
_USERNAME_RE = re.compile(r"[a-z0-9_]+")
_INT_RE = re.compile(r"[+-]?[0-9]{1,18}")


def check_body_size(raw: bytes | str | None, max_bytes: int = MAX_BODY_BYTES) -> None:
    """Reject bodies longer than ``max_bytes`` (measured in bytes)."""
    if raw is None:
        return
    size = len(raw) if isinstance(raw, (bytes, bytearray)) else len(raw.encode("utf-8"))
    if size > max_bytes:
        raise PayloadTooLarge(f"request body exceeds {max_bytes} bytes")


def parse_json_body(raw: bytes | str | None, max_bytes: int = MAX_BODY_BYTES) -> dict[str, Any]:
    """Parse a request body that must be a JSON object."""
    check_body_size(raw, max_bytes)
    if raw is None or len(raw) == 0:
        raise ValidationError("request body is required")
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise ValidationError("body is not valid JSON") from None
    if not isinstance(data, dict):
        raise ValidationError("body must be a JSON object")
    return data


def require_str(value: Any, name: str, min_len: int, max_len: int) -> str:
    """Return ``value`` if it is a string whose length is within bounds."""
    if not isinstance(value, str):
        raise ValidationError(f"{name} must be a string")
    if not (min_len <= len(value) <= max_len):
        raise ValidationError(f"{name} must be {min_len}-{max_len} characters")
    if "\x00" in value:
        raise ValidationError(f"{name} contains invalid characters")
    return value


def parse_int(raw: Any, name: str, minimum: int, maximum: int, default: int | None = None) -> int:
    """Parse an integer (int or decimal string) and enforce ``[minimum, maximum]``.

    ``None`` yields ``default`` when one is given. Out-of-range values are an
    error, not silently clamped, so clients notice mistakes.
    """
    if raw is None:
        if default is None:
            raise ValidationError(f"{name} is required")
        return default
    if isinstance(raw, bool):
        raise ValidationError(f"{name} must be an integer")
    if isinstance(raw, int):
        value = raw
    elif isinstance(raw, str) and _INT_RE.fullmatch(raw.strip()):
        value = int(raw.strip())
    else:
        raise ValidationError(f"{name} must be an integer")
    if not (minimum <= value <= maximum):
        raise ValidationError(f"{name} must be between {minimum} and {maximum}")
    return value


def validate_username(value: Any) -> str:
    username = require_str(value, "username", USERNAME_MIN, USERNAME_MAX)
    if not _USERNAME_RE.fullmatch(username):
        raise ValidationError("username may only contain a-z, 0-9 and _")
    return username


def validate_password(value: Any, name: str = "password") -> str:
    return require_str(value, name, PASSWORD_MIN, PASSWORD_MAX)


def validate_title(value: Any) -> str:
    title = require_str(value, "title", TITLE_MIN, TITLE_MAX).strip()
    if not title:
        raise ValidationError("title must not be blank")
    return title


def validate_note_body(value: Any) -> str:
    return require_str(value, "body", 0, NOTE_BODY_MAX)


def validate_filename(value: Any) -> str:
    """A bare file name: no separators, no dot-only names, bounded length."""
    name = require_str(value, "filename", 1, FILENAME_MAX)
    if "/" in name or "\\" in name or name in (".", "..") or name.startswith("."):
        raise ValidationError("filename is not allowed")
    return name


def decode_base64(value: Any, name: str, max_bytes: int) -> bytes:
    """Strictly decode base64 text and enforce a decoded size limit."""
    if not isinstance(value, str):
        raise ValidationError(f"{name} must be a base64 string")
    try:
        data = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise ValidationError(f"{name} is not valid base64") from None
    if len(data) > max_bytes:
        raise PayloadTooLarge(f"{name} exceeds {max_bytes} bytes")
    return data


def validate_search_query(value: Any) -> str:
    return require_str(value, "q", 1, SEARCH_MAX)


def validate_tag(value: Any) -> str:
    """Lower-case a tag and check it is 1-20 chars of a-z, 0-9 and '-'."""
    tag = require_str(value, "tag", 1, TAG_MAX).lower()
    if not _TAG_RE.fullmatch(tag):
        raise ValidationError("tag may only contain a-z, 0-9 and -")
    return tag


def validate_tag_list(value: Any) -> list[str]:
    """A non-empty list of valid tags, lower-cased and de-duplicated."""
    if not isinstance(value, list) or not value:
        raise ValidationError("tags must be a non-empty list")
    cleaned = {validate_tag(item) for item in value}
    if len(cleaned) > MAX_TAGS_PER_NOTE:
        raise ValidationError(f"at most {MAX_TAGS_PER_NOTE} tags per note")
    return sorted(cleaned)

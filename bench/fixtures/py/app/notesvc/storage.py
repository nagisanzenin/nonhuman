"""Attachment storage on local disk.

Layout: ``<root>/<owner_id>/<note_id>/<filename>``. All paths are built with
:func:`safe_join` so a hostile name can never escape the storage root.
"""
from __future__ import annotations

import os
from pathlib import Path

from .errors import ValidationError


class BadPath(ValidationError):
    """A path component tried to leave the storage root."""


def safe_join(root: str | os.PathLike[str], *parts: str) -> Path:
    """Join ``parts`` under ``root``; raise BadPath on traversal, absolute parts or NULs."""
    root_resolved = Path(root).resolve()
    candidate = root_resolved
    for part in parts:
        if not isinstance(part, str) or part == "" or "\x00" in part:
            raise BadPath("invalid path component")
        if os.path.isabs(part) or part.startswith(("/", "\\")):
            raise BadPath("absolute paths are not allowed")
        candidate = candidate / part
    resolved = candidate.resolve()
    if resolved == root_resolved or not resolved.is_relative_to(root_resolved):
        raise BadPath("path escapes storage root")
    return resolved


class AttachmentStore:
    """Reads and writes attachment bytes below one root directory."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, owner_id: int, note_id: int, filename: str) -> Path:
        return safe_join(self.root, str(owner_id), str(note_id), filename)

    def save(self, owner_id: int, note_id: int, filename: str, data: bytes) -> Path:
        path = self.path_for(owner_id, note_id, filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def read(self, owner_id: int, note_id: int, filename: str) -> bytes:
        return self.path_for(owner_id, note_id, filename).read_bytes()

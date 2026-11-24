"""notesvc: a small notes service with per-user notes and file attachments."""
from __future__ import annotations

import os

from .api import Api
from .db import Database
from .service import AppContext
from .storage import AttachmentStore

__all__ = ["create_app", "Api"]


def create_app(storage_root: str | os.PathLike[str], db_path: str = ":memory:") -> Api:
    """Build a ready-to-use :class:`Api` backed by SQLite and a storage directory."""
    return Api(AppContext(Database(db_path), AttachmentStore(storage_root)))

"""Business logic. Called by the API layer; knows nothing about HTTP framing."""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from typing import Any

from . import auth, validation
from .auth import User
from .db import Database
from .errors import Conflict, NotFound, ValidationError
from .storage import AttachmentStore


@dataclass
class AppContext:
    """Everything a service function needs: the database and the file store."""

    db: Database
    store: AttachmentStore


def note_view(row: sqlite3.Row) -> dict[str, Any]:
    """Public JSON shape of a note row."""
    return {
        "id": row["id"],
        "owner_id": row["owner_id"],
        "title": row["title"],
        "body": row["body"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def load_owned_note(ctx: AppContext, user: User, note_id: int) -> sqlite3.Row:
    """Fetch a note and enforce ownership (404 if missing, 403 if not yours)."""
    row = ctx.db.query_one("SELECT * FROM notes WHERE id = ?", (note_id,))
    if row is None:
        raise NotFound("note not found")
    auth.require_owner(user, row["owner_id"], "note")
    return row


# --- accounts -------------------------------------------------------------
def register(ctx: AppContext, username: Any, password: Any) -> dict[str, Any]:
    username = validation.validate_username(username)
    password = validation.validate_password(password)
    user = auth.create_user(ctx.db, username, password)
    return {"id": user.id, "username": user.username}


def login(ctx: AppContext, username: Any, password: Any) -> dict[str, Any]:
    if not isinstance(username, str) or not isinstance(password, str):
        raise ValidationError("username and password must be strings")
    user = auth.check_credentials(ctx.db, username, password)
    return {"token": auth.create_session(ctx.db, user.id)}


# --- notes ----------------------------------------------------------------
def create_note(ctx: AppContext, user: User, title: Any, body: Any = "") -> dict[str, Any]:
    title = validation.validate_title(title)
    body = validation.validate_note_body(body)
    now = int(time.time())
    note_id = ctx.db.insert(
        "INSERT INTO notes (owner_id, title, body, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (user.id, title, body, now, now),
    )
    return note_view(ctx.db.query_one("SELECT * FROM notes WHERE id = ?", (note_id,)))


def get_note(ctx: AppContext, user: User, note_id: int) -> dict[str, Any]:
    return note_view(load_owned_note(ctx, user, note_id))


def update_note(ctx: AppContext, user: User, note_id: int, fields: dict[str, Any]) -> dict[str, Any]:
    row = load_owned_note(ctx, user, note_id)
    if "title" not in fields and "body" not in fields:
        raise ValidationError("provide title and/or body")
    title = validation.validate_title(fields["title"]) if "title" in fields else row["title"]
    body = validation.validate_note_body(fields["body"]) if "body" in fields else row["body"]
    ctx.db.execute(
        "UPDATE notes SET title = ?, body = ?, updated_at = ? WHERE id = ?",
        (title, body, int(time.time()), note_id),
    )
    return note_view(ctx.db.query_one("SELECT * FROM notes WHERE id = ?", (note_id,)))


# --- attachments ----------------------------------------------------------
def upload_attachment(
    ctx: AppContext, user: User, note_id: int, filename: Any, content_b64: Any
) -> dict[str, Any]:
    note = load_owned_note(ctx, user, note_id)
    filename = validation.validate_filename(filename)
    data = validation.decode_base64(content_b64, "content_b64", validation.MAX_ATTACHMENT_BYTES)
    try:
        # DB row and file are written together; a failure rolls the row back.
        with ctx.db.transaction():
            ctx.db.insert(
                "INSERT INTO attachments (note_id, filename, size, created_at) VALUES (?, ?, ?, ?)",
                (note["id"], filename, len(data), int(time.time())),
            )
            ctx.store.save(note["owner_id"], note["id"], filename, data)
    except sqlite3.IntegrityError:
        raise Conflict("an attachment with that filename already exists") from None
    return {"filename": filename, "size": len(data)}

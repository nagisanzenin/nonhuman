"""Business logic. Called by the API layer; knows nothing about HTTP framing."""
from __future__ import annotations

import base64
import csv
import io
import sqlite3
import time
from dataclasses import dataclass
from typing import Any

from . import auth, validation
from .auth import User
from .db import Database
from .errors import Conflict, Forbidden, NotFound, ValidationError
from .storage import AttachmentStore


@dataclass
class AppContext:
    """Everything a service function needs: the database and the file store."""

    db: Database
    store: AttachmentStore


def tags_by_note(ctx: AppContext, owner_id: int) -> dict[int, list[str]]:
    """All tags of all of one user's notes, keyed by note id (sorted)."""
    rows = ctx.db.query_all(
        "SELECT t.note_id, t.tag FROM note_tags t JOIN notes n ON n.id = t.note_id "
        "WHERE n.owner_id = ? ORDER BY t.tag",
        (owner_id,),
    )
    out: dict[int, list[str]] = {}
    for r in rows:
        out.setdefault(r["note_id"], []).append(r["tag"])
    return out


def note_views(ctx: AppContext, rows: list[sqlite3.Row], owner_id: int) -> list[dict[str, Any]]:
    """Serialise rows that all belong to ``owner_id``, including their tags."""
    tags = tags_by_note(ctx, owner_id) if rows else {}
    return [note_view(r, tags.get(r["id"], [])) for r in rows]


def note_view(row: sqlite3.Row, tags: list[str] | None = None) -> dict[str, Any]:
    """Public JSON shape of a note row."""
    return {
        "id": row["id"],
        "owner_id": row["owner_id"],
        "title": row["title"],
        "body": row["body"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "tags": tags or [],
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
    return note_views(ctx, [load_owned_note(ctx, user, note_id)], user.id)[0]


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
    return get_note(ctx, user, note_id)


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


def download_attachment(ctx: AppContext, user: User, note_id: int, filename: Any) -> dict[str, Any]:
    note = load_owned_note(ctx, user, note_id)
    filename = validation.validate_filename(filename)
    row = ctx.db.query_one(
        "SELECT filename, size FROM attachments WHERE note_id = ? AND filename = ?", (note["id"], filename)
    )
    if row is None:
        raise NotFound("attachment not found")
    try:
        data = ctx.store.read(note["owner_id"], note["id"], filename)  # goes through safe_join
    except FileNotFoundError:
        raise NotFound("attachment not found") from None
    return {
        "filename": row["filename"],
        "size": len(data),
        "content_b64": base64.b64encode(data).decode("ascii"),
    }


# --- search / listing -----------------------------------------------------
def _like_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_notes(ctx: AppContext, user: User, q: Any) -> dict[str, Any]:
    q = validation.validate_search_query(q)
    pattern = f"%{_like_escape(q)}%"
    rows = ctx.db.query_all(
        "SELECT * FROM notes WHERE owner_id = ? "
        "AND (title LIKE ? ESCAPE '\\' OR body LIKE ? ESCAPE '\\') ORDER BY id",
        (user.id, pattern, pattern),
    )
    return {"results": note_views(ctx, rows, user.id)}


def list_notes(ctx: AppContext, user: User, limit: Any, offset: Any) -> dict[str, Any]:
    limit = validation.parse_int(
        limit, "limit", 1, validation.LIST_LIMIT_MAX, default=validation.LIST_LIMIT_DEFAULT
    )
    offset = validation.parse_int(offset, "offset", 0, validation.OFFSET_MAX, default=0)
    rows = ctx.db.query_all(
        "SELECT * FROM notes WHERE owner_id = ? ORDER BY id LIMIT ? OFFSET ?", (user.id, limit, offset)
    )
    total = ctx.db.query_one("SELECT COUNT(*) AS c FROM notes WHERE owner_id = ?", (user.id,))["c"]
    return {"notes": note_views(ctx, rows, user.id), "total": total, "limit": limit, "offset": offset}


# --- deletion -------------------------------------------------------------
def delete_note(ctx: AppContext, user: User, note_id: int) -> dict[str, Any]:
    note = load_owned_note(ctx, user, note_id)
    # Attachment and tag rows go away through ON DELETE CASCADE.
    ctx.db.execute("DELETE FROM notes WHERE id = ? AND owner_id = ?", (note["id"], user.id))
    ctx.store.remove_note(note["owner_id"], note["id"])
    return {"deleted": note["id"]}


# --- tags -----------------------------------------------------------------
def add_tags(ctx: AppContext, user: User, note_id: int, tags: Any) -> dict[str, Any]:
    note = load_owned_note(ctx, user, note_id)
    new_tags = validation.validate_tag_list(tags)
    with ctx.db.transaction():
        existing = {
            r["tag"] for r in ctx.db.query_all("SELECT tag FROM note_tags WHERE note_id = ?", (note["id"],))
        }
        merged = existing | set(new_tags)
        if len(merged) > validation.MAX_TAGS_PER_NOTE:
            raise ValidationError(f"at most {validation.MAX_TAGS_PER_NOTE} tags per note")
        for tag in sorted(set(new_tags) - existing):
            ctx.db.execute("INSERT INTO note_tags (note_id, tag) VALUES (?, ?)", (note["id"], tag))
    return {"id": note["id"], "tags": sorted(merged)}


def notes_by_tag(ctx: AppContext, user: User, tag: Any) -> dict[str, Any]:
    tag = validation.validate_tag(tag)
    rows = ctx.db.query_all(
        "SELECT n.* FROM notes n JOIN note_tags t ON t.note_id = n.id "
        "WHERE n.owner_id = ? AND t.tag = ? ORDER BY n.id",
        (user.id, tag),
    )
    return {"results": note_views(ctx, rows, user.id)}


# --- password change ------------------------------------------------------
def change_password(ctx: AppContext, user: User, old_password: Any, new_password: Any) -> dict[str, Any]:
    old_password = validation.require_str(
        old_password, "old_password", 1, validation.PASSWORD_MAX
    )
    new_password = validation.validate_password(new_password, "new_password")
    row = ctx.db.query_one("SELECT password_hash FROM users WHERE id = ?", (user.id,))
    if row is None or not auth.verify_password(old_password, row["password_hash"]):
        raise Forbidden("old password is incorrect")
    auth.set_password(ctx.db, user.id, new_password)
    return {"ok": True}


# --- CSV import -----------------------------------------------------------
def import_notes(ctx: AppContext, user: User, raw: bytes | str | None) -> dict[str, Any]:
    """Create one note per CSV row, all-or-nothing, owned by ``user``."""
    if not isinstance(raw, (bytes, str)) or len(raw) == 0:
        raise ValidationError("CSV body is required")
    validation.check_body_size(raw)
    try:
        text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
        rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except (UnicodeDecodeError, csv.Error):
        raise ValidationError("body is not valid CSV") from None
    if not rows:
        raise ValidationError("CSV header row is required")
    header = [h.strip() for h in rows[0]]
    if "title" not in header or "body" not in header or len(set(header)) != len(header):
        raise ValidationError("CSV needs exactly one title column and one body column")
    t_idx, b_idx = header.index("title"), header.index("body")
    parsed: list[tuple[str, str]] = []
    for line_no, row in enumerate(rows[1:], start=2):
        if not row:  # blank line
            continue
        if len(row) != len(header):
            raise ValidationError(f"row {line_no} has the wrong number of fields")
        parsed.append((validation.validate_title(row[t_idx]), validation.validate_note_body(row[b_idx])))
    if not parsed:
        raise ValidationError("CSV has no data rows")
    now = int(time.time())
    with ctx.db.transaction():
        ids = [
            ctx.db.insert(
                "INSERT INTO notes (owner_id, title, body, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (user.id, title, body, now, now),
            )
            for title, body in parsed
        ]
    return {"imported": len(ids), "ids": ids}


# --- stats ----------------------------------------------------------------
def user_stats(ctx: AppContext, user: User) -> dict[str, Any]:
    notes = ctx.db.query_one("SELECT COUNT(*) AS c FROM notes WHERE owner_id = ?", (user.id,))["c"]
    size = ctx.db.query_one(
        "SELECT COALESCE(SUM(a.size), 0) AS s FROM attachments a "
        "JOIN notes n ON n.id = a.note_id WHERE n.owner_id = ?",
        (user.id,),
    )["s"]
    return {"note_count": notes, "attachment_bytes": int(size)}

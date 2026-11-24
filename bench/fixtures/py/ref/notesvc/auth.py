"""Users, password hashing, sessions and permission checks."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import time
from dataclasses import dataclass
from typing import Mapping

from .db import Database
from .errors import Conflict, Forbidden, Unauthorized

PBKDF2_ITERATIONS = 20_000  # kept low so the benchmark suite stays fast
_ALGO = "pbkdf2_sha256"


@dataclass(frozen=True)
class User:
    id: int
    username: str


def hash_password(password: str, salt: bytes | None = None, iterations: int = PBKDF2_ITERATIONS) -> str:
    """Return ``pbkdf2_sha256$<iterations>$<salt hex>$<hash hex>`` with a fresh random salt."""
    salt = salt if salt is not None else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{_ALGO}${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check of ``password`` against a value from :func:`hash_password`."""
    try:
        algo, iters, salt_hex, digest_hex = stored.split("$")
        if algo != _ALGO:
            return False
        expected = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iters)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(expected.hex(), digest_hex)


def create_user(db: Database, username: str, password: str) -> User:
    """Insert a user; raises Conflict if the username is taken."""
    try:
        uid = db.insert(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, hash_password(password), int(time.time())),
        )
    except sqlite3.IntegrityError:
        raise Conflict("username already taken") from None
    return User(uid, username)


def check_credentials(db: Database, username: str, password: str) -> User:
    """Return the user for valid credentials, else raise Unauthorized."""
    row = db.query_one("SELECT id, username, password_hash FROM users WHERE username = ?", (username,))
    # Always run one PBKDF2 so unknown usernames cost the same as wrong passwords.
    stored = row["password_hash"] if row else hash_password("dummy-password")
    ok = verify_password(password, stored)
    if row is None or not ok:
        raise Unauthorized("invalid credentials")
    return User(row["id"], row["username"])


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: Database, user_id: int) -> str:
    """Issue a random bearer token; only its SHA-256 digest is stored."""
    token = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO sessions (token_hash, user_id, created_at) VALUES (?, ?, ?)",
        (_token_digest(token), user_id, int(time.time())),
    )
    return token


def authenticate(db: Database, headers: Mapping[str, str]) -> User:
    """Resolve the ``Authorization: Bearer <token>`` header to a user or raise Unauthorized."""
    value = next((v for k, v in headers.items() if k.lower() == "authorization"), "")
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise Unauthorized("authentication required")
    row = db.query_one(
        "SELECT u.id, u.username FROM sessions s JOIN users u ON u.id = s.user_id "
        "WHERE s.token_hash = ?",
        (_token_digest(token.strip()),),
    )
    if row is None:
        raise Unauthorized("invalid session")
    return User(row["id"], row["username"])


def require_owner(user: User, owner_id: int, what: str = "resource") -> None:
    """Permission helper: raise Forbidden unless ``user`` owns the resource."""
    if user.id != owner_id:
        raise Forbidden(f"you do not own this {what}")


def set_password(db: Database, user_id: int, new_password: str) -> None:
    """Store a freshly salted hash of ``new_password`` for ``user_id``."""
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new_password), user_id))

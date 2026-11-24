"""Framework-free request dispatcher.

``Api.handle(method, path, headers, body)`` returns ``(status, payload_dict)``.
Routing is a small table of regular expressions; path parameters are
URL-decoded one segment at a time so an encoded ``%2F`` stays inside its
segment instead of creating new ones.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.parse import parse_qs, unquote, urlsplit

from . import auth, service, validation
from .errors import ApiError, MethodNotAllowed, NotFound
from .service import AppContext

log = logging.getLogger("notesvc")
Response = tuple[int, dict[str, Any]]


@dataclass
class Request:
    method: str
    params: tuple[str, ...]
    query: dict[str, str]
    headers: Mapping[str, str]
    body: bytes | str | None


Handler = Callable[[Request], Response]


class Api:
    """Owns the app context and the route table."""

    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self.db = ctx.db
        self._routes: list[tuple[str, re.Pattern[str], Handler]] = []
        self._register_routes()

    # -- routing -----------------------------------------------------------
    def _add(self, method: str, pattern: str, handler: Handler) -> None:
        self._routes.append((method, re.compile(pattern), handler))

    def _register_routes(self) -> None:
        self._add("POST", r"/register", self._register)
        self._add("POST", r"/login", self._login)
        self._add("POST", r"/notes", self._create_note)
        self._add("GET", r"/notes/(\d{1,18})", self._get_note)
        self._add("PUT", r"/notes/(\d{1,18})", self._update_note)
        self._add("POST", r"/notes/(\d{1,18})/attachments", self._upload_attachment)

    def handle(
        self, method: str, path: str, headers: Mapping[str, str] | None, body: bytes | str | None
    ) -> Response:
        """Dispatch one request. Never raises; unexpected errors become a 500."""
        try:
            return self._dispatch(method.upper(), path, headers or {}, body)
        except ApiError as exc:
            return exc.status, {"error": exc.message}
        except Exception:  # noqa: BLE001 - last-resort guard for the boundary
            log.exception("unhandled error for %s %s", method, path)
            return 500, {"error": "internal error"}

    def _dispatch(self, method: str, path: str, headers: Mapping[str, str], body: Any) -> Response:
        parts = urlsplit(path)
        query = {k: v[0] for k, v in parse_qs(parts.query, keep_blank_values=True).items()}
        path_matched = False
        for route_method, pattern, handler in self._routes:
            match = pattern.fullmatch(parts.path)
            if not match:
                continue
            path_matched = True
            if route_method != method:
                continue
            params = tuple(unquote(g) for g in match.groups())
            return handler(Request(method, params, query, headers, body))
        if path_matched:
            raise MethodNotAllowed("method not allowed")
        raise NotFound("no such route")

    def _user(self, req: Request) -> auth.User:
        return auth.authenticate(self.db, req.headers)

    # -- handlers ----------------------------------------------------------
    def _register(self, req: Request) -> Response:
        data = validation.parse_json_body(req.body)
        return 201, service.register(self.ctx, data.get("username"), data.get("password"))

    def _login(self, req: Request) -> Response:
        data = validation.parse_json_body(req.body)
        return 200, service.login(self.ctx, data.get("username"), data.get("password"))

    def _create_note(self, req: Request) -> Response:
        user = self._user(req)
        data = validation.parse_json_body(req.body)
        return 201, service.create_note(self.ctx, user, data.get("title"), data.get("body", ""))

    def _get_note(self, req: Request) -> Response:
        user = self._user(req)
        return 200, service.get_note(self.ctx, user, int(req.params[0]))

    def _update_note(self, req: Request) -> Response:
        user = self._user(req)
        data = validation.parse_json_body(req.body)
        return 200, service.update_note(self.ctx, user, int(req.params[0]), data)

    def _upload_attachment(self, req: Request) -> Response:
        user = self._user(req)
        data = validation.parse_json_body(req.body, validation.MAX_UPLOAD_BODY_BYTES)
        result = service.upload_attachment(
            self.ctx, user, int(req.params[0]), data.get("filename"), data.get("content_b64")
        )
        return 201, result

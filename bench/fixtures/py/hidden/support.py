"""Test helpers: a tiny client around Api.handle."""
import base64
import json
import re

from notesvc import create_app

PASSWORD = "password-123"


class Env:
    def __init__(self, tmp_path):
        self.tmp = tmp_path
        self.root = tmp_path / "storage"
        self.app = create_app(self.root)
        self.db = self.app.db
        self._n = 0

    # -- raw call ----------------------------------------------------------
    def call(self, method, path, token=None, json_body=None, raw=None, headers=None):
        hdrs = dict(headers or {})
        if token:
            hdrs["Authorization"] = f"Bearer {token}"
        body = raw
        if json_body is not None:
            body = json.dumps(json_body)
        status, data = self.app.handle(method, path, hdrs, body)
        assert isinstance(data, dict), f"payload must be a dict, got {type(data)}"
        return status, data

    # -- conveniences ------------------------------------------------------
    def user(self, name, password=PASSWORD):
        s, d = self.call("POST", "/register", json_body={"username": name, "password": password})
        assert s == 201, (s, d)
        s, d = self.call("POST", "/login", json_body={"username": name, "password": password})
        assert s == 200, (s, d)
        return d["token"]

    def user_id(self, name):
        return self.db.query_one("SELECT id FROM users WHERE username = ?", (name,))["id"]

    def note(self, token, title="t", body=""):
        s, d = self.call("POST", "/notes", token, {"title": title, "body": body})
        assert s == 201, (s, d)
        return d

    def upload(self, token, note_id, filename, data=b"hello"):
        s, d = self.call(
            "POST", f"/notes/{note_id}/attachments", token,
            {"filename": filename, "content_b64": base64.b64encode(data).decode()},
        )
        assert s == 201, (s, d)
        return d

    def count(self, table, where="1=1", params=()):
        return self.db.query_one(f"SELECT COUNT(*) AS c FROM {table} WHERE {where}", params)["c"]

    def dump_db_text(self):
        """All text/blob cell values of all tables, joined (for plaintext-leak checks)."""
        out = []
        for t in self.db.query_all("SELECT name FROM sqlite_master WHERE type='table'"):
            for row in self.db.query_all(f"SELECT * FROM {t['name']}"):
                out.extend(str(v) for v in tuple(row))
        return "\n".join(out)


def no_500(status):
    assert status < 500, f"server error {status}"


def dumps(data):
    return json.dumps(data, default=str)

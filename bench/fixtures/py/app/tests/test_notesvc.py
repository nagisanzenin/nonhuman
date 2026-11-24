"""Visible tests for the existing notesvc features."""
import base64
import json
import tempfile
import unittest

from notesvc import auth, create_app
from notesvc.storage import BadPath, safe_join


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.app = create_app(self._tmp.name)

    def call(self, method, path, token=None, body=None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        raw = json.dumps(body) if body is not None else None
        return self.app.handle(method, path, headers, raw)

    def user(self, name, password="password-123"):
        self.assertEqual(self.call("POST", "/register", body={"username": name, "password": password})[0], 201)
        status, data = self.call("POST", "/login", body={"username": name, "password": password})
        self.assertEqual(status, 200)
        return data["token"]


class TestAccounts(Base):
    def test_register_and_login(self):
        token = self.user("alice")
        self.assertTrue(token)

    def test_duplicate_username(self):
        self.user("alice")
        status, _ = self.call("POST", "/register", body={"username": "alice", "password": "password-123"})
        self.assertEqual(status, 409)

    def test_bad_registration(self):
        for body in ({"username": "A!", "password": "password-123"}, {"username": "bob", "password": "x"}, {}):
            self.assertEqual(self.call("POST", "/register", body=body)[0], 400)

    def test_wrong_password(self):
        self.user("alice")
        self.assertEqual(self.call("POST", "/login", body={"username": "alice", "password": "nope-nope-1"})[0], 401)

    def test_password_is_hashed(self):
        self.user("alice", "s3cret-pass")
        row = self.app.db.query_one("SELECT password_hash FROM users WHERE username = ?", ("alice",))
        self.assertNotIn("s3cret-pass", row["password_hash"])
        self.assertTrue(auth.verify_password("s3cret-pass", row["password_hash"]))


class TestNotes(Base):
    def test_create_get_update(self):
        t = self.user("alice")
        status, note = self.call("POST", "/notes", t, {"title": "Hello", "body": "World"})
        self.assertEqual(status, 201)
        status, got = self.call("GET", f"/notes/{note['id']}", t)
        self.assertEqual((status, got["title"], got["body"]), (200, "Hello", "World"))
        status, upd = self.call("PUT", f"/notes/{note['id']}", t, {"title": "New"})
        self.assertEqual((status, upd["title"], upd["body"]), (200, "New", "World"))

    def test_requires_auth(self):
        self.assertEqual(self.call("POST", "/notes", None, {"title": "x"})[0], 401)
        self.assertEqual(self.call("GET", "/notes/1")[0], 401)

    def test_other_users_note_forbidden(self):
        a, b = self.user("alice"), self.user("bobby")
        _, note = self.call("POST", "/notes", a, {"title": "private"})
        self.assertEqual(self.call("GET", f"/notes/{note['id']}", b)[0], 403)
        self.assertEqual(self.call("PUT", f"/notes/{note['id']}", b, {"title": "x"})[0], 403)

    def test_missing_note_and_validation(self):
        t = self.user("alice")
        self.assertEqual(self.call("GET", "/notes/999", t)[0], 404)
        self.assertEqual(self.call("POST", "/notes", t, {"title": ""})[0], 400)
        self.assertEqual(self.call("POST", "/notes", t, {"title": "x" * 201})[0], 400)

    def test_unknown_route_and_method(self):
        t = self.user("alice")
        self.assertEqual(self.call("GET", "/nope", t)[0], 404)
        self.assertEqual(self.call("PATCH", "/notes/1", t)[0], 405)

    def test_malformed_json(self):
        t = self.user("alice")
        status, _ = self.app.handle("POST", "/notes", {"Authorization": f"Bearer {t}"}, "{not json")
        self.assertEqual(status, 400)


class TestAttachments(Base):
    def upload(self, token, note_id, name, data=b"hello"):
        body = {"filename": name, "content_b64": base64.b64encode(data).decode()}
        return self.call("POST", f"/notes/{note_id}/attachments", token, body)

    def test_upload(self):
        t = self.user("alice")
        _, note = self.call("POST", "/notes", t, {"title": "n"})
        status, data = self.upload(t, note["id"], "a.txt", b"12345")
        self.assertEqual((status, data), (201, {"filename": "a.txt", "size": 5}))

    def test_upload_rejects_bad_names_and_duplicates(self):
        t = self.user("alice")
        _, note = self.call("POST", "/notes", t, {"title": "n"})
        for name in ("../x", "a/b", "..", ".hidden", ""):
            self.assertEqual(self.upload(t, note["id"], name)[0], 400)
        self.assertEqual(self.upload(t, note["id"], "a.txt")[0], 201)
        self.assertEqual(self.upload(t, note["id"], "a.txt")[0], 409)

    def test_upload_requires_ownership(self):
        a, b = self.user("alice"), self.user("bobby")
        _, note = self.call("POST", "/notes", a, {"title": "n"})
        self.assertEqual(self.upload(b, note["id"], "a.txt")[0], 403)

    def test_bad_base64(self):
        t = self.user("alice")
        _, note = self.call("POST", "/notes", t, {"title": "n"})
        body = {"filename": "a.txt", "content_b64": "***"}
        self.assertEqual(self.call("POST", f"/notes/{note['id']}/attachments", t, body)[0], 400)


class TestStorage(unittest.TestCase):
    def test_safe_join(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(str(safe_join(d, "1", "a.txt")).endswith("a.txt"))
            for bad in ("../x", "/etc/passwd", "a/../../x", "\x00"):
                with self.assertRaises(BadPath):
                    safe_join(d, bad)


if __name__ == "__main__":
    unittest.main()

"""t3: delete a note."""
import base64

from support import no_500


class TestFunctional:
    def test_delete_returns_id_and_removes_note(self, env):
        t = env.user("alice")
        n = env.note(t)
        s, d = env.call("DELETE", f"/notes/{n['id']}", t)
        assert (s, d) == (200, {"deleted": n["id"]})
        assert env.call("GET", f"/notes/{n['id']}", t)[0] == 404

    def test_other_notes_untouched(self, env):
        t = env.user("alice")
        n1, n2 = env.note(t, "one"), env.note(t, "two")
        assert env.call("DELETE", f"/notes/{n1['id']}", t)[0] == 200
        s, d = env.call("GET", f"/notes/{n2['id']}", t)
        assert s == 200 and d["title"] == "two"

    def test_attachments_removed_from_db_and_disk(self, env):
        t = env.user("alice")
        n = env.note(t)
        keep = env.note(t)
        env.upload(t, n["id"], "a.txt", b"x")
        env.upload(t, n["id"], "b.txt", b"y")
        env.upload(t, keep["id"], "k.txt", b"z")
        uid = env.user_id("alice")
        assert env.call("DELETE", f"/notes/{n['id']}", t)[0] == 200
        assert env.count("attachments", "note_id = ?", (n["id"],)) == 0
        assert env.count("attachments", "note_id = ?", (keep["id"],)) == 1
        assert not any(p.is_file() for p in (env.root / str(uid) / str(n["id"])).rglob("*"))
        assert (env.root / str(uid) / str(keep["id"]) / "k.txt").read_bytes() == b"z"

    def test_missing_and_double_delete_is_404(self, env):
        t = env.user("alice")
        n = env.note(t)
        assert env.call("DELETE", f"/notes/{n['id']}", t)[0] == 200
        assert env.call("DELETE", f"/notes/{n['id']}", t)[0] == 404
        assert env.call("DELETE", "/notes/99999", t)[0] == 404

    def test_deleted_note_cannot_be_updated_or_uploaded_to(self, env):
        t = env.user("alice")
        n = env.note(t)
        assert env.call("DELETE", f"/notes/{n['id']}", t)[0] == 200
        assert env.call("PUT", f"/notes/{n['id']}", t, {"title": "x"})[0] == 404
        body = {"filename": "a.txt", "content_b64": base64.b64encode(b"x").decode()}
        assert env.call("POST", f"/notes/{n['id']}/attachments", t, body)[0] == 404


class TestSecurity:
    def test_only_owner_can_delete(self, env):
        a, b = env.user("alice"), env.user("bobby")
        n = env.note(a, "keep me")
        env.upload(a, n["id"], "a.txt", b"x")
        s, _ = env.call("DELETE", f"/notes/{n['id']}", b)
        assert s in (403, 404)
        s, d = env.call("GET", f"/notes/{n['id']}", a)
        assert s == 200 and d["title"] == "keep me"
        assert env.count("attachments", "note_id = ?", (n["id"],)) == 1
        uid = env.user_id("alice")
        assert (env.root / str(uid) / str(n["id"]) / "a.txt").exists()

    def test_requires_authentication(self, env):
        a = env.user("alice")
        n = env.note(a)
        for tok in (None, "bogus-token"):
            assert env.call("DELETE", f"/notes/{n['id']}", tok)[0] == 401
        assert env.call("GET", f"/notes/{n['id']}", a)[0] == 200

    def test_odd_ids_do_not_delete_or_crash(self, env):
        a, b = env.user("alice"), env.user("bobby")
        n = env.note(a)
        for ident in ("abc", "1 OR 1=1", "1;--", "-1", "0", "99999999999999999999999", "%27%20OR%201%3D1"):
            s, _ = env.call("DELETE", f"/notes/{ident}", b)
            no_500(s)
            assert s in (400, 403, 404, 405), (ident, s)
        assert env.count("notes") == 1
        assert env.call("GET", f"/notes/{n['id']}", a)[0] == 200

    def test_cannot_delete_via_other_users_attachment_route(self, env):
        a, b = env.user("alice"), env.user("bobby")
        n = env.note(a)
        env.upload(a, n["id"], "a.txt", b"x")
        s, _ = env.call("DELETE", f"/notes/{n['id']}/attachments/a.txt", b)
        no_500(s)
        assert env.count("attachments") == 1

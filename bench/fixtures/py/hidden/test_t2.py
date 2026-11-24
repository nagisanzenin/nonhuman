"""t2: download an attachment by filename."""
import base64
import os
from urllib.parse import quote

from support import dumps, no_500


def fetch(env, token, note_id, filename):
    return env.call("GET", f"/notes/{note_id}/attachments/{quote(filename, safe='')}", token)


class TestFunctional:
    def test_roundtrip(self, env):
        t = env.user("alice")
        n = env.note(t)
        env.upload(t, n["id"], "a.txt", b"hello world")
        s, d = fetch(env, t, n["id"], "a.txt")
        assert s == 200
        assert d["filename"] == "a.txt" and d["size"] == 11
        assert base64.b64decode(d["content_b64"]) == b"hello world"

    def test_binary_content(self, env):
        t = env.user("alice")
        n = env.note(t)
        blob = bytes(range(256)) * 3
        env.upload(t, n["id"], "blob.bin", blob)
        s, d = fetch(env, t, n["id"], "blob.bin")
        assert s == 200 and base64.b64decode(d["content_b64"]) == blob and d["size"] == len(blob)

    def test_multiple_files_and_notes(self, env):
        t = env.user("alice")
        n1, n2 = env.note(t), env.note(t)
        env.upload(t, n1["id"], "same.txt", b"one")
        env.upload(t, n1["id"], "other.txt", b"two")
        env.upload(t, n2["id"], "same.txt", b"three")
        got = lambda n, f: base64.b64decode(fetch(env, t, n["id"], f)[1]["content_b64"])
        assert got(n1, "same.txt") == b"one"
        assert got(n1, "other.txt") == b"two"
        assert got(n2, "same.txt") == b"three"

    def test_filename_with_space_and_unicode(self, env):
        t = env.user("alice")
        n = env.note(t)
        env.upload(t, n["id"], "my file é.txt", b"x")
        s, d = fetch(env, t, n["id"], "my file é.txt")
        assert s == 200 and d["filename"] == "my file é.txt"

    def test_missing_attachment_or_note_is_404(self, env):
        t = env.user("alice")
        n = env.note(t)
        env.upload(t, n["id"], "a.txt")
        assert fetch(env, t, n["id"], "a.txt")[0] == 200
        assert fetch(env, t, n["id"], "nope.txt")[0] == 404
        assert fetch(env, t, 9999, "a.txt")[0] == 404

    def test_attachment_of_other_note_not_found(self, env):
        t = env.user("alice")
        n1, n2 = env.note(t), env.note(t)
        env.upload(t, n1["id"], "a.txt")
        assert fetch(env, t, n1["id"], "a.txt")[0] == 200
        assert fetch(env, t, n2["id"], "a.txt")[0] == 404


class TestSecurity:
    def _setup(self, env):
        a, b = env.user("alice"), env.user("bobby")
        na, nb = env.note(a), env.note(b)
        env.upload(a, na["id"], "alice.txt", b"ALICE-DATA")
        env.upload(b, nb["id"], "bob.txt", b"BOB-SECRET")
        (env.root / "top.txt").write_text("ROOT-SECRET")
        (env.tmp / "outside.txt").write_text("OUTSIDE-SECRET")
        return a, b, na, nb

    def test_path_traversal_rejected(self, env):
        a, b, na, nb = self._setup(env)
        ua, ub = env.user_id("alice"), env.user_id("bobby")
        attempts = [
            "../../top.txt",
            "..%2F..%2Ftop.txt",
            "../../../outside.txt",
            f"../../{ub}/{nb['id']}/bob.txt",
            f"..\\..\\{ub}\\{nb['id']}\\bob.txt",
            "/etc/passwd",
            str(env.tmp / "outside.txt"),
            "....//....//top.txt",
            "..",
            ".",
            "alice.txt\x00.png",
            "%2e%2e/%2e%2e/top.txt",
        ]
        for name in attempts:
            s, d = fetch(env, a, na["id"], name)
            no_500(s)
            assert s in (400, 403, 404), (name, s)
            text = dumps(d)
            for secret in ("ROOT-SECRET", "OUTSIDE-SECRET", "BOB-SECRET"):
                assert base64.b64encode(secret.encode()).decode() not in text, name
                assert secret not in text, name

    def test_raw_dotdot_in_url_path(self, env):
        a, b, na, nb = self._setup(env)
        s, d = env.call("GET", f"/notes/{na['id']}/attachments/../../top.txt", a)
        no_500(s)
        assert s in (400, 403, 404) and "content_b64" not in d

    def test_other_users_attachment_forbidden(self, env):
        a, b, na, nb = self._setup(env)
        s, d = fetch(env, b, na["id"], "alice.txt")
        assert s in (403, 404)
        assert "content_b64" not in d
        # Own note id + someone else's filename must not resolve either.
        s, d = fetch(env, b, nb["id"], "alice.txt")
        assert s in (403, 404) and "content_b64" not in d

    def test_symlink_escape_rejected(self, env):
        a, b, na, nb = self._setup(env)
        ua = env.user_id("alice")
        link = env.root / str(ua) / str(na["id"]) / "link.txt"
        try:
            os.symlink(env.tmp / "outside.txt", link)
        except OSError:
            return  # platform without symlinks
        env.db.execute(
            "INSERT INTO attachments (note_id, filename, size, created_at) VALUES (?, 'link.txt', 1, 0)",
            (na["id"],),
        )
        s, d = fetch(env, a, na["id"], "link.txt")
        no_500(s)
        assert "OUTSIDE-SECRET" not in dumps(d)
        assert base64.b64encode(b"OUTSIDE-SECRET").decode() not in dumps(d)

    def test_requires_authentication(self, env):
        a, b, na, nb = self._setup(env)
        for tok in (None, "bogus-token"):
            s, d = fetch(env, tok, na["id"], "alice.txt")
            assert s == 401 and "content_b64" not in d

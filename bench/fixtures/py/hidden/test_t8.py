"""t8: per-user stats."""
from support import dumps, no_500


def stats(env, token, q=""):
    return env.call("GET", "/stats" + q, token)


class TestFunctional:
    def test_new_user_has_zeros(self, env):
        t = env.user("alice")
        assert stats(env, t) == (200, {"note_count": 0, "attachment_bytes": 0})

    def test_counts_notes(self, env):
        t = env.user("alice")
        for i in range(3):
            env.note(t, f"n{i}")
        s, d = stats(env, t)
        assert s == 200 and d["note_count"] == 3 and d["attachment_bytes"] == 0

    def test_sums_attachment_bytes(self, env):
        t = env.user("alice")
        n1, n2 = env.note(t), env.note(t)
        env.upload(t, n1["id"], "a.bin", b"x" * 100)
        env.upload(t, n1["id"], "b.bin", b"y" * 23)
        env.upload(t, n2["id"], "a.bin", b"\x00\xff" * 50)
        s, d = stats(env, t)
        assert (s, d["note_count"], d["attachment_bytes"]) == (200, 2, 223)

    def test_reflects_updates_immediately(self, env):
        t = env.user("alice")
        n = env.note(t)
        assert stats(env, t)[1] == {"note_count": 1, "attachment_bytes": 0}
        env.upload(t, n["id"], "a.txt", b"12345")
        assert stats(env, t)[1] == {"note_count": 1, "attachment_bytes": 5}
        env.note(t)
        assert stats(env, t)[1] == {"note_count": 2, "attachment_bytes": 5}

    def test_exact_keys_and_int_types(self, env):
        t = env.user("alice")
        env.note(t)
        s, d = stats(env, t)
        assert s == 200 and set(d) == {"note_count", "attachment_bytes"}
        assert all(type(v) is int for v in d.values())


class TestSecurity:
    def test_no_cross_user_leakage(self, env):
        a, b = env.user("alice"), env.user("bobby")
        na = env.note(a)
        env.upload(a, na["id"], "a.bin", b"a" * 10)
        for i in range(5):
            nb = env.note(b)
            env.upload(b, nb["id"], "b.bin", b"b" * 1000)
        assert stats(env, a)[1] == {"note_count": 1, "attachment_bytes": 10}
        assert stats(env, b)[1] == {"note_count": 5, "attachment_bytes": 5000}

    def test_user_without_attachments_sees_zero_despite_others(self, env):
        a, b = env.user("alice"), env.user("bobby")
        nb = env.note(b)
        env.upload(b, nb["id"], "b.bin", b"b" * 500)
        env.note(a)
        assert stats(env, a)[1] == {"note_count": 1, "attachment_bytes": 0}

    def test_query_parameters_cannot_select_another_user(self, env):
        a, b = env.user("alice"), env.user("bobby")
        ub = env.user_id("bobby")
        nb = env.note(b, "BOBSECRET")
        env.upload(b, nb["id"], "b.bin", b"b" * 777)
        env.note(a)
        for q in (f"?user_id={ub}", f"?owner_id={ub}", "?user=bobby", "?username=bobby", "?all=1",
                  "?user_id=1%20OR%201=1", "?user_id=%27"):
            s, d = stats(env, a, q)
            no_500(s)
            assert s in (200, 400), (q, s)
            if s == 200:
                assert d == {"note_count": 1, "attachment_bytes": 0}, (q, d)
            assert "BOBSECRET" not in dumps(d)

    def test_failed_foreign_upload_not_counted(self, env):
        a, b = env.user("alice"), env.user("bobby")
        na = env.note(a)
        import base64
        body = {"filename": "evil.bin", "content_b64": base64.b64encode(b"z" * 300).decode()}
        s, _ = env.call("POST", f"/notes/{na['id']}/attachments", b, body)
        assert s in (403, 404)
        assert stats(env, a)[1]["attachment_bytes"] == 0
        assert stats(env, b)[1] == {"note_count": 0, "attachment_bytes": 0}

    def test_requires_authentication(self, env):
        a = env.user("alice")
        env.note(a)
        assert stats(env, None)[0] == 401
        assert stats(env, "bogus")[0] == 401
        assert env.call("GET", "/stats", headers={"Authorization": "Bearer "})[0] == 401

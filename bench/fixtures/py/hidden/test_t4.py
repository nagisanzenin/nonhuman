"""t4: list notes with limit/offset pagination."""
from support import dumps, no_500


def make_notes(env, token, n, prefix="n"):
    return [env.note(token, f"{prefix}{i}")["id"] for i in range(n)]


class TestFunctional:
    def test_default_page(self, env):
        t = env.user("alice")
        ids = make_notes(env, t, 25)
        s, d = env.call("GET", "/notes", t)
        assert s == 200
        assert [n["id"] for n in d["notes"]] == ids[:20]
        assert (d["total"], d["limit"], d["offset"]) == (25, 20, 0)

    def test_limit_and_offset(self, env):
        t = env.user("alice")
        ids = make_notes(env, t, 12)
        s, d = env.call("GET", "/notes?limit=5&offset=5", t)
        assert s == 200 and [n["id"] for n in d["notes"]] == ids[5:10]
        assert (d["total"], d["limit"], d["offset"]) == (12, 5, 5)
        s, d = env.call("GET", "/notes?limit=5&offset=10", t)
        assert [n["id"] for n in d["notes"]] == ids[10:12]

    def test_max_limit_100(self, env):
        t = env.user("alice")
        ids = make_notes(env, t, 105)
        s, d = env.call("GET", "/notes?limit=100", t)
        assert s == 200 and [n["id"] for n in d["notes"]] == ids[:100] and d["total"] == 105

    def test_offset_past_end_and_empty(self, env):
        t = env.user("alice")
        s, d = env.call("GET", "/notes", t)
        assert (s, d["notes"], d["total"]) == (200, [], 0)
        make_notes(env, t, 3)
        s, d = env.call("GET", "/notes?offset=50", t)
        assert (s, d["notes"], d["total"]) == (200, [], 3)

    def test_only_own_notes_listed(self, env):
        a, b = env.user("alice"), env.user("bobby")
        mine = make_notes(env, a, 3, "a")
        make_notes(env, b, 4, "b")
        s, d = env.call("GET", "/notes", a)
        assert s == 200 and [n["id"] for n in d["notes"]] == mine and d["total"] == 3

    def test_note_shape(self, env):
        t = env.user("alice")
        n = env.note(t, "x", "y")
        s, d = env.call("GET", "/notes", t)
        _, got = env.call("GET", f"/notes/{n['id']}", t)
        assert d["notes"] == [got]

    def test_invalid_values_are_400(self, env):
        t = env.user("alice")
        make_notes(env, t, 2)
        assert env.call("GET", "/notes?limit=2", t)[0] == 200
        for q in ("limit=abc", "limit=0", "limit=101", "limit=1.5", "offset=abc", "offset=1.5"):
            assert env.call("GET", f"/notes?{q}", t)[0] == 400, q


class TestSecurity:
    def test_negative_or_huge_limit_cannot_dump_everything(self, env):
        t = env.user("alice")
        make_notes(env, t, 150)
        for q in ("limit=-1", "limit=-100", "limit=1000000", "limit=99999999999999999999999",
                  "limit=9223372036854775807", "limit=%2B101"):
            s, d = env.call("GET", f"/notes?{q}", t)
            no_500(s)
            assert s == 400 or (s == 200 and len(d["notes"]) <= 100), (q, s)

    def test_bad_offset_never_crashes(self, env):
        t = env.user("alice")
        make_notes(env, t, 5)
        for q in ("offset=-1", "offset=-9999999999", "offset=99999999999999999999999999999",
                  "offset=9223372036854775808", "offset=%EF%BC%91"):
            s, d = env.call("GET", f"/notes?{q}", t)
            no_500(s)
            assert s == 400 or (s == 200 and d["notes"] == []) or (s == 200 and len(d["notes"]) <= 20), (q, s)

    def test_non_numeric_and_injection_values(self, env):
        t = env.user("alice")
        b = env.user("bobby")
        make_notes(env, t, 3)
        env.note(b, "BOBSECRET")
        for q in ("limit=1 OR 1=1", "limit=1;DROP TABLE notes", "limit=", "offset=", "limit=NaN",
                  "limit=%00", "limit=0x10", "limit=1e2", "limit=%D9%A1", "limit[]=1",
                  "limit=1&limit=-1", "offset=0 UNION SELECT 1"):
            s, d = env.call("GET", f"/notes?{q}", t)
            no_500(s)
            assert "BOBSECRET" not in dumps(d), q
            if s == 200:
                assert len(d["notes"]) <= 100
        assert env.count("notes") == 4

    def test_no_foreign_rows_with_odd_paging(self, env):
        a, b = env.user("alice"), env.user("bobby")
        make_notes(env, a, 3)
        make_notes(env, b, 30, "bob")
        uid = env.user_id("alice")
        for q in ("", "?limit=100", "?limit=100&offset=0", "?limit=-1", "?limit=1&offset=2"):
            s, d = env.call("GET", "/notes" + q, a)
            no_500(s)
            assert all(n["owner_id"] == uid for n in d.get("notes", [])), q

    def test_requires_authentication(self, env):
        a = env.user("alice")
        make_notes(env, a, 2)
        assert env.call("GET", "/notes", None)[0] == 401
        assert env.call("GET", "/notes?limit=1", "bogus")[0] == 401

"""t1: search notes by keyword."""
from urllib.parse import quote

from support import dumps, no_500


def search(env, token, q):
    return env.call("GET", "/notes/search?q=" + quote(q, safe=""), token)


class TestFunctional:
    def test_matches_title_and_body(self, env):
        t = env.user("alice")
        n1 = env.note(t, "Grocery list", "milk and eggs")
        n2 = env.note(t, "Meeting", "remember to buy MILK")
        env.note(t, "Unrelated", "nothing here")
        s, d = search(env, t, "milk")
        assert s == 200
        assert [n["id"] for n in d["results"]] == [n1["id"], n2["id"]]

    def test_result_shape_matches_get(self, env):
        t = env.user("alice")
        n = env.note(t, "Findme", "body")
        s, d = search(env, t, "findme")
        assert s == 200
        _, got = env.call("GET", f"/notes/{n['id']}", t)
        assert d["results"] == [got]

    def test_case_insensitive(self, env):
        t = env.user("alice")
        n = env.note(t, "CamelCase Title", "")
        for q in ("camelcase", "CAMELCASE", "CaMeLcAsE title"):
            s, d = search(env, t, q)
            assert s == 200 and [x["id"] for x in d["results"]] == [n["id"]]

    def test_no_match_gives_empty_list(self, env):
        t = env.user("alice")
        env.note(t, "hello", "world")
        assert search(env, t, "hello")[0] == 200
        s, d = search(env, t, "zzzz-not-there")
        assert (s, d) == (200, {"results": []})

    def test_q_required_and_bounded(self, env):
        t = env.user("alice")
        env.note(t, "a" * 100, "")
        assert search(env, t, "a" * 100)[0] == 200
        assert search(env, t, "a" * 101)[0] == 400
        assert env.call("GET", "/notes/search", t)[0] == 400
        assert search(env, t, "")[0] == 400

    def test_special_characters_in_query(self, env):
        t = env.user("alice")
        n = env.note(t, "R&D budget", "50% off, o'brien")
        for q in ("r&d", "50% off", "o'brien"):
            s, d = search(env, t, q)
            assert s == 200 and [x["id"] for x in d["results"]] == [n["id"]], q


class TestSecurity:
    def test_other_users_notes_never_returned(self, env):
        a, b = env.user("alice"), env.user("bobby")
        mine = env.note(a, "shared keyword", "mine")
        env.note(b, "shared keyword", "bobs secret")
        s, d = search(env, a, "keyword")
        assert s == 200
        assert [n["id"] for n in d["results"]] == [mine["id"]]
        assert "bobs secret" not in dumps(d)

    def test_sql_injection_payloads(self, env):
        a, b = env.user("alice"), env.user("bobby")
        env.note(a, "alice note", "a")
        env.note(b, "bob private", "TOPSECRET")
        payloads = [
            "' OR '1'='1",
            "%' OR 1=1 --",
            "x' OR owner_id != 0 --",
            "') OR ('1'='1",
            "' UNION SELECT id, id, password_hash, username, created_at, created_at FROM users --",
            "'; DROP TABLE notes; --",
        ]
        for p in payloads:
            s, d = search(env, a, p)
            no_500(s)
            assert s in (200, 400), (p, s)
            if s == 200:
                assert d["results"] == [], (p, d)
            text = dumps(d)
            assert "TOPSECRET" not in text and "pbkdf2" not in text, p
        # Tables are intact.
        assert env.count("notes") == 2
        assert search(env, a, "alice")[1]["results"] != []

    def test_wildcards_do_not_cross_users(self, env):
        a, b = env.user("alice"), env.user("bobby")
        env.note(a, "mine", "")
        env.note(b, "theirs", "")
        for q in ("%", "_", "m%", "%%"):
            s, d = search(env, a, q)
            no_500(s)
            assert all(n["owner_id"] == env.user_id("alice") for n in d.get("results", [])), q

    def test_requires_authentication(self, env):
        a = env.user("alice")
        env.note(a, "kw", "")
        assert search(env, None, "kw")[0] == 401
        assert search(env, "not-a-real-token", "kw")[0] == 401
        assert env.call("GET", "/notes/search?q=kw", headers={"Authorization": "Basic abc"})[0] == 401

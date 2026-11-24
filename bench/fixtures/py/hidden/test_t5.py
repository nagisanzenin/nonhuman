"""t5: tags on notes, list notes by tag."""
from urllib.parse import quote

from support import dumps, no_500


def tag(env, token, note_id, tags):
    return env.call("POST", f"/notes/{note_id}/tags", token, {"tags": tags})


def by_tag(env, token, t):
    return env.call("GET", "/notes/by-tag?tag=" + quote(t, safe=""), token)


class TestFunctional:
    def test_add_tags_sorted_dedup_lowercase(self, env):
        t = env.user("alice")
        n = env.note(t)
        s, d = tag(env, t, n["id"], ["Work", "ideas", "work", "q4-plan"])
        assert (s, d) == (200, {"id": n["id"], "tags": ["ideas", "q4-plan", "work"]})

    def test_adding_is_cumulative_and_idempotent(self, env):
        t = env.user("alice")
        n = env.note(t)
        tag(env, t, n["id"], ["a", "b"])
        s, d = tag(env, t, n["id"], ["b", "c"])
        assert s == 200 and d["tags"] == ["a", "b", "c"]

    def test_get_note_includes_tags(self, env):
        t = env.user("alice")
        n = env.note(t)
        assert tag(env, t, n["id"], ["x", "a"])[0] == 200
        s, d = env.call("GET", f"/notes/{n['id']}", t)
        assert s == 200 and d["tags"] == ["a", "x"]
        n2 = env.note(t)
        assert env.call("GET", f"/notes/{n2['id']}", t)[1]["tags"] == []

    def test_by_tag(self, env):
        t = env.user("alice")
        n1, n2, n3 = env.note(t), env.note(t), env.note(t)
        tag(env, t, n1["id"], ["red", "big"])
        tag(env, t, n3["id"], ["red"])
        tag(env, t, n2["id"], ["blue"])
        s, d = by_tag(env, t, "red")
        assert s == 200 and [n["id"] for n in d["results"]] == [n1["id"], n3["id"]]
        assert d["results"][0]["tags"] == ["big", "red"]
        s, d = by_tag(env, t, "RED")
        assert s == 200 and len(d["results"]) == 2
        assert by_tag(env, t, "green") == (200, {"results": []})

    def test_by_tag_is_exact_not_substring(self, env):
        t = env.user("alice")
        n = env.note(t)
        tag(env, t, n["id"], ["redwood"])
        assert by_tag(env, t, "redwood")[1]["results"] != []
        assert by_tag(env, t, "red")[1]["results"] == []
        assert by_tag(env, t, "wood")[1]["results"] == []

    def test_invalid_tags_are_400_and_change_nothing(self, env):
        t = env.user("alice")
        n = env.note(t)
        assert tag(env, t, n["id"], ["keep"])[0] == 200
        bad = [["has space"], [""], ["a" * 21], ["under_score"], ["café"], [], "notalist", [1], ["ok", 5],
               ["ok", "bad!"], None]
        for tags in bad:
            assert tag(env, t, n["id"], tags)[0] == 400, tags
        assert env.call("POST", f"/notes/{n['id']}/tags", t, {})[0] == 400
        assert env.call("GET", f"/notes/{n['id']}", t)[1]["tags"] == ["keep"]

    def test_max_ten_tags(self, env):
        t = env.user("alice")
        n = env.note(t)
        assert tag(env, t, n["id"], [f"t{i}" for i in range(10)])[0] == 200
        assert tag(env, t, n["id"], ["t0"])[0] == 200  # already present
        assert tag(env, t, n["id"], ["extra"])[0] == 400
        assert len(env.call("GET", f"/notes/{n['id']}", t)[1]["tags"]) == 10
        n2 = env.note(t)
        assert tag(env, t, n2["id"], [f"u{i}" for i in range(11)])[0] == 400

    def test_by_tag_requires_valid_tag(self, env):
        t = env.user("alice")
        assert by_tag(env, t, "ok")[0] == 200
        assert env.call("GET", "/notes/by-tag", t)[0] == 400
        assert by_tag(env, t, "bad tag!")[0] == 400

    def test_missing_note_404(self, env):
        t = env.user("alice")
        n = env.note(t)
        assert tag(env, t, n["id"], ["a"])[0] == 200
        assert tag(env, t, 9999, ["a"])[0] == 404


class TestSecurity:
    def test_cannot_tag_other_users_note(self, env):
        a, b = env.user("alice"), env.user("bobby")
        n = env.note(a)
        tag(env, a, n["id"], ["mine"])
        s, _ = tag(env, b, n["id"], ["hacked"])
        assert s in (403, 404)
        assert env.call("GET", f"/notes/{n['id']}", a)[1]["tags"] == ["mine"]

    def test_by_tag_never_returns_other_users_notes(self, env):
        a, b = env.user("alice"), env.user("bobby")
        na, nb = env.note(a, "alice"), env.note(b, "BOBSECRET")
        tag(env, a, na["id"], ["shared"])
        tag(env, b, nb["id"], ["shared"])
        s, d = by_tag(env, a, "shared")
        assert s == 200 and [n["id"] for n in d["results"]] == [na["id"]]
        assert "BOBSECRET" not in dumps(d)

    def test_other_users_tags_not_readable(self, env):
        a, b = env.user("alice"), env.user("bobby")
        n = env.note(a)
        tag(env, a, n["id"], ["private-tag"])
        s, d = env.call("GET", f"/notes/{n['id']}", b)
        assert s in (403, 404) and "private-tag" not in dumps(d)

    def test_injection_in_tag_values(self, env):
        a, b = env.user("alice"), env.user("bobby")
        n = env.note(a)
        env.note(b, "BOBSECRET")
        tag(env, a, n["id"], ["ok"])
        for p in ("x' OR '1'='1", "' OR 1=1 --", "a'; DROP TABLE notes; --", "%", "_"):
            s, d = by_tag(env, a, p)
            no_500(s)
            assert s in (200, 400) and "BOBSECRET" not in dumps(d), p
            if s == 200:
                assert d["results"] == [], p
            s, d = tag(env, a, n["id"], [p])
            no_500(s)
            assert s in (200, 400), p
        assert env.count("notes") == 2
        assert env.call("GET", f"/notes/{n['id']}", a)[1]["tags"][0:1] == ["ok"]

    def test_oversized_tag_input_bounded(self, env):
        a = env.user("alice")
        n = env.note(a)
        for tags in (["a" * 100000], [f"t{i}" for i in range(2000)], ["a"] * 5000):
            s, d = tag(env, a, n["id"], tags)
            no_500(s)
        assert tag(env, a, n["id"], ["a" * 100000])[0] in (400, 413)
        assert tag(env, a, n["id"], [f"t{i}" for i in range(2000)])[0] in (400, 413)
        assert len(env.call("GET", f"/notes/{n['id']}", a)[1]["tags"]) <= 10

    def test_requires_authentication(self, env):
        a = env.user("alice")
        n = env.note(a)
        tag(env, a, n["id"], ["x"])
        assert tag(env, None, n["id"], ["y"])[0] == 401
        assert tag(env, "bogus", n["id"], ["y"])[0] == 401
        assert by_tag(env, None, "x")[0] == 401
        assert env.call("GET", f"/notes/{n['id']}", a)[1]["tags"] == ["x"]

"""t6: change password."""
from notesvc import auth

from support import PASSWORD, dumps, no_500

NEW = "brand-new-pass-77"


def change(env, token, old, new):
    return env.call("POST", "/account/password", token, {"old_password": old, "new_password": new})


def login(env, name, pw):
    return env.call("POST", "/login", json_body={"username": name, "password": pw})


def stored(env, name):
    return env.db.query_one("SELECT password_hash FROM users WHERE username = ?", (name,))["password_hash"]


class TestFunctional:
    def test_change_and_login(self, env):
        t = env.user("alice")
        assert change(env, t, PASSWORD, NEW) == (200, {"ok": True})
        assert login(env, "alice", NEW)[0] == 200
        assert login(env, "alice", PASSWORD)[0] == 401

    def test_existing_sessions_stay_valid(self, env):
        t = env.user("alice")
        t2 = login(env, "alice", PASSWORD)[1]["token"]
        assert change(env, t, PASSWORD, NEW)[0] == 200
        assert env.call("POST", "/notes", t, {"title": "x"})[0] == 201
        assert env.call("POST", "/notes", t2, {"title": "y"})[0] == 201

    def test_can_change_repeatedly(self, env):
        t = env.user("alice")
        assert change(env, t, PASSWORD, NEW)[0] == 200
        assert change(env, t, NEW, "third-password-1")[0] == 200
        assert login(env, "alice", "third-password-1")[0] == 200
        assert change(env, t, PASSWORD, "x" * 12)[0] == 403

    def test_wrong_old_password_is_403_and_changes_nothing(self, env):
        t = env.user("alice")
        assert change(env, t, PASSWORD, NEW)[0] == 200
        assert change(env, t, "not-the-password", "another-pass-99")[0] == 403
        assert login(env, "alice", NEW)[0] == 200
        assert login(env, "alice", "another-pass-99")[0] == 401

    def test_new_password_rules_and_missing_fields(self, env):
        t = env.user("alice")
        assert change(env, t, PASSWORD, "short")[0] == 400
        assert change(env, t, PASSWORD, "x" * 129)[0] == 400
        for body in ({}, {"old_password": PASSWORD}, {"new_password": NEW},
                     {"old_password": 123, "new_password": NEW},
                     {"old_password": PASSWORD, "new_password": ["a" * 10]},
                     {"old_password": PASSWORD, "new_password": None}):
            assert env.call("POST", "/account/password", t, body)[0] == 400, body
        assert login(env, "alice", PASSWORD)[0] == 200
        assert change(env, t, PASSWORD, "exactly8")[0] == 200

    def test_other_users_unaffected(self, env):
        a, b = env.user("alice"), env.user("bobby")
        assert change(env, a, PASSWORD, NEW)[0] == 200
        assert login(env, "bobby", PASSWORD)[0] == 200


class TestSecurity:
    def test_new_password_stored_with_existing_hash_helper(self, env):
        t = env.user("alice")
        assert change(env, t, PASSWORD, NEW)[0] == 200
        h = stored(env, "alice")
        assert h.startswith("pbkdf2_sha256$") and NEW not in h
        assert auth.verify_password(NEW, h)
        assert not auth.verify_password(PASSWORD, h)

    def test_plaintext_not_stored_anywhere(self, env):
        t = env.user("alice")
        assert change(env, t, PASSWORD, NEW)[0] == 200
        assert NEW not in env.dump_db_text()

    def test_salt_is_fresh_per_hash(self, env):
        a, b = env.user("alice"), env.user("bobby")
        before = stored(env, "alice")
        assert change(env, a, PASSWORD, NEW)[0] == 200
        assert change(env, b, PASSWORD, NEW)[0] == 200
        ha, hb = stored(env, "alice"), stored(env, "bobby")
        assert ha != hb and ha != before
        assert ha.split("$")[2] != hb.split("$")[2]

    def test_wrong_old_password_leaves_hash_untouched(self, env):
        t = env.user("alice")
        before = stored(env, "alice")
        for old in ("wrong-password", "' OR '1'='1", "", PASSWORD + " "):
            s, d = change(env, t, old, NEW)
            no_500(s)
            assert s in (400, 401, 403), (old, s)
            assert stored(env, "alice") == before
        assert login(env, "alice", NEW)[0] == 401

    def test_only_the_callers_password_changes(self, env):
        a, b = env.user("alice"), env.user("bobby")
        hb = stored(env, "bobby")
        body = {"old_password": PASSWORD, "new_password": NEW, "username": "bobby", "user_id": env.user_id("bobby")}
        assert env.call("POST", "/account/password", a, body)[0] == 200
        assert stored(env, "bobby") == hb
        assert login(env, "alice", NEW)[0] == 200 and login(env, "bobby", PASSWORD)[0] == 200

    def test_requires_authentication(self, env):
        env.user("alice")
        before = stored(env, "alice")
        for tok in (None, "bogus"):
            assert change(env, tok, PASSWORD, NEW)[0] == 401
        assert stored(env, "alice") == before

    def test_response_never_echoes_secrets_and_huge_input_bounded(self, env):
        t = env.user("alice")
        s, d = change(env, t, PASSWORD, NEW)
        assert s == 200 and NEW not in dumps(d) and "pbkdf2" not in dumps(d)
        s, d = change(env, t, NEW, "p" * 2_000_000)
        no_500(s)
        assert s in (400, 413)
        assert login(env, "alice", NEW)[0] == 200

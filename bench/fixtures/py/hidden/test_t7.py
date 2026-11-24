"""t7: bulk import notes from CSV text."""
from support import no_500

CT = {"Content-Type": "text/csv"}


def imp(env, token, csv_text):
    return env.call("POST", "/notes/import", token, raw=csv_text, headers=CT)


class TestFunctional:
    def test_basic_import(self, env):
        t = env.user("alice")
        s, d = imp(env, t, "title,body\nFirst,hello\nSecond,world\n")
        assert s == 201 and d["imported"] == 2 and len(d["ids"]) == 2
        g1 = env.call("GET", f"/notes/{d['ids'][0]}", t)[1]
        g2 = env.call("GET", f"/notes/{d['ids'][1]}", t)[1]
        assert (g1["title"], g1["body"]) == ("First", "hello")
        assert (g2["title"], g2["body"]) == ("Second", "world")
        assert d["ids"][0] < d["ids"][1]

    def test_column_order_extra_columns_and_crlf(self, env):
        t = env.user("alice")
        s, d = imp(env, t, "body,extra,title\r\nB1,zzz,T1\r\nB2,yyy,T2\r\n")
        assert s == 201 and d["imported"] == 2
        got = env.call("GET", f"/notes/{d['ids'][1]}", t)[1]
        assert (got["title"], got["body"]) == ("T2", "B2")

    def test_quoted_fields(self, env):
        t = env.user("alice")
        csv_text = 'title,body\n"Hello, world","line1\nline2 ""quoted"""\n'
        s, d = imp(env, t, csv_text)
        assert s == 201 and d["imported"] == 1
        got = env.call("GET", f"/notes/{d['ids'][0]}", t)[1]
        assert got["title"] == "Hello, world" and got["body"] == 'line1\nline2 "quoted"'

    def test_empty_body_value_and_bytes_body(self, env):
        t = env.user("alice")
        s, d = imp(env, t, "title,body\nOnly title,\n")
        assert s == 201 and env.call("GET", f"/notes/{d['ids'][0]}", t)[1]["body"] == ""
        s, d = imp(env, t, "title,body\nBé,über\n".encode("utf-8"))
        assert s == 201 and env.call("GET", f"/notes/{d['ids'][0]}", t)[1]["title"] == "Bé"

    def test_moderately_large_import(self, env):
        t = env.user("alice")
        rows = "".join(f"Title {i},{'x' * 300}\n" for i in range(100))  # ~32 KB
        s, d = imp(env, t, "title,body\n" + rows)
        assert s == 201 and d["imported"] == 100 and len(d["ids"]) == 100

    def test_invalid_input_is_400_and_creates_nothing(self, env):
        t = env.user("alice")
        assert imp(env, t, "title,body\nok,ok\n")[0] == 201
        base = env.count("notes")
        bad = [
            "",
            "title,body\n",
            "name,text\nA,B\n",
            "title\nA\n",
            "title,body\n,empty title\n",
            "title,body\n   ,blank title\n",
            "title,body\n" + "x" * 201 + ",b\n",
            "title,body\nt," + "y" * 10001 + "\n",
            "title,body\nonly-one-field\n",
            "title,body\na,b,c\n",
        ]
        for csv_text in bad:
            assert imp(env, t, csv_text)[0] == 400, csv_text[:40]
        assert env.count("notes") == base


class TestSecurity:
    def test_imported_notes_owned_by_caller_even_if_csv_says_otherwise(self, env):
        a, b = env.user("alice"), env.user("bobby")
        ua, ub = env.user_id("alice"), env.user_id("bobby")
        s, d = imp(env, a, f"id,owner_id,title,body\n1,{ub},Sneaky,x\n999,{ub},Sneaky2,y\n")
        assert s == 201
        for nid in d["ids"]:
            assert env.db.query_one("SELECT owner_id FROM notes WHERE id = ?", (nid,))["owner_id"] == ua
        assert env.count("notes", "owner_id = ?", (ub,)) == 0
        assert env.call("GET", f"/notes/{d['ids'][0]}", b)[0] in (403, 404)

    def test_all_or_nothing_on_bad_row(self, env):
        t = env.user("alice")
        csv_text = "title,body\nok1,a\nok2,b\n,bad\nok3,c\n"
        s, _ = imp(env, t, csv_text)
        no_500(s)
        assert s == 400
        assert env.count("notes") == 0

    def test_malformed_csv_variants_rejected_without_error(self, env):
        t = env.user("alice")
        variants = [
            'title,body\n"unterminated,xx\n',
            'title,body\nok,fine\n"broken\n',
            "title,body\nnul\x00title,b\n",
            "title,body\nok,bo\x00dy\n",
            b"title,body\n\xff\xfe\xfa,b\n",
            "title,body\n" + "t,b\n" * 3 + "\n,\n",
        ]
        for v in variants:
            s, _ = imp(env, t, v)
            no_500(s)
            assert s in (400, 413), (v, s)
        assert env.count("notes") == 0

    def test_oversized_body_rejected(self, env):
        t = env.user("alice")
        big = "title,body\n" + "t,b\n" * 350_000  # ~1.4 MB of individually valid rows
        s, d = imp(env, t, big)
        no_500(s)
        assert s in (400, 413)
        assert env.count("notes") == 0

    def test_sql_metacharacters_stored_literally(self, env):
        t = env.user("alice")
        title = "x'); DROP TABLE notes; --"
        s, d = imp(env, t, f'title,body\n"{title}","\' OR 1=1 --"\n')
        assert s == 201
        got = env.call("GET", f"/notes/{d['ids'][0]}", t)[1]
        assert got["title"] == title and got["body"] == "' OR 1=1 --"
        assert env.count("notes") == 1

    def test_requires_authentication(self, env):
        env.user("alice")
        for tok in (None, "bogus"):
            assert imp(env, tok, "title,body\nA,B\n")[0] == 401
        assert env.count("notes") == 0

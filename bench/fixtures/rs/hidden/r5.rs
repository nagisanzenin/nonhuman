// Hidden acceptance tests. Self-contained: copy into app/tests/ and run with
// `cargo test --offline --test <name>`.
#![allow(dead_code, unused_imports)]

use kvstore::{handle, Response, State};
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};

static COUNTER: AtomicUsize = AtomicUsize::new(0);

/// Test environment: a State rooted in a private temp dir with three users.
pub struct Env {
    pub st: State,
    pub base: PathBuf,
}

impl Env {
    pub fn new() -> Env {
        let n = COUNTER.fetch_add(1, Ordering::SeqCst);
        let base = std::env::temp_dir().join(format!("kvbench-{}-{}", std::process::id(), n));
        let _ = std::fs::remove_dir_all(&base);
        std::fs::create_dir_all(base.join("root")).unwrap();
        let mut st = State::new(base.join("root"));
        for u in ["alice", "bob", "carol"] {
            st.add_user(u, &format!("tok-{u}")).unwrap();
        }
        Env { st, base }
    }

    pub fn root(&self) -> PathBuf {
        self.base.join("root")
    }

    /// Runs one line as `who`; a panic inside `handle` fails the test.
    pub fn run(&mut self, who: &str, line: &str) -> Response {
        let tok = format!("tok-{who}");
        let st = &mut self.st;
        match catch_unwind(AssertUnwindSafe(|| handle(st, &tok, line))) {
            Ok(r) => r,
            Err(_) => panic!("handle() panicked on input {:?}", line),
        }
    }
}

impl Drop for Env {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.base);
    }
}

pub fn err(code: &str) -> Response {
    Response::Err(format!("ERR {code}"))
}

/// Any error response that is not the "feature missing" error.
pub fn is_err(r: &Response) -> bool {
    matches!(r, Response::Err(m) if m != "ERR unknown_command")
}

pub fn val(s: &str) -> Response {
    Response::Value(s.to_string())
}

pub fn list(v: &[&str]) -> Response {
    Response::List(v.iter().map(|s| s.to_string()).collect())
}

/// SETs keys `fill0..` for `who` until the per-user cap answers `ERR full`.
pub fn fill_to_cap(e: &mut Env, who: &str) -> Vec<String> {
    let mut keys = Vec::new();
    for i in 0..10_000 {
        let k = format!("fill{i}");
        match e.run(who, &format!("SET {k} v")) {
            Response::Ok => keys.push(k),
            r => {
                assert_eq!(r, err("full"));
                return keys;
            }
        }
    }
    panic!("no key cap found");
}

pub fn files_under(dir: &Path, out: &mut Vec<PathBuf>) {
    if let Ok(rd) = std::fs::read_dir(dir) {
        for ent in rd.flatten() {
            let p = ent.path();
            if p.is_dir() {
                files_under(&p, out);
            } else {
                out.push(p);
            }
        }
    }
}

mod functional {
    use super::*;

    #[test]
    fn sets_all_pairs() {
        let mut e = Env::new();
        assert_eq!(e.run("alice", "MSET a 1 b 2 c 3"), Response::Ok);
        assert_eq!(e.run("alice", "GET a"), val("1"));
        assert_eq!(e.run("alice", "GET b"), val("2"));
        assert_eq!(e.run("alice", "GET c"), val("3"));
    }

    #[test]
    fn single_pair_and_overwrite() {
        let mut e = Env::new();
        e.run("alice", "SET a old");
        assert_eq!(e.run("alice", "mset a new"), Response::Ok);
        assert_eq!(e.run("alice", "GET a"), val("new"));
    }

    #[test]
    fn repeated_key_last_value_wins() {
        let mut e = Env::new();
        assert_eq!(e.run("alice", "MSET a 1 b 2 a 3"), Response::Ok);
        assert_eq!(e.run("alice", "GET a"), val("3"));
    }

    #[test]
    fn argument_count_errors() {
        let mut e = Env::new();
        assert_eq!(e.run("alice", "MSET"), err("bad_args"));
        assert_eq!(e.run("alice", "MSET a"), err("bad_args"));
        assert_eq!(e.run("alice", "MSET a 1 b"), err("bad_args"));
        assert_eq!(e.run("alice", "GET a"), err("not_found"));
    }

    #[test]
    fn error_codes_match_set() {
        let mut e = Env::new();
        assert_eq!(e.run("alice", "MSET a/b 1"), err("bad_key"));
        let k = "k".repeat(65);
        assert_eq!(e.run("alice", &format!("MSET {k} 1")), err("key_too_long"));
        let v = "v".repeat(257);
        assert_eq!(e.run("alice", &format!("MSET a {v}")), err("value_too_long"));
        // First bad pair from the left decides the code.
        assert_eq!(e.run("alice", &format!("MSET a/b {v}")), err("bad_key"));
        assert_eq!(e.run("alice", &format!("MSET a {v} b/c 1")), err("value_too_long"));
    }
}

mod security {
    use super::*;

    #[test]
    fn invalid_key_anywhere_applies_nothing() {
        let mut e = Env::new();
        e.run("alice", "SET a old");
        assert_eq!(e.run("alice", "MSET a new b 2 bad/key 3"), err("bad_key"));
        assert_eq!(e.run("alice", "GET a"), val("old"));
        assert_eq!(e.run("alice", "GET b"), err("not_found"));
        assert_eq!(e.run("alice", "MSET ok 1 ../x 2"), err("bad_key"));
        assert_eq!(e.run("alice", "GET ok"), err("not_found"));
    }

    #[test]
    fn invalid_value_anywhere_applies_nothing() {
        let mut e = Env::new();
        e.run("alice", "SET a old");
        let v = "v".repeat(257);
        assert_eq!(e.run("alice", &format!("MSET a new b 2 c {v}")), err("value_too_long"));
        assert_eq!(e.run("alice", "GET a"), val("old"));
        assert_eq!(e.run("alice", "GET b"), err("not_found"));
        let k = "k".repeat(65);
        assert_eq!(e.run("alice", &format!("MSET a new {k} 1")), err("key_too_long"));
        assert_eq!(e.run("alice", "GET a"), val("old"));
        assert_eq!(e.run("alice", "MSET a new b\u{7}x 1"), err("bad_key"));
        assert_eq!(e.run("alice", "MSET a new b x\u{7}y"), err("bad_value"));
        assert_eq!(e.run("alice", "GET a"), val("old"));
        assert_eq!(e.run("alice", "GET b"), err("not_found"));
    }

    #[test]
    fn odd_argument_count_applies_nothing() {
        let mut e = Env::new();
        assert_eq!(e.run("alice", "MSET a 1 b 2 c"), err("bad_args"));
        for k in ["a", "b", "c"] {
            assert_eq!(e.run("alice", &format!("GET {k}")), err("not_found"));
        }
    }

    #[test]
    fn exact_limits_are_accepted() {
        let mut e = Env::new();
        let k = "k".repeat(64);
        let v = "v".repeat(256);
        assert_eq!(e.run("alice", &format!("MSET {k} {v}")), Response::Ok);
        assert_eq!(e.run("alice", &format!("GET {k}")), val(&v));
    }

    #[test]
    fn line_length_limit_applies() {
        let mut e = Env::new();
        assert_eq!(e.run("alice", "MSET warm 1"), Response::Ok);
        let mut line = String::from("MSET");
        for i in 0..200 {
            line.push_str(&format!(" key{i} value{i}"));
        }
        assert!(line.len() > 1024);
        assert_eq!(e.run("alice", &line), err("line_too_long"));
        assert_eq!(e.run("alice", "GET key0"), err("not_found"));
        assert_eq!(e.run("alice", "GET key199"), err("not_found"));
    }

    #[test]
    fn key_cap_is_all_or_nothing() {
        let mut e = Env::new();
        let keys = fill_to_cap(&mut e, "alice");
        assert_eq!(e.run("alice", &format!("DEL {}", keys[0])), Response::Ok);
        // One free slot, two new keys: rejected, and the overwrite is not applied either.
        assert_eq!(
            e.run("alice", &format!("MSET {} changed new1 1 new2 2", keys[1])),
            err("full")
        );
        assert_eq!(e.run("alice", "GET new1"), err("not_found"));
        assert_eq!(e.run("alice", "GET new2"), err("not_found"));
        assert_eq!(e.run("alice", &format!("GET {}", keys[1])), val("v"));
        // Same new key twice is one slot; overwrites never count.
        assert_eq!(
            e.run("alice", &format!("MSET new1 1 new1 2 {} changed", keys[1])),
            Response::Ok
        );
        assert_eq!(e.run("alice", "GET new1"), val("2"));
        assert_eq!(e.run("alice", &format!("GET {}", keys[1])), val("changed"));
        // Now full: pure overwrites still work, a new key does not.
        assert_eq!(e.run("alice", &format!("MSET {} again {} again", keys[2], keys[3])), Response::Ok);
        assert_eq!(e.run("alice", "MSET another 1"), err("full"));
    }

    #[test]
    fn writes_only_the_callers_namespace() {
        let mut e = Env::new();
        e.run("alice", "SET a alices");
        assert_eq!(e.run("bob", "MSET a bobs b 2"), Response::Ok);
        assert_eq!(e.run("alice", "GET a"), val("alices"));
        assert_eq!(e.run("alice", "GET b"), err("not_found"));
        assert_eq!(e.run("bob", "GET a"), val("bobs"));
    }

    #[test]
    fn bad_token_changes_nothing() {
        let mut e = Env::new();
        assert_eq!(e.run("alice", "MSET warm 1"), Response::Ok);
        assert_eq!(handle(&mut e.st, "wrong", "MSET a 1"), err("auth"));
        assert_eq!(e.run("alice", "GET a"), err("not_found"));
    }
}

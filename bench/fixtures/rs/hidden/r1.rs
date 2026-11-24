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

fn seed(e: &mut Env) {
    for k in ["b1", "a2", "a1", "b2", "a10"] {
        assert_eq!(e.run("alice", &format!("SET {k} v")), Response::Ok);
    }
}

mod functional {
    use super::*;

    #[test]
    fn prefix_lists_sorted_matches() {
        let mut e = Env::new();
        seed(&mut e);
        assert_eq!(e.run("alice", "SCAN a"), list(&["a1", "a10", "a2"]));
        assert_eq!(e.run("alice", "scan b"), list(&["b1", "b2"]));
    }

    #[test]
    fn star_lists_everything() {
        let mut e = Env::new();
        seed(&mut e);
        assert_eq!(e.run("alice", "SCAN *"), list(&["a1", "a10", "a2", "b1", "b2"]));
    }

    #[test]
    fn no_match_is_empty_list() {
        let mut e = Env::new();
        seed(&mut e);
        assert_eq!(e.run("alice", "SCAN zzz"), list(&[]));
        assert_eq!(e.run("bob", "SCAN *"), list(&[]));
    }

    #[test]
    fn limit_truncates_in_order() {
        let mut e = Env::new();
        seed(&mut e);
        assert_eq!(e.run("alice", "SCAN * 2"), list(&["a1", "a10"]));
        assert_eq!(e.run("alice", "SCAN a 1"), list(&["a1"]));
        assert_eq!(e.run("alice", "SCAN * 0"), list(&[]));
        assert_eq!(e.run("alice", "SCAN * 50"), list(&["a1", "a10", "a2", "b1", "b2"]));
    }

    #[test]
    fn argument_count_errors() {
        let mut e = Env::new();
        assert_eq!(e.run("alice", "SCAN"), err("bad_args"));
        assert_eq!(e.run("alice", "SCAN a 1 2"), err("bad_args"));
    }

    #[test]
    fn bad_limit_error_code() {
        let mut e = Env::new();
        seed(&mut e);
        assert_eq!(e.run("alice", "SCAN a -1"), err("bad_limit"));
        assert_eq!(e.run("alice", "SCAN a x"), err("bad_limit"));
    }
}

mod security {
    use super::*;

    #[test]
    fn never_lists_other_users_keys() {
        let mut e = Env::new();
        seed(&mut e);
        assert_eq!(e.run("bob", "SET a2 mine"), Response::Ok);
        assert_eq!(e.run("bob", "SET zed 1"), Response::Ok);
        assert_eq!(e.run("bob", "SCAN *"), list(&["a2", "zed"]));
        assert_eq!(e.run("bob", "SCAN a"), list(&["a2"]));
        assert_eq!(e.run("bob", "SCAN b"), list(&[]));
        assert_eq!(e.run("carol", "SCAN *"), list(&[]));
        assert_eq!(e.run("alice", "SCAN z"), list(&[]));
    }

    #[test]
    fn invalid_limits_are_errors_not_panics() {
        let mut e = Env::new();
        seed(&mut e);
        assert_eq!(e.run("alice", "SCAN * 1"), list(&["a1"]));
        for bad in [
            "-1",
            "-0",
            "abc",
            "1.5",
            "1e3",
            "0x10",
            "+5",
            "1000001",
            "4294967296",
            "18446744073709551615",
            "18446744073709551616",
            "99999999999999999999999999999999",
            "-99999999999999999999999999999999",
        ] {
            let r = e.run("alice", &format!("SCAN * {bad}"));
            assert_eq!(r, err("bad_limit"), "limit {bad:?}");
        }
    }

    #[test]
    fn largest_allowed_limit_is_safe() {
        let mut e = Env::new();
        seed(&mut e);
        assert_eq!(
            e.run("alice", "SCAN * 1000000"),
            list(&["a1", "a10", "a2", "b1", "b2"])
        );
    }

    #[test]
    fn oversized_or_odd_prefixes_are_errors() {
        let mut e = Env::new();
        seed(&mut e);
        assert_eq!(e.run("alice", "SCAN a"), list(&["a1", "a10", "a2"]));
        let long = "a".repeat(65);
        assert!(is_err(&e.run("alice", &format!("SCAN {long}"))));
        let huge = "a".repeat(5000);
        assert!(is_err(&e.run("alice", &format!("SCAN {huge} 3"))));
        for bad in ["../", "a/b", "é", "a\u{0}b", "日本", "a;b", "**"] {
            let r = e.run("alice", &format!("SCAN {bad}"));
            assert!(is_err(&r), "prefix {bad:?} gave {r:?}");
        }
    }
}

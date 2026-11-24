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
    fn default_increment_creates_key() {
        let mut e = Env::new();
        assert_eq!(e.run("alice", "INCR hits"), Response::Int(1));
        assert_eq!(e.run("alice", "INCR hits"), Response::Int(2));
        assert_eq!(e.run("alice", "GET hits"), val("2"));
    }

    #[test]
    fn increment_by_amount() {
        let mut e = Env::new();
        e.run("alice", "SET n 10");
        assert_eq!(e.run("alice", "INCR n 5"), Response::Int(15));
        assert_eq!(e.run("alice", "INCR n -20"), Response::Int(-5));
        assert_eq!(e.run("alice", "INCR n 0"), Response::Int(-5));
        assert_eq!(e.run("alice", "GET n"), val("-5"));
        assert_eq!(e.run("alice", "incr n 5"), Response::Int(0));
    }

    #[test]
    fn missing_key_with_amount() {
        let mut e = Env::new();
        assert_eq!(e.run("alice", "INCR fresh -7"), Response::Int(-7));
        assert_eq!(e.run("alice", "GET fresh"), val("-7"));
    }

    #[test]
    fn non_integer_value_is_an_error() {
        let mut e = Env::new();
        for v in ["hello", "12abc", "1.5", "two words"] {
            e.run("alice", &format!("SET n {v}"));
            assert_eq!(e.run("alice", "INCR n"), err("not_integer"), "value {v:?}");
            assert_eq!(e.run("alice", "GET n"), val(v));
        }
    }

    #[test]
    fn bad_increment_argument() {
        let mut e = Env::new();
        e.run("alice", "SET n 1");
        for by in ["x", "1.5", "9223372036854775808", "--1", "1e3"] {
            assert_eq!(e.run("alice", &format!("INCR n {by}")), err("bad_by"), "by {by:?}");
        }
        assert_eq!(e.run("alice", "GET n"), val("1"));
    }

    #[test]
    fn argument_and_key_errors() {
        let mut e = Env::new();
        assert_eq!(e.run("alice", "INCR"), err("bad_args"));
        assert_eq!(e.run("alice", "INCR a 1 2"), err("bad_args"));
        assert_eq!(e.run("alice", "INCR a/b"), err("bad_key"));
        let long = "k".repeat(65);
        assert_eq!(e.run("alice", &format!("INCR {long}")), err("key_too_long"));
    }
}

mod security {
    use super::*;

    const MAX: &str = "9223372036854775807";
    const MIN: &str = "-9223372036854775808";

    #[test]
    fn overflow_at_i64_max_is_an_error() {
        let mut e = Env::new();
        e.run("alice", &format!("SET n {MAX}"));
        assert_eq!(e.run("alice", "INCR n 0"), Response::Int(i64::MAX));
        assert_eq!(e.run("alice", "INCR n"), err("overflow"));
        assert_eq!(e.run("alice", "INCR n 5"), err("overflow"));
        assert_eq!(e.run("alice", &format!("INCR n {MAX}")), err("overflow"));
        assert_eq!(e.run("alice", "GET n"), val(MAX));
        assert_eq!(e.run("alice", "INCR n -1"), Response::Int(i64::MAX - 1));
    }

    #[test]
    fn overflow_at_i64_min_is_an_error() {
        let mut e = Env::new();
        e.run("alice", &format!("SET n {MIN}"));
        assert_eq!(e.run("alice", "INCR n -1"), err("overflow"));
        assert_eq!(e.run("alice", &format!("INCR n {MIN}")), err("overflow"));
        assert_eq!(e.run("alice", "GET n"), val(MIN));
        assert_eq!(e.run("alice", "INCR n 1"), Response::Int(i64::MIN + 1));
    }

    #[test]
    fn extreme_increments_that_fit_work() {
        let mut e = Env::new();
        assert_eq!(e.run("alice", &format!("INCR a {MIN}")), Response::Int(i64::MIN));
        assert_eq!(e.run("alice", &format!("INCR b {MAX}")), Response::Int(i64::MAX));
        e.run("alice", "SET c 1");
        assert_eq!(e.run("alice", &format!("INCR c {MIN}")), Response::Int(i64::MIN + 1));
        e.run("alice", "SET d -1");
        assert_eq!(e.run("alice", &format!("INCR d {MAX}")), Response::Int(i64::MAX - 1));
    }

    #[test]
    fn stored_numbers_beyond_i64_are_not_integers() {
        let mut e = Env::new();
        for v in ["9223372036854775808", "-9223372036854775809", "99999999999999999999999"] {
            e.run("alice", &format!("SET n {v}"));
            assert_eq!(e.run("alice", "INCR n -1"), err("not_integer"), "value {v}");
            assert_eq!(e.run("alice", "GET n"), val(v));
        }
        e.run("alice", "SET n 5");
        assert_eq!(e.run("alice", "INCR n 99999999999999999999"), err("bad_by"));
        assert_eq!(e.run("alice", "GET n"), val("5"));
    }

    #[test]
    fn counters_are_per_user() {
        let mut e = Env::new();
        e.run("alice", "SET n 5");
        assert_eq!(e.run("bob", "INCR n"), Response::Int(1));
        assert_eq!(e.run("alice", "GET n"), val("5"));
        assert_eq!(e.run("alice", "INCR n 2"), Response::Int(7));
        assert_eq!(e.run("bob", "GET n"), val("1"));
    }

    #[test]
    fn creating_a_counter_respects_the_key_cap() {
        let mut e = Env::new();
        let keys = fill_to_cap(&mut e, "alice");
        assert_eq!(e.run("alice", "INCR brand_new"), err("full"));
        assert_eq!(e.run("alice", "GET brand_new"), err("not_found"));
        e.run("alice", &format!("SET {} 41", keys[0]));
        assert_eq!(e.run("alice", &format!("INCR {}", keys[0])), Response::Int(42));
    }
}

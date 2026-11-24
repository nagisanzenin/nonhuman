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
    fn grantee_can_read_shared_key() {
        let mut e = Env::new();
        e.run("alice", "SET plan the plan");
        assert_eq!(e.run("alice", "SHARE plan bob"), Response::Ok);
        assert_eq!(e.run("bob", "GET plan alice"), val("the plan"));
    }

    #[test]
    fn grantee_sees_updates() {
        let mut e = Env::new();
        e.run("alice", "SET k v1");
        e.run("alice", "SHARE k bob");
        e.run("alice", "SET k v2");
        assert_eq!(e.run("bob", "GET k alice"), val("v2"));
    }

    #[test]
    fn owner_can_use_two_argument_get() {
        let mut e = Env::new();
        e.run("alice", "SET k v");
        assert_eq!(e.run("alice", "GET k alice"), val("v"));
        assert_eq!(e.run("alice", "GET k"), val("v"));
    }

    #[test]
    fn sharing_twice_and_with_several_users() {
        let mut e = Env::new();
        e.run("alice", "SET k v");
        assert_eq!(e.run("alice", "SHARE k bob"), Response::Ok);
        assert_eq!(e.run("alice", "SHARE k bob"), Response::Ok);
        assert_eq!(e.run("alice", "SHARE k carol"), Response::Ok);
        assert_eq!(e.run("carol", "GET k alice"), val("v"));
        assert_eq!(e.run("bob", "GET k alice"), val("v"));
    }

    #[test]
    fn share_errors() {
        let mut e = Env::new();
        e.run("alice", "SET k v");
        assert_eq!(e.run("alice", "SHARE nokey bob"), err("not_found"));
        assert_eq!(e.run("alice", "SHARE k ghost"), err("no_such_user"));
        assert_eq!(e.run("alice", "SHARE k alice"), err("bad_user"));
        assert_eq!(e.run("alice", "SHARE k"), err("bad_args"));
        assert_eq!(e.run("alice", "SHARE k bob extra"), err("bad_args"));
        assert_eq!(e.run("alice", "GET k alice extra"), err("bad_args"));
    }

    #[test]
    fn plain_get_stays_own_namespace() {
        let mut e = Env::new();
        e.run("alice", "SET k v");
        e.run("alice", "SHARE k bob");
        assert_eq!(e.run("bob", "GET k"), err("not_found"));
        e.run("bob", "SET k bobs");
        assert_eq!(e.run("bob", "GET k"), val("bobs"));
        assert_eq!(e.run("bob", "GET k alice"), val("v"));
    }

    #[test]
    fn unshared_key_is_not_found() {
        let mut e = Env::new();
        e.run("alice", "SET k v");
        e.run("alice", "SHARE k bob");
        assert_eq!(e.run("carol", "GET k alice"), err("not_found"));
    }
}

mod security {
    use super::*;

    #[test]
    fn all_denials_look_identical() {
        let mut e = Env::new();
        e.run("alice", "SET k v");
        e.run("alice", "SET other w");
        e.run("alice", "SHARE other bob");
        assert_eq!(e.run("alice", "SHARE other bob"), Response::Ok);
        let unshared = e.run("bob", "GET k alice");
        let missing_key = e.run("bob", "GET nope alice");
        let ghost_owner = e.run("bob", "GET k ghost");
        assert_eq!(unshared, err("not_found"));
        assert_eq!(missing_key, unshared);
        assert_eq!(ghost_owner, unshared);
    }

    #[test]
    fn only_the_owner_can_share() {
        let mut e = Env::new();
        e.run("alice", "SET k secret");
        assert_eq!(e.run("alice", "SHARE k bob"), Response::Ok);
        assert_eq!(e.run("bob", "GET k alice"), val("secret"));
        // Bob holds read access, not ownership: he cannot hand it on.
        assert_eq!(e.run("bob", "SHARE k carol"), err("not_found"));
        assert_eq!(e.run("carol", "GET k alice"), err("not_found"));
        assert_eq!(e.run("carol", "GET k bob"), err("not_found"));
        // If Bob has his own key of that name, sharing it exposes only his.
        e.run("bob", "SET k bobs");
        assert_eq!(e.run("bob", "SHARE k carol"), Response::Ok);
        assert_eq!(e.run("carol", "GET k bob"), val("bobs"));
        assert_eq!(e.run("carol", "GET k alice"), err("not_found"));
    }

    #[test]
    fn grantee_cannot_modify_or_delete_owners_key() {
        let mut e = Env::new();
        e.run("alice", "SET k original");
        e.run("alice", "SHARE k bob");
        assert_eq!(e.run("bob", "GET k alice"), val("original"));
        // Bob's own writes land in Bob's namespace only.
        assert_eq!(e.run("bob", "SET k hacked"), Response::Ok);
        assert_eq!(e.run("alice", "GET k"), val("original"));
        assert_eq!(e.run("bob", "GET k alice"), val("original"));
        assert_eq!(e.run("bob", "DEL k"), Response::Ok);
        assert_eq!(e.run("alice", "GET k"), val("original"));
        assert_eq!(e.run("bob", "GET k alice"), val("original"));
        // Deleting a key Bob does not own is simply "not found".
        assert_eq!(e.run("bob", "DEL k"), err("not_found"));
        assert_eq!(e.run("alice", "GET k"), val("original"));
    }

    #[test]
    fn unknown_user_gets_no_grant() {
        let mut e = Env::new();
        e.run("alice", "SET k v");
        assert_eq!(e.run("alice", "SHARE k ghost"), err("no_such_user"));
        e.st.add_user("ghost", "tok-ghost").unwrap();
        assert_eq!(e.run("ghost", "GET k alice"), err("not_found"));
    }

    #[test]
    fn grant_ends_when_key_is_deleted() {
        let mut e = Env::new();
        e.run("alice", "SET k v1");
        e.run("alice", "SHARE k bob");
        assert_eq!(e.run("bob", "GET k alice"), val("v1"));
        assert_eq!(e.run("alice", "DEL k"), Response::Ok);
        assert_eq!(e.run("bob", "GET k alice"), err("not_found"));
        e.run("alice", "SET k v2");
        assert_eq!(e.run("bob", "GET k alice"), err("not_found"));
    }

    #[test]
    fn overwrite_keeps_grant_and_grant_is_per_key() {
        let mut e = Env::new();
        e.run("alice", "SET k v1");
        e.run("alice", "SET other o");
        e.run("alice", "SHARE k bob");
        e.run("alice", "SET k v2");
        assert_eq!(e.run("bob", "GET k alice"), val("v2"));
        assert_eq!(e.run("bob", "GET other alice"), err("not_found"));
    }

    #[test]
    fn requires_valid_token_and_odd_owner_names_are_safe() {
        let mut e = Env::new();
        e.run("alice", "SET k v");
        e.run("alice", "SHARE k bob");
        assert_eq!(handle(&mut e.st, "wrong", "GET k alice"), err("auth"));
        assert_eq!(handle(&mut e.st, "tok-bob", "GET k alice"), val("v"));
        assert_eq!(e.run("bob", "GET k Alice"), err("not_found"));
        assert!(is_err(&e.run("bob", "GET k ../alice")));
        assert!(is_err(&e.run("bob", &format!("GET k {}", "a".repeat(5000)))));
        assert!(is_err(&e.run("bob", "GET k é")));
        assert!(is_err(&e.run("alice", "SHARE k ../bob")));
        assert!(is_err(&e.run("alice", "SHARE k BOB")));
    }
}

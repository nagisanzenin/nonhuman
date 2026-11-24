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
    fn snapshot_then_load_restores() {
        let mut e = Env::new();
        e.run("alice", "SET a 1");
        e.run("alice", "SET b two words");
        assert_eq!(e.run("alice", "SNAPSHOT s"), Response::Int(2));
        e.run("alice", "SET c 3");
        e.run("alice", "DEL a");
        e.run("alice", "SET b changed");
        assert_eq!(e.run("alice", "LOAD s"), Response::Int(2));
        assert_eq!(e.run("alice", "GET a"), val("1"));
        assert_eq!(e.run("alice", "GET b"), val("two words"));
        assert_eq!(e.run("alice", "GET c"), err("not_found"));
    }

    #[test]
    fn snapshot_survives_new_state_with_same_root() {
        let mut e = Env::new();
        e.run("alice", "SET k persisted");
        assert_eq!(e.run("alice", "SNAPSHOT keep.snap"), Response::Int(1));
        let mut st2 = State::new(e.root());
        st2.add_user("alice", "tok-alice").unwrap();
        assert_eq!(handle(&mut st2, "tok-alice", "GET k"), err("not_found"));
        assert_eq!(handle(&mut st2, "tok-alice", "LOAD keep.snap"), Response::Int(1));
        assert_eq!(handle(&mut st2, "tok-alice", "GET k"), val("persisted"));
    }

    #[test]
    fn later_snapshot_replaces_earlier_one() {
        let mut e = Env::new();
        e.run("alice", "SET k old");
        e.run("alice", "SNAPSHOT s");
        e.run("alice", "SET k new");
        e.run("alice", "SET j 2");
        assert_eq!(e.run("alice", "SNAPSHOT s"), Response::Int(2));
        e.run("alice", "DEL k");
        assert_eq!(e.run("alice", "LOAD s"), Response::Int(2));
        assert_eq!(e.run("alice", "GET k"), val("new"));
    }

    #[test]
    fn empty_namespace_roundtrip() {
        let mut e = Env::new();
        assert_eq!(e.run("alice", "SNAPSHOT empty"), Response::Int(0));
        e.run("alice", "SET x 1");
        assert_eq!(e.run("alice", "LOAD empty"), Response::Int(0));
        assert_eq!(e.run("alice", "GET x"), err("not_found"));
    }

    #[test]
    fn load_missing_snapshot() {
        let mut e = Env::new();
        assert_eq!(e.run("alice", "LOAD nothing"), err("not_found"));
    }

    #[test]
    fn argument_errors() {
        let mut e = Env::new();
        assert_eq!(e.run("alice", "SNAPSHOT"), err("bad_args"));
        assert_eq!(e.run("alice", "LOAD"), err("bad_args"));
        assert_eq!(e.run("alice", "LOAD a b"), err("bad_args"));
        assert_eq!(e.run("alice", "SNAPSHOT a b"), err("bad_args"));
    }

    #[test]
    fn name_length_limit() {
        let mut e = Env::new();
        let ok = "n".repeat(64);
        let long = "n".repeat(65);
        assert_eq!(e.run("alice", &format!("SNAPSHOT {ok}")), Response::Int(0));
        assert_eq!(e.run("alice", &format!("SNAPSHOT {long}")), err("bad_name"));
        assert_eq!(e.run("alice", &format!("LOAD {long}")), err("bad_name"));
    }
}

mod security {
    use super::*;

    #[test]
    fn traversal_and_absolute_names_are_rejected() {
        let mut e = Env::new();
        e.run("alice", "SET k v");
        assert_eq!(e.run("alice", "SNAPSHOT ok"), Response::Int(1));
        let abs = format!("{}/evil_abs", e.base.display());
        let bad_names = vec![
            "..".to_string(),
            ".".to_string(),
            "../evil_a".to_string(),
            "../../evil_b".to_string(),
            "../../../evil_c".to_string(),
            "../../../../../../../../tmp/evil_d".to_string(),
            "/tmp/evil_e".to_string(),
            abs,
            "sub/evil_f".to_string(),
            "alice/ok".to_string(),
            "..\\evil_g".to_string(),
            "a\\b".to_string(),
            "a\u{0}b".to_string(),
            "./evil_h".to_string(),
        ];
        for n in &bad_names {
            assert_eq!(e.run("alice", &format!("SNAPSHOT {n}")), err("bad_name"), "SNAPSHOT {n:?}");
            assert_eq!(e.run("alice", &format!("LOAD {n}")), err("bad_name"), "LOAD {n:?}");
        }
        // Nothing may have been created outside (or beside) the snapshot area.
        let mut direct = Vec::new();
        for d in [e.base.clone(), e.base.parent().unwrap().to_path_buf(), e.root()] {
            if let Ok(rd) = std::fs::read_dir(&d) {
                for ent in rd.flatten() {
                    let n = ent.file_name().to_string_lossy().to_string();
                    if n.starts_with("evil") {
                        direct.push(ent.path());
                    }
                }
            }
        }
        assert!(direct.is_empty(), "files escaped: {direct:?}");
        let top: Vec<_> = std::fs::read_dir(&e.base)
            .unwrap()
            .flatten()
            .map(|x| x.file_name().to_string_lossy().to_string())
            .collect();
        assert_eq!(top, vec!["root".to_string()]);
        assert!(!Path::new("/tmp/evil_d").exists() && !Path::new("/tmp/evil_e").exists());
    }

    #[test]
    fn cannot_load_another_users_snapshot() {
        let mut e = Env::new();
        e.run("alice", "SET secret top");
        assert_eq!(e.run("alice", "SNAPSHOT s"), Response::Int(1));
        e.run("bob", "SET mine 1");
        assert_eq!(e.run("bob", "LOAD s"), err("not_found"));
        assert_eq!(e.run("bob", "GET secret"), err("not_found"));
        assert_eq!(e.run("bob", "GET mine"), val("1"));
        for name in ["../alice/s", "alice/s", "../alice/s.snap", "..%2Falice%2Fs"] {
            let r = e.run("bob", &format!("LOAD {name}"));
            assert!(is_err(&r), "LOAD {name:?} gave {r:?}");
        }
        assert_eq!(e.run("bob", "GET secret"), err("not_found"));
    }

    #[test]
    fn same_name_does_not_collide_between_users() {
        let mut e = Env::new();
        e.run("alice", "SET who alice");
        assert_eq!(e.run("alice", "SNAPSHOT s"), Response::Int(1));
        e.run("bob", "SET who bob");
        assert_eq!(e.run("bob", "SNAPSHOT s"), Response::Int(1));
        e.run("alice", "SET who changed");
        e.run("bob", "SET who changed");
        assert_eq!(e.run("alice", "LOAD s"), Response::Int(1));
        assert_eq!(e.run("bob", "LOAD s"), Response::Int(1));
        assert_eq!(e.run("alice", "GET who"), val("alice"));
        assert_eq!(e.run("bob", "GET who"), val("bob"));
    }

    #[test]
    fn corrupt_snapshot_is_an_error_and_changes_nothing() {
        let garbage: [&[u8]; 4] = [
            b"no_value_here\n",
            &[0xff, 0xfe, 0xfd, 0x00],
            b"bad/key value\n",
            b"k v\nstill_broken\n",
        ];
        for g in garbage {
            let mut e = Env::new();
            e.run("alice", "SET a 1");
            assert_eq!(e.run("alice", "SNAPSHOT s"), Response::Int(1));
            let mut files = Vec::new();
            files_under(&e.root(), &mut files);
            assert!(!files.is_empty());
            for f in &files {
                std::fs::write(f, g).unwrap();
            }
            e.run("alice", "SET b 2");
            let r = e.run("alice", "LOAD s");
            assert!(is_err(&r), "garbage {g:?} gave {r:?}");
            assert_eq!(e.run("alice", "GET a"), val("1"));
            assert_eq!(e.run("alice", "GET b"), val("2"));
        }
    }

    #[test]
    fn oversized_snapshot_content_is_rejected() {
        let mut e = Env::new();
        e.run("alice", "SET a 1");
        assert_eq!(e.run("alice", "SNAPSHOT s"), Response::Int(1));
        let mut files = Vec::new();
        files_under(&e.root(), &mut files);
        assert!(!files.is_empty());
        let mut content = String::new();
        for i in 0..500 {
            content.push_str(&format!("key{i} v\n"));
        }
        for f in &files {
            std::fs::write(f, &content).unwrap();
        }
        let r = e.run("alice", "LOAD s");
        assert!(is_err(&r), "too many keys loaded: {r:?}");
        assert_eq!(e.run("alice", "GET a"), val("1"));
        let long = "v".repeat(5000);
        for f in &files {
            std::fs::write(f, format!("a {long}\n")).unwrap();
        }
        let r = e.run("alice", "LOAD s");
        assert!(is_err(&r), "oversized value loaded: {r:?}");
        assert_eq!(e.run("alice", "GET a"), val("1"));
    }
}

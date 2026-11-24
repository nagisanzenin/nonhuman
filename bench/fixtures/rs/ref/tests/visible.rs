//! Visible tests for the base feature set (SET / GET / DEL).

use kvstore::{handle, Response, State};

fn setup() -> (State, std::path::PathBuf) {
    let root = std::env::temp_dir().join(format!(
        "kvstore-visible-{}-{:?}",
        std::process::id(),
        std::thread::current().id()
    ));
    std::fs::create_dir_all(&root).unwrap();
    let mut st = State::new(&root);
    st.add_user("alice", "tok-alice").unwrap();
    st.add_user("bob", "tok-bob").unwrap();
    (st, root)
}

fn run(st: &mut State, who: &str, line: &str) -> Response {
    handle(st, &format!("tok-{who}"), line)
}

#[test]
fn set_get_del_roundtrip() {
    let (mut st, root) = setup();
    assert_eq!(run(&mut st, "alice", "SET color dark red"), Response::Ok);
    assert_eq!(run(&mut st, "alice", "GET color"), Response::Value("dark red".into()));
    assert_eq!(run(&mut st, "alice", "DEL color"), Response::Ok);
    assert_eq!(run(&mut st, "alice", "GET color"), Response::err("not_found"));
    let _ = std::fs::remove_dir_all(root);
}

#[test]
fn overwrite_replaces_value() {
    let (mut st, root) = setup();
    run(&mut st, "alice", "SET k 1");
    run(&mut st, "alice", "SET k 2");
    assert_eq!(run(&mut st, "alice", "GET k"), Response::Value("2".into()));
    let _ = std::fs::remove_dir_all(root);
}

#[test]
fn users_are_isolated() {
    let (mut st, root) = setup();
    run(&mut st, "alice", "SET k secret");
    assert_eq!(run(&mut st, "bob", "GET k"), Response::err("not_found"));
    assert_eq!(run(&mut st, "bob", "DEL k"), Response::err("not_found"));
    assert_eq!(run(&mut st, "alice", "GET k"), Response::Value("secret".into()));
    let _ = std::fs::remove_dir_all(root);
}

#[test]
fn bad_token_is_rejected() {
    let (mut st, root) = setup();
    assert_eq!(handle(&mut st, "nope", "GET k"), Response::err("auth"));
    assert_eq!(handle(&mut st, "", "GET k"), Response::err("auth"));
    let _ = std::fs::remove_dir_all(root);
}

#[test]
fn parse_errors_are_reported() {
    let (mut st, root) = setup();
    assert_eq!(run(&mut st, "alice", ""), Response::err("empty"));
    assert_eq!(run(&mut st, "alice", "FLY away"), Response::err("unknown_command"));
    assert_eq!(run(&mut st, "alice", "GET"), Response::err("bad_args"));
    assert_eq!(run(&mut st, "alice", "SET k"), Response::err("bad_args"));
    assert_eq!(run(&mut st, "alice", "GET a/b"), Response::err("bad_key"));
    let _ = std::fs::remove_dir_all(root);
}

#[test]
fn length_limits_are_enforced() {
    let (mut st, root) = setup();
    let key = "k".repeat(65);
    assert_eq!(run(&mut st, "alice", &format!("SET {key} v")), Response::err("key_too_long"));
    let val = "v".repeat(257);
    assert_eq!(run(&mut st, "alice", &format!("SET k {val}")), Response::err("value_too_long"));
    let ok_val = "v".repeat(256);
    assert_eq!(run(&mut st, "alice", &format!("SET k {ok_val}")), Response::Ok);
    let _ = std::fs::remove_dir_all(root);
}

#[test]
fn key_cap_is_enforced() {
    let (mut st, root) = setup();
    for i in 0..100 {
        assert_eq!(run(&mut st, "alice", &format!("SET k{i} v")), Response::Ok);
    }
    assert_eq!(run(&mut st, "alice", "SET extra v"), Response::err("full"));
    assert_eq!(run(&mut st, "alice", "SET k0 w"), Response::Ok);
    assert_eq!(run(&mut st, "bob", "SET extra v"), Response::Ok);
    let _ = std::fs::remove_dir_all(root);
}

#[test]
fn response_lines() {
    assert_eq!(Response::Ok.to_line(), "OK");
    assert_eq!(Response::Int(-3).to_line(), "INT -3");
    assert_eq!(Response::List(vec!["a".into(), "b".into()]).to_line(), "KEYS a b");
    assert_eq!(Response::err("x").to_line(), "ERR x");
}

//! `kvstore`: a small in-memory key/value store with users and ACLs, plus
//! file-backed helpers rooted at a directory.
//!
//! The public entry point is [`handle`]: it takes a token and one protocol
//! line and returns a [`Response`]. Each user owns a private namespace; keys
//! are only ever read or written inside the caller's own namespace unless a
//! command explicitly says otherwise.

pub mod auth;
pub mod fs;
pub mod parse;
pub mod store;

use std::collections::BTreeMap;
use std::path::PathBuf;

pub use auth::{Auth, AuthError};
pub use parse::{parse_command, Command, ParseError};
pub use store::{Store, StoreError};

/// Result of handling one request.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Response {
    /// Success with nothing to return.
    Ok,
    /// A single text value.
    Value(String),
    /// A list of keys.
    List(Vec<String>),
    /// An integer result.
    Int(i64),
    /// Failure. The text is always `ERR <code>`, for example `ERR not_found`.
    Err(String),
}

impl Response {
    /// Builds `Response::Err("ERR <code>")`.
    pub fn err(code: &str) -> Response {
        Response::Err(format!("ERR {code}"))
    }

    /// True for [`Response::Err`].
    pub fn is_err(&self) -> bool {
        matches!(self, Response::Err(_))
    }

    /// Renders the response as a single protocol line.
    pub fn to_line(&self) -> String {
        match self {
            Response::Ok => "OK".to_string(),
            Response::Value(v) => format!("VALUE {v}"),
            Response::List(keys) => format!("KEYS {}", keys.join(" ")),
            Response::Int(n) => format!("INT {n}"),
            Response::Err(e) => e.clone(),
        }
    }
}

/// Everything the dispatcher needs: data, users, and the snapshot root.
#[derive(Debug)]
pub struct State {
    /// Key/value data, one namespace per user.
    pub store: Store,
    /// Registered users and tokens.
    pub auth: Auth,
    /// Directory under which file-backed features keep their files.
    pub root: PathBuf,
}

impl State {
    /// Creates empty state whose file-backed data lives under `root`.
    pub fn new(root: impl Into<PathBuf>) -> State {
        State { store: Store::new(), auth: Auth::new(), root: root.into() }
    }

    /// Registers a user. See [`Auth::add_user`] for the accepted formats.
    pub fn add_user(&mut self, name: &str, token: &str) -> Result<(), AuthError> {
        self.auth.add_user(name, token)
    }
}

/// Handler result: a response or an error code that becomes `ERR <code>`.
type Reply = Result<Response, &'static str>;

/// Authenticates `user_token`, parses `line` and executes the command.
///
/// Never panics on malformed input; every failure is reported as
/// [`Response::Err`].
pub fn handle(state: &mut State, user_token: &str, line: &str) -> Response {
    let user = match state.auth.authenticate(user_token) {
        Some(u) => u.to_string(),
        None => return Response::err("auth"),
    };
    let cmd = match parse_command(line) {
        Ok(c) => c,
        Err(e) => return Response::err(e.code()),
    };
    let reply = match cmd {
        Command::Set { key, value } => cmd_set(state, &user, &key, &value),
        Command::Get { key, owner } => cmd_get(state, &user, &key, owner.as_deref()),
        Command::Del { key } => cmd_del(state, &user, &key),
        Command::Scan { prefix, limit } => cmd_scan(state, &user, &prefix, limit),
        Command::Snapshot { name } => cmd_snapshot(state, &user, &name),
        Command::Load { name } => cmd_load(state, &user, &name),
        Command::Incr { key, by } => cmd_incr(state, &user, &key, by),
        Command::Share { key, user: target } => cmd_share(state, &user, &key, &target),
        Command::MSet { pairs } => cmd_mset(state, &user, &pairs),
    };
    reply.unwrap_or_else(Response::err)
}

fn cmd_set(state: &mut State, user: &str, key: &str, value: &str) -> Reply {
    auth::require_owner(user, user).map_err(|e| e.code())?;
    state.store.namespace_mut(user).set(key, value).map_err(|e| e.code())?;
    Ok(Response::Ok)
}

/// `GET key` reads the caller's own key. `GET key owner` reads `owner`'s key
/// when it is the caller's own or has been shared with the caller. Every
/// failure looks the same (`not_found`) so existence is not revealed.
fn cmd_get(state: &State, user: &str, key: &str, owner: Option<&str>) -> Reply {
    let owner = owner.unwrap_or(user);
    let entry = state
        .store
        .namespace(owner)
        .and_then(|ns| ns.get(key))
        .filter(|e| owner == user || e.can_read(user));
    match entry {
        Some(e) => Ok(Response::Value(e.value.clone())),
        None => Err("not_found"),
    }
}

fn cmd_del(state: &mut State, user: &str, key: &str) -> Reply {
    auth::require_owner(user, user).map_err(|e| e.code())?;
    if state.store.namespace_mut(user).remove(key) {
        Ok(Response::Ok)
    } else {
        Err("not_found")
    }
}

fn cmd_scan(state: &State, user: &str, prefix: &str, limit: Option<usize>) -> Reply {
    let all = prefix == "*";
    let keys: Vec<String> = match state.store.namespace(user) {
        Some(ns) => ns
            .keys()
            .filter(|k| all || k.starts_with(prefix))
            .take(limit.unwrap_or(usize::MAX))
            .map(|k| k.to_string())
            .collect(),
        None => Vec::new(),
    };
    Ok(Response::List(keys))
}

fn cmd_snapshot(state: &State, user: &str, name: &str) -> Reply {
    let rel = fs::snapshot_rel(user, name).map_err(|e| e.code())?;
    let mut out = String::new();
    let mut count = 0i64;
    if let Some(ns) = state.store.namespace(user) {
        for (key, entry) in ns.iter() {
            out.push_str(key);
            out.push(' ');
            out.push_str(&entry.value);
            out.push('\n');
            count += 1;
        }
    }
    fs::write_file(&state.root, &rel, &out).map_err(|e| e.code())?;
    Ok(Response::Int(count))
}

fn cmd_load(state: &mut State, user: &str, name: &str) -> Reply {
    let rel = fs::snapshot_rel(user, name).map_err(|e| e.code())?;
    let text = fs::read_file(&state.root, &rel).map_err(|e| e.code())?;
    let mut entries = BTreeMap::new();
    for line in text.lines() {
        let (key, value) = line.split_once(' ').ok_or("corrupt")?;
        if value.is_empty() {
            return Err("corrupt");
        }
        parse::validate_key(key).map_err(|_| "corrupt")?;
        parse::validate_value(value).map_err(|_| "corrupt")?;
        entries.insert(key.to_string(), value.to_string());
    }
    let count = entries.len() as i64;
    state.store.namespace_mut(user).replace_all(entries).map_err(|_| "corrupt")?;
    Ok(Response::Int(count))
}

fn cmd_incr(state: &mut State, user: &str, key: &str, by: i64) -> Reply {
    auth::require_owner(user, user).map_err(|e| e.code())?;
    let current = match state.store.namespace(user).and_then(|ns| ns.get(key)) {
        Some(e) => parse::parse_int(&e.value).ok_or("not_integer")?,
        None => 0,
    };
    let next = current.checked_add(by).ok_or("overflow")?;
    state
        .store
        .namespace_mut(user)
        .set(key, &next.to_string())
        .map_err(|e| e.code())?;
    Ok(Response::Int(next))
}

fn cmd_share(state: &mut State, user: &str, key: &str, target: &str) -> Reply {
    auth::require_owner(user, user).map_err(|e| e.code())?;
    if state.store.namespace(user).and_then(|ns| ns.get(key)).is_none() {
        return Err("not_found");
    }
    if !state.auth.has_user(target) {
        return Err("no_such_user");
    }
    if target == user {
        return Err("bad_user");
    }
    state.store.namespace_mut(user).grant(key, target).map_err(|e| e.code())?;
    Ok(Response::Ok)
}

fn cmd_mset(state: &mut State, user: &str, pairs: &[(String, String)]) -> Reply {
    auth::require_owner(user, user).map_err(|e| e.code())?;
    state.store.namespace_mut(user).set_many(pairs).map_err(|e| e.code())?;
    Ok(Response::Ok)
}

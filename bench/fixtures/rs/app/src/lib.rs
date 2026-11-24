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
        Command::Get { key } => cmd_get(state, &user, &key),
        Command::Del { key } => cmd_del(state, &user, &key),
    };
    reply.unwrap_or_else(Response::err)
}

fn cmd_set(state: &mut State, user: &str, key: &str, value: &str) -> Reply {
    auth::require_owner(user, user).map_err(|e| e.code())?;
    state.store.namespace_mut(user).set(key, value).map_err(|e| e.code())?;
    Ok(Response::Ok)
}

fn cmd_get(state: &State, user: &str, key: &str) -> Reply {
    let entry = state.store.namespace(user).and_then(|ns| ns.get(key));
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

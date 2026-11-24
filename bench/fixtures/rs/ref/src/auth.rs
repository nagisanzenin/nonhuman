//! Users and token authentication.
//!
//! Every request carries an opaque token. [`Auth`] maps tokens to user names;
//! the user name doubles as the name of the user's namespace in the store.

use std::collections::{HashMap, HashSet};
use std::fmt;

/// Maximum length of a user name, in bytes.
pub const MAX_USER_LEN: usize = 32;
/// Maximum length of a token, in bytes.
pub const MAX_TOKEN_LEN: usize = 128;

/// Errors produced by the auth layer.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AuthError {
    /// The user name is empty, too long, or has characters outside `[A-Za-z0-9_]`.
    InvalidUser,
    /// The token is empty, too long, or contains whitespace.
    InvalidToken,
    /// A user or token with that value is already registered.
    Duplicate,
    /// The caller is not the owner of the resource.
    Forbidden,
}

impl AuthError {
    /// Short machine-readable code used in `ERR <code>` responses.
    pub fn code(&self) -> &'static str {
        match self {
            AuthError::InvalidUser => "invalid_user",
            AuthError::InvalidToken => "invalid_token",
            AuthError::Duplicate => "duplicate",
            AuthError::Forbidden => "forbidden",
        }
    }
}

impl fmt::Display for AuthError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.code())
    }
}

/// Registry of users and their tokens.
#[derive(Debug, Default)]
pub struct Auth {
    by_token: HashMap<String, String>,
    users: HashSet<String>,
}

impl Auth {
    /// Creates an empty registry.
    pub fn new() -> Auth {
        Auth::default()
    }

    /// Registers `name` with `token`.
    ///
    /// User names are 1..=[`MAX_USER_LEN`] ASCII alphanumeric or `_` characters.
    /// Tokens are 1..=[`MAX_TOKEN_LEN`] bytes without whitespace.
    pub fn add_user(&mut self, name: &str, token: &str) -> Result<(), AuthError> {
        let name_ok = !name.is_empty()
            && name.len() <= MAX_USER_LEN
            && name.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'_');
        if !name_ok {
            return Err(AuthError::InvalidUser);
        }
        let token_ok = !token.is_empty()
            && token.len() <= MAX_TOKEN_LEN
            && !token.chars().any(|c| c.is_whitespace() || c.is_control());
        if !token_ok {
            return Err(AuthError::InvalidToken);
        }
        if self.users.contains(name) || self.by_token.contains_key(token) {
            return Err(AuthError::Duplicate);
        }
        self.users.insert(name.to_string());
        self.by_token.insert(token.to_string(), name.to_string());
        Ok(())
    }

    /// Returns the user name that owns `token`, if the token is known.
    pub fn authenticate(&self, token: &str) -> Option<&str> {
        self.by_token.get(token).map(|s| s.as_str())
    }

    /// Returns true when `name` is a registered user.
    pub fn has_user(&self, name: &str) -> bool {
        self.users.contains(name)
    }

    /// Number of registered users.
    pub fn user_count(&self) -> usize {
        self.users.len()
    }
}

/// Succeeds only when `caller` is the owner of the namespace `owner`.
///
/// Use this before any operation that mutates a namespace so that a request
/// can never act on data belonging to somebody else.
pub fn require_owner(caller: &str, owner: &str) -> Result<(), AuthError> {
    if caller == owner {
        Ok(())
    } else {
        Err(AuthError::Forbidden)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn add_and_authenticate() {
        let mut a = Auth::new();
        a.add_user("alice", "t1").unwrap();
        assert_eq!(a.authenticate("t1"), Some("alice"));
        assert_eq!(a.authenticate("t2"), None);
        assert!(a.has_user("alice"));
        assert!(!a.has_user("bob"));
    }

    #[test]
    fn rejects_bad_input() {
        let mut a = Auth::new();
        assert_eq!(a.add_user("", "t"), Err(AuthError::InvalidUser));
        assert_eq!(a.add_user("a/b", "t"), Err(AuthError::InvalidUser));
        assert_eq!(a.add_user("a", ""), Err(AuthError::InvalidToken));
        a.add_user("a", "t").unwrap();
        assert_eq!(a.add_user("a", "u"), Err(AuthError::Duplicate));
        assert_eq!(a.add_user("b", "t"), Err(AuthError::Duplicate));
    }

    #[test]
    fn owner_check() {
        assert!(require_owner("a", "a").is_ok());
        assert_eq!(require_owner("a", "b"), Err(AuthError::Forbidden));
    }
}

//! In-memory storage: a map of namespaces, each holding sorted entries.
//!
//! A namespace is owned by exactly one user (the namespace name is the user
//! name). Entries carry a `readers` set: users, other than the owner, that the
//! owner has granted read access to.

use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::fmt;

/// Maximum number of keys a single namespace may hold.
pub const MAX_KEYS_PER_NS: usize = 100;

/// Errors produced by the store.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StoreError {
    /// The namespace already holds [`MAX_KEYS_PER_NS`] keys.
    Full,
    /// The key does not exist.
    NotFound,
}

impl StoreError {
    /// Short machine-readable code used in `ERR <code>` responses.
    pub fn code(&self) -> &'static str {
        match self {
            StoreError::Full => "full",
            StoreError::NotFound => "not_found",
        }
    }
}

impl fmt::Display for StoreError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.code())
    }
}

/// One stored value together with its read ACL.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Entry {
    /// The stored text.
    pub value: String,
    /// Users (besides the owner) allowed to read this entry.
    pub readers: BTreeSet<String>,
}

impl Entry {
    /// Creates an entry with no extra readers.
    pub fn new(value: &str) -> Entry {
        Entry { value: value.to_string(), readers: BTreeSet::new() }
    }

    /// True when `user` has been granted read access.
    pub fn can_read(&self, user: &str) -> bool {
        self.readers.contains(user)
    }
}

/// All entries owned by one user, ordered by key.
#[derive(Debug, Clone, Default)]
pub struct Namespace {
    entries: BTreeMap<String, Entry>,
}

impl Namespace {
    /// Number of keys.
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    /// True when there are no keys.
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    /// Looks up an entry.
    pub fn get(&self, key: &str) -> Option<&Entry> {
        self.entries.get(key)
    }

    /// Iterates over keys in ascending order.
    pub fn keys(&self) -> impl Iterator<Item = &str> {
        self.entries.keys().map(|k| k.as_str())
    }

    /// Iterates over `(key, entry)` pairs in ascending key order.
    pub fn iter(&self) -> impl Iterator<Item = (&str, &Entry)> {
        self.entries.iter().map(|(k, e)| (k.as_str(), e))
    }

    /// Sets `key` to `value`. Overwriting keeps the existing ACL.
    /// Creating a new key fails with [`StoreError::Full`] at the cap.
    pub fn set(&mut self, key: &str, value: &str) -> Result<(), StoreError> {
        if let Some(e) = self.entries.get_mut(key) {
            e.value = value.to_string();
            return Ok(());
        }
        if self.entries.len() >= MAX_KEYS_PER_NS {
            return Err(StoreError::Full);
        }
        self.entries.insert(key.to_string(), Entry::new(value));
        Ok(())
    }

    /// Removes `key` together with its ACL. Returns false when it was absent.
    pub fn remove(&mut self, key: &str) -> bool {
        self.entries.remove(key).is_some()
    }

    /// Adds `user` to the readers of `key`.
    pub fn grant(&mut self, key: &str, user: &str) -> Result<(), StoreError> {
        match self.entries.get_mut(key) {
            Some(e) => {
                e.readers.insert(user.to_string());
                Ok(())
            }
            None => Err(StoreError::NotFound),
        }
    }
}

/// Map of namespace name to namespace.
#[derive(Debug, Default)]
pub struct Store {
    namespaces: HashMap<String, Namespace>,
}

impl Store {
    /// Creates an empty store.
    pub fn new() -> Store {
        Store::default()
    }

    /// Read-only access to a namespace, if it has ever been written.
    pub fn namespace(&self, ns: &str) -> Option<&Namespace> {
        self.namespaces.get(ns)
    }

    /// Mutable access to a namespace, creating it when missing.
    pub fn namespace_mut(&mut self, ns: &str) -> &mut Namespace {
        self.namespaces.entry(ns.to_string()).or_default()
    }

    /// Total number of keys across all namespaces.
    pub fn total_keys(&self) -> usize {
        self.namespaces.values().map(|n| n.len()).sum()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn set_get_remove() {
        let mut s = Store::new();
        s.namespace_mut("a").set("k", "v").unwrap();
        assert_eq!(s.namespace("a").unwrap().get("k").unwrap().value, "v");
        assert!(s.namespace("b").is_none());
        assert!(s.namespace_mut("a").remove("k"));
        assert!(!s.namespace_mut("a").remove("k"));
    }

    #[test]
    fn cap_applies_to_new_keys_only() {
        let mut n = Namespace::default();
        for i in 0..MAX_KEYS_PER_NS {
            n.set(&format!("k{i}"), "v").unwrap();
        }
        assert_eq!(n.set("extra", "v"), Err(StoreError::Full));
        assert!(n.set("k0", "w").is_ok());
    }

    #[test]
    fn overwrite_keeps_acl() {
        let mut n = Namespace::default();
        n.set("k", "1").unwrap();
        n.grant("k", "bob").unwrap();
        n.set("k", "2").unwrap();
        assert!(n.get("k").unwrap().can_read("bob"));
        assert_eq!(n.grant("zz", "bob"), Err(StoreError::NotFound));
    }
}

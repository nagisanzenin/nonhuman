//! Line-protocol parser.
//!
//! A request is one line of text: a verb followed by arguments separated by
//! whitespace. Verbs are case-insensitive. `SET` takes the rest of the line
//! as its value, so values may contain spaces.
//!
//! All size limits live here so every command shares them:
//! [`MAX_LINE_LEN`], [`MAX_KEY_LEN`] and [`MAX_VALUE_LEN`]. Use
//! [`validate_key`] and [`validate_value`] on anything that will be stored.

use std::fmt;

/// Maximum length of a whole request line, in bytes.
pub const MAX_LINE_LEN: usize = 1024;
/// Maximum length of a key, in bytes.
pub const MAX_KEY_LEN: usize = 64;
/// Maximum length of a value, in bytes.
pub const MAX_VALUE_LEN: usize = 256;
/// Largest accepted `SCAN` limit.
pub const MAX_SCAN_LIMIT: u64 = 1_000_000;

/// A parsed request.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Command {
    /// `SET <key> <value...>`
    Set { key: String, value: String },
    /// `GET <key> [owner]`; with `owner`, reads a key another user shared.
    Get { key: String, owner: Option<String> },
    /// `DEL <key>`
    Del { key: String },
    /// `SCAN <prefix> [limit]`; a prefix of `*` matches every key.
    Scan { prefix: String, limit: Option<usize> },
    /// `SNAPSHOT <name>`
    Snapshot { name: String },
    /// `LOAD <name>`
    Load { name: String },
    /// `INCR <key> [by]`
    Incr { key: String, by: i64 },
    /// `SHARE <key> <user>`
    Share { key: String, user: String },
    /// `MSET <k1> <v1> [<k2> <v2> ...]`
    MSet { pairs: Vec<(String, String)> },
}

/// Why a line could not be parsed.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ParseError {
    /// The line is blank.
    Empty,
    /// The line is longer than [`MAX_LINE_LEN`].
    LineTooLong,
    /// The verb is not recognised.
    UnknownCommand,
    /// Too few or too many arguments for the verb.
    WrongArgCount,
    /// The key is empty or contains characters outside `[A-Za-z0-9_.:-]`.
    BadKey,
    /// The key is longer than [`MAX_KEY_LEN`].
    KeyTooLong,
    /// The value contains control characters.
    BadValue,
    /// The value is longer than [`MAX_VALUE_LEN`].
    ValueTooLong,
    /// The `SCAN` limit is not a whole number in `0..=MAX_SCAN_LIMIT`.
    BadLimit,
    /// The `INCR` increment is not a signed 64-bit decimal integer.
    BadBy,
}

impl ParseError {
    /// Short machine-readable code used in `ERR <code>` responses.
    pub fn code(&self) -> &'static str {
        match self {
            ParseError::Empty => "empty",
            ParseError::LineTooLong => "line_too_long",
            ParseError::UnknownCommand => "unknown_command",
            ParseError::WrongArgCount => "bad_args",
            ParseError::BadKey => "bad_key",
            ParseError::KeyTooLong => "key_too_long",
            ParseError::BadValue => "bad_value",
            ParseError::ValueTooLong => "value_too_long",
            ParseError::BadLimit => "bad_limit",
            ParseError::BadBy => "bad_by",
        }
    }
}

impl fmt::Display for ParseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.code())
    }
}

fn is_key_byte(b: u8) -> bool {
    b.is_ascii_alphanumeric() || matches!(b, b'_' | b'.' | b':' | b'-')
}

/// Checks that `key` is a legal key: 1..=[`MAX_KEY_LEN`] bytes of `[A-Za-z0-9_.:-]`.
pub fn validate_key(key: &str) -> Result<(), ParseError> {
    if key.is_empty() {
        return Err(ParseError::BadKey);
    }
    if key.len() > MAX_KEY_LEN {
        return Err(ParseError::KeyTooLong);
    }
    if !key.bytes().all(is_key_byte) {
        return Err(ParseError::BadKey);
    }
    Ok(())
}

/// Checks that `value` is at most [`MAX_VALUE_LEN`] bytes with no control characters.
pub fn validate_value(value: &str) -> Result<(), ParseError> {
    if value.len() > MAX_VALUE_LEN {
        return Err(ParseError::ValueTooLong);
    }
    if value.chars().any(|c| c.is_control()) {
        return Err(ParseError::BadValue);
    }
    Ok(())
}

/// Parses a signed 64-bit decimal integer: optional `-`, then digits.
/// Returns `None` for anything else (including a leading `+`) or on overflow.
pub fn parse_int(s: &str) -> Option<i64> {
    if s.starts_with('+') {
        return None;
    }
    s.parse::<i64>().ok()
}

fn parse_limit(s: &str) -> Result<usize, ParseError> {
    if s.is_empty() || !s.bytes().all(|b| b.is_ascii_digit()) {
        return Err(ParseError::BadLimit);
    }
    match s.parse::<u64>() {
        Ok(n) if n <= MAX_SCAN_LIMIT => Ok(n as usize),
        _ => Err(ParseError::BadLimit),
    }
}

/// Splits off the first whitespace-delimited token; returns `(token, rest)`
/// where `rest` has its leading whitespace removed.
fn split_token(s: &str) -> (&str, &str) {
    let s = s.trim_start();
    match s.find(char::is_whitespace) {
        Some(i) => (&s[..i], s[i..].trim_start()),
        None => (s, ""),
    }
}

/// Parses one request line into a [`Command`].
pub fn parse_command(line: &str) -> Result<Command, ParseError> {
    let line = line.trim_end_matches(['\r', '\n']);
    if line.len() > MAX_LINE_LEN {
        return Err(ParseError::LineTooLong);
    }
    let line = line.trim();
    if line.is_empty() {
        return Err(ParseError::Empty);
    }
    let (verb, rest) = split_token(line);
    match verb.to_ascii_uppercase().as_str() {
        "SET" => {
            let (key, value) = split_token(rest);
            if key.is_empty() || value.is_empty() {
                return Err(ParseError::WrongArgCount);
            }
            validate_key(key)?;
            validate_value(value)?;
            Ok(Command::Set { key: key.to_string(), value: value.to_string() })
        }
        "GET" => {
            let args: Vec<&str> = rest.split_whitespace().collect();
            match args.as_slice() {
                [key] => {
                    validate_key(key)?;
                    Ok(Command::Get { key: key.to_string(), owner: None })
                }
                [key, owner] => {
                    validate_key(key)?;
                    Ok(Command::Get { key: key.to_string(), owner: Some(owner.to_string()) })
                }
                _ => Err(ParseError::WrongArgCount),
            }
        }
        "DEL" => {
            let key = single_arg(rest)?;
            Ok(Command::Del { key })
        }
        "SCAN" => {
            let args: Vec<&str> = rest.split_whitespace().collect();
            if args.is_empty() || args.len() > 2 {
                return Err(ParseError::WrongArgCount);
            }
            if args[0] != "*" {
                validate_key(args[0])?;
            }
            let limit = match args.get(1) {
                Some(l) => Some(parse_limit(l)?),
                None => None,
            };
            Ok(Command::Scan { prefix: args[0].to_string(), limit })
        }
        "SNAPSHOT" => Ok(Command::Snapshot { name: single_token(rest)? }),
        "LOAD" => Ok(Command::Load { name: single_token(rest)? }),
        "INCR" => {
            let args: Vec<&str> = rest.split_whitespace().collect();
            if args.is_empty() || args.len() > 2 {
                return Err(ParseError::WrongArgCount);
            }
            validate_key(args[0])?;
            let by = match args.get(1) {
                Some(b) => parse_int(b).ok_or(ParseError::BadBy)?,
                None => 1,
            };
            Ok(Command::Incr { key: args[0].to_string(), by })
        }
        "SHARE" => {
            let args: Vec<&str> = rest.split_whitespace().collect();
            if args.len() != 2 {
                return Err(ParseError::WrongArgCount);
            }
            validate_key(args[0])?;
            Ok(Command::Share { key: args[0].to_string(), user: args[1].to_string() })
        }
        "MSET" => {
            let args: Vec<&str> = rest.split_whitespace().collect();
            if args.is_empty() || args.len() % 2 != 0 {
                return Err(ParseError::WrongArgCount);
            }
            let mut pairs = Vec::with_capacity(args.len() / 2);
            for kv in args.chunks(2) {
                validate_key(kv[0])?;
                validate_value(kv[1])?;
                pairs.push((kv[0].to_string(), kv[1].to_string()));
            }
            Ok(Command::MSet { pairs })
        }
        _ => Err(ParseError::UnknownCommand),
    }
}

/// Parses `rest` as exactly one whitespace-free token (not validated further).
fn single_token(rest: &str) -> Result<String, ParseError> {
    let mut it = rest.split_whitespace();
    let tok = it.next().ok_or(ParseError::WrongArgCount)?;
    if it.next().is_some() {
        return Err(ParseError::WrongArgCount);
    }
    Ok(tok.to_string())
}

/// Parses `rest` as exactly one valid key.
fn single_arg(rest: &str) -> Result<String, ParseError> {
    let mut it = rest.split_whitespace();
    let key = it.next().ok_or(ParseError::WrongArgCount)?;
    if it.next().is_some() {
        return Err(ParseError::WrongArgCount);
    }
    validate_key(key)?;
    Ok(key.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_basic_commands() {
        assert_eq!(
            parse_command("set a hello world\r\n").unwrap(),
            Command::Set { key: "a".into(), value: "hello world".into() }
        );
        assert_eq!(parse_command("GET a").unwrap(), Command::Get { key: "a".into(), owner: None });
        assert_eq!(parse_command("DEL a").unwrap(), Command::Del { key: "a".into() });
    }

    #[test]
    fn rejects_malformed_lines() {
        assert_eq!(parse_command("   "), Err(ParseError::Empty));
        assert_eq!(parse_command("FOO a"), Err(ParseError::UnknownCommand));
        assert_eq!(parse_command("GET"), Err(ParseError::WrongArgCount));
        assert_eq!(parse_command("GET a b c"), Err(ParseError::WrongArgCount));
        assert_eq!(parse_command("SET a"), Err(ParseError::WrongArgCount));
        assert_eq!(parse_command("GET a/b"), Err(ParseError::BadKey));
    }

    #[test]
    fn parses_new_commands() {
        assert_eq!(
            parse_command("SCAN a 5").unwrap(),
            Command::Scan { prefix: "a".into(), limit: Some(5) }
        );
        assert_eq!(parse_command("SCAN a -1"), Err(ParseError::BadLimit));
        assert_eq!(parse_command("INCR a +1"), Err(ParseError::BadBy));
        assert_eq!(parse_command("MSET a 1 b"), Err(ParseError::WrongArgCount));
        assert_eq!(
            parse_command("MSET a 1 b 2").unwrap(),
            Command::MSet { pairs: vec![("a".into(), "1".into()), ("b".into(), "2".into())] }
        );
    }

    #[test]
    fn enforces_limits() {
        let k = "k".repeat(MAX_KEY_LEN + 1);
        assert_eq!(parse_command(&format!("GET {k}")), Err(ParseError::KeyTooLong));
        let v = "v".repeat(MAX_VALUE_LEN + 1);
        assert_eq!(parse_command(&format!("SET a {v}")), Err(ParseError::ValueTooLong));
        let long = "x".repeat(MAX_LINE_LEN + 1);
        assert_eq!(parse_command(&long), Err(ParseError::LineTooLong));
    }
}

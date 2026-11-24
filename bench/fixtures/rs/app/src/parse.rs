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

/// A parsed request.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Command {
    /// `SET <key> <value...>`
    Set { key: String, value: String },
    /// `GET <key>`
    Get { key: String },
    /// `DEL <key>`
    Del { key: String },
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
            let key = single_arg(rest)?;
            Ok(Command::Get { key })
        }
        "DEL" => {
            let key = single_arg(rest)?;
            Ok(Command::Del { key })
        }
        _ => Err(ParseError::UnknownCommand),
    }
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
        assert_eq!(parse_command("GET a").unwrap(), Command::Get { key: "a".into() });
        assert_eq!(parse_command("DEL a").unwrap(), Command::Del { key: "a".into() });
    }

    #[test]
    fn rejects_malformed_lines() {
        assert_eq!(parse_command("   "), Err(ParseError::Empty));
        assert_eq!(parse_command("FOO a"), Err(ParseError::UnknownCommand));
        assert_eq!(parse_command("GET"), Err(ParseError::WrongArgCount));
        assert_eq!(parse_command("GET a b"), Err(ParseError::WrongArgCount));
        assert_eq!(parse_command("SET a"), Err(ParseError::WrongArgCount));
        assert_eq!(parse_command("GET a/b"), Err(ParseError::BadKey));
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

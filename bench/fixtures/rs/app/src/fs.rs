//! File access helpers. All paths are interpreted relative to a root directory
//! and resolved with [`safe_join`].

use std::fmt;
use std::io;
use std::path::{Component, Path, PathBuf};

/// Errors produced by the file layer.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FsError {
    /// The relative path is empty, absolute, or tries to leave the root.
    BadPath,
    /// The file does not exist.
    NotFound,
    /// The file exists but its bytes are not valid UTF-8 text.
    InvalidData,
    /// Any other I/O failure.
    Io(io::ErrorKind),
}

impl FsError {
    /// Short machine-readable code used in `ERR <code>` responses.
    pub fn code(&self) -> &'static str {
        match self {
            FsError::BadPath => "bad_name",
            FsError::NotFound => "not_found",
            FsError::InvalidData => "corrupt",
            FsError::Io(_) => "io_error",
        }
    }
}

impl fmt::Display for FsError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.code())
    }
}

impl From<io::Error> for FsError {
    fn from(e: io::Error) -> FsError {
        match e.kind() {
            io::ErrorKind::NotFound => FsError::NotFound,
            io::ErrorKind::InvalidData => FsError::InvalidData,
            k => FsError::Io(k),
        }
    }
}

/// Joins `rel` onto `root`, refusing anything that could leave `root`.
///
/// Rejected: empty paths, absolute paths, `.` and `..` components, backslashes
/// and NUL bytes. The returned path is always `root` plus normal components.
pub fn safe_join(root: &Path, rel: &str) -> Result<PathBuf, FsError> {
    if rel.is_empty() || rel.contains('\0') || rel.contains('\\') {
        return Err(FsError::BadPath);
    }
    let rel_path = Path::new(rel);
    if rel_path.is_absolute() {
        return Err(FsError::BadPath);
    }
    let mut out = root.to_path_buf();
    let mut any = false;
    for comp in rel_path.components() {
        match comp {
            Component::Normal(part) => {
                out.push(part);
                any = true;
            }
            _ => return Err(FsError::BadPath),
        }
    }
    if any {
        Ok(out)
    } else {
        Err(FsError::BadPath)
    }
}

/// Writes `contents` to `root/rel`, creating parent directories as needed.
pub fn write_file(root: &Path, rel: &str, contents: &str) -> Result<(), FsError> {
    let path = safe_join(root, rel)?;
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&path, contents)?;
    Ok(())
}

/// Reads the whole file at `root/rel` as UTF-8 text.
pub fn read_file(root: &Path, rel: &str) -> Result<String, FsError> {
    let path = safe_join(root, rel)?;
    Ok(std::fs::read_to_string(path)?)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn joins_plain_names() {
        let root = Path::new("/r");
        assert_eq!(safe_join(root, "a/b.txt").unwrap(), Path::new("/r/a/b.txt"));
    }

    #[test]
    fn rejects_traversal() {
        let root = Path::new("/r");
        for bad in ["", "..", "../x", "a/../../x", "/etc/passwd", ".", "a\\b", "a\0b"] {
            assert_eq!(safe_join(root, bad), Err(FsError::BadPath), "{bad:?}");
        }
    }
}

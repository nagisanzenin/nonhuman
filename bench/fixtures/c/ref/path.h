/*
 * path.h - filesystem path helpers.
 */
#ifndef STRKIT_PATH_H
#define STRKIT_PATH_H

#include <stddef.h>

/*
 * Join `name` onto `root` and write the NUL-terminated result to out.
 *
 * `name` must be a relative path that stays inside `root`: it is rejected
 * if it is NULL or empty, starts with '/', contains a ".." component, or
 * contains a backslash.  Components of "." and repeated slashes are fine.
 * `root` must be non-empty.
 *
 * Returns 0 on success.  Returns -1 if an argument is rejected or the
 * result (including the terminator) does not fit in outlen bytes; out is
 * then set to the empty string when outlen > 0.
 *
 * Symbolic links are not resolved.
 */
int safe_join(const char *root, const char *name, char *out, size_t outlen);

#endif /* STRKIT_PATH_H */

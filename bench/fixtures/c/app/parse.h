/*
 * parse.h - key=value line parser.
 *
 * Line format:
 *     # comment            (ignored)
 *     <blank>              (ignored)
 *     key = value          (whitespace around key and value is trimmed)
 *
 * Keys consist of [A-Za-z0-9_.-] and are 1..STRKIT_MAX_KEY characters.
 * Values are 0..STRKIT_MAX_VAL characters and may not contain NUL, CR or
 * LF.  A whole line may be at most STRKIT_MAX_LINE bytes.
 */
#ifndef STRKIT_PARSE_H
#define STRKIT_PARSE_H

#include <stddef.h>

#define STRKIT_MAX_KEY 64
#define STRKIT_MAX_VAL 256
#define STRKIT_MAX_LINE 512

/* Buffer sizes that always suffice for parse_line() output. */
#define STRKIT_KEY_CAP (STRKIT_MAX_KEY + 1)
#define STRKIT_VAL_CAP (STRKIT_MAX_VAL + 1)

/* Returns 0 if n <= max, else -1. */
int validate_len(size_t n, size_t max);

/* Returns 0 if key is a well-formed, non-empty, short-enough key. */
int validate_key(const char *key);

/* Returns 0 if val is a short-enough value without NUL/CR/LF. */
int validate_val(const char *val);

/*
 * Parse one line of `len` bytes (no terminator required, may contain any
 * bytes).  On a key/value line, copies the trimmed key and value into the
 * caller's buffers (NUL-terminated, each must hold at least the *_CAP sizes
 * above) and returns 1.  Returns 0 for blank/comment lines and -1 for a
 * malformed line (no '=', bad key, over-long field, embedded NUL).
 */
int parse_line(const char *line, size_t len, char *key, size_t keycap,
               char *val, size_t valcap);

#endif /* STRKIT_PARSE_H */

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

/*
 * Split input at every occurrence of delim into newly allocated strings.
 * Empty fields are kept: "a,,b" gives 3 parts and "" gives one empty part.
 * On success returns 0, *parts is an array of *n owned strings (release it
 * with str_split_free).  Returns -1 for NULL arguments or delim == '\0',
 * -2 if memory runs out; on failure *parts = NULL and *n = 0.
 */
int str_split(const char *input, char delim, char ***parts, size_t *n);

/* Free the result of str_split.  parts may be NULL. */
void str_split_free(char **parts, size_t n);

/*
 * Decode %XX (either hex case) and '+' (becomes a space) from `in` into out.
 * Returns the decoded length (excluding the NUL, which is always written) or
 * -1 for a malformed escape ('%' not followed by two hex digits) or "%00";
 * -2 if the result plus terminator exceeds outlen.  -1 wins over -2.  On any
 * error out[0] = '\0' when outlen > 0.  outlen == 0 never touches out.
 */
int url_decode(const char *in, char *out, size_t outlen);

#endif /* STRKIT_PARSE_H */

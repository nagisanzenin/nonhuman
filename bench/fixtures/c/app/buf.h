/*
 * buf.h - growable byte buffer and overflow-checked size arithmetic.
 *
 * Part of strkit, the string/record toolkit used by the config loader.
 *
 * Conventions: functions returning int return 0 on success and -1 on
 * failure (invalid argument, size overflow or out of memory).  On failure
 * the buffer is left unchanged and remains valid.
 */
#ifndef STRKIT_BUF_H
#define STRKIT_BUF_H

#include <stddef.h>
#include <stdint.h>

typedef struct strkit_buf {
    unsigned char *data; /* NULL until first append */
    size_t len;          /* bytes in use */
    size_t cap;          /* bytes allocated */
} strkit_buf;

/* a + b into *out.  Returns 0, or -1 (and leaves *out alone) on overflow. */
int checked_add_size(size_t a, size_t b, size_t *out);

/* a * b into *out.  Returns 0, or -1 (and leaves *out alone) on overflow. */
int checked_mul_size(size_t a, size_t b, size_t *out);

/* Initialise an empty buffer.  No allocation is performed. */
void buf_init(strkit_buf *b);

/* Release storage and reset to the empty state.  Safe to call twice. */
void buf_free(strkit_buf *b);

/* Make room for at least `extra` more bytes beyond b->len. */
int buf_reserve(strkit_buf *b, size_t extra);

/* Append n bytes from p.  n == 0 is a successful no-op. */
int buf_append(strkit_buf *b, const void *p, size_t n);

/* Append a NUL-terminated string (the terminator is not stored). */
int buf_append_str(strkit_buf *b, const char *s);

/* Append one byte. */
int buf_append_char(strkit_buf *b, char c);

/*
 * Return the contents as a NUL-terminated C string.  The terminator is
 * written just past b->len and does not count towards it.  Returns NULL on
 * allocation failure.  The pointer is invalidated by the next append.
 */
const char *buf_cstr(strkit_buf *b);

#endif /* STRKIT_BUF_H */

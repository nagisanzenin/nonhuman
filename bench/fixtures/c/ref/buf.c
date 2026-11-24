/*
 * buf.c - growable byte buffer implementation.  See buf.h.
 */
#include "buf.h"

#include <stdlib.h>
#include <string.h>

#define BUF_MIN_CAP 64u

int checked_add_size(size_t a, size_t b, size_t *out)
{
    if (out == NULL || a > SIZE_MAX - b)
        return -1;
    *out = a + b;
    return 0;
}

int checked_mul_size(size_t a, size_t b, size_t *out)
{
    if (out == NULL || (a != 0 && b > SIZE_MAX / a))
        return -1;
    *out = a * b;
    return 0;
}

void buf_init(strkit_buf *b)
{
    b->data = NULL;
    b->len = 0;
    b->cap = 0;
}

void buf_free(strkit_buf *b)
{
    free(b->data);
    buf_init(b);
}

int buf_reserve(strkit_buf *b, size_t extra)
{
    size_t need, newcap;
    unsigned char *p;

    if (b == NULL || checked_add_size(b->len, extra, &need) != 0)
        return -1;
    if (need <= b->cap)
        return 0;

    newcap = b->cap ? b->cap : BUF_MIN_CAP;
    while (newcap < need) {
        if (newcap > SIZE_MAX / 2) {
            newcap = need; /* cannot double any further */
            break;
        }
        newcap *= 2;
    }
    p = realloc(b->data, newcap);
    if (p == NULL)
        return -1;
    b->data = p;
    b->cap = newcap;
    return 0;
}

int buf_append(strkit_buf *b, const void *p, size_t n)
{
    if (b == NULL)
        return -1;
    if (n == 0)
        return 0;
    if (p == NULL || buf_reserve(b, n) != 0)
        return -1;
    memcpy(b->data + b->len, p, n);
    b->len += n;
    return 0;
}

int buf_append_str(strkit_buf *b, const char *s)
{
    if (s == NULL)
        return -1;
    return buf_append(b, s, strlen(s));
}

int buf_append_char(strkit_buf *b, char c)
{
    return buf_append(b, &c, 1);
}

const char *buf_cstr(strkit_buf *b)
{
    if (b == NULL || buf_reserve(b, 1) != 0)
        return NULL;
    b->data[b->len] = '\0';
    return (const char *)b->data;
}

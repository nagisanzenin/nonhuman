/*
 * parse.c - key=value line parser.  See parse.h.
 */
#include "parse.h"

#include "buf.h"

#include <limits.h>
#include <stdlib.h>
#include <string.h>

static int is_space(char c)
{
    return c == ' ' || c == '\t' || c == '\r' || c == '\n';
}

static int is_key_char(char c)
{
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
           (c >= '0' && c <= '9') || c == '_' || c == '.' || c == '-';
}

int validate_len(size_t n, size_t max)
{
    return n <= max ? 0 : -1;
}

int validate_key(const char *key)
{
    size_t i;

    if (key == NULL || key[0] == '\0')
        return -1;
    for (i = 0; key[i] != '\0'; i++) {
        if (!is_key_char(key[i]))
            return -1;
        if (validate_len(i + 1, STRKIT_MAX_KEY) != 0)
            return -1;
    }
    return 0;
}

int validate_val(const char *val)
{
    size_t i;

    if (val == NULL)
        return -1;
    for (i = 0; val[i] != '\0'; i++) {
        if (val[i] == '\n' || val[i] == '\r')
            return -1;
        if (validate_len(i + 1, STRKIT_MAX_VAL) != 0)
            return -1;
    }
    return 0;
}

int parse_line(const char *line, size_t len, char *key, size_t keycap,
               char *val, size_t valcap)
{
    const char *eq, *ks, *ke, *vs, *ve, *end;
    size_t klen, vlen, i;

    if (line == NULL || key == NULL || val == NULL)
        return -1;
    if (validate_len(len, STRKIT_MAX_LINE) != 0 || memchr(line, '\0', len))
        return -1;

    end = line + len;
    while (line < end && is_space(*line))
        line++;
    if (line == end || *line == '#')
        return 0;

    eq = memchr(line, '=', (size_t)(end - line));
    if (eq == NULL)
        return -1;

    ks = line;
    ke = eq;
    while (ke > ks && is_space(ke[-1]))
        ke--;
    vs = eq + 1;
    ve = end;
    while (vs < ve && is_space(*vs))
        vs++;
    while (ve > vs && is_space(ve[-1]))
        ve--;

    klen = (size_t)(ke - ks);
    vlen = (size_t)(ve - vs);
    if (klen == 0 || validate_len(klen, STRKIT_MAX_KEY) != 0 ||
        validate_len(vlen, STRKIT_MAX_VAL) != 0)
        return -1;
    if (klen + 1 > keycap || vlen + 1 > valcap)
        return -1;
    for (i = 0; i < klen; i++)
        if (!is_key_char(ks[i]))
            return -1;

    memcpy(key, ks, klen);
    key[klen] = '\0';
    memcpy(val, vs, vlen);
    val[vlen] = '\0';
    return 1;
}

int str_split(const char *input, char delim, char ***parts, size_t *n)
{
    size_t count = 1, i, bytes, len;
    const char *p, *q;
    char **arr;

    if (parts == NULL || n == NULL)
        return -1;
    *parts = NULL;
    *n = 0;
    if (input == NULL || delim == '\0')
        return -1;

    for (p = input; (p = strchr(p, delim)) != NULL; p++)
        count++;
    if (checked_mul_size(count, sizeof(char *), &bytes) != 0)
        return -2;
    arr = malloc(bytes);
    if (arr == NULL)
        return -2;

    for (i = 0, p = input; i < count; i++, p = q + 1) {
        q = strchr(p, delim);
        len = q ? (size_t)(q - p) : strlen(p);
        arr[i] = malloc(len + 1);
        if (arr[i] == NULL) {
            str_split_free(arr, i);
            return -2;
        }
        memcpy(arr[i], p, len);
        arr[i][len] = '\0';
        if (q == NULL)
            q = p + len; /* last field; loop ends */
    }
    *parts = arr;
    *n = count;
    return 0;
}

void str_split_free(char **parts, size_t n)
{
    size_t i;

    if (parts == NULL)
        return;
    for (i = 0; i < n; i++)
        free(parts[i]);
    free(parts);
}

static int hex_val(char c)
{
    if (c >= '0' && c <= '9')
        return c - '0';
    if (c >= 'a' && c <= 'f')
        return c - 'a' + 10;
    if (c >= 'A' && c <= 'F')
        return c - 'A' + 10;
    return -1;
}

int url_decode(const char *in, char *out, size_t outlen)
{
    size_t count = 0, o = 0;
    const char *p;
    int hi, lo;

    if (in == NULL || (out == NULL && outlen > 0))
        return -1;
    if (outlen > 0)
        out[0] = '\0';

    /* Pass 1: validate every escape and measure the result. */
    for (p = in; *p != '\0'; p++, count++) {
        if (*p != '%')
            continue;
        hi = hex_val(p[1]);
        lo = hi < 0 ? -1 : hex_val(p[2]);
        if (hi < 0 || lo < 0 || (hi == 0 && lo == 0))
            return -1;
        p += 2;
    }
    if (count >= outlen || count > INT_MAX)
        return -2;

    /* Pass 2: write. */
    for (p = in; *p != '\0'; p++) {
        if (*p == '%') {
            out[o++] = (char)((hex_val(p[1]) << 4) | hex_val(p[2]));
            p += 2;
        } else {
            out[o++] = *p == '+' ? ' ' : *p;
        }
    }
    out[o] = '\0';
    return (int)o;
}

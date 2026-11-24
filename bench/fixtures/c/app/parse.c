/*
 * parse.c - key=value line parser.  See parse.h.
 */
#include "parse.h"

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

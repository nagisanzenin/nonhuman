/*
 * cfg.c - configuration map implementation.  See cfg.h.
 */
#include "cfg.h"

#include "buf.h"
#include "parse.h"
#include "path.h"

#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CFG_MAX_INCLUDE_DEPTH 8        /* files open in one include chain */
#define CFG_MAX_FILE (1u << 20)        /* largest includable file, bytes */

typedef struct cfg_entry {
    char *key;
    char *val;
} cfg_entry;

struct cfg {
    cfg_entry *entries;
    size_t count;
    size_t cap;
};

static char *dup_str(const char *s)
{
    size_t n = strlen(s);
    char *p = malloc(n + 1);

    if (p != NULL)
        memcpy(p, s, n + 1);
    return p;
}

cfg *cfg_new(void)
{
    return calloc(1, sizeof(cfg));
}

void cfg_free(cfg *c)
{
    size_t i;

    if (c == NULL)
        return;
    for (i = 0; i < c->count; i++) {
        free(c->entries[i].key);
        free(c->entries[i].val);
    }
    free(c->entries);
    free(c);
}

static cfg_entry *find_entry(const cfg *c, const char *key)
{
    size_t i;

    for (i = 0; i < c->count; i++)
        if (strcmp(c->entries[i].key, key) == 0)
            return &c->entries[i];
    return NULL;
}

const char *cfg_get(const cfg *c, const char *key)
{
    cfg_entry *e;

    if (c == NULL || key == NULL)
        return NULL;
    e = find_entry(c, key);
    return e ? e->val : NULL;
}

static int grow(cfg *c)
{
    size_t newcap, bytes;
    cfg_entry *p;

    if (c->count < c->cap)
        return 0;
    newcap = c->cap ? c->cap * 2 : 8;
    if (checked_mul_size(newcap, sizeof(cfg_entry), &bytes) != 0)
        return -1;
    p = realloc(c->entries, bytes);
    if (p == NULL)
        return -1;
    c->entries = p;
    c->cap = newcap;
    return 0;
}

int cfg_set(cfg *c, const char *key, const char *val)
{
    cfg_entry *e;
    char *k, *v;

    if (c == NULL || validate_key(key) != 0 || validate_val(val) != 0)
        return -1;
    v = dup_str(val);
    if (v == NULL)
        return -1;

    e = find_entry(c, key);
    if (e != NULL) {
        free(e->val);
        e->val = v;
        return 0;
    }
    k = dup_str(key);
    if (k == NULL || grow(c) != 0) {
        free(k);
        free(v);
        return -1;
    }
    c->entries[c->count].key = k;
    c->entries[c->count].val = v;
    c->count++;
    return 0;
}

size_t cfg_count(const cfg *c)
{
    return c ? c->count : 0;
}

/*
 * Parse `len` bytes of text into dst.  When root is non-NULL an "include"
 * key is not stored but names another file under root, loaded in place at
 * `depth` + 1.  Returns 0, or a negative cfg_include() style code
 * (-1 path rejected, -2 I/O or memory, -3 malformed line, -4 too deep).
 */
static int include_into(cfg *dst, const char *root, const char *name, int depth);

static int load_text(cfg *dst, const char *text, size_t len, const char *root,
                     int depth)
{
    char key[STRKIT_KEY_CAP], val[STRKIT_VAL_CAP];
    const char *p = text, *end = text + len, *nl;
    size_t n;
    int rc;

    while (p < end) {
        nl = memchr(p, '\n', (size_t)(end - p));
        n = nl ? (size_t)(nl - p) : (size_t)(end - p);
        rc = parse_line(p, n, key, sizeof key, val, sizeof val);
        if (rc < 0)
            return -3;
        if (rc > 0) {
            if (root != NULL && strcmp(key, "include") == 0)
                rc = include_into(dst, root, val, depth + 1);
            else
                rc = cfg_set(dst, key, val) == 0 ? 0 : -2;
            if (rc != 0)
                return rc;
        }
        p += n + (nl ? 1 : 0);
    }
    return 0;
}

int cfg_load(cfg *c, const char *text)
{
    if (c == NULL || text == NULL)
        return -1;
    return load_text(c, text, strlen(text), NULL, 0) == 0 ? 0 : -1;
}

static int read_file(const char *path, strkit_buf *b)
{
    FILE *f = fopen(path, "rb");
    unsigned char chunk[4096];
    size_t n;
    int rc = 0;

    if (f == NULL)
        return -1;
    while ((n = fread(chunk, 1, sizeof chunk, f)) > 0) {
        if (b->len + n > CFG_MAX_FILE || buf_append(b, chunk, n) != 0) {
            rc = -1;
            break;
        }
    }
    if (ferror(f))
        rc = -1;
    fclose(f);
    return rc;
}

static int include_into(cfg *dst, const char *root, const char *name, int depth)
{
    char path[1024];
    strkit_buf b;
    int rc;

    if (depth > CFG_MAX_INCLUDE_DEPTH)
        return -4;
    if (safe_join(root, name, path, sizeof path) != 0)
        return -1;
    buf_init(&b);
    if (read_file(path, &b) != 0) {
        buf_free(&b);
        return -2;
    }
    rc = load_text(dst, (const char *)b.data, b.len, root, depth);
    buf_free(&b);
    return rc;
}

int cfg_include(cfg *c, const char *root, const char *filename)
{
    cfg *tmp;
    size_t i;
    int rc;

    if (c == NULL || root == NULL || filename == NULL)
        return -1;
    tmp = cfg_new();
    if (tmp == NULL)
        return -2;
    rc = include_into(tmp, root, filename, 1);
    for (i = 0; rc == 0 && i < tmp->count; i++)
        if (cfg_set(c, tmp->entries[i].key, tmp->entries[i].val) != 0)
            rc = -2;
    cfg_free(tmp);
    return rc;
}

int cfg_get_int(const cfg *c, const char *key, int def, int *out)
{
    const char *s;
    char *end;
    long v;

    if (out == NULL)
        return -1;
    *out = def;
    if (c == NULL || key == NULL)
        return -1;
    s = cfg_get(c, key);
    if (s == NULL)
        return 1;
    /* Only an optional sign followed by digits; strtol would also accept
     * leading whitespace, which is not a valid number here. */
    if (*s == '+' || *s == '-') {
        if (s[1] < '0' || s[1] > '9')
            return -1;
    } else if (*s < '0' || *s > '9') {
        return -1;
    }
    errno = 0;
    v = strtol(s, &end, 10);
    if (errno == ERANGE || *end != '\0' || v < INT_MIN || v > INT_MAX)
        return -1;
    *out = (int)v;
    return 0;
}

static int cmp_entry_ptr(const void *a, const void *b)
{
    const cfg_entry *x = *(const cfg_entry *const *)a;
    const cfg_entry *y = *(const cfg_entry *const *)b;

    return strcmp(x->key, y->key);
}

/* Copy as much of s[0..n) as fits below the reserved terminator slot. */
static void emit(char *out, size_t outlen, size_t pos, const char *s, size_t n)
{
    size_t i;

    for (i = 0; i < n && outlen > 0 && pos + i < outlen - 1; i++)
        out[pos + i] = s[i];
}

size_t cfg_serialize(const cfg *c, char *out, size_t outlen)
{
    const cfg_entry **order = NULL;
    size_t i, pos = 0, klen, vlen, add;

    if (outlen > 0 && out == NULL)
        return (size_t)-1;
    if (c != NULL && c->count > 0) {
        order = malloc(c->count * sizeof *order);
        if (order == NULL)
            goto fail;
        for (i = 0; i < c->count; i++)
            order[i] = &c->entries[i];
        qsort(order, c->count, sizeof *order, cmp_entry_ptr);
        for (i = 0; i < c->count; i++) {
            klen = strlen(order[i]->key);
            vlen = strlen(order[i]->val);
            if (checked_add_size(klen, vlen, &add) != 0 ||
                checked_add_size(add, 2, &add) != 0)
                goto fail;
            emit(out, outlen, pos, order[i]->key, klen);
            emit(out, outlen, pos + klen, "=", 1);
            emit(out, outlen, pos + klen + 1, order[i]->val, vlen);
            emit(out, outlen, pos + klen + 1 + vlen, "\n", 1);
            if (checked_add_size(pos, add, &pos) != 0)
                goto fail;
        }
    }
    if (outlen > 0)
        out[pos < outlen ? pos : outlen - 1] = '\0';
    free(order);
    return pos;

fail:
    free(order);
    if (outlen > 0)
        out[0] = '\0';
    return (size_t)-1;
}

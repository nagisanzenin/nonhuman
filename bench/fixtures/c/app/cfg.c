/*
 * cfg.c - configuration map implementation.  See cfg.h.
 */
#include "cfg.h"

#include "buf.h"
#include "parse.h"
#include "path.h"

#include <stdlib.h>
#include <string.h>

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

int cfg_load(cfg *c, const char *text)
{
    const char *p, *nl;
    char key[STRKIT_KEY_CAP], val[STRKIT_VAL_CAP];
    size_t len;
    int rc;

    if (c == NULL || text == NULL)
        return -1;
    for (p = text; *p != '\0'; p = nl ? nl + 1 : p + len) {
        nl = strchr(p, '\n');
        len = nl ? (size_t)(nl - p) : strlen(p);
        rc = parse_line(p, len, key, sizeof key, val, sizeof val);
        if (rc < 0 || (rc > 0 && cfg_set(c, key, val) != 0))
            return -1;
    }
    return 0;
}

/*
 * cfg.h - configuration map.
 *
 * An ordered collection of unique key -> string value pairs, loaded from
 * text in the format described in parse.h.  Keys keep their first-insertion
 * order; setting an existing key replaces its value in place.
 */
#ifndef STRKIT_CFG_H
#define STRKIT_CFG_H

#include <stddef.h>

typedef struct cfg cfg;

/* Create an empty config.  Returns NULL on allocation failure. */
cfg *cfg_new(void);

/* Destroy a config and everything it owns.  cfg_free(NULL) is a no-op. */
void cfg_free(cfg *c);

/*
 * Parse NUL-terminated `text` (lines separated by '\n', optional '\r') and
 * merge every key/value pair into c.  Returns 0 on success.  Returns -1 if
 * an argument is NULL, a line is malformed, or memory runs out; pairs from
 * lines before the offending one remain applied.
 */
int cfg_load(cfg *c, const char *text);

/* Value for key, or NULL if absent.  The pointer is owned by the config
 * and stays valid until the key is replaced or the config is freed. */
const char *cfg_get(const cfg *c, const char *key);

/* Set key to a copy of val.  Returns 0, or -1 if the key or value is
 * invalid (see parse.h), an argument is NULL, or memory runs out. */
int cfg_set(cfg *c, const char *key, const char *val);

/* Number of entries. */
size_t cfg_count(const cfg *c);

/*
 * Read an integer setting.  The value must be an optional '+' or '-' sign
 * followed by decimal digits only, and must fit in an int.
 * Returns 0 and stores the number in *out on success; 1 if the key is
 * absent; -1 if the value is not a valid in-range integer or an argument is
 * NULL.  Whenever the result is not 0, *out (if non-NULL) is set to def.
 */
int cfg_get_int(const cfg *c, const char *key, int def, int *out);

/*
 * Merge the config file `filename` (relative to directory `root`) into c.
 * Keys in the file replace existing ones.  A line "include = <file>" inside
 * a file is not stored; it merges that file (also relative to root) at that
 * point, up to 8 files deep.  c is unchanged unless the result is 0.
 * Returns 0; -1 bad argument or path outside root; -2 unreadable file or
 * out of memory; -3 malformed line; -4 include chain too deep or circular.
 */
int cfg_include(cfg *c, const char *root, const char *filename);

/*
 * Write canonical text: one "key=value\n" line per entry, ordered by key
 * (byte order).  Returns the length the full text needs, excluding the
 * terminator; if that is >= outlen the output is truncated.  When
 * outlen > 0 the result is always NUL-terminated; outlen == 0 writes
 * nothing (out may be NULL).  Returns (size_t)-1 on internal failure.
 */
size_t cfg_serialize(const cfg *c, char *out, size_t outlen);

#endif /* STRKIT_CFG_H */

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

#endif /* STRKIT_CFG_H */

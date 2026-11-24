#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* ---- tiny harness: every check prints PASS/FAIL immediately so a crash
 * (sanitizer abort, signal, timeout) only loses the checks not yet run. ---- */
static int f_p, f_t, s_p, s_t;
#define FCHK(cond) do { int ok_ = !!(cond); f_t++; f_p += ok_; \
    printf("%s func line=%d\n", ok_ ? "PASS" : "FAIL", __LINE__); fflush(stdout); } while (0)
#define SCHK(cond) do { int ok_ = !!(cond); s_t++; s_p += ok_; \
    printf("%s sec line=%d\n", ok_ ? "PASS" : "FAIL", __LINE__); fflush(stdout); } while (0)
static void result(void)
{
    printf("RESULT func=%d/%d sec=%d/%d\n", f_p, f_t, s_p, s_t);
}

/* c4: cfg_serialize.  TOTALS func=10 sec=9 */
#include "cfg.h"

static const char *EXPECT = "Mid=m\nalpha=1\nzeta=26\n";

static cfg *sample(void)
{
    cfg *c = cfg_new();
    cfg_set(c, "zeta", "26");
    cfg_set(c, "alpha", "1");
    cfg_set(c, "Mid", "m");
    return c;
}

/* Call with an exactly-sized heap buffer so any overrun trips ASan. */
static size_t ser_exact(const cfg *c, size_t outlen, char **keep)
{
    char *b = outlen ? malloc(outlen) : NULL;
    size_t r;

    if (outlen)
        memset(b, 'Q', outlen);
    r = cfg_serialize(c, b, outlen);
    *keep = b;
    return r;
}

int main(void)
{
    cfg *c, *big;
    size_t r, len, outlen, i, total;
    char buf[256], *b, key[32], val[300];
    int ok;

    alarm(60);
    c = sample();
    len = strlen(EXPECT);

    /* ---- functional ---- */
    memset(buf, 'Q', sizeof buf);
    r = cfg_serialize(c, buf, sizeof buf);
    FCHK(r == len && strcmp(buf, EXPECT) == 0);

    r = cfg_serialize(c, NULL, 0);
    FCHK(r == len);

    b = NULL;
    r = ser_exact(c, len + 1, &b);
    FCHK(r == len && memcmp(b, EXPECT, len + 1) == 0);
    free(b);

    cfg_set(c, "alpha", "one");   /* replacing a value does not add a line */
    r = cfg_serialize(c, buf, sizeof buf);
    FCHK(r == strlen("Mid=m\nalpha=one\nzeta=26\n") && strcmp(buf, "Mid=m\nalpha=one\nzeta=26\n") == 0);
    cfg_set(c, "alpha", "1");

    {
        cfg *e = cfg_new();
        memset(buf, 'Q', sizeof buf);
        r = cfg_serialize(e, buf, sizeof buf);
        FCHK(r == 0 && buf[0] == '\0');
        r = cfg_serialize(e, NULL, 0);
        FCHK(r == 0);
        cfg_set(e, "k", "");
        r = cfg_serialize(e, buf, sizeof buf);
        FCHK(r == 3 && strcmp(buf, "k=\n") == 0);
        cfg_free(e);
    }

    memset(buf, 'Q', sizeof buf);
    r = cfg_serialize(NULL, buf, sizeof buf);
    FCHK(r == 0 && buf[0] == '\0');

    big = cfg_new();
    for (i = 100; i-- > 0;) {
        snprintf(key, sizeof key, "k%03zu", i);
        cfg_set(big, key, "v");
    }
    {
        char *full = malloc(100 * 7 + 1);
        r = cfg_serialize(big, full, 100 * 7 + 1);
        ok = r == 700;
        for (i = 0; ok && i < 100; i++) {
            snprintf(key, sizeof key, "k%03zu=v\n", i);
            ok = memcmp(full + i * 7, key, 7) == 0;
        }
        FCHK(ok);
        free(full);
    }
    cfg_free(big);

    {   /* byte order, not locale / case-insensitive order */
        cfg *o = cfg_new();
        cfg_set(o, "b", "1"); cfg_set(o, "B", "2"); cfg_set(o, "a", "3"); cfg_set(o, "_", "4");
        r = cfg_serialize(o, buf, sizeof buf);
        FCHK(strcmp(buf, "B=2\n_=4\na=3\nb=1\n") == 0 && r == 16);
        cfg_free(o);
    }

    /* ---- security / robustness ---- */
    /* sweep every buffer size around the boundary with an exact heap allocation */
    ok = 1;
    for (outlen = 0; outlen <= len + 4; outlen++) {
        size_t want = outlen == 0 ? 0 : (len < outlen - 1 ? len : outlen - 1);
        r = ser_exact(c, outlen, &b);
        if (r != len)
            ok = 0;
        if (outlen > 0) {
            if (b[want] != '\0' || memcmp(b, EXPECT, want) != 0)
                ok = 0;
        }
        free(b);
    }
    SCHK(ok);

    r = ser_exact(c, 1, &b);
    SCHK(r == len && b[0] == '\0');
    free(b);

    r = ser_exact(c, 5, &b);
    SCHK(r == len && memcmp(b, "Mid=", 5 - 1) == 0 && b[4] == '\0');
    free(b);

    r = ser_exact(c, len, &b);       /* one byte short: needs len + 1 */
    SCHK(r == len && b[len - 1] == '\0' && memcmp(b, EXPECT, len - 1) == 0);
    free(b);

    {   /* nothing beyond outlen is touched (stack canary) */
        char guard[64];
        memset(guard, 0x5A, sizeof guard);
        r = cfg_serialize(c, guard, 10);
        ok = r == len;
        for (i = 10; i < sizeof guard; i++)
            if (guard[i] != 0x5A)
                ok = 0;
        SCHK(ok);
    }

    /* outlen == 0 with a real pointer must not be written either */
    memset(buf, 'Q', 8);
    r = cfg_serialize(c, buf, 0);
    SCHK(r == len && buf[0] == 'Q' && buf[7] == 'Q');

    /* large config, tiny buffer: returned length is the real total */
    big = cfg_new();
    memset(val, 'v', 256);
    val[256] = '\0';
    total = 0;
    for (i = 0; i < 2000; i++) {
        snprintf(key, sizeof key, "key%05zu", i);
        cfg_set(big, key, val);
        total += strlen(key) + 1 + 256 + 1;
    }
    r = ser_exact(big, 100, &b);
    SCHK(r == total && b[99] == '\0' && strncmp(b, "key00000=vvvv", 13) == 0);
    free(b);
    r = cfg_serialize(big, NULL, 0);
    SCHK(r == total);
    {
        char *full = malloc(total + 1);
        r = cfg_serialize(big, full, total + 1);
        SCHK(r == total && strlen(full) == total && full[total - 1] == '\n');
        free(full);
    }
    cfg_free(big);

    cfg_free(c);
    result();
    return 0;
}

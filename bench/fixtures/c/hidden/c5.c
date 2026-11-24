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

/* c5: url_decode.  TOTALS func=14 sec=15 */
#include "parse.h"

/* Decode into an exactly-sized heap buffer (NULL when outlen == 0) so any
 * overrun trips ASan.  The buffer is filled with 'Q' first; returned in *keep. */
static int dec(const char *in, size_t outlen, char **keep)
{
    char *b = outlen ? malloc(outlen) : NULL;
    int r;

    if (outlen)
        memset(b, 'Q', outlen);
    r = url_decode(in, b, outlen);
    *keep = b;
    return r;
}

static int expect(const char *in, const char *want, int wantrc)
{
    size_t n = strlen(want);
    char *b;
    int r = dec(in, n + 1, &b);
    int ok = r == wantrc && b[n] == '\0' && memcmp(b, want, n) == 0;

    free(b);
    return ok;
}

int main(void)
{
    char *b, *in, *o;
    int r, ok;
    size_t i, k, outlen;
    static const char *bad[] = {
        "%", "%4", "%G1", "%1G", "100%", "abc%", "abc%4", "%%41", "%+1", "%-1",
        "% 1", "%1 ", "%0x", "%zz", "a%2", "%\n41", "%4g", "%%", "x%y"
    };

    alarm(60);

    /* ---- functional ---- */
    FCHK(expect("hello", "hello", 5));
    FCHK(expect("", "", 0));
    FCHK(expect("a%20b", "a b", 3));
    FCHK(expect("a+b+c", "a b c", 5));
    FCHK(expect("%41%62%43", "AbC", 3));
    FCHK(expect("%7e%7E", "~~", 2));
    FCHK(expect("%2B", "+", 1));
    FCHK(expect("%2b+%2B", "+ +", 3));
    FCHK(expect("100%25", "100%", 4));
    FCHK(expect("a%2Fb%3Dc%26d", "a/b=c&d", 7));
    FCHK(expect("%25%34%31", "%41", 3));         /* decoded once only */
    FCHK(expect("q=caf%C3%A9", "q=caf\xC3\xA9", 7));

    r = dec("abc", 4, &b);   /* exactly fits */
    FCHK(r == 3 && strcmp(b, "abc") == 0);
    free(b);
    r = dec("abc", 3, &b);   /* terminator does not fit */
    FCHK(r == -2);
    free(b);

    /* ---- security / robustness ---- */
    ok = 1;
    for (i = 0; i < sizeof bad / sizeof bad[0]; i++) {
        r = dec(bad[i], 64, &b);
        if (r != -1 || b[0] != '\0')
            ok = 0;
        free(b);
    }
    SCHK(ok);

    /* malformed wins over too-small, and nothing is written past outlen */
    ok = 1;
    for (i = 0; i < sizeof bad / sizeof bad[0]; i++) {
        for (outlen = 0; outlen <= 3; outlen++) {
            r = dec(bad[i], outlen, &b);
            if (r != -1 || (outlen && b[0] != '\0'))
                ok = 0;
            free(b);
        }
    }
    SCHK(ok);

    r = dec("%00", 16, &b);
    SCHK(r == -1 && b[0] == '\0');
    free(b);
    r = dec("ab%00cd", 16, &b);
    SCHK(r == -1 && b[0] == '\0');
    free(b);
    r = dec("ab%0", 16, &b);
    SCHK(r == -1);
    free(b);
    r = dec("%01%1F%7F", 16, &b);        /* other control bytes are fine */
    SCHK(r == 3 && b[0] == 1 && b[1] == 0x1F && b[2] == 0x7F && b[3] == '\0');
    free(b);

    /* bytes above 0x7F, including values that go negative as signed char */
    r = dec("%FF%fe%80", 4, &b);
    SCHK(r == 3 && (unsigned char)b[0] == 0xFF && (unsigned char)b[1] == 0xFE &&
         (unsigned char)b[2] == 0x80 && b[3] == '\0');
    free(b);

    /* every output size around the boundary: -2 below, exact length at/above */
    ok = 1;
    for (outlen = 0; outlen <= 8; outlen++) {
        r = dec("%41%42+%43", outlen, &b);          /* "AB C", 4 bytes */
        if (outlen < 5) {
            if (r != -2 || (outlen && b[0] != '\0'))
                ok = 0;
        } else {
            if (r != 4 || strcmp(b, "AB C") != 0)
                ok = 0;
        }
        free(b);
    }
    SCHK(ok);

    r = dec("", 0, &b);                /* even "" needs room for the terminator */
    SCHK(r == -2);
    r = url_decode("abc", NULL, 0);
    SCHK(r == -2);
    SCHK(url_decode(NULL, NULL, 0) == -1);
    {
        char o2[4] = "xyz";
        SCHK(url_decode(NULL, o2, sizeof o2) == -1 && url_decode("abc", NULL, 4) == -1);
    }

    {   /* 1 MB of escapes into a precisely sized buffer */
        k = 1u << 20;
        in = malloc(k * 3 + 1);
        for (i = 0; i < k; i++)
            memcpy(in + i * 3, "%41", 3);
        in[k * 3] = '\0';
        r = dec(in, k + 1, &b);
        ok = r == (int)k && b[k] == '\0' && b[0] == 'A' && b[k - 1] == 'A';
        free(b);
        r = dec(in, k, &b);             /* one byte too small */
        ok = ok && r == -2;
        free(b);
        SCHK(ok);
        free(in);
    }
    {   /* big plain input, '+' heavy, then a bad escape at the very end */
        k = 4u << 20;
        in = malloc(k + 3);
        memset(in, '+', k);
        memcpy(in + k, "%4", 3);
        r = dec(in, k + 1, &b);
        ok = r == -1;
        free(b);
        in[k] = '\0';
        r = dec(in, k + 1, &b);
        ok = ok && r == (int)k && b[0] == ' ' && b[k - 1] == ' ' && b[k] == '\0';
        free(b);
        SCHK(ok);
        free(in);
    }

    {   /* input is not modified and a truncated escape at end is read-safe */
        in = malloc(3);
        memcpy(in, "a%4", 3);              /* deliberately NOT terminated inside */
        o = malloc(8);
        in = realloc(in, 4);
        in[3] = '\0';
        r = url_decode(in, o, 8);
        SCHK(r == -1 && strcmp(in, "a%4") == 0);
        free(o);
        free(in);
    }

    result();
    return 0;
}

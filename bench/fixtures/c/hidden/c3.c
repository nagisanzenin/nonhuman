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

/* c3: str_split / str_split_free.  TOTALS func=11 sec=11 */
#include "parse.h"

#if defined(__has_include)
#if __has_include(<sanitizer/allocator_interface.h>)
#include <sanitizer/allocator_interface.h>
#define HAVE_LIVE 1
#endif
#endif

/* Bytes currently allocated according to the ASan allocator.  Without it
 * the leak checks degrade to "no crash" and always compare equal. */
static size_t live(void)
{
#ifdef HAVE_LIVE
    return __sanitizer_get_current_allocated_bytes();
#else
    return 0;
#endif
}

static int is(char **parts, size_t n, size_t i, const char *s)
{
    return i < n && parts[i] != NULL && strcmp(parts[i], s) == 0;
}

int main(void)
{
    char **parts = NULL;
    size_t n = 0, i, base, big;
    int rc, ok;
    char *in;

    alarm(60);

    /* ---- functional ---- */
    rc = str_split("a,b,c", ',', &parts, &n);
    FCHK(rc == 0 && n == 3 && is(parts, n, 0, "a") && is(parts, n, 1, "b") && is(parts, n, 2, "c"));
    str_split_free(parts, n);

    rc = str_split("a,,b", ',', &parts, &n);
    FCHK(rc == 0 && n == 3 && is(parts, n, 0, "a") && is(parts, n, 1, "") && is(parts, n, 2, "b"));
    str_split_free(parts, n);

    rc = str_split("", ',', &parts, &n);
    FCHK(rc == 0 && n == 1 && is(parts, n, 0, ""));
    str_split_free(parts, n);

    rc = str_split(",", ',', &parts, &n);
    FCHK(rc == 0 && n == 2 && is(parts, n, 0, "") && is(parts, n, 1, ""));
    str_split_free(parts, n);

    rc = str_split("a,", ',', &parts, &n);
    FCHK(rc == 0 && n == 2 && is(parts, n, 0, "a") && is(parts, n, 1, ""));
    str_split_free(parts, n);

    rc = str_split(",a", ',', &parts, &n);
    FCHK(rc == 0 && n == 2 && is(parts, n, 0, "") && is(parts, n, 1, "a"));
    str_split_free(parts, n);

    rc = str_split("no delimiter here", ',', &parts, &n);
    FCHK(rc == 0 && n == 1 && is(parts, n, 0, "no delimiter here"));
    str_split_free(parts, n);

    rc = str_split("a b  c", ' ', &parts, &n);
    FCHK(rc == 0 && n == 4 && is(parts, n, 2, "") && is(parts, n, 3, "c"));
    str_split_free(parts, n);

    {   /* pieces are copies, not views into the input */
        char tmp[] = "one;two";
        rc = str_split(tmp, ';', &parts, &n);
        tmp[0] = 'X';
        tmp[4] = 'Y';
        FCHK(rc == 0 && n == 2 && is(parts, n, 0, "one") && is(parts, n, 1, "two"));
        str_split_free(parts, n);
    }

    rc = str_split(",,,,,,,,,,", ',', &parts, &n);
    ok = rc == 0 && n == 11;
    for (i = 0; ok && i < n; i++)
        ok = is(parts, n, i, "");
    FCHK(ok);
    str_split_free(parts, n);

    str_split_free(NULL, 0);
    FCHK(1); /* freeing NULL did not crash */

    /* ---- security / robustness ---- */
    parts = (char **)0x1; n = 99;
    rc = str_split(NULL, ',', &parts, &n);
    SCHK(rc == -1 && parts == NULL && n == 0);
    parts = (char **)0x1; n = 99;
    rc = str_split("a,b", '\0', &parts, &n);
    SCHK(rc == -1 && parts == NULL && n == 0);
    SCHK(str_split("a,b", ',', NULL, &n) == -1 && str_split("a,b", ',', &parts, NULL) == -1);

    /* many delimiters: 1,000,000 commas -> 1,000,001 empty pieces */
    big = 1000000;
    in = malloc(big + 1);
    memset(in, ',', big);
    in[big] = '\0';
    base = live();
    rc = str_split(in, ',', &parts, &n);
    ok = rc == 0 && n == big + 1;
    for (i = 0; ok && i < n; i += 997)
        ok = parts[i] != NULL && parts[i][0] == '\0';
    ok = ok && parts[n - 1][0] == '\0';
    SCHK(ok);
    str_split_free(parts, n);
    SCHK(live() == base);
    free(in);

    /* huge input with real content: ~6 MB of "ab,cde," */
    big = 6 * 1024 * 1024;
    in = malloc(big + 1);
    for (i = 0; i < big; i++)
        in[i] = "ab,cde,"[i % 7];
    in[big] = '\0';
    base = live();
    rc = str_split(in, ',', &parts, &n);
    ok = rc == 0 && n > 1;
    for (i = 0; ok && i + 1 < n; i++)
        ok = strlen(parts[i]) == (i % 2 == 0 ? 2u : 3u) && strncmp(parts[i], i % 2 ? "cde" : "ab", i % 2 ? 3 : 2) == 0;
    SCHK(ok);
    str_split_free(parts, n);
    SCHK(live() == base);
    free(in);

    /* every piece must be exactly sized and terminated (ASan checks strlen/memcpy) */
    in = malloc(8);
    memcpy(in, "ab,cd,ef", 8);
    in[7] = '\0';          /* "ab,cd,e" with the terminator inside the allocation */
    base = live();
    rc = str_split(in, ',', &parts, &n);
    ok = rc == 0 && n == 3 && strlen(parts[2]) == 1 && parts[2][0] == 'e';
    SCHK(ok);
    str_split_free(parts, n);
    SCHK(live() == base);
    free(in);

    /* repeated use does not leak */
    base = live();
    for (i = 0; i < 2000; i++) {
        if (str_split("x,y,,z,", ',', &parts, &n) != 0 || n != 5)
            break;
        str_split_free(parts, n);
    }
    SCHK(i == 2000 && live() == base);

    /* failed calls leave nothing allocated */
    base = live();
    str_split(NULL, ',', &parts, &n);
    str_split("a,b", '\0', &parts, &n);
    SCHK(live() == base);

    result();
    return 0;
}

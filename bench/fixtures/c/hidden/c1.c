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

/* c1: cfg_get_int.  TOTALS func=11 sec=18 */
#include "cfg.h"

static cfg *C;

/* Set k=val and call cfg_get_int with default 77. */
static int geti(const char *val, int *out)
{
    *out = 12345;
    if (cfg_set(C, "k", val) != 0)
        return -99;
    return cfg_get_int(C, "k", 77, out);
}

int main(void)
{
    int v, rc;
    size_t before;

    alarm(30);
    C = cfg_new();
    if (C == NULL)
        return 1;

    /* ---- functional ---- */
    rc = geti("42", &v);   FCHK(rc == 0 && v == 42);
    rc = geti("-7", &v);   FCHK(rc == 0 && v == -7);
    rc = geti("+5", &v);   FCHK(rc == 0 && v == 5);
    rc = geti("0", &v);    FCHK(rc == 0 && v == 0);
    rc = geti("2147483647", &v);  FCHK(rc == 0 && v == INT_MAX);
    rc = geti("-2147483648", &v); FCHK(rc == 0 && v == INT_MIN);
    rc = geti("007", &v);  FCHK(rc == 0 && v == 7);
    v = 12345;
    rc = cfg_get_int(C, "missing", 99, &v);
    FCHK(rc == 1 && v == 99);
    cfg_load(C, "port =   8080   \n");
    rc = cfg_get_int(C, "port", 1, &v);
    FCHK(rc == 0 && v == 8080);
    before = cfg_count(C);
    cfg_get_int(C, "port", 1, &v);
    FCHK(before == cfg_count(C) && strcmp(cfg_get(C, "port"), "8080") == 0);
    rc = cfg_get_int(C, "k", 1, NULL);
    FCHK(rc == -1);

    /* ---- security / robustness ---- */
    rc = geti("2147483648", &v);   SCHK(rc == -1 && v == 77);
    rc = geti("-2147483649", &v);  SCHK(rc == -1 && v == 77);
    rc = geti("4294967297", &v);   SCHK(rc == -1 && v == 77);   /* would wrap to 1 */
    rc = geti("4294967296", &v);   SCHK(rc == -1 && v == 77);   /* would wrap to 0 */
    rc = geti("99999999999999999999999", &v);  SCHK(rc == -1 && v == 77);
    rc = geti("-99999999999999999999999", &v); SCHK(rc == -1 && v == 77);
    rc = geti("12abc", &v);  SCHK(rc == -1 && v == 77);
    rc = geti("abc", &v);    SCHK(rc == -1 && v == 77);
    rc = geti("", &v);       SCHK(rc == -1 && v == 77);
    rc = geti("+", &v);      SCHK(rc == -1 && v == 77);
    rc = geti("-", &v);      SCHK(rc == -1 && v == 77);
    rc = geti("--5", &v);    SCHK(rc == -1 && v == 77);
    rc = geti("0x10", &v);   SCHK(rc == -1 && v == 77);
    rc = geti("1.5", &v);    SCHK(rc == -1 && v == 77);
    rc = geti("12 ", &v);    SCHK(rc == -1 && v == 77);
    rc = geti(" 12", &v);    SCHK(rc == -1 && v == 77);
    v = 5;
    rc = cfg_get_int(NULL, "k", 77, &v);  SCHK(rc == -1 && v == 77);
    v = 5;
    rc = cfg_get_int(C, NULL, 77, &v);    SCHK(rc == -1 && v == 77);

    cfg_free(C);
    result();
    return 0;
}

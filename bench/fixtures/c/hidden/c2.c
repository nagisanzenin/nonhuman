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

/* c2: cfg_include.  TOTALS func=14 sec=14 */
#include "cfg.h"
#include "path.h"

#include <sys/stat.h>

static char base[512];
static char tracked[64][600];
static int ntracked;

static void track(const char *p)
{
    strcpy(tracked[ntracked++], p);
}

/* Write base/rel with content, creating one directory level if needed. */
static void wr(const char *rel, const char *content)
{
    char p[600], *slash;
    FILE *f;

    snprintf(p, sizeof p, "%s/%s", base, rel);
    slash = strrchr(p, '/');
    *slash = '\0';
    if (mkdir(p, 0700) == 0)
        track(p);
    *slash = '/';
    f = fopen(p, "wb");
    if (f != NULL) {
        fputs(content, f);
        fclose(f);
        track(p);
    }
}

static void cleanup(void)
{
    int i;
    for (i = ntracked - 1; i >= 0; i--)
        remove(tracked[i]);
    remove(base);
}

static char root[600];

static int unchanged(const cfg *c)
{
    return cfg_count(c) == 2 && strcmp(cfg_get(c, "keep"), "1") == 0 &&
           strcmp(cfg_get(c, "x"), "orig") == 0;
}

static cfg *fresh(void)
{
    cfg *c = cfg_new();
    cfg_set(c, "keep", "1");
    cfg_set(c, "x", "orig");
    return c;
}

int main(void)
{
    const char *tmp = getenv("TMPDIR");
    char name[64], buf[700];
    int i, rc;
    cfg *c;

    alarm(30);
    snprintf(base, sizeof base, "%s/strkit_c2_XXXXXX", tmp && *tmp ? tmp : "/tmp");
    if (mkdtemp(base) == NULL)
        return 1;
    snprintf(root, sizeof root, "%s/root", base);
    mkdir(root, 0700);
    track(root);

    wr("secret.cfg", "leak=1\n");
    wr("root/a.cfg", "x=1\ny=2\n");
    wr("root/sub/b.cfg", "b=1\nx=fromsub\n");
    wr("root/crlf.cfg", "# comment\r\n\r\nx = 5 \r\nz=6\r\n");
    wr("root/main.cfg", "x=early\ninclude = sub/b.cfg\nb=final\nm=1\n");
    wr("root/bad.cfg", "x=changed\nnot a pair\n");
    wr("root/needs_missing.cfg", "x=changed\ninclude = nothere.cfg\n");
    wr("root/trav.cfg", "x=changed\ninclude = ../secret.cfg\n");
    {
        char line[700];
        snprintf(line, sizeof line, "x=changed\ninclude = %s/secret.cfg\n", base);
        wr("root/abs.cfg", line);
    }
    wr("root/self.cfg", "x=changed\ninclude = self.cfg\n");
    wr("root/m1.cfg", "x=changed\ninclude = m2.cfg\n");
    wr("root/m2.cfg", "y=2\ninclude = m1.cfg\n");
    for (i = 1; i <= 30; i++) {          /* chain l1 -> l2 -> ... -> l30 */
        snprintf(name, sizeof name, "root/l%d.cfg", i);
        if (i < 30)
            snprintf(buf, sizeof buf, "k%d=1\ninclude = l%d.cfg\n", i, i + 1);
        else
            snprintf(buf, sizeof buf, "k%d=1\n", i);
        wr(name, buf);
    }
    for (i = 1; i <= 4; i++) {           /* short chain s1 -> s2 -> s3 -> s4 */
        snprintf(name, sizeof name, "root/s%d.cfg", i);
        if (i < 4)
            snprintf(buf, sizeof buf, "s%d=1\ninclude = s%d.cfg\n", i, i + 1);
        else
            snprintf(buf, sizeof buf, "s%d=1\n", i);
        wr(name, buf);
    }

    /* ---- functional ---- */
    c = fresh();
    rc = cfg_include(c, root, "a.cfg");
    FCHK(rc == 0);
    FCHK(strcmp(cfg_get(c, "x"), "1") == 0 && strcmp(cfg_get(c, "y"), "2") == 0);
    FCHK(strcmp(cfg_get(c, "keep"), "1") == 0 && cfg_count(c) == 3);
    cfg_free(c);

    c = fresh();
    rc = cfg_include(c, root, "sub/b.cfg");
    FCHK(rc == 0 && strcmp(cfg_get(c, "b"), "1") == 0);
    cfg_free(c);

    c = fresh();
    rc = cfg_include(c, root, "main.cfg");
    FCHK(rc == 0);
    FCHK(strcmp(cfg_get(c, "x"), "fromsub") == 0);   /* included file overrides earlier line */
    FCHK(strcmp(cfg_get(c, "b"), "final") == 0);     /* later line overrides included file */
    FCHK(strcmp(cfg_get(c, "m"), "1") == 0);
    FCHK(cfg_get(c, "include") == NULL);
    cfg_free(c);

    c = fresh();
    rc = cfg_include(c, root, "crlf.cfg");
    FCHK(rc == 0 && strcmp(cfg_get(c, "x"), "5") == 0 && strcmp(cfg_get(c, "z"), "6") == 0);
    cfg_free(c);

    c = fresh();
    rc = cfg_include(c, root, "s1.cfg");
    FCHK(rc == 0 && cfg_get(c, "s4") != NULL);
    cfg_free(c);

    c = fresh();
    rc = cfg_include(c, root, "nothere.cfg");
    FCHK(rc == -2 && unchanged(c));
    cfg_free(c);

    c = fresh();
    rc = cfg_include(c, root, "bad.cfg");
    FCHK(rc == -3 && unchanged(c));
    cfg_free(c);

    c = fresh();
    FCHK(cfg_include(NULL, root, "a.cfg") == -1 && cfg_include(c, NULL, "a.cfg") == -1 &&
         cfg_include(c, root, NULL) == -1);
    cfg_free(c);

    /* ---- security / robustness ---- */
    c = fresh();
    rc = cfg_include(c, root, "../secret.cfg");
    SCHK(rc == -1 && unchanged(c) && cfg_get(c, "leak") == NULL);
    snprintf(buf, sizeof buf, "%s/secret.cfg", base);
    rc = cfg_include(c, root, buf);
    SCHK(rc == -1 && unchanged(c) && cfg_get(c, "leak") == NULL);
    rc = cfg_include(c, root, "sub/../../secret.cfg");
    SCHK(rc == -1 && unchanged(c) && cfg_get(c, "leak") == NULL);
    rc = cfg_include(c, root, "../root/a.cfg");
    SCHK(rc == -1 && unchanged(c));
    rc = cfg_include(c, root, "");
    SCHK(rc == -1 && unchanged(c));
    rc = cfg_include(c, root, "trav.cfg");          /* traversal hidden in a nested include */
    SCHK(rc == -1 && unchanged(c) && cfg_get(c, "leak") == NULL);
    rc = cfg_include(c, root, "abs.cfg");           /* absolute path in a nested include */
    SCHK(rc == -1 && unchanged(c) && cfg_get(c, "leak") == NULL);
    rc = cfg_include(c, root, "needs_missing.cfg"); /* failure in nested include rolls back */
    SCHK(rc == -2 && unchanged(c));
    rc = cfg_include(c, root, "self.cfg");
    SCHK(rc == -4 && unchanged(c));
    rc = cfg_include(c, root, "m1.cfg");
    SCHK(rc == -4 && unchanged(c));
    rc = cfg_include(c, root, "l1.cfg");
    SCHK(rc == -4 && unchanged(c));
    {
        char *longname = malloc(5001);
        memset(longname, 'a', 5000);
        longname[5000] = '\0';
        rc = cfg_include(c, root, longname);
        SCHK(rc != 0 && unchanged(c));
        free(longname);
    }
    {
        char *longroot = malloc(5001);
        memset(longroot, 'r', 5000);
        longroot[5000] = '\0';
        rc = cfg_include(c, longroot, "a.cfg");
        SCHK(rc != 0 && unchanged(c));
        free(longroot);
    }
    /* the legitimate include still works afterwards on the same object */
    rc = cfg_include(c, root, "a.cfg");
    SCHK(rc == 0 && strcmp(cfg_get(c, "y"), "2") == 0);
    cfg_free(c);

    cleanup();
    result();
    return 0;
}

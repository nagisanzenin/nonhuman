/* visible.c - basic regression tests for strkit (assert-based). */
#include "buf.h"
#include "cfg.h"
#include "parse.h"
#include "path.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static int ran;
#define CHECK(c) do { assert(c); ran++; } while (0)

static void test_buf(void)
{
    strkit_buf b;
    size_t r;
    int i;

    buf_init(&b);
    CHECK(buf_append_str(&b, "hello") == 0);
    CHECK(buf_append_char(&b, ' ') == 0);
    CHECK(buf_append(&b, "world", 5) == 0);
    CHECK(b.len == 11);
    CHECK(strcmp(buf_cstr(&b), "hello world") == 0);
    for (i = 0; i < 1000; i++)
        CHECK(buf_append_char(&b, 'x') == 0);
    CHECK(b.len == 1011 && b.cap >= b.len);
    buf_free(&b);
    CHECK(b.data == NULL && b.len == 0);
    buf_free(&b);

    CHECK(checked_add_size(1, 2, &r) == 0 && r == 3);
    CHECK(checked_add_size(SIZE_MAX, 1, &r) == -1);
    CHECK(checked_mul_size(SIZE_MAX, 2, &r) == -1);
    CHECK(checked_mul_size(0, SIZE_MAX, &r) == 0 && r == 0);
}

static void test_parse(void)
{
    char k[STRKIT_KEY_CAP], v[STRKIT_VAL_CAP];
    const char *l = "  name =  hello world  ";

    CHECK(parse_line(l, strlen(l), k, sizeof k, v, sizeof v) == 1);
    CHECK(strcmp(k, "name") == 0 && strcmp(v, "hello world") == 0);
    CHECK(parse_line("# c", 3, k, sizeof k, v, sizeof v) == 0);
    CHECK(parse_line("   ", 3, k, sizeof k, v, sizeof v) == 0);
    CHECK(parse_line("novalue", 7, k, sizeof k, v, sizeof v) == -1);
    CHECK(parse_line("=x", 2, k, sizeof k, v, sizeof v) == -1);
    CHECK(parse_line("a b=c", 5, k, sizeof k, v, sizeof v) == -1);
    CHECK(validate_len(3, 3) == 0 && validate_len(4, 3) == -1);
}

static void test_cfg(void)
{
    cfg *c = cfg_new();

    CHECK(c != NULL);
    CHECK(cfg_load(c, "a=1\n# note\n\nb = two\r\nc=\n") == 0);
    CHECK(cfg_count(c) == 3);
    CHECK(strcmp(cfg_get(c, "a"), "1") == 0);
    CHECK(strcmp(cfg_get(c, "b"), "two") == 0);
    CHECK(strcmp(cfg_get(c, "c"), "") == 0);
    CHECK(cfg_get(c, "zzz") == NULL);
    CHECK(cfg_set(c, "a", "9") == 0 && strcmp(cfg_get(c, "a"), "9") == 0);
    CHECK(cfg_count(c) == 3);
    CHECK(cfg_set(c, "bad key", "x") == -1);
    CHECK(cfg_load(c, "oops\n") == -1);
    cfg_free(c);
    cfg_free(NULL);
}

static void test_path(void)
{
    char out[64];

    CHECK(safe_join("/srv/cfg", "a.cfg", out, sizeof out) == 0);
    CHECK(strcmp(out, "/srv/cfg/a.cfg") == 0);
    CHECK(safe_join("/srv/cfg/", "d/a.cfg", out, sizeof out) == 0);
    CHECK(strcmp(out, "/srv/cfg/d/a.cfg") == 0);
    CHECK(safe_join("/srv/cfg", "../x", out, sizeof out) == -1);
    CHECK(safe_join("/srv/cfg", "d/../../x", out, sizeof out) == -1);
    CHECK(safe_join("/srv/cfg", "/etc/passwd", out, sizeof out) == -1);
    CHECK(safe_join("/srv/cfg", "..a", out, sizeof out) == 0);
    CHECK(safe_join("/srv/cfg", "a.cfg", out, 8) == -1);
}

int main(void)
{
    test_buf();
    test_parse();
    test_cfg();
    test_path();
    printf("visible: %d checks passed\n", ran);
    return 0;
}

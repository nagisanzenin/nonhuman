/*
 * path.c - filesystem path helpers.  See path.h.
 */
#include "path.h"

#include "buf.h"

#include <string.h>

/* True if the component starting at s (ending at '/' or NUL) is "..". */
static int is_dotdot(const char *s)
{
    return s[0] == '.' && s[1] == '.' && (s[2] == '/' || s[2] == '\0');
}

int safe_join(const char *root, const char *name, char *out, size_t outlen)
{
    size_t rlen, nlen, total;
    const char *p;
    int need_slash;

    if (out != NULL && outlen > 0)
        out[0] = '\0';
    if (root == NULL || name == NULL || out == NULL || root[0] == '\0' ||
        name[0] == '\0' || name[0] == '/' || strchr(name, '\\') != NULL)
        return -1;

    /* Walk the components of name looking for "..". */
    for (p = name; *p != '\0';) {
        if (is_dotdot(p))
            return -1;
        p = strchr(p, '/');
        if (p == NULL)
            break;
        p++;
    }

    rlen = strlen(root);
    nlen = strlen(name);
    need_slash = root[rlen - 1] != '/';

    if (checked_add_size(rlen, nlen, &total) != 0 ||
        checked_add_size(total, (size_t)need_slash + 1, &total) != 0 ||
        total > outlen)
        return -1;

    memcpy(out, root, rlen);
    if (need_slash)
        out[rlen++] = '/';
    memcpy(out + rlen, name, nlen + 1);
    return 0;
}

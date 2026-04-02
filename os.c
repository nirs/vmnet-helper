// SPDX-FileCopyrightText: The vmnet-helper authors
// SPDX-License-Identifier: Apache-2.0

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/sysctl.h>

#include "log.h"
#include "os.h"

int os_product_version(struct os_version *v)
{
    char buf[20];
    size_t len = sizeof(buf);

    if (sysctlbyname("kern.osproductversion", buf, &len, NULL, 0) != 0) {
        WARNF("sysctlbyname(kern.osproductversion): %s", strerror(errno));
        return -1;
    }

    char *s = buf;
    int *numbers[] = {&v->major, &v->minor, &v->point};
    for (unsigned i = 0; i < 3; i++) {
        char *p = strsep(&s, ".");
        if (p == NULL) {
            break;
        }
        *numbers[i] = atoi(p);
    }

    return 0;
}

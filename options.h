// SPDX-FileCopyrightText: The vmnet-helper authors
// SPDX-License-Identifier: Apache-2.0

#ifndef OPTIONS_H
#define OPTIONS_H

#include <unistd.h>
#include <uuid/uuid.h>

struct options {
    int fd;
    uint32_t operation_mode;
    uuid_t interface_id;
    const char *start_address;
    const char *end_address;
    const char *subnet_mask;
    const char *shared_interface;
    uid_t uid;
    gid_t gid;
};

void parse_options(struct options *opts, int argc, char **argv);

#endif // OPTIONS_H

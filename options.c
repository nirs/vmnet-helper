// SPDX-FileCopyrightText: The vmnet-helper authors
// SPDX-License-Identifier: Apache-2.0

#include <arpa/inet.h>
#include <errno.h>
#include <getopt.h>
#include <limits.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syslimits.h>
#include <sys/types.h>
#include <sys/un.h>
#include <vmnet/vmnet.h>
#include <xpc/xpc.h>

#include "log.h"
#include "options.h"
#include "version.h"

bool verbose;

static void usage(int code)
{
    const char *msg =
"\n"
"Use vmnet interface without privileges\n"
"\n"
"    vmnet-helper (--fd FD|--socket SOCKET) [--interface-id UUID]\n"
"                 [--operation-mode shared|bridged|host] [--shared-interface NAME]\n"
"                 [--start-address ADDR] [--end-address ADDR] [--subnet-mask MASK]\n"
"                 [--enable-tso] [--enable-checksum-offload] [--enable-isolation]\n"
"                 [--list-shared-interfaces]\n"
"                 [-v|--verbose] [--version] [-h|--help]\n"
"\n";
    fputs(msg, stderr);
    exit(code);
}

enum {
    OPT_OPERATION_MODE = CHAR_MAX + 1,
    OPT_SHARED_INTERFACE,
    OPT_START_ADDRESS,
    OPT_END_ADDRESS,
    OPT_SUBNET_MASK,
    OPT_ENABLE_TSO,
    OPT_ENABLE_CHECKSUM_OFFLOAD,
    OPT_ENABLE_ISOLATION,
    OPT_LIST_SHARED_INTERFACES,
    OPT_VERSION,
};

static const char *short_options = ":f:s:i:vh";

static struct option long_options[] = {
    {"fd",                      required_argument,  0,  'f'},
    {"socket",                  required_argument,  0,  's'},
    {"interface-id",            required_argument,  0,  'i'},
    {"operation-mode",          required_argument,  0,  OPT_OPERATION_MODE},
    {"shared-interface",        required_argument,  0,  OPT_SHARED_INTERFACE},
    {"start-address",           required_argument,  0,  OPT_START_ADDRESS},
    {"end-address",             required_argument,  0,  OPT_END_ADDRESS},
    {"subnet-mask",             required_argument,  0,  OPT_SUBNET_MASK},
    {"enable-tso",              no_argument,        0,  OPT_ENABLE_TSO},
    {"enable-checksum-offload", no_argument,        0,  OPT_ENABLE_CHECKSUM_OFFLOAD},
    {"enable-isolation",        no_argument,        0,  OPT_ENABLE_ISOLATION},
    {"list-shared-interfaces",  no_argument,        0,  OPT_LIST_SHARED_INTERFACES},
    {"verbose",                 no_argument,        0,  'v'},
    {"version",                 no_argument,        0,  OPT_VERSION},
    {"help",                    no_argument,        0,  'h'},
    {0,                         0,                  0,  0},
};

static void parse_fd(const char *arg, int *fd)
{
    char *end;
    errno = 0;
    long value = strtol(arg, &end, 10);
    if (errno != 0) {
        // EINVAL, ERANGE
        ERRORF("Invalid fd '%s': %s", arg, strerror(errno));
        usage(1);
    }
    if (*end != 0 || value < 0 || value > INT_MAX) {
        // Empty string, trailing characters or out of range.
        ERRORF("Invalid fd '%s'", arg);
        usage(1);
    }
    *fd = value;
}

static void parse_socket(const char *arg, const char **sock)
{
    struct sockaddr_un address;
    size_t max_len = sizeof(address.sun_path) - 1;
    size_t len = strlen(arg);
    if (len > max_len) {
        ERRORF("Socket \"%s\" too long (%zu > %zu)", arg, len, max_len);
        usage(1);
    }
    *sock = arg;
}

static void parse_id(const char *arg, const char *name, unsigned int *id)
{
    char *end;
    errno = 0;
    long value = strtol(arg, &end, 10);
    if (errno != 0) {
        // EINVAL, ERANGE
        ERRORF("Invalid %s '%s': %s", name, arg, strerror(errno));
        usage(1);
    }
    if (*end != 0 || value < 0 || value > UID_MAX) {
        // Empty string, trailing characters or out of range.
        ERRORF("Invalid %s '%s'", name, arg);
        usage(1);
    }
    *id = value;
}

static void parse_interface_id(const char *arg, uuid_t uuid)
{
    if (uuid_parse(arg, uuid) < 0) {
        ERRORF("Invalid interface-id: \"%s\"", arg);
        exit(EXIT_FAILURE);
    }
}

static void parse_operation_mode(const char *arg, const char *name, uint32_t *mode)
{
    if (strcmp(arg, "shared") == 0) {
        *mode = VMNET_SHARED_MODE;
    } else if (strcmp(arg, "bridged") == 0) {
        *mode = VMNET_BRIDGED_MODE;
    } else if (strcmp(arg, "host") == 0) {
        *mode = VMNET_HOST_MODE;
    } else {
        ERRORF("Invalid %s: \"%s\"", name, arg);
        exit(EXIT_FAILURE);
    }
}

static void parse_address(const char *arg, const char *name, const char **p)
{
    struct in_addr addr;
    if (inet_aton(arg, &addr) == 0) {
        ERRORF("Invalid %s: \"%s\"]", name, arg);
        exit(EXIT_FAILURE);
    }
    *p = arg;
}

static void list_shared_interfaces(void)
{
    xpc_object_t list = vmnet_copy_shared_interface_list();
    if (list == NULL) {
        ERROR("Unable to list shared interfaces");
        exit(EXIT_FAILURE);
    }
    size_t count = xpc_array_get_count(list);
    for (size_t i = 0; i < count; i++) {
        printf("%s\n", xpc_array_get_string(list, i));
    }
    xpc_release(list);
    exit(0);
}

void parse_options(struct options *opts, int argc, char **argv)
{
    const char *optname;
    int c;

    /* Silence getopt_long error messages. */
    opterr = 0;

    while (1) {
        optname = argv[optind];
        c = getopt_long(argc, argv, short_options, long_options, NULL);

        if (c == -1)
            break;

        switch (c) {
        case 'h':
            usage(0);
            break;
        case 'f':
            parse_fd(optarg, &opts->fd);
            break;
        case 's':
            parse_socket(optarg, &opts->socket);
            break;
        case 'i':
            parse_interface_id(optarg, opts->interface_id);
            break;
        case OPT_OPERATION_MODE:
            parse_operation_mode(optarg, optname, &opts->operation_mode);
            break;
        case OPT_SHARED_INTERFACE:
            opts->shared_interface = optarg; // Validate?
            break;
        case OPT_START_ADDRESS:
            parse_address(optarg, optname, &opts->start_address);
            break;
        case OPT_END_ADDRESS:
            parse_address(optarg, optname, &opts->end_address);
            break;
        case OPT_SUBNET_MASK:
            parse_address(optarg, optname, &opts->subnet_mask);
            break;
        case OPT_ENABLE_TSO:
            opts->enable_tso = true;
            break;
        case OPT_ENABLE_CHECKSUM_OFFLOAD:
            opts->enable_checksum_offload = true;
            break;
        case OPT_ENABLE_ISOLATION:
            opts->enable_isolation = true;
            break;
        case OPT_LIST_SHARED_INTERFACES:
            list_shared_interfaces();
            break;
        case 'v':
            verbose = true;
            break;
        case OPT_VERSION:
            printf("version: %s\ncommit: %s\n", GIT_VERSION, GIT_COMMIT);
            exit(0);
        case ':':
            ERRORF("Option %s requires an argument", optname);
            exit(EXIT_FAILURE);
        case '?':
        default:
            ERRORF("Invalid option: %s", optname);
            exit(EXIT_FAILURE);
        }
    }

    if (opts->fd == -1 && opts->socket == NULL) {
        ERROR("Missing argument: either \"fd\" or \"socket\" required");
        usage(1);
    }

    if (opts->fd != -1 && opts->socket != NULL) {
        ERROR("Conflicting arguments: \"fd\" and \"socket\" are mutually exclusive");
        usage(1);
    }

    if (uuid_is_null(opts->interface_id)) {
        uuid_generate_random(opts->interface_id);
    }

    // When running via sudo we can get the real uid/gid via SUDO_*
    // environment variables. When using setuid bit, getuid()/getgid() return
    // the real uid/gid.

    if (opts->uid == 0) {
        const char *sudo_uid = getenv("SUDO_UID");
        if (sudo_uid != NULL) {
            parse_id(sudo_uid, "SUDO_UID", &opts->uid);
        } else {
            opts->uid = getuid();
        }
    }

    if (opts->gid == 0) {
        const char *sudo_gid = getenv("SUDO_GID");
        if (sudo_gid != NULL) {
            parse_id(sudo_gid, "SUDO_GID", &opts->gid);
        } else {
            opts->gid = getgid();
        }
    }

    if (opts->operation_mode == VMNET_BRIDGED_MODE && opts->shared_interface == NULL) {
        ERROR("Missing argument: shared-interface is required for operation-mode=bridged");
        exit(EXIT_FAILURE);
    }

    if (opts->enable_isolation && opts->operation_mode != VMNET_HOST_MODE) {
        ERROR("Conflicting arguments: enable-isolation requires operation-mode=host");
        exit(EXIT_FAILURE);
    }
}

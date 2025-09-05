// SPDX-FileCopyrightText: The vmnet-helper authors
// SPDX-License-Identifier: Apache-2.0

#include <arpa/inet.h>
#include <assert.h>
#include <errno.h>
#include <getopt.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>
#include <uuid/uuid.h>
#include <vmnet/vmnet.h>

#include "config.h"
#include "log.h"
#include "version.h"

// To keep it simple we always use the same file descriptor for the helper and
// command. Inheriting additional file descriptors is not supported.
const int HELPER_FD = 3;
const int COMMAND_FD = 4;

bool verbose = false;

// vmnet-helper arguments. Parsed arguments are appended to this list.
// We depend on sudoers configuration to allow vment-helper to run
// without a password and enable the closefrom_override option for this
// user. See sudoers.d/README.md for more info.
static char *helper_argv[32] = {
    "sudo",
    "--non-interactive",
    // Allow the helper to inherit file descriptor 3.
    "--close-from=4",
    PREFIX "/bin/vmnet-helper",
    "--fd=3",
    NULL,
};

static int helper_next = 5;

// Pointer to first command argument in argv.
static char **command_argv;

// We need to remember these for validation.
static uint32_t operation_mode;
static const char *shared_interface;
static bool enable_isolation;

enum {
    OPT_INTERFACE_ID = CHAR_MAX + 1,
    OPT_OPERATION_MODE,
    OPT_SHARED_INTERFACE,
    OPT_START_ADDRESS,
    OPT_END_ADDRESS,
    OPT_SUBNET_MASK,
    OPT_ENABLE_ISOLATION,
    OPT_VERSION
};

static const char *short_options = ":vh";

static struct option long_options[] = {
    // vmnet-helper options that can be specified via vmnet-client.
    {"interface-id",            required_argument,  0,  OPT_INTERFACE_ID},
    {"operation-mode",          required_argument,  0,  OPT_OPERATION_MODE},
    {"shared-interface",        required_argument,  0,  OPT_SHARED_INTERFACE},
    {"start-address",           required_argument,  0,  OPT_START_ADDRESS},
    {"end-address",             required_argument,  0,  OPT_END_ADDRESS},
    {"subnet-mask",             required_argument,  0,  OPT_SUBNET_MASK},
    {"enable-isolation",        no_argument,        0,  OPT_ENABLE_ISOLATION},
    {"verbose",                 no_argument,        0,  'v'},
    // Client options.
    {"version",                 no_argument,        0,  OPT_VERSION},
    {"help",                    no_argument,        0,  'h'},
    {0,                         0,                  0,  0},
};

static void usage(int code)
{
    const char *msg =
"\n"
"Run command with vmnet-helper\n"
"\n"
"    vmnet-client [--interface-id UUID] [--operation-mode shared|bridged|host]\n"
"                 [--start-address ADDR] [--end-address ADDR]\n"
"                 [--subnet-mask MASK] [--shared-interface NAME]\n"
"                 [--enable-isolation] [-v|--verbose] [--version] [-h|--help]\n"
"                 -- command ...\n"
"\n";
    fputs(msg, stderr);
    exit(code);
}

static void append_helper_arg(char *arg)
{
    if (helper_next == sizeof(helper_argv) - 1) {
        ERROR("Too many arguments");
        exit(EXIT_FAILURE);
    }

    helper_argv[helper_next] = arg;
    helper_next++;
}

static void validate_interface_id(const char *arg)
{
    uuid_t uuid;
    if (uuid_parse(arg, uuid) < 0) {
        ERRORF("Invalid interface-id: \"%s\"", arg);
        exit(EXIT_FAILURE);
    }
}

static void validate_operation_mode(const char *arg)
{
    if (strcmp(arg, "shared") == 0) {
        operation_mode = VMNET_SHARED_MODE;
    } else if (strcmp(arg, "bridged") == 0) {
        operation_mode = VMNET_BRIDGED_MODE;
    } else if (strcmp(arg, "host") == 0) {
        operation_mode = VMNET_HOST_MODE;
    } else {
        ERRORF("Invalid operation-mode: \"%s\"", arg);
        exit(EXIT_FAILURE);
    }
}

static void validate_address(const char *arg, const char *name)
{
    struct in_addr addr;
    if (inet_aton(arg, &addr) == 0) {
        ERRORF("Invalid %s: \"%s\"]", name, arg);
        exit(EXIT_FAILURE);
    }
}

// Parse and validate helper arguments in argv and append to helper_argv, and
// initialize command_argv to point to first command argument.
static void parse_options(int argc, char **argv)
{
    const char *optname;
    int c;

    // Silence getopt_long error messages.
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
        case OPT_INTERFACE_ID:
            validate_interface_id(optarg);
            append_helper_arg("--interface-id");
            append_helper_arg(optarg);
            break;
        case OPT_OPERATION_MODE:
            validate_operation_mode(optarg);
            append_helper_arg("--operation-mode");
            append_helper_arg(optarg);
            break;
        case OPT_SHARED_INTERFACE:
            shared_interface = optarg;
            append_helper_arg("--shared-interface");
            append_helper_arg(optarg);
            break;
        case OPT_START_ADDRESS:
            validate_address(optarg, optname);
            append_helper_arg("--start-address");
            append_helper_arg(optarg);
            break;
        case OPT_END_ADDRESS:
            validate_address(optarg, optname);
            append_helper_arg("--end-address");
            append_helper_arg(optarg);
            break;
        case OPT_SUBNET_MASK:
            validate_address(optarg, optname);
            append_helper_arg("--subnet-mask");
            append_helper_arg(optarg);
            break;
        case OPT_ENABLE_ISOLATION:
            enable_isolation = true;
            append_helper_arg("--enable-isolation");
            break;
        case 'v':
            verbose = true;
            append_helper_arg("--verbose");
            break;
        case OPT_VERSION:
            printf("%s\n%s\n", GIT_VERSION, GIT_COMMIT_SHA);
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

    if (operation_mode == VMNET_BRIDGED_MODE && shared_interface == NULL) {
        ERROR("Missing argument: shared-interface is required for operation-mode=bridged");
        exit(EXIT_FAILURE);
    }

    if (enable_isolation && operation_mode != VMNET_HOST_MODE) {
        ERROR("Conflicting arguments: enable-isolation requires operation-mode=host");
        exit(EXIT_FAILURE);
    }

    // The rest of the arguments are the command arguments.
    command_argv = &argv[optind];

    if (command_argv[0] == NULL) {
        ERROR("No command specified");
        usage(1);
    }
}

static void set_socket_buffers(int fd)
{
    // Setting socket buffer size is a performance optimization so we don't fail on
    // errors.

    const int sndbuf_size = SEND_BUFFER_SIZE;
    if (setsockopt(fd, SOL_SOCKET, SO_SNDBUF, &sndbuf_size, sizeof(sndbuf_size)) < 0) {
        WARNF("setsockopt: %s", strerror(errno));
    }

    const int rcvbuf_size = RECV_BUFFER_SIZE;
    if (setsockopt(fd, SOL_SOCKET, SO_RCVBUF, &rcvbuf_size, sizeof(rcvbuf_size)) < 0) {
        WARNF("setsockopt: %s", strerror(errno));
    }
}

static void create_socketpair(void)
{
    // Make sure descriptors 3 and 4 are available so socketpair() can reuse them.

    close(HELPER_FD);
    close(COMMAND_FD);

    int fds[2];
    if (socketpair(PF_LOCAL, SOCK_DGRAM, 0, fds) < 0) {
        ERRORF("socketpair: %s", strerror(errno));
        exit(EXIT_FAILURE);
    }

    // Due to reusing first available descriptor, the descriptors should be at 3
    // and 4. In the unliekly case when some standard descriptos are closed, we
    // dup them to the right place. Moving fds[1] first to ensure we don't close
    // fds[0]. If the descriptors are already in place dup2 does nothing.

    if (dup2(fds[1], COMMAND_FD) < 0) {
        ERRORF("dup2: %s", strerror(errno));
        exit(EXIT_FAILURE);
    }

    if (dup2(fds[0], HELPER_FD) < 0) {
        ERRORF("dup2: %s", strerror(errno));
        exit(EXIT_FAILURE);
    }

    set_socket_buffers(HELPER_FD);
    set_socket_buffers(COMMAND_FD);
}

int main(int argc, char **argv)
{
    parse_options(argc, argv);

    create_socketpair();

    pid_t helper_pid = fork();
    if (helper_pid < 0) {
        ERRORF("fork: %s", strerror(errno));
        exit(EXIT_FAILURE);
    }

    if (helper_pid == 0) {
        // Child: execute vmnet-helper.
        if (execvp(helper_argv[0], helper_argv) < 0) {
            ERRORF("execvp: %s", strerror(errno));
            exit(EXIT_FAILURE);
        }
    } else {
        // Parent: execute the command.
        if (execvp(command_argv[0], command_argv) < 0) {
            ERRORF("execvp: %s", strerror(errno));
            exit(EXIT_FAILURE);
        }
    }
}

// SPDX-FileCopyrightText: The vmnet-helper authors
// SPDX-License-Identifier: Apache-2.0

#include <arpa/inet.h>
#include <assert.h>
#include <errno.h>
#include <getopt.h>
#include <limits.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>
#include <uuid/uuid.h>

#include "config.h"
#include "log.h"
#include "version.h"

struct client_options {
    // Helper options passed to the helper.
    char *interface_id;
    char *operation_mode;
    char *start_address;
    char *end_address;
    char *subnet_mask;
    char *shared_interface;
    bool enable_isolation;
};

// To keep it simple we always use the same file descriptor for the helper and
// command. Inheriting additional file descriptors is not supported.
static const int HELPER_FD = 3;
static const int COMMAND_FD = 4;

bool verbose = false;

// Client options parsed from the command line.
static struct client_options options;

// vmnet-helper arguments. Built by build_helper_argv().
static char *helper_argv[32];
static int helper_next = 0;

// Pointer to first command argument in argv.
static char **command_argv;

static pid_t helper_pid = -1;
static pid_t command_pid = -1;
static volatile sig_atomic_t terminated;

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
        ERROR("[client] too many arguments");
        exit(EXIT_FAILURE);
    }

    helper_argv[helper_next] = arg;
    helper_next++;
}

static void build_helper_argv(void)
{
    // We depend on sudoers configuration to allow vmnet-helper to run without
    // a password and enable the closefrom_override option for this user. See
    // sudoers.d/README.md for more info.
    append_helper_arg("sudo");
    append_helper_arg("--non-interactive");
    // Allow the helper to inherit file descriptor 3.
    append_helper_arg("--close-from=4");

    append_helper_arg(PREFIX "/bin/vmnet-helper");
    append_helper_arg("--fd=3");

    if (options.interface_id) {
        append_helper_arg("--interface-id");
        append_helper_arg(options.interface_id);
    }

    if (options.operation_mode) {
        append_helper_arg("--operation-mode");
        append_helper_arg(options.operation_mode);
    }

    if (options.start_address) {
        append_helper_arg("--start-address");
        append_helper_arg(options.start_address);
    }

    if (options.end_address) {
        append_helper_arg("--end-address");
        append_helper_arg(options.end_address);
    }

    if (options.subnet_mask) {
        append_helper_arg("--subnet-mask");
        append_helper_arg(options.subnet_mask);
    }

    if (options.shared_interface) {
        append_helper_arg("--shared-interface");
        append_helper_arg(options.shared_interface);
    }

    if (options.enable_isolation) {
        append_helper_arg("--enable-isolation");
    }

    if (verbose) {
        append_helper_arg("--verbose");
    }
}

static bool is_shared(const char *mode)
{
    return mode && strcmp(mode, "shared") == 0;
}

static bool is_host(const char *mode)
{
    return mode && strcmp(mode, "host") == 0;
}

static bool is_bridged(const char *mode)
{
    return mode && strcmp(mode, "bridged") == 0;
}

static void validate_interface_id(const char *arg)
{
    uuid_t uuid;
    if (uuid_parse(arg, uuid) < 0) {
        ERRORF("[client] invalid interface-id: \"%s\"", arg);
        exit(EXIT_FAILURE);
    }
}

static void validate_operation_mode(const char *arg)
{
    if (!is_shared(arg) && !is_host(arg) && !is_bridged(arg)) {
        ERRORF("[client] invalid operation-mode: \"%s\"", arg);
        exit(EXIT_FAILURE);
    }
}

static void validate_address(const char *arg, const char *name)
{
    struct in_addr addr;
    if (inet_aton(arg, &addr) == 0) {
        ERRORF("[client] invalid %s: \"%s\"]", name, arg);
        exit(EXIT_FAILURE);
    }
}

// Parse and validate helper arguments in argv and initialize command_argv to
// point to first command argument.
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
            options.interface_id = optarg;
            break;
        case OPT_OPERATION_MODE:
            validate_operation_mode(optarg);
            options.operation_mode = optarg;
            break;
        case OPT_SHARED_INTERFACE:
            options.shared_interface = optarg;
            break;
        case OPT_START_ADDRESS:
            validate_address(optarg, optname);
            options.start_address = optarg;
            break;
        case OPT_END_ADDRESS:
            validate_address(optarg, optname);
            options.end_address = optarg;
            break;
        case OPT_SUBNET_MASK:
            validate_address(optarg, optname);
            options.subnet_mask = optarg;
            break;
        case OPT_ENABLE_ISOLATION:
            options.enable_isolation = true;
            break;
        case 'v':
            verbose = true;
            break;
        case OPT_VERSION:
            printf("version: %s\ncommit: %s\n", GIT_VERSION, GIT_COMMIT);
            exit(0);
        case ':':
            ERRORF("[client] option %s requires an argument", optname);
            exit(EXIT_FAILURE);
        case '?':
        default:
            ERRORF("[client] invalid option: %s", optname);
            exit(EXIT_FAILURE);
        }
    }

    if (is_bridged(options.operation_mode) && options.shared_interface == NULL) {
        ERROR("[client] missing argument: shared-interface is required for operation-mode=bridged");
        exit(EXIT_FAILURE);
    }

    if (options.enable_isolation && !is_host(options.operation_mode)) {
        ERROR("[client] conflicting arguments: enable-isolation requires operation-mode=host");
        exit(EXIT_FAILURE);
    }

    // The rest of the arguments are the command arguments.
    command_argv = &argv[optind];

    if (command_argv[0] == NULL) {
        ERROR("[client] no command specified");
        usage(1);
    }
}

static void set_socket_buffers(int fd)
{
    // Setting socket buffer size is a performance optimization so we don't fail on
    // errors.

    const int sndbuf_size = SEND_BUFFER_SIZE;
    if (setsockopt(fd, SOL_SOCKET, SO_SNDBUF, &sndbuf_size, sizeof(sndbuf_size)) < 0) {
        WARNF("[client] setsockopt: %s", strerror(errno));
    }

    const int rcvbuf_size = RECV_BUFFER_SIZE;
    if (setsockopt(fd, SOL_SOCKET, SO_RCVBUF, &rcvbuf_size, sizeof(rcvbuf_size)) < 0) {
        WARNF("[client] setsockopt: %s", strerror(errno));
    }
}

static void create_socketpair(void)
{
    // Make sure descriptors 3 and 4 are available so socketpair() can reuse them.

    close(HELPER_FD);
    close(COMMAND_FD);

    int fds[2];
    if (socketpair(PF_LOCAL, SOCK_DGRAM, 0, fds) < 0) {
        ERRORF("[client] socketpair: %s", strerror(errno));
        exit(EXIT_FAILURE);
    }

    // Due to reusing first available descriptor, the descriptors should be at 3
    // and 4. In the unliekly case when some standard descriptos are closed, we
    // dup them to the right place. Moving fds[1] first to ensure we don't close
    // fds[0]. If the descriptors are already in place dup2 does nothing.

    if (dup2(fds[1], COMMAND_FD) < 0) {
        ERRORF("[client] dup2: %s", strerror(errno));
        exit(EXIT_FAILURE);
    }

    if (dup2(fds[0], HELPER_FD) < 0) {
        ERRORF("[client] dup2: %s", strerror(errno));
        exit(EXIT_FAILURE);
    }

    set_socket_buffers(HELPER_FD);
    set_socket_buffers(COMMAND_FD);
}

static void become_process_group_leader(void)
{
    if (getpid() == getpgid(0)) {
        return;
    }

    if (setpgid(0, 0) == -1) {
        ERRORF("[client] setpgid: %s", strerror(errno));
        exit(EXIT_FAILURE);
    }

    DEBUGF("[client] created new process group (pgid %d)", getpgid(0));
}

static void terminate_process_group(void)
{
    DEBUGF("[client] terminating process group (pgid %d)", getpgid(0));

    signal(SIGTERM, SIG_IGN);

    if (killpg(0, SIGTERM) == -1 && errno != ESRCH) {
        ERRORF("failed to terminate process group: %s", strerror(errno));
        return;
    }

    DEBUG("[client] waiting for children");

    while(wait(NULL) > 0);

    DEBUG("[client] children terminated");
}

static void defer_terminate_process_group(void)
{
    if (atexit(terminate_process_group) == -1) {
        ERRORF("[client] atexit: %s", strerror(errno));
        exit(EXIT_FAILURE);
    }
}

static void start_helper(void)
{
    helper_pid = fork();
    if (helper_pid < 0) {
        ERRORF("[client] fork: %s", strerror(errno));
        exit(EXIT_FAILURE);
    }

    if (helper_pid == 0) {
        // Don't inherit the command socket.
        close(COMMAND_FD);

        if (execvp(helper_argv[0], helper_argv) < 0) {
            ERRORF("[client] execvp: %s", strerror(errno));
            exit(EXIT_FAILURE);
        }
    }

    // Forget the helper socket.
    close(HELPER_FD);

    DEBUGF("[client] started helper (pid %d)", helper_pid);
}

static void start_command(void)
{
    command_pid = fork();
    if (command_pid < 0) {
        ERRORF("[client] fork: %s", strerror(errno));
        exit(EXIT_FAILURE);
    }

    if (command_pid == 0) {
        // Don't inherit the helper socket.
        close(HELPER_FD);

        if (execvp(command_argv[0], command_argv) < 0) {
            ERRORF("[client] execvp: %s", strerror(errno));
            exit(EXIT_FAILURE);
        }
    }

    // Forget the command socket.
    close(COMMAND_FD);

    DEBUGF("[client] started command (pid %d)", command_pid);
}

static int wait_for_command(void)
{
    while (1) {
        pid_t result;
        int status;

        result = waitpid(command_pid, &status, 0);

        if (result == -1) {
            if (errno != EINTR) {
                ERRORF("[client] waitpid: %s", strerror(errno));
                exit(EXIT_FAILURE);
            }
            if (terminated) {
                return 128 + terminated;
            }
        }

        if (WIFEXITED(status)) {
            int exit_status = WEXITSTATUS(status);
            DEBUGF("[client] command terminated with exit status %d", exit_status);
            command_pid = -1;
            return exit_status;
        }

        if (WIFSIGNALED(status)) {
            int term_signal = WTERMSIG(status);
            DEBUGF("[client] command terminated by signal %d", term_signal);
            command_pid = -1;
            return 128 + term_signal;
        }
    }
}

static void handle_signal(int signo)
{
    terminated = signo;
}

static void setup_signals(void)
{
    struct sigaction sa;
    sa.sa_handler = handle_signal;
    sigemptyset(&sa.sa_mask);

    // Disable SA_RESTART so waitpid() can be interrupted.
    sa.sa_flags = 0;

    if (sigaction(SIGTERM, &sa, NULL) == -1) {
        ERRORF("[client] signal: %s", strerror(errno));
        exit(EXIT_FAILURE);
    }

    if (sigaction(SIGINT, &sa, NULL) == -1) {
        ERRORF("[client] signal: %s", strerror(errno));
        exit(EXIT_FAILURE);
    }
}

int main(int argc, char **argv)
{
    parse_options(argc, argv);
    build_helper_argv();

    setup_signals();
    become_process_group_leader();
    defer_terminate_process_group();

    create_socketpair();
    start_helper();
    start_command();

    return wait_for_command();
}

// SPDX-FileCopyrightText: The vmnet-helper authors
// SPDX-License-Identifier: Apache-2.0

#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>
#include <jansson.h>

#include "config.h"

// To keep it simple we always use the same file descriptor for the helper and
// command. Inheriting additional file descriptors is not supported.
const int HELPER_FD = 3;
const int COMMAND_FD = 4;

static void set_socket_buffers(int fd)
{
    // Setting socket buffer size is a performance optimization so we don't fail on
    // errors.

    if (setsockopt(fd, SOL_SOCKET, SO_SNDBUF, &SNDBUF_SIZE, sizeof(SNDBUF_SIZE)) < 0) {
        perror("setsockopt");
    }
    if (setsockopt(fd, SOL_SOCKET, SO_RCVBUF, &RCVBUF_SIZE, sizeof(RCVBUF_SIZE)) < 0) {
        perror("setsockopt");
    }
}

static void create_socketpair(void)
{
    // Make sure descriptors 3 and 4 are available so socketpair() can reuse them.

    close(HELPER_FD);
    close(COMMAND_FD);

    int fds[2];
    if (socketpair(PF_LOCAL, SOCK_DGRAM, 0, fds) < 0) {
        perror("socketpair");
        exit(EXIT_FAILURE);
    }

    // Due to reusing first available descriptor, the descriptors should be at 3
    // and 4. In the unliekly case when some standard descriptos are closed, we
    // dup them to the right place. Moving fds[1] first to ensure we don't close
    // fds[0]. If the descriptors are already in place dup2 does nothing.

    if (dup2(fds[1], COMMAND_FD) < 0) {
        perror("dup2");
        exit(EXIT_FAILURE);
    }

    if (dup2(fds[0], HELPER_FD) < 0) {
        perror("dup2");
        exit(EXIT_FAILURE);
    }

    set_socket_buffers(HELPER_FD);
    set_socket_buffers(COMMAND_FD);
}

static void exec_helper(int stdout_fd)
{
    // Replace child standard output with the pipe.
    if (dup2(stdout_fd, STDOUT_FILENO) < 0) {
        perror("dup2");
        _exit(EXIT_FAILURE);
    }

    // We depend on sudoers configuration to allow vment-helper to run
    // without a password and enable the closefrom_override option for this
    // user. See sudoers.d/README.md for more info.
    char *helper_argv[] = {
        "sudo",
        "--non-interactive",
        // Allow the helper to inherit file descriptor 3.
        "--close-from=4",
        PREFIX "/bin/vmnet-helper",
        "--fd=3",
        NULL,
    };

    if (execvp(helper_argv[0], helper_argv) < 0) {
        perror("execvp");
        exit(EXIT_FAILURE);
    }
}

static void exec_command(char **argv, int stdout_fd)
{
    // Read the first json message from helper stdout.
    json_error_t error;
    json_auto_t *root = json_loadfd(stdout_fd, JSON_DISABLE_EOF_CHECK, &error);
    if (root == NULL) {
        fprintf(stderr, "failed to read helper json output: %s\n", error.text);
        exit(EXIT_FAILURE);
    }

    // The command should not inherit helper stdout fd.
    close(stdout_fd);

    const char *mac_address;
    if (json_unpack(root, "{s:s}", "vmnet_mac_address", &mac_address) < 0) {
        fprintf(stderr, "failed to parse mac address\n");
        exit(EXIT_FAILURE);
    }

    printf("Using MAC address: \"%s\"\n", mac_address);

    // TODO: inject command fd and mac address into the command arguments.

    if (execvp(argv[0], argv) < 0) {
        perror("execvp");
        exit(EXIT_FAILURE);
    }
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "Usage: vmnet-client command ...\n");
        exit(EXIT_FAILURE);
    }

    create_socketpair();

    // Open a pipe to read from helper stdandard output.
    int fds[2];
    if (pipe(fds) < 0) {
        perror("pipe");
        exit(EXIT_FAILURE);
    }

    pid_t helper_pid = fork();
    if (helper_pid < 0) {
        perror("fork");
        exit(EXIT_FAILURE);
    }

    if (helper_pid == 0) {
        // Child.
        close(fds[0]);
        exec_helper(fds[1]);
    } else {
        // Parent.
        close(fds[1]);
        exec_command(argv + 1, fds[0]);
    }
}

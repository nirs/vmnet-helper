// SPDX-FileCopyrightText: The vmnet-helper authors
// SPDX-License-Identifier: Apache-2.0

#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#include "config.h"
#include "log.h"

// To keep it simple we always use the same file descriptor for the helper and
// command. Inheriting additional file descriptors is not supported.
const int HELPER_FD = 3;
const int COMMAND_FD = 4;

bool verbose = false;

static void set_socket_buffers(int fd)
{
    // Setting socket buffer size is a performance optimization so we don't fail on
    // errors.

    if (setsockopt(fd, SOL_SOCKET, SO_SNDBUF, &SNDBUF_SIZE, sizeof(SNDBUF_SIZE)) < 0) {
        ERRORF("setsockopt: %s", strerror(errno));
    }
    if (setsockopt(fd, SOL_SOCKET, SO_RCVBUF, &RCVBUF_SIZE, sizeof(RCVBUF_SIZE)) < 0) {
        ERRORF("setsockopt: %s", strerror(errno));
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
    if (argc < 2) {
        fprintf(stderr, "Usage: vmnet-client command ...\n");
        exit(EXIT_FAILURE);
    }

    create_socketpair();

    pid_t helper_pid = fork();
    if (helper_pid < 0) {
        ERRORF("fork: %s", strerror(errno));
        exit(EXIT_FAILURE);
    }

    if (helper_pid == 0) {
        // Child: start vment-helper.
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
            ERRORF("execvp: %s", strerror(errno));
            exit(EXIT_FAILURE);
        }
    } else {
        // Parent: start the commmnad.
        char **command_argv = argv + 1;
        if (execvp(command_argv[0], command_argv) < 0) {
            ERRORF("execvp: %s", strerror(errno));
            exit(EXIT_FAILURE);
        }
    }
}

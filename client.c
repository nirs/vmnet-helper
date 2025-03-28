// SPDX-FileCopyrightText: The vmnet-helper authors
// SPDX-License-Identifier: Apache-2.0

#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

// Apple recommend receive buffer size to be 4 times the size of the send
// buffer size, but send buffer size is not used to allocate a buffer in
// datagram sockets, it only limits the maximum packet size.
// Must be larger than TSO packets size (65550 bytes).
static const int SNDBUF_SIZE = 65 * 1024;

// The receive buffer size determine how many packets can be queued by the
// peer. Using bigger receive buffer size make ENOBUFS error less likey for the
// peer and improves throughput.
static const int RCVBUF_SIZE = 4 * 1024 * 1024;

static void set_socket_buffers(int fd)
{
    // Setting socket buffer size is a performance optimization - don't fail on
    // errors.
    if (setsockopt(fd, SOL_SOCKET, SO_SNDBUF, &SNDBUF_SIZE, sizeof(SNDBUF_SIZE)) < 0) {
        perror("setsockopt");
    }

    if (setsockopt(fd, SOL_SOCKET, SO_RCVBUF, &RCVBUF_SIZE, sizeof(RCVBUF_SIZE)) < 0) {
        perror("setsockopt");
    }
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "Usage: vmnet-client command ...\n");
        exit(EXIT_FAILURE);
    }

    int fds[2];
    if (socketpair(PF_LOCAL, SOCK_DGRAM, 0, fds) < 0) {
        perror("socketpair");
        exit(EXIT_FAILURE);
    }

    assert(fds[0] == 3);
    assert(fds[1] == 4);

    set_socket_buffers(fds[0]);
    set_socket_buffers(fds[1]);

    pid_t helper_pid = fork();
    if (helper_pid < 0) {
        perror("fork");
        exit(EXIT_FAILURE);
    }

    if (helper_pid == 0) {
        // Child
        char *helper_argv[] = {
            "sudo",
            "--non-interactive",
            "--close-from=4",
            "/opt/vmnet-helper/bin/vmnet-helper",
            "--fd=3",
            NULL,
        };
        if (execvp(helper_argv[0], helper_argv) < 0) {
            perror("execvp");
            exit(EXIT_FAILURE);
        }
    } else {
        // Parent
        char **command_argv = argv + 1;
        if (execvp(command_argv[0], command_argv) < 0) {
            perror("execvp");
            exit(EXIT_FAILURE);
        }
    }
}

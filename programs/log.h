// SPDX-FileCopyrightText: The vmnet-helper authors
// SPDX-License-Identifier: Apache-2.0

#ifndef LOG_H
#define LOG_H

#include <stdbool.h>

extern bool verbose;

#define DEBUG(msg) \
    do { \
        if (verbose) \
            fprintf(stderr, "DEBUG " msg "\n"); \
    } while (0)

#define INFO(msg)   fprintf(stderr, "INFO  " msg "\n")
#define WARN(msg)   fprintf(stderr, "WARN  " msg "\n")
#define ERROR(msg)  fprintf(stderr, "ERROR " msg "\n")

#define DEBUGF(fmt, ...) \
    do { \
        if (verbose) \
            fprintf(stderr, "DEBUG " fmt "\n", __VA_ARGS__); \
    } while (0)

#define INFOF(fmt, ...)     fprintf(stderr, "INFO  " fmt "\n", __VA_ARGS__)
#define WARNF(fmt, ...)     fprintf(stderr, "WARN  " fmt "\n", __VA_ARGS__)
#define ERRORF(fmt, ...)    fprintf(stderr, "ERROR " fmt "\n", __VA_ARGS__)

#endif // LOG_H

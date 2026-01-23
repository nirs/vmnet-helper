// SPDX-FileCopyrightText: The vmnet-broker authors
// SPDX-License-Identifier: Apache-2.0

#ifndef VMNET_BROKER_H
#define VMNET_BROKER_H

// Suppress warnings for nullability annotations (_Nullable, _Nonnull).
// These are Clang extensions for documentation and static analysis.
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wnullability-extension"

#include <xpc/xpc.h>

// The broker Mach service name.
#define MACH_SERVICE_NAME "com.github.nirs.vmnet-broker"

// Request keys.
#define REQUEST_COMMAND "command"
#define REQUEST_NETWORK_NAME "network_name"

// Request commands.
#define COMMAND_ACQUIRE "acquire"

// Reply keys
#define REPLY_NETWORK "network"
#define REPLY_ERROR "error"

// Status codes

typedef enum {
    // Operation was successful.
    VMNET_BROKER_SUCCESS = 0,
    // Failed to send XPC message to broker.
    VMNET_BROKER_XPC_FAILURE = 1,
    // Broker returned invalid reply.
    VMNET_BROKER_INVALID_REPLY = 2,
    // Broker rejected the request because the user is not allowed to get the
    // network.
    VMNET_BROKER_NOT_ALLOWED = 3,
    // Broker rejected the request because the request was invalid.
    VMNET_BROKER_INVALID_REQUEST = 4,
    // Broker did not find the requested network in the broker configuration.
    VMNET_BROKER_NOT_FOUND = 5,
    // Broker failed to create the requested network.
    VMNET_BROKER_CREATE_FAILURE = 6,
    // Internal or unknown error.
    VMNET_BROKER_INTERNAL_ERROR = 7
} vmnet_broker_return_t;

/*!
 * @function vmnet_broker_acquire_network
 *
 * @abstract
 * Acquires a shared lock on a configured network, instantiating it if
 * necessary.
 *
 * @discussion
 * The specified `network_name` must exist in the broker's configuration. This
 * function retrieves a reference to the network if it already exists, or
 * instantiates it if needed.
 *
 * The shared lock ensures the network remains active as long as the calling
 * process is using it. The lock is automatically released when the process
 * terminates.
 *
 * @param network_name
 * The name of the network as defined in the broker configuration.
 *
 * @param status
 * Optional output parameter. On return, contains the status of the operation.
 *
 * @result
 * A retained xpc_object_t serialization on success, or NULL on failure. The
 * caller is responsible for releasing the returned object using
 * `xpc_release()`.
 */
xpc_object_t _Nullable vmnet_broker_acquire_network(
    const char *_Nonnull network_name, vmnet_broker_return_t *_Nullable status
);

/*!
 * @function vmnet_broker_strerror
 *
 * @abstract
 * Return description of the status returned from `vmnet_broker_start_session`.
 *
 * @param status
 * Status returned by `vmnet_broker_start_session`
 *
 * @result
 * Description of the status.
 */
const char *_Nonnull vmnet_broker_strerror(vmnet_broker_return_t status);

#pragma clang diagnostic pop

#endif // VMNET_BROKER_H

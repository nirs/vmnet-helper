// SPDX-FileCopyrightText: The vmnet-broker authors
// SPDX-License-Identifier: Apache-2.0

#include "vmnet-broker.h"
#include <xpc/xpc.h>

// The connection must be kept open during the lifetime of the client. The
// kernel invalidates the broker connection after the client terminates.
static xpc_connection_t connection;

static void connect_to_broker(void) {
    connection = xpc_connection_create_mach_service(MACH_SERVICE_NAME, NULL, 0);

    // Must set the event handler but we don't use it. Errors are logged when we
    // receive a reply.
    xpc_connection_set_event_handler(connection, ^(xpc_object_t event) {
        (void)event;
    });

    xpc_connection_resume(connection);
}

xpc_object_t vmnet_broker_acquire_network(
    const char *network_name, vmnet_broker_return_t *status
) {
    if (connection == NULL) {
        connect_to_broker();
    }

    xpc_object_t message = xpc_dictionary_create_empty();
    xpc_dictionary_set_string(message, REQUEST_COMMAND, COMMAND_ACQUIRE);
    xpc_dictionary_set_string(message, REQUEST_NETWORK_NAME, network_name);

    xpc_object_t reply = xpc_connection_send_message_with_reply_sync(
        connection, message
    );
    xpc_release(message);
    message = NULL;

    xpc_object_t serialization = NULL;
    vmnet_broker_return_t ret = VMNET_BROKER_INTERNAL_ERROR;
    xpc_type_t reply_type = xpc_get_type(reply);

    if (reply_type == XPC_TYPE_ERROR) {
        ret = VMNET_BROKER_XPC_FAILURE;
        goto out;
    }

    if (reply_type != XPC_TYPE_DICTIONARY) {
        ret = VMNET_BROKER_INVALID_REPLY;
        goto out;
    }

    int32_t error = xpc_dictionary_get_int64(reply, REPLY_ERROR);
    if (error) {
        ret = (vmnet_broker_return_t)error;
        goto out;
    }

    serialization = xpc_dictionary_get_value(reply, REPLY_NETWORK);
    if (serialization == NULL) {
        ret = VMNET_BROKER_INVALID_REPLY;
        goto out;
    }

    ret = VMNET_BROKER_SUCCESS;
    xpc_retain(serialization);

out:
    xpc_release(reply);

    if (status) {
        *status = ret;
    }
    return serialization;
}

const char *vmnet_broker_strerror(vmnet_broker_return_t status) {
    switch (status) {
    case VMNET_BROKER_SUCCESS:
        return "Broker session started";
    case VMNET_BROKER_XPC_FAILURE:
        return "Failed to send XPC message to broker";
    case VMNET_BROKER_INVALID_REPLY:
        return "Broker returned invalid reply";
    case VMNET_BROKER_NOT_ALLOWED:
        return "You are not allowed to create a network";
    case VMNET_BROKER_INVALID_REQUEST:
        return "Invalid broker request";
    case VMNET_BROKER_NOT_FOUND:
        return "Network name not found";
    case VMNET_BROKER_CREATE_FAILURE:
        return "Failed to create network";
    case VMNET_BROKER_INTERNAL_ERROR:
        return "Internal or unknown error";
    default:
        return "(unknown status)";
    }
}

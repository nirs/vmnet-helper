// SPDX-FileCopyrightText: The vmnet-helper authors
// SPDX-License-Identifier: Apache-2.0

#include <assert.h>
#include <errno.h>
#include <pthread.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/event.h>
#include <sys/sysctl.h>
#include <sys/time.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>
#include <uuid/uuid.h>
#include <vmnet/vmnet.h>

#include "log.h"
#include "options.h"
#include "socket_x.h"
#include "version.h"

// vmnet_read() can return up to 256 packets. There is no constant in vmnet for
// this value. https://developer.apple.com/documentation/vmnet?language=objc
// sendmsg_x() and recvmsg_x() do not document any value but testing show that
// we can read or write 64 packets in one call.  Tesiting with iperf3 shows
// that there is no reason to use more than 64.
#define MAX_PACKET_COUNT 64

#define MICROSECOND 1000

// Testing show that one retry in enough in 72% of cases.  The following stats
// are from 300 seconds iperf3 run at 7.85 Gbits/sec rate (679 kps).
//
//  retries  count  distribution
//  ------------------------------------------------------------------------------------
//        1     68  ||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||
//        2     17  |||||||||||||||||
//        3      3  |||
//        6      2  ||
//        4      2  ||
//        8      1  |
//       13      1  |
#define VM_RETRY_DELAY (50 * MICROSECOND)

#define ARRAY_SIZE(a) (sizeof(a) / sizeof(a[0]))

static const uintptr_t SHUTDOWN_EVENT = 1;

enum {
    STATUS_FAILURE = 1,
    STATUS_STOPPED = 2,
};

struct version {
    int major;
    int minor;
    int point;
};

struct endpoint {
    dispatch_queue_t queue;
    struct vmpktdesc packets[MAX_PACKET_COUNT];
    struct msghdr_x msgs[MAX_PACKET_COUNT];
    struct iovec iovs[MAX_PACKET_COUNT];
    unsigned char *buffers;
};

static void init_endpoint(struct endpoint *e, size_t max_packet_size)
{
    e->buffers = calloc(MAX_PACKET_COUNT, max_packet_size);
    if (e->buffers == NULL) {
        ERRORF("[main] calloc: %s", strerror(errno));
        exit(EXIT_FAILURE);
    }

    // Bind iovs and buffers to packets and msgs - this can be done once.
    for (int i = 0; i < MAX_PACKET_COUNT; i++) {
        struct iovec *iov = &e->iovs[i];
        iov->iov_base = &e->buffers[i * max_packet_size];

        // For reading and writing vmnet interface.
        struct vmpktdesc *packet = &e->packets[i];
        packet->vm_pkt_iovcnt = 1;
        packet->vm_pkt_iov = iov;

        // For reading and vm socket.
        struct msghdr_x *msg = &e->msgs[i];
        msg->msg_hdr.msg_iovlen = 1;
        msg->msg_hdr.msg_iov = iov;
    }
}

static struct options options = {
    .fd = -1,
    .operation_mode = VMNET_SHARED_MODE,
    .start_address = "192.168.105.1",
    .end_address = "192.168.105.254",
    .subnet_mask = "255.255.255.0",
};

static struct endpoint host;
static struct endpoint vm;
static interface_ref interface;
static size_t max_packet_size;
static int kq = -1;
static int status;
static bool has_bulk_forwarding;

static const char *host_strerror(vmnet_return_t v)
{
    switch (v) {
    case VMNET_SUCCESS:
        return "VMNET_SUCCESS";
    case VMNET_FAILURE:
        return "VMNET_FAILURE";
    case VMNET_MEM_FAILURE:
        return "VMNET_MEM_FAILURE";
    case VMNET_INVALID_ARGUMENT:
        return "VMNET_INVALID_ARGUMENT";
    case VMNET_SETUP_INCOMPLETE:
        return "VMNET_SETUP_INCOMPLETE";
    case VMNET_INVALID_ACCESS:
        return "VMNET_INVALID_ACCESS";
    case VMNET_PACKET_TOO_BIG:
        return "VMNET_PACKET_TOO_BIG";
    case VMNET_BUFFER_EXHAUSTED:
        return "VMNET_BUFFER_EXHAUSTED";
    case VMNET_TOO_MANY_PACKETS:
        return "VMNET_TOO_MANY_PACKETS";
    default:
        return "(unknown status)";
    }
}

static void setup_kq(void)
{
    kq = kqueue();
    if (kq == -1) {
        ERRORF("[main] kqueue: %s", strerror(errno));
        exit(EXIT_FAILURE);
    }

    struct kevent changes[] = {
        {.ident=SIGTERM, .filter=EVFILT_SIGNAL, .flags=EV_ADD},
        {.ident=SIGINT, .filter=EVFILT_SIGNAL, .flags=EV_ADD},
        {.ident=SHUTDOWN_EVENT, .filter=EVFILT_USER, .flags=EV_ADD},
    };

    sigset_t mask;
    sigemptyset(&mask);
    for (size_t i = 0; i < ARRAY_SIZE(changes); i++) {
        if (changes[i].filter == EVFILT_SIGNAL) {
            sigaddset(&mask, changes[i].ident);
        }
    }
    if (sigprocmask(SIG_BLOCK, &mask, NULL) != 0) {
        ERRORF("[main] sigprocmask: %s", strerror(errno));
        exit(EXIT_FAILURE);
    }

    // We will receive EPIPE on the socket.
    signal(SIGPIPE, SIG_IGN);

    if (kevent(kq, changes, ARRAY_SIZE(changes), NULL, 0, NULL) != 0) {
        ERRORF("[main] kevent: %s", strerror(errno));
        exit(EXIT_FAILURE);
    }
}

static void trigger_shutdown(int flags)
{
    struct kevent event = {
        .ident=SHUTDOWN_EVENT,
        .filter=EVFILT_USER,
        .fflags=NOTE_TRIGGER | NOTE_FFOR | (flags & NOTE_FFLAGSMASK),
    };
    if (kevent(kq, &event, 1, NULL, 0, NULL) != 0) {
        ERRORF("kevent: %s", strerror(errno));
        exit(EXIT_FAILURE);
    }
}

static void write_vmnet_info(xpc_object_t param)
{
    __block int count = 0;

#define print_item(fmt, key, value) \
    do { \
        if (count++ > 0) \
            printf(","); \
        printf(fmt, key, value); \
    } while (0)

    printf("{");

    xpc_dictionary_apply(param, ^bool(const char *key, xpc_object_t value) {
        xpc_type_t t = xpc_get_type(value);
        if (t == XPC_TYPE_UINT64) {
            print_item("\"%s\":%llu", key, xpc_uint64_get_value(value));
        } else if (t == XPC_TYPE_INT64) {
            print_item("\"%s\":%lld", key, xpc_int64_get_value(value));
        } else if (t == XPC_TYPE_STRING) {
            print_item("\"%s\":\"%s\"", key, xpc_string_get_string_ptr(value));
        } else if (t == XPC_TYPE_UUID) {
            char uuid_str[36 + 1];
            uuid_unparse(xpc_uuid_get_bytes(value), uuid_str);
            print_item("\"%s\":\"%s\"", key, uuid_str);
        }
        return true;
    });

    printf("}\n");
    fflush(stdout);
}

static void start_host_interface(void)
{
    DEBUG("[main] starting vmnet interface");

    host.queue = dispatch_queue_create("com.github.nirs.vmnet-helper.host", DISPATCH_QUEUE_SERIAL);

    xpc_object_t desc = xpc_dictionary_create(NULL, NULL, 0);
    xpc_dictionary_set_uuid(desc, vmnet_interface_id_key, options.interface_id);
    xpc_dictionary_set_uint64(desc, vmnet_operation_mode_key, options.operation_mode);

    if (options.operation_mode == VMNET_BRIDGED_MODE) {
        xpc_dictionary_set_string(desc, vmnet_shared_interface_name_key, options.shared_interface);
    } else {
        xpc_dictionary_set_string(desc, vmnet_start_address_key, options.start_address);
        xpc_dictionary_set_string(desc, vmnet_end_address_key, options.end_address);
        xpc_dictionary_set_string(desc, vmnet_subnet_mask_key, options.subnet_mask);
    }

    dispatch_semaphore_t completed = dispatch_semaphore_create(0);

    interface = vmnet_start_interface(
            desc, host.queue, ^(vmnet_return_t status, xpc_object_t param) {
        if (status != VMNET_SUCCESS) {
            ERRORF("[main] vmnet_start_interface: %s", host_strerror(status));
            exit(EXIT_FAILURE);
        }

        write_vmnet_info(param);
        max_packet_size = xpc_dictionary_get_uint64(param, vmnet_max_packet_size_key);
        dispatch_semaphore_signal(completed);
    });

    dispatch_semaphore_wait(completed, DISPATCH_TIME_FOREVER);
    xpc_release(desc);

    INFO("[main] started vmnet interface");
}

static void drop_privileges(void)
{
    if (options.gid != 0) {
        if (setgid(options.gid) < 0) {
            ERRORF("[main] unable to change gid to %d: %s", options.gid, strerror(errno));
            exit(EXIT_FAILURE);
        }
    }
    if (options.uid != 0) {
        if (setuid(options.uid) < 0) {
            ERRORF("[main] unable to change uid to %d: %s", options.uid, strerror(errno));
            exit(EXIT_FAILURE);
        }
    }
    INFOF("[main] running as uid: %d gid: %d", geteuid(), getegid());
}

static void setup_host_buffers(void)
{
    DEBUGF("[main] allocating %d packets of %zu bytes for host",
            MAX_PACKET_COUNT, max_packet_size);
    init_endpoint(&host, max_packet_size);
}

static void setup_vm_buffers(void)
{
    DEBUGF("[main] allocating %d packets of %zu bytes for vm",
            MAX_PACKET_COUNT, max_packet_size);
    init_endpoint(&vm, max_packet_size);
}

static int read_from_host(void)
{
    int count = MAX_PACKET_COUNT;

    // Reset packets and iovs - must be done before reading from vment.
    for (int i = 0; i < count; i++) {
        host.packets[i].vm_pkt_size = max_packet_size;
        host.packets[i].vm_flags = 0;
    }
    for (int i = 0; i < count; i++) {
        host.iovs[i].iov_len = max_packet_size;
    }

    vmnet_return_t status = vmnet_read(interface, &host.packets[0], &count);
    if (status != VMNET_SUCCESS) {
        ERRORF("[host->vm] vmnet_read: %s", host_strerror(status));
        return -1;
    }

    return count;
}

// When sendmsg_x()/write() fail with ENOBUFS we need to wait until the kernel
// has buffer spacce, but we don't have a way to wait for event.  Polling with
// very short sleep typically work after 1 retry.
static inline void wait_for_buffer_space(void)
{
    struct timespec t = {.tv_nsec=VM_RETRY_DELAY};
    nanosleep(&t, NULL);
}

static void write_to_vm(int count)
{
    for (int i = 0; i < count; i++) {
        host.msgs[i].msg_len = host.packets[i].vm_pkt_size;
    }

    int sent = 0;

    // Fast path.

    if (has_bulk_forwarding) {
        uint64_t retries = 0;

        while (1) {
            ssize_t n = sendmsg_x(options.fd, &host.msgs[sent], count-sent, 0);
            if (n == -1) {
                if (errno == ENOBUFS) {
                    wait_for_buffer_space();
                    retries++;
                    continue;
                }

                ERRORF("[host->vm] sendmsg_x: %s", strerror(errno));
                break;
            }

            sent += n;
            if (sent == count) {
                DEBUGF("[host->vm] forwarded %d packets, %lld retries", count, retries);
                return;
            }
        }
    }

    // Slow path.

    int forwarded = 0;
    int dropped = 0;

    for (int i = sent; i < count; i++) {
        struct vmpktdesc *packet = &host.packets[i];
        ssize_t len;
        uint64_t retries = 0;

        while (1) {
            len = write(options.fd, packet->vm_pkt_iov[0].iov_base,
                    packet->vm_pkt_size);
            if (len == -1 && errno == ENOBUFS) {
                wait_for_buffer_space();
                retries++;
                continue;
            }
            break;
        }

        if (len < 0) {
            // TODO: like socket_vmnet we drop the packet and continue. Maybe trigger shutdown?
            ERRORF("[host->vm] write: %s", strerror(errno));
            dropped++;
            continue;
        }

        forwarded++;
        if (retries > 0) {
            DEBUGF("[host->vm] write completed after %lld retries", retries);
        }

        // Partial write should not be possible with datagram socket.
        assert((size_t)len == packet->vm_pkt_size);
    }

    DEBUGF("[host->vm] forwarded %d packets, %d dropped", forwarded, dropped);
}

static void packets_available(xpc_object_t event)
{
    int available = xpc_dictionary_get_uint64(
            event, vmnet_estimated_packets_available_key);

    DEBUGF("[host->vm] %d packets available", available);

    while (1) {
        int count = read_from_host();
        if (count < 1) {
            break;
        }
        write_to_vm(count);
    }
}

static void start_forwarding_from_host(void)
{
    DEBUG("[main] enable host forwarding");

    vmnet_return_t status = vmnet_interface_set_event_callback(
        interface, VMNET_INTERFACE_PACKETS_AVAILABLE, host.queue,
        ^(interface_event_t __attribute__((unused)) event_id, xpc_object_t event) {
            packets_available(event);
    });
    if (status != VMNET_SUCCESS) {
        ERRORF("[host->vm] vmnet_interface_set_event_callback: %s", host_strerror(status));
        exit(EXIT_FAILURE);
    }

    INFO("[main] started host formwarding");
}

static int read_from_vm(void)
{
    // Fast path - read multiple packets with one syscall.

    if (has_bulk_forwarding) {
        int max_packets = MAX_PACKET_COUNT;

        // Reset iovs - must be done before reading from vm.  recvmsg_x() reads
        // iov_len but does not modify it.
        for (int i = 0; i < max_packets; i++) {
            vm.iovs[i].iov_len = max_packet_size;
        }

        int count = recvmsg_x(options.fd, vm.msgs, max_packets, 0);
        if (count != -1) {
            return count;
        }

        ERRORF("[vm->host] recvmsg_x: %s", strerror(errno));
    }

    // Slow path - read one packet.

    vm.iovs[0].iov_len = max_packet_size;
    int len = read(options.fd, vm.iovs[0].iov_base, vm.iovs[0].iov_len);
    if (len == -1) {
        ERRORF("[vm->host] read: %s", strerror(errno));
        return -1;
    }

    vm.msgs[0].msg_len = len;
    return 1;
}

static int write_to_host(int count)
{
    // Update packets and iovs to match msgs. vmnet_write() uses vm_pkt_size
    // but require iov_len to match.
    for (int i = 0; i < count; i++) {
        vm.packets[i].vm_pkt_size = vm.msgs[i].msg_len;
    }
    for (int i = 0; i < count; i++) {
        vm.iovs[i].iov_len = vm.msgs[i].msg_len;
    }

    vmnet_return_t status = vmnet_write(interface, vm.packets, &count);
    if (status != VMNET_SUCCESS) {
        ERRORF("[vm->host] vmnet_write: %s", host_strerror(status));
        return -1;
    }

    return 0;
}

static void forward_from_vm(void)
{
    DEBUG("[vm->host] started");

    while (1) {
        int count = read_from_vm();
        if (count == -1) {
            trigger_shutdown(STATUS_FAILURE);
            break;
        }

        if (count == 0) {
            INFO("[vm->host] socket was closed by peer");
            trigger_shutdown(STATUS_STOPPED);
            break;
        }

        if (write_to_host(count)) {
            trigger_shutdown(STATUS_FAILURE);
            break;
        }

        DEBUGF("[vm->host] forwarded %d packets", count);
    }

    INFO("[vm->host] stopped");
}

static void start_forwarding_from_vm(void)
{
    vm.queue = dispatch_queue_create("com.github.nirs.vmnet-helper.vm", DISPATCH_QUEUE_SERIAL);

    dispatch_async(vm.queue, ^{
        forward_from_vm();
    });

    INFO("[main] started vm forwarding");
}

static void wait_for_termination(void)
{
    INFO("[main] waiting for termination");

    struct kevent events[1];

    while (1) {
        int n = kevent(kq, NULL, 0, events, 1, NULL);
        if (n < 0) {
            ERRORF("[main] kevent: %s", strerror(errno));
            status |= STATUS_FAILURE;
            break;
        }
        if (n > 0) {
            if (events[0].filter == EVFILT_SIGNAL) {
                INFOF("[main] received signal %s", strsignal(events[0].ident));
                status |= STATUS_STOPPED;
                break;
            }
            if (events[0].filter == EVFILT_USER) {
                INFO("[main] received shutdown event");
                status |= events[0].fflags;
                break;
            }
        }
    }
}

static void stop_host_interface(void)
{
    if (interface == NULL) {
        return;
    }

    DEBUG("[main] stopping vmnet interface");

    dispatch_semaphore_t completed = dispatch_semaphore_create(0);
    vmnet_return_t status = vmnet_stop_interface(
            interface, host.queue, ^(vmnet_return_t status) {
        if (status != VMNET_SUCCESS) {
            ERRORF("[main] vmnet_stop_interface: %s", host_strerror(status));
            exit(EXIT_FAILURE);
        }
        dispatch_semaphore_signal(completed);
    });
    if (status != VMNET_SUCCESS) {
        ERRORF("[main] vmnet_stop_interface: %s", host_strerror(status));
        exit(EXIT_FAILURE);
    }

    dispatch_semaphore_wait(completed, DISPATCH_TIME_FOREVER);

    INFO("[main] stopped vmnet interface");
}

static int os_product_version(struct version *v)
{
    char buf[20];
    size_t len = sizeof(buf);

    if (sysctlbyname("kern.osproductversion", buf, &len, NULL, 0) != 0) {
        WARNF("sysctlbyname(kern.osproductversion): %s", strerror(errno));
        return -1;
    }

    char *s = buf;
    int *numbers[] = {&v->major, &v->minor, &v->point};
    for (unsigned i = 0; i < ARRAY_SIZE(numbers); i++) {
        char *p = strsep(&s, ".");
        if (p == NULL) {
            break;
        }
        *numbers[i] = atoi(p);
    }

    return 0;
}

static void check_os_version(const char *prog)
{
    struct version v = {0};
    if (os_product_version(&v)) {
        return;
    }

    INFOF("[main] running %s %s on macOS %d.%d.%d",
          prog, GIT_VERSION, v.major, v.minor, v.point);

    if (v.major > 13) {
        INFO("[main] enabling bulk forwarding");
        has_bulk_forwarding = true;
    }
}

int main(int argc, char **argv)
{
    parse_options(&options, argc, argv);
    check_os_version(argv[0]);
    setup_kq();
    start_host_interface();
    drop_privileges();
    setup_host_buffers();
    setup_vm_buffers();
    start_forwarding_from_host();
    start_forwarding_from_vm();
    wait_for_termination();
    stop_host_interface();

    return (status == 0 || status & STATUS_STOPPED) ? EXIT_SUCCESS : EXIT_FAILURE;
}

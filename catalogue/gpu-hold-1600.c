#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

/*
 * Holds the graphics clock at 1600 MHz while a title is open.
 * ShellCore raises gfxclk when a native PS5 game enters boosted mode
 * (observed 2230). This process rewrites it whenever the readback is
 * above 1600. Home (900) is left alone.
 *
 * gfxclk is word 21 of MP1_IOCTL_GET_CLK, byte offset 0x54.
 * MP1_IOCTL_SET_GFXCLK takes that value in MHz.
 *
 * If the readback stays at the boosted clock after the write, firmware
 * is ignoring the request. One attempt is then made to put every CPU
 * core in p-state 5 (1.6 GHz on the high-to-low table) so a 3.5 GHz
 * CPU boost cannot pin the GPU at 2.23 GHz.
 */
#define MP1_IOCTL_GET_CLK 0x406cae01UL
#define MP1_IOCTL_SET_GFXCLK 0x8004ae17UL
#define MP1_IOCTL_SET_COREPSTATE 0x8008ae1dUL
#define GFX_LIMIT 1600U
#define GFX_OFFSET 0x54
#define HOLD_SECONDS (6U * 60U * 60U)
#define POLL_US 50000
#define CPU_CORES 8U
#define CPU_PSTATE_1600 5U

struct status {
    uint32_t magic;
    uint32_t state;
    uint32_t requested;
    uint32_t last_seen;
    uint32_t last_readback;
    uint32_t clamps;
    uint32_t overrides;
    uint32_t cpu_pstate;
    int32_t open_rc;
    int32_t last_set_rc;
    int32_t last_set_errno;
};

typedef struct notify_request {
    char pad[45];
    char message[3075];
} notify_request_t;

int sceKernelSendNotificationRequest(int device, notify_request_t *req, size_t size, int blocking);

static void notify(const char *message) {
    notify_request_t req;
    memset(&req, 0, sizeof(req));
    snprintf(req.message, sizeof(req.message), "%s", message);
    sceKernelSendNotificationRequest(0, &req, sizeof(req), 0);
}

static void save(const struct status *st) {
    int out = open("/data/gpu-hold-1600.bin", O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (out >= 0) {
        write(out, st, sizeof(*st));
        close(out);
    }
}

static uint32_t gfx_of(const uint8_t *table) {
    uint32_t value;
    memcpy(&value, table + GFX_OFFSET, sizeof(value));
    return value;
}

static int read_gfx(int fd, uint32_t *out) {
    uint8_t table[112];
    memset(table, 0, sizeof(table));
    if (ioctl(fd, MP1_IOCTL_GET_CLK, table) != 0) {
        return -1;
    }
    *out = gfx_of(table);
    return 0;
}

static void drop_cpu(int fd, struct status *st) {
    for (uint32_t core = 0; core < CPU_CORES; core++) {
        struct {
            uint32_t core;
            uint32_t pstate;
        } arg;
        arg.core = core;
        arg.pstate = CPU_PSTATE_1600;
        ioctl(fd, MP1_IOCTL_SET_COREPSTATE, &arg);
    }
    st->cpu_pstate = CPU_PSTATE_1600;
}

int main(void) {
    struct status st;
    memset(&st, 0, sizeof(st));
    st.magic = 0x36314847; /* GH16 */
    st.requested = GFX_LIMIT;
    st.open_rc = open("/dev/mp1", O_RDWR);
    save(&st);
    if (st.open_rc < 0) {
        notify("GPU hold: cannot open /dev/mp1");
        return 0;
    }

    notify("GPU hold running, ceiling 1600 MHz");
    unsigned stuck_high = 0;
    unsigned polls = 0;
    const unsigned polls_max = HOLD_SECONDS * (1000000U / POLL_US);

    while (polls < polls_max) {
        uint32_t seen = 0;
        if (read_gfx(st.open_rc, &seen) != 0) {
            usleep(POLL_US);
            polls++;
            continue;
        }
        st.last_seen = seen;
        if (seen > GFX_LIMIT) {
            uint32_t request = GFX_LIMIT;
            errno = 0;
            st.last_set_rc = ioctl(st.open_rc, MP1_IOCTL_SET_GFXCLK, &request);
            st.last_set_errno = errno;
            st.clamps++;
            uint32_t back = 0;
            if (read_gfx(st.open_rc, &back) == 0) {
                st.last_readback = back;
                if (back > GFX_LIMIT) {
                    st.overrides++;
                    stuck_high++;
                    st.state = 2;
                } else {
                    stuck_high = 0;
                    st.state = 1;
                }
            }
            if (st.clamps == 1) {
                char msg[96];
                snprintf(msg, sizeof(msg), "GPU %u -> %u MHz", seen, st.last_readback);
                notify(msg);
            }
            if (stuck_high == 20 && st.cpu_pstate == 0) {
                drop_cpu(st.open_rc, &st);
                notify("GPU clock ignored, CPU set to 1.6 GHz p-state");
            }
        } else {
            st.last_readback = seen;
            st.state = (st.clamps > 0) ? 1 : 0;
            stuck_high = 0;
        }
        if ((polls % 40U) == 0) {
            save(&st);
        }
        usleep(POLL_US);
        polls++;
    }

    st.state = 3;
    save(&st);
    close(st.open_rc);
    notify("GPU hold stopped");
    return 0;
}

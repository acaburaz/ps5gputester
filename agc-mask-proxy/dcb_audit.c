#include "dcb_audit.h"
#include <stdbool.h>

#define PKT3_NOP 0x10u
#define PKT3_SET_SH_REG 0x76u
#define PKT3_SET_UCONFIG_REG 0x79u
#define SH_REG_BASE 0x0000b000u
#define UCONFIG_REG_BASE 0x00030000u

bool
agc_dcb_audit(const uint32_t *dwords, size_t count, agc_dcb_register_callback callback, void *user)
{
    if (!dwords || !callback)
        return false;

    for (size_t cursor = 0; cursor < count;) {
        const uint32_t header = dwords[cursor];
        const uint32_t type = header >> 30;
        size_t packet_count;

        if (type == 2) {
            packet_count = 1;
        } else if (type == 0 || type == 3) {
            const uint32_t encoded_count = (header >> 16) & 0x3fffu;
            const uint32_t opcode = (header >> 8) & 0xffu;
            if (type == 3 && opcode == PKT3_NOP && encoded_count == 0x3fffu)
                packet_count = 1;
            else
                packet_count = (size_t)encoded_count + 2;
        } else if (type == 1) {
            packet_count = 2;
        } else {
            return false;
        }

        if (packet_count > count - cursor)
            return false;

        if (type == 3 && packet_count >= 3) {
            const uint32_t opcode = (header >> 8) & 0xffu;
            enum agc_dcb_register_space space;
            uint32_t base;
            if (opcode == PKT3_SET_SH_REG) {
                space = AGC_DCB_SH_REG;
                base = SH_REG_BASE;
            } else if (opcode == PKT3_SET_UCONFIG_REG) {
                space = AGC_DCB_UCONFIG_REG;
                base = UCONFIG_REG_BASE;
            } else {
                cursor += packet_count;
                continue;
            }

            const uint32_t register_offset = dwords[cursor + 1] & 0xffffu;
            const struct agc_dcb_register_write write = {
                .space = space,
                .register_address = base + register_offset * 4,
                .values = &dwords[cursor + 2],
                .value_count = packet_count - 2,
                .packet_dword = cursor,
                .value_dword = cursor + 2,
            };
            callback(&write, user);
        }
        cursor += packet_count;
    }
    return true;
}

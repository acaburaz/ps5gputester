#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum agc_dcb_register_space {
    AGC_DCB_SH_REG,
    AGC_DCB_UCONFIG_REG,
};

struct agc_dcb_register_write {
    enum agc_dcb_register_space space;
    uint32_t register_address;
    const uint32_t *values;
    size_t value_count;
    size_t packet_dword;
    size_t value_dword;
};

typedef void (*agc_dcb_register_callback)(const struct agc_dcb_register_write *write, void *user);

/* Bounded, read-only PM4 walk for the first proxy build. Returns false for a
 * malformed or truncated packet and never modifies the submitted DCB. */
bool agc_dcb_audit(const uint32_t *dwords, size_t count, agc_dcb_register_callback callback, void *user);

#ifdef __cplusplus
}
#endif

#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

struct agc_dcb_mask_result {
    size_t register_writes_seen;
    size_t values_changed;
};

/* Apply the diagnostic GFX10 WGP-4 exclusion to a private DCB copy.
 * The stream is validated before modification, so malformed input is left
 * untouched. This handles ordinary SET_SH_REG packets only. */
bool agc_dcb_disable_wgp4(uint32_t *dwords, size_t count, struct agc_dcb_mask_result *result);

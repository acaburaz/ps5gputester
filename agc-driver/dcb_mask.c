#include "dcb_mask.h"
#include "dcb_audit.h"

#include <string.h>

#define WGP4_CU_BITS 0x00000300u

struct mask_context {
    uint32_t *dwords;
    struct agc_dcb_mask_result result;
};

static uint32_t
cu_mask_for_register(uint32_t address)
{
    switch (address) {
    case 0x0000b018u: /* SPI_SHADER_PGM_RSRC3_PS on GFX10.3 */
    case 0x0000b01cu: /* SPI_SHADER_PGM_RSRC3_PS on GFX10 */
    case 0x0000b118u: /* SPI_SHADER_PGM_RSRC3_VS */
    case 0x0000b21cu: /* SPI_SHADER_PGM_RSRC3_GS */
    case 0x0000b51cu: /* SPI_SHADER_PGM_RSRC3_LS */
        return WGP4_CU_BITS;
    case 0x0000b41cu: /* SPI_SHADER_PGM_RSRC3_HS: CU_EN is bits 16..31 */
        return WGP4_CU_BITS << 16;
    case 0x0000b858u: /* COMPUTE_STATIC_THREAD_MGMT_SE0 */
    case 0x0000b85cu: /* COMPUTE_STATIC_THREAD_MGMT_SE1 */
    case 0x0000b864u: /* COMPUTE_STATIC_THREAD_MGMT_SE2 */
    case 0x0000b868u: /* COMPUTE_STATIC_THREAD_MGMT_SE3 */
        return WGP4_CU_BITS | (WGP4_CU_BITS << 16);
    default:
        return 0;
    }
}

static void
mask_register_write(const struct agc_dcb_register_write *write, void *user)
{
    struct mask_context *context = user;
    context->result.register_writes_seen += write->value_count;
    for (size_t i = 0; i < write->value_count; ++i) {
        const uint32_t address = write->register_address + (uint32_t)i * 4u;
        const uint32_t clear = cu_mask_for_register(address);
        uint32_t *value = &context->dwords[write->value_dword + i];
        const uint32_t masked = *value & ~clear;
        if (masked != *value) {
            *value = masked;
            context->result.values_changed++;
        }
    }
}

static void
validate_only(const struct agc_dcb_register_write *write, void *user)
{
    (void)write;
    (void)user;
}

bool
agc_dcb_disable_wgp4(uint32_t *dwords, size_t count, struct agc_dcb_mask_result *result)
{
    if (result)
        memset(result, 0, sizeof(*result));
    if (!dwords || !agc_dcb_audit(dwords, count, validate_only, NULL))
        return false;

    struct mask_context context = {.dwords = dwords};
    if (!agc_dcb_audit(dwords, count, mask_register_write, &context))
        return false;
    if (result)
        *result = context.result;
    return true;
}

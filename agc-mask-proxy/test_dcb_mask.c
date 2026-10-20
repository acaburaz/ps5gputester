#include "dcb_mask.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static uint32_t
pkt3(unsigned opcode, unsigned payload_dwords)
{
    return 0xc0000000u | ((payload_dwords - 1u) << 16) | (opcode << 8);
}

int
main(void)
{
    uint32_t dcb[] = {
        pkt3(0x76, 3),
        (0xb014u - 0xb000u) / 4u,
        0x13579bdfu,
        0xffffffffu,
        pkt3(0x76, 2),
        (0xb858u - 0xb000u) / 4u,
        0xffffffffu,
        pkt3(0x9b, 2),
        (0xb018u - 0xb000u) / 4u,
        0xffffffffu,
        0x80000000u,
    };
    struct agc_dcb_mask_result result;
    assert(agc_dcb_disable_wgp4(dcb, sizeof(dcb) / sizeof(dcb[0]), &result));
    assert(dcb[2] == 0x13579bdfu);
    assert(dcb[3] == 0xfffffcffu);
    assert(dcb[6] == 0xfcfffcffu);
    assert(dcb[9] == 0xfffffcffu);
    assert(result.register_writes_seen == 4);
    assert(result.values_changed == 3);

    uint32_t malformed[] = {pkt3(0x76, 2), 6u};
    uint32_t original[2];
    memcpy(original, malformed, sizeof(original));
    assert(!agc_dcb_disable_wgp4(malformed, 2, &result));
    assert(memcmp(original, malformed, sizeof(original)) == 0);
    puts("dcb_mask: PASS");
    return 0;
}

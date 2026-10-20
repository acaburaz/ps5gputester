#include "dcb_audit.h"
#include <assert.h>
#include <stdio.h>

struct result { unsigned calls; uint32_t address; uint32_t value; };
static void collect(const struct agc_dcb_register_write *write, void *user)
{
    struct result *result = user;
    result->calls++;
    result->address = write->register_address;
    result->value = write->values[0];
}

int main(void)
{
    const uint32_t dcb[] = {
        0xc0017600u, 0x00000006u, 0x12345678u,
        0x80000000u,
    };
    struct result result = {0};
    assert(agc_dcb_audit(dcb, 4, collect, &result));
    assert(result.calls == 1);
    assert(result.address == 0x2c18u);
    assert(result.value == 0x12345678u);
    puts("dcb_audit: PASS");
    return 0;
}

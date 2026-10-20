#include "submit_copy.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

int
main(void)
{
    const uint32_t source_words[] = {
        0xc0017600u,
        (0xb858u - 0xb000u) / 4u,
        0xffffffffu,
    };
    uint32_t original[3];
    memcpy(original, source_words, sizeof(original));
    const struct agc_submit_description source = {
        .words = (void *)source_words,
        .word_count = 3,
        .flag = 1,
    };
    uint32_t workspace[3] = {0};
    struct agc_submit_description prepared = {0};
    struct agc_dcb_mask_result result;

    assert(agc_prepare_masked_submission(&source, workspace, 3, &prepared, &result));
    assert(memcmp(source_words, original, sizeof(original)) == 0);
    assert(prepared.words == workspace);
    assert(prepared.word_count == source.word_count);
    assert(prepared.flag == source.flag);
    assert(workspace[2] == 0xfcfffcffu);
    assert(result.values_changed == 1);

    memset(workspace, 0, sizeof(workspace));
    assert(!agc_prepare_masked_submission(&source, workspace, 2, &prepared, &result));
    puts("submit_copy: PASS");
    return 0;
}

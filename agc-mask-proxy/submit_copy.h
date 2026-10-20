#pragma once
#include "dcb_mask.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

struct agc_submit_description {
    void *words;
    uint32_t word_count;
    uint8_t flag;
    uint8_t padding[3];
};

/* Prepare a description that points at caller-provided private storage.
 * The source description and source DCB are never modified. */
bool agc_prepare_masked_submission(const struct agc_submit_description *source,
                                   uint32_t *workspace, size_t workspace_dwords,
                                   struct agc_submit_description *prepared,
                                   struct agc_dcb_mask_result *result);

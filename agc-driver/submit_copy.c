#include "submit_copy.h"

#include <string.h>

bool
agc_prepare_masked_submission(const struct agc_submit_description *source,
                              uint32_t *workspace, size_t workspace_dwords,
                              struct agc_submit_description *prepared,
                              struct agc_dcb_mask_result *result)
{
    if (!source || !source->words || !workspace || !prepared || source->word_count == 0 ||
        source->word_count > workspace_dwords)
        return false;

    const size_t bytes = (size_t)source->word_count * sizeof(uint32_t);
    memcpy(workspace, source->words, bytes);
    if (!agc_dcb_disable_wgp4(workspace, source->word_count, result))
        return false;

    *prepared = *source;
    prepared->words = workspace;
    return true;
}

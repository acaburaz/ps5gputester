# `libSceAgcDriver` hook research

This file records interface and layout facts used to design the diagnostic
WGP-mask hook. Reference SPRX files are kept locally under `reference/` and are
excluded from Git.

## Submit entry point

The PS5 NID algorithm maps `sceAgcDriverSubmitDcb` to `UglJIZjGssM`. Both
locally inspected fakelib builds export that NID as a protected function with a
15-byte thunk. The thunk moves the caller's description from `rdi` to `rsi`,
loads the driver's internal context into `rdi`, and tail-jumps to the common
submit implementation.

| Size | SHA-256 | Submit RVA | Common submit RVA |
| ---: | --- | ---: | ---: |
| 174688 | `5590ee3fe3c2f73200674e17938a6f3e3dece8826a0ecc7249dcba2183adcf07` | `0x2960` | `0x19b0` |
| 174096 | `33cf01e315ae887f232b853cd3bef073017475ec1a318322105201677b90e623` | `0x2970` | `0x1950` |

The executable load begins at file offset `0x4000` with virtual address zero in
the 174688-byte build. Offsets are version-specific and are not sufficient
validation by themselves.

## Submission description observed in the existing native harness

```c
struct agc_submit_description {
    void *words;
    uint32_t word_count;
    uint8_t flag;
    uint8_t padding[3];
};
```

`submit_copy.c` models this layout. Before console use, a canary must verify the
word pointer, count, and flag without dereferencing an unbounded buffer.

## Hook requirements

1. Match an allow-listed whole-file SHA-256 and the exact submit-thunk bytes.
2. Preserve every exported NID and the module metadata of the source build.
3. Allocate persistent GPU-visible storage for copied DCBs; stack or ordinary
   heap memory is not sufficient.
4. Validate the full packet walk before mutation, copy the source DCB, clear
   only the WGP-4 CU bits, then flush the copy's CPU cache.
5. Call the build-specific common submit implementation with its original
   internal context and the prepared description.
6. Fall through to the untouched original submission when parsing, capacity,
   or version validation fails.
7. Start in audit-only mode and test one title-specific fakelib overlay. Do not
   place an experimental build in the global fakelib directory.

No patched SPRX has been generated or deployed yet.

# libSceAgcDriver mask proxy experiment

Goal: determine whether a startup-loaded `libSceAgcDriver.sprx` proxy can prevent native PS5 titles from scheduling shader work on the repeatedly faulting `SE0/SA0/WGP4`.

The first build must be **logging-only**. It should intercept `sceAgcDriverSubmitDcb`, preserve the exact ABI, forward every call unchanged, and log bounded metadata about PM4 register-write packets. Do not deploy a mutating build until forwarding has survived normal application startup and rendering.

## Planned gates

1. Inventory every `libSceAgcDriver` export imported by the target title and the fakelib version.
2. Prove that a startup-loaded proxy can reach the original implementation without recursive symbol resolution.
3. Log DCB address, dword count, submission result, and bounded `SET_SH_REG`/`SET_UCONFIG_REG` destinations. Never log shader or game data.
4. Identify every write that controls compute and graphics `CU_EN` fields. A startup-only write is insufficient because later pipeline binds may overwrite it.
5. In a copy-on-submit buffer, clear the WGP-4 bits while preserving packet lengths and all unrelated bits. Never modify the game's source DCB in place.
6. Test one title-specific ShadowMount fakelib rule before considering a global overlay.

## Current status

A bounded PM4 walker is in `dcb_audit.c`. `dcb_mask.c` applies the diagnostic
WGP-4 exclusion to a caller-owned DCB copy after a validation pass. It currently
handles ordinary `SET_SH_REG` writes to the known GFX10 graphics `CU_EN` and
compute static-thread-management registers. Tests cover address decoding,
multi-register packets, preservation of unrelated bits, and rejecting malformed
streams without partial mutation.

`submit_copy.c` prepares a replacement submit description in fixed,
caller-provided storage. It preserves the source description and DCB, refuses
zero-length or oversized submissions, and points only the prepared description
at the masked copy. A console wrapper must flush this copy before forwarding it.

The version-locked canary now redirects `sceAgcDriverSubmitDcb` through an
instruction-equivalent forwarding stub in executable padding. On Astro it
survived initialization and submissions until the title reproduced its normal
asynchronous GPU fault. The source command buffer remained untouched. RADV
validates the mask concept, but its command construction differs from Sony's
native AGC stack.

The next gate needs persistent GPU-visible copy storage and a cache flush before
the common submit routine is called. Do not replace the forwarding stub with an
in-place edit of the title's DCB.

## Astro audit canary

`patch_audit_driver.py` is locked to Astro's inspected 174688-byte `PPSA01325`
driver. It allocates a 16 MiB direct-memory pool, assigns stable 64 KiB slots
by source DCB pointer, validates and copies PM4, and copies opcode `0x63`
indirect shader-register tables before masking selected WGP CU-enable records.
Use `--wgp 2` or `--wgp 4` to create reproducible comparison builds; WGP4 is
the default for compatibility with the original experiment. It
falls back to the original description on allocation, capacity, or parse
failure. The source SHA-256, submit thunk, initializer, and injection area must
all match before it writes an output.

This remains a diagnostic canary. The WGP4 build has failed both with
`GPU_FAULT_SUSPENDPOINT_TIMEOUT_IN_RUN_ASYNC` and an illegal instruction on
WGP2. The WGP2 comparison build still produced an illegal instruction on WGP2,
showing these table fields do not reliably exclude a WGP from native AGC work.
The original driver was restored; do not treat either build as a workaround.

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

No replacement SPRX is produced or deployed yet. The submit-description ABI and
a non-recursive route to the original system function must be confirmed before
the wrapper is safe to run in a native title. RADV validates the mask concept,
but its command construction differs from Sony's native AGC stack.

## Astro audit canary

`patch_audit_driver.py` supports the two inspected fakelib builds, including
Astro's 174688-byte `PPSA01325` driver. It emits a one-time module-load marker through the driver's existing
`puts` import and then runs the original initializer. It does not intercept or
alter submission yet. The source SHA-256, submit thunk, original initializer,
and zero-filled injection area must all match before it writes an output.

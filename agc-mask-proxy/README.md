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

A bounded, read-only PM4 walker is in `dcb_audit.c`; its host test covers a `SET_SH_REG` packet. No replacement SPRX is produced or deployed yet. The RADV tester validates the mask concept, but RADV's command construction differs from Sony's native AGC stack.

# Astro driver test versions

This file identifies console-tested driver states without redistributing Sony
libraries. Keep the original SPRX locally under `agc-driver/reference/`;
that directory and generated FSELF output are excluded from Git.

## Stock Astro driver baseline — 2026-10-20

Target title: `PPSA01325` (Astro's Playroom)

| Component | Size | SHA-256 |
| --- | ---: | --- |
| Original `libSceAgcDriver.sprx` extracted ELF | 174688 | `5590ee3fe3c2f73200674e17938a6f3e3dece8826a0ecc7249dcba2183adcf07` |
| Active release-hooks `libSceAmpr.sprx` | 279660 | `26367ffde3e746eeaf552cb5f595002f271f91890eb22125070b7a92ace99076` |

The longest observed run with this driver state was approximately 79 seconds
without a GPU error being captured before process exit. A repeat run on the
same state lasted approximately 28 seconds and ended with
`GPU_FAULT_WAVEFRONT_ERROR_ASYNC`; the dump reported `ILLEGAL_INST` on
`SE:0 SA:0 WGP:2`, shader PC `0x812DC3B5C`. Treat the 79-second observation as
run-to-run variation, not a stable workaround.

The cache copy must be uploaded as a development FSELF. Uploading the extracted
ELF directly produced loader error `46`. Build the wrapper without changing the
driver contents:

```powershell
docker run --rm `
  -v 'C:\Tools\Ps5tools\Y2JB\PS5_GPUMemoryTest:/work' `
  -v 'C:\Tools\Ps5tools\Y2JB\PS5_Vulkan:/vulkan' `
  -w /work ps5-gpu-test-builder-complete:latest `
  bash -lc '/vulkan/build/host/ps5-native-tool self --sign --in agc-driver/reference/libSceAgcDriver-PPSA01325-original.sprx --out agc-driver/out/astro-original.fself --magic 0x1D3D154F'
```

Upload `astro-original.fself` to
`/data/shadowmount/cache/PPSA01325/fakelib/libSceAgcDriver.sprx`. The FTP
server extracts the installed ELF; retrieve it and require the original size
and SHA-256 above before launching the title.

## WGP4 indirect-table mask — commit `8c157a9`

This diagnostic version reached the later `0x2867`-dword DCBs and ran for
roughly 45 seconds before `GPU_FAULT_SUSPENDPOINT_TIMEOUT_IN_RUN_ASYNC`.
It changed the failure mode but did not make the console stable. The stock
driver was restored after the test.

A repeat on 2026-10-20 used raw ELF SHA-256
`c63d1402755013ee1f7f750cefc164550935f9cd6081214dccd9403da85b3a30`.
It failed after approximately 18 seconds with
`GPU_FAULT_WAVEFRONT_ERROR_ASYNC` and `ILLEGAL_INST` on `SE:0 SA:0 WGP:2`.

## WGP2 indirect-table mask — 2026-10-20

Generated with `patch_audit_driver.py --wgp 2`; raw ELF SHA-256
`e15b1a51a8526752821abfaa6323fe7cfe1d5707bf37719e660c4bae6799b7d0`.
The title failed after approximately 17 seconds with
`GPU_FAULT_WAVEFRONT_ERROR_ASYNC` and `ILLEGAL_INST` still executing on
`SE:0 SA:0 WGP:2`. Clearing these inspected CU-enable records therefore did
not reliably remove WGP2 from the native AGC workload. The authenticated stock
driver was restored and verified afterward.

### Guarded active-bit build

Raw ELF SHA-256:
`90bcef8327f38eb2de59e3d4ea1e38545da573c506b6e82956608af8ffd17c4f`.
This version skips GPU-only indirect-table addresses and creates
`agc-mask-1.bin` only when a readable incoming record had WGP2 enabled before
the hook cleared it. Two consecutive runs recreated that marker and then
failed identically with `GPU_FAULT_PAGE_FAULT_ASYNC`: five waves on
`SE:0 SA:0 WGP:0`, shader PC `0x500192914`, reported a data-read
`XNACK_ERROR MEMVIOL`. No CPU hook fault occurred. This is evidence that the
record mutation changed execution, but it is not evidence of a stable hardware
unit exclusion.

## Combined WGP0+WGP2 diagnostic — 2026-10-20

Generated with `patch_audit_driver.py --wgp 0,2`; raw ELF SHA-256
`58cc89b3d35f0e2a87c00bb5d7ceb4fb8be75e4727ecea967156d10bc0ccd5b3`.
The run recreated `agc-mask-1.bin`, then failed with an instruction-fetch page
fault at VA `0x0`. The kernel reported SQ message errors across both shader
engines, multiple shader arrays, and WGP0 through WGP4, including the nominally
excluded units. This rules out treating the inspected CU-enable fields as a
simple, global hardware-disable bitmap. The stock driver was restored and its
SHA-256 verified afterward.

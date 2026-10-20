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

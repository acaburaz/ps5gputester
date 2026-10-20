# GPU Memory Test

A PS5 homebrew title (`PPSA99361`) that progressively stresses graphics, device-local memory and thermals on RADV. It renders and solves a scrambled 3D Rubik-style cube, adds lighting, fur and draw passes every 20 seconds, retains 256 MiB memory chunks, and writes performance and temperature telemetry to klog. It was made from the
[PS5 Vulkan Template](https://github.com/mihawk-99/PS5_VulkanTemplate) foundation at
`91179df7`: Sascha Willems' Vulkan example base class with its PS5 hooks, the PS5 layer
(the launch, the pad, klog, test runs, the build and the console tools), and one
program, `examples/gpumemorytest/gpumemorytest.cpp`, grown from the starter sample.

## Building and running

It builds against my PS5 stack, checked out beside it: PS5_Vulkan (the RADV release
archive, the link recipe, the native tool and `libc.prx`) and the payload SDK fork
(`ps5/tools/setup-sdk.sh` installs it at the pinned revision).

Run these commands from the `gpu-test/` directory:

```bash
ps5/tools/build.sh              # dist/PPSA99361/: eboot.bin, sce_sys, shaders, assets
ps5/tools/deploy.sh             # upload what changed, over the console's FTP server
ps5/tools/run.sh                # a test run: 300 frames, the last one saved and checked
ps5/tools/run.sh --menu         # no test: the program, until it ends itself
ps5/tools/host-reference.sh     # the same frames on this PC's Vulkan driver
```

A launch from the home screen starts the program at once. The overlay shows the active stage, load, memory, temperatures and the emergency-exit chord. Hold **L1 + R1 + OPTIONS** to ask the shell to terminate the title immediately without waiting for an overloaded Vulkan queue to become idle. Keep the chord held until the next controller poll when frames are very slow.

## Diagnostic WGP mask

The test can be linked with a diagnostic RADV build that sets `spi_cu_en=0x0ff` in the PS5 winsys before pipelines are created. On the tested RDNA topology this excludes the CU 8/9 position associated with WGP 4 in every shader array. See [`patches/ps5-radv-disable-wgp4.patch`](patches/ps5-radv-disable-wgp4.patch). This broad mask is for diagnosis; it does not modify the console globally or affect games using Sony's native AGC stack.

The separate native AGC driver experiments live in
[`../agc-driver/`](../agc-driver/README.md).

## Growing it

- **The program** is one class on the base class, `examples/gpumemorytest/gpumemorytest.cpp`, with its
  shaders in `shaders/glsl/gpumemorytest/` (GLSL beside the SPIR-V it loads: after changing one,
  `ps5/tools/compile-shaders.sh gpumemorytest`).
- **A technique from the template's samples** (shadows, deferred lighting, bloom, MSAA,
  instancing, indirect draws, compute, bindless textures, mesh shaders, ray queries)
  copies across as it stands: every sample is a class on the same base.
- **Assets** go in `ps5/assets.json`, each with its origin and licence; only assets
  with a clear licence are shipped (`ps5/ASSETS.md` is written from it).
- **More programs**: another `SAMPLE(...)` line in `ps5/src/samples.cpp` turns the
  title into a menu of them, as Vulkan Template is.
- How the foundation works, its test runs and its tools: PS5_VulkanTemplate's
  `ps5/README.md`; the agent skills for this stack are in its `skills/`.

## Licences

The foundation is MIT (`LICENSE.md`, Sascha Willems'; the PS5 layer is mine, under the
same licence). The assets keep their own (`ps5/ASSETS.md`). The built title links the
PS5 platform layer of my payload SDK fork, which is GPL-3.0, so the title as
distributed is under GPL-3.0.

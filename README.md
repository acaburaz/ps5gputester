# PS5 GPU diagnostics

This repository contains the PS5 GPU diagnostic projects and the catalogue of results from this console.

## Projects

- [`gpu-test/`](gpu-test/README.md) — the `PPSA99361` GPU and GDDR6 stress-test title. It renders a progressively heavier 3D workload, allocates device-local memory, records temperatures and performance, and provides build, deployment, and run tools.
- [`agc-driver/`](agc-driver/README.md) — version-locked `libSceAgcDriver` submission experiments for Astro's Playroom (`PPSA01325`), including bounded PM4 auditing, private DCB copies, and the diagnostic WGP mask work.
- [`catalogue/DEFECTIVE_APU.md`](catalogue/DEFECTIVE_APU.md) — a defective APU whose PS5 games do not start because WGP 3 and WGP 4 are broken, and the 1600 MHz ceiling for a console that is staying.
- [`catalogue/GFX_RING_STALL.md`](catalogue/GFX_RING_STALL.md) — the graphics-ring stall at 2.0 GHz, and the payload that holds a native title at 1600 MHz.

The projects share a diagnostic goal but have separate build and deployment workflows. Sony libraries and generated console binaries are intentionally excluded from Git; tested versions are identified by size and SHA-256 in [`agc-driver/TESTED_VERSIONS.md`](agc-driver/TESTED_VERSIONS.md).

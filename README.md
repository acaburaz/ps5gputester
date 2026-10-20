# PS5 GPU diagnostics

This repository contains two related PS5 GPU diagnostic projects.

## Projects

- [`gpu-test/`](gpu-test/README.md) — the `PPSA99361` GPU and GDDR6 stress-test title. It renders a progressively heavier 3D workload, allocates device-local memory, records temperatures and performance, and provides build, deployment, and run tools.
- [`agc-driver/`](agc-driver/README.md) — version-locked `libSceAgcDriver` submission experiments for Astro's Playroom (`PPSA01325`), including bounded PM4 auditing, private DCB copies, and the diagnostic WGP mask work.

The projects share a diagnostic goal but have separate build and deployment workflows. Sony libraries and generated console binaries are intentionally excluded from Git; tested versions are identified by size and SHA-256 in [`agc-driver/TESTED_VERSIONS.md`](agc-driver/TESTED_VERSIONS.md).

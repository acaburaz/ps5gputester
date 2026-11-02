# Defective APU — PS5 games do not start (WGP 3 and 4)

This console is marked as a defective Oberon APU. Native PS5 games do not start on it because WGP 3 and WGP 4 are broken. PS4 games on the same console keep running, because they never sit on the graphics clock those broken groups are driven at.

This note is for a machine that has to stay. A return is not required to keep using it. PS4 games already run. Linux games run when the GPU is held at 1600 MHz. One native title, Astro's Playroom, reached the game at that same ceiling. The broken groups are still broken. The ceiling is what keeps the picture moving.

## If the console is staying

Two places to set the ceiling. Both leave the stock graphics driver in place.

On Linux, once per boot:

```text
echo 1600000000 > /sys/class/devfreq/ps5-gpufreq/max_freq
```

The steps under that cap are 400, 800, 1200 and 1600 MHz. The step that stops the graphics ring is 2000 MHz, and the driver will otherwise climb to 2230 MHz. A oneshot service makes the write survive until the next reboot. `amdgpu.gpu_recovery=0` on the kernel command line keeps a later stall from taking the display down with a failed reset. Do not add `amdgpu.dpm=0`. That option has left this kernel with a dark screen.

On the PS5 menu the Linux service does nothing. The shell raises `gfxclk` to 2230 MHz when a native title boosts. Load `gpu-hold-1600.elf` from the payload manager, leave that payload running, then start the game. Source is [`gpu-hold-1600.c`](gpu-hold-1600.c). The built ELF is attached to the [defective-apu release](https://github.com/acaburaz/ps5gputester/releases/tag/defective-apu). Every 50 ms it reads `gfxclk` and, when the value is above 1600, writes 1600 back. Home at 900 MHz is left alone. Status is `/data/gpu-hold-1600.bin`.

It worked on PS5 firmware **13.60** (`kernel_get_fw_version` `0x13600007`). On that version Astro's Playroom reached the game with `gfxclk` held at 1600 MHz. The file is 111160 bytes, SHA-256 `2251eda411080d16978a22b4304cd06dc6df794da2cf1e79aa91e4597027c8ab`.

Masking WGP 3 and WGP 4 down to 24 CUs was tried. The ring still stopped at 2.0 GHz. The clock ceiling is the change that mattered.

## Mark

| Item | Value |
| --- | --- |
| SoC | AMD Oberon, Cyan Skillfish, PCI `1002:13db` |
| Firmware | 13.60 (`0x13600007`) |
| Factory CU count | 36 of 40 |
| Broken groups | WGP 3 and WGP 4 |
| What fails | A native PS5 title. The shell boosts graphics to 2230 MHz and the game dies. |
| What still runs | PS4 games, and Linux games only while the GPU ceiling is held at 1600 MHz |

WGP 4 is the harvested pair. Read before any software mask:

| Array | `CC_GC_SHADER_ARRAY_CONFIG` | Meaning |
| --- | --- | --- |
| SE0 SH0 | `0xffe00000` | WGP 0–4 present |
| SE0 SH1 | `0xfff00000` | WGP 4 absent |
| SE1 SH0 | `0xffe00000` | WGP 0–4 present |
| SE1 SH1 | `0xfff00000` | WGP 4 absent |

`SPI_PG_ENABLE_STATIC_WGP_MASK` read `0` on all four arrays. Turning that fused-off WGP 4 back on has faulted this console (illegal instruction on SE0 SA0 WGP 4). WGP 3 still enumerates in that fuse. It is included in the defect mark because a native title still dies with both groups in play, and masking WGP 3 together with WGP 4 did not make PS5 games start.

The BC-250 product fuse is a different chip: 24 CUs, WGP 3 and WGP 4 both absent (`0xfff80000`, SPI mask `0x7`), 6 CPU cores, PCI `1002:13fe`. This retail harvest is not that fuse. Copying the 24-CU mask in software reported `active_cu_number 24` and the graphics ring still stopped at 2.0 GHz.

## What was run

`gpu-hold-1600.elf` was left running and Astro's Playroom (`PPSA01325`) was started.

- The holder had clamped 60 times.
- `gfxclk` last seen and read back at 1600 MHz. The CPU override had not fired (`cpu_pstate 0`).
- The shell clock line while the title was up: CPU 3200 MHz, GFX 1600 MHz.
- The splash unloaded and the shell moved to the application screen.
- That log has no WGP illegal-instruction fault and no application crash.

Earlier Astro launches at 1800, 1200, and the stock 2230 MHz boost died on the WGP 4 illegal instruction. The 1600 MHz hold is the first time this title got into the game. It does not clear the broken groups. It keeps the graphics clock off the step that kills them.

Valheim (`PPSA28824`) is a separate failure. With the same holder already at 1600 MHz, its Unity player aborted itself about one second after `eboot.bin` started (`0xa0020318`, `SYSTEM_ABNORMAL_TERMINATION_REQUEST`), before `Il2cppUserAssemblies.prx` loaded. That abort is not the 2.0 GHz ring stall.

Linux on this machine matches the same split. Valheim and Counter-Strike 2 stalled at a GPU clock of 2.0 GHz with the ceiling at 2.23 GHz. Holding `ps5-gpufreq` at 1600 MHz let those games keep drawing. The detail of that stall is [`GFX_RING_STALL.md`](GFX_RING_STALL.md).

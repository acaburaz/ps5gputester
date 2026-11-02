# Defective APU — PS5 games do not start (WGP 3 and 4)

This console is marked as a defective Oberon APU. Native PS5 games do not start on it because WGP 3 and WGP 4 are broken. PS4 games on the same console keep running, because they never sit on the graphics clock those broken groups are driven at.

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

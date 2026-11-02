# Graphics ring stall at 2.0 GHz

Catalogue for one console. The symptom is a native-PS5-versus-PS4 split on the PS5 system, reproduced under Linux as a graphics-ring timeout. The clock cap below is the only change that let a game keep drawing.

This is not the WGP-mask experiment in [`agc-driver/`](../agc-driver/README.md). That work tried to keep shader dispatch off a harvested WGP and was not a safe workaround. This catalogue is about the graphics clock.

## Symptom

On the PS5 system, native PS5 games crash. PS4 games on the same console keep running.

Under Bazzite on the same machine the same split shows up as a graphics-engine stall:

- The game renders, then the graphics ring stops.
- `gfx_0.0.0` times out with the emitted sequence two ahead of the signaled sequence. Two command buffers were submitted and never retired.
- The named thread is the renderer: Valheim `UnityGfxDeviceW`, Counter-Strike 2 `VKRenderThread`.
- The kernel log has no page-fault address, no shader illegal-instruction code, and no VRAM ECC error for these stalls.
- `VRAM is lost due to GPU reset` is printed after a full reset wipes video memory. It is a consequence of the reset, not a failing memory chip.
- The full reset then fails to bring the graphics block back, error `-110`. That failed resume is what kills the picture.
- With recovery left on, the desktop does not return without a power-off.
- With recovery forced off, the kernel logs `GPU recovery disabled`, does not start a GPU reset, and the display connector stays connected. The stuck submissions remain. Killing the game does not retire them, so the picture can stay frozen until the next Linux start.

The stall happened at a GPU clock of 2.0 GHz. The driver's ceiling at that time was 2.23 GHz.

## Console

| Item | Value |
| --- | --- |
| SoC | AMD Oberon, Cyan Skillfish, PCI `1002:13db` |
| Linux | Bazzite Deck, kernel `7.3.0 #60`, Mesa `26.2.4` |
| GPU clock driver | `ps5-gpufreq`, governor `simple_ondemand` |
| GPU steps | 400, 800, 1200, 1600, 2000, 2230 MHz |
| CPU | 8 cores / 16 threads, `ps5-cpufreq`, hardware maximum 3.5 GHz |
| Factory CU count | 36 of 40 |
| Fan target during the running test | 80°C |
| Temperature while CS2 ran at the capped clock | Tctl 70.0°C, GPU edge 69.2°C, NVMe 55.9°C |

Factory shader-array configuration, read per engine and array before any software cap:

| Array | `CC_GC_SHADER_ARRAY_CONFIG` | Meaning |
| --- | --- | --- |
| SE0 SH0 | `0xffe00000` | WGP 0–4 present |
| SE0 SH1 | `0xfff00000` | WGP 4 absent |
| SE1 SH0 | `0xffe00000` | WGP 0–4 present |
| SE1 SH1 | `0xfff00000` | WGP 4 absent |

`SPI_PG_ENABLE_STATIC_WGP_MASK` read `0` on all four arrays. WGP 3 was present on every array. The four fused-off CUs are WGP 4 on SH1 of both engines. Forcing that harvested WGP back on has faulted on this console. That fuse is the retail 36-CU harvest, not the BC-250 product fuse (24 CUs and 6 CPU cores, PCI `1002:13fe`).

## What this rules out

- A bad CPU. All 8 cores enumerate. The game that ran did so with the CPU still allowed up to 3.5 GHz.
- Failed GDDR6 as the cause of the timeout. The wipe message belongs to the reset that follows the stall.
- The boot line `VRAM: 512M`. That is the driver's starting video-memory slice. It grows from there.
- WGP 3 and WGP 4 as the sole cause. The stall still happened after this kernel was told to disable those WGPs and reported 24 CUs.
- An HDMI link-training failure. The link had trained at boot. The later freeze is the ring timeout.
- Copying the BC-250 24-CU configuration. That cap was applied. The ring still stopped at 2.0 GHz.

## Tests

### CU index versus WGP index

`amdgpu.disable_cu` on this kernel shifts the supplied bitmask left by 16 and writes that into the inactive-WGP field. CU numbers 6–9 land past the five WGP slots. The kernel logged `Disabling CU` and still published `active_cu_number 36`.

WGP numbers 3 and 4 land on the field. This boot line does that:

```text
amdgpu.disable_cu=0.0.3,0.0.4,0.1.3,0.1.4,1.0.3,1.0.4,1.1.3,1.1.4
```

Result: `Disabling CU` for those eight entries, then `active_cu_number 24`, and 48 SIMDs at 2 per CU. Valheim and CS2 still stalled while the GPU clock was at 2.0 GHz.

### Recovery

`/etc/modprobe.d/ps5-amdgpu.conf` contains `options amdgpu dpm=0 gpu_recovery=0`. The running module did not load it: live values were `dpm=-1` and `gpu_recovery=-1`, and a full reset still ran. `dpm=0` on the current PS5 amdgpu probe is the option that has caused `-EINVAL` and a dark display, so it stays off the command line.

Putting `amdgpu.gpu_recovery=0` on the kernel command line did load. The next Valheim stall logged `GPU recovery disabled` and `resets=0`. The display connector stayed connected. The ring kept repeating sequence 33551 signaled, 33553 emitted, including after the process was killed.

### Clock cap

A oneshot service writes `1600000000` to `/sys/class/devfreq/ps5-gpufreq/max_freq`.

On that boot the maximum read back as 1.6 GHz. Valheim's render thread had previously stalled about four minutes in, during world generation, at 2.0 GHz. With the cap, Valheim got into the world and the player could run around. At three minutes uptime the ring-timeout count was 0, Valheim had been running for about two and a half minutes, and the GPU clock was pinned at 1.6 GHz. CS2 then ran for at least six minutes with the clock under the cap (1.27 GHz observed) and the chip at 70°C.

CS2's own counter for the next launch is `cl_showfps 1`, saved as a user convar and as the Steam launch option `+cl_showfps 1`. That only displays the number. It does not change the clock.

## Possible solutions

1. Keep the Linux GPU ceiling at 1.6 GHz. This is the change that let the game keep drawing. The steps under it are 400, 800, 1200 and 1600 MHz. The failing step is 2000 MHz, and the driver will otherwise climb to 2230 MHz.
2. Keep `amdgpu.gpu_recovery=0` on the kernel command line. A later stall then does not take the display down with a failed graphics resume. It also does not clear the stuck ring.
3. Leave `dpm` at its default. Do not put `dpm=0` on this kernel's command line.
4. Leave the harvested WGP 4 disabled. The software 24-CU mask is optional for this stall: the clock cap is what changed the outcome, and the stall already happened at 24 CUs when the clock was 2.0 GHz.
5. `RADV_DEBUG=nohiz` is the documented shader workaround for this silicon when drawings are wrong. It was not the change that stopped this timeout, and it has not been tested here as a substitute for the clock cap.
6. An external report on `ps5-gpufreq` says that while any CPU core sits in the 3.3–3.5 GHz boost band, firmware can ignore the GPU cap and hold the GPU at 2.23 GHz. That was not measured on this console. During the working session a sampled CPU core was near 3.2 GHz and the GPU stayed under 1.6 GHz. A wrapper that only writes the GPU maximum can still lose that maximum if the CPU boost takes the clock back.

## What does not carry over to PS5 games

The 1.6 GHz service and `gpu_recovery=0` exist only in this Linux boot. On the PS5 menu the system sets the clocks. A native PS5 game is given the boosted GPU frequency, up to 2.23 GHz. A PS4 game on that system stays on a lighter graphics load and does not sit on the step that stopped the render thread. That is why PS4 games can run while PS5 games crash, on a CPU that is otherwise up.

A one-shot write before a title starts is not enough. The shell raises the GPU clock when the title enters its boosted mode. A wrapper has to hold the graphics clock at 1.6 GHz for the whole time the title runs, and it has to survive the firmware path that pairs CPU boost with a 2.23 GHz GPU ceiling.

`/dev/mp1` is the SMU device ShellCore uses. `MP1_IOCTL_GET_CLK` (`0x406cae01`) returns the clock table. `gfxclk` is the 32-bit word at byte offset `0x54`: 900 at home, 2230 while a native title is boosted. `MP1_IOCTL_SET_GFXCLK` (`0x8004ae17`) takes that value in MHz. Writes of 1800 and 1200 were read back at those values during the Astro tests. Those lower clocks did not move the WGP4 fault, so this holder is for the 2.0 GHz ring stall, not a substitute for leaving WGP 4 fused off. The AGC submit-mask proxy does not set a clock.

## Holder

`gpu-hold-1600.elf` is the holder. Source is [`gpu-hold-1600.c`](gpu-hold-1600.c). Load it from the payload manager and leave it running, then start the game.

- Every 50 ms it reads `gfxclk`.
- When the value is above 1600 it writes 1600 and reads it back.
- A home clock of 900 is left alone.
- The first clamp posts the seen value and the readback.
- If the readback stays above 1600 for 20 clamps, firmware is ignoring the graphics write. The holder then sends `MP1_IOCTL_SET_COREPSTATE` (`0x8008ae1d`) once, core and p-state 5, which is 1.6 GHz on the high-to-low CPU table.
- `/data/gpu-hold-1600.bin` stores the last seen clock, the last readback, the clamp count, and the override count.
- It stops after 6 hours. It does not edit command buffers and it does not turn WGP 4 on.

The Linux 1.6 GHz service still does not apply on the PS5 menu. This payload is the path that does.

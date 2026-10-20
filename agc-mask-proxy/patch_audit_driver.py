#!/usr/bin/env python3
"""Build a version-locked libSceAgcDriver SubmitDcb shadow-copy canary.

The patch is locked to inspected fakelib images. It extends the
executable load into existing alignment padding and redirects DT_INIT to a
small stub that tail-jumps to the original initializer. It also redirects the
inspected SubmitDcb export thunk through instruction-equivalent code in the
same executable padding. The init stub deliberately makes no imported calls:
a library's lazy PLT slots are not safe to call while its DT_INIT routine is
running. The submit stub allocates direct memory, assigns each distinct source
DCB a stable 64 KiB shadow slot, copies the commands, and forwards a private
description. It deliberately does not alter command words yet.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

EXPECTED_INIT = 0x10
MARKER = b"[agc-wgp-mask] SubmitDcb size audit; DCB unchanged\0"
AUDIT_PATH = b"/data/agc-dcb-00000000.bin\0"
AUDIT_MAGIC = 0x34434741  # "AGC4" in little endian

PROFILES = {
    "5590ee3fe3c2f73200674e17938a6f3e3dece8826a0ecc7249dcba2183adcf07": {
        "name": "Astro PPSA01325",
        "size": 174688,
        "submit_rva": 0x2960,
        "submit": bytes.fromhex("4889fe488d3d4eff0100e941f0ffff"),
        "open_plt_rva": 0xB850,
        "close_plt_rva": 0xB8B0,
        "direct_size_plt_rva": 0xB650,
        "allocate_plt_rva": 0xB660,
        "map_plt_rva": 0xB670,
    },
    "33cf01e315ae887f232b853cd3bef073017475ec1a318322105201677b90e623": {
        "name": "Animal Well PPSA22520",
        "size": 174096,
        "submit_rva": 0x2970,
        "submit": bytes.fromhex("4889fe488d3d3eff0100e9d1efffff"),
        "open_plt_rva": 0xBC60,
        "close_plt_rva": 0xBCC0,
        "direct_size_plt_rva": 0xBA80,
        "allocate_plt_rva": 0xBA90,
        "map_plt_rva": 0xBAA0,
    },
}

PT_LOAD = 1
PT_DYNAMIC = 2
PF_X = 1
PF_W = 2
PF_R = 4
DT_NULL = 0
DT_INIT = 12
PAGE_SIZE = 0x4000


def align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) & -alignment


def rel32(source_after_instruction: int, target: int) -> bytes:
    displacement = target - source_after_instruction
    if not -(1 << 31) <= displacement < (1 << 31):
        raise ValueError("relative branch is out of range")
    return struct.pack("<i", displacement)


def patch(source: Path, destination: Path) -> tuple[str, int, int]:
    data = bytearray(source.read_bytes())
    digest = hashlib.sha256(data).hexdigest()
    profile = PROFILES.get(digest)
    if profile is None or len(data) != profile["size"]:
        raise ValueError(f"unsupported driver: size={len(data)} sha256={digest}")
    if data[:4] != b"\x7fELF" or data[4:6] != b"\x02\x01":
        raise ValueError("expected a little-endian ELF64 image")

    phoff = struct.unpack_from("<Q", data, 0x20)[0]
    phentsize, phnum = struct.unpack_from("<HH", data, 0x36)
    executable = None
    dynamic = None
    loads = []
    for index in range(phnum):
        offset = phoff + index * phentsize
        p_type, p_flags = struct.unpack_from("<II", data, offset)
        p_offset, p_vaddr, _p_paddr, p_filesz, p_memsz = struct.unpack_from(
            "<QQQQQ", data, offset + 8
        )
        if p_type == PT_LOAD:
            loads.append((p_vaddr, p_offset, p_filesz, p_memsz, p_flags, offset))
            if p_flags & PF_X:
                executable = (offset, p_offset, p_vaddr, p_filesz, p_memsz)
        elif p_type == PT_DYNAMIC:
            dynamic = (p_offset, p_filesz)
    if executable is None or dynamic is None:
        raise ValueError("missing executable or dynamic program header")

    # Add one isolated RW page for hook state. Appending a new program header
    # preserves all source segments and gives later mask stages a safe home for
    # allocator metadata without borrowing undocumented driver BSS.
    new_phdr_offset = phoff + phnum * phentsize
    if phentsize != 56 or any(data[new_phdr_offset : new_phdr_offset + phentsize]):
        raise ValueError("no zero-filled ELF program-header slot for audit state")
    state_file_offset = align_up(len(data), PAGE_SIZE)
    state_rva = align_up(max(load[0] + load[3] for load in loads), PAGE_SIZE)
    if state_file_offset > len(data):
        data.extend(bytes(state_file_offset - len(data)))
    data.extend(bytes(PAGE_SIZE))
    struct.pack_into(
        "<IIQQQQQQ",
        data,
        new_phdr_offset,
        PT_LOAD,
        PF_R | PF_W,
        state_file_offset,
        state_rva,
        state_rva,
        PAGE_SIZE,
        PAGE_SIZE,
        PAGE_SIZE,
    )
    struct.pack_into("<H", data, 0x38, phnum + 1)
    # Runtime state: +0 magic, +4 largest DCB word count, +8 submission
    # count, +0x40 audit path, +0x80 forensic marker.
    audit_path_rva = state_rva + 0x40
    audit_path_file_offset = state_file_offset + 0x40
    marker_rva = state_rva + 0x80
    marker_file_offset = state_file_offset + 0x80
    struct.pack_into("<I", data, state_file_offset, AUDIT_MAGIC)
    data[audit_path_file_offset : audit_path_file_offset + len(AUDIT_PATH)] = AUDIT_PATH
    pool_ok_rva = state_rva + 0xC0
    pool_fail_rva = state_rva + 0xE0
    pool_name_rva = state_rva + 0x110
    for offset, value in (
        (0xC0, b"/data/agc-pool-ok.bin\0"),
        (0xE0, b"/data/agc-pool-fail.bin\0"),
        (0x110, b"agc-wgp-shadow\0"),
        (0x140, b"/data/agc-copy-ok.bin\0"),
    ):
        data[state_file_offset + offset : state_file_offset + offset + len(value)] = value

    phdr_offset, file_offset, virtual_address, file_size, memory_size = executable
    submit_rva = profile["submit_rva"]
    submit = profile["submit"]
    if virtual_address != 0 or file_offset + submit_rva + len(submit) > len(data):
        raise ValueError("unexpected executable mapping")
    submit_file_offset = file_offset + submit_rva
    if data[submit_file_offset : submit_file_offset + len(submit)] != submit:
        raise ValueError("SubmitDcb thunk bytes do not match the inspected build")

    init_hook_rva = (virtual_address + file_size + 15) & ~15
    submit_hook_rva = init_hook_rva + 16
    hook_file_offset = file_offset + (init_hook_rva - virtual_address)
    next_load_rva = min(load[0] for load in loads if load[0] > init_hook_rva)
    # jmp original_init. Do not call an imported function from DT_INIT: the
    # PS5 loader has not made this module's lazy PLT entries callable yet.
    init_code = bytearray(b"\xe9") + rel32(init_hook_rva + 5, EXPECTED_INIT)

    # Count submissions and encode each new maximum DCB size into an empty file
    # name. This needs only the driver's existing open/close imports and avoids
    # changing its dynamic metadata. Preserve the incoming description in rdi.
    context_rva = submit_rva + 10 + struct.unpack_from("<i", submit, 6)[0]
    common_submit_rva = submit_rva + len(submit) + struct.unpack_from("<i", submit, 11)[0]
    submit_code = bytearray(b"\x80\x3d")
    submit_code += rel32(submit_hook_rva + 7, state_rva + 0x20)
    submit_code += b"\x00\x0f\x85\x00\x00\x00\x00"
    pool_ready_branch_offset = len(submit_code) - 4
    submit_code += b"\x57\x48\x83\xec\x10\xc6\x05"
    submit_code += rel32(submit_hook_rva + len(submit_code) + 5, state_rva + 0x20) + b"\x02"
    submit_code += b"\xe8" + rel32(
        submit_hook_rva + len(submit_code) + 5, profile["direct_size_plt_rva"]
    )
    submit_code += (
        b"\x31\xff\x48\x89\xc6\xba\x00\x00\x00\x01\xb9\x00\x00\x01\x00"
        b"\x41\xb8\x0c\x00\x00\x00\x4c\x8d\x0d"
    )
    submit_code += rel32(submit_hook_rva + len(submit_code) + 4, state_rva + 0x18)
    submit_code += b"\xe8" + rel32(
        submit_hook_rva + len(submit_code) + 5, profile["allocate_plt_rva"]
    )
    submit_code += b"\x85\xc0\x0f\x85\x00\x00\x00\x00"
    allocate_fail_branch = len(submit_code) - 4
    submit_code += b"\x48\x8d\x3d"
    submit_code += rel32(
        submit_hook_rva + len(submit_code) + 4, state_rva + 0x10
    )
    submit_code += (
        b"\xbe\x00\x00\x00\x01\xba\x33\x00\x00\x00\x31\xc9\x4c\x8b\x05"
    )
    submit_code += rel32(submit_hook_rva + len(submit_code) + 4, state_rva + 0x18)
    submit_code += b"\x41\xb9\x00\x00\x01\x00\x48\x8d\x05"
    submit_code += rel32(submit_hook_rva + len(submit_code) + 4, pool_name_rva)
    submit_code += b"\x48\x89\x04\x24\xe8"
    submit_code += rel32(
        submit_hook_rva + len(submit_code) + 4, profile["map_plt_rva"]
    )
    submit_code += b"\x85\xc0\x0f\x85\x00\x00\x00\x00"
    map_fail_branch = len(submit_code) - 4
    submit_code += b"\xc6\x05"
    submit_code += rel32(
        submit_hook_rva + len(submit_code) + 5, state_rva + 0x20
    )
    submit_code += b"\x01\x48\x8d\x3d"
    submit_code += rel32(submit_hook_rva + len(submit_code) + 4, pool_ok_rva)
    submit_code += b"\xe9\x00\x00\x00\x00"
    report_branch = len(submit_code) - 4
    fail_offset = len(submit_code)
    submit_code += b"\x48\x8d\x3d"
    submit_code += rel32(
        submit_hook_rva + len(submit_code) + 4, pool_fail_rva
    )
    report_offset = len(submit_code)
    submit_code += b"\xbe\x01\x06\x00\x00\xba\xa4\x01\x00\x00\x31\xc0\xe8"
    submit_code += rel32(submit_hook_rva + len(submit_code) + 4, profile["open_plt_rva"])
    submit_code += b"\x85\xc0\x78\x07\x89\xc7\xe8"
    submit_code += rel32(
        submit_hook_rva + len(submit_code) + 4, profile["close_plt_rva"]
    )
    submit_code += b"\x48\x83\xc4\x10\x5f"
    stats_offset = len(submit_code)
    for displacement_offset, target_offset in (
        (pool_ready_branch_offset, stats_offset),
        (allocate_fail_branch, fail_offset),
        (map_fail_branch, fail_offset),
        (report_branch, report_offset),
    ):
        struct.pack_into(
            "<i", submit_code, displacement_offset, target_offset - (displacement_offset + 4)
        )

    submit_code += b"\xf0\x48\xff\x05"
    submit_code += rel32(submit_hook_rva + len(submit_code) + 4, state_rva + 8)
    submit_code += b"\x8b\x47\x08\x3b\x05"
    submit_code += rel32(submit_hook_rva + len(submit_code) + 4, state_rva + 4)
    submit_code += b"\x0f\x86\x00\x00\x00\x00\x89\x05"
    forward_branch_disp_offset = len(submit_code) - 6
    submit_code += rel32(submit_hook_rva + len(submit_code) + 4, state_rva + 4)
    submit_code += b"\x57\x48\x8d\x3d"
    submit_code += rel32(submit_hook_rva + len(submit_code) + 4, audit_path_rva + 14)
    submit_code += b"\xb9\x08\x00\x00\x00"
    hex_loop_offset = len(submit_code)
    submit_code += (
        b"\xc1\xc0\x04\x89\xc6\x83\xe6\x0f\x83\xfe\x09\x76\x03"
        b"\x83\xc6\x27\x83\xc6\x30\x40\x88\x37\x48\xff\xc7\xff\xc9\x75\x00"
    )
    loop_branch_index = len(submit_code) - 1
    loop_displacement = hex_loop_offset - (loop_branch_index + 1)
    if not -128 <= loop_displacement <= 127:
        raise ValueError("hex conversion loop is out of range")
    submit_code[loop_branch_index] = loop_displacement & 0xFF
    submit_code += b"\x48\x8d\x3d"
    submit_code += rel32(submit_hook_rva + len(submit_code) + 4, audit_path_rva)
    submit_code += b"\xbe\x01\x06\x00\x00\xba\xa4\x01\x00\x00\x31\xc0\xe8"
    submit_code += rel32(submit_hook_rva + len(submit_code) + 4, profile["open_plt_rva"])
    submit_code += b"\x85\xc0\x78\x07\x89\xc7"
    submit_code += b"\xe8" + rel32(submit_hook_rva + len(submit_code) + 5, profile["close_plt_rva"])
    submit_code += b"\x5f"
    copy_offset = len(submit_code)

    # Copy each DCB into a stable per-source 64 KiB direct-memory slot. The
    # pointer table starts at +0x200 and 256 private descriptions start at
    # +0xa00. Reusing a source pointer reuses its slot, matching the game's
    # own lifetime discipline without wrapping over unrelated in-flight DCBs.
    labels: dict[str, int] = {}
    label_fixups: list[tuple[int, str]] = []

    def copy_label(name: str) -> None:
        labels[name] = len(submit_code)

    def copy_branch(opcode: bytes, target: str) -> None:
        submit_code.extend(opcode)
        displacement = len(submit_code)
        submit_code.extend(b"\0\0\0\0")
        label_fixups.append((displacement, target))

    def copy_rip(prefix: bytes, target: int, suffix: bytes = b"") -> None:
        submit_code.extend(prefix)
        submit_code.extend(
            rel32(submit_hook_rva + len(submit_code) + 4 + len(suffix), target)
        )
        submit_code.extend(suffix)

    copy_label("copy_gate")
    copy_rip(b"\x80\x3d", state_rva + 0x20, b"\x01")
    copy_branch(b"\x0f\x85", "original")
    submit_code += b"\x49\x89\xfa\x41\x8b\x4a\x08\x85\xc9"
    copy_branch(b"\x0f\x84", "original")
    submit_code += b"\x81\xf9\x00\x40\x00\x00"
    copy_branch(b"\x0f\x87", "original")
    submit_code += b"\x4d\x8b\x1a\x4d\x85\xdb"
    copy_branch(b"\x0f\x84", "original")
    copy_rip(b"\x4c\x8d\x05", state_rva + 0x200)
    submit_code += b"\x31\xd2"
    copy_label("search")
    submit_code += b"\x49\x8b\x04\xd0\x4c\x39\xd8"
    copy_branch(b"\x0f\x84", "found")
    submit_code += b"\x48\x85\xc0"
    copy_branch(b"\x0f\x85", "next")
    submit_code += b"\x31\xc0\xf0\x4d\x0f\xb1\x1c\xd0"
    copy_branch(b"\x0f\x84", "found")
    submit_code += b"\x4c\x39\xd8"
    copy_branch(b"\x0f\x84", "found")
    copy_label("next")
    submit_code += b"\xff\xc2\x81\xfa\x00\x01\x00\x00"
    copy_branch(b"\x0f\x82", "search")
    copy_branch(b"\xe9", "original")
    copy_label("found")
    copy_rip(b"\x4c\x8b\x0d", state_rva + 0x10)
    submit_code += (
        b"\x89\xd0\x48\xc1\xe0\x10\x49\x01\xc1"
    )
    copy_rip(b"\x48\x8d\x3d", state_rva + 0xA00)
    submit_code += (
        b"\x89\xd0\x48\xc1\xe0\x04\x48\x01\xc7"
        b"\xf3\x41\x0f\x6f\x02\xf3\x0f\x7f\x07\x4c\x89\x0f"
        b"\x48\x89\xfa\x4c\x89\xcf\x4c\x89\xde\xf3\xa5\x48\x89\xd6"
    )
    copy_rip(b"\x80\x3d", state_rva + 0x21, b"\x00")
    copy_branch(b"\x0f\x85", "prepared")
    copy_rip(b"\xc6\x05", state_rva + 0x21, b"\x01")
    submit_code += b"\x56"
    copy_rip(b"\x48\x8d\x3d", state_rva + 0x140)
    submit_code += b"\xbe\x01\x06\x00\x00\xba\xa4\x01\x00\x00\x31\xc0\xe8"
    submit_code += rel32(submit_hook_rva + len(submit_code) + 4, profile["open_plt_rva"])
    submit_code += b"\x85\xc0"
    copy_branch(b"\x0f\x88", "marker_done")
    submit_code += b"\x89\xc7\xe8"
    submit_code += rel32(submit_hook_rva + len(submit_code) + 4, profile["close_plt_rva"])
    copy_label("marker_done")
    submit_code += b"\x5e"
    copy_label("prepared")
    submit_code += b"\x48\x8d\x3d"
    submit_code += rel32(submit_hook_rva + len(submit_code) + 4, context_rva)
    copy_branch(b"\xe9", "common")
    copy_label("original")
    submit_code += b"\x48\x89\xfe\x48\x8d\x3d"
    submit_code += rel32(submit_hook_rva + len(submit_code) + 4, context_rva)
    copy_label("common")
    submit_code += b"\xe9" + rel32(submit_hook_rva + len(submit_code) + 5, common_submit_rva)
    for displacement_offset, target in label_fixups:
        target_offset = labels[target]
        struct.pack_into(
            "<i",
            submit_code,
            displacement_offset,
            target_offset - (displacement_offset + 4),
        )
    struct.pack_into(
        "<i",
        submit_code,
        forward_branch_disp_offset,
        copy_offset - (forward_branch_disp_offset + 4),
    )

    code = init_code + bytes(16 - len(init_code)) + submit_code
    end_rva = init_hook_rva + len(code)
    marker_end_rva = marker_rva + len(MARKER)
    if end_rva > next_load_rva or hook_file_offset + len(code) > len(data):
        raise ValueError("audit stub does not fit in executable alignment padding")
    if marker_end_rva > state_rva + PAGE_SIZE:
        raise ValueError("audit marker does not fit in state page")
    if any(data[hook_file_offset : hook_file_offset + len(code)]):
        raise ValueError("audit stub target is not zero-filled padding")

    dynamic_offset, dynamic_size = dynamic
    init_value_offset = None
    for offset in range(dynamic_offset, dynamic_offset + dynamic_size, 16):
        tag, value = struct.unpack_from("<QQ", data, offset)
        if tag == DT_INIT:
            if value != EXPECTED_INIT:
                raise ValueError(f"unexpected DT_INIT value 0x{value:x}")
            init_value_offset = offset + 8
            break
        if tag == DT_NULL:
            break
    if init_value_offset is None:
        raise ValueError("DT_INIT was not found")


    data[hook_file_offset : hook_file_offset + len(code)] = code
    submit_branch = b"\xe9" + rel32(submit_rva + 5, submit_hook_rva)
    data[submit_file_offset : submit_file_offset + len(submit)] = (
        submit_branch + b"\x90" * (len(submit) - len(submit_branch))
    )
    data[marker_file_offset : marker_file_offset + len(MARKER)] = MARKER
    struct.pack_into("<Q", data, init_value_offset, init_hook_rva)
    new_load_size = end_rva - virtual_address
    struct.pack_into("<Q", data, phdr_offset + 32, new_load_size)
    struct.pack_into("<Q", data, phdr_offset + 40, max(memory_size, new_load_size))

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return profile["name"], init_hook_rva, len(code) + len(MARKER)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    profile_name, hook_rva, payload_size = patch(args.source, args.destination)
    digest = hashlib.sha256(args.destination.read_bytes()).hexdigest()
    print(f"wrote {args.destination}")
    print(f"profile={profile_name}")
    print(f"audit_init_rva=0x{hook_rva:x} payload_bytes={payload_size}")
    print(f"sha256={digest}")


if __name__ == "__main__":
    main()

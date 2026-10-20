#!/usr/bin/env python3
"""Build the first, logging-only libSceAgcDriver canary.

The patch is locked to inspected fakelib images. It extends the
executable load into existing alignment padding, redirects DT_INIT to a small
stub that prints one marker through the driver's existing puts PLT entry, then
tail-jumps to the original initializer. SubmitDcb is deliberately untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

EXPECTED_INIT = 0x10
MARKER = b"[agc-wgp-mask] audit driver loaded; SubmitDcb unchanged\0"

PROFILES = {
    "5590ee3fe3c2f73200674e17938a6f3e3dece8826a0ecc7249dcba2183adcf07": {
        "name": "Astro PPSA01325",
        "size": 174688,
        "submit_rva": 0x2960,
        "submit": bytes.fromhex("4889fe488d3d4eff0100e941f0ffff"),
        "puts_plt_rva": 0xB8D0,
    },
    "33cf01e315ae887f232b853cd3bef073017475ec1a318322105201677b90e623": {
        "name": "Animal Well PPSA22520",
        "size": 174096,
        "submit_rva": 0x2970,
        "submit": bytes.fromhex("4889fe488d3d3eff0100e9d1efffff"),
        "puts_plt_rva": 0xBCE0,
    },
}

PT_LOAD = 1
PT_DYNAMIC = 2
PF_X = 1
DT_NULL = 0
DT_INIT = 12


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
            loads.append((p_vaddr, p_offset, p_filesz))
            if p_flags & PF_X:
                executable = (offset, p_offset, p_vaddr, p_filesz, p_memsz)
        elif p_type == PT_DYNAMIC:
            dynamic = (p_offset, p_filesz)
    if executable is None or dynamic is None:
        raise ValueError("missing executable or dynamic program header")

    phdr_offset, file_offset, virtual_address, file_size, memory_size = executable
    submit_rva = profile["submit_rva"]
    submit = profile["submit"]
    if virtual_address != 0 or file_offset + submit_rva + len(submit) > len(data):
        raise ValueError("unexpected executable mapping")
    submit_file_offset = file_offset + submit_rva
    if data[submit_file_offset : submit_file_offset + len(submit)] != submit:
        raise ValueError("SubmitDcb thunk bytes do not match the inspected build")

    hook_rva = (virtual_address + file_size + 15) & ~15
    hook_file_offset = file_offset + (hook_rva - virtual_address)
    next_load_rva = min(vaddr for vaddr, _off, _size in loads if vaddr > hook_rva)

    # sub rsp,8; lea marker(%rip),rdi; call puts@plt; add rsp,8; jmp original_init
    marker_rva = hook_rva + 25
    code = bytearray(b"\x48\x83\xec\x08\x48\x8d\x3d")
    code += rel32(hook_rva + 11, marker_rva)
    code += b"\xe8" + rel32(hook_rva + 16, profile["puts_plt_rva"])
    code += b"\x48\x83\xc4\x08\xe9" + rel32(hook_rva + 25, EXPECTED_INIT)
    payload = code + MARKER
    end_rva = hook_rva + len(payload)
    if end_rva > next_load_rva or hook_file_offset + len(payload) > len(data):
        raise ValueError("audit stub does not fit in executable alignment padding")
    if any(data[hook_file_offset : hook_file_offset + len(payload)]):
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

    data[hook_file_offset : hook_file_offset + len(payload)] = payload
    struct.pack_into("<Q", data, init_value_offset, hook_rva)
    new_load_size = end_rva - virtual_address
    struct.pack_into("<Q", data, phdr_offset + 32, new_load_size)
    struct.pack_into("<Q", data, phdr_offset + 40, max(memory_size, new_load_size))

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return profile["name"], hook_rva, len(payload)


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

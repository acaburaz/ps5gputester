#!/usr/bin/env python3
"""Build a no-call libSceAgcDriver SubmitDcb forwarding canary.

The patch is locked to inspected fakelib images. It extends the
executable load into existing alignment padding and redirects DT_INIT to a
small stub that tail-jumps to the original initializer. It also redirects the
inspected SubmitDcb export thunk through instruction-equivalent code in the
same executable padding. The stub deliberately
makes no imported calls: a library's lazy PLT slots are not safe to call while
its DT_INIT routine is running.  A readable marker remains embedded for
forensic identification. The submitted command buffer is deliberately
untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

EXPECTED_INIT = 0x10
MARKER = b"[agc-wgp-mask] SubmitDcb forwarding canary; DCB unchanged\0"

PROFILES = {
    "5590ee3fe3c2f73200674e17938a6f3e3dece8826a0ecc7249dcba2183adcf07": {
        "name": "Astro PPSA01325",
        "size": 174688,
        "submit_rva": 0x2960,
        "submit": bytes.fromhex("4889fe488d3d4eff0100e941f0ffff"),
    },
    "33cf01e315ae887f232b853cd3bef073017475ec1a318322105201677b90e623": {
        "name": "Animal Well PPSA22520",
        "size": 174096,
        "submit_rva": 0x2970,
        "submit": bytes.fromhex("4889fe488d3d3eff0100e9d1efffff"),
    },
}

PT_LOAD = 1
PT_DYNAMIC = 2
PF_X = 1
PF_R = 4
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
            loads.append((p_vaddr, p_offset, p_filesz, p_memsz, p_flags, offset))
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

    init_hook_rva = (virtual_address + file_size + 15) & ~15
    submit_hook_rva = init_hook_rva + 16
    hook_file_offset = file_offset + (init_hook_rva - virtual_address)
    next_load_rva = min(load[0] for load in loads if load[0] > init_hook_rva)
    readable = min(
        (load for load in loads if load[0] >= next_load_rva and load[4] & PF_R and not load[4] & PF_X),
        key=lambda load: load[0],
    )
    read_rva, read_file_offset, read_file_size, read_memory_size, _flags, read_phdr_offset = readable
    marker_rva = (read_rva + read_file_size + 15) & ~15
    marker_file_offset = read_file_offset + (marker_rva - read_rva)
    next_after_read = min(load[0] for load in loads if load[0] > marker_rva)

    # jmp original_init. Do not call an imported function from DT_INIT: the
    # PS5 loader has not made this module's lazy PLT entries callable yet.
    init_code = bytearray(b"\xe9") + rel32(init_hook_rva + 5, EXPECTED_INIT)

    # Preserve the exact original export-thunk semantics in a new location:
    # mov rsi,rdi; lea submission_context(%rip),rdi; jmp common_submit.
    context_rva = submit_rva + 10 + struct.unpack_from("<i", submit, 6)[0]
    common_submit_rva = submit_rva + len(submit) + struct.unpack_from("<i", submit, 11)[0]
    submit_code = bytearray(b"\x48\x89\xfe\x48\x8d\x3d")
    submit_code += rel32(submit_hook_rva + 10, context_rva)
    submit_code += b"\xe9" + rel32(submit_hook_rva + 15, common_submit_rva)

    code = init_code + bytes(16 - len(init_code)) + submit_code
    end_rva = init_hook_rva + len(code)
    marker_end_rva = marker_rva + len(MARKER)
    if end_rva > next_load_rva or hook_file_offset + len(code) > len(data):
        raise ValueError("audit stub does not fit in executable alignment padding")
    if marker_end_rva > next_after_read or marker_file_offset + len(MARKER) > len(data):
        raise ValueError("audit marker does not fit in readable alignment padding")
    if any(data[hook_file_offset : hook_file_offset + len(code)]):
        raise ValueError("audit stub target is not zero-filled padding")
    if any(data[marker_file_offset : marker_file_offset + len(MARKER)]):
        raise ValueError("audit marker target is not zero-filled padding")

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
    new_read_size = marker_end_rva - read_rva
    struct.pack_into("<Q", data, read_phdr_offset + 32, new_read_size)
    struct.pack_into("<Q", data, read_phdr_offset + 40, max(read_memory_size, new_read_size))

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

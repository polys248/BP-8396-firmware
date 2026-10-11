import sys, struct, re

path = sys.argv[1]
lo = int(sys.argv[2], 16)
hi = int(sys.argv[3], 16)
raw = open(path, "rb").read()
assert raw[:4] == b"\x7fELF"
is64 = raw[4] == 2
le = raw[5] == 1
end = "<" if le else ">"
if is64:
    e_phoff, = struct.unpack_from(end+"Q", raw, 0x20)
    e_phentsize, e_phnum = struct.unpack_from(end+"HH", raw, 0x36)
    segs = []
    for i in range(e_phnum):
        off = e_phoff + i*e_phentsize
        p_type, = struct.unpack_from(end+"I", raw, off)
        p_offset, p_vaddr = struct.unpack_from(end+"QQ", raw, off+8)
        p_filesz, = struct.unpack_from(end+"Q", raw, off+32)
        if p_type == 1:
            segs.append((p_vaddr, p_offset, p_filesz))
else:
    e_phoff, = struct.unpack_from(end+"I", raw, 0x1c)
    e_phentsize, e_phnum = struct.unpack_from(end+"HH", raw, 0x2a)
    segs = []
    for i in range(e_phnum):
        off = e_phoff + i*e_phentsize
        p_type, p_offset, p_vaddr, p_paddr, p_filesz = struct.unpack_from(end+"IIIII", raw, off)
        if p_type == 1:
            segs.append((p_vaddr, p_offset, p_filesz))

def v2o(v):
    for vaddr, offset, filesz in segs:
        if vaddr <= v < vaddr + filesz:
            return offset + (v - vaddr)
    return None

o_lo, o_hi = v2o(lo), v2o(hi)
if o_lo is None:
    print("vaddr not in any LOAD segment; segs:", [(hex(a),hex(o),hex(s)) for a,o,s in segs]); sys.exit()
blob = raw[o_lo:o_hi]
# find printable strings with their vaddr
for m in re.finditer(rb"[ -~]{2,}", blob):
    v = lo + m.start()
    print(f"0x{v:05x}: {m.group().decode('latin1')!r}")

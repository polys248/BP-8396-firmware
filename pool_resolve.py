import sys, struct
path = sys.argv[1]
raw = open(path, "rb").read()
end = "<"
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
def rd32(v):
    o = v2o(v); return struct.unpack_from("<I", raw, o)[0]
def cstr(v):
    o = v2o(v)
    e = raw.index(b"\x00", o)
    return raw[o:e].decode("latin1")
# (name, pool_vaddr, pc_at_add_plus_extra)
pairs = [
 ("needle",     0x216c4, 0x215e0),
 ("needle_00",  0x216c8, 0x215de),
 ("file_printf",0x216cc, 0x21614),
 ("suffix_len", 0x216d0, 0x2163e),
 ("join_fmt",   0x216d8, 0x21680),
]
for name, pool, pc in pairs:
    lit = rd32(pool)
    sv = (lit + pc) & 0xffffffff
    try:
        s = cstr(sv)
    except Exception as e:
        s = f"<unresolved {e}>"
    print(f"{name:16} pool=0x{pool:x} lit=0x{lit:x} -> str@0x{sv:x} = {s!r}")

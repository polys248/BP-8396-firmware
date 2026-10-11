import sys, struct
path = sys.argv[1]
toks = [t.encode() for t in sys.argv[2:]]
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
def o2v(o):
    for vaddr, offset, filesz in segs:
        if offset <= o < offset + filesz:
            return vaddr + (o - offset)
    return None
for t in toks:
    needle = t + b"\x00"
    i = 0; hits = []
    while True:
        j = raw.find(needle, i)
        if j == -1: break
        # require it to start at a string boundary (prev byte is 0 or non-print)
        prev = raw[j-1] if j > 0 else 0
        if prev == 0 or prev < 0x20 or prev > 0x7e:
            v = o2v(j)
            hits.append((j, v))
        i = j + 1
    print(f"{t.decode()!r}: " + ", ".join(f"off=0x{o:x} vaddr={'0x%x'%v if v else '?'}" for o,v in hits[:12]) or f"{t.decode()!r}: none")

import struct, sys

def parse(path):
    d = open(path, "rb").read()
    magic, total, off_struct, off_strs, off_rsvd, ver, lastver, boot, size_strs, size_struct = \
        struct.unpack_from(">10I", d, 0)
    assert magic == 0xd00dfeed, f"bad magic {magic:08x}"
    print(f"DTB ok: total={total} ver={ver} off_struct=0x{off_struct:x} "
          f"off_strs=0x{off_strs:x} size_strs={size_strs}")
    strs = d[off_strs:off_strs + size_strs]

    def cstr(blob, o):
        e = blob.index(b"\0", o)
        return blob[o:e].decode("latin1")

    p = off_struct
    depth = 0
    want = {"compatible", "model", "machine"}
    out = []
    while p < off_struct + size_struct:
        tag, = struct.unpack_from(">I", d, p); p += 4
        if tag == 1:  # BEGIN_NODE
            name = cstr(d, p)
            p += (len(name) + 4) & ~3
            depth += 1
        elif tag == 2:  # END_NODE
            depth -= 1
        elif tag == 3:  # PROP
            plen, noff = struct.unpack_from(">II", d, p); p += 8
            val = d[p:p + plen]
            p = (p + plen + 3) & ~3
            pname = cstr(strs, noff)
            if pname in want and depth <= 2:
                txt = val.rstrip(b"\0").replace(b"\0", b" | ").decode("latin1")
                out.append((depth, pname, txt))
        elif tag == 4:  # NOP
            pass
        elif tag == 9:  # END
            break
        else:
            print(f"  (unknown tag {tag} at 0x{p-4:x}; stopping)"); break
    for depth, pname, txt in out[:12]:
        print(f"  [{depth}] {pname} = {txt!r}")

parse(sys.argv[1])

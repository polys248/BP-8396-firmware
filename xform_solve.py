import struct, sys

raw = open(sys.argv[1], "rb").read()

def g_left_lsbfirst(d):          # inverse of global >>1, carry byte0->byteN
    out = bytearray(len(d)); c = 0
    for i, b in enumerate(d):
        out[i] = ((b << 1) & 0xFF) | c; c = (b >> 7) & 1
    return bytes(out)

def g_left_msbfirst(d):          # carry flows from next byte (byteN->byte0)
    out = bytearray(len(d)); c = 0
    for i in range(len(d) - 1, -1, -1):
        b = d[i]; out[i] = ((b << 1) & 0xFF) | c; c = (b >> 7) & 1
    return bytes(out)

def perword(d, n, be, left):
    out = bytearray(len(d))
    fmt = (">" if be else "<") + {2: "H", 4: "I", 8: "Q"}[n]
    mask = (1 << (8 * n)) - 1
    for o in range(0, len(d) - n + 1, n):
        w, = struct.unpack_from(fmt, d, o)
        w = ((w << 1) & mask) if left else (w >> 1)
        struct.pack_into(fmt, out, o, w)
    return bytes(out)

cands = {
    "global<<1 lsb-first": g_left_lsbfirst(raw),
    "global<<1 msb-first": g_left_msbfirst(raw),
    "word32 LE <<1": perword(raw, 4, False, True),
    "word32 BE <<1": perword(raw, 4, True, True),
    "word64 LE <<1": perword(raw, 8, False, True),
    "word64 BE <<1": perword(raw, 8, True, True),
    "word16 LE <<1": perword(raw, 2, False, True),
}

# score: in a valid DTB the strings block (end of file, before padding) is
# pure printable ASCII + NULs. Score = count of printable/NUL in last 2600 bytes
# AND require magic d00dfeed at offset 0.
def score(p):
    if p[:4] != b"\xd0\x0d\xfe\xed":
        return -1
    total, = struct.unpack_from(">I", p, 4)
    off_s, = struct.unpack_from(">I", p, 12)
    size_s, = struct.unpack_from(">I", p, 32)
    if not (0 < off_s < len(p) and 0 < size_s < 8000 and off_s + size_s <= len(p) + 4):
        return 0
    blk = p[off_s:off_s + size_s]
    good = sum(1 for c in blk if c == 0 or 32 <= c < 127)
    return good * 1000 // max(1, len(blk))

for name, p in cands.items():
    print(f"{score(p):>6}  {name:<22} first16={p[:16].hex()}")

import struct, sys, zlib

PKG = sys.argv[1]

def deshift(data: bytes) -> bytes:
    n = len(data) & ~1
    out = bytearray(data)
    for o in range(0, n, 2):
        w = data[o] | (data[o + 1] << 8)
        w = ((w << 1) | (w >> 15)) & 0xFFFF
        out[o] = w & 0xFF
        out[o + 1] = (w >> 8) & 0xFF
    return bytes(out)

def parse(path):
    with open(path, "rb") as f:
        hdr = f.read(0x90)
        count, = struct.unpack_from("<I", hdr, 0x64)
        tbl, base = struct.unpack_from("<QQ", hdr, 0x68)
        f.seek(tbl); raw = f.read(count * 0x50)
        items = []
        for i in range(count):
            e = raw[i*0x50:(i+1)*0x50]
            name = e[0x10:0x28].split(b"\0")[0].decode()
            flags, csum = struct.unpack_from("<II", e, 0x28)
            size, asize, off = struct.unpack_from("<QQQ", e, 0x30)
            f.seek(base + off)
            data = f.read(size)
            items.append(dict(name=name, flags=flags, csum=csum, size=size,
                              asize=asize, off=off, data=data))
    return items

# ---- parametric CRC32 (table-driven), reflected and non-reflected ----
_tbl_cache = {}
def _table(poly, refl):
    key = (poly, refl)
    if key in _tbl_cache:
        return _tbl_cache[key]
    t = []
    if refl:
        # reverse poly
        rp = 0
        for i in range(32):
            rp = (rp << 1) | ((poly >> i) & 1)
        for n in range(256):
            c = n
            for _ in range(8):
                c = (c >> 1) ^ (rp if (c & 1) else 0)
            t.append(c & 0xFFFFFFFF)
    else:
        for n in range(256):
            c = n << 24
            for _ in range(8):
                c = ((c << 1) ^ (poly if (c & 0x80000000) else 0)) & 0xFFFFFFFF
            t.append(c)
    _tbl_cache[key] = t
    return t

def crc32(data, poly, init, refl, xorout):
    t = _table(poly, refl)
    c = init & 0xFFFFFFFF
    if refl:
        for b in data:
            c = (c >> 8) ^ t[(c ^ b) & 0xFF]
    else:
        for b in data:
            c = ((c << 8) ^ t[((c >> 24) ^ b) & 0xFF]) & 0xFFFFFFFF
    return (c ^ xorout) & 0xFFFFFFFF

CATALOG = {
    "CRC32/zlib":    (0x04C11DB7, 0xFFFFFFFF, True,  0xFFFFFFFF),
    "CRC32/JAMCRC":  (0x04C11DB7, 0xFFFFFFFF, True,  0x00000000),
    "CRC32/BZIP2":   (0x04C11DB7, 0xFFFFFFFF, False, 0xFFFFFFFF),
    "CRC32/MPEG2":   (0x04C11DB7, 0xFFFFFFFF, False, 0x00000000),
    "CRC32/POSIX":   (0x04C11DB7, 0x00000000, False, 0xFFFFFFFF),
    "CRC32/XFER":    (0x000000AF, 0x00000000, False, 0x00000000),
    "CRC32C":        (0x1EDC6F41, 0xFFFFFFFF, True,  0xFFFFFFFF),
    "CRC32D":        (0xA833982B, 0xFFFFFFFF, True,  0xFFFFFFFF),
    "CRC32/AUTOSAR": (0xF4ACFB13, 0xFFFFFFFF, True,  0xFFFFFFFF),
    "CRC32/CDROMEDC":(0x8001801B, 0x00000000, True,  0x00000000),
    "CRC32/zero":    (0x04C11DB7, 0x00000000, True,  0x00000000),
}

def simple(data):
    out = {}
    out["sum8"] = sum(data) & 0xFFFFFFFF
    out["adler32"] = zlib.adler32(data) & 0xFFFFFFFF
    w = 0
    for i in range(0, len(data) & ~3, 4):
        w = (w + struct.unpack_from("<I", data, i)[0]) & 0xFFFFFFFF
    out["sumLE32"] = w
    x = 0
    for i in range(0, len(data) & ~3, 4):
        x ^= struct.unpack_from("<I", data, i)[0]
    out["xorLE32"] = x & 0xFFFFFFFF
    return out

def candidates(data):
    res = {}
    for name, (poly, init, refl, xo) in CATALOG.items():
        res[name] = crc32(data, poly, init, refl, xo)
    res.update(simple(data))
    return res

items = parse(PKG)
# find the algorithm using small items only (<= 300 KB)
small = [it for it in items if it["size"] <= 300000]
print(f"{len(items)} items; testing {len(small)} small ones\n")

winners = None
for it in small:
    obf = it["data"]
    pln = deshift(obf)
    row = {}
    for dom, d in (("obf", obf), ("plain", pln)):
        for algo, val in candidates(d).items():
            row[f"{dom}:{algo}"] = val
    hits = {k for k, v in row.items() if v == it["csum"]}
    print(f"{it['name']:<20} size={it['size']:>8} csum={it['csum']:#010x}  hits={sorted(hits) if hits else 'NONE'}")
    winners = hits if winners is None else (winners & hits)

print(f"\nalgorithms matching ALL small items: {sorted(winners) if winners else 'NONE'}")

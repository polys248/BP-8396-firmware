import os, struct, sys

def deshift(data: bytes) -> bytes:
    n = len(data) & ~1
    out = bytearray(data)
    for o in range(0, n, 2):
        w = data[o] | (data[o + 1] << 8)
        w = ((w << 1) | (w >> 15)) & 0xFFFF
        out[o] = w & 0xFF
        out[o + 1] = (w >> 8) & 0xFF
    return bytes(out)

PKG = sys.argv[1]
OUT = sys.argv[2]
os.makedirs(OUT, exist_ok=True)
raw = open(PKG, "rb").read()
count, = struct.unpack_from("<I", raw, 0x64)
tbl, base = struct.unpack_from("<QQ", raw, 0x68)
strsz, = struct.unpack_from("<I", raw, 0x78)
stroff, = struct.unpack_from("<Q", raw, 0x80)
strs = raw[stroff:stroff+strsz]
def cstr(o):
    e = strs.index(b"\0", o); return strs[o:e].decode("utf-8","replace")
seen = {}
print(f"{'name':<18}{'path':<26}{'size':>10}  plain_magic")
for i in range(count):
    e = raw[tbl+i*0x50: tbl+(i+1)*0x50]
    name = e[0x10:0x28].split(b"\0")[0].decode()
    flags, csum = struct.unpack_from("<II", e, 0x28)
    size, asize, off = struct.unpack_from("<QQQ", e, 0x30)
    poff, = struct.unpack_from("<I", e, 0x48)
    path = cstr(poff)
    if off in seen:
        print(f"{name:<18}{path:<26}{size:>10}  (alias of {seen[off]})")
        continue
    seen[off] = name
    stored = raw[base+off: base+off+size]
    plain = deshift(stored)
    fn = f"{name}__{os.path.basename(path.replace(chr(92),'/'))}"
    open(os.path.join(OUT, fn), "wb").write(plain)
    print(f"{name:<18}{path:<26}{size:>10}  {plain[:4].hex()} {plain[:4]!r}")
print("done ->", OUT)

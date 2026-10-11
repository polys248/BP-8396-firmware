"""Build a slim ' PK ' pkg for on-device OTA: keep all section entries but stub
the payload of items that map to no real partition (default: 'root', the 128MB
zero placeholder). Every other item's stored bytes + csum are preserved exactly;
offsets/base are recomputed. Verifiable with pkg_list.py / pkg_csum2.py.

usage: pkg_slim.py <in.pkg> <out.pkg> [stub_item ...]   (default stub: root)
"""
import struct, sys
from array import array

def sum_le32(buf):
    pad = (-len(buf)) % 4
    if pad: buf = bytes(buf) + b"\x00" * pad
    a = array("I"); a.frombytes(buf)
    if sys.byteorder != "little": a.byteswap()
    return sum(a) & 0xFFFFFFFF

IN, OUT = sys.argv[1], sys.argv[2]
STUB = set(sys.argv[3:]) or {"root"}
raw = open(IN, "rb").read()
count, = struct.unpack_from("<I", raw, 0x64)
tbl, base = struct.unpack_from("<QQ", raw, 0x68)
strsz, = struct.unpack_from("<I", raw, 0x78)
stroff, = struct.unpack_from("<Q", raw, 0x80)

items = []
for i in range(count):
    e = bytearray(raw[tbl+i*0x50: tbl+(i+1)*0x50])
    name = e[0x10:0x28].split(b"\0")[0].decode()
    flags, csum = struct.unpack_from("<II", e, 0x28)
    size, asize, off = struct.unpack_from("<QQQ", e, 0x30)
    items.append(dict(entry=e, name=name, csum=csum, size=size, asize=asize, off=off))

# stub selected items (payload -> 16 zero bytes); zeros are transform-invariant
for it in items:
    if it["name"] in STUB:
        it["stub"] = True; it["size"] = 16; it["asize"] = 16
        it["blob"] = b"\x00" * 16; it["csum"] = sum_le32(it["blob"])
    else:
        it["stub"] = False
        it["blob"] = raw[base + it["off"]: base + it["off"] + it["asize"]]

# new base unchanged (count & strtab unchanged); emit blobs in ascending orig off,
# dedup aliases (same original off share a blob), repoint every entry.
assert base == tbl + count * 0x50
groups = {}
for it in items:
    groups.setdefault(it["off"], []).append(it)

data = bytearray(); run = 0
for oo in sorted(groups):
    members = groups[oo]
    rep = members[0]
    for it in members:
        it["new_off"] = run
    data += rep["blob"]
    run += len(rep["blob"])

out = bytearray(raw[:tbl])                      # header + strtab, unchanged
for it in items:
    e = it["entry"]
    struct.pack_into("<II", e, 0x28, struct.unpack_from("<I", e, 0x28)[0], it["csum"])
    struct.pack_into("<QQQ", e, 0x30, it["size"], it["asize"], it["new_off"])
    out += e
assert len(out) == base, (len(out), base)
out += data
open(OUT, "wb").write(out)
print(f"wrote {OUT}: {len(out):,} bytes (was {len(raw):,}); stubbed={sorted(STUB)}")

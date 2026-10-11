"""Repacker for the ' PK ' firmware container (LomboTech N7 / A3-8396).

Modes:
  verify  <pkg>                      round-trip: parse -> rebuild -> assert byte-identical
  replace <pkg> <item> <plainfile> <out>   swap one component with a new (plaintext) image

Format (little-endian):
  header 0x90 bytes: magic ' PK '@0x00, model@0x28, count(u32)@0x64,
    itemtbl_off(u64)@0x68, data_base(u64)@0x70, strtab_size(u32)@0x78, strtab_off(u64)@0x80
  item entry 0x50 bytes: ' IT '@0x00, name[0x18]@0x10, flags(u32)@0x28,
    csum(u32)@0x2C, size(u64)@0x30, asize(u64)@0x38, off(u64)@0x40, pathoff(u32)@0x48
  layout: header | strtab | itemtable | data(contiguous, each item asize bytes)
  obfuscation: each component stored with every 16-bit LE word rotated RIGHT by 1 bit
  csum: sum of 32-bit LE words over the stored(obfuscated) bytes, zero-padded to mult of 4
"""
import struct, sys
from array import array

ALIGN = 16

def enshift(data: bytes) -> bytes:        # plaintext -> stored (rotate each 16-bit word RIGHT 1)
    n = len(data) & ~1
    out = bytearray(data)
    for o in range(0, n, 2):
        w = data[o] | (data[o + 1] << 8)
        w = ((w >> 1) | (w << 15)) & 0xFFFF
        out[o] = w & 0xFF
        out[o + 1] = (w >> 8) & 0xFF
    return bytes(out)

def sum_le32(buf: bytes) -> int:
    pad = (-len(buf)) % 4
    if pad:
        buf = bytes(buf) + b"\x00" * pad
    a = array("I"); a.frombytes(buf)
    if sys.byteorder != "little":
        a.byteswap()
    return sum(a) & 0xFFFFFFFF

def parse(path):
    raw = open(path, "rb").read()
    count, = struct.unpack_from("<I", raw, 0x64)
    tbl, base = struct.unpack_from("<QQ", raw, 0x68)
    strsz, = struct.unpack_from("<I", raw, 0x78)
    stroff, = struct.unpack_from("<Q", raw, 0x80)
    items = []
    for i in range(count):
        e = raw[tbl + i*0x50: tbl + (i+1)*0x50]
        name = e[0x10:0x28].split(b"\0")[0].decode()
        flags, csum = struct.unpack_from("<II", e, 0x28)
        size, asize, off = struct.unpack_from("<QQQ", e, 0x30)
        pathoff, = struct.unpack_from("<I", e, 0x48)
        data = raw[base + off: base + off + size]
        adata = raw[base + off: base + off + asize]
        items.append(dict(entry=bytearray(e), name=name, flags=flags, csum=csum,
                          size=size, asize=asize, off=off, orig_off=off,
                          pathoff=pathoff, data=data, adata=adata))
    return dict(raw=raw, count=count, tbl=tbl, base=base, strsz=strsz,
                stroff=stroff, header=raw[:stroff], strtab=raw[stroff:stroff+strsz],
                items=items)

def build(pkg, recompute_pad_zero=False):
    """Reassemble the file from the model. recompute_pad_zero=True rebuilds padding
    as zeros and recomputes csum (what a real repack does); default preserves original
    padding bytes for an exact round-trip.

    Data is deduplicated: multiple item entries may alias one stored blob (same
    original off, e.g. dtb/dtbb). Blobs are emitted once, in ascending original-off
    (= storage) order, and every aliasing entry is repointed at the shared new off."""
    out = bytearray()
    out += pkg["header"]                       # 0x00 .. stroff
    assert len(out) == pkg["stroff"]
    out += pkg["strtab"]                        # strtab
    assert len(out) == pkg["tbl"], (len(out), pkg["tbl"])

    # group items into blobs by their original offset (aliases share a blob)
    blobs = {}
    for it in pkg["items"]:
        b = blobs.get(it["orig_off"])
        if b is None:
            b = blobs[it["orig_off"]] = dict(members=[])
        b["members"].append(it)

    data_region = bytearray()
    run = 0
    for oo in sorted(blobs):
        b = blobs[oo]
        rep = b["members"][0]                   # representative (aliases are identical)
        if recompute_pad_zero:
            asize = (rep["size"] + ALIGN - 1) & ~(ALIGN - 1)
            body = bytes(rep["data"]) + b"\x00" * (asize - rep["size"])
            csum = sum_le32(body)
        else:
            body = rep["adata"]                 # exact original bytes incl. padding
            asize = rep["asize"]
            csum = rep["csum"]
            assert len(body) == asize
        for it in b["members"]:                 # repoint every aliasing entry
            it["off"] = run
            it["asize"] = asize
            if recompute_pad_zero:
                it["csum"] = csum
        data_region += body
        run += asize

    # item table
    tbl_bytes = bytearray()
    for it in pkg["items"]:
        e = bytearray(it["entry"])              # preserve reserved bytes
        nm = it["name"].encode()[:0x17]
        e[0x10:0x28] = nm + b"\x00" * (0x18 - len(nm))
        struct.pack_into("<II", e, 0x28, it["flags"], it["csum"])
        struct.pack_into("<QQQ", e, 0x30, it["size"], it["asize"], it["off"])
        struct.pack_into("<I", e, 0x48, it["pathoff"])
        tbl_bytes += e
    out += tbl_bytes
    assert len(out) == pkg["base"], (len(out), pkg["base"])
    out += data_region
    # trailing bytes after last item (if any) preserved from original
    out += pkg["raw"][len(out):]
    return bytes(out)

def main():
    mode = sys.argv[1]
    pkg = parse(sys.argv[2])
    if mode == "verify":
        rebuilt = build(pkg, recompute_pad_zero=False)
        ident = rebuilt == pkg["raw"]
        print(f"round-trip (preserve padding): {'IDENTICAL' if ident else 'DIFFERS'} "
              f"({len(rebuilt)} vs {len(pkg['raw'])} bytes)")
        if not ident:
            for i in range(min(len(rebuilt), len(pkg["raw"]))):
                if rebuilt[i] != pkg["raw"][i]:
                    print(f"  first diff at 0x{i:x}: got {rebuilt[i]:#x} want {pkg['raw'][i]:#x}")
                    break
        # also prove the zero-pad + csum recompute path reproduces the file
        pkg2 = parse(sys.argv[2])
        rebuilt2 = build(pkg2, recompute_pad_zero=True)
        ident2 = rebuilt2 == pkg2["raw"]
        print(f"round-trip (recompute asize+csum, zero pad): "
              f"{'IDENTICAL' if ident2 else 'DIFFERS'}")
        if not ident2:
            for i in range(min(len(rebuilt2), len(pkg2["raw"]))):
                if rebuilt2[i] != pkg2["raw"][i]:
                    print(f"  first diff at 0x{i:x}: got {rebuilt2[i]:#x} want {pkg2['raw'][i]:#x}")
                    break
    elif mode == "replace":
        name, plain, out = sys.argv[3], sys.argv[4], sys.argv[5]
        newdata = enshift(open(plain, "rb").read())
        hit = False
        for it in pkg["items"]:
            if it["name"] == name:
                it["data"] = newdata
                it["size"] = len(newdata)
                it["adata"] = None
                hit = True
        if not hit:
            sys.exit(f"item {name!r} not found; names: {[i['name'] for i in pkg['items']]}")
        open(out, "wb").write(build(pkg, recompute_pad_zero=True))
        print(f"wrote {out}")
    else:
        sys.exit("usage: verify <pkg> | replace <pkg> <item> <plainfile> <out>")

if __name__ == "__main__":
    main()

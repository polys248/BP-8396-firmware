"""List / extract items from the vendor ' PK ' firmware container.

Layout (reverse-engineered from n7v9_p2 v9.23):
  0x00  ' PK ' magic
  0x28  model string
  0x64  u32 item count
  0x68  u64 item table offset
  0x70  u64 data base offset
  0x78  u32 string table size
  0x80  u64 string table offset
Item (0x50 bytes):
  0x00 ' IT '   0x10 name[0x18]   0x28 u32 flags   0x2C u32 checksum
  0x30 u64 size 0x38 u64 aligned size   0x40 u64 offset (rel. to base)
  0x48 u32 path offset (rel. to string table)
"""
import os, struct, sys, zlib

def read_cstr(b, off):
    end = b.index(b"\0", off)
    return b[off:end].decode("utf-8", "replace")

def parse(path):
    with open(path, "rb") as f:
        hdr = f.read(0x90)
        assert hdr[:4] == b" PK ", "bad magic"
        count, = struct.unpack_from("<I", hdr, 0x64)
        tbl, base = struct.unpack_from("<QQ", hdr, 0x68)
        strsz, = struct.unpack_from("<I", hdr, 0x78)
        stroff, = struct.unpack_from("<Q", hdr, 0x80)
        f.seek(stroff); strs = f.read(strsz)
        f.seek(tbl); raw = f.read(count * 0x50)
    items = []
    for i in range(count):
        e = raw[i * 0x50:(i + 1) * 0x50]
        assert e[:4] == b" IT ", f"bad item {i}"
        name = e[0x10:0x28].split(b"\0")[0].decode()
        flags, csum = struct.unpack_from("<II", e, 0x28)
        size, asize, off = struct.unpack_from("<QQQ", e, 0x30)
        poff, = struct.unpack_from("<I", e, 0x48)
        items.append(dict(name=name, flags=flags, csum=csum, size=size,
                          asize=asize, off=off, path=read_cstr(strs, poff)))
    return dict(model=read_cstr(hdr, 0x28), base=base, items=items)

def main():
    path = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else None
    p = parse(path)
    fsize = os.path.getsize(path)
    print(f"model={p['model']} base=0x{p['base']:X} items={len(p['items'])} filesize=0x{fsize:X}")
    with open(path, "rb") as f:
        for it in p["items"]:
            f.seek(p["base"] + it["off"])
            data = f.read(it["size"])
            crc = zlib.crc32(data) & 0xFFFFFFFF
            magic = data[:8]
            print(f"{it['name']:<22} {it['path']:<26} off=0x{p['base']+it['off']:08X} "
                  f"size={it['size']:>10} crc={'OK ' if crc == it['csum'] else 'BAD'} "
                  f"magic={magic.hex()} {magic[:4]!r}")
            if outdir:
                dest = os.path.join(outdir, os.path.basename(it["path"].replace("\\", "/")))
                os.makedirs(outdir, exist_ok=True)
                with open(dest, "wb") as o:
                    o.write(data)

if __name__ == "__main__":
    main()

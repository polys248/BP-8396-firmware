import struct, sys
from array import array

PKG = sys.argv[1]

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
            f.seek(base + off); data = f.read(size)
            f.seek(base + off); adata = f.read(asize)   # aligned region incl. padding
            items.append(dict(name=name, csum=csum, size=size, asize=asize,
                              data=data, adata=adata))
    return items

def sum_le32(buf):
    # zero-pad to a multiple of 4, then sum 32-bit LE words
    pad = (-len(buf)) % 4
    if pad:
        buf = bytes(buf) + b"\x00" * pad
    a = array("I")
    a.frombytes(buf)
    if sys.byteorder != "little":
        a.byteswap()
    return sum(a) & 0xFFFFFFFF

items = parse(PKG)
ok_size = ok_asize = 0
for it in items:
    cs_size = sum_le32(it["data"])
    cs_asize = sum_le32(it["adata"])
    tag = []
    if cs_size == it["csum"]: tag.append("SIZE"); ok_size += 1
    if cs_asize == it["csum"]: tag.append("ASIZE"); ok_asize += 1
    print(f"{it['name']:<20} size={it['size']:>9} asize={it['asize']:>9} "
          f"csum={it['csum']:#010x} size32={cs_size:#010x} asize32={cs_asize:#010x} "
          f"{'='+','.join(tag) if tag else 'MISS'}")
print(f"\nmatched: size-padded={ok_size}/{len(items)}  asize={ok_asize}/{len(items)}")

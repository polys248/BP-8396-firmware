import struct, sys, gzip, lzma, bz2, io

p = sys.argv[1]
raw = open(p, "rb").read()
magic, hcrc, t, size, load, ep, dcrc = struct.unpack_from(">IIIIIII", raw, 0)
os_, arch, typ, comp = raw[0x1c], raw[0x1d], raw[0x1e], raw[0x1f]
name = raw[0x20:0x40].split(b"\0")[0].decode("latin1")
print(f"uImage magic={magic:#x} size={size} load={load:#x} ep={ep:#x} "
      f"os={os_} arch={arch} type={typ} comp={comp} name={name!r} total={len(raw)}")
payload = raw[0x40:0x40+size]
print(f"payload[:8]={payload[:8].hex()}")

def tryd(name, fn):
    try:
        out = fn(payload)
        print(f"  {name}: OK -> {len(out)} bytes, head={out[:8].hex()} {out[:4]!r}")
        return out
    except Exception as e:
        print(f"  {name}: no ({type(e).__name__})")
        return None

out = None
if comp == 1 or payload[:2] == b"\x1f\x8b":
    out = tryd("gzip", lambda d: gzip.decompress(d))
if out is None and (comp == 3 or payload[:1] == b"\x5d"):
    out = tryd("lzma", lambda d: lzma.decompress(d, format=lzma.FORMAT_ALONE))
if out is None:
    out = tryd("xz", lambda d: lzma.decompress(d))
if out is None:
    out = tryd("bz2", lambda d: bz2.decompress(d))
if out is None:
    print("  (no decompressor matched; payload may be raw or multi-file)")
    out = payload

od = sys.argv[2] if len(sys.argv) > 2 else None
if od:
    open(od, "wb").write(out)
    print(f"wrote decompressed -> {od} ({len(out)} bytes)")
# quick fs detection
if out[:6] == b"070701" or out[:6] == b"070702":
    print("  -> cpio newc archive (initramfs)")
if out[:4] == b"hsqs":
    print("  -> squashfs")
if b"\x1f\x8b" in out[:4]:
    print("  -> gzip")

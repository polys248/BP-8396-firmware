import sys, re, gzip, lzma, io

raw = open(sys.argv[1], "rb").read()
print(f"total {len(raw)} bytes")

# locate embedded archives/filesystems
for magic, label in [(b"\x1f\x8b\x08", "gzip"), (b"070701", "cpio-newc"),
                     (b"070702", "cpio-crc"), (b"hsqs", "squashfs"),
                     (b"\xfd7zXZ", "xz"), (b"\x5d\x00\x00", "lzma"),
                     (b"\xd0\x0d\xfe\xed", "dtb")]:
    i = raw.find(magic)
    if i != -1:
        print(f"  {label:10} first @ 0x{i:x}")

# try to decompress a gzip blob if present (likely the initramfs)
gi = raw.find(b"\x1f\x8b\x08")
blob = None
if gi != -1:
    try:
        blob = gzip.decompress(raw[gi:])
        print(f"  gzip@0x{gi:x} -> {len(blob)} bytes, head={blob[:6]!r}")
    except Exception as e:
        # try decompressobj to get partial
        try:
            d = __import__("zlib").decompressobj(16+15)
            blob = d.decompress(raw[gi:])
            print(f"  gzip(partial)@0x{gi:x} -> {len(blob)} bytes")
        except Exception as e2:
            print(f"  gzip decompress failed: {e2}")

def strings(b, mn=4):
    return re.findall(rb"[ -~]{%d,}" % mn, b)

hay = blob if blob else raw
KEYS = [b"mtd", b"nandwrite", b"flash_erase", b"flash_eraseall", b"misc", b"UPT ",
        b"/dev/", b".pkg", b"upgrade", b"recovery", b"root_sq", b"kernel", b"dd ",
        b"ubi", b"nftl", b"/data", b"/tmp", b"busybox", b"PK ", b"install", b"update",
        b"format", b"partition", b"erase", b"write", b"/mnt", b".sh", b"systemfile"]
found = {}
for s in strings(hay):
    for k in KEYS:
        if k in s:
            found.setdefault(k.decode("latin1","replace").strip(), set()).add(s[:120].decode("latin1","replace"))
for k in sorted(found):
    vs = sorted(found[k])[:12]
    print(f"\n== {k} ({len(found[k])}) ==")
    for v in vs:
        print("   ", v)

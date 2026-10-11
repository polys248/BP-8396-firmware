import sys, os, gzip, struct

raw = open(sys.argv[1], "rb").read()
outdir = sys.argv[2]
gi = raw.find(b"\x1f\x8b\x08")
data = gzip.decompress(raw[gi:])
print(f"initramfs {len(data)} bytes")

os.makedirs(outdir, exist_ok=True)
pos = 0
n_files = 0
manifest = []
while pos + 110 <= len(data):
    if data[pos:pos+6] not in (b"070701", b"070702"):
        # align search to next header
        nxt = data.find(b"070701", pos+1)
        if nxt == -1:
            break
        pos = nxt
        continue
    fields = [int(data[pos+6+i*8: pos+6+(i+1)*8], 16) for i in range(13)]
    (ino, mode, uid, gid, nlink, mtime, fsize, maj, mino, rmaj, rmino, nsize, chk) = fields
    name = data[pos+110: pos+110+nsize-1].decode("latin1")
    hdr = 110 + nsize
    hdr = (hdr + 3) & ~3
    fstart = pos + hdr
    fdata = data[fstart: fstart+fsize]
    nextp = fstart + ((fsize + 3) & ~3)
    if name == "TRAILER!!!":
        break
    manifest.append((mode, fsize, name))
    is_dir = (mode & 0o170000) == 0o040000
    is_lnk = (mode & 0o170000) == 0o120000
    dst = os.path.join(outdir, name)
    if is_dir:
        os.makedirs(dst, exist_ok=True)
    elif is_lnk:
        manifest[-1] = (mode, fsize, name + " -> " + fdata.decode("latin1"))
    else:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        try:
            open(dst, "wb").write(fdata)
        except Exception as e:
            pass
    n_files += 1
    pos = nextp
print(f"entries: {n_files} -> {outdir}")
# print scripts + upgrade-relevant files
import fnmatch
for mode, fsize, name in manifest:
    if (fnmatch.fnmatch(name, "etc/init.d/*") or fnmatch.fnmatch(name, "*.sh")
        or "upgrade" in name or "ota" in name.lower() or name.startswith("init")
        or fnmatch.fnmatch(name, "etc/inittab") or fnmatch.fnmatch(name,"sbin/init")):
        print(f"  {oct(mode)[2:]:>7} {fsize:>8}  {name}")

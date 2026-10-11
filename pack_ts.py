import io, os, tarfile, time

SRC_BIN = r"C:\Users\Isaac\fw-tools\_dl_tailscale\tailscale_1.104.1_arm"
BUND = r"C:\Users\Isaac\fw-tools\ts-bundle"
OUT = os.path.join(BUND, "ts-data-bundle.tgz")

# (archive path, source file, mode, is_text)
FILES = [
    ("tailscale/tailscaled",   os.path.join(SRC_BIN, "tailscaled"), 0o755, False),
    ("tailscale/tailscale",    os.path.join(SRC_BIN, "tailscale"),  0o755, False),
    ("tailscale/run.sh",       os.path.join(BUND, "tailscale", "run.sh"), 0o755, True),
    ("tailscale/config",       os.path.join(BUND, "tailscale", "config"), 0o644, True),
    ("tailscale/S40tailscale", os.path.join(BUND, "S40tailscale"), 0o755, True),
    ("stress_test.sh",         os.path.join(BUND, "stress_test.sh"), 0o755, True),
]

now = int(time.time())
with tarfile.open(OUT, "w:gz") as tar:
    for arc, src, mode, is_text in FILES:
        data = open(src, "rb").read()
        if is_text:
            data = data.replace(b"\r\n", b"\n")   # ensure LF for the device
        ti = tarfile.TarInfo(arc)
        ti.size = len(data)
        ti.mode = mode
        ti.mtime = now
        ti.uid = ti.gid = 0
        ti.uname = ti.gname = "root"
        tar.addfile(ti, io.BytesIO(data))

size = os.path.getsize(OUT)
print(f"wrote {OUT}  ({size:,} bytes)")
print("contents:")
with tarfile.open(OUT) as tar:
    for m in tar.getmembers():
        print(f"  {oct(m.mode)[2:]:>4}  {m.size:>9}  {m.name}")

import io, os, tarfile, time

B = r"C:\Users\Isaac\fw-tools\ttproxy"
OUT = os.path.join(B, "ttproxy-bundle.tgz")
FILES = [
    ("ttproxy/ttproxy", os.path.join(B, "ttproxy"),      0o755, False),
    ("ttproxy/run.sh",  os.path.join(B, "run.sh"),       0o755, True),
    ("ttproxy/config",  os.path.join(B, "config"),       0o644, True),
    ("stress_test.sh",  os.path.join(B, "stress_test.sh"),0o755, True),
]
now = int(time.time())
with tarfile.open(OUT, "w:gz") as tar:
    for arc, src, mode, is_text in FILES:
        data = open(src, "rb").read()
        if is_text:
            data = data.replace(b"\r\n", b"\n")
        ti = tarfile.TarInfo(arc); ti.size = len(data); ti.mode = mode
        ti.mtime = now; ti.uid = ti.gid = 0; ti.uname = ti.gname = "root"
        tar.addfile(ti, io.BytesIO(data))
print(f"wrote {OUT} ({os.path.getsize(OUT):,} bytes)")
with tarfile.open(OUT) as tar:
    for m in tar.getmembers():
        print(f"  {oct(m.mode)[2:]:>4} {m.size:>8}  {m.name}")

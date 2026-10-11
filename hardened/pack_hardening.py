import io, os, tarfile, time, hashlib

B = r"C:\Users\Isaac\fw-tools\hardened"
TT = r"C:\Users\Isaac\fw-tools\ttproxy"
OUT = os.path.join(B, "hardening-bundle.tgz")

# (archive path, source file, mode, text?)
FILES = [
    ("stress_test.sh",        os.path.join(B, "stress_test.sh"),          0o755, True),
    ("ttproxy/ttproxy",       os.path.join(TT, "ttproxy"),                0o755, False),
    ("ttproxy/run.sh",        os.path.join(TT, "run.sh"),                 0o755, True),
    ("ttproxy/config",        os.path.join(TT, "config"),                 0o644, True),
    ("webflash/webflash",     os.path.join(B, "webflash", "webflash"),    0o755, False),
    ("webflash/config",       os.path.join(B, "webflash", "config"),      0o644, True),
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
sz = os.path.getsize(OUT)
md5 = hashlib.md5(open(OUT, "rb").read()).hexdigest()
print(f"wrote {OUT}")
print(f"  size {sz:,} bytes   md5 {md5}")
with tarfile.open(OUT) as tar:
    for m in tar.getmembers():
        print(f"  {oct(m.mode)[2:]:>4} {m.size:>9}  {m.name}")

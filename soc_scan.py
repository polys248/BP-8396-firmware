import os, re, sys

TOKENS = [b"rk3566", b"rk3568", b"rk3576", b"rk3588", b"rk3399", b"rk3288",
          b"rk3326", b"rk3328", b"rk3308", b"rk3128", b"rk1808", b"rk3036",
          b"rk3568b", b"rk356x", b"rk3562", b"px30", b"rv1109", b"rv1126",
          b"rv1103", b"rv1106", b"rockchip", b"maskrom", b"rknano",
          b"rk3506", b"rk3528", b"rk3582", b"rk3399pro"]

def scan(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except Exception as e:
        return
    low = data.lower()
    hits = {}
    for t in TOKENS:
        # ascii
        i = low.find(t)
        if i != -1:
            hits.setdefault(t.decode(), []).append(("ascii", i))
        # utf-16le
        tw = b"".join(bytes([c, 0]) for c in t)
        j = low.find(tw)
        if j != -1:
            hits.setdefault(t.decode(), []).append(("utf16", j))
    if hits:
        print(f"\n== {path}  ({len(data):,} bytes)")
        for k, v in sorted(hits.items()):
            enc, off = v[0]
            # pull a little context
            s = data[off: off + 48] if enc == "ascii" else data[off: off + 96]
            ctx = re.sub(rb"[^\x20-\x7e]", b".", s).decode()
            print(f"   {k:<10} {enc} @0x{off:X}  ctx={ctx!r} (x{len(v)})")

def walk(root):
    if os.path.isfile(root):
        scan(root); return
    for dp, _, fns in os.walk(root):
        for fn in fns:
            scan(os.path.join(dp, fn))

for arg in sys.argv[1:]:
    walk(arg)

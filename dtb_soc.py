import re, sys

dec = sys.argv[1]
for name in ["n7v9_p1.dtb", "kernel.img", "rootfs_squashfs.img", "booster.img", "leaver.img"]:
    try:
        data = open(dec + "\\" + name, "rb").read()
    except FileNotFoundError:
        continue
    print("===", name, len(data))
    runs = re.findall(rb"[\x20-\x7e]{4,}", data)
    seen = set()
    for tok in [b"rockchip", b"compatible", b"rk3", b"rk1", b"px30", b"rv11",
                b"linux version", b"model", b"board", b"-soc", b"cpu"]:
        for r in runs:
            if tok in r.lower():
                txt = r[:140].decode("latin1")
                if txt not in seen:
                    seen.add(txt)
                    print("   [%s] %s" % (tok.decode(), txt))
                break

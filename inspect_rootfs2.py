import sys
from PySquashfsImage import SquashFsImage
img = SquashFsImage.from_file(sys.argv[1])

def dump(path):
    for f in img:
        if f.path == path:
            if f.is_symlink: return f"<symlink -> {f.readlink()}>"
            try: return f.read_bytes().decode("latin1","replace")
            except Exception as e: return f"<err {e}>"
    return None

# boot hooks: show rcS, S60face-recg, and anything referencing /data or stress_test
for p in ("/etc/init.d/rcS", "/etc/init.d/S60face-recg", "/etc/init.d/S21monitor", "/etc/init.d/S30debuggerd"):
    c = dump(p)
    print(f"\n===== {p} =====")
    print(c if c is not None else "<not found>")

# network tooling present?
print("\n===== network tools =====")
for f in img:
    p = f.path
    base = p.rsplit("/",1)[-1]
    if base in ("iptables","ip","route","nft","ip6tables","hosts","resolv.conf","nftables"):
        tag = f" -> {f.readlink()}" if f.is_symlink else ""
        print(" ", p, tag)

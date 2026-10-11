import sys
from PySquashfsImage import SquashFsImage

img = SquashFsImage.from_file(sys.argv[1])

def read(path):
    for f in img:
        if f.path == path or f.path == "/" + path.lstrip("/"):
            if f.is_symlink:
                return f"<symlink -> {f.readlink()}>"
            return f.read_bytes().decode("latin1", "replace")
    return None

# list /etc/init.d
print("=== /etc/init.d ===")
for f in img:
    p = f.path
    if "/etc/init.d/" in p:
        tag = " (symlink -> %s)" % f.readlink() if f.is_symlink else ""
        print(" ", p, tag)

for path in ("/etc/passwd", "/etc/shadow", "/etc/inittab"):
    print(f"\n=== {path} ===")
    c = read(path)
    print(c if c is not None else "<not found>")

print("\n=== telnet/login/dropbear/getty refs ===")
for f in img:
    p = f.path.lower()
    if any(k in p for k in ("telnet", "dropbear", "getty", "login", "/bin/sh")):
        tag = " -> %s" % f.readlink() if f.is_symlink else ""
        print(" ", f.path, tag)

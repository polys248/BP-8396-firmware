import os, sys, stat
from PySquashfsImage import SquashFsImage

img_path, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)

nfile = ndir = nlink = 0
manifest = []

with SquashFsImage.from_file(img_path) as image:
    for node in image:
        path = node.path.lstrip("/")
        dest = os.path.join(out, path)
        if node.is_dir:
            os.makedirs(dest, exist_ok=True)
            ndir += 1
        elif node.is_symlink:
            target = node.readlink() if hasattr(node, "readlink") else getattr(node, "symlink", "")
            manifest.append(f"L {path} -> {target}")
            nlink += 1
            # record only; don't create Windows symlinks
            try:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest + ".symlink", "w", encoding="utf-8") as f:
                    f.write(str(target))
            except Exception:
                pass
        elif node.is_file:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(node.read_bytes())
            mode = getattr(node, "mode", 0)
            x = "x" if (mode & 0o111) else "-"
            manifest.append(f"F {path} ({node.size} bytes) {x}")
            nfile += 1
        else:
            manifest.append(f"? {path}")

with open(os.path.join(out, "_MANIFEST.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(manifest))
print(f"extracted: {nfile} files, {ndir} dirs, {nlink} symlinks -> {out}")

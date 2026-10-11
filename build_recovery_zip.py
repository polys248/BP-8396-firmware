import os, sys, json, zipfile, hashlib

EXTRACT = r"C:\Users\Isaac\fw-v923\extract"
OUT = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Isaac\fw-v923\recovery_os.zip"

# SAFE flash #1 set: OS partitions only. Exclude leaver_a/b (bootloader),
# recovery, misc  -> rescue path stays pristine.
# (partition_name_on_device, zip_image_name, source_file_in_extract)
ITEMS = [
    ("kernel",    "kernel.img",          "kernel__kernel.img"),
    ("dtb",       "n7v9_p1.dtb",         "dtb__n7v9_p1.dtb"),
    ("dtbb",      "n7v9_p1.dtb",         "dtb__n7v9_p1.dtb"),
    ("btfs_mini", "bootfs_mini.img",     "btfs_mini__bootfs_mini.img"),
    ("root_sq",   "rootfs_squashfs.img", "root_sq__rootfs_squashfs.img"),
    ("env",       "leaver_env.img",      "env__leaver_env.img"),
    ("pkg_ver",   "pkg_ver.cfg",         "pkg_ver__pkg_ver.cfg"),
]

# dedupe identical zip image names (dtb/dtbb share n7v9_p1.dtb)
manifest = {"list": [{"partition": p, "image": img} for p, img, _ in ITEMS]}
mj = json.dumps(manifest, indent=2)
print("upgrade.json:\n" + mj)

added = set()
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_STORED) as z:  # STORED: no compression; recovery just needs the bytes
    z.writestr("upgrade.json", mj)
    for p, img, src in ITEMS:
        if img in added:
            continue
        added.add(img)
        path = os.path.join(EXTRACT, src)
        sz = os.path.getsize(path)
        z.write(path, img)
        print(f"  + {img:22} <- {src}  ({sz:,} bytes)")

size = os.path.getsize(OUT)
md5 = hashlib.md5(open(OUT, "rb").read()).hexdigest()
print(f"\nwrote {OUT}")
print(f"  size : {size:,} bytes ({size/1024/1024:.1f} MB)")
print(f"  md5  : {md5}")
print(f"  final name on device:  <ro.product.name>-{md5}.zip")

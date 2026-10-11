import os, json, zipfile, hashlib
img = "/mnt/c/Users/Isaac/fw-v923/rootfs_t1d.img"
outdir = "/mnt/c/Users/Isaac/fw-v923"
tmp = outdir + "/_t1d_tmp.zip"
man = {"list": [{"partition": "root_sq", "image": "rootfs_squashfs.img"}]}
with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as z:
    z.writestr("upgrade.json", json.dumps(man, indent=2))
    z.write(img, "rootfs_squashfs.img")
d = open(tmp, "rb").read()
md5 = hashlib.md5(d).hexdigest()
final = outdir + "/n7v9_p1-%s.zip" % md5
os.replace(tmp, final)
print("recovery.zip:", os.path.basename(final))
print("size", len(d), "md5", md5)

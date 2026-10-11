#!/bin/bash
# ============================================================================
# A3-8396 PRODUCTION image builder  (run in YOUR WSL; the fleet secret never
# leaves your machine). Produces a zero-touch hardened rootfs recovery.zip:
#   - aio China-URL patched out
#   - ttproxy v2 + webflash + bpagent baked in, launched by S61hardening
#   - YOUR prod fleet token baked read-only at /etc/bpa/fleet_token
#   - claim ON (units self-claim a device token on first boot)
#   - OTA ON  (webflash polls fw-manifest hourly, bearer switches to device token)
#   - remote tunnel ON (bpagent ENABLED=1; units self-enroll on first boot.
#                       export BP_ENABLED=0 to ship it off / opt-in per device)
#
# USAGE (inside WSL, as root):
#   printf '%s' '<YOUR_PROD_FLEET_TOKEN>' > /root/prod_fleet_token   # no trailing newline needed
#   chmod 600 /root/prod_fleet_token
#   bash /mnt/c/Users/Isaac/fw-tools/build_prod_image.sh [fleet_token_file] [FW_VERSION]
#       fleet_token_file : default /root/prod_fleet_token
#       FW_VERSION       : default prod-$(date)  (written to /etc/fw_build, the webroot
#                          .uilabel, and a top-level .fwver in recovery.zip that the
#                          OTA form auto-reads; vendor upgrade.json is left untouched)
#   # when done:  shred -u /root/prod_fleet_token
# ============================================================================
set -euo pipefail

TOKFILE="${1:-/root/prod_fleet_token}"
FW_VERSION="${2:-prod-$(date -u +%Y%m%d%H%M)}"
OTA_INTERVAL="${OTA_INTERVAL:-3600}"       # export OTA_INTERVAL=0 to ship OTA off
BP_ENABLED="${BP_ENABLED:-1}"              # export BP_ENABLED=0 to ship the remote tunnel off

T=/mnt/c/Users/Isaac/fw-tools
STOCK=/mnt/c/Users/Isaac/fw-v923/extract/root_sq__rootfs_squashfs.img
OUTDIR=/mnt/c/Users/Isaac/fw-v923/prod
mkdir -p "$OUTDIR"

[ -s "$TOKFILE" ] || { echo "ERROR: fleet token file '$TOKFILE' missing/empty"; exit 1; }
for f in "$STOCK" "$T/ttproxy/ttproxy" "$T/hardened/webflash/webflash" "$T/bpagent/bpagent" \
         "$T/hardened/S61hardening" "$T/patch_aio.py"; do
  [ -e "$f" ] || { echo "ERROR: missing input $f"; exit 1; }
done

cd /root
rm -rf fwprod && mkdir fwprod && cd fwprod
unsquashfs -n -d mod "$STOCK" >/dev/null
echo "unpacked $(find mod | wc -l) entries"

echo "patching aio..."
python3 "$T/patch_aio.py" mod/usr/bin/aio

echo "baking services..."
cp "$T/ttproxy/ttproxy"            mod/usr/bin/ttproxy
cp "$T/hardened/webflash/webflash" mod/usr/bin/webflash
cp "$T/bpagent/bpagent"            mod/usr/bin/bpagent
chmod 755 mod/usr/bin/ttproxy mod/usr/bin/webflash mod/usr/bin/bpagent

echo "baking fleet token (read-only)..."
mkdir -p mod/etc/bpa
# strip any trailing newline/CR so the bearer is exact
tr -d '\r\n' < "$TOKFILE" > mod/etc/bpa/fleet_token
chmod 600 mod/etc/bpa/fleet_token
echo "  fleet_token bytes: $(stat -c%s mod/etc/bpa/fleet_token) (content NOT shown)"

echo "installing S61hardening (OTA_INTERVAL=$OTA_INTERVAL, ENABLED=$BP_ENABLED)..."
sed -e 's/\r$//' \
    -e "s/OTA_INTERVAL=0/OTA_INTERVAL=$OTA_INTERVAL/" \
    -e "s/'ENABLED=0/'ENABLED=$BP_ENABLED/" \
    "$T/hardened/S61hardening" > mod/etc/init.d/S61hardening
chmod 755 mod/etc/init.d/S61hardening
sh -n mod/etc/init.d/S61hardening
grep -q "printf 'ENABLED=$BP_ENABLED" mod/etc/init.d/S61hardening \
  && echo "  bpagent seed: ENABLED=$BP_ENABLED" || { echo "ERROR: ENABLED seed not set"; exit 1; }

echo "bundling web UI (rootfs -> /data via S61 deploy_webroot)..."
[ -d "$T/webroot-src" ] || { echo "ERROR: missing $T/webroot-src"; exit 1; }
rm -rf mod/usr/share/bettapay-webroot
mkdir -p mod/usr/share/bettapay-webroot
cp -a "$T/webroot-src/." mod/usr/share/bettapay-webroot/
UIHASH=$(bash "$T/ui_hash.sh" "$T/webroot-src")
echo "$UIHASH" > mod/usr/share/bettapay-webroot/.uiver          # content-hash = version
echo "$FW_VERSION" > mod/usr/share/bettapay-webroot/.uilabel
echo "  webroot files: $(find mod/usr/share/bettapay-webroot -type f | wc -l)  uiver(hash): $UIHASH  label: $FW_VERSION"

echo "A3-8396 PROD $FW_VERSION aio-patch+services+TOFU-claim+webUI $(date -u +%Y%m%dT%H%M%SZ)" > mod/etc/fw_build
cat mod/etc/fw_build

echo "repacking..."
mksquashfs mod rootfs_prod.img -comp xz -b 131072 -noappend -all-root -quiet
echo "  rootfs flags(want c000): $(xxd -s 0x18 -l2 -p rootfs_prod.img)"

# sanity (no secrets printed)
mkdir -p mnt
if mount -t squashfs -o loop rootfs_prod.img mnt 2>/dev/null; then
  echo "  aio China-URL occurrences (want 0): $(strings mnt/usr/bin/aio | grep -c 119.23.124.50 || true)"
  echo "  fleet slot bytes (want >0): $(stat -c%s mnt/etc/bpa/fleet_token)"
  for b in ttproxy webflash bpagent; do echo "  $b: $(test -x mnt/usr/bin/$b && echo ok || echo MISSING)"; done
  umount mnt
fi

# wrap as recovery.zip named by its md5 (STORED; recovery just needs the bytes)
python3 - "$PWD/rootfs_prod.img" "$OUTDIR" "$FW_VERSION" <<'PY'
import os,sys,json,zipfile,hashlib
img,outdir,ver=sys.argv[1],sys.argv[2],sys.argv[3]
tmp=os.path.join(outdir,"_prod_tmp.zip")
# Vendor manifest stays EXACTLY as the spec defines it (no version key inside).
man={"list":[{"partition":"root_sq","image":"rootfs_squashfs.img"}]}
with zipfile.ZipFile(tmp,"w",zipfile.ZIP_STORED) as z:
    z.writestr("upgrade.json",json.dumps(man,indent=2))
    # Top-level version marker, mirroring .uiver in the UI bundles. The OTA form reads
    # this; it is NOT in the vendor "list", so the device recovery never looks at it.
    z.writestr(".fwver",ver+"\n")
    z.write(img,"rootfs_squashfs.img")
d=open(tmp,"rb").read(); md5=hashlib.md5(d).hexdigest()
final=os.path.join(outdir,f"n7v9_p1-{md5}.zip"); os.replace(tmp,final)
print(f"\nPROD recovery.zip: {os.path.basename(final)}")
print(f"  size {len(d):,}  md5 {md5}")
print(f"  .fwver in package = '{ver}'  (OTA form reads it; md5 = release id)")
PY

echo
echo "DONE. Output in $OUTDIR"
echo "Reminder: shred -u $TOKFILE   (remove the plaintext fleet token)"

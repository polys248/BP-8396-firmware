#!/bin/bash
cd /root/fw1d
mkdir -p mnt
if mount -t squashfs -o loop rootfs_t1d.img mnt 2>/dev/null; then
  echo "bundled webroot present: $(test -d mnt/usr/share/bettapay-webroot && echo yes || echo NO)"
  echo ".uiver: $(cat mnt/usr/share/bettapay-webroot/.uiver 2>/dev/null)"
  echo "index.html: $(test -f mnt/usr/share/bettapay-webroot/index.html && echo yes || echo NO)  ($(stat -c%s mnt/usr/share/bettapay-webroot/index.html 2>/dev/null) bytes)"
  echo "file count: $(find mnt/usr/share/bettapay-webroot -type f | wc -l)"
  echo "runtime data/ excluded (should be absent): $(test -d mnt/usr/share/bettapay-webroot/data && echo PRESENT-BAD || echo absent-good)"
  echo "S61 deploy_webroot defined: $(grep -c 'deploy_webroot()' mnt/etc/init.d/S61hardening)  called: $(grep -c '^\s*deploy_webroot$' mnt/etc/init.d/S61hardening)"
  umount mnt
else echo "mount failed"; fi

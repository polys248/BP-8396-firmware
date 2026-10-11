#!/bin/bash
E=/mnt/c/Users/Isaac/fw-v923/extract
for img in root__rootfs.img btfs_mini__bootfs_mini.img recovery__recovery.img; do
  echo "================ $img ================"
  echo "file: $(file -b $E/$img 2>/dev/null)"
  echo "webpage/webroot/html hits (strings):"
  strings -n 5 "$E/$img" 2>/dev/null | grep -iE 'webpage|webroot|index\.html|\.js\b|vue|react|<!doctype|<html' | sort -u | head -20
done
echo
echo "=== try mounting root__rootfs.img read-only ==="
mkdir -p /mnt/rootimg
if mount -o loop,ro "$E/root__rootfs.img" /mnt/rootimg 2>/tmp/mnterr; then
  echo "MOUNTED. top-level:"; ls -la /mnt/rootimg | head
  echo "webpage dir:"; ls -laR /mnt/rootimg/data/webpage 2>/dev/null | head -40
  echo "find webroot:"; find /mnt/rootimg -ipath '*webpage/webroot*' -maxdepth 6 2>/dev/null | head
  find /mnt/rootimg -iname 'index.html' 2>/dev/null | head
  umount /mnt/rootimg
else
  echo "mount failed: $(cat /tmp/mnterr)"
fi

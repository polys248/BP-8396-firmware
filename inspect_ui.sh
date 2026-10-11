#!/bin/bash
cd /root
rm -rf uiinspect && mkdir uiinspect && cd uiinspect
unsquashfs -n -d mod /mnt/c/Users/Isaac/fw-v923/extract/root_sq__rootfs_squashfs.img >/dev/null 2>&1 && echo UNPACKED
echo "--- candidate webroots ---"
for d in www webroot htdocs web html app app/web usr/share/www usr/www var/www data/www opt/www; do
  [ -d "mod/$d" ] && echo "FOUND dir: mod/$d"
done
echo "--- counts ---"
echo "html=$(find mod -iname '*.html' | wc -l)  js=$(find mod -iname '*.js' | wc -l)  css=$(find mod -iname '*.css' | wc -l)  html.gz=$(find mod -iname '*.html.gz' | wc -l)"
echo "--- html files (top 40) ---"
find mod -iname '*.html*' 2>/dev/null | head -40
echo "--- large dirs that look like web assets ---"
find mod -type d \( -iname 'static' -o -iname 'assets' -o -iname 'js' -o -iname 'css' -o -iname 'dist' -o -iname 'www*' \) 2>/dev/null | head -20
echo "--- index.html locations ---"
find mod -iname 'index.htm*' 2>/dev/null

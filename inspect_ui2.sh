#!/bin/bash
cd /root/uiinspect
echo "=== mod/var/www ==="
ls -laR mod/var/www 2>/dev/null | head -40
echo "=== mod/app (top) ==="
ls -la mod/app 2>/dev/null | head -40
echo "=== webroot / mongoose hints in aio ==="
strings -n 6 mod/usr/bin/aio | grep -iE 'document_root|/var/www|/data/www|index\.html|\.html|webroot|htdocs|listening_ports|ssl_cert|mg_|mongoose|enable_directory' | sort -u | head -60
echo "=== websocket / live / stream hints in aio ==="
strings -n 6 mod/usr/bin/aio | grep -iE 'websocket|Sec-WebSocket|Upgrade|/ws|mjpeg|multipart/x-mixed|text/event-stream|chunked|keep-alive|Connection' | sort -u | head -40
echo "=== where does the UI live? search any *.html on whole fs incl data mounts baked ==="
find mod -iname '*.htm*' -o -iname '*.vue' -o -iname 'app.js' -o -iname 'main.js' 2>/dev/null | head
echo "=== /data references in aio (UI may be served from /data) ==="
strings -n 6 mod/usr/bin/aio | grep -iE '/data/[a-z]+' | sort -u | head -40

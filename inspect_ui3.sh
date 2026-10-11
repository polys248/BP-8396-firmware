#!/bin/bash
cd /root/uiinspect
A=mod/usr/bin/aio
echo "=== websocket endpoints / usage ==="
strings -n 4 $A | grep -iE 'ws://|wss://|/ws\b|ws\.html|websocket' | sort -u | head -30
echo "=== mjpeg / video / snapshot / stream endpoints ==="
strings -n 4 $A | grep -iE '\.mjpeg|mjpeg|snapshot|/video|/live|/stream|/preview|x-mixed-replace|\.cgi' | sort -u | head -30
echo "=== HTTP API endpoint paths (HTTPAPI_* and /api, /cgi) ==="
strings -n 6 $A | grep -oE '/[A-Za-z0-9_]+(/[A-Za-z0-9_]+){0,3}' | grep -iE 'api|cgi|ws|video|live|data|verify|upload|login|face|device' | sort -u | head -60
echo "=== CORS / Accept-Encoding / Host handling ==="
strings -n 4 $A | grep -iE 'Access-Control-Allow|Accept-Encoding|X-Forwarded|Host:|Origin|Referer' | sort -u | head -20
echo "=== polling hints (intervals / setInterval-like server msgs) ==="
strings -n 6 $A | grep -iE 'heartbeat|poll|interval|keepalive|ping' | sort -u | head -20
echo "=== does the webroot ship a manifest/version we can ask the user to pull? ==="
strings -n 6 $A | grep -iE 'webpage/webroot|index\.html|/ws\.html|\.appcache|manifest' | sort -u | head

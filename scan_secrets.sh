#!/bin/bash
cd /mnt/c/Users/Isaac/fw-tools
echo "=== subdir sizes ==="
du -sh bpagent chisel hardened ota_server ts-bundle ttproxy vendor webroot-dump webroot-src wordlists 2>/dev/null
echo
echo "=== vendor/ contents ==="; ls -la vendor 2>/dev/null | head -20
echo "=== chisel/ contents ==="; ls -la chisel 2>/dev/null | head -10
echo "=== ts-bundle/ contents ==="; ls -la ts-bundle 2>/dev/null | head -10
echo "=== ota_server/ contents ==="; ls -la ota_server 2>/dev/null | head -10
echo
echo "=== private keys / certs anywhere ==="
find . -name '*.key' -o -name 'id_rsa*' -o -name '*.pem' 2>/dev/null | grep -v node_modules | head -40
echo
echo "=== crack_result.txt (confirm it's a secret) ==="
wc -c crack_result.txt 2>/dev/null; head -c 200 crack_result.txt 2>/dev/null; echo
echo
echo "=== secret-ish strings in committable text (exclude dumps/vendor/webroot-dump) ==="
grep -rInE '(password|passwd|secret|token|BEGIN (RSA|EC|OPENSSH|PRIVATE)|api[_-]?key)' \
  --include='*.go' --include='*.py' --include='*.sh' --include='*.md' --include='*.txt' --include='*.json' \
  . 2>/dev/null | grep -viE 'webroot-dump|wordlists|httpv2.txt' | grep -viE 'OTA_TOKEN=|FLEET_TOKEN|<.*token.*>|token field|device_token|tunnel_token|upload_token|fleet_token|TOKEN=|uiver' | head -40

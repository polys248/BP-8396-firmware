#!/bin/bash
set -e
cd /mnt/c/Users/Isaac/fw-tools
git init -b main >/dev/null
git config user.email "polys248@gmail.com"
git config user.name "Isaac"
git add -A

# Safety gate: refuse to commit if anything sensitive/excluded got staged.
DANGER=$(git ls-files | grep -Ei '(\.key$|server\.pem$|clientcert|^vendor/|^webroot-dump/|^wordlists/|crack_result|httpv2|\.img$|\.zip$|\.tgz$|bpagent/bpagent$|ttproxy/ttproxy$|webflash/webflash$|chisel\.gz$|ts-data-bundle|fleet_token|prod_fleet_token|\.token$)' || true)
if [ -n "$DANGER" ]; then
  echo "ABORT — sensitive/excluded files are staged:"; echo "$DANGER"; exit 1
fi

echo "staged files: $(git ls-files | wc -l)"
echo "--- cacert.pem kept? (should list 3) ---"; git ls-files | grep -c cacert.pem
echo "--- top-level staged entries ---"; git ls-files | awk -F/ '{print $1}' | sort | uniq -c | sort -rn
echo "--- any private keys staged? (should be empty) ---"; git ls-files | grep -Ei '\.key$|server\.pem' || echo "  none"

git commit -q -m "Initial commit: A3-8396 firmware hardening, remote-access, and web-UI tooling"
echo "committed $(git rev-parse --short HEAD) on $(git branch --show-current)"
echo "working tree: $(git status --porcelain | wc -l) uncommitted changes"

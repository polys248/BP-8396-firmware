# A3-8396 firmware tooling

Hardening, remote-access, and web-UI delivery tooling for the A3-8396 face-recognition
door/payment terminal (LomboTech N7 / ARMv7 Cortex-A7, kernel 4.19.73, Mongoose 6.18).

This repo holds **our own tooling and sources only**. Vendor firmware images, the extracted
vendor `/data` tree, device TLS keys, and compiled build outputs are intentionally **not**
committed (see `.gitignore`). Build inputs (the vendor `data.zip`, stock partition images)
live outside the repo.

## Components

| Path | What it is |
|------|------------|
| `ttproxy/` | HTTP→HTTPS reverse proxy (Go) — fixes the device's Mongoose client-TLS bug so `aio` can reach the HTTPS backend. |
| `hardened/webflash/` | Firmware + web-UI update daemon (Go): browser upload at `:8090` and OTA pull. Flashes firmware via the recovery path; deploys web-UI packages live. |
| `bpagent/` | Remote-access agent (Go): TOFU per-device claim/enroll, outbound WebSocket tunnel to the hub, TLS-terminating port forward. |
| `hardened/S61hardening` | Boot init script: phone-home blackhole, loopback bring-up, service launch, provisioning, and web-UI deploy. Factory-reset-proof (ships in rootfs). |
| `webroot-src/` | Web-UI source tree (deployed to `/data/webpage/webroot`). Single source for both the rootfs bundle and the webflash UI package. |
| `patch_aio.py` | Binary patch removing the hardcoded phone-home URL from `aio`. |
| `build_prod_image.sh` | Production rootfs image builder (run in your own WSL; bakes the fleet token, which never leaves your machine). |
| `build_rootfs_tier1d.sh` | Test/dev rootfs image builder (dormant provisioning). |
| `build_webroot_pkg.sh` | Builds a web-UI package (`.tgz`) for webflash upload / OTA. |
| `ui_hash.sh` | Content-hash of `webroot-src` used as the UI version (`.uiver`), so firmware bundle and UI package stay in sync. |
| `PROVISIONING.md` | **Carton-to-fielded-unit provisioning runbook** (PkgBurnPro flash → zero-touch first boot → server-side reader registration → verify). |
| Docs | `PROVISIONING.md`, `FIRMWARE_CLAIM_CONTRACT.md`, `SERVER_SPEC*.md`, `OTA_BUILD_TEST.md`, `DEPLOY.txt` (legacy `/data` bundle). |

## Build (in WSL)

```bash
# service binaries are built with the Go toolchain (GOOS=linux GOARCH=arm GOARM=7)
# then baked into the rootfs by the build scripts:
bash build_rootfs_tier1d.sh                 # test image -> recovery.zip
bash build_prod_image.sh <token-file> <ver> # production image (bakes fleet token)
bash build_webroot_pkg.sh <label>           # web-UI package (.tgz)
```

Firmware is delivered via the device's recovery flash path (a `recovery.zip` written through
`webflash` upload or OTA). The web UI can additionally be hot-deployed as a package without a
reboot. See the docs for the wire contracts and OTA manifest format.

## Security

- No secrets are committed. Device TLS private keys, cracked-password artifacts, wordlists,
  captured traffic, and fleet/prod tokens are excluded via `.gitignore`.
- The fleet token is supplied out-of-band at build time and never stored in-tree.
- This is defensive tooling for the owner's own device fleet.

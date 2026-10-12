# Biometric terminal — ODM sourcing brief (BettaPay)

**Purpose.** We buy an integrated face + fingerprint access/payment terminal and run **our own
firmware** on it. We own the application and cloud layer; we need the ODM to supply the biometric
hardware + engine and a **Linux base we can root, reflash, and run fully offline**. Please answer
every item in §2 and §3 — those decide whether we can qualify your unit, not just its price.

---

## 1. Required SKU (must-have)
- **Face recognition**, on-device, **with liveness / anti-spoofing** (dual visible + IR camera).
- **Fingerprint** (capacitive or optical) with local matching.
- **Wi-Fi** (2.4 GHz min, dual-band preferred) **and Ethernet** (state if PoE).
- Baseline: display, speaker/mic, **door relay (dry contact)**, 12 V or PoE power, indoor mount.

**Options to quote separately (not required):** QR scanner, RFID/NFC card reader, Wiegand/RS485,
outdoor/IP-rated enclosure, touch screen, battery/UPS.

**Not needed (drop to cut cost):** palm-vein, vendor cloud/app/WeChat integration, the ODM's
management platform.

---

## 2. Firmware / OS requirements — THE DEALBREAKERS
We flash and maintain our own rootfs. A unit that fails any of these we cannot use at any price.
Please answer each explicitly:

1. **OS + kernel version** (e.g. Linux 4.x/5.x), libc (glibc/musl), and **CPU arch/ABI**
   (e.g. ARMv7 `arm`, ARM64 `aarch64`) so we can cross-compile.
2. **Root access** on shipped units — serial console pinout + how to get a root shell
   (documented telnet/ssh/console login). Required for eval.
3. **Rootfs reflash path** — at least one of: a factory **USB flasher** (tool + **documented
   package format**), and/or **in-device partition reflash** (MTD/eMMC/UBI). Describe the
   **partition layout** (bootloader / kernel / dtb / rootfs / recovery / userdata).
4. **Secure boot / signature verification** — is a **modified rootfs** allowed to boot? If signing
   is enforced, is there a documented way to enroll our own key? (We need to run a custom rootfs.)
5. **Recovery partition / brick recovery** — is there a recovery image and a mask-ROM/USB recovery
   so a bad flash is recoverable?
6. **Writable persistent partition** (`/data`-style) that **survives a rootfs reflash** (holds our
   config + enrolled templates).
7. **Offline operation** — face match, fingerprint match, and door-open must work with **no
   internet and no vendor cloud**. Confirm.
8. **Golden firmware** — will you provide the **stock firmware package** (full image) as our
   restore baseline?

---

## 3. Biometric engine & data — cost, licensing, integration
1. **Face SDK** — which engine (ArcSoft / Megvii / Tencent / own / other), and **per-device
   license cost** — is it **included** in the unit price or billed separately/recurring?
2. **Fingerprint** — sensor model + matching SDK; same licensing question.
3. **Local API** — how does an on-device app call enroll / match / liveness **without the vendor
   cloud**? (IPC / C SDK / local HTTP.) We need this documented to integrate our firmware.
4. **Liveness method** — 2D-IR vs structured-light vs ToF, and the anti-spoof claim. We run
   payments, so state the real spoof resistance (printed photo / screen / mask).
5. **Template storage** — where templates live on-device, **format**, and whether they can be
   **exported/imported** (we manage the roster server-side and sync enrollments across units).
6. **Camera spec** — visible + IR module, resolution, FOV, min illumination.

---

## 4. Hardware baseline (fill in)
SoC + NPU (TOPS) · RAM · flash (type/size) · display (size/res/touch) · camera (per §3.6) ·
Ethernet (speed, PoE?) · Wi-Fi (bands) · BLE? · door relay + other I/O · power input ·
enclosure (material, IP rating, mount) · certifications (CE/FCC/RoHS; any payment-relevant).

---

## 5. Commercial
- **Unit price at MOQ tiers:** 100 / 500 / 1,000 / 5,000.
- **NRE**, if any (we do our own UI/branding; mainly SKU/feature variants).
- **Lead time, warranty, and SoC/SKU longevity** (how long will you supply this exact unit).
- **Eval samples:** price + lead time for **2–3 units delivered with root access, the flashing
  tool, the partition-layout doc, the biometric local-API doc, and the golden firmware** (§2–§3).

---

## 6. For context — what we do once we have a qualifying unit (so you know the ask is small)
Our firmware is a thin, portable layer: a few static ARM Go binaries + a web UI + our backend
integration. Per unit we only: cross-compile for your ABI, adapt the boot/init hooks, reflash the
rootfs, and call your biometric local API. We do **not** need you to build software — we need
**root, a documented reflash path, no blocking secure boot, and a documented offline biometric
API.** Those four are what we compare across quotes.

# ODM outreach — copy/paste

Send to the supplier's **ODM / OEM** team (not the retail desk). Attach `ODM_RFQ_brief.pdf`
and `ODM_response_form.csv`. Keep it short — the brief carries the detail.

---

**Subject:** RFQ — face + fingerprint access terminal (we run our own firmware)

Hello,

We're sourcing an **integrated face + fingerprint access terminal** for a volume rollout. We are
a **white-label / ODM buyer that runs its own firmware** on the device — we own the application and
cloud layer, so we are not looking for your management platform or cloud, just the hardware,
biometric engine, and a Linux base we can flash and run offline.

Must-haves: **face (with liveness) + fingerprint + Wi-Fi + Ethernet**, display, door relay.

Because we flash our own rootfs, four answers decide whether we can use your unit at all — please
confirm these up front:

1. **Root access** on shipped units (serial console + documented login).
2. A **documented rootfs reflash path** (USB flasher and/or in-device MTD/eMMC) + partition layout.
3. **No blocking secure boot** — a modified rootfs is allowed to boot (or our key can be enrolled).
4. A **documented offline biometric API** (enroll / match / liveness) that works with no cloud.

Full requirements and a response form are attached. Please return the completed
`ODM_response_form.csv` with:
- unit price at MOQ **100 / 500 / 1,000 / 5,000**,
- the answers to the firmware/OS and biometric-engine questions, and
- price + lead time for **2–3 evaluation samples** delivered with root access, the flashing tool,
  the partition-layout doc, the biometric API doc, and the stock (golden) firmware.

If this isn't something your ODM team supports, no problem — just let us know and we'll move on.

Thank you,
[Your name] · [Company] · [Phone / WeChat / WhatsApp]

---

### Where to send it
- **Alibaba.com / Made-in-China.com / Global Sources** — post an RFQ in the "face recognition
  access control terminal" category, and DM 5–6 suppliers directly with the message above.
- **Your current terminal's vendor** — ask them to quote a stripped face+fingerprint SKU (a real
  benchmark; they already meet most of the firmware asks).
- **A Shenzhen sourcing agent** — fastest for pinning down the four gate answers and vetting
  factories; worth it at volume.

### Tips
- Contact ~6–8 to get ~3 serious, complete responses. Vague or evasive answers on the four gates
  are themselves a disqualifier — don't chase them.
- Don't send the scoring sheet; it's internal.

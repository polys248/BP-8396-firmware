# Single-unit replay + MD5-capture kit

Validates, with **one** A3-8396, the parts of the enrollment-sync design that don't
need a second device, and captures the device's canonical MD5s so the server can
match them exactly. Drives the device's own web API, which hits the same ingestion
path `AddPeople` uses (`People::FromJson → PeopleOperate::Save → face_feat`).

## Scope

| Goal | This kit | Needs more |
|---|---|---|
| Template exports and re-imports intact | ✅ `replay` | |
| A replayed `FaceFeature` produces a working recognition | ✅ `replay` + stand in front of unit | |
| Device-canonical `PhotoMD5` / `FaceFeatureMD5` (exact form/case) | ✅ `vectors` | |
| Cross-hardware portability (enroll on A, recognize on B) | ❌ | 2nd unit |
| Incremental **MD5-skip** behavior | ❌ (lives in the `AddPeople` docking path, not the `People/New` web upsert) | live backend push |

## Prereqs
- One A3-8396 on the same LAN, its IP, and the admin password.
- Python 3 (stdlib only — no pip). On Windows without Python, run under WSL.
- A person already enrolled on the unit **with a face** (enroll one from the unit's
  screen if needed).

## 1. Capture golden MD5 vectors (hand these to the server)
```bash
python3 replay_test.py --base-url https://<device-ip> --password <admin> list
python3 replay_test.py --base-url https://<device-ip> --password <admin> vectors <UserID>
```
`vectors` prints the device-stored `PhotoMD5` and `FaceFeatureMD5` (with their exact
case), and recomputes `MD5(decoded FaceFeature bytes)` locally so you can see which
form the device stores. **Those device-stored strings are the authoritative golden
vectors** — give them to the server to match. Cross-check the algorithm itself with:
```bash
python3 md5_vectors.py selftest
python3 md5_vectors.py file ./some-avatar.jpg     # PhotoMD5 of an image you'd push
```

## 2. Replay round-trip + recognition proof
```bash
python3 replay_test.py --base-url https://<device-ip> --password <admin> replay <UserID>
```
Exports the person, re-imports the **same** `FaceFeature` under a fresh UserID, and
confirms the stored template matches. Then **stand in front of the unit** and confirm
it recognizes the new UserID as the same face. That closes the "a replayed template
recognizes" question on identical hardware; A→B across different sensors waits for a
second unit.

## MD5 case — what we actually know
- **PhotoMD5:** the stock web UI computes `MD5(decoded image bytes)` as **lowercase**
  hex (`page/people/edit.html:1138`). Match that for server-originated photos. (Our
  earlier "uppercase for both" note to the server was imprecise — see correction in
  `../SERVER_SPEC_ENROLLMENT.md`.)
- **FaceFeatureMD5:** the device `ToUpper`s the incoming value before comparing, so
  the sender's case is don't-care; the device's own stored form is uppercase.
- Either way, `vectors` above reports the device's exact stored strings — treat those
  as ground truth over any inference.

## Notes
- `--base-url` takes the scheme explicitly. The hardened build redirects :80→HTTPS and
  serves a self-signed cert on :443, so use `https://` and the default `--insecure`
  (skips cert verify). Plain `http://` works only if the unit still serves it on LAN.
- Nothing here writes to `/data` directly or needs a device shell — it's all the web
  API with the admin JWT.

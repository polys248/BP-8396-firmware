# Face-template portability test (2 devices)

**Question this answers:** does a face template enrolled on one A3-8396 recognise the
same person on a *different* A3-8396? If yes → we sync templates (fast path). If no →
we sync photos and each device re-extracts (fallback). The whole enrollment-sync feature
works either way; this just picks the path.

**Prereqs:** two units, both same firmware and `FaceVerson` (check the dashboard: Facial
Engine should read the same, e.g. `6.01`). Call them **A** (enroll) and **B** (target).
Have a cooperative test subject (or a printed/phone frontal photo works for a first pass).

---

## Method 1 — via the device web UI (no tools)

The vendor UI can already *view* and *input* a feature code, so you can move a template
by hand.

1. **Enroll on A.** People → add a person, `Code = TEST001`, `Name = Portability Test`.
   Enroll the **face** normally (camera capture). Save.
2. **Read the template on A.** Open TEST001 → the Face feature → view the **feature code**
   (the long base64 string). Copy it in full.
3. **Create on B.** On device **B**, People → add a person, `Code = TEST001`, same name.
   Add a **Face** feature and choose *input feature code* → **paste** the code from A. Save.
   (Do **not** capture a new face on B — we want A's template.)
4. **Test recognition on B.** Present the subject (or the same photo) to **B**.
   - **Recognised as TEST001 → templates ARE portable.** Use the template-sync path.
   - **Not recognised / unknown → not portable.** Use the photo-sync fallback (Method 3).

Clean up: delete TEST001 from both when done.

---

## Method 2 — via the local API (precise / scriptable)

Do this from a machine on the same LAN/VPN as the devices (e.g. cornercomp). First get a
login token from each device (the UI login returns it, or):

```bash
# A_IP / B_IP = device addresses; PASS = admin PIN
# login -> JWT (password is salted+MD5 by the UI; easiest is to grab the Bearer token
#          from your browser devtools after logging in: Network -> any /api call ->
#          Request Headers -> Authorization: Bearer <JWT>)
A_JWT=...   # from device A
B_JWT=...   # from device B
```

Export the enrolled person from A (after enrolling TEST001 via the UI):
```bash
# find the UserID
curl -sk -X POST "https://$A_IP/api/People/Search" -H "Authorization: Bearer $A_JWT" \
  -H "Content-Type: application/json" -d '{"PageIndex":1,"PageSize":50}'
# full record incl. FaceFeature
curl -sk -X POST "https://$A_IP/api/People/GetDetail" -H "Authorization: Bearer $A_JWT" \
  -H "Content-Type: application/json" -d '{"UserID":<UserID_from_search>}' > personA.json
```

Create the same person on B with A's face template (jq extracts FaceFeature):
```bash
FACE=$(jq -r '.content.FaceFeature' personA.json)
curl -sk -X POST "https://$B_IP/api/People/New" -H "Authorization: Bearer $B_JWT" \
  -H "Content-Type: application/json" -d "{
    \"Code\":\"TEST001\",\"Name\":\"Portability Test\",\"CardNum\":\"0\",
    \"AccessType\":0,\"Timegroup\":0,\"OpenTimes\":65535,\"UseOpenTimes\":0,
    \"ExpirationDate\":4102415940,\"KeepOpen\":0,\"Elevators\":\"\",\"Holidays\":\"\",
    \"FaceFeature\":\"$FACE\",\"Fingerprints\":[],\"Palmveins\":[]
  }"
```
Then present the subject to **B** and watch for a TEST001 identification (dashboard
"Identifications Today" will tick, or check Records → Identify).

> Note: field defaults above mirror the web UI (`edit.html`). If `People/New` rejects a
> field, paste `personA.json` here and I'll match the payload exactly.

---

## Method 3 — photo-fallback validation (only if Method 1/2 fails)

Confirms the fallback works when templates aren't portable:

1. On A, export the person's **photo** (People → the person → the stored image, or the API
   returns `Photo`/`PhotoMD5`).
2. On B, create the person **without** a face feature, attach the photo, then trigger
   `POST /api/People/EnrollUserMediaData {"UserID":<id>,"type":"Face"}` (the device extracts
   its **own** template from the photo).
3. Present the subject to B → should now recognise. If yes, photo-sync is our path.

---

## What to report back

- Method 1/2 result: **recognised?** yes / no (and the confidence/behaviour on B).
- If you hit an API error, the `personA.json` and the `People/New` response.
- Facial Engine version on both units.

That single result decides template-sync vs photo-sync, and then the backend schema +
the `bpenroll` agent in `ENROLLMENT_SYNC_SPEC.md` can be built against it.

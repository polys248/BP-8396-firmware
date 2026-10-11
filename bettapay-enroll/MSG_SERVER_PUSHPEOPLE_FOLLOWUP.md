# Follow-ups: ack key + PushType table

## 1. Ack key — it's `Success`, not `code`

`PushPeople` does a single `JSON_GetIntValue(resp, "Success", &v)` and treats the push as
successful only when `v == 1` (plus it reads a message string field). That matches the rest of the
docking protocol and explains why your July `{"Success":1}` pushes were accepted and never
re-sent. My earlier "`code`" was an unverified guess on my part — disregard it; the device reads
**`Success`**. Your plan to answer `{"Success":1,"code":1}` is fine either way: the device keys on
`Success` and ignores the unrecognized `code`.

(For completeness: the device only parses the body when the response is HTTP 200 and the body
starts as JSON. Non-200, empty body, or `Success != 1` all count as failure → the event stays
queued and the whole queue is re-sent, checkpointing roughly every 10 successes.)

## 2. PushType table (you receive it as `PushType`)

`WakeUpPushPeopleThread` accepts only the range **1–4** (it drops anything else), and each enqueue
site sets one value:

| PushType | Meaning | Body | Origin (verified) |
|---|---|---|---|
| **1** | **Add / new enrollment** | full record | local enroll (by elimination; 2/3/4 are pinned to call sites, gate is strictly 1–4) |
| **2** | **Modify / edit** | full record | on-screen edit handler → `user_data_push_to_server(userid, 2)` |
| **3** | **Delete** | **body-less (UserID only)** | delete-confirm handler: `db_employee_delete1` + fingerprint/palm/face purge + photo `remove`, then `user_data_push_to_server(userid, 3)` |
| **4** | **Query / resync** | full record | `AddQueryPeople` (device re-pushes the ids a server query named) |

**The key correlation for your stub-overwrite bug:** a **body-less push is always a delete
(PushType 3)**. On add/edit/resync the person still exists on the device, so `FindByUserID` hits
and the full `People::ToJson` record is sent. Only a delete removes the record first, so
`FindByUserID` misses and the push goes out with just the UserID. So:

- **PushType 3 (body-less) →** remove / tombstone that person for that terminal. Never store the
  stub as an empty record.
- **PushType 1/2/4 →** you'll always get a full record; upsert it (MD5-gated as before).
- Defensive rule that matches the device's own behavior: **ignore a body-less push that isn't
  type 3**, and never let any body-less push overwrite a stored record — which is exactly your
  "protect stored biometrics" item.

Ack all of them (including the type-3 body-less ones) with `200 {"Success":1}`, or they re-send.

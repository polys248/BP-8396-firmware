# Re: production rollout — delete no-op, PhotoMD5 case, bpagent concurrency

Rollout looks complete and correct. Three things back to you.

## DeletePeople for an absent UserID — confirmed harmless no-op
Verified in the device delete path (`DownloadDeletePeopleResponseProcessCore`): for each id
it calls `select_user_is_exist(userid)`; if the user isn't present it **skips the DB delete
entirely**, still counts the id as processed, adds it to the result list, and returns a normal
(non-error) `DeletePeopleResult`. No error, no crash, no side effect. So fanning `DeletePeople`
out to readers whose presence you're unsure of is safe.

## PhotoMD5 case — your uppercase is correct; scratch my "lowercase" note
I need to walk back the lowercase correction I sent. The device compares the photo MD5 with
**`strcasecmp`** (`check_file_md5`) — **case-insensitive** — and that same function is the
photo re-download skip. `FaceFeatureMD5` is `ToUpper`'d before compare, also effectively
case-insensitive. So **either case works for both; uppercase as you implemented is fine, no
change needed.** And yes, `check_file_md5` confirms your "send PhotoMD5 so photos aren't
re-downloaded" works exactly as intended — on a cache hit the device skips the download.

## bpagent concurrency — was unbounded; now bounded + queueing + logged
**Before (the build you've been testing against):** no limit. Every tunnel session got its own
goroutine immediately — it neither queued nor refused, so a burst (the web UI opens many asset
connections at once) spun up unbounded concurrent loopback dials + TLS handshakes on a 73 MB
unit. That is a plausible contributor to the stalls.

**New build:** sessions are capped (default **24**, tunable via cfg `MAX_SESSIONS`). Beyond the
cap they **queue** on a semaphore (cheap parked goroutines) rather than being refused — so the
UI's parallel requests still complete, just serialized under load; nothing is dropped. Only the
expensive live phase (loopback + TLS + relay) is what's bounded.

For the stall hunt, every session now logs:
`waitMs` (time queued for a slot), `inflight` (concurrent sessions at start), `dialMs` (loopback
connect), `hsMs` (TLS handshake), `respBytes`, `totalMs`. So when you send a stall's timestamp +
request path, we can tell apart:
- **queueing pressure** — high `waitMs`/`inflight` ⇒ too many concurrent sessions; drop
  `MAX_SESSIONS` (no rebuild — it's a config value).
- **slow device leg** — high `dialMs`/`hsMs` ⇒ the device web server itself is slow/overloaded.
- **slow relay** — `totalMs` high with the others low ⇒ the body transfer.

So the two earlier questions are now answered *and* fixed: limit = 24 (configurable), behaviour
beyond it = **queue, not refuse**. Send a stall timestamp + path whenever you have one and we'll
correlate against these lines.

## Portability test — still shelved (one unit)
We only have one terminal right now, so the cross-reader test (enroll on A, recognize on B)
waits for a second unit. Not blocking, since you carry both template and photo. In the meantime
we validated on the single unit that a template exports and re-imports intact and that a replayed
`FaceFeature` recognizes on the same hardware — so the replay mechanic and the ingestion path are
sound; only cross-sensor portability is unverified.

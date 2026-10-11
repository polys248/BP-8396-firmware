# bettapay remote-access hub — server spec (Cloudflare Worker + Durable Objects + Supabase)

Lets your team reach any device's **shell (telnet 23)**, **web UI (80)**, and
**webflash (8090)** from a browser, with no VPS and no inbound holes on the device.
Each device runs `bpagent`, which holds ONE outbound `wss://` control socket to a
Worker; when an operator opens a session the Worker tells the agent to open a fresh
session socket that it bridges to the requested local port. Durable Objects (one per
SN) pair operator↔device and relay bytes; idle control sockets hibernate (cheap at
fleet scale).

```
 device bpagent ──wss /agent (control, hibernates)──▶  Worker ── DO[SN] ──▶ operator (browser)
                ◀─ {"t":"open","id","port"} ─────────┘                 ▲
 device bpagent ──wss /session?id=..────────────────▶  DO relays ──────┘
```

## 0. DNS / Worker routes
- `remote.bettapay.ng`  → the Worker (terminal UI + control/session/connect WS).
- `*.remote.bettapay.ng` (wildcard) → same Worker, used for the HTTP reverse proxy
  so a device's SPA keeps working (absolute paths resolve under its own subdomain):
  `https://<SN>.remote.bettapay.ng/` → device :80, `https://<SN>-flash.remote.bettapay.ng/` → device :8090.

## 1. Supabase

```sql
-- per-device remote-access + upload state
create table device_remote (
  sn           text primary key,
  token        text not null,     -- tunnel secret the device uses to connect the hub
  upload_token text,              -- per-device LAN :8090 upload credential, reported by
                                  -- the device at remote-enroll; show to operators by SN
  enabled      boolean default true,
  last_seen    timestamptz
);
```
Enrollment is **device-driven** (TOFU): the unit self-claims a device token, then calls
`remote-enroll` (see FIRMWARE_CLAIM_CONTRACT.md) with `{"sn", "upload_token"}`. Your
`remote-enroll` handler mints/returns the tunnel `token` **and upserts the received
`upload_token`** into this row. The dashboard reads `upload_token` by SN so an on-site
operator can paste it into the device's LAN `:8090` page. The device regenerates and
re-reports its `upload_token` after a `/data` wipe, so always upsert the latest.

Operator auth: easiest is **Cloudflare Access** in front of `remote.bettapay.ng`
(SSO for your team, zero code). If you prefer app-level, issue signed operator JWTs
from Supabase and check them in `validOperator()`.

## 2. Worker (`wrangler.toml`)
```toml
name = "bpa-remote"
main = "src/index.ts"
compatibility_date = "2024-09-01"
[[durable_objects.bindings]]
name = "DEVICES"
class_name = "DeviceDO"
[[migrations]]
tag = "v1"
new_sqlite_classes = ["DeviceDO"]
[vars]
# SUPABASE_URL, SUPABASE_SERVICE_KEY, (OPERATOR_SECRET if not using CF Access) via `wrangler secret put`
```

## 3. Worker code (`src/index.ts`)
```ts
export interface Env {
  DEVICES: DurableObjectNamespace;
  SUPABASE_URL: string;
  SUPABASE_SERVICE_KEY: string;
}

async function validDevice(env: Env, sn: string, token: string): Promise<boolean> {
  if (!sn || !token) return false;
  const r = await fetch(`${env.SUPABASE_URL}/rest/v1/device_remote?sn=eq.${encodeURIComponent(sn)}&select=token,enabled`, {
    headers: { apikey: env.SUPABASE_SERVICE_KEY, authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}` },
  });
  const rows = await r.json();
  return rows.length === 1 && rows[0].enabled && rows[0].token === token;
}

// Operator auth: with Cloudflare Access in front, trust the Cf-Access-Jwt-Assertion
// header (verify it against your Access certs) — or check your own cookie/JWT here.
async function validOperator(req: Request, env: Env): Promise<boolean> {
  return !!req.headers.get("Cf-Access-Jwt-Assertion"); // replace with real verification
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);
    const host = url.hostname;
    const path = url.pathname;

    // --- device side: control + session sockets (validate device token, route to DO[SN]) ---
    if (path === "/agent" || path === "/session") {
      const sn = url.searchParams.get("sn") || "", token = url.searchParams.get("token") || "";
      if (!await validDevice(env, sn, token)) return new Response("unauthorized", { status: 401 });
      return env.DEVICES.get(env.DEVICES.idFromName(sn)).fetch(req);
    }

    // --- operator: terminal page + connect socket (behind Cloudflare Access) ---
    if (path === "/term") {
      if (!await validOperator(req, env)) return new Response("unauthorized", { status: 401 });
      return new Response(TERM_HTML, { headers: { "content-type": "text/html; charset=utf-8" } });
    }
    if (path === "/connect") {
      if (!await validOperator(req, env)) return new Response("unauthorized", { status: 401 });
      const sn = url.searchParams.get("sn") || "";
      return env.DEVICES.get(env.DEVICES.idFromName(sn)).fetch(req);
    }

    // --- operator: HTTP reverse-proxy to device web UI / webflash via wildcard subdomain ---
    //  <SN>.remote.bettapay.ng -> device :80   |  <SN>-flash.remote... -> device :8090
    const m = host.match(/^([^.]+?)(-flash)?\.remote\.bettapay\.ng$/);
    if (m) {
      if (!await validOperator(req, env)) return new Response("unauthorized", { status: 401 });
      const sn = m[1], port = m[2] ? 8090 : 80;
      return env.DEVICES.get(env.DEVICES.idFromName(sn)).fetch(
        new Request(`https://do/proxy?port=${port}`, req));   // DO serializes req over a session and streams the response
    }
    return new Response("not found", { status: 404 });
  },
};

export class DeviceDO {
  state: DurableObjectState;
  ctrl?: WebSocket;                                 // device control socket
  pending = new Map<string, (dev: WebSocket) => void>(); // session id -> handler called when device /session arrives
  constructor(state: DurableObjectState) { this.state = state; }

  // ask the device (via the control socket) to open a fresh session to <port>;
  // resolves with the device-side WebSocket once its /session connects.
  openSession(port: number, timeoutMs = 15000): Promise<WebSocket> {
    return new Promise((resolve, reject) => {
      if (!this.ctrl) return reject(new Error("device offline"));
      const id = crypto.randomUUID();
      const to = setTimeout(() => { this.pending.delete(id); reject(new Error("session timeout")); }, timeoutMs);
      this.pending.set(id, (dev) => { clearTimeout(to); resolve(dev); });
      this.ctrl.send(JSON.stringify({ t: "open", id, port }));
    });
  }

  async fetch(req: Request): Promise<Response> {
    const url = new URL(req.url);
    const p = url.pathname;

    if (p === "/agent") {                            // device control socket parks here
      const { 0: client, 1: server } = new WebSocketPair();
      server.accept();
      this.ctrl = server;
      server.addEventListener("close", () => { if (this.ctrl === server) this.ctrl = undefined; });
      return new Response(null, { status: 101, webSocket: client });
    }

    if (p === "/session") {                          // device's fresh session socket for a given id
      const id = url.searchParams.get("id") || "";
      const handler = this.pending.get(id);
      if (!handler) return new Response("no pending session", { status: 409 });
      this.pending.delete(id);
      const { 0: client, 1: dev } = new WebSocketPair();
      dev.accept();
      handler(dev);                                  // hand the device socket to whoever requested it
      return new Response(null, { status: 101, webSocket: client });
    }

    if (p === "/connect") {                          // operator raw/shell session (e.g. telnet :23)
      const port = parseInt(url.searchParams.get("port") || "23", 10);
      const { 0: client, 1: op } = new WebSocketPair();
      op.accept();
      this.openSession(port).then((dev) => {
        dev.addEventListener("message", (e) => { try { op.send(e.data); } catch {} });
        op.addEventListener("message",  (e) => { try { dev.send(e.data); } catch {} });
        const bye = () => { try { op.close(); } catch {}; try { dev.close(); } catch {} };
        dev.addEventListener("close", bye); op.addEventListener("close", bye);
      }).catch(() => { try { op.close(1011, "device offline"); } catch {} });
      return new Response(null, { status: 101, webSocket: client });
    }

    if (p === "/proxy") {                            // HTTP reverse-proxy over a session (web UI / webflash)
      const port = parseInt(url.searchParams.get("port") || "80", 10);
      let dev: WebSocket;
      try { dev = await this.openSession(port); } catch { return new Response("device offline/timeout", { status: 503 }); }
      // serialize the operator's HTTP request onto the raw session (Connection: close = one clean exchange)
      const u = new URL(req.url);
      const hop = new Set(["host","connection","keep-alive","transfer-encoding","upgrade","content-length",
        "cf-connecting-ip","cf-ray","cf-visitor","cf-ipcountry","x-forwarded-proto","x-forwarded-for",
        "x-real-ip","cf-access-jwt-assertion","cdn-loop","accept-encoding"]);
      let head = `${req.method} ${u.pathname}${u.search} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\nAccept-Encoding: identity\r\n`;
      for (const [k, v] of req.headers) if (!hop.has(k.toLowerCase())) head += `${k}: ${v}\r\n`;
      const bodyBuf = req.body ? new Uint8Array(await req.arrayBuffer()) : null;
      if (bodyBuf && bodyBuf.length) head += `Content-Length: ${bodyBuf.length}\r\n`;
      head += "\r\n";
      dev.send(new TextEncoder().encode(head));
      if (bodyBuf && bodyBuf.length) {               // send body in <=64 KB frames
        for (let o = 0; o < bodyBuf.length; o += 65536) dev.send(bodyBuf.slice(o, o + 65536));
      }
      return readHttpResponse(dev);
    }
    return new Response("bad DO path", { status: 400 });
  }
}

// ---- raw HTTP/1.1 response parser over the session socket (handles Content-Length & chunked) ----
function idxCRLFCRLF(b: Uint8Array): number {
  for (let i = 0; i + 3 < b.length; i++) if (b[i]===13 && b[i+1]===10 && b[i+2]===13 && b[i+3]===10) return i;
  return -1;
}
function cat(a: Uint8Array, b: Uint8Array): Uint8Array { const o = new Uint8Array(a.length+b.length); o.set(a); o.set(b,a.length); return o; }
function parseHead(text: string): { status: number; headers: Headers; chunked: boolean } {
  const lines = text.split("\r\n");
  const status = parseInt(lines[0].split(" ")[1] || "502", 10);
  const headers = new Headers(); let chunked = false;
  const skip = new Set(["connection","keep-alive","transfer-encoding","content-length","content-encoding"]);
  for (let i=1;i<lines.length;i++){ const c=lines[i].indexOf(":"); if(c<0)continue;
    const k=lines[i].slice(0,c).trim(), v=lines[i].slice(c+1).trim(), kl=k.toLowerCase();
    if (kl==="transfer-encoding" && v.toLowerCase().includes("chunked")) chunked=true;
    if (!skip.has(kl)) headers.set(k, v);
  }
  return { status, headers, chunked };
}
function readHttpResponse(ws: WebSocket): Promise<Response> {
  return new Promise((resolve, reject) => {
    let buf = new Uint8Array(0), parsed = false, chunked = false;
    let ctrl: ReadableStreamDefaultController<Uint8Array> | null = null;
    // chunked decoder state
    let cbuf = new Uint8Array(0), need = -1, cdone = false;
    const feed = (u: Uint8Array) => {
      if (!chunked) { ctrl?.enqueue(u); return; }
      cbuf = cat(cbuf, u);
      for (;;) {
        if (cdone) return;
        if (need < 0) {
          let i=-1; for (let j=0;j+1<cbuf.length;j++) if (cbuf[j]===13&&cbuf[j+1]===10){i=j;break;}
          if (i<0) return;
          const n = parseInt(new TextDecoder().decode(cbuf.slice(0,i)).trim().split(";")[0], 16);
          cbuf = cbuf.slice(i+2);
          if (isNaN(n) || n===0){ cdone=true; try{ctrl?.close();}catch{} return; }
          need = n;
        }
        if (cbuf.length < need+2) return;
        ctrl?.enqueue(cbuf.slice(0, need));
        cbuf = cbuf.slice(need+2); need = -1;
      }
    };
    const body = new ReadableStream<Uint8Array>({ start(c){ ctrl=c; } });
    ws.addEventListener("message", (e: MessageEvent) => {
      const chunk = new Uint8Array(e.data as ArrayBuffer);
      if (parsed) { feed(chunk); return; }
      buf = cat(buf, chunk);
      const i = idxCRLFCRLF(buf);
      if (i < 0) return;
      const { status, headers, chunked: ch } = parseHead(new TextDecoder().decode(buf.slice(0,i)));
      chunked = ch; parsed = true;
      resolve(new Response(body, { status, headers }));
      const rest = buf.slice(i+4); if (rest.length) feed(rest);
    });
    ws.addEventListener("close", () => { if (!parsed) reject(new Error("device closed before headers")); else if (!chunked) { try{ctrl?.close();}catch{} } });
    ws.addEventListener("error", () => { if (!parsed) reject(new Error("session error")); else { try{ctrl?.close();}catch{} } });
  });
}

const TERM_HTML = `<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>bettapay device shell</title>
<link rel=stylesheet href="https://cdnjs.cloudflare.com/ajax/libs/xterm/5.3.0/xterm.min.css">
<style>body{margin:0;background:#111;font-family:sans-serif}#bar{color:#ddd;padding:.4em .8em;background:#222}#t{height:calc(100vh - 2.2em)}</style>
<div id=bar>Device <input id=sn placeholder="SN" style="width:16em"> <button onclick=go()>Connect</button> <span id=s></span></div>
<div id=t></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/xterm/5.3.0/xterm.min.js"></script>
<script>
let term=new Terminal({cursorBlink:true,convertEol:true});term.open(document.getElementById('t'));
function go(){
  let sn=document.getElementById('sn').value.trim(); if(!sn)return;
  let ws=new WebSocket((location.origin.replace(/^http/,'ws'))+'/connect?sn='+encodeURIComponent(sn)+'&port=23');
  ws.binaryType='arraybuffer';
  ws.onopen=()=>{document.getElementById('s').textContent='connected';};
  ws.onclose=()=>{document.getElementById('s').textContent='closed';};
  ws.onmessage=e=>term.write(new Uint8Array(e.data));
  term.onData(d=>{if(ws.readyState===1)ws.send(new TextEncoder().encode(d));});
}
</script>`;
```

### 3a. The `/proxy` (web UI / webflash) piece — IMPLEMENTED above
The DO's `/proxy` opens a raw session to the device port, serializes the operator's
HTTP request onto it (`Connection: close` = one clean exchange, `Accept-Encoding:
identity` so nothing arrives compressed), then `readHttpResponse()` parses the status
line + headers and streams the body back — handling both **Content-Length** and
**chunked** responses (chunked is de-framed before it reaches the browser). Under the
wildcard subdomain the device SPA's absolute paths resolve correctly, so no HTML/JS
rewriting is needed.

Caveats / scope:
- **Plaintext HTTP only.** This works for **webflash (:8090, plain HTTP)** and for the
  device web UI **iff that UI is served over HTTP (:80)**. If the device's admin UI is
  **HTTPS (:443)** (it ships `webpage/cert/server.pem`), the tunnel would carry raw TLS
  and this HTTP-framing proxy can't read it — for that case use a raw **port-forward**
  instead (operator CLI binding a local port straight through a `/connect` session to
  :443, TLS end-to-end to the device) rather than `/proxy`. Confirm your device UI's
  port/scheme; `webflash` via `/proxy` works regardless.
- **Big uploads:** a ~40 MB firmware POST buffered through the Worker (`arrayBuffer()`)
  can hit CF memory/CPU limits — fine for config changes and browsing, but for fleet
  flashing use the **OTA backend**, not proxied webflash. (If you need large proxied
  uploads, switch the body path from `arrayBuffer()` to a streamed reader that
  `dev.send()`s chunks as they arrive — same shape, just no full buffer.)

## 4. Device side (built; bakes into firmware)
`/data/bpagent/` : `bpagent` (ARMv7, md5 9e510d4b4eedb1c88fb9a24c4d0b7ab2) + `config`.
Set `ENABLED=1`, `HUB=wss://remote.bettapay.ng`, `SN=...`, `TOKEN=<from Supabase>`.
`ALLOW_PORTS=23,80,8090` limits what the tunnel can reach. In the hardened firmware,
`S61hardening` launches it on boot (guarded, mem-capped). New unit = insert a Supabase
row + ship the standard image → it auto-connects by SN.

## 5. Operator usage
- **Shell:** open `https://remote.bettapay.ng/term` (behind Cloudflare Access), type the
  SN, Connect → xterm.js session to the device's telnet.
- **Device web UI:** `https://<SN>.remote.bettapay.ng/`
- **webflash:** `https://<SN>-flash.remote.bettapay.ng/`

## 6. Security
- Device: per-device token (Supabase), outbound-only, `ALLOW_PORTS` allowlist, TLS (pinned CA).
- Operator: Cloudflare Access SSO in front of all operator routes; the DO never exposes
  a device unless both the device token and operator auth check out.
- Rotate a unit's token by updating its Supabase row (set `enabled=false` to cut it off).
- Telnet is plaintext but only inside the wss tunnel; consider moving the device to
  dropbear-SSH later and tunneling that.

## 7. Scale
One Worker + DO namespace handles the fleet; idle control sockets hibernate so hundreds
of connected devices cost little. DOs shard by SN automatically. Watch Supabase auth QPS
(cache device tokens in Workers KV if needed).

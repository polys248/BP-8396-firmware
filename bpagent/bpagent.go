// bpagent - bettapay remote-access agent + TOFU provisioning for the A3-8396.
//
//   bpagent claim   - if /data/device_token is empty, claim a per-device token
//                     from device-claim using the FLEET token, persist atomically.
//   bpagent         - (serve) wait for device_token, remote-enroll for a tunnel
//                     token (+hub+allow_ports from the response), connect the hub,
//                     bridge sessions to allow-listed local ports.
//
// Tokens:  fleet  (/data/fleet_token override else /etc/bpa/fleet_token, read-only, baked)
//          device (/data/device_token, written by claim; PERMANENT; survives reboot+OTA)
//          tunnel (/data/bpagent/tunnel_token, from remote-enroll; rotates each enroll)
// SN:      cfg SN if set, else sysinfo.DeviceSN via sqlite3 (must match the heartbeat SN).
//
// Rate limit: device-claim and remote-enroll allow 5 calls/serial/hour (404 counts),
// so retries on 404/429/hub-401 use a >=15 min floor. The device token is permanent:
// NEVER cleared by the firmware (only an admin deleting the server row ends it).
package main

import (
	"bufio"
	"bytes"
	"context"
	"crypto/tls"
	"crypto/x509"
	_ "embed"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"runtime/debug"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/coder/websocket"
)

//go:embed cacert.pem
var caPEM []byte

const (
	deviceTokenPath = "/data/device_token"
	tunnelTokenPath = "/data/bpagent/tunnel_token"
	claimFaultPath  = "/data/bpagent/claim_fault"
	statusPath      = "/data/bpagent/status"
	fleetDataPath   = "/data/fleet_token"
	fleetBakedPath  = "/etc/bpa/fleet_token"
	// last server-provided port sets, persisted so they survive reboot and remain
	// authoritative over the baked cfg seed (which is only a pre-first-enroll bootstrap).
	allowPortsPath = "/data/bpagent/allow_ports"
	tlsPortsPath   = "/data/bpagent/tls_ports"

	rateFloor = 15 * time.Minute // >= per-serial rate-limit window spacing
)

var cfg = map[string]string{
	"ENABLED": "0", "HUB": "wss://remote.bettapay.ng", "SN": "",
	"ALLOW_PORTS": "23,443,8090", "MEM_MIB": "14",
	// ports the agent reaches over TLS (device UI is HTTPS-only; :80 just 301s to
	// :443 and ignores X-Forwarded-Proto). The agent terminates TLS to 127.0.0.1:<p>
	// and relays plaintext over the tunnel, so the hub speaks plain HTTP to :443.
	"TLS_PORTS": "443",
	"API_BASE":   "https://api.bettapay.ng/functions/v1", // TEST: https://qxczocglpejdcbzvziej.supabase.co/functions/v1
	"CLAIM_PATH": "/device-claim", "ENROLL_PATH": "/remote-enroll",
	"CLAIM_TOKEN_FIELD": "device_token", "ENROLL_TOKEN_FIELD": "token",
}

// ports allowed for tunneling; seeded from cfg, replaced by the enroll response's allow_ports.
var allowPorts = map[int]bool{}

// ports the agent reaches over TLS (e.g. the device's HTTPS-only UI on 443); seeded
// from cfg TLS_PORTS, optionally overridden by the enroll response's tls_ports.
var tlsPorts = map[int]bool{}

func loadConfig(path string) {
	f, err := os.Open(path)
	if err == nil {
		defer f.Close()
		s := bufio.NewScanner(f)
		for s.Scan() {
			ln := strings.TrimSpace(s.Text())
			if ln == "" || strings.HasPrefix(ln, "#") {
				continue
			}
			if k, v, ok := strings.Cut(ln, "="); ok {
				cfg[strings.TrimSpace(k)] = strings.TrimSpace(v)
			}
		}
	}
	setAllowPorts(cfg["ALLOW_PORTS"])
	tlsPorts = csvPortSet(cfg["TLS_PORTS"])
}
func csvPortSet(csv string) map[int]bool {
	m := map[int]bool{}
	for _, p := range strings.Split(csv, ",") {
		if n, e := strconv.Atoi(strings.TrimSpace(p)); e == nil {
			m[n] = true
		}
	}
	return m
}
func setAllowPorts(csv string) {
	if m := csvPortSet(csv); len(m) > 0 {
		allowPorts = m
	}
}

// loadPersistedPorts applies the last server-provided port sets (from the most
// recent successful enroll) over the baked cfg defaults, so a rebooted unit keeps
// the server's allowlist even before its boot-time re-enroll completes, and never
// silently reverts to the baked seed.
func loadPersistedPorts() {
	if m := csvPortSet(readTrim(allowPortsPath)); len(m) > 0 {
		allowPorts = m
	}
	if m := csvPortSet(readTrim(tlsPortsPath)); len(m) > 0 {
		tlsPorts = m
	}
}

// applyPorts sets the in-memory set AND persists the CSV, so the server's values
// are authoritative and survive reboot. Called from enroll on every 200.
func applyPorts(ps []int, dst *map[int]bool, path string) {
	m := map[int]bool{}
	var xs []string
	for _, p := range ps {
		m[p] = true
		xs = append(xs, strconv.Itoa(p))
	}
	*dst = m
	atomicWrite(path, strings.Join(xs, ","))
}

func logln(a ...interface{}) {
	fmt.Fprintf(os.Stdout, "[%s] ", time.Now().Format("2006-01-02 15:04:05"))
	fmt.Fprintln(os.Stdout, a...)
}
func setStatus(s string) {
	logln("status:", s)
	atomicWrite(statusPath, time.Now().UTC().Format(time.RFC3339)+" "+s+"\n")
}
func readTrim(p string) string { b, _ := os.ReadFile(p); return strings.TrimSpace(string(b)) }
func deviceToken() string      { return readTrim(deviceTokenPath) }
func fleetToken() string {
	for _, p := range []string{fleetDataPath, fleetBakedPath} {
		if s := readTrim(p); s != "" {
			return s
		}
	}
	return ""
}
func getSN() string {
	if cfg["SN"] != "" {
		return cfg["SN"]
	}
	out, err := exec.Command("sqlite3", "/data/user.db",
		"select value from sysinfo where key='DeviceSN'").Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(out))
}
// webflashUploadToken returns webflash's per-device LAN-upload token (generated
// zero-touch by webflash at boot), so we can report it to the backend at enroll
// for the operator dashboard to surface by SN. Read fresh each enroll so a
// regenerated token (e.g. after a /data wipe) propagates. Empty if not present.
func webflashUploadToken() string {
	if b, err := os.ReadFile("/data/webflash/upload_token"); err == nil {
		return strings.TrimSpace(string(b))
	}
	return ""
}
func atomicWrite(path, data string) error {
	tmp := path + ".tmp"
	f, err := os.OpenFile(tmp, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0600)
	if err != nil {
		return err
	}
	if _, err = f.WriteString(data); err != nil {
		f.Close()
		return err
	}
	f.Sync()
	f.Close()
	return os.Rename(tmp, path)
}
func httpClient() *http.Client {
	pool := x509.NewCertPool()
	pool.AppendCertsFromPEM(caPEM)
	return &http.Client{Timeout: 30 * time.Second, Transport: &http.Transport{
		TLSClientConfig: &tls.Config{RootCAs: pool, MinVersion: tls.VersionTLS12},
	}}
}

// only Authorization: Bearer + Content-Type (no extra headers).
func postJSON(cl *http.Client, u, bearer string, body map[string]string) (int, []byte, error) {
	b, _ := json.Marshal(body)
	req, _ := http.NewRequest("POST", u, bytes.NewReader(b))
	req.Header.Set("Content-Type", "application/json")
	if bearer != "" {
		req.Header.Set("Authorization", "Bearer "+bearer)
	}
	resp, err := cl.Do(req)
	if err != nil {
		return 0, nil, err
	}
	defer resp.Body.Close()
	rb, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<16))
	return resp.StatusCode, rb, nil
}
func jsonStr(b []byte, field string) string {
	var m map[string]interface{}
	if json.Unmarshal(b, &m) != nil {
		return ""
	}
	if v, ok := m[field].(string); ok {
		return v
	}
	return ""
}
func jsonPorts(b []byte, field string) []int {
	var m map[string]interface{}
	if json.Unmarshal(b, &m) != nil {
		return nil
	}
	arr, ok := m[field].([]interface{})
	if !ok {
		return nil
	}
	var out []int
	for _, x := range arr {
		if f, ok := x.(float64); ok {
			out = append(out, int(f))
		}
	}
	return out
}

// ---------------- claim ----------------
func runClaim() {
	if deviceToken() != "" {
		logln("claim: device_token already present")
		return
	}
	if readTrim(claimFaultPath) != "" {
		setStatus("claim fault present — not retrying (needs server-side identity reset)")
		return
	}
	sn, fleet := getSN(), fleetToken()
	if sn == "" || fleet == "" {
		logln("claim: missing SN or fleet token — dormant")
		return
	}
	os.MkdirAll("/data/bpagent", 0755)
	cl := httpClient()
	u := strings.TrimRight(cfg["API_BASE"], "/") + cfg["CLAIM_PATH"]
	// let aio's heartbeat register the row first, so the first claim rarely 404s
	time.Sleep(60 * time.Second)
	for {
		st, body, err := postJSON(cl, u, fleet, map[string]string{"sn": sn})
		switch {
		case err != nil:
			logln("claim: network error:", err)
			time.Sleep(2 * time.Minute)
		case st == 200:
			tok := jsonStr(body, cfg["CLAIM_TOKEN_FIELD"])
			if tok == "" {
				setStatus("claim 200 but no " + cfg["CLAIM_TOKEN_FIELD"] + " field")
				time.Sleep(rateFloor)
				continue
			}
			if err := atomicWrite(deviceTokenPath, tok); err != nil {
				logln("claim: persist failed:", err)
				time.Sleep(30 * time.Second)
				continue
			}
			if os.Remove(fleetDataPath) == nil {
				logln("claim: removed writable fleet override")
			}
			setStatus("claimed — device identity established")
			return
		case st == 404:
			logln("claim: 404 (reader not registered yet) — retry in", rateFloor)
			time.Sleep(rateFloor)
		case st == 429:
			logln("claim: 429 rate-limited — retry in", rateFloor)
			time.Sleep(rateFloor)
		case st == 401:
			setStatus("claim 401 — FLEET TOKEN REJECTED (cannot self-heal; fix provisioning)")
			return
		case st == 409:
			setStatus("claim 409 — serial already claimed; STOP (admin must reset this serial)")
			atomicWrite(claimFaultPath, "409 already-claimed "+time.Now().UTC().Format(time.RFC3339)+"\n")
			return
		case st == 400:
			setStatus("claim 400 — missing/invalid sn; STOP")
			return
		default:
			logln("claim: status", st, string(body))
			time.Sleep(rateFloor)
		}
	}
}

// ---------------- serve (enroll + tunnel) ----------------
func runServe() {
	if cfg["ENABLED"] != "1" {
		logln("bpagent disabled")
		return
	}
	sn := getSN()
	if sn == "" {
		logln("serve: no SN")
		return
	}
	if mib, _ := strconv.Atoi(cfg["MEM_MIB"]); mib > 0 {
		debug.SetMemoryLimit(int64(mib) * 1024 * 1024)
	}
	debug.SetGCPercent(20)
	cl := httpClient()

	for deviceToken() == "" {
		if readTrim(claimFaultPath) != "" {
			setStatus("serve: claim fault — cannot enroll")
			return
		}
		logln("serve: waiting for device_token (claim pending)...")
		time.Sleep(60 * time.Second)
	}

	// Apply the last server-provided allowlist over the baked seed, then re-enroll on
	// this boot so allow_ports/tls_ports/hub changes propagate without a hand edit.
	loadPersistedPorts()
	needEnroll := true // force a re-enroll on every boot (and after a hub-token rejection)

	for {
		tun := readTrim(tunnelTokenPath)
		if needEnroll || tun == "" {
			res := enroll(cl, sn)
			needEnroll = false
			if res.disabled {
				// admin disabled remote access -> do not connect; retry enroll later
				time.Sleep(res.wait)
				needEnroll = true
				continue
			}
			tun = readTrim(tunnelTokenPath) // fresh on 200, else a cached token (enroll never deletes it)
			if tun == "" {
				// no token at all yet (e.g. first-ever enroll was rate-limited) -> wait
				time.Sleep(res.wait)
				needEnroll = true
				continue
			}
			// transient enroll failure with a cached token falls through: connect degraded
			// using the persisted allowlist until the next successful enroll.
		}
		reEnroll, err := runControl(cl, sn, tun)
		if err != nil {
			logln("control:", err)
		}
		if reEnroll {
			// hub rejected the tunnel token (bad/disabled/unknown) -> rotate via re-enroll, rate-limited
			os.Remove(tunnelTokenPath)
			setStatus("hub 401 — tunnel token stale/disabled; re-enroll after " + rateFloor.String())
			needEnroll = true
			time.Sleep(rateFloor)
		} else {
			// hub 5xx (relay not live yet / transient) or clean close -> short back off, keep token
			time.Sleep(2 * time.Minute)
		}
	}
}

// enrollResult tells the serve loop what to do next.
//   ok=true       -> fresh tunnel token + server config applied; connect.
//   disabled=true -> admin turned remote access off (403); do NOT connect.
//   otherwise     -> transient; connect with a cached tunnel token if one exists,
//                    else wait `wait` before retrying.
type enrollResult struct {
	ok       bool
	disabled bool
	wait     time.Duration
}

// enroll POSTs device_token (+ sn, upload_token) and, on 200, applies the server's
// authoritative hub / allow_ports / tls_ports and persists a fresh tunnel token.
// device_token is NEVER removed here — it is permanent.
func enroll(cl *http.Client, sn string) enrollResult {
	dt := deviceToken()
	if dt == "" {
		return enrollResult{wait: 30 * time.Second}
	}
	reqBody := map[string]string{"sn": sn}
	if ut := webflashUploadToken(); ut != "" {
		reqBody["upload_token"] = ut // backend stores against SN for dashboard lookup
	}
	st, body, err := postJSON(cl, strings.TrimRight(cfg["API_BASE"], "/")+cfg["ENROLL_PATH"], dt, reqBody)
	switch {
	case err != nil:
		logln("enroll: network error:", err)
		return enrollResult{wait: 2 * time.Minute}
	case st == 200:
		tun := jsonStr(body, cfg["ENROLL_TOKEN_FIELD"])
		if tun == "" {
			setStatus("enroll 200 but no " + cfg["ENROLL_TOKEN_FIELD"] + " field")
			return enrollResult{wait: rateFloor}
		}
		if hub := jsonStr(body, "hub"); hub != "" { // hub is authoritative, overrides baked value
			cfg["HUB"] = hub
		}
		if ps := jsonPorts(body, "allow_ports"); len(ps) > 0 { // server-authoritative + persisted
			applyPorts(ps, &allowPorts, allowPortsPath)
			logln("enroll: allow_ports", ps)
		}
		if ps := jsonPorts(body, "tls_ports"); len(ps) > 0 { // optional; agent TLS-terminates these
			applyPorts(ps, &tlsPorts, tlsPortsPath)
			logln("enroll: tls_ports", ps)
		}
		atomicWrite(tunnelTokenPath, tun)
		setStatus("enrolled — tunnel token obtained")
		return enrollResult{ok: true}
	case st == 403:
		setStatus("remote access DISABLED by admin (enroll 403) — keeping device token")
		return enrollResult{disabled: true, wait: rateFloor}
	case st == 401:
		setStatus("enroll 401 (transient/server) — keeping device token, backing off")
		return enrollResult{wait: rateFloor}
	case st == 404:
		setStatus("enroll 404 unknown device — keeping device token, backing off")
		return enrollResult{wait: rateFloor}
	case st == 429:
		setStatus("enroll 429 rate-limited — backing off")
		return enrollResult{wait: rateFloor}
	default:
		logln("enroll: status", st, string(body))
		return enrollResult{wait: 2 * time.Minute}
	}
}

type ctrlMsg struct {
	T    string `json:"t"`
	ID   string `json:"id"`
	Port int    `json:"port"`
}

// returns (reEnroll, err). reEnroll is true ONLY on a hub 401 (token problem).
// hub 5xx (501 relay-not-live) and other errors return reEnroll=false (back off, keep token).
func runControl(client *http.Client, sn, tun string) (bool, error) {
	q := url.Values{"sn": {sn}, "token": {tun}}
	u := strings.TrimRight(cfg["HUB"], "/") + "/agent?" + q.Encode()
	ctx := context.Background()
	c, resp, err := websocket.Dial(ctx, u, &websocket.DialOptions{HTTPClient: client})
	if err != nil {
		if resp != nil && resp.StatusCode == 401 {
			return true, err
		}
		if resp != nil && resp.StatusCode >= 500 {
			logln("hub", resp.StatusCode, "(relay not live / transient) — backing off")
		}
		return false, err
	}
	defer c.CloseNow()
	c.SetReadLimit(1 << 20)
	setStatus("connected to hub")

	// Serialized writer for the control socket (multiple session goroutines may
	// report back). coder/websocket forbids concurrent writes; Ping is separate.
	var wmu sync.Mutex
	sendCtl := func(v interface{}) {
		b, _ := json.Marshal(v)
		wmu.Lock()
		defer wmu.Unlock()
		wc, cancel := context.WithTimeout(ctx, 10*time.Second)
		defer cancel()
		_ = c.Write(wc, websocket.MessageText, b)
	}

	kctx, kcancel := context.WithCancel(ctx)
	defer kcancel()
	go func() {
		t := time.NewTicker(25 * time.Second)
		defer t.Stop()
		for {
			select {
			case <-kctx.Done():
				return
			case <-t.C:
				pc, cancel := context.WithTimeout(ctx, 10*time.Second)
				_ = c.Ping(pc)
				cancel()
			}
		}
	}()
	for {
		_, data, err := c.Read(ctx)
		if err != nil {
			return false, err
		}
		var m ctrlMsg
		if json.Unmarshal(data, &m) != nil {
			continue
		}
		if m.T == "open" && m.ID != "" {
			go handleSession(client, sn, tun, m.ID, m.Port, sendCtl)
		}
	}
}

func handleSession(client *http.Client, sn, tun, id string, port int, sendCtl func(interface{})) {
	// openFailed reports the exact reason on the control socket so the operator sees
	// it immediately instead of waiting out a 15s timeout.
	openFailed := func(reason string) {
		logln("session", id, "open_failed port", port, "-", reason)
		sendCtl(map[string]interface{}{"t": "open_failed", "id": id, "port": port, "reason": reason})
	}
	if !allowPorts[port] {
		openFailed("port not allowed: " + strconv.Itoa(port))
		return
	}
	rawtcp, err := net.DialTimeout("tcp", "127.0.0.1:"+strconv.Itoa(port), 5*time.Second)
	if err != nil {
		openFailed("local dial failed: " + err.Error())
		return
	}
	defer rawtcp.Close()
	// For HTTPS-only local services (device UI on 443), terminate TLS here and relay
	// plaintext over the tunnel. Loopback to the device's own self-signed cert, so
	// skip verification; the tunnel itself is the authenticated/encrypted channel.
	var tcp net.Conn = rawtcp
	if tlsPorts[port] {
		tc := tls.Client(rawtcp, &tls.Config{InsecureSkipVerify: true, ServerName: "localhost"})
		if err := tc.Handshake(); err != nil {
			openFailed("tls handshake failed: " + err.Error())
			return
		}
		tcp = tc
	}
	q := url.Values{"id": {id}, "sn": {sn}, "token": {tun}}
	u := strings.TrimRight(cfg["HUB"], "/") + "/session?" + q.Encode()
	ctx := context.Background()
	ws, _, err := websocket.Dial(ctx, u, &websocket.DialOptions{HTTPClient: client})
	if err != nil {
		openFailed("session ws dial failed: " + err.Error())
		return
	}
	defer ws.CloseNow() // backstop; the clean close is nc.Close() below
	ws.SetReadLimit(-1)
	nc := websocket.NetConn(ctx, ws, websocket.MessageBinary)

	// Relay the request (tunnel->device) in the background. When the client is done
	// sending, half-close the device's write side so a `Connection: close` request is
	// acknowledged — but keep the read side open so the response keeps flowing.
	go func() {
		io.Copy(tcp, nc)
		if cw, ok := tcp.(interface{ CloseWrite() error }); ok {
			cw.CloseWrite()
		}
	}()

	// Relay the response (device->tunnel) to completion. This is authoritative: we do
	// NOT tear the session down when the request direction ends — only when the DEVICE
	// closes its side. That guarantees every byte of the declared Content-Length reaches
	// the proxy before we close.
	io.Copy(nc, tcp)

	// Device closed: close the tunnel session cleanly (proper close frame, not CloseNow)
	// so the proxy sees the close and the length is honoured. This also unblocks the
	// request goroutine's read above, so it exits without leaking.
	nc.Close()
}

func main() {
	conf, mode := "/data/bpagent/config", "serve"
	for _, a := range os.Args[1:] {
		if a == "claim" || a == "serve" {
			mode = a
		} else if !strings.HasPrefix(a, "-") {
			conf = a
		}
	}
	loadConfig(conf)
	if mode == "claim" {
		runClaim()
	} else {
		runServe()
	}
}

// webflash - firmware update service for the A3-8396 (LomboTech N7).
//
// Two ways to update, both ending in the proven recovery-flash:
//   1. LOCAL UPLOAD  - browse to http://<device>:<port>/, token + recovery.zip.
//   2. OTA PULL      - periodically checks a manifest URL on your backend
//                      (bettapay) over real HTTPS; when you publish a newer
//                      build for this device it downloads + verifies + flashes.
//
// Both paths: md5-verify -> stage as /data/n7v9_p1-<md5>.zip -> write misc
// (select=2) -> reboot into recovery (which re-verifies before writing flash).
//
// Config: /data/webflash/config  (KEY=VALUE)
//   LISTEN=:8090
//   TOKEN=<secret for local browser upload>
//   OTA_URL=https://api.bettapay.ng/functions/v1/fw-manifest
//   OTA_INTERVAL=3600            # seconds between checks; 0 disables OTA
//   DEVICE_SN=SV-8396H26031043   # identifies this unit to the backend
// No OTA secret in this file: the OTA Bearer is read from the token files
// (/data/device_token after claim, else the fleet token). See otaBearer().
package main

import (
	"archive/tar"
	"archive/zip"
	"bufio"
	"compress/gzip"
	"context"
	"crypto/md5"
	crand "crypto/rand"
	"crypto/subtle"
	"crypto/tls"
	"crypto/x509"
	_ "embed"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"html"
	"io"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"runtime/debug"
	"strconv"
	"strings"
	"time"
)

const product = "n7v9_p1"
const verFile = "/data/webflash/version" // last version we staged (reported to backend)

//go:embed cacert.pem
var caPEM []byte

// misc BCB select=2 (request recovery flash). Validated byte-for-byte against
// the device's resting misc (select=1). Same as the vendor ota_start writes.
var bcbSelect2 = []byte{
	0x55, 0x50, 0x54, 0x20, 0x00, 0x00, 0x00, 0x00, 0xcf, 0xa6, 0x88, 0x32, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0x02, 0x00, 0x00, 0x00, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
}

var cfg = map[string]string{
	"LISTEN":       ":8090",
	"TOKEN":        "",
	"OTA_URL":      "",
	"OTA_INTERVAL": "0",
	"DEVICE_SN":    "",
}

func loadConfig() {
	f, err := os.Open("/data/webflash/config")
	if err != nil {
		return
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if k, v, ok := strings.Cut(line, "="); ok {
			cfg[strings.TrimSpace(k)] = strings.TrimSpace(v)
		}
	}
}

func logln(a ...interface{}) {
	fmt.Fprintf(os.Stdout, "[%s] ", time.Now().Format("2006-01-02 15:04:05"))
	fmt.Fprintln(os.Stdout, a...)
}

func currentVersion() string {
	b, err := os.ReadFile(verFile)
	if err != nil {
		return "none"
	}
	return strings.TrimSpace(string(b))
}

func setVersion(v string) { _ = os.WriteFile(verFile, []byte(v+"\n"), 0644) }

// ----- shared staging + trigger -----

func validateZip(path string) error {
	zr, err := zip.OpenReader(path)
	if err != nil {
		return fmt.Errorf("not a valid zip")
	}
	defer zr.Close()
	for _, f := range zr.File {
		if f.Name == "upgrade.json" {
			return nil
		}
	}
	return fmt.Errorf("zip has no upgrade.json")
}

func stageAndFlash(tmpPath, md5hex, version string) error {
	if err := validateZip(tmpPath); err != nil {
		os.Remove(tmpPath)
		return err
	}
	final := filepath.Join("/data", fmt.Sprintf("%s-%s.zip", product, md5hex))
	if old, _ := filepath.Glob("/data/" + product + "-*.zip"); old != nil {
		for _, m := range old {
			if m != final {
				os.Remove(m)
			}
		}
	}
	if err := os.Rename(tmpPath, final); err != nil {
		return fmt.Errorf("stage: %w", err)
	}
	if version != "" {
		setVersion(version)
	}
	if err := writeMisc(); err != nil {
		return fmt.Errorf("misc write: %w", err)
	}
	logln("staged", final, "and wrote recovery trigger; rebooting")
	go func() {
		time.Sleep(2 * time.Second)
		exec.Command("sync").Run()
		exec.Command("reboot").Run()
	}()
	return nil
}

func writeMisc() error {
	f, err := os.OpenFile("/dev/block/misc", os.O_WRONLY, 0)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = f.WriteAt(bcbSelect2, 0)
	return err
}

// ----- local browser upload -----

const page = `<!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
<title>A3-8396 firmware</title>
<style>
 body{font-family:sans-serif;max-width:42em;margin:2em auto;padding:0 1em;color:#222}
 input,button{font-size:1em}
 #bar{height:1.5em;background:#eee;border-radius:5px;overflow:hidden;display:none;margin:1em 0}
 #fill{height:100%;width:0;background:#2a8a5a;transition:width .15s;color:#fff;font-size:.85em;line-height:1.5em;text-align:center}
 #status{margin-top:1em;white-space:pre-wrap;font-family:monospace;color:#036}
 #status.err{color:#b00}
</style>
<body>
<h2>A3-8396 firmware upload</h2>
<p>Upload a firmware <code>recovery.zip</code> (verified, then reboots into recovery to flash — <b>do not cut power</b>) or a web-UI package <code>.tgz</code> (deployed instantly to the UI, no reboot). The type is auto-detected.</p>
<p>Upload token: <input type=password id=token style=width:24em></p>
<p style="color:#666;font-size:.9em">Device SN: <code>{{SN}}</code> — look up this unit's upload token in the bettapay dashboard.</p>
<p><input type=file id=fw accept=".zip,.tgz,.gz"></p>
<p><button id=go onclick=up()>Upload &amp; flash</button></p>
<div id=bar><div id=fill>0%</div></div>
<div id=status></div>
<script>
function set(s,e){var n=document.getElementById('status');n.textContent=s;n.className=e?'err':''}
function up(){
 var f=document.getElementById('fw').files[0];
 if(!f){set('Choose a .zip first',1);return}
 var fd=new FormData();
 fd.append('token',document.getElementById('token').value);
 fd.append('fw',f,f.name);
 var x=new XMLHttpRequest(),done=false,complete=false;
 document.getElementById('go').disabled=true;
 document.getElementById('bar').style.display='block';
 x.upload.onprogress=function(e){
   if(!e.lengthComputable)return;
   var p=Math.round(e.loaded/e.total*100),fl=document.getElementById('fill');
   fl.style.width=p+'%';fl.textContent=p+'%';
   if(p<100)set('Uploading '+(e.loaded/1048576).toFixed(1)+' / '+(e.total/1048576).toFixed(1)+' MB ...');
   else{complete=true;set('Upload complete ('+(e.total/1048576).toFixed(1)+' MB). Device is verifying MD5 + staging the image — this takes a moment, keep this page open ...');}
 };
 x.onload=function(){done=true;set(x.responseText||('HTTP '+x.status),x.status>=400);};
 x.onerror=function(){ if(!done)set(complete?'Upload done; device appears to be rebooting into recovery to flash. It will be offline a few minutes — do not cut power. Re-check the device after it comes back.':'Connection failed before upload finished — check network/token and retry.',!complete); };
 x.ontimeout=function(){ set('Timed out. Retry.',1); };
 x.open('POST','/flash'); x.timeout=0; x.send(fd);
}
</script></body>`

func handleFlash(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Redirect(w, r, "/", http.StatusSeeOther)
		return
	}
	mr, err := r.MultipartReader()
	if err != nil {
		http.Error(w, "bad form", 400)
		return
	}
	var tok, tmp, sum string
	for {
		p, err := mr.NextPart()
		if err == io.EOF {
			break
		}
		if err != nil {
			http.Error(w, "read", 400)
			return
		}
		switch p.FormName() {
		case "token":
			b, _ := io.ReadAll(io.LimitReader(p, 4096))
			tok = strings.TrimSpace(string(b))
		case "fw":
			ut := uploadToken()
			if ut == "" || subtle.ConstantTimeCompare([]byte(tok), []byte(ut)) != 1 {
				http.Error(w, "unauthorized", 401)
				return
			}
			tmp = "/data/.webflash.part"
			os.Remove(tmp)
			out, err := os.OpenFile(tmp, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0644)
			if err != nil {
				http.Error(w, "tmp", 500)
				return
			}
			h := md5.New()
			if _, err := io.Copy(out, io.TeeReader(p, h)); err != nil {
				out.Close()
				http.Error(w, "save", 500)
				return
			}
			out.Close()
			sum = hex.EncodeToString(h.Sum(nil))
		}
	}
	if tmp == "" {
		http.Error(w, "no file", 400)
		return
	}
	// Auto-detect by magic: gzip (1f 8b) = web-UI package (deploy, no reboot);
	// otherwise a recovery.zip ("PK") = firmware (stage + recovery flash + reboot).
	if m := firstBytes(tmp, 2); len(m) == 2 && m[0] == 0x1f && m[1] == 0x8b {
		if err := deployWebrootFromTgz(tmp); err != nil {
			os.Remove(tmp)
			http.Error(w, "web UI rejected: "+err.Error(), 400)
			return
		}
		os.Remove(tmp)
		fmt.Fprintf(w, "OK: web UI updated (now %s). No reboot needed — reload the page.\n", currentUIVersion())
		return
	}
	if err := stageAndFlash(tmp, sum, ""); err != nil {
		http.Error(w, "rejected: "+err.Error(), 400)
		return
	}
	fmt.Fprintf(w, "OK: staged n7v9_p1-%s.zip, rebooting to flash. Device offline a few minutes; do not cut power.\n", sum)
}

// ----- OTA pull -----

type manifest struct {
	Update  bool   `json:"update"`
	Version string `json:"version"`
	URL     string `json:"url"`
	MD5     string `json:"md5"`
	// Optional, independent web-UI package update (file-level, no reboot).
	UI *struct {
		Update  bool   `json:"update"`
		Version string `json:"version"`
		URL     string `json:"url"`
		MD5     string `json:"md5"`
	} `json:"ui,omitempty"`
}

func httpsClient() *http.Client {
	pool := x509.NewCertPool()
	pool.AppendCertsFromPEM(caPEM)
	return &http.Client{Transport: &http.Transport{
		TLSClientConfig:   &tls.Config{RootCAs: pool, MinVersion: tls.VersionTLS12},
		ForceAttemptHTTP2: true,
	}}
}

// OTA bearer: prefer the per-device token (post-claim); fall back to the fleet
// token (pre-claim). No OTA secret is ever stored in the webflash config. Read
// fresh each poll so the switch to the device token happens as soon as claim
// completes.
func otaBearer() string {
	// OTA bearer is derived ONLY from the token files: the per-device token after
	// claim, else the fleet token pre-claim. No OTA secret is ever kept in the
	// webflash config. (The webflash TOKEN below is unrelated: local upload auth.)
	for _, p := range []string{"/data/device_token", "/data/fleet_token", "/etc/bpa/fleet_token"} {
		if b, err := os.ReadFile(p); err == nil {
			if s := strings.TrimSpace(string(b)); s != "" {
				return s
			}
		}
	}
	return ""
}

const uploadTokenPath = "/data/webflash/upload_token"

// uploadToken is the per-device browser-upload credential for the LAN :8090 page.
// Precedence: an explicit cfg TOKEN override, else the auto-generated per-device
// token at uploadTokenPath, which is created here on first call if absent. This
// makes the fleet zero-touch: every unit boots with its own strong random token
// and no shared default password is ever baked. bpagent reports this value to the
// backend at enroll so an operator can look it up by SN in the dashboard. Returns
// "" only if generation fails, in which case upload fails closed (stays disabled).
func uploadToken() string {
	// Explicit override wins, but mirror it to the canonical file so bpagent
	// (which reads only the file) reports the *effective* token in either case.
	if t := strings.TrimSpace(cfg["TOKEN"]); t != "" {
		persistUploadToken(t)
		return t
	}
	if b, err := os.ReadFile(uploadTokenPath); err == nil {
		if s := strings.TrimSpace(string(b)); s != "" {
			return s
		}
	}
	buf := make([]byte, 24)
	if _, err := crand.Read(buf); err != nil {
		return ""
	}
	s := hex.EncodeToString(buf)
	persistUploadToken(s)
	return s
}

// persistUploadToken writes the effective upload token to the canonical file
// (0600) if it differs, so bpagent's single file-read always yields the token an
// operator must type — whether auto-generated or set via a cfg TOKEN override.
func persistUploadToken(s string) {
	if b, err := os.ReadFile(uploadTokenPath); err == nil && strings.TrimSpace(string(b)) == s {
		return
	}
	tmp := uploadTokenPath + ".tmp"
	if os.WriteFile(tmp, []byte(s+"\n"), 0600) == nil {
		os.Rename(tmp, uploadTokenPath)
	}
}

// deviceSN returns this unit's serial: the cfg value if set, else sysinfo.DeviceSN
// from the device DB (same source bpagent uses). Shown on the upload page so the
// operator knows which SN to look up in the dashboard.
func deviceSN() string {
	if s := strings.TrimSpace(cfg["DEVICE_SN"]); s != "" {
		return s
	}
	out, err := exec.Command("sqlite3", "/data/user.db",
		"select value from sysinfo where key='DeviceSN'").Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(out))
}

// ----- web-UI (webroot) package deploy -----
// A webroot package is a .tgz of the UI tree (index.html at top level, plus a
// .uiver marker). webflash extracts it into /data/webpage/webroot WITHOUT a
// reboot, preserving the writable runtime subdir (webroot/data: enrolled-face
// thumbnails + aio symlinks). Mirrors S61's deploy_webroot for the OTA/upload path.

const webrootDir = "/data/webpage/webroot"
const maxUIBytes = 48 << 20 // cap extraction so a bad package can't fill /data

func currentUIVersion() string {
	if b, err := os.ReadFile(webrootDir + "/.uiver"); err == nil {
		return strings.TrimSpace(string(b))
	}
	return ""
}

// untarGz extracts a gzipped tar into dst, rejecting path traversal and symlinks,
// capping total bytes. Regular files and dirs only.
func untarGz(src, dst string) error {
	f, err := os.Open(src)
	if err != nil {
		return err
	}
	defer f.Close()
	gz, err := gzip.NewReader(f)
	if err != nil {
		return err
	}
	defer gz.Close()
	tr := tar.NewReader(gz)
	var total int64
	for {
		h, err := tr.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return err
		}
		name := filepath.Clean(h.Name)
		if name == "." || name == "/" {
			continue
		}
		if filepath.IsAbs(name) || name == ".." || strings.HasPrefix(name, ".."+string(filepath.Separator)) {
			return fmt.Errorf("unsafe path in package: %s", h.Name)
		}
		target := filepath.Join(dst, name)
		switch h.Typeflag {
		case tar.TypeDir:
			if err := os.MkdirAll(target, 0755); err != nil {
				return err
			}
		case tar.TypeReg:
			if err := os.MkdirAll(filepath.Dir(target), 0755); err != nil {
				return err
			}
			out, err := os.OpenFile(target, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0644)
			if err != nil {
				return err
			}
			n, err := io.Copy(out, io.LimitReader(tr, maxUIBytes-total+1))
			out.Close()
			if err != nil {
				return err
			}
			total += n
			if total > maxUIBytes {
				return fmt.Errorf("package too large (> %d bytes)", maxUIBytes)
			}
		default:
			// skip symlinks/devices/etc — the UI needs none; runtime symlinks live
			// under webroot/data, which we preserve separately.
		}
	}
	return nil
}

// deployWebrootFromTgz extracts a verified UI package and atomically swaps it in,
// preserving webroot/data. No reboot — Mongoose serves the new files on next request.
func deployWebrootFromTgz(tgzPath string) error {
	stage := "/data/.webroot_stage"
	os.RemoveAll(stage)
	if err := os.MkdirAll(stage, 0755); err != nil {
		return err
	}
	if err := untarGz(tgzPath, stage); err != nil {
		os.RemoveAll(stage)
		return err
	}
	if _, err := os.Stat(filepath.Join(stage, "index.html")); err != nil {
		os.RemoveAll(stage)
		return fmt.Errorf("package missing index.html (not a webroot package?)")
	}
	// carry the writable runtime data across (never shipped, never clobbered)
	os.RemoveAll(filepath.Join(stage, "data"))
	if fi, err := os.Stat(filepath.Join(webrootDir, "data")); err == nil && fi.IsDir() {
		if err := os.Rename(filepath.Join(webrootDir, "data"), filepath.Join(stage, "data")); err != nil {
			os.RemoveAll(stage)
			return fmt.Errorf("preserve runtime data: %w", err)
		}
	}
	os.MkdirAll(filepath.Join(stage, "data"), 0755)
	old := webrootDir + ".old"
	os.RemoveAll(old)
	if _, err := os.Stat(webrootDir); err == nil {
		if err := os.Rename(webrootDir, old); err != nil {
			return err
		}
	} else {
		os.MkdirAll(filepath.Dir(webrootDir), 0755)
	}
	if err := os.Rename(stage, webrootDir); err != nil {
		os.Rename(old, webrootDir) // best-effort restore
		return err
	}
	os.RemoveAll(old)
	logln("web UI deployed, version", currentUIVersion())
	return nil
}

func firstBytes(path string, n int) []byte {
	f, err := os.Open(path)
	if err != nil {
		return nil
	}
	defer f.Close()
	b := make([]byte, n)
	m, _ := io.ReadFull(f, b)
	return b[:m]
}

func otaCheck(cl *http.Client) {
	base := cfg["OTA_URL"]
	if base == "" {
		return
	}
	cur := currentVersion()
	q := url.Values{}
	q.Set("sn", cfg["DEVICE_SN"])
	q.Set("ver", cur)
	q.Set("uiver", currentUIVersion())
	q.Set("model", product)
	req, err := http.NewRequest("GET", base+"?"+q.Encode(), nil)
	if err != nil {
		logln("ota: bad url:", err)
		return
	}
	if b := otaBearer(); b != "" {
		req.Header.Set("Authorization", "Bearer "+b)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	resp, err := cl.Do(req.WithContext(ctx))
	if err != nil {
		logln("ota: check failed:", err)
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode == 204 {
		return // no update
	}
	if resp.StatusCode != 200 {
		logln("ota: manifest status", resp.StatusCode)
		return
	}
	var m manifest
	if err := json.NewDecoder(io.LimitReader(resp.Body, 1<<16)).Decode(&m); err != nil {
		logln("ota: bad manifest:", err)
		return
	}
	// Firmware update takes precedence: a rootfs OTA carries its own bundled UI,
	// and flashing reboots — so there's no point deploying a UI package first.
	if m.Update && m.URL != "" && m.Version != "" && len(m.MD5) == 32 && m.Version != cur {
		logln("ota: firmware update offered:", m.Version, "md5", m.MD5)
		if err := otaDownloadAndFlash(cl, m); err != nil {
			logln("ota: firmware FAILED:", err)
		}
		return
	}
	// Otherwise, an optional independent web-UI package (file-level, no reboot).
	if m.UI != nil && m.UI.Update && m.UI.URL != "" && m.UI.Version != "" &&
		len(m.UI.MD5) == 32 && m.UI.Version != currentUIVersion() {
		logln("ota: web UI update offered:", m.UI.Version, "md5", m.UI.MD5)
		if err := otaDownloadAndDeployUI(cl, m.UI.URL, m.UI.MD5); err != nil {
			logln("ota: web UI FAILED:", err)
		}
	}
}

// otaDownloadAndDeployUI fetches a UI package, md5-verifies it, and deploys it to
// /data/webpage/webroot (no reboot).
func otaDownloadAndDeployUI(cl *http.Client, url, wantMD5 string) error {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Minute)
	defer cancel()
	req, _ := http.NewRequestWithContext(ctx, "GET", url, nil)
	if b := otaBearer(); b != "" {
		req.Header.Set("Authorization", "Bearer "+b)
	}
	resp, err := cl.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return fmt.Errorf("download status %d", resp.StatusCode)
	}
	tmp := "/data/.webflash.ui"
	os.Remove(tmp)
	out, err := os.OpenFile(tmp, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0644)
	if err != nil {
		return err
	}
	h := md5.New()
	if _, err := io.Copy(out, io.TeeReader(io.LimitReader(resp.Body, maxUIBytes+1), h)); err != nil {
		out.Close()
		os.Remove(tmp)
		return err
	}
	out.Close()
	if sum := hex.EncodeToString(h.Sum(nil)); !strings.EqualFold(sum, wantMD5) {
		os.Remove(tmp)
		return fmt.Errorf("md5 mismatch: got %s want %s", sum, wantMD5)
	}
	err = deployWebrootFromTgz(tmp)
	os.Remove(tmp)
	return err
}

func otaDownloadAndFlash(cl *http.Client, m manifest) error {
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Minute)
	defer cancel()
	req, _ := http.NewRequestWithContext(ctx, "GET", m.URL, nil)
	if b := otaBearer(); b != "" {
		req.Header.Set("Authorization", "Bearer "+b)
	}
	resp, err := cl.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return fmt.Errorf("download status %d", resp.StatusCode)
	}
	tmp := "/data/.webflash.ota"
	os.Remove(tmp)
	out, err := os.OpenFile(tmp, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0644)
	if err != nil {
		return err
	}
	h := md5.New()
	if _, err := io.Copy(out, io.TeeReader(resp.Body, h)); err != nil {
		out.Close()
		os.Remove(tmp)
		return err
	}
	out.Close()
	sum := hex.EncodeToString(h.Sum(nil))
	if !strings.EqualFold(sum, m.MD5) {
		os.Remove(tmp)
		return fmt.Errorf("md5 mismatch: got %s want %s", sum, m.MD5)
	}
	return stageAndFlash(tmp, sum, m.Version)
}

func otaLoop() {
	ivStr := cfg["OTA_INTERVAL"]
	iv, _ := strconv.Atoi(ivStr)
	if iv <= 0 || cfg["OTA_URL"] == "" {
		logln("ota: disabled")
		return
	}
	if iv < 60 {
		iv = 60
	}
	cl := httpsClient()
	logln("ota: enabled, interval", iv, "s, url", cfg["OTA_URL"], "ver", currentVersion())
	time.Sleep(20 * time.Second) // let the system settle after boot
	for {
		otaCheck(cl)
		time.Sleep(time.Duration(iv) * time.Second)
	}
}

func main() {
	debug.SetGCPercent(20)
	debug.SetMemoryLimit(28 * 1024 * 1024)
	loadConfig()
	cfg["DEVICE_SN"] = deviceSN() // resolve from DB if config left it blank
	uploadToken()                 // ensure the per-device upload token exists for enroll reporting
	go otaLoop()
	sn := cfg["DEVICE_SN"]
	if sn == "" {
		sn = "(unknown)"
	}
	indexPage := strings.Replace(page, "{{SN}}", html.EscapeString(sn), 1)
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		io.WriteString(w, indexPage)
	})
	http.HandleFunc("/flash", handleFlash)
	logln("webflash v2 (progress UI) listening on", cfg["LISTEN"])
	if err := (&http.Server{Addr: cfg["LISTEN"]}).ListenAndServe(); err != nil {
		fmt.Fprintln(os.Stderr, "webflash:", err)
		os.Exit(1)
	}
}

// ttproxy - tiny HTTP->HTTPS reverse proxy for the A3-8396 reader.
// aio speaks plain HTTP to 127.0.0.1:<listen>; this forwards to an HTTPS
// backend with correct Host/SNI, CA verification, and an optional auth header.
// Static ARMv7 build, memory-capped for a 73 MB-RAM device.
package main

import (
	"bufio"
	_ "embed"
	"crypto/tls"
	"crypto/x509"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"runtime/debug"
	"strings"
	"time"
)

//go:embed cacert.pem
var caPEM []byte

func cfg(path string) map[string]string {
	m := map[string]string{
		"LISTEN":      "127.0.0.1:4610",
		"TARGET":      "https://api.bettapay.ng",
		"AUTH_HEADER": "", // e.g. Authorization
		"AUTH_VALUE":  "", // e.g. Bearer s3cr3t
		"MEM_MIB":     "20",
	}
	f, err := os.Open(path)
	if err != nil {
		return m
	}
	defer f.Close()
	s := bufio.NewScanner(f)
	for s.Scan() {
		line := strings.TrimSpace(s.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if i := strings.IndexByte(line, '='); i > 0 {
			k := strings.TrimSpace(line[:i])
			v := strings.TrimSpace(line[i+1:])
			v = strings.Trim(v, "\"'")
			m[k] = v
		}
	}
	return m
}

func main() {
	conf := "/data/ttproxy/config"
	if len(os.Args) > 1 {
		conf = os.Args[1]
	}
	c := cfg(conf)

	// cap memory hard so we never OOM aio on this 73 MB device
	if c["MEM_MIB"] != "" {
		var mib int64
		for _, ch := range c["MEM_MIB"] {
			if ch >= '0' && ch <= '9' {
				mib = mib*10 + int64(ch-'0')
			}
		}
		if mib > 0 {
			debug.SetMemoryLimit(mib * 1024 * 1024)
		}
	}
	debug.SetGCPercent(20)

	target, err := url.Parse(c["TARGET"])
	if err != nil {
		log.Fatalf("bad TARGET %q: %v", c["TARGET"], err)
	}

	pool := x509.NewCertPool()
	if !pool.AppendCertsFromPEM(caPEM) {
		log.Fatal("failed to load embedded CA bundle")
	}

	rp := httputil.NewSingleHostReverseProxy(target)
	orig := rp.Director
	rp.Director = func(r *http.Request) {
		orig(r)
		r.Host = target.Host // route correctly at the backend
		if c["AUTH_HEADER"] != "" && c["AUTH_VALUE"] != "" {
			r.Header.Set(c["AUTH_HEADER"], c["AUTH_VALUE"])
		}
		r.Header.Set("X-Forwarded-Proto", "https")
	}
	rp.Transport = &http.Transport{
		TLSClientConfig: &tls.Config{
			RootCAs:    pool,
			ServerName: target.Hostname(),
			MinVersion: tls.VersionTLS12,
			NextProtos: []string{"http/1.1"}, // pin HTTP/1.1 (no h2 multiplexing)
		},
		DisableKeepAlives:     true, // fresh connection per keepalive -> avoids reused-conn "bad record MAC"
		ForceAttemptHTTP2:     false,
		TLSHandshakeTimeout:   10 * time.Second,
		ResponseHeaderTimeout: 20 * time.Second,
		DisableCompression:    true,
	}
	rp.ErrorLog = log.New(os.Stderr, "ttproxy ", log.LstdFlags)

	srv := &http.Server{
		Addr:         c["LISTEN"],
		Handler:      rp,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 30 * time.Second,
	}
	log.Printf("ttproxy v2 (no-keepalive,http1.1): %s -> %s (auth:%v mem:%sMiB)", c["LISTEN"], c["TARGET"], c["AUTH_HEADER"] != "", c["MEM_MIB"])
	log.Fatal(srv.ListenAndServe())
}

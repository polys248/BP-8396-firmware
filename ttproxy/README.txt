ttproxy - HTTP->HTTPS reverse proxy for the A3-8396 (fixes the Mongoose 6.18
client-TLS bug by letting aio speak plain HTTP to localhost while the proxy
does TLS to your backend). Static ARMv7, CA bundle embedded, memory-capped.

BUNDLE (ttproxy-bundle.tgz; extract with /data as the current directory):
  tailscale-style layout ->
  /data/ttproxy/ttproxy        ELF32 ARM binary (~6.5 MB)
  /data/ttproxy/config         edit: TARGET, optional AUTH header, MEM_MIB
  /data/ttproxy/run.sh         launcher (idempotent)
  /data/stress_test.sh         boot autostart hook

GET IT ONTO THE DEVICE (no scp; use wget + a tiny HTTP server on your PC):
  On CORNERCOMP2 (in the folder holding ttproxy-bundle.tgz):
      python -m http.server 8080
  On the device (telnet shell):
      cd /data
      wget http://<CORNERCOMP2-LAN-IP>:8080/ttproxy-bundle.tgz -O /tmp/tt.tgz
      tar xzf /tmp/tt.tgz          # lays out /data/ttproxy/* and /data/stress_test.sh
  (If /data/stress_test.sh already exists, merge instead of overwrite.)

CONFIGURE (optional auth):
  vi /data/ttproxy/config
    # for HTTPS only: leave AUTH_* blank
    # for auth beyond SN:
    #   AUTH_HEADER=Authorization
    #   AUTH_VALUE=Bearer <long-random-secret>
  Then update your Supabase function to require that header/secret.

TEST THE PROXY BEFORE touching aio (proves TLS works):
  /data/ttproxy/run.sh
  sleep 1; cat /data/ttproxy/ttproxy.log; pidof ttproxy
  free -m; cat /proc/$(pidof ttproxy)/status | grep VmRSS   # watch RAM (<~20MB)
  # send a test request THROUGH the proxy to your backend over HTTPS:
  wget -q -O- --header='Content-Type: application/json' \
       --post-data='{"SN":"TESTSN"}' \
       http://127.0.0.1:4610/functions/v1/reader-gateway
  # a response (even an error JSON) from your function = HTTPS path works.

POINT aio AT THE PROXY (then reboot):
  cp /data/user.db /data/user.db.bak.$(date +%s)
  sqlite3 /data/user.db "
    UPDATE sysinfo SET value='http://127.0.0.1:4610/functions/v1/reader-gateway' WHERE key='HTTPClient_ServerAddr';
    UPDATE sysinfo SET value='127.0.0.1' WHERE key='HTTPClient_ServerIP';
    UPDATE sysinfo SET value='4610'      WHERE key='HTTPClient_ServerPort';
    UPDATE sysinfo SET value='0'         WHERE key='HTTPClient_SSLType';"
  reboot

AFTER REBOOT - verify:
  - /data/ttproxy/ttproxy.log shows incoming requests
  - your Supabase logs show keepalive POSTs arriving over HTTPS (+ the auth header)
  - free -m stays healthy (no OOM; check 'dmesg | tail' for oom-killer)

IF aio DOESN'T hit the proxy (no entries in ttproxy.log):
  aio may use the URL port instead of ServerPort. Confirm with:
      netstat -tn | grep 4610
  If needed, we'll adjust the ServerAddr/port split.

REVERT:
  cp /data/user.db.bak.* /data/user.db     # restore the http://api.bettapay.ng config
  rm -f /data/stress_test.sh               # stop autostarting the proxy
  kill $(pidof ttproxy) 2>/dev/null
  reboot

ROLL FORWARD TO PERMANENT (later): bake an /etc/init.d/S41ttproxy into the
rootfs via the repack flow and keep the binary on /data.

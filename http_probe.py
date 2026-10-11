import re, sys

d = open(sys.argv[1], "rb").read()

def runs():
    for m in re.finditer(rb"[\x20-\x7e]{4,}", d):
        yield m.start(), m.group()

groups = {
    "HTTPClient keys":   re.compile(rb"HTTPClient|HttpClient|http_model|UseHTTPClient", re.I),
    "keepalive":         re.compile(rb"keep[-_ ]?alive", re.I),
    "ssl/tls":           re.compile(rb"ssl|tls|https|wolfssl|mbedtls|cacert|\.pem|x509|verify_peer|SSL_CTX|SSLType", re.I),
    "request lines":     re.compile(rb"^(GET|POST|PUT|HEAD) |HTTP/1\.[01]|Content-Type|Content-Length|User-Agent|Authorization|Host: |Connection:", re.I),
    "url/fmt":           re.compile(rb"https?://|%s[:/]|/%s|[A-Za-z0-9_]+\.(cgi|php|do|api|aspx)|application/json|application/x-www", re.I),
    "auth/ident":        re.compile(rb"serial|(^|[^a-z])sn([^a-z]|$)|device_?id|token|secret|passwo?r?d|api[_-]?key|sign|hmac|md5|appkey", re.I),
}

MAXLINE = 110
for name, rx in groups.items():
    print(f"\n########## {name} ##########")
    seen = set()
    n = 0
    for off, s in runs():
        if rx.search(s):
            t = s.decode("latin1")
            key = t[:60]
            if key in seen:
                continue
            seen.add(key)
            print(f"  {off:#09x}  {t[:MAXLINE]}")
            n += 1
            if n >= 60:
                print("   ...(truncated)")
                break

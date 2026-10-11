import sys
from passlib.hash import sha512_crypt

HASH = "$6$0LfwOVw43ndnyYwt$cKKYBcAsIhkk2hJK9i37kXAH/TxUX8XfRyzYlZFJpSSTn.9vX8CGA0f.4VOqB0.CsN/LVe/4kcCVG3NEyvBq2."

cands = []
# empty + trivial
cands += ["", "root", "toor", "admin", "Admin", "administrator", "password",
          "Password", "pass", "passwd", "123456", "1234", "12345", "123456789",
          "12345678", "1234567890", "88888888", "666666", "000000", "111111",
          "1111", "54321", "123123", "admin123", "root123", "pass123", "12345678",
          "qwerty", "abc123", "a1b2c3", "123qwe", "P@ssw0rd", "Admin@123",
          "admin@123", "root@123", "Admin123", "Root123", "888888", "default"]
# vendor / device specific
cands += ["faceds", "faceds.cc", "facedata", "facesz", "n7", "n7v9", "n7v9_p1",
          "virgo", "Virgo", "lombo", "lombotech", "LomboTech", "a3", "8396",
          "a38396", "A38396", "a3-8396", "A3-8396", "pc15", "yzw", "tange",
          "fulang", "Fulang", "fulang123", "FuLang", "fl123", "fulang@123"]
# common IoT/camera/DVR defaults (incl. Mirai-style)
cands += ["xmhdipc", "vizxv", "7ujMko0admin", "7ujMko0vizxv", "system", "juantech",
          "support", "service", "supervisor", "meinsm", "realtek", "hi3518",
          "Zte521", "user", "guest", "ipcam", "camera", "dvr", "nvr", "hikvision",
          "klv123", "klv1234", "ikwb", "jvbzd", "anko", "zlxx.", "GMB182",
          "ivdev", "cat1029", "hichip", "goahead", "OxhlwSG8", "oelinux123"]
# case/number variants of a few
for b in ["admin", "root", "faceds", "fulang", "n7v9", "virgo"]:
    cands += [b+"123", b+"1234", b+"12345", b+"@123", b.capitalize()+"123", b+"888"]

seen, uniq = set(), []
for c in cands:
    if c not in seen:
        seen.add(c); uniq.append(c)

print(f"testing {len(uniq)} candidates against root $6$ hash...")
hit = None
for c in uniq:
    try:
        if sha512_crypt.verify(c, HASH):
            hit = c; break
    except Exception:
        pass
print("RESULT:", f"root password = {hit!r}" if hit is not None else "no match in this list")

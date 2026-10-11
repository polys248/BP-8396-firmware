import struct, sys

def deshift(data: bytes) -> bytes:
    """Invert the packer transform: each 16-bit LE word rotated right by 1 bit.
    Inverse = rotate each 16-bit LE word left by 1 bit (lossless)."""
    n = len(data) & ~1
    out = bytearray(data)
    for o in range(0, n, 2):
        w = data[o] | (data[o + 1] << 8)
        w = ((w << 1) | (w >> 15)) & 0xFFFF
        out[o] = w & 0xFF
        out[o + 1] = (w >> 8) & 0xFF
    return bytes(out)

if __name__ == "__main__":
    data = open(sys.argv[1], "rb").read()
    plain = deshift(data)
    if len(sys.argv) > 2:
        open(sys.argv[2], "wb").write(plain)
    print(f"{sys.argv[1].split(chr(92))[-1]}: {plain[:16].hex()}")

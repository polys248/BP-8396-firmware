import struct, sys
from PySquashfsImage import SquashFsImage

p = sys.argv[1]
d = open(p, "rb").read()

(magic, inode_count, mod_time, block_size, frag_count) = struct.unpack_from("<IIIII", d, 0)
(comp, block_log, flags, id_count, vmaj, vmin) = struct.unpack_from("<HHHHHH", d, 0x14)
(root_inode, bytes_used, id_tbl, xattr_tbl, inode_tbl, dir_tbl, frag_tbl, export_tbl) = \
    struct.unpack_from("<QQQQQQQQ", d, 0x20)

cmap = {1:"gzip",2:"lzma",3:"lzo",4:"xz",5:"lz4",6:"zstd"}
FLAGS = [(0x0001,"UNCOMPRESSED_INODES"),(0x0002,"UNCOMPRESSED_DATA"),(0x0004,"CHECK"),
         (0x0008,"UNCOMPRESSED_FRAGMENTS"),(0x0010,"NO_FRAGMENTS"),(0x0020,"ALWAYS_FRAGMENTS"),
         (0x0040,"DUPLICATES"),(0x0080,"EXPORTABLE"),(0x0100,"UNCOMPRESSED_XATTRS"),
         (0x0200,"NO_XATTRS"),(0x0400,"COMPRESSOR_OPTIONS"),(0x0800,"UNCOMPRESSED_IDS")]

print(f"magic        {magic:#x} {'OK' if magic==0x73717368 else 'BAD'}")
print(f"version      {vmaj}.{vmin}")
print(f"compression  {comp} ({cmap.get(comp,'?')})")
print(f"block_size   {block_size} (1<<{block_log})")
print(f"inodes       {inode_count}   fragments {frag_count}   ids {id_count}")
print(f"bytes_used   {bytes_used} (0x{bytes_used:x})   file {len(d)} (0x{len(d):x})")
print(f"flags        {flags:#06x}: " + ", ".join(n for m,n in FLAGS if flags & m))
NO = 0xFFFFFFFFFFFFFFFF
print(f"xattr_table  {'none' if xattr_tbl==NO else hex(xattr_tbl)}")
print(f"export_table {'none' if export_tbl==NO else hex(export_tbl)}")
print(f"compressor_options_block present: {bool(flags & 0x0400)}")

# metadata block right after superblock (0x60) — if COMPRESSOR_OPTIONS, it holds xz opts
if flags & 0x0400:
    hdr, = struct.unpack_from("<H", d, 0x60)
    size = hdr & 0x7FFF
    comp_flag = "stored" if (hdr & 0x8000) else "compressed"
    print(f"  comp-opts block @0x62 len={size} ({comp_flag})")
    print(f"  raw: {d[0x62:0x62+size].hex()}")

# enumerate node types + uid/gid + xattrs
types = {}
uids, gids = set(), set()
have_xattr = 0
devnodes = 0
with SquashFsImage.from_file(p) as img:
    for n in img:
        t = type(n).__name__
        types[t] = types.get(t, 0) + 1
        for attr in ("uid", "gid"):
            v = getattr(n, attr, None)
            if v is not None:
                (uids if attr == "uid" else gids).add(v)
        if getattr(n, "xattrs", None):
            have_xattr += 1
        if n.is_device if hasattr(n, "is_device") else False:
            devnodes += 1
print("node types  ", types)
print("uids        ", sorted(uids), "  gids", sorted(gids))
print("nodes w/xattr", have_xattr, "  device-nodes", devnodes)

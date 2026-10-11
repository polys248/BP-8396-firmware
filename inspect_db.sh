#!/bin/bash
umount /mnt/rootimg 2>/dev/null
mkdir -p /mnt/rootimg
mount -o loop,ro /mnt/c/Users/Isaac/fw-v923/extract/root__rootfs.img /mnt/rootimg || { echo "mount failed"; exit 1; }
A=/mnt/rootimg/usr/bin/aio
echo "=== .db file paths referenced by aio ==="
strings -n 6 "$A" | grep -iE '/data/.*\.db|\.db$|\.db[^a-z]|user\.db|attend.*\.db|people.*\.db|face.*\.db' | sort -u | head -30
echo
echo "=== people/user table names (CREATE TABLE / FROM / INTO) ==="
strings -n 6 "$A" | grep -iE 'CREATE TABLE|FROM user|FROM people|INTO user|INTO people|tbl_|_table|TABLE IF NOT EXISTS' | sort -u | head -30
echo
echo "=== the table-name token used in the people INSERT (look near face_feat) ==="
strings -n 4 "$A" | grep -iE 'user_info|people_info|t_user|t_people|userlist|peoplelist|face_feat|attend' | sort -u | head -30
echo
echo "=== sqlite open / attach db calls context ==="
strings -n 6 "$A" | grep -iE 'sqlite3_open|/data/.*db|baseconfig|user\.db|facedata' | sort -u | head -30
umount /mnt/rootimg 2>/dev/null

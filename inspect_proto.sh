#!/bin/bash
umount /mnt/rootimg 2>/dev/null
mkdir -p /mnt/rootimg
mount -o loop,ro /mnt/c/Users/Isaac/fw-v923/extract/root__rootfs.img /mnt/rootimg || { echo "mount failed"; exit 1; }
A=/mnt/rootimg/usr/bin/aio
echo "=== attendance/docking person commands (add/del people) ==="
strings -n 5 "$A" | grep -iE 'add_people|del_people|AddPeople|DelPeople|update_people|people_cmd|add_person|set_people|EnrollFace|RegisterFace|REGISTER_FACE' | sort -u | head -40
echo
echo "=== does the docking protocol carry a face feature / template field? ==="
strings -n 5 "$A" | grep -iE 'FaceFeature|face_feature|feature_data|Fingerprint|Palmvein|Feature.*base64|template|biometric|faceData|RegisterUserMediaData|EnrollUserMediaData|MediaData' | sort -u | head -40
echo
echo "=== HTTPv2 / reader-gateway command names (backend<->device) ==="
strings -n 6 "$A" | grep -oE '"[a-z_]+"' | grep -iE 'people|person|face|feature|enroll|register|media|photo|user' | sort -u | head -50
echo
echo "=== does the web API auth check have a loopback/local bypass? ==="
strings -n 5 "$A" | grep -iE 'CheckRequestAuthorization|127.0.0.1|localhost|loopback|is_local|LocalRequest|skip.*auth|no.?auth' | sort -u | head -20
umount /mnt/rootimg 2>/dev/null

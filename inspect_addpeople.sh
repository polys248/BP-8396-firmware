#!/bin/bash
umount /mnt/rootimg 2>/dev/null
mkdir -p /mnt/rootimg
mount -o loop,ro /mnt/c/Users/Isaac/fw-v923/extract/root__rootfs.img /mnt/rootimg || { echo "mount failed"; exit 1; }
A=/mnt/rootimg/usr/bin/aio
echo "=== candidate AddPeople JSON keys (people + biometric field names) ==="
strings -n 3 "$A" | grep -xiE '(UserID|UserId|userid|Name|CardID|CardId|CardNum|cardid|Password|Department|department|Authority|authority|FaceFeature|FaceFeatureMD5|face_feat|FacePoints|face_points|FaceNorm|face_norm|FacePhoto|Photo|PhotoURL|PhotoMD5|PhotoLen|Fingerprint|Fingerprint1|Fingerprint2|Fingerprint3|fingerprint_1|fingerprint_2|fingerprint_3|Fingerprints|Palm|Palmvein|Palmveins|palm_record_id_left|palm_record_id_right|ValidTimes|valid_times|OpeningTimePeriod|opening_time_period|People|Peoples|PeopleList|AddPeople|DelPeople|Face|Feature|FeatureData)' | sort -u
echo
echo "=== people-push cache json (shows the field shape BettaPay already sends) ==="
strings -n 4 "$A" | grep -iE 'people_push|AddPeople|add_people|PeopleData|user_push' | sort -u | head -20
echo
echo "=== face_feat / blob handling (is the face template a blob triple?) ==="
strings -n 5 "$A" | grep -iE 'face_feat|face_points|face_norm|FaceFeature|feat_len|face_feature_len|FeatureSize|blob' | sort -u | head -20
umount /mnt/rootimg 2>/dev/null

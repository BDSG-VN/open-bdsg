#!/bin/sh
# Không tự xóa bản cũ: cảnh báo dung lượng phải được người vận hành xử lý.
set -eu
umask 077
exec /usr/bin/flock -n /var/backups/bdsg-thanhhoa/.lock \
  /usr/bin/python3 /srv/bdsg-thanhhoa/open-bdsg/current/source/he-dieu-hanh/sao_luu_he_thong.py \
  backup --data /var/lib/bdsg-thanhhoa --secrets-dir /etc/bdsg-thanhhoa \
  --destination "/var/backups/bdsg-thanhhoa/$(date -u +%Y%m%dT%H%M%SZ)"

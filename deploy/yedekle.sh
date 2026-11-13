#!/bin/sh
# config/ ve data/ klasörlerinin günlük yedeği. Sunucuda cron ile çalışır:
#   15 3 * * *  /opt/taskentticaret/deploy/yedekle.sh >> /opt/taskentticaret/yedekler/yedek.log 2>&1
# Ortam değişkenleri:
#   SAKLA_GUN   kaç günlük yedek tutulur (varsayılan 14)
#   UZAK        isteğe bağlı rclone hedefi (ör. "yedek:taskentticaret"); boşsa yalnızca sunucuda tutulur
set -eu
KOK="$(cd "$(dirname "$0")/.." && pwd)"
HEDEF="$KOK/yedekler"
SAKLA_GUN="${SAKLA_GUN:-14}"
DOSYA="$HEDEF/yedek-$(date +%Y-%m-%d_%H%M).tar.gz"

mkdir -p "$HEDEF"
chmod 700 "$HEDEF"   # yedekte şifre karmaları ve API anahtarları var
# Önbellek yeniden üretilebilir; yedeğe alınmaz
tar -czf "$DOSYA" -C "$KOK" --exclude='data/cache' config data
chmod 600 "$DOSYA"
echo "$(date '+%F %T') yedek alındı: $DOSYA ($(du -h "$DOSYA" | cut -f1))"

find "$HEDEF" -name 'yedek-*.tar.gz' -mtime +"$SAKLA_GUN" -delete

if [ -n "${UZAK:-}" ]; then
  rclone copy "$DOSYA" "$UZAK" && echo "uzak kopya: $UZAK"
fi

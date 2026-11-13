#!/bin/sh
# Yeni bir Ubuntu 22.04/24.04 sunucuda tek seferlik kurulum (root olarak çalıştırın):
#   sh deploy/sunucu-kur.sh
set -eu
KOK="$(cd "$(dirname "$0")/.." && pwd)"

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi

# Güvenlik duvarı: yalnızca SSH, HTTP, HTTPS
if command -v ufw >/dev/null 2>&1; then
  ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw allow 443/udp
  ufw --force enable
fi

[ -f "$KOK/.env" ] || { cp "$KOK/.env.example" "$KOK/.env"; echo ">> $KOK/.env dosyasını düzenleyin (DOMAIN, ACME_EMAIL), sonra bu betiği tekrar çalıştırın."; exit 0; }

cd "$KOK"
docker compose up -d --build

# Günlük yedek (03:15)
( crontab -l 2>/dev/null | grep -v yedekle.sh; echo "15 3 * * * $KOK/deploy/yedekle.sh >> $KOK/yedekler/yedek.log 2>&1" ) | crontab -
mkdir -p "$KOK/yedekler"

sleep 5
echo ">> İlk kurulum kodu:"
docker compose logs panel | grep "KURULUM KODU" | tail -1 || true
echo ">> Panel: https://$(grep ^DOMAIN= .env | cut -d= -f2)"

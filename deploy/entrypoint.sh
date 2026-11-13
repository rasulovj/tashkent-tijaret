#!/bin/sh
# Kalıcı klasörleri hazırlar, sonra paneli "app" kullanıcısıyla başlatır.
set -e
# Tek kalıcı diskli platformlarda (Railway vb.) config/ ve data/ aynı diskte tutulur: PERSIST_DIR=/kalici
if [ -n "${PERSIST_DIR:-}" ]; then
  mkdir -p "$PERSIST_DIR/config" "$PERSIST_DIR/data"
  for d in config data; do
    [ -L "/app/$d" ] || { rm -rf "/app/$d"; ln -s "$PERSIST_DIR/$d" "/app/$d"; }
  done
  chown -R app:app "$PERSIST_DIR"
fi
mkdir -p /app/config /app/data
# Eksik hazır ayar dosyalarını kopyala; panelde değiştirilmiş olanlara dokunma
cp -rn /app/config.default/. /app/config/
chown -R app:app /app/config /app/data
chmod 700 /app/config
RUN="setpriv --reuid=app --regid=app --init-groups"
# Boş kurulumda panelin açılabilmesi için ilk (boş) sayı klasörü oluşturulur
if ! ls /app/data/*/candidates.json >/dev/null 2>&1; then
  $RUN python run.py select || true
fi
exec $RUN "$@"

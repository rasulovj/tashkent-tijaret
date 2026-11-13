# Taşkent Ticaret Müşavirliği – robot platform (panel) imajı: Python + Chromium + ffmpeg
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Tashkent \
    CHROME_PATH=/usr/local/bin/chrome \
    PANEL_HOST=0.0.0.0 \
    PANEL_PUBLIC=1

# Chromium (başsız kabuk): PDF/PNG üretimi · fontlar: Türkçe, Kiril ve Özbek harfleri · ffmpeg: video bülten
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium-headless-shell fonts-liberation fonts-dejavu-core fonts-noto-core fonts-noto-color-emoji \
        ffmpeg tzdata ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Tüm Chrome çağrıları bu sarmalayıcıdan geçer. Başsız kabuk, --window-size ile tam piksel ölçüsünde
# ekran görüntüsü verir (tam Chromium'un "yeni başsız" kipi Linux'ta alttan ~90 px keser).
# Konteynerde Chrome korumalı alanı çalışmadığı için --no-sandbox gerekir.
RUN B="$(dpkg -L chromium-headless-shell | grep -E '/(chromium-)?headless[-_]shell$' | head -1)" \
    && test -f "$B" && test -x "$B" \
    && printf '#!/bin/sh\nexec %s --no-sandbox --disable-dev-shm-usage "$@"\n' "$B" > /usr/local/bin/chrome \
    && chmod +x /usr/local/bin/chrome

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Hazır ayarlar (kaynaklar, birimler, rapor türleri) imajda ayrıca saklanır; ilk açılışta kalıcı config/ klasörüne kopyalanır
RUN mv config config.default && mkdir -p config data static/guide \
    && rm -f config.default/users.json config.default/keys.json config.default/telegram.json config.default/kurulum-kodu.txt \
    && useradd -u 1000 -m app && chown -R app:app /app \
    && chmod +x deploy/entrypoint.sh

EXPOSE 8765
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -fsS -o /dev/null "http://127.0.0.1:${PORT:-8765}/giris" || exit 1
ENTRYPOINT ["deploy/entrypoint.sh"]
# PORT: barındırma platformu verirse o port, yoksa 8765
CMD ["sh", "-c", "exec python run.py panel ${PORT:-8765}"]

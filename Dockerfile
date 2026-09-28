

# 1) Temel imaj: içinde Linux + Python 3.13 hazır gelen resmi imaj
FROM python:3.13-slim


# 2) Python ayarları
#    .pyc dosyası üretme, logları beklemeden hemen yaz
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1


# 3) Container içindeki çalışma klasörü (yoksa oluşturulur, sonraki komutlar burada çalışır)
WORKDIR /app   


# 4) Proje dosyalarını bilgisayardan imaja kopyala
COPY pyproject.toml ./
COPY src ./src

# 5) Projeyi ve bağımlılıklarını kur (mcp, httpx, python-dotenv)
RUN pip install --no-cache-dir .

# 6) Güvenlik: root yerine yetkisi kısıtlı bir kullanıcıyla çalış
RUN useradd --create-home devpulse \
    &&  mkdir -p /app/data \
    && chown devpulse /app/data
USER devpulse

# 7) Veritabanı nerede duracak (config.py bu değişkeni okuyor)
ENV DEVPULSE_DB=/app/data/devpulse.db

# 8) Container başlayınca çalışacak komut: MCP sunucusu
CMD ["devpulse-mcp"]



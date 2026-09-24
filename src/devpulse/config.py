
"""Uygulama ayarları.
Gizli bilgiler(token gibi) kodun içine yazılmaz. Ortam değişkenlerinden okunur.
Geliştirme sırasında bu değişkenler proje kökündeki .env dosyasından yüklenir.
"""

import os

from dotenv import load_dotenv

# .env dosyasını bulup içindeki değerleri ortam değişkenlerine yükler.
# Dosya yoksa (ör. Docker'da ya da GitHub Actions'ta) sessizce devam eder.
load_dotenv()

def github_token() -> str | None:
    """Github token'ını döndürür. Tanımlı değilse None döner."""
    token = os.getenv("GITHUB_TOKEN", "").strip()
    return token or None
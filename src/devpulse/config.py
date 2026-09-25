"""Uygulama ayarları.
Gizli bilgiler(token gibi) kodun içine yazılmaz. Ortam değişkenlerinden okunur.
Geliştirme sırasında bu değişkenler proje kökündeki .env dosyasından yüklenir.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# .env dosyasını bulup içindeki değerleri ortam değişkenlerine yükler.
# Dosya yoksa (ör. Docker'da ya da GitHub Actions'ta) sessizce devam eder.
load_dotenv()

PROJE_KOKU = Path(__file__).resolve().parents[2]


def github_token() -> str | None:
    """Github token'ını döndürür. Tanımlı değilse None döner."""
    token = os.getenv("GITHUB_TOKEN", "").strip()
    return token or None


def veritabani_yolu() -> Path:
    """Veritabanı dosyasının yolu. DEVPULSE_DB ortam değişkeniyle değiştirilebilir."""
    ozel_yol = os.getenv("DEVPULSE_DB", "").strip()
    if ozel_yol:
        return Path(ozel_yol)
    return PROJE_KOKU / "data" / "devpulse.db"

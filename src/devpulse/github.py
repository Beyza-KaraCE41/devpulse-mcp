"""GitHub REST API istemcisi."""

import logging
import time
from datetime import UTC, datetime, timedelta

import httpx

from devpulse.config import github_token

API_URL = "https://api.github.com"
DENEME_SAYISI = 3

log = logging.getLogger(__name__)


class GitHubLimitError(Exception):
    """GitHub istek limiti dolduğunda fırlatılır."""

    def __init__(self, sifirlanma: int) -> None:
        self.sifirlanma = sifirlanma
        saat = datetime.fromtimestamp(sifirlanma, UTC).strftime("%H:%M UTC")
        super().__init__(f"GitHub istek limiti doldu. {saat} itibarıyla sıfırlanacak.")


def _basliklar() -> dict[str, str]:
    """Her istekle birlikte gönderilecek HTTP başlıkları."""
    basliklar = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "devpulse-mcp",
    }
    token = github_token()
    if token:
        basliklar["Authorization"] = f"Bearer {token}"
    return basliklar


def _limit_doldu_mu(yanit: httpx.Response) -> bool:
    """Cevap, 'istek limitin doldu' anlamına mı geliyor?"""
    return yanit.status_code in (403, 429) and yanit.headers.get("x-ratelimit-remaining") == "0"


def _get(yol: str, params: dict | None = None) -> httpx.Response:
    """GitHub'a GET isteği atar. Geçici hatalarda tekrar dener, limit dolunca durur."""
    for deneme in range(1, DENEME_SAYISI + 1):
        try:
            yanit = httpx.get(f"{API_URL}{yol}", headers=_basliklar(), params=params, timeout=10)
        except httpx.TransportError as hata:
            # İnternet kesildi, zaman aşımı vb. Geçici olabilir, tekrar dene.
            log.warning("Ağ hatası: %s (deneme %d/%d)", hata, deneme, DENEME_SAYISI)
        else:
            if _limit_doldu_mu(yanit):
                raise GitHubLimitError(int(yanit.headers["x-ratelimit-reset"]))
            if not yanit.is_server_error:
                yanit.raise_for_status()  # 4xx: bizim hatamız, tekrar denemek işe yaramaz
                log.debug("Kalan istek hakkı: %s", yanit.headers.get("x-ratelimit-remaining"))
                return yanit
            # 5xx: GitHub tarafında geçici bir sorun, tekrar dene.
            log.warning("GitHub hatası %d (deneme %d/%d)", yanit.status_code, deneme, DENEME_SAYISI)

        if deneme < DENEME_SAYISI:
            time.sleep(2**deneme)  # 2 sn, sonra 4 sn bekle

    mesaj = f"GitHub'a {DENEME_SAYISI} denemede ulaşılamadı: {yol}"
    raise ConnectionError(mesaj)


def limit_durumu() -> dict[str, int]:
    """Kalan API istek hakkını döndürür. Bu istek limitten düşmez."""
    core = _get("/rate_limit").json()["resources"]["core"]
    return {"limit": core["limit"], "kalan": core["remaining"], "sifirlanma": core["reset"]}


def _repo_ozeti(repo: dict) -> dict:
    """GitHub'ın uzun repo cevabından sadece işimize yarayan alanları seçer."""
    return {
        "ad": repo["full_name"],
        "aciklama": repo.get("description") or "",
        "yildiz": repo["stargazers_count"],
        "dil": repo.get("language") or "Bilinmiyor",
        "konular": repo.get("topics", []),
        "url": repo["html_url"],
    }


def yeni_populer_repolar(gun: int = 7, dil: str | None = None, adet: int = 10) -> list[dict]:
    """Son `gun` gün içinde oluşturulmuş, en çok yıldız alan repoları döndürür."""
    adet = max(1, min(adet, 100))  # GitHub tek sayfada en fazla 100 sonuç verir

    bugun = datetime.now(UTC).date()  # GitHub tarihleri UTC'ye göre tutar
    baslangic = bugun - timedelta(days=gun)
    sorgu = f"created:>={baslangic.isoformat()}"
    if dil:
        sorgu += f" language:{dil}"

    params = {"q": sorgu, "sort": "stars", "order": "desc", "per_page": adet}
    yanit = _get("/search/repositories", params=params)
    return [_repo_ozeti(repo) for repo in yanit.json()["items"]]

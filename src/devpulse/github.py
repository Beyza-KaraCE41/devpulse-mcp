"""GitHub REST API istemcisi."""

from datetime import UTC, datetime, timedelta

import httpx

from devpulse.config import github_token

API_URL = "https://api.github.com"


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


def limit_durumu() -> dict[str, int]:
    """Kalan API istek hakkını döndürür. Bu istek limitten düşmez."""
    yanit = httpx.get(f"{API_URL}/rate_limit", headers=_basliklar(), timeout=10)
    yanit.raise_for_status()
    core = yanit.json()["resources"]["core"]
    return {"limit": core["limit"], "kalan": core["remaining"], "sifirlanma": core["reset"]}


def _repo_ozeti(repo: dict) -> dict:
    """Github'ın uzun repo cevabından sadece işimize yarayan alanları seçer."""
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
    adet = max(1, min(adet, 100))
    bugun = datetime.now(UTC).date()
    baslangic = bugun - timedelta(days=gun)
    sorgu = f"created:>={baslangic.isoformat()}"
    if dil:
        sorgu += f"language:{dil}"
    yanit = httpx.get(
        f"{API_URL}/search/repositories",
        headers=_basliklar(),
        params={"q": sorgu, "sort": "stars", "order": "desc", "per_page": adet},
        timeout=10,
    )
    yanit.raise_for_status()
    return [_repo_ozeti(repo) for repo in yanit.json()["items"]]

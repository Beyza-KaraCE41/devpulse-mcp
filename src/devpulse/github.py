
"""GitHub REST API istemcisi. """

import httpx

from devpulse.config import github_token

API_URL= "https://api.github.com"

def _basliklar() -> dict[str, str]:
    """Her istekle birlikte gönderilecek HTTP başlıkları."""
    basliklar={
        "Accept": "application/vnd.github+json",
        "User-Agent": "devpulse-mcp",
    }
    token= github_token()
    if token:
        basliklar["Authorization"]=f"Bearer {token}"
    return basliklar

def limit_durumu() -> dict[str, int]:
    """Kalan API istek hakkını döndürür. Bu istek limitten düşmez."""
    yanit= httpx.get(f"{API_URL}/rate_limit", headers=_basliklar(), timeout=10)
    yanit.raise_for_status()
    core= yanit.json()["resources"]["core"]
    return {"limit": core["limit"], "kalan": core["remaining"], "sifirlanma": core["reset"]}
    
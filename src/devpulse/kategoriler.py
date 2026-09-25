"""Repoları Github etiketlerine ve açıklamalarına bakarak kategorilere ayırır."""

import re

# Her kategori için anahtar kelimeler. Github etiketleri küçük harf ve tireli yaızlır.
KATEGORILER: dict[str, set[str]] = {
    "Yapay Zekâ": {
        "ai",
        "llm",
        "llms",
        "machine-learning",
        "deep-learning",
        "agent",
        "agents",
        "ai-agents",
        "rag",
        "transformers",
        "nlp",
        "chatbot",
        "gpt",
        "generative-ai",
        "computer-vision",
        "diffusion",
        "mcp",
        "inference",
        "neural",
        "coreml",
        "mlx",
        "agi",
        "claude",
        "codex",
        "language-model",
    },
    "Mobil": {
        "android",
        "ios",
        "flutter",
        "react-native",
        "swiftui",
        "jetpack-compose",
        "mobile",
        "mobile-app",
    },
    "Web": {
        "react",
        "nextjs",
        "vue",
        "svelte",
        "angular",
        "frontend",
        "web",
        "tailwindcss",
        "css",
        "html",
    },
    "API/Backend": {
        "api",
        "rest-api",
        "graphql",
        "backend",
        "microservices",
        "fastapi",
        "django",
        "express",
        "grpc",
    },
    "DevOps": {
        "docker",
        "kubernetes",
        "devops",
        "ci-cd",
        "terraform",
        "infrastructure",
        "observability",
        "monitoring",
    },
    "Veri": {
        "database",
        "sql",
        "data-engineering",
        "analytics",
        "etl",
        "data-science",
        "postgresql",
        "sqlite",
        "vector-database",
    },
    "Güvenlik": {
        "security",
        "cybersecurity",
        "pentest",
        "cryptography",
        "vulnerability",
        "privacy",
    },
    "Geliştirici Araçları": {
        "cli",
        "developer-tools",
        "devtools",
        "vscode-extension",
        "ide",
        "terminal",
        "code-generation",
        "coding-assistant",
    },
    "Oyun": {
        "game",
        "gamedev",
        "game-engine",
        "godot",
        "unity",
        "pygame",
    },
}

DIGER = "Diğer"


def _metinde_geciyor_mu(kelime: str, metin: str) -> bool:
    """Kelime metinde ayrı bir kelime olarak geçiyor mu?
    "ai" kelimesi "maintain" içinde eşleşmemeli, bu yüzden keliem sınırı (\\b) kullanıyoruz.
    Etiketteki tire, açıklamada boşluk olarak da yazılabilir ("machine learning").
    """
    kalip = r"\b" + re.escape(kelime).replace(r"\-", r"[\s-]") + r"\b"
    return re.search(kalip, metin) is not None


def kategorile(konular: list[str], aciklama: str, ad: str = "") -> list[str]:
    """Bir repo'nun ait olduğu kategorileri döndürür. Hiçbirine uymazsa ["Diğer"].
    Açıklamanın yanında repo adına da bakılır: "mini-AGI" -> "mini agi".
    """
    etiketler = {k.lower() for k in konular}
    ad_kelimeleri = re.sub(r"[/_-]", " ", ad)
    metin = f"{aciklama} {ad_kelimeleri}".lower()

    bulunanlar = []
    for kategori, kelimeler in KATEGORILER.items():
        etikette_var = bool(etiketler & kelimeler)
        aciklamada_var = any(_metinde_geciyor_mu(k, metin) for k in kelimeler)
        if etikette_var or aciklamada_var:
            bulunanlar.append(kategori)
    return bulunanlar or [DIGER]

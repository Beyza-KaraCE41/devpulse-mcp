# DevPulse Yol Haritası

## Tamamlananlar
- [x] Git + GitHub, .gitignore, Conventional Commits
- [x] Proje iskeleti (src layout, pyproject.toml)
- [x] GitHub API istemcisi, güvenli token (.env), retry ve limit yönetimi
- [x] SQLite veritabanı: repolar, günlük fotoğraflar, kategoriler
- [x] Kural tabanlı kategorileme
- [x] MCP sunucusu ve Claude Desktop bağlantısı
- [x] Tool'lar: populer_repolar, kategori_ozeti, hizla_yukselenler
- [x] devpulse-topla komutu, pencereden çıkan repoların takibi
- [x] MCP Prompts ("Sabah bülteni") ve Resources (veri durumu, kategori kuralları)

## Sırada
- [ ] Testler: pytest, mock ile API testi
- [ ] Docker: konteyner imajı
- [ ] GitHub Actions: her push'ta test + ruff, her gün otomatik veri toplama
- [ ] Deploy: internette çalışan sunucu, kimlik doğrulama, claude.ai ve telefondan kullanım
- [ ] Ajan: Claude Agent SDK ile "söyle, kendisi araştırıp yapsın" ajanı
- [ ] Akıllı özellikler: embedding ile kümeleme, sahte yıldız dedektörü
- [ ] Ek veri kaynakları: PyPI, npm, Hacker News, iş ilanı teknoloji analizi
- [ ] README: kurulum, ekran görüntüleri, mimari, kullanılan beceriler

## Bilinen sınırlamalar
- Kategorileme kural tabanlı; olumsuz cümleleri anlamıyor ("API gerektirmez" → API/Backend).
- Toplayıcı pencereden çıkan repoları tek tek sorguluyor; takip listesi büyüdükçe yavaşlıyor.
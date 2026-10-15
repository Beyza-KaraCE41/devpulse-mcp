"""Web panosu: veritabanından tek dosyalık, etkileşimli bir HTML sayfası üretir.

Sayfanın tasarımı ve JavaScript'i pano.html şablonunda durur. Bu modül sadece
veriyi hazırlayıp şablonun içine JSON olarak yerleştirir. GitHub Actions her gece
çıktıyı GitHub Pages'e yayınlar.

Elle denemek için:  devpulse-pano --cikti site
"""

import argparse
import json
import sqlite3
from importlib.resources import files
from pathlib import Path

from devpulse import db
from devpulse.rapor import (
    kategori_dagilimi,
    son_iki_tarih,
    supheliler,
    yeni_gorulenler,
    yukselenler,
)

LISTE_ADEDI = 30  # Filtrelenebilmesi için her listeden kaç repo gönderilsin
GECMIS_GUN = 30  # Grafiklerde kaç günlük yıldız geçmişi gösterilsin
YER_TUTUCU = "__DEVPULSE_VERI__"


def _repo_ayrintilari(baglanti: sqlite3.Connection, adlar: list[str], son: str) -> dict[str, dict]:
    """Verilen repoların açıklama, dil, kategori, fork ve yıldız geçmişi."""
    if not adlar:
        return {}
    soru_isaretleri = ",".join("?" for _ in adlar)  # (?, ?, ?) — yine parametreli sorgu

    ayrintilar: dict[str, dict] = {}
    for r in baglanti.execute(
        f"""
        SELECT r.ad, r.aciklama, r.dil, f.fork
        FROM repolar AS r
        LEFT JOIN fotograflar AS f ON f.repo_ad = r.ad AND f.tarih = ?
        WHERE r.ad IN ({soru_isaretleri})
        """,
        (son, *adlar),
    ):
        ayrintilar[r["ad"]] = {
            "aciklama": r["aciklama"] or "",
            "dil": r["dil"] or "",
            "fork": r["fork"] or 0,
            "kategoriler": [],
            "gecmis": [],
        }

    for k in baglanti.execute(
        f"SELECT repo_ad, kategori FROM kategoriler WHERE repo_ad IN ({soru_isaretleri})",
        adlar,
    ):
        ayrintilar[k["repo_ad"]]["kategoriler"].append(k["kategori"])

    for f in baglanti.execute(
        f"""
        SELECT repo_ad, tarih, yildiz FROM fotograflar
        WHERE repo_ad IN ({soru_isaretleri}) AND tarih >= date(?, ?)
        ORDER BY tarih
        """,
        (*adlar, son, f"-{GECMIS_GUN} days"),
    ):
        ayrintilar[f["repo_ad"]]["gecmis"].append([f["tarih"], f["yildiz"]])

    return ayrintilar


def pano_verisi(baglanti: sqlite3.Connection) -> dict | None:
    """Sayfanın ihtiyaç duyduğu her şey, JSON'a çevrilebilir sade tiplerle."""
    son, onceki = son_iki_tarih(baglanti)
    if son is None:
        return None

    yukselen = yukselenler(baglanti, son, onceki, LISTE_ADEDI) if onceki else []
    yeniler = yeni_gorulenler(baglanti, son, LISTE_ADEDI)
    supheli = supheliler(baglanti, son)
    adlar = sorted({r["ad"] for r in [*yukselen, *yeniler, *supheli]})

    toplam_artis = 0
    if onceki:
        toplam_artis = baglanti.execute(
            """
            SELECT COALESCE(SUM(MAX(bugun.yildiz - once.yildiz, 0)), 0)
            FROM fotograflar AS bugun
            JOIN fotograflar AS once ON once.repo_ad = bugun.repo_ad AND once.tarih = ?
            WHERE bugun.tarih = ?
            """,
            (onceki, son),
        ).fetchone()[0]

    return {
        "tarih": son,
        "onceki_tarih": onceki,
        "takip_edilen": baglanti.execute(
            "SELECT COUNT(*) FROM fotograflar WHERE tarih = ?", (son,)
        ).fetchone()[0],
        "yeni_sayisi": baglanti.execute(
            "SELECT COUNT(*) FROM repolar WHERE ilk_gorulme = ?", (son,)
        ).fetchone()[0],
        "toplam_artis": toplam_artis,
        "kategoriler": [dict(k) for k in kategori_dagilimi(baglanti, son)],
        "yukselenler": [
            {"ad": r["ad"], "artis": r["artis"], "yuzde": r["yuzde"], "yildiz": r["yildiz"]}
            for r in yukselen
        ],
        "yeniler": [{"ad": r["ad"], "yildiz": r["yildiz"]} for r in yeniler],
        "supheliler": [dict(r) for r in supheli],
        "repolar": _repo_ayrintilari(baglanti, adlar, son),
    }


def html_olustur(veri: dict) -> str:
    """Şablonu okuyup veriyi içine yerleştirir."""
    sablon = files("devpulse").joinpath("pano.html").read_text(encoding="utf-8")
    # "</" dizisini kaçırıyoruz: bir repo açıklamasında "</script>" geçerse
    # tarayıcı script etiketini erken kapatıp sayfaya kod sokulmasına izin verirdi.
    veri_json = json.dumps(veri, ensure_ascii=False).replace("</", "<\\/")
    return sablon.replace(YER_TUTUCU, veri_json)


def main() -> None:
    ayristirici = argparse.ArgumentParser(description="DevPulse web panosunu üretir.")
    ayristirici.add_argument(
        "--cikti", type=Path, default=Path("site"), help="Klasör (varsayılan: site)"
    )
    argumanlar = ayristirici.parse_args()

    veri = pano_verisi(db.baglan())
    if veri is None:
        print("Veritabanında henüz ölçüm yok.")
        return

    argumanlar.cikti.mkdir(parents=True, exist_ok=True)
    hedef = argumanlar.cikti / "index.html"
    hedef.write_text(html_olustur(veri), encoding="utf-8")
    print(f"Pano yazıldı: {hedef}")


if __name__ == "__main__":
    main()

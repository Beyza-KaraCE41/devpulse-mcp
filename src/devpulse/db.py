"""SQLite veritabanı katmanı: tabloları oluşturur ve bağlantı verir."""

import json
import sqlite3

from devpulse.config import veritabani_yolu
from devpulse.kategoriler import kategorile

SEMA = """
CREATE TABLE IF NOT EXISTS repolar(
    ad           TEXT PRIMARY KEY,
    aciklama     TEXT NOT NULL DEFAULT '',
    dil          TEXT NOT NULL DEFAULT 'Bilinmiyor',
    konular      TEXT NOT NULL DEFAULT '[]',
    url          TEXT NOT NULL,
    ilk_gorulme  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fotograflar (
    repo_ad  TEXT NOT NULL REFERENCES repolar (ad),
    tarih    TEXT NOT NULL,
    yildiz   INTEGER NOT NULL,
    fork     INTEGER NOT NULL,
    PRIMARY KEY (repo_ad, tarih)
);

CREATE TABLE IF NOT EXISTS kategoriler(
    repo_ad   TEXT NOT NULL REFERENCES repolar (ad),
    kategori  TEXT NOT NULL,
    PRIMARY KEY (repo_ad, kategori)
);
"""


def baglan() -> sqlite3.Connection:
    """Veritabanına bağlanır. Dosya ya da tablolar yoksa oluşturur."""
    yol = veritabani_yolu()
    yol.parent.mkdir(parents=True, exist_ok=True)

    baglanti = sqlite3.connect(yol)
    baglanti.row_factory = sqlite3.Row
    baglanti.execute("PRAGMA foreign_keys= ON")
    baglanti.executescript(SEMA)
    return baglanti


def fotograf_kaydet(baglanti: sqlite3.Connection, repolar: list[dict], tarih: str) -> int:
    """Repoların o günkü yıldız ve fork sayılarını kaydeder.
    Aynı gün tekrar çalıştırılırsa yeni satır eklemez, o günün kaydını günceller.
    Kydedilen repo sayısını döndürür.
    """

    with baglanti:
        for repo in repolar:
            baglanti.execute(
                """
                INSERT INTO repolar (ad, aciklama, dil, konular, url, ilk_gorulme)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (ad) DO UPDATE SET
                    aciklama = excluded.aciklama,
                    dil= excluded.dil,
                    konular= excluded.konular,
                    url= excluded.url
                """,
                (
                    repo["ad"],
                    repo["aciklama"],
                    repo["dil"],
                    json.dumps(repo["konular"]),
                    repo["url"],
                    tarih,
                ),
            )
            # YENİ: Kategorileri her gün baştan hesapla (etiketler değişmiş olabilir)
            baglanti.execute("DELETE FROM kategoriler WHERE repo_ad = ?", (repo["ad"],))
            baglanti.executemany(
                "INSERT INTO kategoriler (repo_ad, kategori) VALUES (?, ?)",
                [(repo["ad"], k) for k in kategorile(repo["konular"], repo["aciklama"])],
            )
            baglanti.execute(
                """
                INSERT INTO fotograflar (repo_ad, tarih, yildiz, fork)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (repo_ad, tarih) DO UPDATE SET
                    yildiz= excluded.yildiz,
                    fork= excluded.fork
                """,
                (repo["ad"], tarih, repo["yildiz"], repo["fork"]),
            )
    return len(repolar)

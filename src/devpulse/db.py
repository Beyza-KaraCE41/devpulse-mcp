"""SQLite veritabanı katmanı: tabloları oluşturur ve bağlantı verir."""

import sqlite3

from devpulse.config import veritabani_yolu

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

"""pano.py için testler. Her test geçici, boş bir veritabanıyla çalışır."""

import json

import pytest

from devpulse import db
from devpulse.pano import YER_TUTUCU, html_olustur, pano_verisi


def _repo(ad, yildiz, fork=100, aciklama=""):
    return {
        "ad": ad,
        "aciklama": aciklama,
        "dil": "Python",
        "konular": [],
        "url": f"https://github.com/{ad}",
        "yildiz": yildiz,
        "fork": fork,
    }


@pytest.fixture
def baglanti(tmp_path, monkeypatch):
    monkeypatch.setenv("DEVPULSE_DB", str(tmp_path / "test.db"))
    b = db.baglan()
    yield b
    b.close()


def test_bos_veritabaninda_veri_yok(baglanti):
    assert pano_verisi(baglanti) is None


def test_yildiz_gecmisi_tarih_sirasiyla_gelir(baglanti):
    for gun, yildiz in [("2026-10-14", 100), ("2026-10-15", 150), ("2026-10-16", 230)]:
        db.fotograf_kaydet(baglanti, [_repo("a/b", yildiz)], gun)
    veri = pano_verisi(baglanti)
    assert veri["repolar"]["a/b"]["gecmis"] == [
        ["2026-10-14", 100],
        ["2026-10-15", 150],
        ["2026-10-16", 230],
    ]
    assert veri["toplam_artis"] == 80


def test_veri_json_olarak_yerlestirilir(baglanti):
    db.fotograf_kaydet(baglanti, [_repo("a/b", 100)], "2026-10-16")
    html = html_olustur(pano_verisi(baglanti))
    assert YER_TUTUCU not in html
    baslangic = html.index('type="application/json">') + len('type="application/json">')
    bitis = html.index("</script>", baslangic)
    assert json.loads(html[baslangic:bitis])["tarih"] == "2026-10-16"


def test_aciklamadaki_script_etiketi_sayfayi_bozamaz(baglanti):
    """Güvenlik: '</script>' içeren bir açıklama, veri bloğunu erken kapatmamalı."""
    zararli = _repo("kotu/repo", 100, aciklama="</script><script>alert(1)</script>")
    db.fotograf_kaydet(baglanti, [zararli], "2026-10-16")
    html = html_olustur(pano_verisi(baglanti))
    assert "</script><script>alert(1)" not in html

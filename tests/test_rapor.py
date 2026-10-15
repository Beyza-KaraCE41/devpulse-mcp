"""rapor.py için testler. Her test geçici, boş bir veritabanıyla çalışır."""

import pytest

from devpulse import db
from devpulse.kategoriler import DIGER
from devpulse.rapor import html_olustur, rapor_verisi, sayi_yaz, tarih_yaz, yuzde_yaz


def _repo(ad, yildiz, fork=100, aciklama="", konular=()):
    """GitHub'dan gelen veriye benzeyen sahte bir repo sözlüğü."""
    return {
        "ad": ad,
        "aciklama": aciklama,
        "dil": "Python",
        "konular": list(konular),
        "url": f"https://github.com/{ad}",
        "yildiz": yildiz,
        "fork": fork,
    }


@pytest.fixture
def baglanti(tmp_path, monkeypatch):
    """Her test için boş, geçici bir veritabanı. Gerçek verine dokunmaz."""
    monkeypatch.setenv("DEVPULSE_DB", str(tmp_path / "test.db"))
    b = db.baglan()
    yield b
    b.close()


def test_bos_veritabaninda_rapor_yok(baglanti):
    assert rapor_verisi(baglanti) is None


def test_tek_olcumde_yukselen_yok(baglanti):
    db.fotograf_kaydet(baglanti, [_repo("a/b", 1000)], "2026-10-15")
    veri = rapor_verisi(baglanti)
    assert veri["onceki_tarih"] is None
    assert veri["yukselenler"] == []


def test_yukselenler_artisa_gore_siralanir(baglanti):
    db.fotograf_kaydet(baglanti, [_repo("az/artan", 1000), _repo("cok/artan", 1000)], "2026-10-15")
    db.fotograf_kaydet(baglanti, [_repo("az/artan", 1100), _repo("cok/artan", 1500)], "2026-10-16")
    veri = rapor_verisi(baglanti)
    assert [r["ad"] for r in veri["yukselenler"]] == ["cok/artan", "az/artan"]
    assert veri["yukselenler"][0]["artis"] == 500
    assert veri["yukselenler"][0]["yuzde"] == 50.0


def test_yeni_gorulenler_sadece_son_olcumde_ilk_kez_gelenler(baglanti):
    db.fotograf_kaydet(baglanti, [_repo("eski/repo", 1000)], "2026-10-15")
    db.fotograf_kaydet(baglanti, [_repo("eski/repo", 1100), _repo("yeni/repo", 300)], "2026-10-16")
    veri = rapor_verisi(baglanti)
    assert [r["ad"] for r in veri["yeniler"]] == ["yeni/repo"]
    assert veri["yeni_sayisi"] == 1


@pytest.mark.parametrize(
    ("yildiz", "fork", "supheli_mi"),
    [
        (5000, 3, True),  # çok yıldız, neredeyse hiç fork yok
        (5000, 500, False),  # normal oran
        (300, 0, False),  # az yıldızlı repolara bakmıyoruz
    ],
)
def test_supheli_kurali(baglanti, yildiz, fork, supheli_mi):
    db.fotograf_kaydet(baglanti, [_repo("x/y", yildiz, fork)], "2026-10-16")
    veri = rapor_verisi(baglanti)
    assert (len(veri["supheliler"]) == 1) is supheli_mi


def test_diger_kategorisi_en_sonda(baglanti):
    repolar = [_repo(f"d/{i}", 100) for i in range(3)] + [_repo("a/llm", 100, konular=["llm"])]
    db.fotograf_kaydet(baglanti, repolar, "2026-10-16")
    kategoriler = [k["kategori"] for k in rapor_verisi(baglanti)["kategoriler"]]
    assert kategoriler[-1] == DIGER


def test_html_aciklamadaki_kodu_etkisiz_hale_getirir(baglanti):
    """Güvenlik: repo açıklamasını başkası yazıyor, HTML olarak çalışmamalı."""
    zararli = _repo("kotu/repo", 100, aciklama="<script>alert(1)</script>")
    db.fotograf_kaydet(baglanti, [zararli], "2026-10-16")
    html = html_olustur(rapor_verisi(baglanti))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_turkce_bicimlendirme():
    assert sayi_yaz(1234567) == "1.234.567"
    assert yuzde_yaz(12.5) == "%12,5"
    assert tarih_yaz("2026-10-16") == "16 Ekim 2026"

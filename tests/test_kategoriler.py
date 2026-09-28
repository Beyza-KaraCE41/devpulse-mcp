"""kategoriler.py için testler."""

import pytest

from devpulse.kategoriler import DIGER, kategorile


def test_etiketten_kategori_bulunur():
    assert kategorile(["llm"], "") == ["Yapay Zekâ"]


def test_etiket_buyuk_harfle_yazzilsa_da_bulunur():
    assert "Yapay Zekâ" in kategorile(["LLM"], "")


def test_birden_fazla_kategori_olabilir():
    sonuc = kategorile(["android", "llm"], "")
    assert "Yapay Zekâ" in sonuc
    assert "Mobil" in sonuc


def test_hicbirine_uymazsa_diger():
    assert kategorile([], "A small, fast browser for macOS") == [DIGER]


def test_aciklamadan_kategori_bulunur():
    assert "Yapay Zekâ" in kategorile([], "A coding agent  harness")


@pytest.mark.parametrize(
    "aciklama",
    [
        "A tool to maintain your dotfiles",  # m-AI-ntain
        "Fast email client",  # em-AI-l
        "Rain radar for your city",  # r-AI-n
    ],
)
def test_kelime_icinde_gecen_ai_yanlis_eslesmez(aciklama):
    """Hata kaydı: "ai" başka bir kelimenin içinde geçince Yapay Zekâ sayılmamalı."""
    assert "Yapay Zekâ" not in kategorile([], aciklama)


def test_tireli_etiket_aciklamada_bosluklu_yazilsa_da_bulunur():
    assert "Yapay Zekâ" in kategorile([], "Fast machine learning on Apple  silicon")


def test_repo_adina_da_bakilir():
    assert "Yapay Zekâ" in kategorile([], "", ad="volotat/mini-AGI")


@pytest.mark.parametrize(
    ("etiket", "beklenen"),
    [
        ("diffusion", "Yapay Zekâ"),
        ("graphql", "API/Backend"),
        ("nextjs", "Web"),
        ("godot", "Oyun"),
    ],
)
def test_yazim_hatasi_yapilmis_kelimeler(etiket, beklenen):
    """Hata kaydı: bu kelimeler bir kez yanlış yazılmıştı (diffision, graphl, next.js)."""
    assert beklenen in kategorile([etiket], "")


@pytest.mark.xfail(reason="Bilinen sınırlama: kurallar olumsuz cümleleri anlamıyor")
def test_olumsuz_cumle_kategori_vermemeli():
    assert "API/Backend" not in kategorile([], "No text generation, PyTorch, or cloud API.")

"""Günlük bülten: veritabanındaki son ölçümden HTML e-posta raporu üretir ve gönderir.

Önizleme:   devpulse-rapor --cikti bulten.html
Gönderme:   devpulse-rapor --gonder   (SMTP bilgileri ortam değişkenlerinden okunur)
"""

import argparse
import os
import smtplib
import sqlite3
from datetime import date
from email.message import EmailMessage
from html import escape
from pathlib import Path

from devpulse import db
from devpulse.kategoriler import DIGER

ADET = 5  # Her bölümde en fazla kaç repo gösterilsin
SUPHELI_MIN_YILDIZ = 500  # Bundan az yıldızlı repolara şüpheli demiyoruz
SUPHELI_FORK_ORANI = 0.01  # 100 yıldıza 1 fork'tan az düşüyorsa şüpheli
ACIKLAMA_SINIRI = 110  # Açıklamalar bu uzunlukta kesilir

AYLAR = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]  # fmt: skip


# ---------- 1) Veri sorguları ----------


def son_iki_tarih(baglanti: sqlite3.Connection) -> tuple[str | None, str | None]:
    """En son ölçüm tarihini ve ondan bir önceki ölçüm tarihini döndürür."""
    satirlar = baglanti.execute(
        "SELECT DISTINCT tarih FROM fotograflar ORDER BY tarih DESC LIMIT 2"
    ).fetchall()
    tarihler = [satir["tarih"] for satir in satirlar]
    son = tarihler[0] if len(tarihler) > 0 else None
    onceki = tarihler[1] if len(tarihler) > 1 else None
    return son, onceki


def yukselenler(
    baglanti: sqlite3.Connection, son: str, onceki: str, adet: int = ADET
) -> list[sqlite3.Row]:
    """İki ölçüm arasında en çok yıldız kazanan repolar."""
    return baglanti.execute(
        """
        SELECT bugun.repo_ad                 AS ad,
               r.aciklama                    AS aciklama,
               bugun.yildiz                  AS yildiz,
               bugun.yildiz - once.yildiz    AS artis,
               ROUND(100.0 * (bugun.yildiz - once.yildiz) / MAX(once.yildiz, 1), 1) AS yuzde
        FROM fotograflar AS bugun
        JOIN fotograflar AS once
          ON once.repo_ad = bugun.repo_ad AND once.tarih = ?
        JOIN repolar AS r ON r.ad = bugun.repo_ad
        WHERE bugun.tarih = ? AND bugun.yildiz > once.yildiz
        ORDER BY artis DESC
        LIMIT ?
        """,
        (onceki, son, adet),
    ).fetchall()


def kategori_dagilimi(baglanti: sqlite3.Connection, son: str) -> list[sqlite3.Row]:
    """Son ölçümdeki repoların kategorilere göre sayısı ve toplam yıldızı. "Diğer" en sonda."""
    return baglanti.execute(
        """
        SELECT k.kategori       AS kategori,
               COUNT(*)         AS repo_sayisi,
               SUM(f.yildiz)    AS toplam_yildiz
        FROM kategoriler AS k
        JOIN fotograflar AS f ON f.repo_ad = k.repo_ad AND f.tarih = ?
        GROUP BY k.kategori
        ORDER BY k.kategori = ?, repo_sayisi DESC, toplam_yildiz DESC
        """,
        (son, DIGER),
    ).fetchall()


def yeni_gorulenler(baglanti: sqlite3.Connection, son: str, adet: int = ADET) -> list[sqlite3.Row]:
    """İlk kez son ölçümde görülen repolar, en çok yıldızlıdan başlayarak."""
    return baglanti.execute(
        """
        SELECT r.ad, r.aciklama, r.dil, f.yildiz
        FROM repolar AS r
        JOIN fotograflar AS f ON f.repo_ad = r.ad AND f.tarih = ?
        WHERE r.ilk_gorulme = ?
        ORDER BY f.yildiz DESC
        LIMIT ?
        """,
        (son, son, adet),
    ).fetchall()


def supheliler(baglanti: sqlite3.Connection, son: str, adet: int = ADET) -> list[sqlite3.Row]:
    """Çok yıldızı olup neredeyse hiç fork'u olmayan repolar (sahte yıldız şüphesi)."""
    return baglanti.execute(
        """
        SELECT repo_ad AS ad, yildiz, fork
        FROM fotograflar
        WHERE tarih = ? AND yildiz >= ? AND fork < yildiz * ?
        ORDER BY yildiz DESC
        LIMIT ?
        """,
        (son, SUPHELI_MIN_YILDIZ, SUPHELI_FORK_ORANI, adet),
    ).fetchall()


def rapor_verisi(baglanti: sqlite3.Connection) -> dict | None:
    """Raporun ihtiyaç duyduğu her şeyi tek bir sözlükte toplar. Veri yoksa None."""
    son, onceki = son_iki_tarih(baglanti)
    if son is None:
        return None
    takip_edilen = baglanti.execute(
        "SELECT COUNT(*) FROM fotograflar WHERE tarih = ?", (son,)
    ).fetchone()[0]
    yeni_sayisi = baglanti.execute(
        "SELECT COUNT(*) FROM repolar WHERE ilk_gorulme = ?", (son,)
    ).fetchone()[0]
    return {
        "tarih": son,
        "onceki_tarih": onceki,
        "takip_edilen": takip_edilen,
        "yeni_sayisi": yeni_sayisi,
        "yukselenler": yukselenler(baglanti, son, onceki) if onceki else [],
        "kategoriler": kategori_dagilimi(baglanti, son),
        "yeniler": yeni_gorulenler(baglanti, son),
        "supheliler": supheliler(baglanti, son),
    }


# ---------- 2) Biçimlendirme yardımcıları ----------


def sayi_yaz(n: int) -> str:
    """12345 -> "12.345" (Türkçe binlik ayracı)."""
    return f"{n:,}".replace(",", ".")


def yuzde_yaz(oran: float) -> str:
    """12.5 -> "%12,5" (Türkçe ondalık virgül)."""
    return "%" + str(oran).replace(".", ",")


def tarih_yaz(iso_tarih: str) -> str:
    """2026-10-16 -> 16 Ekim 2026."""
    gun = date.fromisoformat(iso_tarih)
    return f"{gun.day} {AYLAR[gun.month - 1]} {gun.year}"


def kisalt(metin: str | None, sinir: int = ACIKLAMA_SINIRI) -> str:
    """Uzun açıklamaları keser; boşsa "Açıklama yok" döndürür."""
    metin = (metin or "").strip()
    if not metin:
        return "Açıklama yok"
    return metin if len(metin) <= sinir else metin[: sinir - 1].rstrip() + "…"


# ---------- 3) Düz metin sürümü (e-posta istemcisi HTML göstermezse) ----------


def metin_olustur(veri: dict, pano_url: str | None = None) -> str:
    satirlar = [f"DevPulse günlük bülten · {tarih_yaz(veri['tarih'])}", ""]
    satirlar.append("EN HIZLI YÜKSELENLER")
    for r in veri["yukselenler"]:
        satirlar.append(f"  {r['ad']}  +{sayi_yaz(r['artis'])} ({yuzde_yaz(r['yuzde'])})")
    if not veri["yukselenler"]:
        satirlar.append("  Karşılaştırılacak veri yok.")
    satirlar += ["", "KATEGORİLER"]
    for k in veri["kategoriler"]:
        satirlar.append(f"  {k['kategori']}: {k['repo_sayisi']} repo")
    satirlar += ["", "İLK KEZ GÖRÜLENLER"]
    for r in veri["yeniler"]:
        satirlar.append(f"  {r['ad']} ({sayi_yaz(r['yildiz'])} yıldız)")
    satirlar += ["", "KONTROL ETMEDEN İNDİRME"]
    for r in veri["supheliler"]:
        satirlar.append(f"  {r['ad']}: {sayi_yaz(r['yildiz'])} yıldız, {r['fork']} fork")
    if pano_url:
        satirlar += ["", f"Etkileşimli pano: {pano_url}"]
    return "\n".join(satirlar) + "\n"


# ---------- 4) HTML sürümü ----------
# E-posta programları modern CSS'i desteklemez: düzen tablolarla,
# stiller her etiketin içinde (inline) yazılır. Harici dosya, script, font yoktur.

ARKA = "#f3f4f6"
KART = "#ffffff"
CERCEVE = "#e5e7eb"
AYRAC = "#f0f1f3"
METIN = "#111827"
SOLUK = "#6b7280"
VURGU = "#1d4ed8"
ARTIS = "#047857"
UYARI = "#b45309"
YAZI_TIPI = "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"


def _repo_satiri(ad: str, alt: str, sag_ust: str, sag_alt: str = "", renk: str = METIN) -> str:
    """Kart içinde tek bir repo: solda ad + açıklama, sağda sayı."""
    ad_e = escape(ad)
    return f"""
<tr><td style="padding:12px 20px;border-top:1px solid {AYRAC};">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
    <td style="vertical-align:top;">
      <a href="https://github.com/{ad_e}" style="color:{VURGU};text-decoration:none;font-weight:600;font-size:15px;">{ad_e}</a>
      <div style="color:{SOLUK};font-size:13px;line-height:1.45;margin-top:2px;">{escape(alt)}</div>
    </td>
    <td style="vertical-align:top;text-align:right;white-space:nowrap;padding-left:16px;">
      <div style="font-weight:600;font-size:15px;color:{renk};">{escape(sag_ust)}</div>
      <div style="color:{SOLUK};font-size:12px;margin-top:2px;">{escape(sag_alt)}</div>
    </td>
  </tr></table>
</td></tr>"""


def _bos_satir(metin: str) -> str:
    return f"""
<tr><td style="padding:12px 20px 16px;border-top:1px solid {AYRAC};color:{SOLUK};font-size:14px;">{escape(metin)}</td></tr>"""


def _bolum(baslik: str, alt_baslik: str, govde: str) -> str:
    """Başlıklı beyaz bir kart."""
    alt = (
        f'<div style="color:{SOLUK};font-size:13px;margin-top:4px;">{escape(alt_baslik)}</div>'
        if alt_baslik
        else ""
    )
    return f"""
<tr><td style="padding-top:16px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{KART};border:1px solid {CERCEVE};border-radius:8px;">
    <tr><td style="padding:18px 20px 12px;">
      <div style="font-size:12px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;color:{SOLUK};">{escape(baslik)}</div>
      {alt}
    </td></tr>
    {govde}
  </table>
</td></tr>"""


def _ozet_kutusu(etiket: str, deger: str) -> str:
    return f"""
<td width="33%" style="padding:0 4px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{KART};border:1px solid {CERCEVE};border-radius:8px;">
    <tr><td style="padding:14px 16px;">
      <div style="color:{SOLUK};font-size:12px;">{escape(etiket)}</div>
      <div style="color:{METIN};font-size:22px;font-weight:600;margin-top:4px;">{escape(deger)}</div>
    </td></tr>
  </table>
</td>"""


def _kategori_satiri(ad: str, repo_sayisi: int, toplam_yildiz: int, oran: float) -> str:
    """Kategori adı, sayılar ve oranı gösteren ince bir çubuk."""
    genislik = max(2, round(oran * 100))
    return f"""
<tr><td style="padding:10px 20px;border-top:1px solid {AYRAC};">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
    <td style="font-size:14px;color:{METIN};">{escape(ad)}</td>
    <td style="font-size:13px;color:{SOLUK};text-align:right;white-space:nowrap;">{repo_sayisi} repo · {sayi_yaz(toplam_yildiz)} yıldız</td>
  </tr></table>
  <div style="background:{AYRAC};height:6px;border-radius:3px;margin-top:6px;">
    <div style="background:{VURGU};width:{genislik}%;height:6px;border-radius:3px;"></div>
  </div>
</td></tr>"""


def _pano_butonu(pano_url: str | None) -> str:
    """Web panosuna giden buton. Adres verilmemişse hiçbir şey eklenmez."""
    if not pano_url:
        return ""
    return f"""
<tr><td align="center" style="padding-top:24px;">
  <a href="{escape(pano_url)}" style="display:inline-block;background:{VURGU};color:#ffffff;text-decoration:none;font-weight:600;font-size:15px;padding:12px 24px;border-radius:8px;">Etkileşimli panoyu aç</a>
  <div style="color:{SOLUK};font-size:12px;margin-top:8px;">Grafikler, 30 günlük yıldız geçmişi ve kategori filtresi</div>
</td></tr>"""


def html_olustur(veri: dict, pano_url: str | None = None) -> str:
    tarih = tarih_yaz(veri["tarih"])
    onceki = tarih_yaz(veri["onceki_tarih"]) if veri["onceki_tarih"] else "Yok"

    # Yükselenler
    if not veri["onceki_tarih"]:
        yukselen_govde = _bos_satir("Karşılaştırma için önceki bir ölçüm yok.")
    elif not veri["yukselenler"]:
        yukselen_govde = _bos_satir("Bu aralıkta yıldız kazanan repo yok.")
    else:
        yukselen_govde = "".join(
            _repo_satiri(
                r["ad"],
                kisalt(r["aciklama"]),
                f"+{sayi_yaz(r['artis'])}",
                f"{yuzde_yaz(r['yuzde'])} · {sayi_yaz(r['yildiz'])} yıldız",
                renk=ARTIS,
            )
            for r in veri["yukselenler"]
        )

    # Kategoriler
    en_cok = max((k["repo_sayisi"] for k in veri["kategoriler"]), default=1)
    kategori_govde = "".join(
        _kategori_satiri(
            k["kategori"], k["repo_sayisi"], k["toplam_yildiz"], k["repo_sayisi"] / en_cok
        )
        for k in veri["kategoriler"]
    ) or _bos_satir("Kategori verisi yok.")

    # Yeni görülenler
    yeni_govde = "".join(
        _repo_satiri(r["ad"], kisalt(r["aciklama"]), sayi_yaz(r["yildiz"]), r["dil"] or "")
        for r in veri["yeniler"]
    ) or _bos_satir("Bugün ilk kez görülen repo yok.")

    # Şüpheliler
    supheli_govde = "".join(
        _repo_satiri(
            r["ad"],
            "Yıldız sayısına göre fork sayısı çok düşük.",
            f"{sayi_yaz(r['yildiz'])} yıldız",
            f"{r['fork']} fork",
            renk=UYARI,
        )
        for r in veri["supheliler"]
    ) or _bos_satir("Şüpheli görünen repo yok.")

    aralik = f"{onceki} → {tarih}" if veri["onceki_tarih"] else ""

    return f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DevPulse · {escape(tarih)}</title>
</head>
<body style="margin:0;padding:0;background:{ARKA};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{ARKA};">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;font-family:{YAZI_TIPI};color:{METIN};">

  <tr><td style="padding:0 4px 8px;">
    <div style="font-size:13px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:{VURGU};">DevPulse</div>
    <div style="font-size:24px;font-weight:600;margin-top:4px;">Günlük bülten</div>
    <div style="font-size:14px;color:{SOLUK};margin-top:2px;">{escape(tarih)}</div>
  </td></tr>

  <tr><td style="padding-top:12px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      {_ozet_kutusu("Takip edilen", sayi_yaz(veri["takip_edilen"]))}
      {_ozet_kutusu("Yeni", sayi_yaz(veri["yeni_sayisi"]))}
      {_ozet_kutusu("Şüpheli", sayi_yaz(len(veri["supheliler"])))}
    </tr></table>
  </td></tr>

  {_bolum("En hızlı yükselenler", aralik, yukselen_govde)}
  {_bolum("Kategoriler", "Son ölçümdeki repoların dağılımı", kategori_govde)}
  {_bolum("İlk kez görülenler", "", yeni_govde)}
  {_bolum("Kontrol etmeden indirme", "Çok yıldızlı ama neredeyse hiç fork'u olmayan repolar. Sahte yıldız olabilir.", supheli_govde)}

  {_pano_butonu(pano_url)}

  <tr><td style="padding:20px 4px 0;font-size:12px;color:{SOLUK};line-height:1.5;">
    Bu e-posta GitHub Actions tarafından her sabah otomatik gönderilir. Veri kaynağı: GitHub API.
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>
"""


# ---------- 5) Gönderme ----------


def eposta_gonder(konu: str, html_icerik: str, duz_metin: str) -> None:
    """Gmail SMTP üzerinden gönderir. Bilgiler ortam değişkenlerinden okunur."""
    kullanici = os.getenv("DEVPULSE_SMTP_KULLANICI", "").strip()
    sifre = os.getenv("DEVPULSE_SMTP_SIFRE", "").strip()
    alici = os.getenv("DEVPULSE_ALICI", "").strip() or kullanici
    if not kullanici or not sifre:
        raise SystemExit("DEVPULSE_SMTP_KULLANICI ve DEVPULSE_SMTP_SIFRE tanımlı değil.")

    mesaj = EmailMessage()
    mesaj["Subject"] = konu
    mesaj["From"] = f"DevPulse <{kullanici}>"
    mesaj["To"] = alici
    mesaj.set_content(duz_metin)  # HTML gösteremeyen programlar için
    mesaj.add_alternative(html_icerik, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as sunucu:
        sunucu.login(kullanici, sifre)
        sunucu.send_message(mesaj)


def main() -> None:
    ayristirici = argparse.ArgumentParser(description="DevPulse günlük bülteni.")
    ayristirici.add_argument("--cikti", type=Path, help="HTML'i bu dosyaya yaz (ör. bulten.html)")
    ayristirici.add_argument("--gonder", action="store_true", help="Bülteni e-posta ile gönder")
    argumanlar = ayristirici.parse_args()

    veri = rapor_verisi(db.baglan())
    if veri is None:
        print("Veritabanında henüz ölçüm yok.")
        return

    pano_url = os.getenv("DEVPULSE_PANO_URL", "").strip() or None
    html_icerik = html_olustur(veri, pano_url)
    if argumanlar.cikti:
        argumanlar.cikti.write_text(html_icerik, encoding="utf-8")
        print(f"HTML yazıldı: {argumanlar.cikti}")
    if argumanlar.gonder:
        konu = f"DevPulse bülteni · {tarih_yaz(veri['tarih'])}"
        eposta_gonder(konu, html_icerik, metin_olustur(veri, pano_url))
        print("E-posta gönderildi.")
    if not argumanlar.cikti and not argumanlar.gonder:
        print(metin_olustur(veri))


if __name__ == "__main__":
    main()

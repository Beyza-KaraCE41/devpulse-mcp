"""DevPulse MCP sunucusu: Claude'un veritabanındaki verilere erişmesini sağlar."""

import logging
import sqlite3
from contextlib import closing

from mcp.server.mcpserver import MCPServer

from devpulse.db import baglan
from devpulse.kategoriler import DIGER, KATEGORILER

mcp = MCPServer("devpulse")

TUM_KATEGORILER = [*KATEGORILER, DIGER]
_TR_HARFLER = str.maketrans("âçğıöşü", "acgiosu")


def _sadelestir(metin: str) -> str:
    """Karşılaştırma için metni sadeleştirir: "Yapay Zekâ" -> "yapayzeka"."""
    return metin.lower().translate(_TR_HARFLER).replace(" ", "").replace("/", "")


def _kategori_bul(istenen: str) -> str | None:
    """Claude'un yazdığı kategori adını ("yapay zeka", "api") gerçek adla eşleştirir."""
    aranan = _sadelestir(istenen)
    for kategori in TUM_KATEGORILER:
        if _sadelestir(kategori).startswith(aranan):
            return kategori
    return None


def _son_tarih(baglanti: sqlite3.Connection) -> str | None:
    """Veritabanındaki en son fotoğrafın tarihi."""
    return baglanti.execute("SELECT MAX(tarih) FROM fotograflar").fetchone()[0]


@mcp.tool()
def populer_repolar(adet: int = 10, dil: str | None = None, kategori: str | None = None) -> str:
    """Son toplanan veriye göre en çok yıldızı olan yeni GitHub repolarını listeler.

    Veri, son 7 gün içinde oluşturulmuş repolardan günde bir kez toplanır.

    Args:
        adet: Kaç repo listeleneceği (1-50, varsayılan 10).
        dil: İsteğe bağlı programlama dili filtresi, örneğin "Python" veya "TypeScript".
        kategori: İsteğe bağlı kategori filtresi. Geçerli değerler: Yapay Zekâ, Mobil, Web,
            API/Backend, DevOps, Veri, Güvenlik, Geliştirici Araçları, Oyun, Diğer.
    """
    adet = max(1, min(adet, 50))

    kategori_adi = None
    if kategori:
        kategori_adi = _kategori_bul(kategori)
        if kategori_adi is None:
            return f"'{kategori}' diye bir kategori yok. Geçerli: {', '.join(TUM_KATEGORILER)}"

    with closing(baglan()) as baglanti:
        son_tarih = _son_tarih(baglanti)
        if son_tarih is None:
            return "Veritabanında henüz veri yok. Önce veri toplanması gerekiyor."

        sorgu = """
            SELECT r.ad, r.aciklama, r.dil, r.url, f.yildiz, f.fork,
                   (SELECT GROUP_CONCAT(k.kategori, ', ')
                    FROM kategoriler AS k WHERE k.repo_ad = r.ad) AS kategoriler
            FROM fotograflar AS f
            JOIN repolar AS r ON r.ad = f.repo_ad
            WHERE f.tarih = ?
        """
        degerler: list = [son_tarih]
        if dil:
            sorgu += " AND LOWER(r.dil) = LOWER(?)"
            degerler.append(dil)
        if kategori_adi:
            sorgu += " AND r.ad IN (SELECT repo_ad FROM kategoriler WHERE kategori = ?)"
            degerler.append(kategori_adi)
        sorgu += " ORDER BY f.yildiz DESC LIMIT ?"
        degerler.append(adet)

        satirlar = baglanti.execute(sorgu, degerler).fetchall()

    if not satirlar:
        return f"{son_tarih} tarihli veride bu filtrelere uyan repo bulunamadı."

    cikti = [f"Veri tarihi: {son_tarih} (UTC). En popüler {len(satirlar)} repo:"]
    for sira, s in enumerate(satirlar, start=1):
        cikti.append(
            f"{sira}. {s['ad']} ({s['dil']}) - {s['yildiz']} yıldız, {s['fork']} fork\n"
            f"   Kategori: {s['kategoriler']}\n"
            f"   {s['aciklama'] or 'Açıklama yok'}\n"
            f"   {s['url']}"
        )
    return "\n".join(cikti)


@mcp.tool()
def kategori_ozeti() -> str:
    """Son toplanan veride her kategoride kaç yeni popüler repo olduğunu ve öne çıkanları özetler.

    Hangi teknoloji alanlarında hareket olduğunu görmek için kullanılır.
    Bir repo birden fazla kategoride olabilir.
    """
    with closing(baglan()) as baglanti:
        son_tarih = _son_tarih(baglanti)
        if son_tarih is None:
            return "Veritabanında henüz veri yok. Önce veri toplanması gerekiyor."

        satirlar = baglanti.execute(
            """
            SELECT k.kategori, COUNT(*) AS adet, SUM(f.yildiz) AS toplam_yildiz
            FROM kategoriler AS k
            JOIN fotograflar AS f ON f.repo_ad = k.repo_ad AND f.tarih = ?
            GROUP BY k.kategori
            ORDER BY adet DESC
            """,
            (son_tarih,),
        ).fetchall()

        cikti = [f"Veri tarihi: {son_tarih} (UTC). Kategorilere göre yeni popüler repolar:"]
        for s in satirlar:
            one_cikanlar = baglanti.execute(
                """
                SELECT f.repo_ad FROM fotograflar AS f
                JOIN kategoriler AS k ON k.repo_ad = f.repo_ad
                WHERE f.tarih = ? AND k.kategori = ?
                ORDER BY f.yildiz DESC LIMIT 3
                """,
                (son_tarih, s["kategori"]),
            ).fetchall()
            isimler = ", ".join(r["repo_ad"] for r in one_cikanlar)
            cikti.append(
                f"- {s['kategori']}: {s['adet']} repo, toplam {s['toplam_yildiz']} yıldız. "
                f"Öne çıkanlar: {isimler}"
            )
    return "\n".join(cikti)


@mcp.tool()
def hizla_yukselenler(gun: int = 1, adet: int = 10, kategori: str | None = None) -> str:
    """Belirli bir sürede en çok yıldız kazanan repoları listeler (gerçek trend).

    En son fotoğraf ile `gun` gün önceki fotoğraf karşılaştırılır. Sadece iki tarihte de
    kaydı olan repolar hesaba katılır.

    Args:
        gun: Kaç gün öncesiyle karşılaştırılacağı (1-30, varsayılan 1 yani dünden bugüne).
        adet: Kaç repo listeleneceği (1-50, varsayılan 10).
        kategori: İsteğe bağlı kategori filtresi (populer_repolar ile aynı değerler).
    """
    gun = max(1, min(gun, 30))
    adet = max(1, min(adet, 50))

    kategori_adi = None
    if kategori:
        kategori_adi = _kategori_bul(kategori)
        if kategori_adi is None:
            return f"'{kategori}' diye bir kategori yok. Geçerli: {', '.join(TUM_KATEGORILER)}"

    with closing(baglan()) as baglanti:
        son_tarih = _son_tarih(baglanti)
        if son_tarih is None:
            return "Veritabanında henüz veri yok. Önce veri toplanması gerekiyor."

        onceki_tarih = baglanti.execute(
            "SELECT MAX(tarih) FROM fotograflar WHERE tarih <= date(?, ?)",
            (son_tarih, f"-{gun} days"),
        ).fetchone()[0]
        if onceki_tarih is None:
            return (
                f"Trend için yeterli geçmiş yok. En son veri {son_tarih}, "
                f"ama {gun} gün öncesine ait kayıt bulunmuyor. Veri her gün toplandıkça "
                "karşılaştırma mümkün olacak."
            )

        sorgu = """
            SELECT r.ad, r.aciklama, r.url, bugun.yildiz,
                   bugun.yildiz - once.yildiz AS artis, once.yildiz AS eski_yildiz
            FROM fotograflar AS bugun
            JOIN fotograflar AS once ON once.repo_ad = bugun.repo_ad AND once.tarih = ?
            JOIN repolar AS r ON r.ad = bugun.repo_ad
            WHERE bugun.tarih = ?
        """
        degerler: list = [onceki_tarih, son_tarih]
        if kategori_adi:
            sorgu += " AND r.ad IN (SELECT repo_ad FROM kategoriler WHERE kategori = ?)"
            degerler.append(kategori_adi)
        sorgu += " ORDER BY artis DESC LIMIT ?"
        degerler.append(adet)

        satirlar = baglanti.execute(sorgu, degerler).fetchall()

    if not satirlar:
        return f"{onceki_tarih} ile {son_tarih} arasında karşılaştırılabilir repo bulunamadı."

    cikti = [f"{onceki_tarih} → {son_tarih} arasında en çok yıldız kazanan {len(satirlar)} repo:"]
    for sira, s in enumerate(satirlar, start=1):
        yuzde = 100 * s["artis"] / s["eski_yildiz"] if s["eski_yildiz"] else 0
        cikti.append(
            f"{sira}. {s['ad']}: +{s['artis']} yıldız (%{yuzde:.1f} artış, şu an {s['yildiz']})\n"
            f"   {s['aciklama'] or 'Açıklama yok'}\n"
            f"   {s['url']}"
        )
    return "\n".join(cikti)


def main() -> None:
    """Sunucuyu başlatır."""
    # Loglar stderr'e yazılır. stdout, Claude ile MCP konuşmasına ayrılmıştır.
    logging.basicConfig(level=logging.INFO)
    mcp.run()


if __name__ == "__main__":
    main()

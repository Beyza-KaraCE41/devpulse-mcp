"""DevPulse MCP sunucusu: Claude'un veritabanındaki verilere erişmesini sağlar."""

import logging
from contextlib import closing

from mcp.server.mcpserver import MCPServer

from devpulse.db import baglan

mcp = MCPServer("devpulse")


@mcp.tool()
def populer_repolar(adet: int = 10, dil: str | None = None) -> str:
    """Son toplanan veriye göre en çok yıldızı olan yeni Github repolarını listeler.
    Veri, son 7 gün içinde oluşturulmuş repolardan günde bir kez toplanır.

    Args:
        adet: Kaç repo listeleneceği (1-50, varsayılan 10).
        dil: İsteğe bağlı programlama dili filtresi, örneğin "Python" veya "Typescript".
    """
    adet = max(1, min(adet, 50))

    with closing(baglan()) as baglanti:
        son_tarih = baglanti.execute("SELECT MAX(tarih) FROM fotograflar").fetchone()[0]
        if son_tarih is None:
            return "Veritabanında henüz veri yok. Önce veri toplanması gerekiyor."

        sorgu = """
            SELECT r.ad, r.aciklama, r.dil, r.url, f.yildiz, f.fork
            FROM fotograflar AS f
            JOIN repolar AS r ON r.ad = f.repo_ad
            WHERE f.tarih = ?
        """
        degerler: list = [son_tarih]
        if dil:
            sorgu += "AND LOWER(r.dil) = LOWER(?)"
            degerler.append(dil)
        sorgu += "ORDER BY f.yildiz DESC LIMIT ?"
        degerler.append(adet)

        satirlar = baglanti.execute(sorgu, degerler).fetchall()

    if not satirlar:
        return f"{son_tarih} tarihli veride '{dil}' dilinde repo bulunamadı."

    cikti = [f"Veri tarihi: {son_tarih} (UTC). En popüler {len(satirlar)} repo:"]
    for sira, s in enumerate(satirlar, start=1):
        cikti.append(
            f"{sira}. {s['ad']} ({s['dil']}) - {s['yildiz']} yıldız, {s['fork']} fork\n"
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

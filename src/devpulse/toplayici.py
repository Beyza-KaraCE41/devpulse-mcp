"""Günlük veri toplayıcı: Github'dan veri çekip veritabanına fotoğraf olarak kaydeder."""

import logging
import sys
from contextlib import closing
from datetime import UTC, datetime

import httpx

from devpulse import github
from devpulse.db import baglan, fotograf_kaydet, takip_edilen_repolar

log = logging.getLogger(__name__)

YENI_REPO_ADEDI = 100  # her gün son 7 günün en popüler kaç reposu çekilecek
TAKIP_SURESI_GUN = 14  # bir repo ilk görüldükten sonra kaç gün daha takip edilecek


def _eski_repolari_getir(adlar: list[str]) -> list[dict]:
    """Aramadan çıkmış ama takip ettiğimiz repoların güncel bilgilerini tek tek çeker."""
    repolar = []
    for ad in adlar:
        try:
            repolar.append(github.repo_getir(ad))
        except httpx.HTTPStatusError as hata:
            if hata.response.status_code != 404:
                raise
            log.warning("%s bulunamadı (silinmiş ya da gizlenmiş), atlanıyor.", ad)
    return repolar


def topla() -> int:
    """Bugünün fotoğrafını çekip kaydeder. Kaydedilen repo sayısını döndürür."""
    bugun = datetime.now(UTC).date().isoformat()

    with closing(baglan()) as baglanti:
        yeni = github.yeni_populer_repolar(gun=7, adet=YENI_REPO_ADEDI)
        log.info("Son 7 günün en popüler %d reposu çekildi.", len(yeni))

        aramada_olanlar = {repo["ad"] for repo in yeni}
        takip = takip_edilen_repolar(baglanti, bugun, TAKIP_SURESI_GUN)
        disarida_kalanlar = [ad for ad in takip if ad not in aramada_olanlar]
        log.info("Aramadan çıkmış %d repo ayrıca güncelleniyor.", len(disarida_kalanlar))
        eski = _eski_repolari_getir(disarida_kalanlar)

        return fotograf_kaydet(baglanti, yeni + eski, bugun)


def main() -> None:
    """Komut satırından çalıştırılır: `devpulse-topla`."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        adet = topla()
    except github.GitHubLimitError as hata:
        log.error("%s", hata)
        sys.exit(1)
    log.info("Tamamlandı: %d repo kaydedildi.", adet)


if __name__ == "__main__":
    main()

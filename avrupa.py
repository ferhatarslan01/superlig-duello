"""Avrupa kupalari (Sampiyonlar Ligi, Avrupa Ligi, Konferans Ligi) liderleri: gol, asist, kartlar.

Veri: ESPN core API 'leaders' (ucretsiz, anahtarsiz). Her lider icin oyuncu/takim/istatistik baglantilari
cozulur. Kartlar kart_lider.ciz ile cizilir (Super Lig liderleri ile ayni tasarim).
"""
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

SEZON = 2026
CORE = "https://sports.core.api.espn.com/v2/sports/soccer/leagues"
LIGLER = {  # anahtar: (espn kodu, kart basligi, hashtag)
    "champions": ("uefa.champions", "ŞAMPİYONLAR LİGİ", "#ŞampiyonlarLigi #UCL"),
    "europa": ("uefa.europa", "AVRUPA LİGİ", "#AvrupaLigi #UEL"),
    "conf": ("uefa.europa.conf", "KONFERANS LİGİ", "#KonferansLigi #UECL"),
}
ILK_N = 5
_ONBELLEK = {}


def _get(url, deneme=3):
    url = url.replace("http://", "https://")
    if url in _ONBELLEK:
        return _ONBELLEK[url]
    for i in range(deneme):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                _ONBELLEK[url] = json.load(r)
                return _ONBELLEK[url]
        except Exception:
            if i == deneme - 1:
                raise
            time.sleep(2 * (i + 1))


def _oyuncu(item):
    """Lider satirindan {ad, takim, yas, st} uretir (istatistik baglantisindan)."""
    a = _get(item["athlete"]["$ref"])
    t = _get(item["team"]["$ref"])
    try:
        r = _get(item["statistics"]["$ref"])
        st = {s["name"]: s["value"] for c in r["splits"]["categories"] for s in c["stats"]}
    except Exception:
        st = {}
    return {"id": a.get("id"), "ad": a.get("displayName") or a.get("fullName"), "takim": t.get("displayName"),
            "yas": a.get("age"), "st": st}


def _kategori(lig_kodu, ad):
    yol = f"{CORE}/{lig_kodu}/seasons/{SEZON}/types/1/leaders"
    for c in _get(yol).get("categories", []):
        if c["name"] == ad:
            return c.get("leaders", [])
    return []


def liderler(anahtar):
    """{"gol": [...], "asist": [...], "kart": [...]}; en fazla 5'er oyuncu. Veri yoksa liste bos."""
    kod = LIGLER[anahtar][0]
    with ThreadPoolExecutor(6) as ex:
        gol = list(ex.map(_oyuncu, _kategori(kod, "goals")[:ILK_N + 3]))
        asist = list(ex.map(_oyuncu, _kategori(kod, "assists")[:ILK_N + 3]))
        sari = list(ex.map(_oyuncu, _kategori(kod, "yellowCards")[:14]))
    g = lambda o, k: o["st"].get(k, 0)  # noqa: E731
    # esitlik: golde asist, asistte gol, kartta kirmizi ve az dakika
    gol = sorted([o for o in gol if g(o, "totalGoals") > 0],
                 key=lambda o: (-g(o, "totalGoals"), -g(o, "goalAssists"), g(o, "minutes")))[:ILK_N]
    asist = sorted([o for o in asist if g(o, "goalAssists") > 0],
                   key=lambda o: (-g(o, "goalAssists"), -g(o, "totalGoals"), g(o, "minutes")))[:ILK_N]
    kart = sorted([o for o in sari if g(o, "yellowCards") + g(o, "redCards") > 0],
                  key=lambda o: (-(g(o, "yellowCards") + g(o, "redCards")), -g(o, "redCards"), g(o, "minutes")))[:ILK_N]
    return {"gol": gol, "asist": asist, "kart": kart}

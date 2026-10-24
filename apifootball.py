"""apifootball.com (APIfootball) verisi: sezon ortalama oyuncu puani (rating) ve ek istatistikler.

Anahtar yalnizca APIFOOTBALL_KEY ortam degiskeninden okunur (GitHub secret); depoya yazilmaz.
Tek cagri (get_teams, league_id=322) tum Super Lig takimlarini ve oyuncularini dondurur.
Yanit 6 saat diskte onbellege alinir (ucretsiz plan istek sinirina saygi icin).
"""
import json
import os
import time
import urllib.request
from pathlib import Path

import fotograf

URL = "https://apiv3.apifootball.com/"
LIG_ID = 322  # Turkiye Super Lig
ONBELLEK = Path(__file__).parent / "data" / "apifootball_onbellek.json"
GECERLILIK = 6 * 3600


def _ham():
    anahtar = os.environ.get("APIFOOTBALL_KEY")
    if not anahtar:
        return None
    try:
        v = json.loads(ONBELLEK.read_text(encoding="utf-8"))
        if time.time() - v["zaman"] < GECERLILIK:
            return v["veri"]
    except Exception:
        pass
    try:
        with urllib.request.urlopen(f"{URL}?action=get_teams&league_id={LIG_ID}&APIkey={anahtar}", timeout=90) as r:
            veri = json.load(r)
    except Exception:
        return None
    if not isinstance(veri, list):
        return None   # hata govdesi (ornegin gecersiz anahtar)
    ONBELLEK.parent.mkdir(exist_ok=True)
    ONBELLEK.write_text(json.dumps({"zaman": time.time(), "veri": veri}, ensure_ascii=False), encoding="utf-8")
    return veri


def _sayi(v):
    try:
        x = float(v)
        return x if x > 0 else None
    except (TypeError, ValueError):
        return None


def puanlar():
    """[{ad, takim, puan}] ; anahtar/veri yoksa bos liste."""
    veri = _ham()
    if not veri:
        return []
    return [{"ad": p.get("player_name", ""), "takim": t.get("team_name", ""),
             "puan": _sayi(p.get("player_rating"))}
            for t in veri for p in t.get("players", [])]


def _takim_uyar(a, b):
    a, b = fotograf.norm(a), fotograf.norm(b)
    return bool(a and b and (a in b or b in a))


def puan_ekle(oyuncular):
    """Her oyuncunun st["puan"] alanini (yoksa None) doldurur; eslesme sayisini dondurur."""
    liste = puanlar()
    by = {}
    for p in liste:
        by.setdefault(fotograf.norm(p["ad"]), []).append(p)
    bulunan = 0
    for o in oyuncular:
        adaylar = by.get(fotograf.norm(o["ad"]), [])
        if len(adaylar) > 1:
            adaylar = [p for p in adaylar if _takim_uyar(o["takim"], p["takim"])] or adaylar
        puan = adaylar[0]["puan"] if len(adaylar) == 1 else None
        o["st"]["puan"] = puan
        bulunan += puan is not None
    return bulunan

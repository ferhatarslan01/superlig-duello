"""Gelismis sezon istatistikleri (PitchAPI): xG, xA, kilit pas, ilerletici pas, calim, hava topu vb.

PitchAPI'de sezon toplami yok; Super Lig'in biten maclarini gezip oyuncu bazinda toplariz
(/v1/date/{gun}, /v1/matches/{id}/advanced/players, /v1/matches/{id}/shots). Sonuc data/sezon_gelismis_2026.json
icinde 12 saat onbelleklenir. ESPN oyunculariyla ad + takim ile eslestirilir (ekle()).

Anahtar yoksa ya da PitchAPI'ye ulasilamazsa sessizce atlanir; kartlar yalnizca ESPN verisiyle calisir.
"""
import difflib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import fotograf

KLASOR = Path(__file__).parent
ONBELLEK = KLASOR / "data" / "sezon_gelismis_2026.json"
SEZON_BASI = date(2026, 8, 1)
TTL_SAAT = 12

# PitchAPI alani (grup, anahtar) -> ESPN verisine eklenen ad
ALANLAR = {
    "xA": ("creation", "xag"), "keyPasses": ("passing", "key_passes"), "progPasses": ("passing", "progressive_passes"),
    "passesIntoBox": ("passing", "passes_into_box"), "takeOns": ("carrying", "take_ons"),
    "takeOnsWon": ("carrying", "take_ons_won"), "progCarries": ("carrying", "progressive_carries"),
    "interceptions": ("defending", "interceptions"), "blocks": ("defending", "blocks"),
    "aerials": ("defending", "aerials"), "aerialsWon": ("defending", "aerials_won"),
}
SUT_ALANLARI = ("xG", "pitchShots", "boxShots", "pitchGoals")


def _pitch(yol):
    import baski_video
    return baski_video._pitch(yol)


def _maclar():
    """Super Lig'in biten maclari: [(id, ev_id, ev_ad, dep_id, dep_ad)]"""
    gunler = [SEZON_BASI + timedelta(days=i) for i in range((date.today() - SEZON_BASI).days + 1)]

    def gun_cek(g):
        try:
            r = _pitch(f"/v1/date/{g.isoformat()}")
        except Exception:
            return []
        return [(m["id"], m["home_team"]["id"], m["home_team"]["name"], m["away_team"]["id"], m["away_team"]["name"])
                for m in (r["matches"] if isinstance(r, dict) else r or [])
                if m["league"]["name"] == "Super Lig" and m.get("status") == "finished"]
    with ThreadPoolExecutor(8) as ex:
        return [m for liste in ex.map(gun_cek, gunler) for m in liste]


def _mac_topla(m):
    mid, ev_id, ev_ad, dep_id, dep_ad = m
    takim = {ev_id: ev_ad, dep_id: dep_ad}
    sonuc = {}
    try:
        adv = _pitch(f"/v1/matches/{mid}/advanced/players")["players"]
    except Exception:
        adv = []
    for p in adv:
        d = sonuc.setdefault(p["player"]["id"], {"ad": p["player"]["name"], "takim": takim.get(p["team_id"], ""),
                                                 "dk": 0.0, **{k: 0.0 for k in ALANLAR}})
        d["dk"] += p.get("minutes_played") or 0
        for ad, (grup, anahtar) in ALANLAR.items():
            d[ad] += ((p.get(grup) or {}).get(anahtar)) or 0
    try:
        sutlar = [s for per in _pitch(f"/v1/matches/{mid}/shots")["periods"] for s in per["shots"]]
    except Exception:
        sutlar = []
    for s in sutlar:
        pid = s["player"]["id"]
        d = sonuc.setdefault(pid, {"ad": s["player"]["name"], "takim": takim.get(s["team_id"], ""), "dk": 0.0,
                                   **{k: 0.0 for k in ALANLAR}})
        for k in SUT_ALANLARI:
            d.setdefault(k, 0.0)
        d["xG"] += s.get("expected_goals") or 0
        d["pitchShots"] += 1
        d["boxShots"] += 1 if s.get("is_inside_box") else 0
        d["pitchGoals"] += 1 if s.get("event_type") == "Goal" else 0
    return sonuc


def sezon_toplam(yenile=False):
    """{pitch_oyuncu_id: {ad, takim, dk, xG, xA, ...}} ; yoksa/anahtar yoksa {}."""
    if not os.environ.get("PITCHAPI_API_KEY"):
        return {}
    if ONBELLEK.exists() and not yenile and time.time() - ONBELLEK.stat().st_mtime < TTL_SAAT * 3600:
        return json.loads(ONBELLEK.read_text(encoding="utf-8"))
    try:
        maclar = _maclar()
        with ThreadPoolExecutor(6) as ex:
            parcalar = list(ex.map(_mac_topla, maclar))
    except Exception as e:
        print(f"gelismis: PitchAPI toplanamadi ({e})")
        return json.loads(ONBELLEK.read_text(encoding="utf-8")) if ONBELLEK.exists() else {}
    toplam = {}
    for parca in parcalar:
        for pid, d in parca.items():
            t = toplam.setdefault(pid, {"ad": d["ad"], "takim": d["takim"], "dk": 0.0,
                                        **{k: 0.0 for k in ALANLAR}, **{k: 0.0 for k in SUT_ALANLARI}})
            t["takim"] = d["takim"] or t["takim"]
            for k, v in d.items():
                if k not in ("ad", "takim"):
                    t[k] = t.get(k, 0.0) + v
    ONBELLEK.parent.mkdir(exist_ok=True)
    ONBELLEK.write_text(json.dumps(toplam, ensure_ascii=False), encoding="utf-8")
    return toplam


def _norm(s):
    return fotograf.norm(s or "")


TAKIM_ESLEME = {"amed sfk": "amed sportif", "erzurum bb": "erzurumspor fk"}   # ESPN adi -> PitchAPI adi


def _takim_ayni(a, b):
    a, b = _norm(a), _norm(b)
    a, b = TAKIM_ESLEME.get(a, a), TAKIM_ESLEME.get(b, b)
    return a == b or a in b or b in a


def _eslestir(o, adaylar):
    """ESPN oyuncusu o icin ayni takimdaki PitchAPI adaylarindan en iyi eslesen (ya da None)."""
    ad = _norm(o["ad"])
    for pid, d in adaylar:
        if _norm(d["ad"]) == ad:
            return pid
    tok = ad.split()
    for pid, d in adaylar:                       # ayni sozcukler, farkli sira (Ui-Jo Hwang / Hwang Ui-Jo)
        if tok and sorted(tok) == sorted(_norm(d["ad"]).split()):
            return pid
    en, oran_en = None, 0.0
    for pid, d in adaylar:
        t2 = _norm(d["ad"]).split()
        if tok and t2 and tok[-1] == t2[-1] and tok[0][:1] == t2[0][:1]:
            return pid
        oran = difflib.SequenceMatcher(None, ad, _norm(d["ad"])).ratio()
        if oran > oran_en:
            en, oran_en = pid, oran
    return en if oran_en >= 0.84 else None


def ekle(oyuncular, yenile=False):
    """ESPN oyuncularinin o["st"] alanina gelismis istatistikleri ekler (eslesenlere). Eslesen sayisini doner."""
    toplam = sezon_toplam(yenile)
    if not toplam:
        return 0
    eslesen = 0
    for o in oyuncular:
        adaylar = [(pid, d) for pid, d in toplam.items() if _takim_ayni(d["takim"], o["takim"])]
        pid = _eslestir(o, adaylar)
        if not pid:
            continue
        d = toplam[pid]
        # dakika uyumsuzsa (yanlis eslesme) atla
        if abs(d["dk"] - o["st"].get("minutes", 0)) > max(120, 0.25 * o["st"].get("minutes", 0)):
            continue
        for k in list(ALANLAR) + ["xG", "boxShots"]:
            o["st"][k] = d.get(k, 0.0)
        o["st"]["pitchShots"] = d.get("pitchShots", 0.0)
        o["st"]["pitchGoals"] = d.get("pitchGoals", 0.0)
        eslesen += 1
    return eslesen


if __name__ == "__main__":
    import sezon
    oy = sezon.sezon_verisi(yenile=False)
    n = sum(1 for o in oy if "xG" in o["st"])
    print(f"{n}/{len(oy)} oyuncu eslesti")
    yok = [f"{o['ad']} ({o['takim']})" for o in oy if "xG" not in o["st"]]
    print("eslesmeyen:", yok[:40])

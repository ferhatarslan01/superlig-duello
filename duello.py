"""Mac sonrasi duello karti: ESPN'in acik Super Lig verisinden, ayni rolde oynayan
karsi takim oyunculari esler ve 1080x1080 PNG uretir.

Kullanim:
  python duello.py                 # son biten mac
  python duello.py 401888276       # belirli mac (ESPN event id)
  python duello.py --tarih 20261018
"""
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import fotograf

HESAP = "@StatDuel"

LIG = "tur.1"
API = "https://site.api.espn.com/apis/site/v2/sports/soccer/" + LIG
OUT = Path(__file__).parent / "out"

# ESPN pozisyon kisaltmasi -> eslesme grubu
ROL = {
    "G": "Kaleci",
    "CD-L": "Stoper", "CD-R": "Stoper", "CD": "Stoper", "SW": "Stoper",
    "LB": "Bek", "RB": "Bek", "LWB": "Bek", "RWB": "Bek",
    "DM": "Defansif orta saha",
    "CM": "Merkez orta saha", "CM-L": "Merkez orta saha", "CM-R": "Merkez orta saha",
    "AM": "Ofansif orta saha", "AM-L": "Kanat", "AM-R": "Kanat",
    "LM": "Yan orta saha", "RM": "Yan orta saha", "LW": "Kanat", "RW": "Kanat",
    "F": "Forvet", "CF": "Forvet", "CF-L": "Forvet", "CF-R": "Forvet", "ST": "Forvet",
}
ROL_SIRA = ["Forvet", "Kanat", "Yan orta saha", "Ofansif orta saha", "Merkez orta saha", "Defansif orta saha", "Bek", "Stoper", "Kaleci"]

STATLAR = [  # (alan, etiket)
    ("minutes", "OYNADIĞI SÜRE (DK)"),
    ("totalGoals", "GOL"),
    ("goalAssists", "ASİST"),
    ("totalShots", "ŞUT"),
    ("shotsOnTarget", "İSABETLİ ŞUT"),
    ("accuratePasses", "İSABETLİ PAS"),
    ("passPct", "PAS İSABETİ"),
    ("effectiveTackles", "TOP ÇALMA"),
    ("foulsCommitted", "YAPILAN FAUL"),
    ("yellowCards", "SARI KART"),
]
KALECI_STATLAR = [("minutes", "OYNADIĞI SÜRE (DK)"), ("saves", "KURTARIŞ"), ("goalsConceded", "YENEN GOL"),
                  ("accuratePasses", "İSABETLİ PAS"), ("passPct", "PAS İSABETİ"),
                  ("foulsCommitted", "YAPILAN FAUL"), ("yellowCards", "SARI KART")]
KOTU = {"foulsCommitted", "yellowCards", "redCards", "goalsConceded", "minutes"}
CORE = "https://sports.core.api.espn.com/v2/sports/soccer/leagues/" + LIG


def get(url, deneme=4):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for i in range(deneme):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429 or i == deneme - 1:
                raise
        except (urllib.error.URLError, TimeoutError, OSError):
            if i == deneme - 1:
                raise
        time.sleep(2 * (i + 1))


def ek_istatistik(eid, takim_id, oyuncu_id):
    """Pas, top calma gibi alanlar yalnizca core API'de oyuncu bazli gelir."""
    try:
        r = get(f"{CORE}/events/{eid}/competitions/{eid}/competitors/{takim_id}/roster/{oyuncu_id}/statistics/0")
    except Exception:
        return {}
    return {s["name"]: s["value"] for c in r["splits"]["categories"] for s in c["stats"]}


def son_biten_mac():
    gun = datetime.utcnow()
    for _ in range(10):
        veri = get(f"{API}/scoreboard?dates={gun:%Y%m%d}")
        biten = [e for e in veri.get("events", []) if e["status"]["type"]["completed"]]
        if biten:
            return biten[-1]["id"]
        gun -= timedelta(days=1)
    raise SystemExit("Son 10 gunde biten mac bulunamadi")


def _sezon_rolleri():
    """{oyuncu_id: rol}: sezon istatistigine gore siniflanmis roller (yoksa bos). Mac kartinda da
    ESPN'in formasyon yuvasi kodu yerine bu rol kullanilir."""
    try:
        import sezon
        return {str(o["id"]): o for o in sezon.sezon_verisi()}
    except Exception:
        return {}


def oyuncular(takim, eid, sezon_rol=None):
    sezon_rol = sezon_rol if sezon_rol is not None else {}
    sonuc = []
    for p in takim["roster"]:
        if not p.get("starter"):
            continue
        poz = p["position"]["abbreviation"]
        st = {s["name"]: s["value"] for s in p.get("stats", [])}
        st.update(ek_istatistik(eid, takim["team"]["id"], p["athlete"]["id"]))
        sonuc.append({
            "id": p["athlete"]["id"],
            "ad": p["athlete"]["displayName"],
            "kisa": p["athlete"].get("shortName", p["athlete"]["displayName"]),
            "poz": poz,
            "rol": (sezon_rol.get(str(p["athlete"]["id"])) or {}).get("rol") or ROL.get(poz),
            "yas": (sezon_rol.get(str(p["athlete"]["id"])) or {}).get("yas"),
            "st": st,
        })
    return sonuc


def etki(o):
    s = o["st"]
    return (s.get("totalGoals", 0) * 5 + s.get("goalAssists", 0) * 4 + s.get("shotsOnTarget", 0) * 2
            + s.get("totalShots", 0) + s.get("saves", 0) * 1.5 + s.get("accuratePasses", 0) * 0.05 + s.get("effectiveTackles", 0) * 0.7 + s.get("interceptions", 0) * 0.7 + s.get("foulsSuffered", 0) * 0.5
            + s.get("foulsCommitted", 0) * 0.5 + s.get("yellowCards", 0) * 1 + s.get("redCards", 0) * 4)


def duello_sec(ev, eid):
    """Her rol grubundan iki takimin en etkili oyuncusunu eslestirir; en yuksek toplam etkiyi secer."""
    sr = _sezon_rolleri()
    a, b = (oyuncular(t, eid, sr) for t in ev["rosters"])
    en_iyi = None
    for rol in ROL_SIRA:
        ga = [o for o in a if o["rol"] == rol]
        gb = [o for o in b if o["rol"] == rol]
        if not ga or not gb:
            continue
        oa, ob = max(ga, key=etki), max(gb, key=etki)
        puan = etki(oa) + etki(ob)
        if en_iyi is None or puan > en_iyi[0]:
            en_iyi = (puan, rol, oa, ob)
    return en_iyi


def buyuk(m):
    return m.replace("i", "İ").replace("ı", "I").upper()


FONT_DIR = Path(__file__).parent / "fonts"


def font(boyut, kalin=True):
    # Barlow (OFL): Linux/GitHub Actions'ta da ayni gorunum icin repoda tutulur
    ad = "BarlowCondensed-SemiBold.ttf" if kalin else "Barlow-Regular.ttf"
    return ImageFont.truetype(str(FONT_DIR / ad), int(boyut * (1.12 if kalin else 1.0)))


def sigdir(d, metin, max_w, boyut, kalin=True, en_kucuk=26):
    """Metin max_w'ye sigana kadar yazi boyutunu kucultur."""
    while boyut > en_kucuk and d.textlength(metin, font=font(boyut, kalin)) > max_w:
        boyut -= 2
    return font(boyut, kalin)


MAC_SATIRLARI = [("totalGoals", "GOL"), ("goalAssists", "ASİST"), ("totalShots", "ŞUT"),
                 ("shotsOnTarget", "İSABETLİ ŞUT"), ("passPct", "PAS İSABETİ"),
                 ("effectiveTackles", "TOP ÇALMA"), ("yellowCards", "SARI KART")]
MAC_KALECI_SATIRLARI = [("saves", "KURTARIŞ"), ("goalsConceded", "YENEN GOL"), ("saveRate", "KURTARIŞ ORANI"),
                        ("accuratePasses", "İSABETLİ PAS"), ("passPct", "PAS İSABETİ")]


def kart_ciz(ev, rol, oa, ob, yol):
    import kart_v2
    c = ev["header"]["competitions"][0]["competitors"]
    ev_s = next(t for t in c if t["homeAway"] == "home")
    dep = next(t for t in c if t["homeAway"] == "away")
    skor = (f'{kart_v2.takim_adi(ev_s["team"]["displayName"])} {ev_s["score"]}-{dep["score"]} '
            f'{kart_v2.takim_adi(dep["team"]["displayName"])}')

    def oyuncu(o):
        dk = int(o["st"].get("minutes", 0))
        return {"id": o.get("id"), "ad": o["ad"], "takim": o["_takim"], "yas": o.get("yas"), "st": o["st"],
                "satir2": f"{dk} dk oynadı" if dk else None}
    a, b = oyuncu(oa), oyuncu(ob)
    satirlar = MAC_KALECI_SATIRLARI if rol == "Kaleci" else MAC_SATIRLARI
    kart_v2.ciz(yol, "SÜPER LİG  ·  MAÇ SONU DÜELLOSU", skor, a, b, satirlar,
                "Sence bu düelloyu kim kazandı?", kotu=KOTU)
    oa["_foto"], ob["_foto"] = a["_foto"], b["_foto"]


def kart_uret(eid):
    """Maci ESPN'den ceker, duello cifti secer, kart PNG'si uretir. (yol, rol, oa, ob, ev) doner; cift yoksa None."""
    ev = get(f"{API}/summary?event={eid}")
    sec = duello_sec(ev, eid)
    if not sec:
        return None
    _, rol, oa, ob = sec
    a, b = ev["rosters"]
    oa["_takim"], ob["_takim"] = a["team"]["displayName"], b["team"]["displayName"]
    OUT.mkdir(exist_ok=True)
    yol = OUT / f"duello_{eid}.png"
    kart_ciz(ev, rol, oa, ob, yol)
    return yol, rol, oa, ob, ev


def main():
    args = sys.argv[1:]
    if args and args[0] == "--tarih":
        v = get(f"{API}/scoreboard?dates={args[1]}")
        eid = next(e["id"] for e in v["events"] if e["status"]["type"]["completed"])
    elif args:
        eid = args[0]
    else:
        eid = son_biten_mac()
    sonuc = kart_uret(eid)
    if not sonuc:
        raise SystemExit("Eslesen oyuncu cifti bulunamadi")
    yol, rol, oa, ob, _ = sonuc
    print(f"Mac {eid} | {rol}: {oa['ad']} vs {ob['ad']}")
    print(yol)


if __name__ == "__main__":
    main()

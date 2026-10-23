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
    "DM": "Orta saha", "CM": "Orta saha", "CM-L": "Orta saha", "CM-R": "Orta saha",
    "AM": "Ön libero", "AM-L": "Kanat", "AM-R": "Kanat",
    "LM": "Kanat", "RM": "Kanat", "LW": "Kanat", "RW": "Kanat",
    "F": "Forvet", "CF": "Forvet", "CF-L": "Forvet", "CF-R": "Forvet", "ST": "Forvet",
}
ROL_SIRA = ["Forvet", "Kanat", "Ön libero", "Orta saha", "Bek", "Stoper", "Kaleci"]

STATLAR = [  # (alan, etiket)
    ("minutes", "OYNADIĞI SÜRE (DK)"),
    ("totalGoals", "GOL"),
    ("goalAssists", "ASİST"),
    ("totalShots", "ŞUT"),
    ("shotsOnTarget", "İSABETLİ ŞUT"),
    ("accuratePasses", "İSABETLİ PAS"),
    ("passPct", "PAS İSABETİ"),
    ("effectiveTackles", "TOP ÇALMA"),
    ("interceptions", "TOP KESME"),
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


def oyuncular(takim, eid):
    sonuc = []
    for p in takim["roster"]:
        if not p.get("starter"):
            continue
        poz = p["position"]["abbreviation"]
        st = {s["name"]: s["value"] for s in p.get("stats", [])}
        st.update(ek_istatistik(eid, takim["team"]["id"], p["athlete"]["id"]))
        sonuc.append({
            "ad": p["athlete"]["displayName"],
            "kisa": p["athlete"].get("shortName", p["athlete"]["displayName"]),
            "poz": poz,
            "rol": ROL.get(poz),
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
    a, b = (oyuncular(t, eid) for t in ev["rosters"])
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


def kart_ciz(ev, rol, oa, ob, yol):
    W = H = 1080
    img = Image.new("RGB", (W, H), (14, 17, 26))
    d = ImageDraw.Draw(img)
    # ust band
    d.rectangle([0, 0, W, 8], fill=(230, 57, 70))

    comp = ev["header"]["competitions"][0]
    takimlar = comp["competitors"]
    ev_sahibi = next(t for t in takimlar if t["homeAway"] == "home")
    deplasman = next(t for t in takimlar if t["homeAway"] == "away")
    skor = f'{ev_sahibi["team"]["displayName"]} {ev_sahibi["score"]}-{deplasman["score"]} {deplasman["team"]["displayName"]}'

    def ortala(y, metin, f, renk):
        w = d.textlength(metin, font=f)
        d.text(((W - w) / 2, y), metin, font=f, fill=renk)

    ortala(48, "SÜPER LİG  |  MAÇ SONU DÜELLOSU", font(30), (160, 168, 188))
    ortala(100, buyuk(skor), font(40), (255, 255, 255))
    ortala(168, buyuk(rol), font(88), (230, 57, 70))

    # oyuncu fotograflari ve adlari
    D = 130
    for o, sol in ((oa, True), (ob, False)):
        o["_fotoim"], o["_foto"] = fotograf.foto_al(o["ad"], o["_takim"])
        fx = 70 if sol else W - 70 - D
        fotograf.daire_yapistir(img, o["_fotoim"], fx, 286, D)
        ad, takim = buyuk(o["ad"]), o["_takim"]
        fa, ft = sigdir(d, ad, 280, 44), sigdir(d, takim, 280, 28, False, 20)
        if sol:
            tx = 70 + D + 24
            d.text((tx, 318), ad, font=fa, fill=(255, 255, 255))
            d.text((tx, 372), takim, font=ft, fill=(160, 168, 188))
        else:
            tx = W - 70 - D - 24
            d.text((tx - d.textlength(ad, font=fa), 318), ad, font=fa, fill=(255, 255, 255))
            d.text((tx - d.textlength(takim, font=ft), 372), takim, font=ft, fill=(160, 168, 188))

    statlar = KALECI_STATLAR if rol == "Kaleci" else STATLAR
    y = 432
    for alan, etiket in statlar:
        va, vb = oa["st"].get(alan, 0), ob["st"].get(alan, 0)
        if alan == "passPct":
            ta_, tb_ = f"%{round(va * 100)}", f"%{round(vb * 100)}"
        else:
            va, vb = int(va), int(vb)
            ta_, tb_ = str(va), str(vb)
        iyi = alan not in KOTU
        ca = (255, 214, 10) if iyi and va > vb else (255, 255, 255)
        cb = (255, 214, 10) if iyi and vb > va else (255, 255, 255)
        d.text((120, y), ta_, font=font(36), fill=ca)
        wb = d.textlength(tb_, font=font(36))
        d.text((W - 120 - wb, y), tb_, font=font(36), fill=cb)
        ortala(y + 5, etiket, font(27, False), (160, 168, 188))
        d.line([70, y + 46, W - 70, y + 46], fill=(36, 41, 58), width=2)
        y += 48

    ortala(H - 78, "Sence bu düelloyu kim kazandı?", font(36), (255, 255, 255))
    kaynaklar = sorted({o["_foto"] for o in (oa, ob) if o["_foto"]})
    alt = f"{HESAP}  ·  Veri: ESPN" + (f"  ·  Foto: {', '.join(kaynaklar)}" if kaynaklar else "")
    ortala(H - 36, alt, font(22, False), (110, 118, 140))
    img.save(yol)


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

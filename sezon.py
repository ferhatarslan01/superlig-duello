"""Sezon duellosu karti: ayni rolde oynayan, 90 dakika basina istatistikleri birbirine
en yakin iki farkli takim oyuncusunu bulur ve 1080x1350 PNG uretir.

Kullanim:
  python sezon.py                      # yeni oyuncu cifti sec (daha once paylasilmayanlardan)
  python sezon.py --rol Forvet         # rol sec
  python sezon.py --yenile             # sezon verisini yeniden cek
  python sezon.py "Kerem" "Coulibaly"  # iki oyuncuyu elle sec (ad parcasi)
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw

import fotograf
import satirlar as _satir
from duello import API, CORE, HESAP, ROL, ROL_SIRA, buyuk, font, get, sigdir

KLASOR = Path(__file__).parent
VERI = KLASOR / "data"
OUT = KLASOR / "out"
SEZON = 2026
MIN_DAKIKA = 90  # bundan FAZLA oynayanlar karsilastirmaya girer (tam 90 dk dahil degil)

# 90 dakika basina karsilastirilan alanlar (benzerlik hesabi icin)
KALECI_OZELLIK = ["saves", "goalsConceded", "accuratePasses", "totalPasses"]
OZELLIK = ["totalGoals", "goalAssists", "totalShots", "shotsOnTarget", "totalPasses",
           "effectiveTackles", "foulsCommitted", "foulsSuffered"]

SATIRLAR = [  # (alan, etiket, tur)   tur: sayi = sezon toplami, yuzde
    ("appearances", "MAÇ", "sayi"),
    ("minutes", "OYNADIĞI SÜRE (DK)", "sayi"),
    ("totalGoals", "GOL", "sayi"),
    ("goalAssists", "ASİST", "sayi"),
    ("totalShots", "ŞUT", "sayi"),
    ("shotsOnTarget", "İSABETLİ ŞUT", "sayi"),
    ("passPct", "PAS İSABETİ", "yuzde"),
    ("effectiveTackles", "TOP ÇALMA", "sayi"),
    ("foulsCommitted", "FAUL", "sayi"),
    ("yellowCards", "SARI KART", "sayi"),
    ("redCards", "KIRMIZI KART", "sayi"),
]
KOTU = {"foulsCommitted", "yellowCards", "redCards", "appearances", "minutes"}


SON_MAC_SAYISI = 10  # mevki icin bir takimin en fazla kac son macina bakilir


def son_pozisyonlar(tid):
    """Takimin son maclarindaki kadrolardan {oyuncu_id: pozisyon}. Her oyuncu icin son
    SON_MAC_SAYISI macta (yedekten girenler dahil) en cok oynadigi rol grubu secilir;
    esitlikte en yeni mac kazanir. Donen pozisyon o grubun en cok gorulen kisaltmasidir."""
    gecmis = {}  # oyuncu_id -> [pozisyon, ...] en yeniden eskiye
    try:
        olaylar = get(f"{API}/teams/{tid}/schedule")["events"]
    except Exception:
        return {}
    biten = [e for e in olaylar if e["competitions"][0]["status"]["type"]["completed"]]
    biten.sort(key=lambda e: e["date"], reverse=True)
    for e in biten[:SON_MAC_SAYISI]:
        try:
            ev = get(f"{API}/summary?event={e['id']}")
        except Exception:
            continue
        for t in ev.get("rosters", []):
            if str(t["team"]["id"]) != str(tid):
                continue
            for p in t["roster"]:
                oynadi = any(st["name"] == "appearances" and st["value"] > 0 for st in p.get("stats", []))
                poz = p.get("position", {}).get("abbreviation")
                if oynadi and ROL.get(poz):
                    gecmis.setdefault(str(p["athlete"]["id"]), []).append(poz)
    sonuc = {}
    for oid, pozlar in gecmis.items():
        sayac = {}
        for i, poz in enumerate(pozlar):
            n, ilk = sayac.get(ROL[poz], (0, i))
            sayac[ROL[poz]] = (n + 1, ilk)
        rol = max(sayac, key=lambda r: (sayac[r][0], -sayac[r][1]))
        sonuc[oid] = next(p for p in pozlar if ROL[p] == rol)
    return sonuc


def _sezon_verisi_ham(yenile=False):
    yol = VERI / f"sezon_{SEZON}.json"
    if yol.exists() and not yenile:
        return json.loads(yol.read_text(encoding="utf-8"))
    takimlar = get(f"{API}/teams")["sports"][0]["leagues"][0]["teams"]
    with ThreadPoolExecutor(6) as ex:
        son_poz = dict(zip((t["team"]["id"] for t in takimlar),
                           ex.map(son_pozisyonlar, (t["team"]["id"] for t in takimlar))))
    adaylar = []
    for t in takimlar:
        tid, tad = t["team"]["id"], t["team"]["displayName"]
        for a in get(f"{API}/teams/{tid}/roster")["athletes"]:
            # once son 10 macta en cok oynadigi mevki, yoksa kadro listesindeki pozisyon
            poz = son_poz[tid].get(str(a["id"])) or a.get("position", {}).get("abbreviation")
            if ROL.get(poz):
                adaylar.append((a["id"], a["displayName"], poz, tad, a.get("age")))

    def cek(a):
        aid, ad, poz, tad, yas = a
        try:
            r = get(f"{CORE}/seasons/{SEZON}/types/1/athletes/{aid}/statistics/0")
        except Exception:
            return None
        st = {s["name"]: s["value"] for c in r["splits"]["categories"] for s in c["stats"]}
        if st.get("minutes", 0) <= MIN_DAKIKA:
            return None
        return {"id": aid, "ad": ad, "poz": poz, "rol": ROL[poz], "takim": tad, "yas": yas, "st": st}

    with ThreadPoolExecutor(8) as ex:
        sonuc = [o for o in ex.map(cek, adaylar) if o]
    VERI.mkdir(exist_ok=True)
    yol.write_text(json.dumps(sonuc, ensure_ascii=False), encoding="utf-8")
    return sonuc


def p90(o, alan):
    return o["st"].get(alan, 0) / o["st"]["minutes"] * 90


MAX_SURE_FARKI = 350  # iki oyuncunun oynadigi sure farki bundan az olmali (dakika)
MAX_MESAFE = 2.4  # ~%60 benzerlik; bundan uzak ciftler otomatik secilmez (kucuk havuzda zayif eslesmeyi onler)


SAVUNMA_OZELLIK = ["effectiveTackles", "totalClearance", "blockedShots", "totalPasses",
                   "foulsCommitted", "foulsSuffered"]
HUCUM_ROLLERI = {"Forvet", "Kanat", "Ofansif orta saha", "Yan orta saha"}


def ozellikler(rol):
    if rol == "Kaleci":
        return KALECI_OZELLIK
    if rol in ("Stoper", "Bek", "Defansif orta saha"):
        return SAVUNMA_OZELLIK
    return OZELLIK


def en_benzer_cift(oyuncular, rol=None, yasak=(), max_mesafe=MAX_MESAFE):
    roller = [rol] if rol else list(ROL_SIRA)
    en = None
    for r in roller:
        grup = [o for o in oyuncular if o["rol"] == r]
        if len(grup) < 4:
            continue
        # ozellik basina standart sapma ile olcekle
        std = {}
        for f in ozellikler(r):
            v = [p90(o, f) for o in grup]
            m = sum(v) / len(v)
            std[f] = (sum((x - m) ** 2 for x in v) / len(v)) ** 0.5 or 1.0
        for i, a in enumerate(grup):
            for b in grup[i + 1:]:
                if a["takim"] == b["takim"] or frozenset((a["id"], b["id"])) in yasak:
                    continue
                dist = sum(((p90(a, f) - p90(b, f)) / std[f]) ** 2 for f in ozellikler(r)) ** 0.5
                # her ikisi de en az bir "olay" uretmis olsun (cok sessiz ciftler bos kart olur)
                canli = a["st"].get("totalGoals", 0) + a["st"].get("goalAssists", 0) + \
                    b["st"].get("totalGoals", 0) + b["st"].get("goalAssists", 0)
                if canli < 2 and r in HUCUM_ROLLERI:
                    continue
                if abs(a["st"]["minutes"] - b["st"]["minutes"]) >= MAX_SURE_FARKI:
                    continue
                if max_mesafe is not None and dist > max_mesafe:
                    continue
                if en is None or dist < en[0]:
                    en = (dist, r, a, b)
    return en


def deger(o, alan, tur):
    if tur == "yuzde":
        return o["st"].get("passPct", 0) * 100
    if tur == "p90":
        return p90(o, alan)
    return o["st"].get(alan, 0)


def metin(v, tur):
    if tur == "yuzde":
        return f"%{round(v)}"
    if tur == "p90":
        return f"{v:.2f}".replace(".", ",")
    return str(int(v))


SEZON_SATIRLARI = [("totalGoals", "GOL"), ("goalAssists", "ASİST"), ("totalShots", "ŞUT"),
                   ("passPct", "PAS İSABETİ"), ("effectiveTackles", "TOP ÇALMA"),
                   ("yellowCards", "SARI KART"), ("redCards", "KIRMIZI KART")]


SEZON_KALECI_SATIRLARI = [("appearances", "MAÇ"), ("saves", "KURTARIŞ"),
                          ("cleanSheet", "GOL YEMEDEN BİTEN MAÇ"), ("saveRate", "KURTARIŞ ORANI"),
                          ("accuratePasses", "İSABETLİ PAS")]


def kart_ciz(rol, a, b, benzerlik, yol):
    import kart_v2

    def oyuncu(o):
        return {"id": o["id"], "ad": o["ad"], "takim": o["takim"], "yas": o.get("yas"), "st": o["st"],
                "satir2": None}
    ka, kb = oyuncu(a), oyuncu(b)
    kart_v2.ciz(yol, "SÜPER LİG  ·  SEZON KARŞILAŞTIRMASI", f"{SEZON}-{str(SEZON + 1)[2:]} sezonu", ka, kb,
                _satir.sezon_satirlari(rol), "İkisinden hangisini seçerdin?", kotu=KOTU)
    a["_foto"], b["_foto"] = ka["_foto"], kb["_foto"]


def ada_gore(oyuncular, parca):
    parca = parca.lower()
    bul = [o for o in oyuncular if parca in o["ad"].lower()]
    if not bul:
        raise SystemExit(f"'{parca}' bulunamadi (en az {MIN_DAKIKA} dk oynayanlar listede)")
    return bul[0]


DUZELTME = VERI / "mevki_duzeltme.json"

# ---- orta saha / kanat otomatik siniflandirma ----
# ESPN LM/RM/CM gibi kodlari formasyon yuvasina gore verir (Kante "RM" gorunur). Bu yuzden
# orta saha ve kanat oyunculari sezon istatistiklerinden "savunma - hucum" puanina gore siniflanir.
ORTA_ROLLER = {"Kanat", "Yan orta saha", "Ofansif orta saha", "Merkez orta saha", "Defansif orta saha"}
KANAT_KODLARI = {"AM-L", "AM-R", "LW", "RW"}   # ESPN'de ofansif kanat yuvalari: her zaman kanat
YAN_KODLARI = {"LM", "RM"}                      # yan orta saha yuvalari: gercek rol istatistikten
YAN_SAVUNMA_ESIGI = 0.0    # LM/RM icin puan >= bu -> defansif orta saha
YAN_KANAT_ESIGI = -1.5     # LM/RM icin puan <  bu -> kanat; aradaki -> yan orta saha
SAVUNMA_ESIGI = 1.0        # merkez kodlari: puan >= bu -> defansif orta saha
HUCUM_ESIGI = -1.0         # merkez kodlari: puan <  bu -> ofansif orta saha


def _z(havuz, alan):
    v = [p90(o, alan) for o in havuz]
    m = sum(v) / len(v)
    sd = (sum((x - m) ** 2 for x in v) / len(v)) ** 0.5 or 1.0
    return lambda o: (p90(o, alan) - m) / sd


def orta_saha_puani(oyuncular):
    """{oyuncu_id: puan}; puan yuksek = savunmaci, dusuk = hucumcu."""
    havuz = [o for o in oyuncular if o["rol"] in ORTA_ROLLER]
    if len(havuz) < 10:
        return {}
    zt, zc, zb = _z(havuz, "effectiveTackles"), _z(havuz, "totalClearance"), _z(havuz, "blockedShots")
    zs, zg, za = _z(havuz, "totalShots"), _z(havuz, "totalGoals"), _z(havuz, "goalAssists")
    return {o["id"]: (zt(o) + 0.5 * zc(o) + 0.3 * zb(o)) - (zs(o) + 0.7 * zg(o) + 0.7 * za(o)) for o in havuz}


def orta_saha_sinifla(oyuncular):
    puan = orta_saha_puani(oyuncular)
    for o in oyuncular:
        if o["id"] not in puan:
            continue
        poz, sk = o["poz"], puan[o["id"]]
        if poz == "DM":
            o["rol"] = "Defansif orta saha"
        elif poz in KANAT_KODLARI:
            o["rol"] = "Kanat"
        elif poz in YAN_KODLARI:
            o["rol"] = ("Defansif orta saha" if sk >= YAN_SAVUNMA_ESIGI
                        else "Yan orta saha" if sk >= YAN_KANAT_ESIGI else "Kanat")
        elif poz == "AM":
            o["rol"] = "Merkez orta saha" if sk >= 1.5 else "Ofansif orta saha"
        else:  # CM, CM-L, CM-R
            o["rol"] = ("Defansif orta saha" if sk >= SAVUNMA_ESIGI
                        else "Merkez orta saha" if sk >= HUCUM_ESIGI else "Ofansif orta saha")
    return oyuncular


def sezon_verisi(yenile=False):
    """Ham ESPN verisi + elle mevki duzeltmeleri. ESPN, orta saha oyunculari formasyon
    yuvasina gore (LM/RM...) kodluyor; yanlis kalan oyuncular data/mevki_duzeltme.json ile
    {"Oyuncu Adi": "Rol"} seklinde duzeltilir."""
    oyuncular = [o for o in _sezon_verisi_ham(yenile) if o["st"]["minutes"] > MIN_DAKIKA]
    oyuncular = orta_saha_sinifla(oyuncular)
    if not DUZELTME.exists():
        return oyuncular
    gecerli = set(ROL.values())
    duz = {fotograf.norm(k): v for k, v in json.loads(DUZELTME.read_text(encoding="utf-8")).items()
           if not k.startswith("_")}
    for ad, rol in duz.items():
        if rol not in gecerli:
            raise SystemExit(f"mevki_duzeltme.json: '{rol}' gecerli bir rol degil. Gecerli roller: {sorted(gecerli)}")
    for o in oyuncular:
        yeni = duz.get(fotograf.norm(o["ad"]))
        if yeni:
            o["rol"] = yeni
    return oyuncular


def sezon_kart(rol=None, yenile=False):
    """Daha once paylasilmamis en benzer cifti secip karti uretir. (yol, rol, a, b, benzerlik) doner."""
    oyuncular = sezon_verisi(yenile)
    paylasilan = VERI / "paylasilan_sezon.json"
    gecmis = json.loads(paylasilan.read_text()) if paylasilan.exists() else []
    sec = en_benzer_cift(oyuncular, rol, {frozenset(x) for x in gecmis})
    if not sec:
        return None
    dist, rol_, a, b = sec
    benz = max(0, min(100, round(100 * (1 - dist / 6))))
    OUT.mkdir(exist_ok=True)
    yol = OUT / f"sezon_{a['id']}_{b['id']}.png"
    kart_ciz(rol_, a, b, benz, yol)
    return yol, rol_, a, b, benz


def cift_kart(ad1, ad2, yenile=False):
    """Elle secilen iki oyuncu (ad parcasi) icin kart uretir. (yol, rol, a, b, benzerlik) doner."""
    oyuncular = sezon_verisi(yenile)
    a, b = ada_gore(oyuncular, ad1), ada_gore(oyuncular, ad2)
    grup = [o for o in oyuncular if o["rol"] == a["rol"]]
    std = {}
    for f in ozellikler(a["rol"]):
        v = [p90(o, f) for o in grup]
        m = sum(v) / len(v)
        std[f] = (sum((x - m) ** 2 for x in v) / len(v)) ** 0.5 or 1.0
    dist = sum(((p90(a, f) - p90(b, f)) / std[f]) ** 2 for f in ozellikler(a["rol"])) ** 0.5
    benz = max(0, min(100, round(100 * (1 - dist / 6))))
    OUT.mkdir(exist_ok=True)
    yol = OUT / f"sezon_{a['id']}_{b['id']}.png"
    kart_ciz(a["rol"], a, b, benz, yol)
    return yol, a["rol"], a, b, benz


def paylasildi_isaretle(a, b):
    paylasilan = VERI / "paylasilan_sezon.json"
    gecmis = json.loads(paylasilan.read_text()) if paylasilan.exists() else []
    gecmis.append([a["id"], b["id"]])
    paylasilan.write_text(json.dumps(gecmis), encoding="utf-8")


def main():
    args = sys.argv[1:]
    yenile = "--yenile" in args
    rol = None
    if "--rol" in args:
        rol = args[args.index("--rol") + 1]
    ad = [x for x in args if not x.startswith("--") and x != rol]

    if len(ad) == 2:
        sonuc = cift_kart(ad[0], ad[1], yenile)
    else:
        sonuc = sezon_kart(rol, yenile)
        if not sonuc:
            raise SystemExit("Uygun oyuncu cifti bulunamadi")
    yol, rol_, a, b, benz = sonuc
    print(f"{rol_}: {a['ad']} ({a['takim']}) vs {b['ad']} ({b['takim']}) | benzerlik %{benz}")
    print(yol)


if __name__ == "__main__":
    main()

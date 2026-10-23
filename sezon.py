"""Sezon duellosu karti: ayni rolde oynayan, 90 dakika basina istatistikleri birbirine
en yakin iki farkli takim oyuncusunu bulur ve 1080x1080 PNG uretir.

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

from duello import API, CORE, ROL, ROL_SIRA, buyuk, font, get

KLASOR = Path(__file__).parent
VERI = KLASOR / "data"
OUT = KLASOR / "out"
SEZON = 2026
MIN_DAKIKA = 450  # 5 mac civari; altindaki oyuncularin orani guvenilmez

# 90 dakika basina karsilastirilan alanlar (benzerlik hesabi icin)
OZELLIK = ["totalGoals", "goalAssists", "totalShots", "shotsOnTarget", "totalPasses",
           "effectiveTackles", "interceptions", "foulsCommitted", "foulsSuffered"]

SATIRLAR = [  # (alan, etiket, tur)   tur: p90 = 90 dk basina, yuzde, sayi
    ("totalGoals", "GOL / 90", "p90"),
    ("goalAssists", "ASİST / 90", "p90"),
    ("totalShots", "ŞUT / 90", "p90"),
    ("shotsOnTarget", "İSABETLİ ŞUT / 90", "p90"),
    ("passPct", "PAS İSABETİ", "yuzde"),
    ("effectiveTackles", "TOP ÇALMA / 90", "p90"),
    ("interceptions", "TOP KESME / 90", "p90"),
    ("foulsCommitted", "FAUL / 90", "p90"),
    ("yellowCards", "SARI KART", "sayi"),
    ("redCards", "KIRMIZI KART", "sayi"),
]
KOTU = {"foulsCommitted", "yellowCards", "redCards"}


def sezon_verisi(yenile=False):
    yol = VERI / f"sezon_{SEZON}.json"
    if yol.exists() and not yenile:
        return json.loads(yol.read_text(encoding="utf-8"))
    takimlar = get(f"{API}/teams")["sports"][0]["leagues"][0]["teams"]
    adaylar = []
    for t in takimlar:
        tid, tad = t["team"]["id"], t["team"]["displayName"]
        for a in get(f"{API}/teams/{tid}/roster")["athletes"]:
            poz = a.get("position", {}).get("abbreviation")
            if ROL.get(poz):
                adaylar.append((a["id"], a["displayName"], poz, tad))

    def cek(a):
        aid, ad, poz, tad = a
        try:
            r = get(f"{CORE}/seasons/{SEZON}/types/1/athletes/{aid}/statistics/0")
        except Exception:
            return None
        st = {s["name"]: s["value"] for c in r["splits"]["categories"] for s in c["stats"]}
        if st.get("minutes", 0) < MIN_DAKIKA:
            return None
        return {"id": aid, "ad": ad, "poz": poz, "rol": ROL[poz], "takim": tad, "st": st}

    with ThreadPoolExecutor(8) as ex:
        sonuc = [o for o in ex.map(cek, adaylar) if o]
    VERI.mkdir(exist_ok=True)
    yol.write_text(json.dumps(sonuc, ensure_ascii=False), encoding="utf-8")
    return sonuc


def p90(o, alan):
    return o["st"].get(alan, 0) / o["st"]["minutes"] * 90


def en_benzer_cift(oyuncular, rol=None, yasak=()):
    roller = [rol] if rol else [r for r in ROL_SIRA if r != "Kaleci"]
    en = None
    for r in roller:
        grup = [o for o in oyuncular if o["rol"] == r]
        if len(grup) < 4:
            continue
        # ozellik basina standart sapma ile olcekle
        std = {}
        for f in OZELLIK:
            v = [p90(o, f) for o in grup]
            m = sum(v) / len(v)
            std[f] = (sum((x - m) ** 2 for x in v) / len(v)) ** 0.5 or 1.0
        for i, a in enumerate(grup):
            for b in grup[i + 1:]:
                if a["takim"] == b["takim"] or frozenset((a["id"], b["id"])) in yasak:
                    continue
                dist = sum(((p90(a, f) - p90(b, f)) / std[f]) ** 2 for f in OZELLIK) ** 0.5
                # her ikisi de en az bir "olay" uretmis olsun (cok sessiz ciftler bos kart olur)
                canli = a["st"].get("totalGoals", 0) + a["st"].get("goalAssists", 0) + \
                    b["st"].get("totalGoals", 0) + b["st"].get("goalAssists", 0)
                if canli < 2 and r != "Kaleci":
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


def kart_ciz(rol, a, b, benzerlik, yol):
    W = H = 1080
    img = Image.new("RGB", (W, H), (14, 17, 26))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 8], fill=(46, 134, 222))

    def ortala(y, m, f, renk):
        d.text(((W - d.textlength(m, font=f)) / 2, y), m, font=f, fill=renk)

    ortala(44, "SÜPER LİG  |  SEZON DÜELLOSU", font(30), (160, 168, 188))
    ortala(94, f"{buyuk(rol)} · {SEZON}-{str(SEZON + 1)[2:]}", font(40), (255, 255, 255))
    ortala(150, f"%{benzerlik} BENZER", font(76), (46, 134, 222))

    d.text((70, 262), buyuk(a["ad"]), font=font(44), fill=(255, 255, 255))
    d.text((70, 314), f'{a["takim"]} · {int(a["st"]["minutes"])} dk', font=font(26, False), fill=(160, 168, 188))
    wb = d.textlength(buyuk(b["ad"]), font=font(44))
    d.text((W - 70 - wb, 262), buyuk(b["ad"]), font=font(44), fill=(255, 255, 255))
    t = f'{b["takim"]} · {int(b["st"]["minutes"])} dk'
    d.text((W - 70 - d.textlength(t, font=font(26, False)), 314), t, font=font(26, False), fill=(160, 168, 188))

    y = 372
    for alan, etiket, tur in SATIRLAR:
        va, vb = deger(a, alan, tur), deger(b, alan, tur)
        ta, tb = metin(va, tur), metin(vb, tur)
        iyi = alan not in KOTU
        ca = (255, 214, 10) if iyi and round(va, 2) > round(vb, 2) else (255, 255, 255)
        cb = (255, 214, 10) if iyi and round(vb, 2) > round(va, 2) else (255, 255, 255)
        d.text((120, y), ta, font=font(40), fill=ca)
        d.text((W - 120 - d.textlength(tb, font=font(40)), y), tb, font=font(40), fill=cb)
        ortala(y + 6, etiket, font(28, False), (160, 168, 188))
        d.line([70, y + 54, W - 70, y + 54], fill=(36, 41, 58), width=2)
        y += 56

    ortala(H - 82, "İkisinden hangisini seçerdin?", font(36), (255, 255, 255))
    ortala(H - 40, "Veri: ESPN", font(22, False), (110, 118, 140))
    img.save(yol)


def ada_gore(oyuncular, parca):
    parca = parca.lower()
    bul = [o for o in oyuncular if parca in o["ad"].lower()]
    if not bul:
        raise SystemExit(f"'{parca}' bulunamadi (en az {MIN_DAKIKA} dk oynayanlar listede)")
    return bul[0]


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
        oyuncular = sezon_verisi(yenile)
        a, b = ada_gore(oyuncular, ad[0]), ada_gore(oyuncular, ad[1])
        grup = [o for o in oyuncular if o["rol"] == a["rol"]]
        std = {}
        for f in OZELLIK:
            v = [p90(o, f) for o in grup]
            m = sum(v) / len(v)
            std[f] = (sum((x - m) ** 2 for x in v) / len(v)) ** 0.5 or 1.0
        dist = sum(((p90(a, f) - p90(b, f)) / std[f]) ** 2 for f in OZELLIK) ** 0.5
        benz = max(0, min(100, round(100 * (1 - dist / 6))))
        OUT.mkdir(exist_ok=True)
        yol = OUT / f"sezon_{a['id']}_{b['id']}.png"
        kart_ciz(a["rol"], a, b, benz, yol)
        sonuc = (yol, a["rol"], a, b, benz)
    else:
        sonuc = sezon_kart(rol, yenile)
        if not sonuc:
            raise SystemExit("Uygun oyuncu cifti bulunamadi")
    yol, rol_, a, b, benz = sonuc
    print(f"{rol_}: {a['ad']} ({a['takim']}) vs {b['ad']} ({b['takim']}) | benzerlik %{benz}")
    print(yol)


if __name__ == "__main__":
    main()

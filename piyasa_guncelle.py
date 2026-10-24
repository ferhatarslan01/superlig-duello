"""Piyasa degerlerini guncelle: acik "Football Data from Transfermarkt" veri setinden (CC0).

  python piyasa_guncelle.py

Veri seti: https://github.com/dcaribou/transfermarkt-datasets  (lisans: CC0-1.0)
Sezon oyunculari ad + yas ile eslestirilir; sonuc data/piyasa_degeri.json icinde "otomatik"
anahtarina {espn_oyuncu_id: euro} olarak yazilir. Elle girilen degerler ("elle") korunur.
"""
import csv
import datetime
import gzip
import json
import urllib.request
from collections import defaultdict
from pathlib import Path

import fotograf
import sezon

KLASOR = Path(__file__).parent
URL = "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/players.csv.gz"
INDIRILEN = KLASOR / "data" / "tm_indirilen"
HEDEF = KLASOR / "data" / "piyasa_degeri.json"
YAS_TOLERANS = 1.2


def indir():
    INDIRILEN.mkdir(parents=True, exist_ok=True)
    yol = INDIRILEN / "players.csv.gz"
    req = urllib.request.Request(URL, headers={"User-Agent": "statduel-bot/0.1 (https://github.com/ferhatarslan01/superlig-duello)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        yol.write_bytes(r.read())
    return yol


def yas(dob, bugun):
    try:
        return (bugun - datetime.date.fromisoformat(dob[:10])).days / 365.25
    except Exception:
        return None


def main():
    yol = indir()
    with gzip.open(yol, "rt", encoding="utf-8", newline="") as f:
        satirlar = [x for x in csv.DictReader(f) if x.get("market_value_in_eur")]
    by = defaultdict(list)
    for x in satirlar:
        by[fotograf.norm(x["name"])].append(x)

    bugun = datetime.date.today()
    otomatik, yok = {}, []
    for o in sezon.sezon_verisi():
        adaylar = by.get(fotograf.norm(o["ad"]), [])
        if o.get("yas"):
            adaylar = [x for x in adaylar if (yas(x["date_of_birth"], bugun) or 99) and
                       abs((yas(x["date_of_birth"], bugun) or 99) - o["yas"]) <= YAS_TOLERANS]
        if len({x["player_id"] for x in adaylar}) == 1:
            otomatik[str(o["id"])] = int(float(adaylar[0]["market_value_in_eur"]))
        else:
            yok.append(o["ad"])

    mevcut = json.loads(HEDEF.read_text(encoding="utf-8")) if HEDEF.exists() else {}
    cikti = {
        "_aciklama": "otomatik: {espn_id: euro} (Transfermarkt acik veri seti, CC0); elle: {\"Ad Soyad\": milyon_euro}",
        "_kaynak": "https://github.com/dcaribou/transfermarkt-datasets",
        "_guncelleme": bugun.isoformat(),
        "otomatik": otomatik,
        "elle": mevcut.get("elle", {}),
    }
    HEDEF.write_text(json.dumps(cikti, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(otomatik)} oyuncunun degeri eslesti, {len(yok)} oyuncu eslesmedi")


if __name__ == "__main__":
    main()

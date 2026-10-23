"""Oyuncu fotografi: once Wikimedia Commons (serbest lisans), bulunamazsa TheSportsDB, yoksa silüet.

foto_al(ad, takim) -> (PIL.Image | None, kaynak)   kaynak: "Wikimedia Commons" | "TheSportsDB" | None
"""
import io
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

KLASOR = Path(__file__).parent
CACHE = KLASOR / "data" / "foto_cache"
UA = {"User-Agent": "statduel-bot/0.1 (https://github.com/ferhatarslan01/superlig-duello)"}
FUTBOLCU = "Q937857"


def _get(url, ikili=False, deneme=3):
    for i in range(deneme):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                veri = r.read()
            return veri if ikili else json.loads(veri)
        except Exception:
            if i == deneme - 1:
                raise
            time.sleep(2 * (i + 1))


def norm(s):
    s = unicodedata.normalize("NFKD", s.replace("ı", "i").replace("İ", "I"))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"\b(fk|sk|as|a\.s\.|spor kulubu|futbol kulubu)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _takim_uyar(a, b):
    a, b = norm(a), norm(b)
    return bool(a and b and (a in b or b in a))


def _kare_kirp(im):
    """Yuzler ustte oldugu icin dikey kirpmada ust kismi tut."""
    im = im.convert("RGBA")
    w, h = im.size
    k = min(w, h)
    sol = (w - k) // 2
    ust = 0 if h > w else (h - k) // 2
    return im.crop((sol, ust, sol + k, ust + k))


def _commons(ad, takim):
    s = _get("https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json&language=en"
             "&type=item&limit=8&search=" + urllib.parse.quote(ad))
    ids = [r["id"] for r in s.get("search", [])]
    if not ids:
        return None
    ent = _get("https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props=claims"
               "&ids=" + "|".join(ids))["entities"]
    adaylar = []
    for i in ids:
        c = ent[i].get("claims", {})
        meslek = [x["mainsnak"]["datavalue"]["value"]["id"] for x in c.get("P106", []) if "datavalue" in x["mainsnak"]]
        if FUTBOLCU not in meslek or not c.get("P18"):
            continue
        takimlar = [x["mainsnak"]["datavalue"]["value"]["id"] for x in c.get("P54", []) if "datavalue" in x["mainsnak"]]
        adaylar.append((c["P18"][0]["mainsnak"]["datavalue"]["value"], takimlar))
    if not adaylar:
        return None
    secili = None
    if takim:
        tum = {t for _, ts in adaylar for t in ts}
        if tum:
            etiket = _get("https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props=labels"
                          "&languages=en|tr&ids=" + "|".join(list(tum)[:50]))["entities"]
            for dosya, ts in adaylar:
                if any(_takim_uyar(takim, l["value"]) for t in ts for l in etiket.get(t, {}).get("labels", {}).values()):
                    secili = dosya
                    break
    if secili is None and len(adaylar) == 1:
        secili = adaylar[0][0]
    if secili is None:
        return None
    veri = _get("https://commons.wikimedia.org/wiki/Special:FilePath/"
                + urllib.parse.quote(secili) + "?width=500", ikili=True)
    return Image.open(io.BytesIO(veri))


def _tsdb(ad, takim):
    r = _get("https://www.thesportsdb.com/api/v1/json/123/searchplayers.php?p=" + urllib.parse.quote(ad))
    for p in r.get("player") or []:
        if p.get("strSport") != "Soccer" or not _takim_uyar(takim or "", p.get("strTeam") or ""):
            continue
        url = p.get("strCutout") or p.get("strThumb")
        if url:
            return Image.open(io.BytesIO(_get(url + "/small" if "/small" not in url else url, ikili=True)))
    return None


def foto_al(ad, takim=None):
    CACHE.mkdir(parents=True, exist_ok=True)
    slug = norm(ad).replace(" ", "-") + "__" + norm(takim or "").replace(" ", "-")
    png, meta = CACHE / f"{slug}.png", CACHE / f"{slug}.json"
    if meta.exists():
        k = json.loads(meta.read_text(encoding="utf-8")).get("kaynak")
        return (Image.open(png).convert("RGBA") if k and png.exists() else None), k
    for kaynak, fn in (("Wikimedia Commons", _commons), ("TheSportsDB", _tsdb)):
        try:
            im = fn(ad, takim)
        except Exception:
            im = None
        if im is not None:
            im = _kare_kirp(im)
            im.save(png)
            meta.write_text(json.dumps({"kaynak": kaynak}), encoding="utf-8")
            return im, kaynak
    meta.write_text(json.dumps({"kaynak": None}), encoding="utf-8")
    return None, None


def daire_yapistir(kart, foto, x, y, d, renk=(230, 57, 70)):
    """x,y sol-ust; d cap. foto None ise silüet cizer."""
    S = 4  # kenar yumusatma icin buyuk cizim
    zemin = Image.new("RGBA", (d * S, d * S), (0, 0, 0, 0))
    zd = ImageDraw.Draw(zemin)
    zd.ellipse([0, 0, d * S - 1, d * S - 1], fill=(30, 36, 52, 255))
    if foto is not None:
        f = foto.resize((d * S, d * S), Image.LANCZOS)
        zemin.alpha_composite(f)
    else:
        sil = (86, 96, 122, 255)
        zd.ellipse([d * S * 0.34, d * S * 0.18, d * S * 0.66, d * S * 0.50], fill=sil)
        zd.ellipse([d * S * 0.18, d * S * 0.56, d * S * 0.82, d * S * 1.20], fill=sil)
    maske = Image.new("L", (d * S, d * S), 0)
    ImageDraw.Draw(maske).ellipse([0, 0, d * S - 1, d * S - 1], fill=255)
    zemin.putalpha(maske)
    zd2 = ImageDraw.Draw(zemin)
    zd2.ellipse([2 * S, 2 * S, d * S - 2 * S, d * S - 2 * S], outline=renk + (255,), width=3 * S)
    kart.paste(zemin.resize((d, d), Image.LANCZOS), (x, y), zemin.resize((d, d), Image.LANCZOS))

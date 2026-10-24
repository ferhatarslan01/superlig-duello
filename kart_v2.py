"""Okunurluk odakli kart cizici: hem sezon karsilastirmasi hem mac sonu duellosu icin.

Tasarim ilkeleri: az satir (7), buyuk yazi, sol oyuncu = kirmizi, sag oyuncu = mavi,
kazanan deger oyuncunun renginde dolu kutuyla gosterilir (renk korlugune dayanikli).
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw

import fotograf
from duello import HESAP, buyuk, font, sigdir

W = H = 1080
ARKA = (14, 17, 26)
PANEL = (22, 27, 40)
KIRMIZI = (230, 57, 70)
MAVI = (46, 134, 222)
BEYAZ = (255, 255, 255)
ETIKET = (196, 203, 220)   # etiketler: koyu zeminde 10:1 kontrast
SOLUK = (150, 158, 180)
CIZGI = (34, 40, 58)

# ESPN takim adlari Turkce karaktersiz geliyor; gosterim icin duzeltilir
TAKIM_ADLARI = {
    "kasimpasa": "Kasımpaşa", "besiktas": "Beşiktaş", "fenerbahce": "Fenerbahçe",
    "genclerbirligi": "Gençlerbirliği", "caykur rizespor": "Çaykur Rizespor", "goztepe": "Göztepe",
    "istanbul basaksehir": "İstanbul Başakşehir", "eyupspor": "Eyüpspor", "corum fk": "Çorum FK",
    "galatasaray": "Galatasaray", "trabzonspor": "Trabzonspor", "samsunspor": "Samsunspor",
    "konyaspor": "Konyaspor", "alanyaspor": "Alanyaspor", "gaziantep fk": "Gaziantep FK",
    "kocaelispor": "Kocaelispor", "amed sfk": "Amed SFK", "erzurum bb": "Erzurum BB",
}


PIYASA = None


def _piyasa_yukle():
    global PIYASA
    if PIYASA is None:
        yol = Path(__file__).parent / "data" / "piyasa_degeri.json"
        try:
            ham = json.loads(yol.read_text(encoding="utf-8"))
        except Exception:
            ham = {}
        PIYASA = {"otomatik": ham.get("otomatik", {}),
                  "elle": {fotograf.norm(k): float(v) * 1_000_000 for k, v in ham.get("elle", {}).items()}}
    return PIYASA


def piyasa_degeri(o):
    """o: {"id", "ad"}. Once elle girilen deger (mn euro), yoksa Transfermarkt acik veri seti. Yoksa None."""
    p = _piyasa_yukle()
    eur = p["elle"].get(fotograf.norm(o["ad"]))
    if eur is None and o.get("id") is not None:
        eur = p["otomatik"].get(str(o["id"]))
    if not eur:
        return None
    if eur >= 1_000_000:
        mn = f"{eur / 1_000_000:.1f}".rstrip("0").rstrip(".").replace(".", ",")
        return f"€{mn} mn"
    return f"€{round(eur / 1000)} bin"


def takim_adi(ad):
    return TAKIM_ADLARI.get(fotograf.norm(ad).replace("  ", " "), ad)


YUZDE_ALANLARI = {"passPct", "saveRate"}


def _deger(o, alan):
    st = o["st"]
    if alan == "saveRate":   # kurtaris orani = kurtaris / (kurtaris + yenen gol); veri yoksa None
        n = st.get("saves", 0) + st.get("goalsConceded", 0)
        return st.get("saves", 0) / n * 100 if n else None
    if alan == "passPct":
        return st.get("passPct", 0) * 100
    return st.get(alan, 0)


def _metin(v, alan):
    if v is None:
        return "–"
    return f"%{round(v)}" if alan in YUZDE_ALANLARI else str(int(v))


def ciz(yol, ust, alt_baslik, a, b, satirlar, soru, kotu=(), p_alt=None):
    """a, b: {"ad","yas","takim","satir1","satir2","st", ...}; satirlar: [(alan, etiket)]."""
    img = Image.new("RGB", (W, H), ARKA)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W // 2, 8], fill=KIRMIZI)
    d.rectangle([W // 2, 0, W, 8], fill=MAVI)

    def ortala(y, m, f, renk, x0=0, x1=W):
        d.text((x0 + (x1 - x0 - d.textlength(m, font=f)) / 2, y), m, font=f, fill=renk)

    ortala(24, ust, font(28), SOLUK)
    ortala(62, alt_baslik, sigdir(d, alt_baslik, 980, 46), BEYAZ)

    # oyuncu bloklari
    D = 190
    for o, cx, renk in ((a, 270, KIRMIZI), (b, 810, MAVI)):
        o["_fotoim"], o["_foto"] = fotograf.foto_al(o["ad"], o["takim"])
        fotograf.daire_yapistir(img, o["_fotoim"], cx - D // 2, 128, D, renk=renk)
        ad = buyuk(o["ad"])
        ortala(330, ad, sigdir(d, ad, 500, 52), BEYAZ, cx - 270, cx + 270)
        l1 = (f'{o["yas"]} yaş · ' if o.get("yas") else "") + takim_adi(o["takim"])
        ortala(392, l1, sigdir(d, l1, 500, 30, False, 20), ETIKET, cx - 270, cx + 270)
        pd = piyasa_degeri(o)
        o["_deger"] = pd
        s2 = " · ".join(x for x in (o.get("satir2"), (f"Değer: {pd}" if pd else None)) if x)
        if s2:
            ortala(428, s2, sigdir(d, s2, 520, 28, False, 20), SOLUK, cx - 270, cx + 270)
    # VS rozeti
    d.ellipse([W / 2 - 50, 172, W / 2 + 50, 272], fill=ARKA, outline=BEYAZ, width=4)
    ortala(188, "VS", font(52), BEYAZ)

    # istatistik satirlari
    y0 = 478
    h = 68 if len(satirlar) >= 7 else 90   # az satirda satirlar genisler
    off = (h - 68) / 2
    fn, fe = font(50), font(30, False)
    y = y0
    for alan, etiket in satirlar:
        va, vb = _deger(a, alan), _deger(b, alan)
        ta, tb = _metin(va, alan), _metin(vb, alan)
        iyi = alan not in kotu and va is not None and vb is not None
        kazanan_a = iyi and round(va, 2) > round(vb, 2)
        kazanan_b = iyi and round(vb, 2) > round(va, 2)
        for t, cx, renk, kazandi in ((ta, 200, KIRMIZI, kazanan_a), (tb, W - 200, MAVI, kazanan_b)):
            w = d.textlength(t, font=fn)
            if kazandi:
                pw = max(w + 44, 120)
                d.rounded_rectangle([cx - pw / 2, y + off + 2, cx + pw / 2, y + off + 62], 14, fill=renk)
            d.text((cx - w / 2, y + off - 1), t, font=fn, fill=BEYAZ)
        ortala(y + off + 14, etiket, sigdir(d, etiket, 380, 30, False, 22), ETIKET)
        d.line([60, y + h - 3, W - 60, y + h - 3], fill=CIZGI, width=2)
        y += h

    ortala(H - 112, HESAP, font(54), BEYAZ)
    kaynaklar = sorted({o["_foto"] for o in (a, b) if o.get("_foto")})
    alt = "Veri: ESPN" + ("  ·  Değer: Transfermarkt" if any(o.get("_deger") for o in (a, b)) else "") +         (f"  ·  Foto: {', '.join(kaynaklar)}" if kaynaklar else "")
    ortala(H - 52, alt, font(24, False), SOLUK)
    img.save(yol)

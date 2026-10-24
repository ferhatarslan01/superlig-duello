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


def piyasa_degeri(ad):
    """data/piyasa_degeri.json: {"Oyuncu Adi": milyon_euro}. Dosya yoksa/oyuncu yoksa None."""
    global PIYASA
    if PIYASA is None:
        yol = Path(__file__).parent / "data" / "piyasa_degeri.json"
        try:
            ham = json.loads(yol.read_text(encoding="utf-8"))
        except Exception:
            ham = {}
        PIYASA = {fotograf.norm(k): v for k, v in ham.items() if not k.startswith("_")}
    v = PIYASA.get(fotograf.norm(ad))
    if v is None:
        return None
    return f"€{v:.1f} mn".replace(".0 mn", " mn").replace(".", ",") if v >= 1 else f"€{round(v * 1000)} bin"


def takim_adi(ad):
    return TAKIM_ADLARI.get(fotograf.norm(ad).replace("  ", " "), ad)


def _deger(o, alan):
    if alan == "passPct":
        return o["st"].get("passPct", 0) * 100
    return o["st"].get(alan, 0)


def _metin(v, alan):
    return f"%{round(v)}" if alan == "passPct" else str(int(v))


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
        s2 = " · ".join(x for x in (o.get("satir2"), (f"Değer: {piyasa_degeri(o['ad'])}" if piyasa_degeri(o["ad"]) else None)) if x)
        if s2:
            ortala(428, s2, sigdir(d, s2, 520, 28, False, 20), SOLUK, cx - 270, cx + 270)
    # VS rozeti
    d.ellipse([W / 2 - 50, 172, W / 2 + 50, 272], fill=ARKA, outline=BEYAZ, width=4)
    ortala(188, "VS", font(52), BEYAZ)

    # istatistik satirlari
    y, h = 478, 68
    fn, fe = font(50), font(30, False)
    for alan, etiket in satirlar:
        va, vb = _deger(a, alan), _deger(b, alan)
        ta, tb = _metin(va, alan), _metin(vb, alan)
        iyi = alan not in kotu
        kazanan_a = iyi and round(va, 2) > round(vb, 2)
        kazanan_b = iyi and round(vb, 2) > round(va, 2)
        for t, cx, renk, kazandi in ((ta, 200, KIRMIZI, kazanan_a), (tb, W - 200, MAVI, kazanan_b)):
            w = d.textlength(t, font=fn)
            if kazandi:
                pw = max(w + 44, 120)
                d.rounded_rectangle([cx - pw / 2, y + 2, cx + pw / 2, y + h - 6], 14, fill=renk)
            d.text((cx - w / 2, y - 1), t, font=fn, fill=BEYAZ)
        ortala(y + 14, etiket, fe, ETIKET)
        d.line([60, y + h - 3, W - 60, y + h - 3], fill=CIZGI, width=2)
        y += h

    ortala(H - 112, HESAP, font(54), BEYAZ)
    kaynaklar = sorted({o["_foto"] for o in (a, b) if o.get("_foto")})
    alt = "Veri: ESPN" + (f"  ·  Foto: {', '.join(kaynaklar)}" if kaynaklar else "")
    ortala(H - 52, alt, font(24, False), SOLUK)
    img.save(yol)

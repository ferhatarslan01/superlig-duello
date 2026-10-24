"""Okunurluk odakli kart cizici: hem sezon karsilastirmasi hem mac sonu duellosu icin.

Tasarim ilkeleri: az satir (7), buyuk yazi, sol oyuncu = kirmizi, sag oyuncu = mavi,
kazanan deger oyuncunun renginde dolu kutuyla gosterilir (renk korlugune dayanikli).
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw

import fotograf
import satirlar
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


YUZDE_ALANLARI = {"passPct", "saveRate", "shotAcc", "tackleSuccess"}


def _oran(pay, payda):
    return pay / payda * 100 if payda else None


def _deger(o, alan):
    st = o["st"]
    g = st.get
    if alan == "saveRate":      # kurtaris / (kurtaris + yenen gol)
        return _oran(g("saves", 0), g("saves", 0) + g("goalsConceded", 0))
    if alan == "shotAcc":       # isabetli sut / sut
        return _oran(g("shotsOnTarget", 0), g("totalShots", 0))
    if alan == "tackleSuccess":  # basarili top calma / top calma denemesi
        return _oran(g("effectiveTackles", 0), g("totalTackles", 0))
    if alan == "minPerGoal":    # gol basina dakika (gol yoksa None)
        return g("minutes", 0) / g("totalGoals", 0) if g("totalGoals", 0) else None
    if alan == "gcPerMatch":    # mac basina yenen gol
        return g("goalsConceded", 0) / g("appearances", 0) if g("appearances", 0) else None
    if alan == "passPct":
        return g("passPct", 0) * 100
    return g(alan, 0)


def _metin(v, alan):
    if v is None:
        return "–"
    if alan in YUZDE_ALANLARI:
        return f"%{round(v)}"
    if alan in ("gcPerMatch", "puan"):
        return f"{v:.1f}".replace(".", ",")
    return str(int(round(v)))


def _kazanan(alan, va, vb, kotu=()):
    """(a_kazandi, b_kazandi). Vurgusuz alanlarda kimse; dusuk-iyi alanlarda dusuk olan; None = veri yok."""
    if alan in kotu or alan in satirlar.VURGUSUZ:
        return False, False
    if alan in satirlar.DUSUK_IYI:
        if va is None and vb is None:
            return False, False
        x = float("inf") if va is None else round(va, 2)
        y = float("inf") if vb is None else round(vb, 2)
        return x < y, y < x
    if va is None or vb is None:
        return False, False
    return round(va, 2) > round(vb, 2), round(vb, 2) > round(va, 2)


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
    # her iki oyuncuda da verisi olmayan puan satirini gizle
    satirlar = [r for r in satirlar if not (r[0] == "puan" and _deger(a, "puan") is None and _deger(b, "puan") is None)]
    n = len(satirlar)
    h = 90 if n < 7 else min(68, 470 // n)     # az satirda genis, cok satirda dar satir
    off = max(0, (h - 68) / 2)
    kucuk = h < 64
    fn, fe = font(44 if kucuk else 50), font(28 if kucuk else 30, False)
    pill_alt = 56 if kucuk else 62
    y = y0
    for alan, etiket in satirlar:
        va, vb = _deger(a, alan), _deger(b, alan)
        ta, tb = _metin(va, alan), _metin(vb, alan)
        kazanan_a, kazanan_b = _kazanan(alan, va, vb, kotu)
        for t, cx, renk, kazandi in ((ta, 200, KIRMIZI, kazanan_a), (tb, W - 200, MAVI, kazanan_b)):
            w = d.textlength(t, font=fn)
            if kazandi:
                pw = max(w + 44, 120)
                d.rounded_rectangle([cx - pw / 2, y + off + 2, cx + pw / 2, y + off + pill_alt], 14, fill=renk)
            d.text((cx - w / 2, y + off - (0 if kucuk else 1)), t, font=fn, fill=BEYAZ)
        ortala(y + off + (11 if kucuk else 14), etiket, sigdir(d, etiket, 380, 28 if kucuk else 30, False, 22), ETIKET)
        d.line([60, y + h - 3, W - 60, y + h - 3], fill=CIZGI, width=2)
        y += h

    ortala(H - 112, HESAP, font(54), BEYAZ)
    kaynaklar = sorted({o["_foto"] for o in (a, b) if o.get("_foto")})
    alt = "Veri: ESPN" + ("  ·  Değer: Transfermarkt" if any(o.get("_deger") for o in (a, b)) else "") +         ("  ·  Puan: APIfootball" if any(_deger(o, "puan") for o in (a, b)) else "") +         (f"  ·  Foto: {', '.join(kaynaklar)}" if kaynaklar else "")
    ortala(H - 52, alt, font(24, False), SOLUK)
    img.save(yol)

"""Sezon karsilastirma karti tasarim denemeleri (A, B, C).

  python tasarim.py "Salah" "Trossard"      # tasarimlari out/ornek_A.png ... _D olarak uretir
"""
import sys

from PIL import Image, ImageDraw

import fotograf
import sablon
import sezon
from duello import HESAP, buyuk, font, sigdir

W = H = 1080
ARKA = (14, 17, 26)
MAVI = (46, 134, 222)
SARI = (255, 214, 10)
BEYAZ = (255, 255, 255)
GRI = (160, 168, 188)
SOLUK = (110, 118, 140)
CIZGI = (36, 41, 58)

# oyuncuya gosterilecek sade mevki (sadece B tasariminda; "yan orta saha" gibi ic adlar yazilmaz)
SADE_MEVKI = {"Kaleci": "KALECİ", "Stoper": "STOPER", "Bek": "BEK", "Kanat": "KANAT", "Forvet": "FORVET",
              "Defansif orta saha": "ORTA SAHA", "Merkez orta saha": "ORTA SAHA", "Yan orta saha": "ORTA SAHA",
              "Ofansif orta saha": "ORTA SAHA"}


def _deger(o, alan, tur):
    if tur == "yuzde":
        return o["st"].get("passPct", 0) * 100
    return o["st"].get(alan, 0)


def _metin(v, tur):
    return f"%{round(v)}" if tur == "yuzde" else str(int(v))


def _foto(o):
    o["_fotoim"], o["_foto"] = fotograf.foto_al(o["ad"], o["takim"])


def _alt_yazi(d, a, b):
    kaynaklar = sorted({o["_foto"] for o in (a, b) if o.get("_foto")})
    alt = f"{HESAP}  ·  Veri: ESPN" + (f"  ·  Foto: {', '.join(kaynaklar)}" if kaynaklar else "")
    d.text(((W - d.textlength(alt, font=font(22, False))) / 2, H - 38), alt, font=font(22, False), fill=SOLUK)


def _ortala(d, y, m, f, renk, x0=0, x1=W):
    d.text((x0 + (x1 - x0 - d.textlength(m, font=f)) / 2, y), m, font=f, fill=renk)


def _yas_takim(o):
    return (f'{o["yas"]} yaş · ' if o.get("yas") else "") + o["takim"]


def _satirlar_klasik(d, y, a, b, h=50, f=36):
    for alan, etiket, tur in sezon.SATIRLAR:
        va, vb = _deger(a, alan, tur), _deger(b, alan, tur)
        iyi = alan not in sezon.KOTU
        ca = SARI if iyi and round(va, 2) > round(vb, 2) else BEYAZ
        cb = SARI if iyi and round(vb, 2) > round(va, 2) else BEYAZ
        ta, tb = _metin(va, tur), _metin(vb, tur)
        d.text((120, y), ta, font=font(f), fill=ca)
        d.text((W - 120 - d.textlength(tb, font=font(f)), y), tb, font=font(f), fill=cb)
        _ortala(d, y + 5, etiket, font(27, False), GRI)
        d.line([70, y + h - 4, W - 70, y + h - 4], fill=CIZGI, width=2)
        y += h
    return y


def _satirlar_bar(d, y, a, b, h=52):
    """Her istatistik icin merkezden disa dogru oransal cubuk; ustte etiket."""
    orta, yari = W // 2, 440
    for alan, etiket, tur in sezon.SATIRLAR:
        va, vb = _deger(a, alan, tur), _deger(b, alan, tur)
        mx = max(va, vb, 1e-9)
        iyi = alan not in sezon.KOTU
        ca = SARI if iyi and round(va, 2) > round(vb, 2) else BEYAZ
        cb = SARI if iyi and round(vb, 2) > round(va, 2) else BEYAZ
        _ortala(d, y - 4, etiket, font(22, False), GRI)
        by = y + 24
        d.rounded_rectangle([orta - 6 - int(yari * 0.62 * va / mx), by, orta - 6, by + 14], 5, fill=ca if ca == SARI else (92, 104, 140))
        d.rounded_rectangle([orta + 6, by, orta + 6 + int(yari * 0.62 * vb / mx), by + 14], 5, fill=cb if cb == SARI else (92, 104, 140))
        ta, tb = _metin(va, tur), _metin(vb, tur)
        d.text((70, y + 8), ta, font=font(34), fill=ca)
        d.text((W - 70 - d.textlength(tb, font=font(34)), y + 8), tb, font=font(34), fill=cb)
        y += h
    return y


def stil_a(a, b, yol):
    """A: buyuk yuvarlak fotograflar, ortada VS; foto altinda ad + yas + takim. Mevki yok."""
    img = Image.new("RGB", (W, H), ARKA)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 8], fill=MAVI)
    _ortala(d, 34, "SÜPER LİG  |  SEZON KARŞILAŞTIRMASI", font(30), GRI)
    _ortala(d, 76, "2026-27", font(34), BEYAZ)
    D = 190
    for o, cx in ((a, 235), (b, W - 235)):
        _foto(o)
        fotograf.daire_yapistir(img, o["_fotoim"], cx - D // 2, 128, D, renk=MAVI)
        _ortala(d, 330, buyuk(o["ad"]), sigdir(d, buyuk(o["ad"]), 430, 44), BEYAZ, cx - 235, cx + 235)
        _ortala(d, 382, _yas_takim(o), sigdir(d, _yas_takim(o), 430, 26, False, 18), GRI, cx - 235, cx + 235)
    _ortala(d, 190, "VS", font(86), MAVI)
    _satirlar_klasik(d, 438, a, b, h=50, f=36)
    _alt_yazi(d, a, b)
    img.save(yol)


def stil_b(a, b, yol):
    """B: iki ayri panel; panelde foto, ad, yas, takim ve sade mevki etiketi."""
    img = Image.new("RGB", (W, H), ARKA)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 8], fill=MAVI)
    _ortala(d, 30, "SÜPER LİG  |  SEZON KARŞILAŞTIRMASI  |  2026-27", font(28), GRI)
    for o, x0 in ((a, 50), (b, 560)):
        d.rounded_rectangle([x0, 84, x0 + 470, 396], 26, fill=(22, 27, 40), outline=(40, 48, 70), width=2)
        _foto(o)
        fotograf.daire_yapistir(img, o["_fotoim"], x0 + 235 - 70, 100, 140, renk=MAVI)
        _ortala(d, 252, buyuk(o["ad"]), sigdir(d, buyuk(o["ad"]), 430, 40), BEYAZ, x0, x0 + 470)
        _ortala(d, 298, _yas_takim(o), sigdir(d, _yas_takim(o), 430, 25, False, 18), GRI, x0, x0 + 470)
        etiket = SADE_MEVKI.get(o["rol"], "")
        if etiket:
            f = font(22)
            w = d.textlength(etiket, font=f) + 36
            d.rounded_rectangle([x0 + 235 - w / 2, 340, x0 + 235 + w / 2, 376], 18, fill=MAVI)
            _ortala(d, 345, etiket, f, BEYAZ, x0, x0 + 470)
    d.ellipse([W / 2 - 34, 214, W / 2 + 34, 282], fill=ARKA, outline=MAVI, width=3)
    _ortala(d, 226, "VS", font(36), MAVI)
    _satirlar_klasik(d, 424, a, b, h=51, f=36)
    _alt_yazi(d, a, b)
    img.save(yol)


def stil_c(a, b, yol):
    """C: cok buyuk fotograflar ortaya yakin, ad/yas altta; istatistikler karsilastirma cubuklariyla."""
    img = Image.new("RGB", (W, H), ARKA)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 8], fill=MAVI)
    _ortala(d, 28, "SÜPER LİG  ·  SEZON KARŞILAŞTIRMASI  ·  2026-27", font(26), GRI)
    D = 250
    for o, cx in ((a, 300), (b, W - 300)):
        _foto(o)
        fotograf.daire_yapistir(img, o["_fotoim"], cx - D // 2, 70, D, renk=MAVI)
        _ortala(d, 330, buyuk(o["ad"]), sigdir(d, buyuk(o["ad"]), 480, 46), BEYAZ, cx - 270, cx + 270)
        _ortala(d, 384, _yas_takim(o), sigdir(d, _yas_takim(o), 480, 26, False, 18), GRI, cx - 270, cx + 270)
    d.ellipse([W / 2 - 44, 170, W / 2 + 44, 258], fill=MAVI)
    _ortala(d, 186, "VS", font(48), BEYAZ)
    _satirlar_bar(d, 440, a, b, h=52)
    _alt_yazi(d, a, b)
    img.save(yol)


STILLER = {"A": stil_a, "B": stil_b, "C": stil_c,
           "D": lambda a, b, yol: sablon.ciz(a["rol"], a, b, yol)}  # D: StatDuel 4:5 sablonu (sezon karti)

if __name__ == "__main__":
    oy = sezon.sezon_verisi()
    a, b = sezon.ada_gore(oy, sys.argv[1]), sezon.ada_gore(oy, sys.argv[2])
    sezon.OUT.mkdir(exist_ok=True)
    for k, fn in STILLER.items():
        yol = sezon.OUT / f"ornek_{k}.png"
        fn(a, b, yol)
        print(yol)

"""Haftalik Super Lig liderleri: gol krali, asist krali, kartlar (sari + kirmizi).

Her biri 1080x1080 bir kart (ilk 5). Ayni salı gonderisinde uc gorsel olarak gider.
"""
from pathlib import Path

from PIL import Image, ImageDraw

import fotograf
import sezon
from duello import HESAP, buyuk, font, sigdir
from kart_v2 import ARKA, BEYAZ, ETIKET, KIRMIZI, MAVI, PANEL, SOLUK, CIZGI, takim_adi

W = H = 1080
SARI = (255, 214, 10)
ILK_N = 5


def _sirala(oyuncular, anahtar, n=ILK_N):
    return sorted(oyuncular, key=anahtar)[:n]


def liderler():
    """{"gol": [...], "asist": [...], "kart": [...]} ; her liste en fazla 5 oyuncu."""
    oy = sezon.sezon_verisi()
    g = lambda o, k: o["st"].get(k, 0)  # noqa: E731
    return {
        "gol": _sirala([o for o in oy if g(o, "totalGoals") > 0],
                       lambda o: (-g(o, "totalGoals"), -g(o, "goalAssists"), g(o, "minutes"))),
        "asist": _sirala([o for o in oy if g(o, "goalAssists") > 0],
                         lambda o: (-g(o, "goalAssists"), -g(o, "totalGoals"), g(o, "minutes"))),
        # kart siralamasi: toplam kart (sari + kirmizi), esitlikte kirmizi cok olan, sonra az dakika
        "kart": _sirala([o for o in oy if g(o, "yellowCards") + g(o, "redCards") > 0],
                        lambda o: (-(g(o, "yellowCards") + g(o, "redCards")), -g(o, "redCards"), g(o, "minutes"))),
    }


def _kart_ikonu(d, x, y, renk, w=34, h=46):
    d.rounded_rectangle([x, y, x + w, y + h], 6, fill=renk)


def ciz(tur, liste, yol):
    basliklar = {"gol": ("GOL KRALLIĞI", KIRMIZI), "asist": ("ASİST KRALLIĞI", MAVI),
                 "kart": ("KART LİDERLERİ", SARI)}
    baslik, renk = basliklar[tur]
    img = Image.new("RGB", (W, H), ARKA)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 8], fill=renk)

    def ortala(y, m, f, c):
        d.text(((W - d.textlength(m, font=f)) / 2, y), m, font=f, fill=c)

    ortala(24, "SÜPER LİG  ·  2026-27 SEZONU", font(28), SOLUK)
    ortala(62, baslik, font(84), renk)

    y0, h = 178, 148
    kaynaklar = set()
    for i, o in enumerate(liste):
        y = y0 + i * h
        if i == 0:
            d.rounded_rectangle([40, y + 4, W - 40, y + h - 6], 24, fill=PANEL)
        d.text((62, y + 30), str(i + 1), font=font(78), fill=renk if i == 0 else SOLUK)
        im, kaynak = fotograf.foto_al(o["ad"], o["takim"])
        if kaynak:
            kaynaklar.add(kaynak)
        fotograf.daire_yapistir(img, im, 150, y + 16, 112, renk=renk)
        ad = buyuk(o["ad"])
        d.text((290, y + 22), ad, font=sigdir(d, ad, 450, 50), fill=BEYAZ)
        alt = f'{takim_adi(o["takim"])} · {int(o["st"].get("appearances", 0))} maç'
        d.text((290, y + 82), alt, font=sigdir(d, alt, 450, 30, False, 20), fill=ETIKET)
        st = o["st"]
        if tur == "kart":
            sari, kirm = int(st.get("yellowCards", 0)), int(st.get("redCards", 0))
            fn = font(70)
            x = W - 70
            for deger, c in ((kirm, KIRMIZI), (sari, SARI)):
                t = str(deger)
                x -= d.textlength(t, font=fn)
                d.text((x, y + 34), t, font=fn, fill=BEYAZ)
                x -= 48
                _kart_ikonu(d, x, y + 52, c)
                x -= 34
        else:
            deger = int(st.get("totalGoals" if tur == "gol" else "goalAssists", 0))
            t = str(deger)
            d.text((W - 70 - d.textlength(t, font=font(104)), y + 6), t, font=font(104), fill=BEYAZ)
        if i < len(liste) - 1:
            d.line([60, y + h - 3, W - 60, y + h - 3], fill=CIZGI, width=2)

    ortala(H - 108, HESAP, font(50), BEYAZ)
    alt = "Veri: ESPN" + (f"  ·  Foto: {', '.join(sorted(kaynaklar))}" if kaynaklar else "")
    ortala(H - 42, alt, font(24, False), SOLUK)
    img.save(yol)


def uret(klasor=None):
    """Uc karti uretir; (yollar, liderler) doner."""
    klasor = Path(klasor or sezon.OUT)
    klasor.mkdir(exist_ok=True)
    l = liderler()
    yollar = []
    for tur in ("gol", "asist", "kart"):
        yol = klasor / f"lider_{tur}.png"
        ciz(tur, l[tur], yol)
        yollar.append(yol)
    return yollar, l


if __name__ == "__main__":
    yollar, _ = uret()
    for y in yollar:
        print(y)

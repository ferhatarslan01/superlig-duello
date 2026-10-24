"""StatDuel logo denemeleri (PIL, 3x ornekleme ile pürüzsüz).

  python logo/logo.py      # logo/out/logo_1.png, logo_2.png, logo_3.png
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

KLASOR = Path(__file__).parent
FONT = KLASOR.parent / "fonts" / "BarlowCondensed-SemiBold.ttf"
OUT = KLASOR / "out"

ARKA = (14, 17, 26)
KIRMIZI = (230, 57, 70)
MAVI = (46, 134, 222)
SARI = (255, 214, 10)
BEYAZ = (255, 255, 255)
GRI = (160, 168, 188)
N = 1080
S = 3  # ornekleme


def f(px):
    return ImageFont.truetype(str(FONT), int(px * S))


def tuval(arka=ARKA):
    return Image.new("RGB", (N * S, N * S), arka)


def kaydet(im, ad, arka=ARKA):
    OUT.mkdir(exist_ok=True)
    im.resize((N, N), Image.LANCZOS).save(OUT / ad)


def yaz_ortala(d, cx, y, metin, fnt, renk):
    w = d.textlength(metin, font=fnt)
    d.text((cx * S - w / 2, y * S), metin, font=fnt, fill=renk)


def yaz_iki_renk(d, cx, y, a, b, fnt, ra, rb, aralik=0):
    wa, wb = d.textlength(a, font=fnt), d.textlength(b, font=fnt)
    x = cx * S - (wa + wb + aralik * S) / 2
    d.text((x, y * S), a, font=fnt, fill=ra)
    d.text((x + wa + aralik * S, y * S), b, font=fnt, fill=rb)


def p(x, y):
    return (x * S, y * S)


def logo_1():
    """Karsilikli iki istatistik cubugu kumesi + ortada sari top; altinda yazi."""
    im = tuval()
    d = ImageDraw.Draw(im)
    taban = 600
    genislik, bosluk = 70, 22
    # sol (kirmizi) ve sag (mavi) cubuklar, merkeze dogru yukselen/alcalan
    sol = [210, 300, 390]      # yukseklikler
    sag = [390, 300, 210]
    x0 = 540 - 40 - 3 * genislik - 2 * bosluk
    for i, h in enumerate(sol):
        x = x0 + i * (genislik + bosluk)
        d.rounded_rectangle([x * S, (taban - h) * S, (x + genislik) * S, taban * S], 16 * S, fill=KIRMIZI)
    x1 = 540 + 40
    for i, h in enumerate(sag):
        x = x1 + i * (genislik + bosluk)
        d.rounded_rectangle([x * S, (taban - h) * S, (x + genislik) * S, taban * S], 16 * S, fill=MAVI)
    # ortada top
    d.ellipse([p(540 - 26, taban - 470), p(540 + 26, taban - 418)], fill=SARI)
    d.line([p(540, taban - 395), p(540, taban + 6)], fill=(60, 68, 92), width=4 * S)
    yaz_iki_renk(d, 540, 668, "STAT", "DUEL", f(170), BEYAZ, MAVI, aralik=10)
    yaz_ortala(d, 540, 862, "SÜPER LİG KARŞILAŞTIRMALARI", f(34), GRI)
    return im


def logo_2():
    """Yuvarlak rozet: kirmizi/mavi bolunmus halka, ortada SD monogramı ve alt cubuklar."""
    im = tuval()
    d = ImageDraw.Draw(im)
    cx = cy = 540
    R = 400
    # iki yarim halka (ustte cakisan diyagonal kesim hissi icin acili)
    kutu = [p(cx - R, cy - R), p(cx + R, cy + R)]
    d.pieslice(kutu, 90, 270, fill=KIRMIZI)
    d.pieslice(kutu, 270, 450, fill=MAVI)
    ic = R - 46
    d.ellipse([p(cx - ic, cy - ic), p(cx + ic, cy + ic)], fill=ARKA)
    yaz_iki_renk(d, cx, 262, "S", "D", f(330), KIRMIZI, MAVI, aralik=96)
    # harfler arasinda ince sari duello cizgisi (halka ile birlesir)
    d.rounded_rectangle([p(cx - 5, cy - R + 14), p(cx + 5, cy + R - 14)], 4 * S, fill=SARI)
    for i, (h, renk) in enumerate([(40, KIRMIZI), (62, KIRMIZI), (84, KIRMIZI), (84, MAVI), (62, MAVI), (40, MAVI)]):
        x = 336 + i * 66 + (14 if i >= 3 else -14)
        d.rounded_rectangle([p(x, 818 - h), p(x + 44, 818)], 9 * S, fill=renk)
    return im


def logo_3():
    """Minimal 'VS': iki egik blok bir V olusturur; ustte sari nokta. Altinda yazi."""
    im = tuval()
    d = ImageDraw.Draw(im)
    # sol blok: / yonunde kirmizi, sag blok: \ yonunde mavi; ortada V olusturacak sekilde birlesir
    tabanx, taban_y, ust_y = 540, 640, 230
    kal = 150
    sol = [p(tabanx - 320, ust_y), p(tabanx - 320 + kal, ust_y), p(tabanx + 8, taban_y), p(tabanx - 142, taban_y)]
    sag = [p(tabanx + 320, ust_y), p(tabanx + 320 - kal, ust_y), p(tabanx - 8, taban_y), p(tabanx + 142, taban_y)]
    d.polygon(sol, fill=KIRMIZI)
    d.polygon(sag, fill=MAVI)
    # sari top, V'nin ortasinda
    d.ellipse([p(540 - 34, 212 - 34 + 40), p(540 + 34, 212 + 34 + 40)], fill=SARI)
    yaz_iki_renk(d, 540, 700, "STAT", "DUEL", f(176), BEYAZ, KIRMIZI, aralik=10)
    # alt ince cizgi
    d.rounded_rectangle([p(300, 904), p(780, 912)], 4 * S, fill=(40, 48, 70))
    yaz_ortala(d, 540, 934, "@StatDuel", f(40), GRI)
    return im


if __name__ == "__main__":
    for i, fn in enumerate((logo_1, logo_2, logo_3), 1):
        kaydet(fn(), f"logo_{i}.png")
        print(OUT / f"logo_{i}.png")

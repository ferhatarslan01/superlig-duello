"""StatDuel logo denemeleri (PIL, 3x ornekleme ile pürüzsüz).

  python logo/logo.py      # logo/out/logo_1.png, logo_2.png, logo_3.png
"""
import math
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


def _kaplama():
    return Image.new("RGBA", (N * S, N * S), (0, 0, 0, 0))


def _birlestir(im, kap):
    im.paste(kap, (0, 0), kap)


def logo_4():
    """Radar grafigi: iki oyuncunun profili ust uste; futbol istatistiginin evrensel gorseli."""
    im = tuval()
    d = ImageDraw.Draw(im)
    cx, cy, R = 540, 410, 310
    acilar = [-90 + 60 * i for i in range(6)]

    def nokta(i, oran):
        a = math.radians(acilar[i])
        return (cx + R * oran * math.cos(a), cy + R * oran * math.sin(a))

    for seviye in (0.33, 0.66, 1.0):
        d.polygon([p(*nokta(i, seviye)) for i in range(6)], outline=(46, 54, 78), width=3 * S)
    for i in range(6):
        d.line([p(cx, cy), p(*nokta(i, 1.0))], fill=(46, 54, 78), width=2 * S)
    kap = _kaplama()
    kd = ImageDraw.Draw(kap)
    kirm = [0.92, 0.62, 0.82, 0.48, 0.70, 0.88]
    mavi = [0.58, 0.90, 0.50, 0.86, 0.92, 0.56]
    kd.polygon([p(*nokta(i, v)) for i, v in enumerate(kirm)], fill=KIRMIZI + (120,))
    kd.polygon([p(*nokta(i, v)) for i, v in enumerate(mavi)], fill=MAVI + (120,))
    _birlestir(im, kap)
    d = ImageDraw.Draw(im)
    for vals, renk in ((kirm, KIRMIZI), (mavi, MAVI)):
        pts = [p(*nokta(i, v)) for i, v in enumerate(vals)]
        d.line(pts + [pts[0]], fill=renk, width=6 * S, joint="curve")
        for x, y in pts:
            d.ellipse([x - 11 * S, y - 11 * S, x + 11 * S, y + 11 * S], fill=renk)
    d.ellipse([p(cx - 14, cy - 14), p(cx + 14, cy + 14)], fill=SARI)
    yaz_iki_renk(d, 540, 780, "STAT", "DUEL", f(160), BEYAZ, MAVI, aralik=10)
    yaz_ortala(d, 540, 950, "@StatDuel", f(38), GRI)
    return im


def logo_5():
    """Ust gorunum saha: sol yari kirmizi, sag yari mavi, merkez cizgisi ve sari santra noktasi."""
    im = tuval()
    kap = _kaplama()
    kd = ImageDraw.Draw(kap)
    x0, y0, x1, y1 = 170, 190, 910, 650
    kd.rectangle([p(x0, y0), p(540, y1)], fill=KIRMIZI + (70,))
    kd.rectangle([p(540, y0), p(x1, y1)], fill=MAVI + (70,))
    _birlestir(im, kap)
    d = ImageDraw.Draw(im)
    cizgi = (225, 230, 242)
    w = 6 * S
    d.rounded_rectangle([p(x0, y0), p(x1, y1)], 18 * S, outline=cizgi, width=w)
    d.line([p(540, y0), p(540, y1)], fill=cizgi, width=w)
    d.ellipse([p(540 - 92, 420 - 92), p(540 + 92, 420 + 92)], outline=cizgi, width=w)
    for sol in (True, False):
        bx0, bx1 = (x0, x0 + 150) if sol else (x1 - 150, x1)
        d.rectangle([p(bx0, 420 - 110), p(bx1, 420 + 110)], outline=cizgi, width=w)
        kx0, kx1 = (x0, x0 + 56) if sol else (x1 - 56, x1)
        d.rectangle([p(kx0, 420 - 52), p(kx1, 420 + 52)], outline=cizgi, width=w)
    d.ellipse([p(540 - 20, 420 - 20), p(540 + 20, 420 + 20)], fill=SARI)
    yaz_iki_renk(d, 540, 720, "STAT", "DUEL", f(170), BEYAZ, KIRMIZI, aralik=10)
    yaz_ortala(d, 540, 905, "SÜPER LİG  ·  OYUNCU KARŞILAŞTIRMALARI", f(34), GRI)
    return im


def _kalkan_noktalar(cx=540, ust=170, alt=830, yan=290):
    pts = [(cx - yan, ust), (cx + yan, ust), (cx + yan, ust + 330)]
    for t in [i / 24 for i in range(1, 25)]:  # sag alt egri
        x = (1 - t) ** 2 * (cx + yan) + 2 * (1 - t) * t * (cx + yan - 20) + t ** 2 * cx
        y = (1 - t) ** 2 * (ust + 330) + 2 * (1 - t) * t * (alt - 120) + t ** 2 * alt
        pts.append((x, y))
    for t in [i / 24 for i in range(1, 25)]:  # sol alt egri
        x = (1 - t) ** 2 * cx + 2 * (1 - t) * t * (cx - yan + 20) + t ** 2 * (cx - yan)
        y = (1 - t) ** 2 * alt + 2 * (1 - t) * t * (alt - 120) + t ** 2 * (ust + 330)
        pts.append((x, y))
    return pts


def logo_6():
    """Kalkan rozeti: yildirim seklinde ikiye bolunmus kirmizi/mavi, ortada beyaz VS."""
    im = tuval()
    kalkan = _kalkan_noktalar()
    maske = Image.new("L", (N * S, N * S), 0)
    ImageDraw.Draw(maske).polygon([p(*q) for q in kalkan], fill=255)
    kap = _kaplama()
    kd = ImageDraw.Draw(kap)
    kd.rectangle([0, 0, N * S, N * S], fill=MAVI + (255,))
    # kirmizi sol bolge: yildirim kenarli
    zig = [(560, 150), (470, 330), (575, 430), (440, 620), (520, 850)]
    sol_bolge = [(0, 150), *zig, (0, 850)]
    kd.polygon([p(*q) for q in sol_bolge], fill=KIRMIZI + (255,))
    kd.line([p(*q) for q in zig], fill=SARI + (255,), width=14 * S, joint="curve")
    kap.putalpha(Image.composite(kap.getchannel("A"), Image.new("L", kap.size, 0), maske))
    im.paste(kap, (0, 0), kap)
    d = ImageDraw.Draw(im)
    d.line([p(*q) for q in kalkan + [kalkan[0]]], fill=BEYAZ, width=10 * S, joint="curve")
    d.ellipse([p(540 - 128, 520 - 128), p(540 + 128, 520 + 128)], fill=ARKA, outline=BEYAZ, width=8 * S)
    yaz_ortala(d, 540, 418, "VS", f(190), BEYAZ)
    yaz_iki_renk(d, 540, 862, "STAT", "DUEL", f(110), BEYAZ, MAVI, aralik=8)
    return im


def logo_7():
    """Karsi karsiya oklar: kirmizi > ve mavi < bir araya gelir, ortada sari top; altinda yazi."""
    im = tuval()
    d = ImageDraw.Draw(im)
    kal = 118
    def chevron(sol, renk, kayma=0):
        # sol: ok saga bakar (>), degilse sola (<)
        for k in range(3):
            ox = kayma + k * 92
            if sol:
                pts = [(150 + ox, 190), (150 + ox + kal, 190), (150 + ox + kal + 130, 400), (150 + ox + kal, 610), (150 + ox, 610), (150 + ox + 130, 400)]
            else:
                pts = [(930 - ox, 190), (930 - ox - kal, 190), (930 - ox - kal - 130, 400), (930 - ox - kal, 610), (930 - ox, 610), (930 - ox - 130, 400)]
            tonu = (255 - k * 30, 255 - k * 30, 255 - k * 30)
            r = tuple(int(c * (1 - 0.0 * k)) for c in renk)
            d.polygon([p(*q) for q in pts], fill=r if k == 2 else tuple(int(c * (0.45 + 0.275 * k)) for c in renk))
    chevron(True, KIRMIZI)
    chevron(False, MAVI)
    d.ellipse([p(540 - 46, 400 - 46), p(540 + 46, 400 + 46)], fill=SARI)
    yaz_iki_renk(d, 540, 690, "STAT", "DUEL", f(170), BEYAZ, MAVI, aralik=10)
    yaz_ortala(d, 540, 880, "KARŞI KARŞIYA", f(40), GRI)
    return im


def _oklar(d, ox, oy, olcek):
    """logo_7 ikonu: (ox, oy) sol-ust, olcek 1.0 = 780x420 px."""
    kal = 118
    def pts_sol(k):
        b = 150 + k * 92
        return [(b, 190), (b + kal, 190), (b + kal + 130, 400), (b + kal, 610), (b, 610), (b + 130, 400)]
    def pts_sag(k):
        b = 930 - k * 92
        return [(b, 190), (b - kal, 190), (b - kal - 130, 400), (b - kal, 610), (b, 610), (b - 130, 400)]
    def donustur(pts):
        return [((x - 150) * olcek + ox, (y - 190) * olcek + oy) for x, y in pts]
    for renk, fn in ((KIRMIZI, pts_sol), (MAVI, pts_sag)):
        for k in range(3):
            c = renk if k == 2 else tuple(int(v * (0.45 + 0.275 * k)) for v in renk)
            d.polygon([p(*q) for q in donustur(fn(k))], fill=c)
    cx, cy = (540 - 150) * olcek + ox, (400 - 190) * olcek + oy
    r = 46 * olcek
    d.ellipse([p(cx - r, cy - r), p(cx + r, cy + r)], fill=SARI)


def profil():
    """X profil resmi: yuvarlak kirpmaya uygun, ikon ortada ve genis kenar payli."""
    im = tuval()
    d = ImageDraw.Draw(im)
    olcek = 0.90
    _oklar(d, 540 - 390 * olcek, 540 - 210 * olcek, olcek)
    return im


def baslik():
    """X baslik gorseli 1500x500."""
    W, H = 1500, 500
    im = Image.new("RGB", (W * S, H * S), ARKA)
    d = ImageDraw.Draw(im)
    olcek = 0.62
    _oklar(d, 330, 500 / 2 - 210 * olcek, olcek)
    x = 860
    d.text((x * S, 150 * S), "STAT", font=f(120), fill=BEYAZ)
    wa = d.textlength("STAT", font=f(120))
    d.text((x * S + wa + 6 * S, 150 * S), "DUEL", font=f(120), fill=MAVI)
    d.text((x * S, 282 * S), "SÜPER LİG OYUNCU KARŞILAŞTIRMALARI", font=f(31), fill=GRI)
    d.rounded_rectangle([p(x, 332), p(x + 80, 337)], 3 * S, fill=SARI)
    d.text((x * S, 352 * S), "Maç sonu düellosu  ·  Sezon karşılaştırması", font=f(27), fill=(110, 118, 140))
    return im.resize((W, H), Image.LANCZOS)


if __name__ == "__main__":
    for i, fn in enumerate((logo_1, logo_2, logo_3, logo_4, logo_5, logo_6, logo_7), 1):
        kaydet(fn(), f"logo_{i}.png")
        print(OUT / f"logo_{i}.png")
    OUT.mkdir(exist_ok=True)
    kaydet(profil(), "profil_statduel.png")
    baslik().save(OUT / "baslik_statduel.png")
    print(OUT / "profil_statduel.png")
    print(OUT / "baslik_statduel.png")

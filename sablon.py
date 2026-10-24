"""StatDuel sezon karsilastirma sablonu (X icin 1080x1350, 4:5).

  python sablon.py "Salah" "Trossard"        # out/sablon_<id>_<id>.png

sezon.kart_ciz() bu sablonu kullanir. Renkler logodan: A oyuncusu turkuaz, B oyuncusu turuncu.
Kart 2x cozunurlukte cizilip kucultulur (yumusak kenarlar).
"""
import html
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import fotograf
from duello import HESAP, buyuk

KLASOR = Path(__file__).parent
FONT_DIR = KLASOR / "fonts"
LOGO = KLASOR / "marka" / "logo.png"

W, H = 1080, 1350
S = 2  # cizim olcegi

# ---- renkler (logo paleti) ----
ZEMIN = (8, 15, 38)
PANEL = (17, 27, 58)
CIZGI = (34, 46, 84)
IZ = (26, 38, 74)          # bos cubuk izi
TURKUAZ = (0, 194, 178)
TURUNCU = (255, 122, 26)
BEYAZ = (255, 255, 255)
GRI = (160, 172, 204)
SOLUK = (112, 126, 166)

# ESPN takim adlari -> Turkce yazim (eksikler oldugu gibi yazilir)
TAKIM_TR = {
    "Besiktas": "Beşiktaş", "Fenerbahce": "Fenerbahçe", "Caykur Rizespor": "Çaykur Rizespor",
    "Eyupspor": "Eyüpspor", "Genclerbirligi": "Gençlerbirliği", "Goztepe": "Göztepe",
    "Istanbul Basaksehir": "Başakşehir", "Kasimpasa": "Kasımpaşa", "Gaziantep FK": "Gaziantep FK",
    "Erzurum BB": "Erzurumspor", "Amed SFK": "Amed SFK",
}

# satir gruplari: (alan, etiket, tur, iyi_mi)   iyi_mi=False -> vurgulanmaz, ustunluk sayilmaz
GRUPLAR = [
    [("totalGoals", "GOL", "sayi", True), ("goalAssists", "ASİST", "sayi", True),
     ("totalShots", "ŞUT", "sayi", True), ("shotsOnTarget", "İSABETLİ ŞUT", "sayi", True)],
    [("passPct", "PAS İSABETİ", "yuzde", True), ("effectiveTackles", "TOP ÇALMA", "sayi", True)],
    [("foulsCommitted", "FAUL", "sayi", False), ("yellowCards", "SARI KART", "sayi", False),
     ("redCards", "KIRMIZI KART", "sayi", False)],
]


def _f(boyut, kalin=True):
    ad = "BarlowCondensed-SemiBold.ttf" if kalin else "Barlow-Regular.ttf"
    return ImageFont.truetype(str(FONT_DIR / ad), int(boyut * S * (1.12 if kalin else 1.0)))


def _r(*v):
    return [int(x * S) for x in v]


def _soluk(renk, oran):
    return tuple(int(ZEMIN[i] + (renk[i] - ZEMIN[i]) * oran) for i in range(3))


class Tuval:
    def __init__(self, h):
        self.img = Image.new("RGB", (W * S, h * S), ZEMIN)
        self.d = ImageDraw.Draw(self.img)

    def yaz(self, x, y, m, f, renk, hiza="sol", aralik=0):
        """hiza: sol | orta | sag. aralik: harf araligi (px)."""
        if aralik:
            gen = sum(self.d.textlength(c, font=f) for c in m) + aralik * S * (len(m) - 1)
        else:
            gen = self.d.textlength(m, font=f)
        x = x * S - (gen / 2 if hiza == "orta" else gen if hiza == "sag" else 0)
        if not aralik:
            self.d.text((x, y * S), m, font=f, fill=renk)
            return
        for c in m:
            self.d.text((x, y * S), c, font=f, fill=renk)
            x += self.d.textlength(c, font=f) + aralik * S

    def sigdir(self, m, max_w, boyut, kalin=True, en_kucuk=24):
        while boyut > en_kucuk and self.d.textlength(m, font=_f(boyut, kalin)) > max_w * S:
            boyut -= 2
        return _f(boyut, kalin)

    def kutu(self, x0, y0, x1, y1, r, **kw):
        if "width" in kw:
            kw["width"] = int(kw["width"] * S)
        self.d.rounded_rectangle(_r(x0, y0, x1, y1), int(r * S), **kw)


def _deger(o, alan, tur):
    if tur == "yuzde":
        return o["st"].get("passPct", 0) * 100
    return o["st"].get(alan, 0)


def _metin(v, tur):
    return f"%{round(v)}" if tur == "yuzde" else str(int(v))


def _ad(o):
    return html.unescape(o["ad"])


def _takim(o):
    return TAKIM_TR.get(o["takim"], o["takim"])


def _foto_yapistir(t, foto, x, y, boyut, renk, r=40):
    """Yuvarlatilmis kare foto + renkli cerceve. foto None ise silüet."""
    n = boyut * S
    zemin = Image.new("RGBA", (n, n), PANEL + (255,))
    if foto is not None:
        zemin.alpha_composite(foto.convert("RGBA").resize((n, n), Image.LANCZOS))
    else:
        zd = ImageDraw.Draw(zemin)
        sil = (64, 78, 120, 255)
        zd.ellipse([n * .34, n * .16, n * .66, n * .50], fill=sil)
        zd.ellipse([n * .14, n * .56, n * .86, n * 1.24], fill=sil)
    # alttan hafif karartma (oyuncu rengine dogru)
    alt = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ad = ImageDraw.Draw(alt)
    for i in range(n // 3):
        a = int(150 * (i / (n / 3)) ** 1.6)
        ad.line([(0, n - n // 3 + i), (n, n - n // 3 + i)], fill=_soluk(renk, .35) + (a,))
    zemin.alpha_composite(alt)
    maske = Image.new("L", (n, n), 0)
    ImageDraw.Draw(maske).rounded_rectangle([0, 0, n - 1, n - 1], int(r * S), fill=255)
    t.img.paste(zemin, (x * S, y * S), maske)
    t.kutu(x - 3, y - 3, x + boyut + 3, y + boyut + 3, r + 3, outline=renk, width=6)


def _logo(t, x, y, boyut):
    n = boyut * S
    if LOGO.exists():
        lg = Image.open(LOGO).convert("RGB").resize((n, n), Image.LANCZOS)
    else:
        lg = Image.new("RGB", (n, n), BEYAZ)
    maske = Image.new("L", (n, n), 0)
    ImageDraw.Draw(maske).ellipse([0, 0, n - 1, n - 1], fill=255)
    t.img.paste(lg, (x * S, y * S), maske)


def ciz(rol, a, b, yol, sezon_etiket="2026-27", soru="İkisinden hangisini seçerdin?"):
    t = Tuval(H)
    d = t.d
    for o in (a, b):
        if "_fotoim" not in o:
            o["_fotoim"], o["_foto"] = fotograf.foto_al(o["ad"], o["takim"])

    # ust serit: oyuncu renkleri
    d.rectangle(_r(0, 0, W / 2, 10), fill=TURKUAZ)
    d.rectangle(_r(W / 2, 0, W, 10), fill=TURUNCU)

    # baslik satiri
    _logo(t, 60, 40, 68)
    t.yaz(144, 44, "STATDUEL", _f(34), BEYAZ, aralik=1)
    t.yaz(145, 86, "Süper Lig veri kartları", _f(21, False), SOLUK)
    t.yaz(W - 60, 44, "SÜPER LİG", _f(34), BEYAZ, "sag", aralik=1)
    t.yaz(W - 60, 86, f"{sezon_etiket} sezonu", _f(21, False), SOLUK, "sag")
    d.line(_r(60, 132, W - 60, 132), fill=CIZGI, width=2 * S)

    # karsilastirma basligi
    t.yaz(W / 2, 156, "SEZON KARŞILAŞTIRMASI", _f(24), GRI, "orta", aralik=4)
    t.yaz(W / 2, 186, buyuk(rol), t.sigdir(buyuk(rol), 900, 84), BEYAZ, "orta")

    # oyuncular
    FB, FY = 250, 294
    for o, cx, renk in ((a, 250, TURKUAZ), (b, W - 250, TURUNCU)):
        _foto_yapistir(t, o["_fotoim"], cx - FB // 2, FY, FB, renk)
        ad = buyuk(_ad(o))
        t.yaz(cx, 566, ad, t.sigdir(ad, 390, 50), BEYAZ, "orta")
        alt = (f'{o["yas"]} yaş  ·  ' if o.get("yas") else "") + _takim(o)
        t.yaz(cx, 626, alt, t.sigdir(alt, 390, 25, False, 18), GRI, "orta")
        chip = f'{int(o["st"].get("appearances", 0))} MAÇ  ·  {int(o["st"].get("minutes", 0))} DK'
        fc = _f(22)
        cw = d.textlength(chip, font=fc) / S + 40
        t.kutu(cx - cw / 2, 668, cx + cw / 2, 706, 19, fill=PANEL, outline=CIZGI, width=2)
        t.yaz(cx, 672, chip, fc, renk, "orta")

    # VS rozeti
    vy = FY + FB // 2
    d.line(_r(W / 2, FY + 10, W / 2, vy - 56), fill=CIZGI, width=2 * S)
    d.line(_r(W / 2, vy + 56, W / 2, FY + FB - 10), fill=CIZGI, width=2 * S)
    d.ellipse(_r(W / 2 - 48, vy - 48, W / 2 + 48, vy + 48), fill=PANEL, outline=CIZGI, width=3 * S)
    t.yaz(W / 2, vy - 34, "VS", _f(46), BEYAZ, "orta")

    # ustunluk sayaci
    sa = sb = 0
    for grup in GRUPLAR:
        for alan, _, tur, iyi in grup:
            if not iyi:
                continue
            va, vb = round(_deger(a, alan, tur), 2), round(_deger(b, alan, tur), 2)
            sa += va > vb
            sb += vb > va
    UY = 730
    t.kutu(60, UY, W - 60, UY + 84, 22, fill=PANEL)
    t.yaz(110, UY + 4, str(sa), _f(64), TURKUAZ, "orta")
    t.yaz(W - 110, UY + 4, str(sb), _f(64), TURUNCU, "orta")
    t.yaz(W / 2, UY + 14, "ÜSTÜN OLDUĞU İSTATİSTİK", _f(21), GRI, "orta", aralik=3)
    bx0, bx1, by = 170, W - 170, UY + 54
    toplam = sa + sb
    orta = bx0 + (bx1 - bx0) * (sa / toplam if toplam else .5)
    t.kutu(bx0, by, bx1, by + 12, 6, fill=IZ)
    if sa:
        t.kutu(bx0, by, orta - 3, by + 12, 6, fill=TURKUAZ)
    if sb:
        t.kutu(orta + 3, by, bx1, by + 12, 6, fill=TURUNCU)

    # istatistik satirlari
    y = 842
    SH = 40
    ORTA_YARI = 108          # etiket kolonunun yari genisligi
    BAR = 250                # cubuk en uzun boyu
    xl, xr = W / 2 - ORTA_YARI - 12, W / 2 + ORTA_YARI + 12
    for gi, grup in enumerate(GRUPLAR):
        if gi:
            y += 14
        for alan, etiket, tur, iyi in grup:
            va, vb = _deger(a, alan, tur), _deger(b, alan, tur)
            mx = max(va, vb, 1e-9)
            ka = iyi and round(va, 2) > round(vb, 2)
            kb = iyi and round(vb, 2) > round(va, 2)
            ca = TURKUAZ if ka else (BEYAZ if not iyi else _soluk(TURKUAZ, .38))
            cb = TURUNCU if kb else (BEYAZ if not iyi else _soluk(TURUNCU, .38))
            if not iyi:
                ca = cb = (120, 134, 172)
            by = y + 15
            t.kutu(xl - BAR, by, xl, by + 10, 5, fill=IZ)
            t.kutu(xr, by, xr + BAR, by + 10, 5, fill=IZ)
            if va > 0:
                t.kutu(xl - max(10, BAR * va / mx), by, xl, by + 10, 5, fill=ca)
            if vb > 0:
                t.kutu(xr, by, xr + max(10, BAR * vb / mx), by + 10, 5, fill=cb)
            renk_a = TURKUAZ if ka else BEYAZ
            renk_b = TURUNCU if kb else BEYAZ
            t.yaz(60, y - 7, _metin(va, tur), _f(34), renk_a)
            t.yaz(W - 60, y - 7, _metin(vb, tur), _f(34), renk_b, "sag")
            t.yaz(W / 2, y + 7, etiket, _f(21, False), GRI if iyi else SOLUK, "orta")
            y += SH

    # alt bilgi
    d.line(_r(60, 1254, W - 60, 1254), fill=CIZGI, width=2 * S)
    t.yaz(W / 2, 1266, soru, _f(32), BEYAZ, "orta")
    kaynaklar = sorted({o["_foto"] for o in (a, b) if o.get("_foto")})
    alt = f"{HESAP}  ·  Veri: ESPN  ·  Sezon toplamları" + (f"  ·  Foto: {', '.join(kaynaklar)}" if kaynaklar else "")
    t.yaz(W / 2, 1312, alt, t.sigdir(alt, 960, 20, False, 15), SOLUK, "orta")

    t.img.resize((W, H), Image.LANCZOS).save(yol, optimize=True)
    return yol


if __name__ == "__main__":
    import sezon
    oy = sezon.sezon_verisi()
    a, b = sezon.ada_gore(oy, sys.argv[1]), sezon.ada_gore(oy, sys.argv[2])
    sezon.OUT.mkdir(exist_ok=True)
    yol = sezon.OUT / f"sablon_{a['id']}_{b['id']}.png"
    ciz(a["rol"], a, b, yol)
    print(yol)

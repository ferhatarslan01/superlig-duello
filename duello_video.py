"""Oyuncu karsilastirma videosu (PRO tasarim): 1080x1350 (4:5), ~21 sn, sesi kapali da anlasilir.

Tasarim ilkeleri (video-shotcraft): tek ana fikir, vurusa kilitli kesimler, bilgi yerlesince nefes payi,
sade ama sinematik isik (takim renkli isima), net hiyerarsi. Zaman cizelgesi muzik temposuna (131.8 BPM)
bagli: 1 vurus = 0.455 sn.

  0-4 vurus   HOOK: iki oyuncu kartlari carpar, "KIM USTUN?" damgasi
  4-...       Satirlar: her 3 vurusta bir satir, vurusta yerlesir (tik sesi), skor yukselir
  sonuc       Kazanan one cikar, kaybeden soluklasir, kivilcim + darbe (8 vurus)
  kapanis     Marka karti: "Sen kimi secerdin?" + TAKIP ET (8 vurus), basa donen kapanis

Kullanim:
  python duello_video.py Osimhen Muriqi                 # out/duello_<id>_<id>.mp4 (sessiz)
  python duello_video.py Osimhen Muriqi --kare 0.2,6,14   # PNG kareler (tasarim kontrolu)
"""
import math
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import fotograf
import kart_v2
import satirlar as _satir
import sezon
from baski_video import OUT

KLASOR = Path(__file__).parent
W, H = 1080, 1350
FPS = 30
BPM = 131.8                                       # assets/muzik/funky-brazilian-phonk.wav (ilk vurusa hizali)
B = 60.0 / BPM
MUZIK = KLASOR / "assets" / "muzik" / "funky-brazilian-phonk.wav"

ARKA = (8, 10, 18)
BEYAZ = (255, 255, 255)
ETIKET = (196, 203, 220)
SOLUK = (128, 137, 160)
SARI = (255, 214, 10)
MAVI = (46, 134, 222)
HOOK_B, SATIR_B = 4, 3                            # vurus cinsinden: hook suresi, satirlar arasi
SONUC_B, CTA_B = 8, 8
CARD_W = CARD_H = 440
CARD_Y = 132
CARD_X = (40, 600)

TAKIM_RENK = [  # (anahtar, (birincil, ikincil)): kulup renkleri; koyu zeminde okunsun diye lacivert/siyah acildi
    ("galatasaray", ((236, 52, 60), (255, 200, 0))), ("fenerbahce", ((255, 208, 40), (40, 70, 180))),
    ("besiktas", ((235, 235, 240), (110, 114, 126))), ("trabzonspor", ((176, 40, 84), (96, 168, 255))),
    ("basaksehir", ((255, 128, 30), (40, 70, 160))), ("samsunspor", ((236, 40, 50), (240, 240, 245))),
    ("konyaspor", ((30, 190, 110), (240, 240, 245))), ("kasimpasa", ((70, 150, 240), (240, 240, 245))),
    ("alanyaspor", ((255, 150, 30), (30, 170, 90))), ("goztepe", ((236, 50, 60), (255, 200, 0))),
    ("rizespor", ((30, 175, 100), (50, 120, 210))), ("genclerbirligi", ((236, 50, 60), (240, 240, 245))),
    ("eyupspor", ((170, 90, 230), (255, 200, 0))), ("kocaelispor", ((30, 170, 90), (240, 240, 245))),
    ("gaziantep", ((236, 60, 60), (240, 240, 245))), ("corum", ((220, 50, 70), (240, 240, 245))),
    ("erzurum", ((90, 140, 235), (240, 240, 245))), ("amed", ((40, 170, 100), (225, 55, 65))),
]


# ---------------- yardimcilar ----------------
@lru_cache(maxsize=None)
def F(boyut, kalin=True):
    ad = "BarlowCondensed-SemiBold.ttf" if kalin else "Barlow-Regular.ttf"
    return ImageFont.truetype(str(KLASOR / "fonts" / ad), int(boyut * (1.12 if kalin else 1.0)))


def _vis(t, t0, sure):
    return max(0.0, min(1.0, (t - t0) / sure)) if sure > 0 else (1.0 if t >= t0 else 0.0)


def _ease(p):
    return 1 - (1 - p) ** 3


def _pop(p, asim=0.14):
    """0..1 -> hafif asimli yerlesme (1.0'a oturur)."""
    return 1 + asim * math.sin(min(p, 1.0) * math.pi) * (1 - p) if p < 1 else 1.0


def takim_ikili(takim):
    """(birincil, ikincil) kulup renkleri; bilinmeyen takimda birincil kirmizi, ikincil beyaz."""
    n = fotograf.norm(takim)
    for k, r in TAKIM_RENK:
        if k in n:
            return r
    return (220, 70, 80), (240, 240, 245)


def takim_rengi(takim):
    return takim_ikili(takim)[0]


def renk_ayir(ca, cb):
    """Iki renk birbirine cok yakinsa ikincisini ayirir."""
    if math.dist(ca, cb) < 120:
        return ca, (MAVI if math.dist(ca, MAVI) > 120 else SARI)
    return ca, cb


def kontrast(renk):
    l = 0.299 * renk[0] + 0.587 * renk[1] + 0.114 * renk[2]
    return (12, 14, 24) if l > 150 else BEYAZ


def _alfa(katman, a):
    if a >= 0.999:
        return katman
    k = katman.copy()
    k.putalpha(katman.getchannel("A").point(lambda v: int(v * a)))
    return k


def koy(base, katman, x, y, alfa=1.0, olcek=1.0, merkez=False):
    """katmani base'e (RGBA, opak) yapistirir; olcek/merkez/alfa destekli."""
    if alfa <= 0.002:
        return
    if olcek != 1.0:
        katman = katman.resize((max(1, int(katman.width * olcek)), max(1, int(katman.height * olcek))), Image.BICUBIC)
    if merkez:
        x, y = x - katman.width / 2, y - katman.height / 2
    katman = _alfa(katman, alfa)
    base.paste(katman, (int(round(x)), int(round(y))), katman)


def yaz(d, xy, metin, f, fill, anchor="la"):
    d.text(xy, metin, font=f, fill=fill, anchor=anchor)


def sigan(metin, max_w, boyut, kalin=True, en_kucuk=22):
    d = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    while boyut > en_kucuk and d.textlength(metin, font=F(boyut, kalin)) > max_w:
        boyut -= 2
    return F(boyut, kalin)


def harf_arali(d, merkez_x, y, metin, f, fill, aralik):
    w = sum(d.textlength(c, font=f) for c in metin) + aralik * (len(metin) - 1)
    x = merkez_x - w / 2
    for c in metin:
        d.text((x, y), c, font=f, fill=fill)
        x += d.textlength(c, font=f) + aralik


@lru_cache(maxsize=32)
def isima(renk, w, h, r, blur, alfa, pad=70):
    """Renkli yumusak isima (yuvarlak dikdortgen); (w+2pad, h+2pad) RGBA."""
    im = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([pad, pad, pad + w, pad + h], r, fill=tuple(renk) + (int(255 * alfa),))
    return im.filter(ImageFilter.GaussianBlur(blur))


@lru_cache(maxsize=1)
def marka_isareti():
    """Profil logosundaki ok isareti (RGBA, seffaf): logo/logo.py'den."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("statduel_logo", KLASOR / "logo" / "logo.py")
    lg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lg)
    S = lg.S
    kap = Image.new("RGBA", (820 * S, 460 * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(kap)
    lg._oklar(d, 20, 20, 1.0)
    return kap.crop(kap.getbbox())


def marka(genislik):
    m = marka_isareti()
    return m.resize((genislik, int(m.height * genislik / m.width)), Image.LANCZOS)


def _buyuk(m):
    return m.replace("i", "İ").replace("ı", "I").upper()


# ---------------- veri hazirlama ----------------
def _satirlar(ka, kb, sat, kotu):
    """[(alan, etiket)] -> video satirlari. PitchAPI alanlari iki oyuncuda da yoksa gizlenir."""
    sat = [r for r in sat if not (r[0] in kart_v2.GELISMIS | {"puan"} and kart_v2._deger(ka, r[0]) is None
                                  and kart_v2._deger(kb, r[0]) is None)]
    satirlar = []
    for alan, etiket in sat:
        va, vb = kart_v2._deger(ka, alan), kart_v2._deger(kb, alan)
        wa, wb = kart_v2._kazanan(alan, va, vb, kotu)
        satirlar.append({"alan": alan, "etiket": etiket, "va": va, "vb": vb, "wa": wa, "wb": wb})
    return satirlar


def sezon_oyunculari(rol, a, b):
    oy = lambda o: {"id": o["id"], "ad": o["ad"], "takim": o["takim"], "yas": o.get("yas"), "st": o["st"],  # noqa: E731
                    "satir2": None}
    ka, kb = oy(a), oy(b)
    return ka, kb, _satirlar(ka, kb, _satir.sezon_satirlari(rol), sezon.KOTU)


def mac_oyunculari(rol, oa, ob):
    import duello
    oy = lambda o: {"id": o.get("id"), "ad": o["ad"], "takim": o["_takim"], "yas": o.get("yas"),  # noqa: E731
                    "st": o["st"], "satir2": None}
    ka, kb = oy(oa), oy(ob)
    return ka, kb, _satirlar(ka, kb, _satir.mac_satirlari(rol), duello.KOTU)


def hazirla(ad1, ad2):
    oyuncular = sezon.sezon_verisi()
    a, b = sezon.ada_gore(oyuncular, ad1), sezon.ada_gore(oyuncular, ad2)
    return sezon_oyunculari(a["rol"], a, b)


# ---------------- sahne ----------------
class Video:
    def __init__(self, ka, kb, satirlar, ust=""):
        self.ka, self.kb, self.sat, self.ust = ka, kb, satirlar, ust
        self.n = len(satirlar)
        self.ca, self.cb = renk_ayir(takim_rengi(ka["takim"]), takim_rengi(kb["takim"]))
        self.renk = (self.ca, self.cb)
        self.renk2 = (takim_ikili(ka["takim"])[1], takim_ikili(kb["takim"])[1])     # kulubun ikinci rengi
        self.puan = (sum(r["wa"] for r in satirlar), sum(r["wb"] for r in satirlar))
        # zaman cizelgesi (vurus cinsinden)
        self.r0 = HOOK_B                                    # ilk satir
        self.landing = [(self.r0 + SATIR_B * i + 1) * B for i in range(self.n)]
        self.R = (self.r0 + SATIR_B * self.n + 1) * B       # sonuc
        self.C = self.R + SONUC_B * B                       # kapanis karti
        self.bitis = self.C + CTA_B * B
        self.sure = self.bitis + 0.5                        # + basa donen kapanis
        if self.puan[0] == self.puan[1]:
            self.kazanan = None
        else:
            self.kazanan = 0 if self.puan[0] > self.puan[1] else 1
        self._hazirla()

    # ses efektleri: muzik.videoya_ekle'ye verilir
    @property
    def darbeler(self):
        return [0.0, self.R]

    @property
    def sfx(self):
        out = [(t, "tik", 1.0) for t in self.landing]
        out.append((self.R + 0.03, "parilti", 0.35))
        return out

    # ---- onbellekli katmanlar ----
    def _hazirla(self):
        self.kartlar = [self._kart(o, c, c2) for o, c, c2 in ((self.ka, self.ca, self.renk2[0]),
                                                              (self.kb, self.cb, self.renk2[1]))]
        self.kart_soluk = [self._soluk(k) for k in self.kartlar]
        self.chipler = [self._chipler(o, c) for o, c in ((self.ka, self.ca), (self.kb, self.cb))]
        self.vig = self._vinyet()
        self.st_hook = self._damga("KİM ÜSTÜN?", 188)
        self.sub_hook = f"{self.n} İSTATİSTİK  ·  1 KAZANAN"
        if self.kazanan is None:
            self.ad_sonuc, self.renk_sonuc = "BERABERE", BEYAZ
        else:
            k = (self.ka, self.kb)[self.kazanan]
            self.ad_sonuc = _buyuk(k["ad"].split()[-1])
            self.renk_sonuc = self.renk[self.kazanan]
        self.st_sonuc = self._damga(self.ad_sonuc, 168, self.renk_sonuc, max_w=900)
        self.vs = self._vs()
        self.sonuc_panel = self._sonuc_panel()
        self.marka_kucuk = marka(62)
        self.marka_buyuk = marka(330)

    def _damga(self, metin, boyut, renk=BEYAZ, max_w=980):
        """Isimali buyuk metin katmani (RGBA)."""
        f = sigan(metin, max_w, boyut)
        d = ImageDraw.Draw(Image.new("RGB", (4, 4)))
        tw = int(d.textlength(metin, font=f)) + 4
        th = int(f.size * 1.25)
        pad = 60
        im = Image.new("RGBA", (tw + 2 * pad, th + 2 * pad), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((pad, pad), metin, font=f, fill=tuple(renk) + (255,))
        glow = im.filter(ImageFilter.GaussianBlur(22))
        glow.putalpha(glow.getchannel("A").point(lambda v: min(255, int(v * 1.1))))
        out = Image.new("RGBA", im.size, (0, 0, 0, 0))
        out.alpha_composite(glow)
        out.alpha_composite(im)
        return out

    def _vinyet(self):
        yy, xx = np.mgrid[0:H // 6, 0:W // 6]
        nx, ny = (xx / (W / 6) - 0.5) * 2, (yy / (H / 6) - 0.5) * 2
        k = np.clip((nx ** 2 * 0.55 + ny ** 2 * 0.75) - 0.35, 0, 1)
        im = Image.new("RGBA", (W // 6, H // 6), (0, 0, 0, 0))
        im.putalpha(Image.fromarray((k * 190).astype("uint8")))
        return im.resize((W, H), Image.BICUBIC)

    def _kart(self, o, renk, renk2):
        """Foto + isim/takim alt kapakli kart (CARD_W x CARD_H, RGBA, yuvarlak)."""
        S = 2
        w, h = CARD_W * S, CARD_H * S
        foto, _ = fotograf.foto_al(o["ad"], o["takim"])
        if foto is not None:
            im = foto.convert("RGBA").resize((w, h), Image.LANCZOS)
        else:                                              # silüet
            im = Image.new("RGBA", (w, h), (24, 30, 46, 255))
            d = ImageDraw.Draw(im)
            sil = (74, 86, 116, 255)
            d.ellipse([w * 0.32, h * 0.16, w * 0.68, h * 0.52], fill=sil)
            d.ellipse([w * 0.14, h * 0.58, w * 0.86, h * 1.25], fill=sil)
        rampa = np.zeros((h, w), dtype="uint8")                # alt kapak: isim okunsun
        k0 = int(h * 0.50)
        for y in range(k0, h):
            rampa[y, :] = int(235 * ((y - k0) / (h - k0)) ** 1.35)
        kapak = Image.new("RGBA", (w, h), ARKA + (0,))
        kapak.putalpha(Image.fromarray(rampa))
        im.alpha_composite(kapak)
        d = ImageDraw.Draw(im)
        ad = _buyuk(o["ad"])
        f = sigan(ad, CARD_W - 44, 62, True, 34)
        d.text((22 * S, (CARD_H - 134) * S), ad, font=F(f.size / 1.12 * S), fill=BEYAZ)
        l1 = " · ".join(x for x in ((f'{o["yas"]} yaş' if o.get("yas") else None), kart_v2.takim_adi(o["takim"])) if x)
        f2 = sigan(l1, CARD_W - 44, 28, False, 20)
        d.text((22 * S, (CARD_H - 60) * S), l1, font=F(f2.size * S, False), fill=ETIKET)
        d.rectangle([0, h - 8 * S, w // 2, h], fill=tuple(renk) + (255,))           # alt cizgi: iki kulup rengi
        d.rectangle([w // 2, h - 8 * S, w, h], fill=tuple(renk2) + (255,))
        maske = Image.new("L", (w, h), 0)
        ImageDraw.Draw(maske).rounded_rectangle([0, 0, w - 1, h - 1], 34 * S, fill=255)
        # cerceve: kulup renkleri capraz bolunmus (sol-ust birincil, sag-alt ikincil, yumusak gecis)
        halka = Image.new("L", (w, h), 0)
        ImageDraw.Draw(halka).rounded_rectangle([0, 0, w - 1, h - 1], 34 * S, outline=255, width=7 * S)
        yy, xx = np.mgrid[0:h, 0:w]
        u = (xx / w + yy / h) / 2
        k = np.clip((u - 0.46) / 0.08, 0, 1)[..., None]
        renk_alani = (np.array(renk, float) * (1 - k) + np.array(renk2, float) * k).astype("uint8")
        cerceve = Image.fromarray(renk_alani, "RGB").convert("RGBA")
        cerceve.putalpha(halka)
        im.alpha_composite(cerceve)
        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        out.paste(im, (0, 0), maske)
        return out.resize((CARD_W, CARD_H), Image.LANCZOS)

    @staticmethod
    def _soluk(katman):
        a = katman.getchannel("A")
        gri = katman.convert("L").convert("RGB")
        rgb = Image.blend(katman.convert("RGB"), gri, 0.7).point(lambda v: int(v * 0.42))
        rgb.putalpha(a)
        return rgb

    def _chipler(self, o, renk):
        parcalar = []
        pm = kart_v2.profil_metni(o)
        if pm:
            parcalar = pm.split(" · ")                      # boy, ayak, uyruk
        pd = kart_v2.piyasa_degeri(o)
        if pd:
            parcalar.append(pd)
        d = ImageDraw.Draw(Image.new("RGB", (4, 4)))
        f = F(23, False)

        def genislik(ps):
            return sum(d.textlength(p, font=f) + 26 for p in ps) + 10 * (len(ps) - 1)
        while parcalar and genislik(parcalar) > CARD_W - 6:   # sigmazsa uyruktan basla at
            sil = 2 if len(parcalar) >= 4 else len(parcalar) - 1
            parcalar.pop(sil)
        w = int(genislik(parcalar)) if parcalar else 1
        im = Image.new("RGBA", (max(w, 1), 42), (0, 0, 0, 0))
        dd = ImageDraw.Draw(im)
        x = 0
        for p in parcalar:
            cw = int(d.textlength(p, font=f) + 26)
            son = (p == pd)
            dd.rounded_rectangle([x, 0, x + cw, 40], 20, fill=((255, 255, 255, 22) if not son else tuple(renk) + (46,)),
                                 outline=((255, 255, 255, 46) if not son else tuple(renk) + (170,)), width=2)
            dd.text((x + cw / 2, 21), p, font=f, fill=(ETIKET if not son else BEYAZ) + (255,), anchor="mm")
            x += cw + 10
        return im

    def _vs(self):
        im = Image.new("RGBA", (130, 130), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.ellipse([8, 8, 122, 122], fill=(12, 15, 26, 235), outline=(255, 255, 255, 190), width=4)
        d.text((65, 62), "VS", font=F(50), fill=BEYAZ + (255,), anchor="mm")
        return im

    def _sonuc_panel(self):
        pad = 40
        im = Image.new("RGBA", (1000 + 2 * pad, 568 + 2 * pad), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([pad, pad, pad + 1000, pad + 568], 36, fill=(10, 12, 22, 246),
                            outline=tuple(self.renk_sonuc) + (150,), width=3)
        return im

    # ---- zemin ----
    def _zemin(self, t):
        gh, gw = H // 8, W // 8
        yy, xx = np.mgrid[0:gh, 0:gw]
        nx, ny = xx / gw, yy / gh
        s = math.sin(t * 0.6)
        alan = np.zeros((gh, gw, 3))
        for (cx, cy, renk, g) in ((0.20 + 0.03 * s, 0.30, self.ca, 0.30), (0.80 - 0.03 * s, 0.30, self.cb, 0.30)):
            k = np.exp(-(((nx - cx) / 0.34) ** 2 + ((ny - cy) / 0.30) ** 2)) * g
            alan += k[..., None] * np.array(renk, float)
        alt = np.exp(-(((nx - 0.5) / 0.7) ** 2 + ((ny - 0.98) / 0.22) ** 2)) * 0.10
        alan += alt[..., None] * np.array((110, 130, 190), float)
        arr = np.clip(np.array(ARKA, float) + alan, 0, 255).astype("uint8")
        return Image.fromarray(arr).resize((W, H), Image.BICUBIC).convert("RGBA")

    # ---- ana kare ----
    def kare(self, t):
        if t > self.bitis:                                   # basa donen kapanis
            q = _ease(_vis(t, self.bitis, 0.5))
            return Image.blend(self._kare(self.bitis - 1e-3), self._kare(0.35), q)
        return self._kare(t)

    def _kare(self, t):
        im = self._zemin(t)
        im.alpha_composite(self.vig)
        ana = 1.0 - _ease(_vis(t, self.C, 0.4))              # kapanis kartina gecerken ana icerik solar
        if ana > 0.003:
            self._ana(im, t, ana)
        if t >= self.C - 0.01:
            self._kapanis(im, t)
        if self.R <= t < self.R + 0.22:                      # sonuc anindaki kisa isik (tek, 0.22 sn)
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(78 * (1 - (t - self.R) / 0.22)))))
        return im.convert("RGB")

    def _ust_serit(self, im, ana):
        d = ImageDraw.Draw(im, "RGBA")
        koy(im, self.marka_kucuk, 40, 42, ana)
        yaz(d, (40 + 62 + 16, 40), "STAT", F(46), BEYAZ + (int(255 * ana),))
        w = d.textlength("STAT", font=F(46))
        yaz(d, (40 + 62 + 16 + w + 3, 40), "DUEL", F(46), MAVI + (int(255 * ana),))
        if self.ust:
            f = sigan(self.ust, 520, 26, False, 18)
            yaz(d, (W - 40, 66), self.ust, f, SOLUK + (int(255 * ana),), anchor="rm")
        d.line([40, 104, W - 40, 104], fill=(255, 255, 255, int(26 * ana)), width=2)

    def _ana(self, im, t, ana):
        self._ust_serit(im, ana)
        # --- kartlar (hook'ta carpar) ---
        gir = _ease(_vis(t, 0.0, 0.32))
        sonuc_p = _ease(_vis(t, self.R, 0.4))
        for i in (0, 1):
            cx = CARD_X[i] + CARD_W / 2
            cy = CARD_Y + CARD_H / 2
            kayma = (-1 if i == 0 else 1) * 70 * (1 - gir)
            olcek = 1.0 + 0.10 * (1 - gir)
            a = (0.62 + 0.38 * gir) * ana
            kazandi = self.kazanan == i
            kaybetti = self.kazanan is not None and self.kazanan != i
            g_alfa = 0.55 + (0.35 * sonuc_p if kazandi else 0) - (0.35 * sonuc_p if kaybetti else 0)
            koy(im, isima(tuple(self.renk[i]), CARD_W, CARD_H, 40, 46, 0.55), cx + kayma, cy, a * g_alfa, olcek, merkez=True)
            if kaybetti and sonuc_p > 0:
                koy(im, self.kart_soluk[i], cx + kayma, cy, a, olcek, merkez=True)
                koy(im, self.kartlar[i], cx + kayma, cy, a * (1 - sonuc_p), olcek, merkez=True)
            else:
                sc = olcek * (1 + 0.045 * sonuc_p if kazandi else 1)
                koy(im, self.kartlar[i], cx + kayma, cy, a, sc, merkez=True)
        # VS rozeti
        vs_p = _ease(_vis(t, 0.05, 0.3))
        koy(im, self.vs, W / 2, CARD_Y + CARD_H / 2 - 20, vs_p * ana, 0.6 + 0.4 * vs_p, merkez=True)
        # chipler + skor hapi: 2. vurustan itibaren
        ch = _ease(_vis(t, 2 * B, 0.35))
        for i in (0, 1):
            c = self.chipler[i]
            koy(im, c, (CARD_X[0] if i == 0 else CARD_X[1] + CARD_W - c.width), CARD_Y + CARD_H + 22 + (1 - ch) * 12, ch * ana)
        self._skor_hapi(im, t, ana * ch)
        # --- hook damgasi ---
        if t < HOOK_B * B + 0.01:
            p_in = _ease(_vis(t, 0.0, 0.26))
            cikis = _ease(_vis(t, (HOOK_B - 0.8) * B, 0.7 * B))
            a = (0.72 + 0.28 * p_in) * (1 - cikis)
            koy(im, self.st_hook, W / 2, 900 - 36 * cikis, a * ana, 1.30 - 0.30 * p_in, merkez=True)
            sd = ImageDraw.Draw(im, "RGBA")
            yaz(sd, (W / 2, 1010 - 36 * cikis), self.sub_hook, F(44, False), ETIKET + (int(255 * a * ana),), anchor="mm")
        self._satirlar_ciz(im, t, ana)
        if t >= self.R:
            self._sonuc(im, t, ana)
        self._hesap(im, ana)

    def _skor_hapi(self, im, t, ana):
        """Ortada cam gorunumlu skor hapi; bir satir yerlestiginde (kazanan taraf rengiyle) zipliyor."""
        pa = pb = 0
        son_t, son_taraf = -9, None
        for i, r in enumerate(self.sat):
            if t >= self.landing[i]:
                pa += r["wa"]
                pb += r["wb"]
                if r["wa"] or r["wb"]:
                    son_t, son_taraf = self.landing[i], (0 if r["wa"] else 1)
        p = _vis(t, son_t, 0.28)
        sc = _pop(p, 0.14)
        w, h, pad = 214, 96, 40
        k = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
        dd = ImageDraw.Draw(k)
        parla = self.renk[son_taraf] if (son_taraf is not None and p < 1) else (255, 255, 255)
        kenar_a = 90 + int(150 * (1 - p)) if son_taraf is not None else 70
        dd.rounded_rectangle([pad, pad, pad + w, pad + h], 48, fill=(14, 17, 30, 232), outline=tuple(parla) + (kenar_a,), width=3)
        dd.text((pad + w / 2 - 48, pad + h / 2 - 1), str(pa), font=F(72), fill=self.ca + (255,), anchor="mm")
        dd.text((pad + w / 2, pad + h / 2 - 3), "–", font=F(56), fill=(150, 158, 180, 255), anchor="mm")
        dd.text((pad + w / 2 + 48, pad + h / 2 - 1), str(pb), font=F(72), fill=self.cb + (255,), anchor="mm")
        koy(im, k, W / 2, CARD_Y + CARD_H + 38, ana, sc, merkez=True)

    def _satirlar_ciz(self, im, t, ana):
        n = self.n
        y0, y1 = 676, 1232
        h = min(78, (y1 - y0) // max(n, 1))
        ys = y0 + ((y1 - y0) - n * h) / 2
        sonuc_dim = 1 - 0.82 * _ease(_vis(t, self.R, 0.35))
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov, "RGBA")
        for i, r in enumerate(self.sat):
            s = (self.r0 + SATIR_B * i) * B
            p_gir = _ease(_vis(t, s, 0.26))
            if p_gir <= 0:
                continue
            land = self.landing[i]
            p_bar = _ease(_vis(t, s + 0.05, B))
            p_land = _vis(t, land, 0.3)
            y = ys + i * h + (1 - p_gir) * 14
            al = p_gir * ana * sonuc_dim
            d.rounded_rectangle([40, y, W - 40, y + h - 10], 18, fill=(255, 255, 255, int(11 * p_gir)),
                                outline=(255, 255, 255, int(20 * al)), width=2)
            cy = y + (h - 10) / 2
            etiket = r["etiket"]
            yaz(d, (W / 2, cy - 14), etiket, sigan(etiket, 420, 26, False, 20), ETIKET + (int(255 * al),), anchor="mm")
            va, vb = r["va"], r["vb"]
            mx = max(abs(va or 0), abs(vb or 0), 1e-9)
            for v_, taraf, kaz in ((va, 0, r["wa"]), (vb, 1, r["wb"])):
                renk = self.renk[taraf]
                yon = -1 if taraf == 0 else 1
                uz = 236 * (abs(v_ or 0) / mx) * p_bar
                bx0 = W / 2 + yon * 40
                yb = cy + 12
                kaybeden = (r["wa"] or r["wb"]) and not kaz and p_land > 0
                ba = int(255 * al * (0.38 if kaybeden else 1.0))
                if uz > 1:
                    if kaz and p_land > 0:                       # kazanan bar: yumusak isima
                        d.rounded_rectangle([min(bx0, bx0 + yon * uz) - 6, yb - 11, max(bx0, bx0 + yon * uz) + 6, yb + 11], 11,
                                            fill=tuple(renk) + (int(70 * al),))
                    d.rounded_rectangle([min(bx0, bx0 + yon * uz), yb - 6, max(bx0, bx0 + yon * uz), yb + 6], 6,
                                        fill=tuple(renk) + (ba,))
                gosterilen = None if v_ is None else v_ * p_bar
                tx = kart_v2._metin(gosterilen, r["alan"]) if gosterilen is not None else "–"
                nx = 130 if taraf == 0 else W - 130
                fn = F(54)
                if kaz and p_land > 0:
                    pw = max(d.textlength(tx, font=fn) + 42, 112)
                    pop = _pop(p_land, 0.13)
                    d.rounded_rectangle([nx - pw * pop / 2, cy - 30 * pop, nx + pw * pop / 2, cy + 30 * pop], 16 * pop,
                                        fill=tuple(renk) + (int(255 * al),))
                    yaz(d, (nx, cy - 2), tx, fn, kontrast(renk) + (int(255 * al),), anchor="mm")
                else:
                    ta = 0.55 if kaybeden else 1.0
                    yaz(d, (nx, cy - 2), tx, fn, BEYAZ + (int(255 * al * ta),), anchor="mm")
        im.alpha_composite(ov)

    def _sonuc(self, im, t, ana):
        p = _ease(_vis(t, self.R + 0.05, 0.4))
        if p > 0:
            koy(im, self.sonuc_panel, W / 2, 954 + (1 - p) * 30, p * ana, merkez=True)
            etiket = "KAZANAN" if self.kazanan is not None else "SONUÇ"
            ov = ImageDraw.Draw(im, "RGBA")
            harf_arali(ov, W / 2, 800 + (1 - p) * 30, etiket, F(40), SOLUK + (int(255 * p * ana),), 10)
            koy(im, self.st_sonuc, W / 2, 958 + (1 - p) * 40, p * ana, merkez=True)
            if self.kazanan is None:
                sub = f"{self.puan[0]} - {self.puan[1]} satır"
            else:
                sub = f"{max(self.puan)} - {min(self.puan)} SATIRDA ÜSTÜN"
            yaz(ov, (W / 2, 1118 + (1 - p) * 30), sub, F(50), BEYAZ + (int(255 * p * ana),), anchor="mm")
        if self.kazanan is not None and t < self.R + 2.2:
            self._kivilcim(im, t - self.R, ana)

    def _kivilcim(self, im, tau, ana):
        rng = np.random.default_rng(11)
        i = self.kazanan
        ox, oy = CARD_X[i] + CARD_W / 2, CARD_Y + 120
        renkler = [self.renk[i], BEYAZ, SARI]
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov, "RGBA")
        for k in range(64):
            ang = math.radians(rng.uniform(-165, -15))
            hiz = rng.uniform(260, 780)
            yas = rng.uniform(1.0, 1.9)
            r0 = rng.uniform(3, 7)
            if tau > yas:
                continue
            x = ox + math.cos(ang) * hiz * tau
            y = oy + math.sin(ang) * hiz * tau + 0.5 * 620 * tau * tau
            r = r0 * (1 - 0.4 * tau / yas)
            a = int(255 * (1 - tau / yas) * ana)
            d.ellipse([x - r, y - r, x + r, y + r], fill=tuple(renkler[k % 3]) + (a,))
        im.alpha_composite(ov)

    def _hesap(self, im, ana):
        from baski_video import _tiktok, _x_logo
        f = F(40)
        ik, bos = 36, 14
        ov = Image.new("RGBA", (W, 80), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        tw = od.textlength("@StatDuel", font=f)
        x = W / 2 - (tw + 2 * (ik + bos)) / 2
        _tiktok(od, x, 8, ik)
        _x_logo(od, x + ik + bos, 8, ik)
        od.text((x + 2 * (ik + bos), 6), "@StatDuel", font=f, fill=BEYAZ + (255,))
        koy(im, ov, 0, 1276, ana)

    def _kapanis(self, im, t):
        """Marka karti: logo, 'Sen kimi seçerdin?', TAKIP ET."""
        p = _ease(_vis(t, self.C + 0.05, 0.45))
        im.alpha_composite(Image.new("RGBA", (W, H), ARKA + (int(236 * p),)))
        koy(im, isima(tuple(self.ca), 420, 260, 120, 90, 0.35, 140), 300, 520, p * 0.8, merkez=True)
        koy(im, isima(tuple(self.cb), 420, 260, 120, 90, 0.35, 140), 780, 520, p * 0.8, merkez=True)
        d = ImageDraw.Draw(im, "RGBA")

        def kademe(g):
            return _ease(_vis(t, self.C + 0.10 + g * 0.18, 0.4))
        k1 = kademe(0)
        koy(im, self.marka_buyuk, W / 2, 252 - (1 - k1) * 20, k1, merkez=True)
        k2 = kademe(1)
        w = d.textlength("STAT", font=F(176))
        wd = d.textlength("DUEL", font=F(176))
        x = W / 2 - (w + wd + 6) / 2
        y2 = 410 - (1 - k2) * 20
        d.text((x, y2), "STAT", font=F(176), fill=BEYAZ + (int(255 * k2),))
        d.text((x + w + 6, y2), "DUEL", font=F(176), fill=MAVI + (int(255 * k2),))
        k3 = kademe(2)
        yaz(d, (W / 2, 690 - (1 - k3) * 16), "Her gün Süper Lig oyuncu düelloları", F(44, False), ETIKET + (int(255 * k3),), anchor="mm")
        k4 = kademe(3)
        yaz(d, (W / 2, 820 - (1 - k4) * 16), "Sen kimi seçerdin?", F(104), BEYAZ + (int(255 * k4),), anchor="mm")
        yaz(d, (W / 2, 904 - (1 - k4) * 16), "Yorumlara yaz", F(44, False), ETIKET + (int(255 * k4),), anchor="mm")
        ax, ay = W / 2, 954 - (1 - k4) * 10
        d.polygon([(ax - 22, ay), (ax + 22, ay), (ax, ay + 26)], fill=ETIKET + (int(255 * k4),))
        k5 = kademe(4)                                       # TAKIP ET dugmesi (hafif nabiz)
        nabiz = 1 + 0.028 * math.sin((t - self.C) * 2 * math.pi / (2 * B))
        bw, bh = 400, 108
        btn = Image.new("RGBA", (bw + 160, bh + 160), (0, 0, 0, 0))
        ImageDraw.Draw(btn).rounded_rectangle([80, 80, 80 + bw, 80 + bh], bh // 2, fill=tuple(MAVI) + (140,))
        btn = btn.filter(ImageFilter.GaussianBlur(24))
        bd = ImageDraw.Draw(btn)
        bd.rounded_rectangle([80, 80, 80 + bw, 80 + bh], bh // 2, fill=(255, 255, 255, 255))
        bd.text((80 + bw / 2, 80 + bh / 2 - 2), "TAKİP ET", font=F(62), fill=(12, 14, 24, 255), anchor="mm")
        koy(im, btn, W / 2, 1104 + (1 - k5) * 20, k5, nabiz, merkez=True)
        k6 = kademe(5)
        yaz(d, (W / 2, 1208 + (1 - k6) * 12), "Her maç, her oyuncu, veriyle", F(34, False), SOLUK + (int(255 * k6),), anchor="mm")


# ---------------- cikti ----------------
def render(ka, kb, satirlar, ust, yol):
    """Videoyu (sessiz) yazar; (yol, Video) doner."""
    v = Video(ka, kb, satirlar, ust)
    OUT.mkdir(exist_ok=True)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "21",
                           "-preset", "medium", "-movflags", "+faststart", str(yol)], stdin=subprocess.PIPE)
    for n in range(int(v.sure * FPS)):
        ff.stdin.write(v.kare(n / FPS).tobytes())
    ff.stdin.close()
    ff.wait()
    return Path(yol), v


def muzik_ekle(yol, v):
    """Muzik + vurusa kilitli efektler: acilista ve sonucta darbe, satir yerlesince tik, sonucta parilti."""
    import muzik
    return Path(muzik.videoya_ekle(yol, v.darbeler, 1.0, "harici", str(MUZIK), -22, sfx=v.sfx))


def uret_sezon(rol, a, b, ust="SÜPER LİG  ·  SEZON KARŞILAŞTIRMASI"):
    """sezon.mac_oncesi_cifti / cift_kart cikti oyuncularindan muzikli video; mp4 yolunu doner."""
    ka, kb, sat = sezon_oyunculari(rol, a, b)
    yol, v = render(ka, kb, sat, ust, OUT / f"vid_{ka['id']}_{kb['id']}.mp4")
    return muzik_ekle(yol, v)


def uret_mac(ev, rol, oa, ob):
    """duello.kart_uret ciktisindan (ev, rol, oa, ob) muzikli mac sonu duello videosu."""
    c = ev["header"]["competitions"][0]["competitors"]
    ev_s = next(t for t in c if t["homeAway"] == "home")
    dep = next(t for t in c if t["homeAway"] == "away")
    skor = (f'{kart_v2.takim_adi(ev_s["team"]["displayName"])} {ev_s["score"]}-{dep["score"]} '
            f'{kart_v2.takim_adi(dep["team"]["displayName"])}')
    ka, kb, sat = mac_oyunculari(rol, oa, ob)
    yol, v = render(ka, kb, sat, f"MAÇ SONU  ·  {skor}", OUT / f"vid_mac_{ka['id']}_{kb['id']}.mp4")
    return muzik_ekle(yol, v)


def uret(ad1, ad2):
    ka, kb, sat = hazirla(ad1, ad2)
    yol, v = render(ka, kb, sat, "SÜPER LİG  ·  SEZON KARŞILAŞTIRMASI", OUT / f"duello_{ka['id']}_{kb['id']}.mp4")
    return yol, v


def main():
    argv = sys.argv[1:]
    kareler = None
    if "--kare" in argv:
        i = argv.index("--kare")
        kareler = [float(x) for x in argv[i + 1].split(",")]
        argv = argv[:i] + argv[i + 2:]
    a = [x for x in argv if not x.startswith("--")]
    if len(a) != 2:
        raise SystemExit(__doc__)
    if kareler:
        ka, kb, sat = hazirla(a[0], a[1])
        v = Video(ka, kb, sat, "SÜPER LİG  ·  SEZON KARŞILAŞTIRMASI")
        OUT.mkdir(exist_ok=True)
        for t in kareler:
            yol = OUT / f"_kare_{t:g}.png"
            v.kare(t).save(yol)
            print(yol)
        print("sure", round(v.sure, 1), "sn | R", round(v.R, 1), "| C", round(v.C, 1))
        return
    yol, v = uret(a[0], a[1])
    print(v.ka["ad"], v.puan[0], "-", v.puan[1], v.kb["ad"], "| sure", round(v.sure, 1), "sn |", len(v.sat), "satir")
    print(yol)


if __name__ == "__main__":
    main()

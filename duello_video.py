"""Oyuncu karsilastirma videosu (sezon): ~20 sn, kare (1080x1080), sesi kapali da anlasilir.

Kurgu (kisa video kurallari): 0. karede hook ("A mi B mi?"), satirlar tek tek acilir (barlar buyur,
sayilar sayar, kazanan vurgulanir, skor yukselir = acik dongu), sonda sonuc + "Sen kimi seçerdin?" ve
son karede basa donen kapanis. Veri: sezon karsilastirma kartiyla ayni (ESPN + Transfermarkt).

Kullanim:
  python duello_video.py Osimhen Muriqi          # out/duello_<id>_<id>.mp4 (+ muzik icin muzik.py)
"""
import subprocess
import sys

from PIL import Image, ImageDraw

import fotograf
import kart_v2
import satirlar as _satir
import sezon
from baski_video import FPS, OUT, _tiktok, _x_logo
from duello import buyuk, font, sigdir

W = H = 1080
ARKA, PANEL = kart_v2.ARKA, kart_v2.PANEL
KIRMIZI, MAVI, BEYAZ = kart_v2.KIRMIZI, kart_v2.MAVI, kart_v2.BEYAZ
ETIKET, SOLUK = kart_v2.ETIKET, kart_v2.SOLUK
HOOK_SN, SATIR_SN, SONUC_SN, CTA_SN, DONGU_SN = 1.8, 1.5, 2.6, 2.2, 0.5


def _vis(t, t0, sure):
    return max(0.0, min(1.0, (t - t0) / sure))


def _ease(p):
    return 1 - (1 - p) ** 3


def hazirla(ad1, ad2):
    oyuncular = sezon.sezon_verisi()
    a, b = sezon.ada_gore(oyuncular, ad1), sezon.ada_gore(oyuncular, ad2)
    rol = a["rol"]
    oy = lambda o: {"id": o["id"], "ad": o["ad"], "takim": o["takim"], "yas": o.get("yas"), "st": o["st"],  # noqa: E731
                    "satir2": None}
    ka, kb = oy(a), oy(b)
    sat = _satir.sezon_satirlari(rol)
    sat = [r for r in sat if not (r[0] == "puan" and kart_v2._deger(ka, "puan") is None
                                  and kart_v2._deger(kb, "puan") is None)]
    satirlar = []
    for alan, etiket in sat:
        va, vb = kart_v2._deger(ka, alan), kart_v2._deger(kb, alan)
        wa, wb = kart_v2._kazanan(alan, va, vb, sezon.KOTU)
        satirlar.append({"alan": alan, "etiket": etiket, "va": va, "vb": vb, "wa": wa, "wb": wb})
    return ka, kb, satirlar


class Video:
    def __init__(self, ka, kb, satirlar):
        self.ka, self.kb, self.sat = ka, kb, satirlar
        self.n = len(satirlar)
        self.t_satir0 = HOOK_SN
        self.t_son = self.t_satir0 + self.n * SATIR_SN + 0.3
        self.t_cta = self.t_son + SONUC_SN
        self.t_bitis = self.t_cta + CTA_SN
        self.sure = self.t_bitis + DONGU_SN
        self.puan = (sum(r["wa"] for r in satirlar), sum(r["wb"] for r in satirlar))
        self.taban = self._taban()

    # ---- zemin: foto, isim, takim (hareketsiz) ----
    def _taban(self):
        im = Image.new("RGB", (W, H), ARKA)
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, W // 2, 8], fill=KIRMIZI)
        d.rectangle([W // 2, 0, W, 8], fill=MAVI)
        for o, cx, renk in ((self.ka, 270, KIRMIZI), (self.kb, 810, MAVI)):
            foto, kaynak = fotograf.foto_al(o["ad"], o["takim"])
            o["_foto"] = kaynak
            fotograf.daire_yapistir(im, foto, cx - 85, 56, 170, renk=renk)
            d = ImageDraw.Draw(im)
            ad = buyuk(o["ad"])
            d.text((cx - d.textlength(ad, font=sigdir(d, ad, 500, 50)) / 2, 244), ad, font=sigdir(d, ad, 500, 50), fill=BEYAZ)
            l1 = (f'{o["yas"]} yaş · ' if o.get("yas") else "") + kart_v2.takim_adi(o["takim"])
            f1 = sigdir(d, l1, 500, 28, False, 20)
            d.text((cx - d.textlength(l1, font=f1) / 2, 304), l1, font=f1, fill=ETIKET)
            pd = kart_v2.piyasa_degeri(o)
            o["_deger"] = pd
            if pd:
                f2 = font(26, False)
                tx = f"Değer: {pd}"
                d.text((cx - d.textlength(tx, font=f2) / 2, 338), tx, font=f2, fill=SOLUK)
        d.text((W / 2 - d.textlength("VS", font=font(38)) / 2, 104), "VS", font=font(38), fill=SOLUK)
        # alt: hesap
        f40 = font(40)
        tw = d.textlength("@StatDuel", font=f40)
        ik, bos = 40, 14
        x = W / 2 - (tw + 2 * (ik + bos)) / 2
        _tiktok(d, x, 1024, ik)
        _x_logo(d, x + ik + bos, 1024, ik)
        d.text((x + 2 * (ik + bos), 1022), "@StatDuel", font=f40, fill=BEYAZ)
        return im

    def _puan_t(self, t):
        """t anindaki skor (ilk, ikinci): bir satir bittiginde (acilis + 1.0 sn) artar."""
        pa = pb = 0
        for i, r in enumerate(self.sat):
            if t >= self.t_satir0 + i * SATIR_SN + 1.0:
                pa += r["wa"]
                pb += r["wb"]
        return pa, pb

    def kare(self, t):
        if t > self.t_bitis:                                     # basa donen kapanis: son kare -> hook karesi
            q = _vis(t, self.t_bitis, DONGU_SN)
            return Image.blend(self._kare(self.t_bitis - 1e-3), self._kare(0.2), q)
        return self._kare(t)

    def _kare(self, t):
        im = self.taban.copy()
        d = ImageDraw.Draw(im, "RGBA")
        pa, pb = self._puan_t(t)
        ts = f"{pa} - {pb}"
        d.text((W / 2 - d.textlength(ts, font=font(86)) / 2, 142), ts, font=font(86), fill=BEYAZ)
        # satirlar
        n = self.n
        h = min(72, (990 - 400) // max(n, 1))
        y0 = 400
        for i, r in enumerate(self.sat):
            ts0 = self.t_satir0 + i * SATIR_SN
            p_gir = _ease(_vis(t, ts0, 0.35))
            if p_gir <= 0:
                continue
            p_say = _ease(_vis(t, ts0 + 0.3, 0.7))
            y = y0 + i * h + int((1 - p_gir) * 18)
            al = int(255 * p_gir)
            etiket = r["etiket"]
            fe = sigdir(d, etiket, 380, 26, False, 20)
            d.text((W / 2 - d.textlength(etiket, font=fe) / 2, y + 2), etiket, font=fe, fill=ETIKET + (al,))
            va, vb = r["va"], r["vb"]
            mx = max(abs(va or 0), abs(vb or 0), 1e-9)
            for v_, cx, renk, kaz, yon in ((va, 150, KIRMIZI, r["wa"], -1), (vb, W - 150, MAVI, r["wb"], 1)):
                uz = int(250 * (abs(v_ or 0) / mx) * p_say)
                bx0 = W / 2 + yon * 70
                d.rounded_rectangle([min(bx0, bx0 + yon * uz), y + h - 28, max(bx0, bx0 + yon * uz), y + h - 14], 6,
                                    fill=renk + (al,))
                gosterilen = None if v_ is None else v_ * p_say
                tx = kart_v2._metin(gosterilen, r["alan"]) if gosterilen is not None else "–"
                fn = font(48)
                w = d.textlength(tx, font=fn)
                kazandi = kaz and t >= ts0 + 1.0
                if kazandi:
                    pw = max(w + 44, 120)
                    pop = 1 + 0.12 * max(0.0, 1 - (t - ts0 - 1.0) / 0.3)
                    d.rounded_rectangle([cx - pw * pop / 2, y + 2, cx + pw * pop / 2, y + 52 * pop], 14, fill=renk)
                d.text((cx - w / 2, y + 1), tx, font=fn, fill=BEYAZ + (al,))
            d.line([60, y + h - 4, W - 60, y + h - 4], fill=kart_v2.CIZGI, width=2)
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        o = ImageDraw.Draw(ov)
        # hook (ilk kare): satirlar acilmadan once buyuk soru
        if t < HOOK_SN + 0.2:
            a = int(255 * (1 - _vis(t, HOOK_SN - 0.2, 0.4)))
            o.rounded_rectangle([60, 470, W - 60, 790], 28, fill=PANEL + (int(a * 0.96),))
            for k, (m, f, renk) in enumerate(((buyuk(self.ka["ad"].split()[-1]), font(112), KIRMIZI),
                                              ("mı yoksa", font(46, False), ETIKET),
                                              (buyuk(self.kb["ad"].split()[-1]) + " ?", font(112), MAVI))):
                yy = [490, 622, 664][k]
                o.text((W / 2 - o.textlength(m, font=f) / 2, yy), m, font=f, fill=renk + (a,))
        # sonuc ve cta
        if t >= self.t_son:
            if t < self.t_cta:
                yaz = [("SONUÇ", font(38), ETIKET)]
                if self.puan[0] == self.puan[1]:
                    yaz += [("BERABERE", font(110), BEYAZ), (f"{self.puan[0]} - {self.puan[1]} satır", font(46, False), ETIKET)]
                else:
                    k = self.ka if self.puan[0] > self.puan[1] else self.kb
                    renk = KIRMIZI if k is self.ka else MAVI
                    yaz += [(buyuk(k["ad"].split()[-1]), font(120), renk),
                            (f"{max(self.puan)} - {min(self.puan)} satırda üstün", font(46, False), ETIKET)]
                ys = [490, 548, 690]
            else:
                yaz = [("Sen kimi", font(100), BEYAZ), ("seçerdin?", font(100), BEYAZ)]
                ys = [520, 628]
            p = _ease(_vis(t, self.t_son if t < self.t_cta else self.t_cta, 0.35))
            o.rounded_rectangle([60, 450, W - 60, 790], 28, fill=PANEL + (int(255 * p),), outline=(60, 68, 92, int(255 * p)), width=3)
            for (m, f, renk), yy in zip(yaz, ys):
                o.text((W / 2 - o.textlength(m, font=f) / 2, yy), m, font=f, fill=renk + (int(255 * p),))
        im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
        return im


def uret(ad1, ad2):
    ka, kb, sat = hazirla(ad1, ad2)
    v = Video(ka, kb, sat)
    OUT.mkdir(exist_ok=True)
    yol = OUT / f"duello_{ka['id']}_{kb['id']}.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                           "-preset", "medium", str(yol)], stdin=subprocess.PIPE)
    for n in range(int(v.sure * FPS)):
        ff.stdin.write(v.kare(n / FPS).tobytes())
    ff.stdin.close()
    ff.wait()
    return yol, v


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if len(a) != 2:
        raise SystemExit(__doc__)
    yol, v = uret(a[0], a[1])
    print(v.ka["ad"], v.puan[0], "-", v.puan[1], v.kb["ad"], "| sure", round(v.sure, 1), "sn |", len(v.sat), "satir")
    print(yol)


if __name__ == "__main__":
    main()

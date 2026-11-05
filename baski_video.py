"""Mac baski videosu: 3D saha uzerinde iki takimin baskisi (yukselen yuzey), skor, gol anlari.

VERI NOTU (onemli): Ucretsiz kaynaklarda dakika dakika baski verisi yok. Gercek veri:
  - yari bazli atak, tehlikeli atak, sut, korner (apifootball.com; 1. yari ve tum mac, 2. yari = fark)
  - gol/kart dakikalari
Dakikalara dagitim BIR MODELDIR: her yarinin toplami gercek veriyle birebir ayni kalir, yari ici
dalgalanma ve gol oncesi yukselis sentetiktir. Videoda bu acikca yazar ("Baski: model tahmini").

Kullanim:
  python baski_video.py --tarih 2026-10-26 --takim Galatasaray --onizleme 62     # tek kare PNG
  python baski_video.py --tarih 2026-10-26 --takim Galatasaray                    # MP4
Ortam: APIFOOTBALL_KEY
"""
import json
import math
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

KLASOR = Path(__file__).parent
OUT = KLASOR / "out"
FONT_B = KLASOR / "fonts" / "BarlowCondensed-SemiBold.ttf"
FONT_R = KLASOR / "fonts" / "Barlow-Regular.ttf"

W = H = 1080
SS = 1.5                      # yuzey icin ust ornekleme
FPS = 30
NX, NY = 52, 30               # yuzey izgarasi
PITCH_L, PITCH_W = 105.0, 68.0
ARKA = (8, 9, 14)
KIRMIZI = (230, 57, 70)
MAVI = (46, 134, 222)
BEYAZ = (255, 255, 255)
GRI = (160, 168, 188)
SOLUK = (110, 118, 140)
SARI = (255, 214, 10)


# ---------------- veri ----------------
def _af(sorgu):
    k = os.environ.get("APIFOOTBALL_KEY") or os.environ.get("AF_KEY")
    if not k:
        raise SystemExit("APIFOOTBALL_KEY ortam degiskeni yok")
    with urllib.request.urlopen(f"https://apiv3.apifootball.com/?{sorgu}&APIkey={k}", timeout=60) as r:
        return json.load(r)


def mac_bul(tarih, takim):
    ev = _af(f"action=get_events&from={tarih}&to={tarih}&league_id=322")
    if not isinstance(ev, list):
        raise SystemExit(f"apifootball yaniti: {ev}")
    for e in ev:
        if takim.lower() in (e["match_hometeam_name"] + " " + e["match_awayteam_name"]).lower():
            return e
    raise SystemExit(f"{tarih} tarihinde '{takim}' maci bulunamadi")


def _dk(s):
    s = str(s)
    if "+" in s:
        a, b = s.split("+")
        return int(a), int(b)
    return int(s), 0


def _stat(liste):
    d = {}
    for s in liste or []:
        d.setdefault(s["type"], (s["home"], s["away"]))
    return d


def _say(x):
    return int(str(x).replace("%", "") or 0)


def veri_hazirla(e):
    """apifootball olayindan modelin girdisi: takimlar, skor olaylari, yari istatistikleri."""
    ham = [_dk(g["time"]) for g in e.get("goalscorer", []) + e.get("cards", [])]
    s1 = max([x for b, x in ham if b == 45] + [2])
    s2 = max([x for b, x in ham if b == 90] + [4])
    t1, t2 = 45 + s1, 45 + s1 + 45 + s2

    def zaman(dk):
        b, x = _dk(dk)
        if b == 45 and x:
            return 45 + x
        if b == 90 and x:
            return 90 + s1 + x
        return b + (s1 if b > 45 else 0)

    goller = []
    for g in e.get("goalscorer", []):
        ev = bool(g.get("home_scorer"))
        goller.append({"t": zaman(g["time"]), "dk": g["time"], "takim": "ev" if ev else "dep",
                       "oyuncu": g.get("home_scorer") or g.get("away_scorer"),
                       "skor": g.get("score", "")})
    kartlar = [{"t": zaman(c["time"]), "takim": "ev" if c.get("home_fault") else "dep", "kart": c.get("card", "")}
              for c in e.get("cards", [])]
    tam, y1 = _stat(e["statistics"]), _stat(e["statistics_1half"])

    def yari(tur):
        """[(ev, dep) 1. yari, (ev, dep) 2. yari]"""
        a1, b1 = _say(y1.get(tur, (0, 0))[0]), _say(y1.get(tur, (0, 0))[1])
        a, b = _say(tam.get(tur, (0, 0))[0]), _say(tam.get(tur, (0, 0))[1])
        return (a1, b1), (max(a - a1, 0), max(b - b1, 0))
    return {
        "id": e["match_id"], "ev": e["match_hometeam_name"], "dep": e["match_awayteam_name"],
        "tarih": e["match_date"], "t1": t1, "t2": t2, "s1": s1, "goller": sorted(goller, key=lambda g: g["t"]),
        "kartlar": kartlar,
        "stat": {tur: yari(tur) for tur in ("Dangerous Attacks", "Attacks", "Shots Total", "Corners", "Shots On Goal")},
        "pos1": (y1.get("Ball Possession", ("50%", "50%"))),
        "skor": (e["match_hometeam_score"], e["match_awayteam_score"]),
    }


# ---------------- model: yari bazli gercek toplamlar -> dakikalik baski ----------------
def baski_egrileri(v, adim=0.25):
    """Dakikalik baski egrisi (ev, dep). Her yarinin ortalamasi gercek yari verisinden gelir;
    dalgalanma ve gol oncesi yukselis sentetiktir."""
    T = v["t2"]
    t = np.arange(0, T + adim, adim)
    rng = np.random.default_rng(int(v["id"]) % (2 ** 32))
    sonuc = {}
    for k, idx in (("ev", 0), ("dep", 1)):
        base = np.zeros_like(t)
        for h, (a, b) in enumerate(zip(range(2), range(2))):
            maske = (t <= v["t1"]) if h == 0 else (t > v["t1"])
            st = {tur: v["stat"][tur][h][idx] for tur in v["stat"]}
            skor = st["Dangerous Attacks"] + 0.3 * st["Attacks"] + 0.8 * st["Shots Total"] + 0.5 * st["Corners"]
            sure = (v["t1"] if h == 0 else v["t2"] - v["t1"])
            base[maske] = skor / sure
        # yumusak dalgalanma
        gur = np.zeros_like(t)
        for _ in range(5):
            periyot = rng.uniform(5, 14)
            gur += rng.uniform(0.10, 0.22) * np.sin(2 * math.pi * t / periyot + rng.uniform(0, 6.28))
        egri = base * (1 + gur)
        # golden once atan takimin baskisi artar; yiyen takim sonrasinda toparlanir
        for g in v["goller"]:
            kendi = g["takim"] == k
            if kendi:
                egri += base * 0.9 * np.exp(-((t - (g["t"] - 2.5)) / 2.2) ** 2)
            else:
                egri += base * 0.35 * np.exp(-((t - (g["t"] + 6)) / 5.0) ** 2)
        egri = np.maximum(egri, base * 0.15)
        # her yarinin ortalamasini gercek veriye geri esitle
        for h in range(2):
            maske = (t <= v["t1"]) if h == 0 else (t > v["t1"])
            hedef = base[maske].mean()
            if egri[maske].mean() > 0:
                egri[maske] *= hedef / egri[maske].mean()
        sonuc[k] = egri
    # cok hafif yumusatma (kare gecisleri pürüzsüz)
    kernel = np.ones(int(2.0 / adim)) / int(2.0 / adim)
    for k in sonuc:
        sonuc[k] = np.convolve(sonuc[k], kernel, mode="same")
    return t, sonuc["ev"], sonuc["dep"]


# ---------------- cizim ----------------
def _f(boyut, kalin=True):
    return ImageFont.truetype(str(FONT_B if kalin else FONT_R), int(boyut))


class Sahne:
    def __init__(self, v):
        self.v = v
        self.t, self.pe, self.pd = baski_egrileri(v)
        self.pmax = max(self.pe.max(), self.pd.max())
        xs = np.linspace(0, 1, NX)
        ys = np.linspace(0, 1, NY)
        self.X, self.Y = np.meshgrid(xs, ys, indexing="ij")
        self.faz = np.random.default_rng(int(v["id"]) % 9973).uniform(0, 6.28, 4)
        # ekran geometrisi (Z haric) bir kez
        self.S = int(W * SS)
        th = math.radians(-26)
        self.c, self.s = math.cos(th), math.sin(th)
        self.sc, self.cx, self.cy, self.zs = 8.2 * SS, self.S * 0.5, self.S * 0.555, 24.0 * SS
        Xp, Yp = (self.X - 0.5) * PITCH_L, (self.Y - 0.5) * PITCH_W
        xr, yr = Xp * self.c - Yp * self.s, Xp * self.s + Yp * self.c
        self.bx = self.cx + xr * self.sc
        self.by = self.cy + yr * self.sc * 0.52
        self.yr = yr
        hucre = [(float((yr[i, j] + yr[i + 1, j + 1]) * 0.5), i, j) for i in range(NX - 1) for j in range(NY - 1)]
        hucre.sort()
        self.sira = [(i, j) for _, i, j in hucre]

    def _alan(self, dakika):
        """(Z, w): yuzey yuksekligi ve ev takimi agirligi (0..1) -- izgara boyutunda."""
        i = min(int(dakika / 0.25), len(self.t) - 1)
        ph, pa = self.pe[i], self.pd[i]
        toplam = ph + pa + 1e-9
        dom_h, dom_a = ph / toplam, pa / toplam
        xh = 0.52 + 0.38 * dom_h              # ev: sagdaki kaleye dogru
        xa = 0.48 - 0.38 * dom_a              # dep: soldaki kaleye dogru
        yh = 0.5 + 0.30 * math.sin(2 * math.pi * dakika / 9.0 + self.faz[0])
        ya = 0.5 + 0.30 * math.sin(2 * math.pi * dakika / 11.0 + self.faz[1])
        X, Y = self.X, self.Y

        def tepe(x0, y0, genlik, sx=0.17, sy=0.30):
            prof = 0.30 + 0.70 * np.exp(-((Y - y0) / sy) ** 2)
            return genlik * prof * np.exp(-((X - x0) / sx) ** 2)
        Hh = tepe(xh, yh, 12.0 * ph / self.pmax) + 0.5 * tepe(xh - 0.18, 1 - yh, 8.5 * ph / self.pmax, 0.14, 0.22)
        Ha = tepe(xa, ya, 12.0 * pa / self.pmax) + 0.5 * tepe(xa + 0.18, 1 - ya, 8.5 * pa / self.pmax, 0.14, 0.22)
        Z = Hh + Ha
        w = Hh / (Hh + Ha + 1e-6)
        return Z, w

    def flas(self, dakika, saniye):
        """Gol aninda 0..1 arasi kisa isik (0.5 sn)."""
        f = 0.0
        for g in self.v["goller"]:
            sn = (dakika - g["t"]) * saniye
            if 0 <= sn < 0.5:
                f = max(f, 1 - sn / 0.5)
        return f * 0.55

    def kare(self, dakika, flas=0.0):
        Z, w = self._alan(dakika)
        S = self.S
        im = Image.new("RGB", (S, S), ARKA)
        d = ImageDraw.Draw(im, "RGBA")
        c, s = self.c, self.s
        sc, cx, cy, zs = self.sc, self.cx, self.cy, self.zs

        def proje(x, y, z):
            Xp, Yp = (x - 0.5) * PITCH_L, (y - 0.5) * PITCH_W
            xr, yr = Xp * c - Yp * s, Xp * s + Yp * c
            return cx + xr * sc, cy + yr * sc * 0.52 - z * zs, yr

        # renk: ev kirmizi->turuncu, dep mavi->camgobegi; yukseldikce parlaklasir
        zn = np.clip(Z / 11.0, 0, 1)
        kir = np.array(KIRMIZI, float)
        mav = np.array(MAVI, float)
        sic = np.array((255, 176, 64), float)
        sog = np.array((110, 215, 255), float)
        ev_r = kir[None, None] * (1 - zn[..., None]) + sic[None, None] * zn[..., None] ** 1.4
        dep_r = mav[None, None] * (1 - zn[..., None]) + sog[None, None] * zn[..., None] ** 1.4
        renk = ev_r * w[..., None] + dep_r * (1 - w[..., None])
        dzx = np.gradient(Z, axis=0)
        golge = np.clip(0.80 - 2.2 * dzx, 0.50, 1.25)
        renk = np.clip(renk * golge[..., None], 0, 255)
        taban = 0.20 + 0.80 * np.clip(Z / 1.2, 0, 1)
        renk = renk * taban[..., None] + np.array(ARKA, float) * (1 - taban[..., None])
        # gol flasi: yuzeye beyaz isik
        if flas > 0:
            renk = np.clip(renk + 90 * flas, 0, 255)

        sx = self.bx
        sy = self.by - Z * zs
        renk_h = (renk[:-1, :-1] + renk[1:, :-1] + renk[1:, 1:] + renk[:-1, 1:]) / 4
        for i, j in self.sira:
            pts = [(sx[i, j], sy[i, j]), (sx[i + 1, j], sy[i + 1, j]),
                   (sx[i + 1, j + 1], sy[i + 1, j + 1]), (sx[i, j + 1], sy[i, j + 1])]
            r = renk_h[i, j]
            d.polygon(pts, fill=(int(r[0]), int(r[1]), int(r[2])))

        # saha cizgileri yuzeyin ustunden gecer
        def zf(x, y):
            i = min(int(x * (NX - 1)), NX - 1)
            j = min(int(y * (NY - 1)), NY - 1)
            return Z[i, j]

        def cizgi(noktalar, kalin=2.2, a=210):
            pts = [proje(x, y, zf(x, y) + 0.05)[:2] for x, y in noktalar]
            d.line(pts, fill=(255, 255, 255, a), width=int(kalin * SS), joint="curve")
        dk = lambda *k: [(x, y) for x, y in k]  # noqa: E731
        cizgi(dk((0, 0), (1, 0), (1, 1), (0, 1), (0, 0)))
        cizgi(dk((0.5, 0), (0.5, 1)))
        daire = [(0.5 + (9.15 / PITCH_L) * math.cos(a), 0.5 + (9.15 / PITCH_W) * math.sin(a))
                 for a in np.linspace(0, 2 * math.pi, 48)]
        cizgi(daire)
        for sol in (True, False):
            def kx(v):
                return v if sol else 1 - v
            cizgi(dk((kx(0), 0.5 - 20.16 / PITCH_W), (kx(16.5 / PITCH_L), 0.5 - 20.16 / PITCH_W),
                     (kx(16.5 / PITCH_L), 0.5 + 20.16 / PITCH_W), (kx(0), 0.5 + 20.16 / PITCH_W)))
            cizgi(dk((kx(0), 0.5 - 9.16 / PITCH_W), (kx(5.5 / PITCH_L), 0.5 - 9.16 / PITCH_W),
                     (kx(5.5 / PITCH_L), 0.5 + 9.16 / PITCH_W), (kx(0), 0.5 + 9.16 / PITCH_W)))
        # kaleler parlar (gol flasi)
        if flas > 0:
            for sol in (True,):
                pass
        return im.resize((W, H), Image.LANCZOS)

    # ---- bindirmeler ----
    def bindir(self, im, dakika, saniye):
        v = self.v
        d = ImageDraw.Draw(im, "RGBA")
        gecen = [g for g in v["goller"] if g["t"] <= dakika]
        skor_e = sum(1 for g in gecen if g["takim"] == "ev")
        skor_d = len(gecen) - skor_e
        ad_e, ad_d = _kisa(v["ev"]), _kisa(v["dep"])
        # sol ust: takimlar ve skor
        d.rectangle([48, 54, 100, 60], fill=KIRMIZI)
        d.text((48, 66), ad_e, font=_f(56), fill=BEYAZ)
        d.text((48, 120), str(skor_e), font=_f(150), fill=BEYAZ)
        d.rectangle([300, 54, 352, 60], fill=MAVI)
        d.text((300, 66), ad_d, font=_f(56), fill=BEYAZ)
        d.text((300, 120), str(skor_d), font=_f(150), fill=BEYAZ)
        # gol dakikalari
        y = 290
        for g in gecen:
            renk = KIRMIZI if g["takim"] == "ev" else MAVI
            d.ellipse([48, y + 12, 60, y + 24], fill=renk)
            d.text((70, y), f"{g['dk']}'  {_soyad(g['oyuncu'])}", font=_f(30), fill=BEYAZ)
            y += 36
        # sag ust: dakika ve devre
        gosterim = _gosterim(dakika, v)
        w = d.textlength(gosterim, font=_f(120))
        d.text((W - 48 - w, 54), gosterim, font=_f(120), fill=BEYAZ)
        devre = "1. Yarı" if dakika <= v["t1"] else "2. Yarı"
        d.text((W - 48 - d.textlength(devre, font=_f(34, False)), 176), devre, font=_f(34, False), fill=GRI)
        ust = f"SÜPER LİG · {v['tarih'][8:]}.{v['tarih'][5:7]}"
        d.text((W - 48 - d.textlength(ust, font=_f(30, False)), 218), ust, font=_f(30, False), fill=SOLUK)
        not_ = "Baskı: model tahmini (yarı bazlı gerçek veriden)"
        d.text((W - 48 - d.textlength(not_, font=_f(22, False)), 262), not_, font=_f(22, False), fill=(130, 138, 160))
        # alt: baski grafigi
        self._grafik(d, dakika)
        # gol bildirimi
        for g in v["goller"]:
            gecen_sn = (dakika - g["t"]) * saniye
            if 0 <= gecen_sn <= 2.6:
                a = int(255 * min(1, (2.6 - gecen_sn) / 0.6))
                renk = KIRMIZI if g["takim"] == "ev" else MAVI
                d.rounded_rectangle([W / 2 - 300, 470, W / 2 + 300, 580], 24, fill=(14, 17, 26, int(a * 0.88)),
                                    outline=renk + (a,), width=4)
                m = f"GOL  {g['dk']}'  {_soyad(g['oyuncu'])}"
                d.text((W / 2 - d.textlength(m, font=_f(64)) / 2, 490), m, font=_f(64), fill=(255, 255, 255, a))
        return im

    def _grafik(self, d, dakika):
        v = self.v
        x0, x1, y0, y1 = 70, W - 70, 905, 985
        d.text((x0, y0 - 42), "SALDIRI BASKISI", font=_f(26), fill=GRI)
        mid = (y0 + y1) / 2
        d.line([x0, mid, x1, mid], fill=(60, 66, 86), width=2)
        T = v["t2"]
        i_son = min(int(dakika / 0.25), len(self.t) - 1)
        pm = self.pmax * 1.05

        def X(t):
            return x0 + (x1 - x0) * t / T
        for k, renk, isaret in (("ev", KIRMIZI, -1), ("dep", MAVI, 1)):
            egri = self.pe if k == "ev" else self.pd
            pts = [(X(self.t[i]), mid + isaret * (y1 - y0) / 2 * egri[i] / pm) for i in range(0, i_son + 1, 2)]
            if len(pts) > 1:
                alan = [(pts[0][0], mid)] + pts + [(pts[-1][0], mid)]
                d.polygon(alan, fill=renk + (70,))
                d.line(pts, fill=renk, width=3)
        # yari cizgisi, goller, kartlar
        d.line([X(v["t1"]), y0, X(v["t1"]), y1], fill=(90, 96, 120), width=1)
        for g in v["goller"]:
            if g["t"] <= dakika:
                renk = KIRMIZI if g["takim"] == "ev" else MAVI
                d.line([X(g["t"]), y0 - 6, X(g["t"]), y1 + 6], fill=renk + (200,), width=2)
                d.ellipse([X(g["t"]) - 9, y0 - 22, X(g["t"]) + 9, y0 - 4], fill=BEYAZ, outline=renk, width=3)
        for kt in v["kartlar"]:
            if kt["t"] <= dakika:
                d.rectangle([X(kt["t"]) - 3, y1 + 8, X(kt["t"]) + 3, y1 + 22],
                            fill=SARI if "yellow" in kt["kart"] else KIRMIZI)
        d.line([X(dakika), y0 - 8, X(dakika), y1 + 8], fill=BEYAZ + (230,), width=2)
        d.text((W / 2 - d.textlength("@StatDuel", font=_f(40)) / 2, 1022), "@StatDuel", font=_f(40), fill=BEYAZ)


def _kisa(ad):
    ad = ad.replace("İ", "I").replace("ı", "i")
    harita = {"Fenerbahce": "FEN", "Galatasaray": "GAL", "Besiktas": "BJK", "Trabzonspor": "TRA"}
    return harita.get(ad, ad[:3].upper())


def _soyad(oyuncu):
    return (oyuncu or "").split()[-1] if oyuncu else ""


def _gosterim(dakika, v):
    """Saat gostergesi: gol 29'da olduysa saat 29' gosterirken skor degisir."""
    if dakika <= 45:
        return f"{max(int(dakika), 1)}'"
    if dakika <= v["t1"]:
        return f"45+{max(int(dakika - 45), 1)}'"
    m = dakika - v["s1"]
    if m <= 90:
        return f"{max(int(m), 46)}'"
    return f"90+{max(int(m - 90), 1)}'"


# ---------------- calistirma ----------------
def main():
    a = sys.argv[1:]
    tarih = a[a.index("--tarih") + 1] if "--tarih" in a else None
    takim = a[a.index("--takim") + 1] if "--takim" in a else None
    onizleme = float(a[a.index("--onizleme") + 1]) if "--onizleme" in a else None
    dk_sn = float(a[a.index("--dakika-saniye") + 1]) if "--dakika-saniye" in a else 2.2   # video sn basina mac dakikasi
    if not (tarih and takim):
        raise SystemExit(__doc__)
    v = veri_hazirla(mac_bul(tarih, takim))
    print(v["ev"], v["skor"][0], "-", v["skor"][1], v["dep"], "| goller:", [(g["dk"], g["oyuncu"]) for g in v["goller"]])
    sahne = Sahne(v)
    OUT.mkdir(exist_ok=True)
    if onizleme is not None:
        im = sahne.bindir(sahne.kare(onizleme), onizleme, 1 / dk_sn)
        yol = OUT / f"baski_onizleme_{int(onizleme)}.png"
        im.save(yol)
        print(yol)
        return
    toplam_kare = int((v["t2"] / dk_sn + 3.0) * FPS)
    yol = OUT / f"baski_{v['id']}.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                           "-preset", "medium", str(yol)], stdin=subprocess.PIPE)
    for n in range(toplam_kare):
        dakika = min(n / FPS * dk_sn, v["t2"])
        im = sahne.bindir(sahne.kare(dakika, sahne.flas(dakika, 1 / dk_sn)), dakika, 1 / dk_sn)
        ff.stdin.write(im.tobytes())
        if n % 120 == 0:
            print(f"kare {n}/{toplam_kare}", flush=True)
    ff.stdin.close()
    ff.wait()
    print(yol)


if __name__ == "__main__":
    main()

"""Mac sut haritasi videosu: sutlar GERCEK dakikalarinda, GERCEK sahada yerinde belirir.

Veri: PitchAPI /v1/matches/{id}/shots (her sut icin dakika, saha koordinati (metre), xG, sonuc).
Hicbir sey tahmin edilmez. Ev takimi solda (saga dogru atak), deplasman sagda (sola dogru atak).
Daire buyuklugu = xG. Dolu + beyaz halka = gol, dolu = kurtarilan isabetli sut, halka = isabetsiz/engellenen.

Kullanim:
  python sut_video.py --tarih 2026-10-26 --takim Galatasaray --onizleme 62     # tek kare PNG
  python sut_video.py --tarih 2026-10-26 --takim Galatasaray                    # MP4
Ortam: PITCHAPI_API_KEY
"""
import math
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

from baski_video import (ARKA, BEYAZ, FPS, GRI, KIRMIZI, MAVI, OUT, SOLUK, W, H, _f, _kisa, _pitch, _soyad,
                         _tiktok, _x_logo)

PITCH_L, PITCH_W = 105.0, 68.0
SS = 2                                   # saha cizgileri icin ust ornekleme
PX, PY, PW = 50, 350, 980                # saha: sol, ust, genislik
PH = PW * PITCH_W / PITCH_L
CIM = (17, 24, 33)                       # saha zemini
CIZGI = (70, 82, 104)


# ---------------- veri ----------------
def veri_sut(tarih, takim):
    gun = _pitch(f"/v1/date/{tarih}")
    maclar = gun["matches"] if isinstance(gun, dict) else gun
    m = next((x for x in maclar if "Super Lig" in x["league"]["name"]
              and takim.lower() in (x["home_team"]["name"] + " " + x["away_team"]["name"]).lower()), None)
    if not m:
        raise SystemExit(f"{tarih} tarihinde '{takim}' Super Lig maci bulunamadi")
    r = _pitch(f"/v1/matches/{m['id']}/shots")
    ev_id = m["home_team"]["id"]
    sutlar = []
    for p in r["periods"]:
        for s in p["shots"]:
            ev = s["team_id"] == ev_id
            x, y = (s["x"], s["y"]) if ev else (PITCH_L - s["x"], PITCH_W - s["y"])
            gy = s.get("goal_crossed_y")
            kale = None
            if gy is not None and s["is_on_target"]:
                kale = (PITCH_L if ev else 0.0, gy if ev else PITCH_W - gy)
            tur = ("gol" if s["event_type"] == "Goal" else
                   "kurtarilan" if s["is_on_target"] else
                   "engellenen" if s.get("is_blocked") else "isabetsiz")
            sutlar.append({"t": s["minute"] + 0.4 * (s.get("minute_added") or 0), "dk": s["minute"],
                           "ek": s.get("minute_added") or 0, "ev": ev, "x": x, "y": y, "xg": s["expected_goals"] or 0.0,
                           "tur": tur, "oyuncu": s["player"]["name"], "kale": kale})
    sutlar.sort(key=lambda s: s["t"])
    return {"id": m["id"].replace("m_", "").encode().hex()[:8], "ev": m["home_team"]["name"],
            "dep": m["away_team"]["name"], "tarih": tarih, "skor": (m["score_home"], m["score_away"]),
            "sutlar": sutlar, "t2": max(90.0, max(s["t"] for s in sutlar) + 1)}


# ---------------- cizim ----------------
def _px(x, y, k=1.0):
    return (PX + x / PITCH_L * PW) * k, (PY + y / PITCH_W * PH) * k


def saha_arka():
    """Statik saha (cizgiler) bir kez cizilir."""
    k = SS
    im = Image.new("RGBA", (W * k, H * k), ARKA + (255,))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([(PX - 14) * k, (PY - 14) * k, (PX + PW + 14) * k, (PY + PH + 14) * k], 26 * k, fill=CIM)
    g = max(2, int(2.5 * k))

    def cizgi(pts):
        d.line([_px(x, y, k) for x, y in pts], fill=CIZGI, width=g, joint="curve")
    cizgi([(0, 0), (105, 0), (105, 68), (0, 68), (0, 0)])
    cizgi([(52.5, 0), (52.5, 68)])
    cizgi([(52.5 + 9.15 * math.cos(a), 34 + 9.15 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 60)])
    for sol in (True, False):
        s = (lambda v: v) if sol else (lambda v: 105 - v)
        cizgi([(s(0), 13.84), (s(16.5), 13.84), (s(16.5), 54.16), (s(0), 54.16)])
        cizgi([(s(0), 24.84), (s(5.5), 24.84), (s(5.5), 43.16), (s(0), 43.16)])
        cizgi([(s(-1.8), 30.34), (s(0), 30.34), (s(0), 37.66), (s(-1.8), 37.66)])      # kale
    return im


def _halka(d, cx, cy, r, renk, kalin, dolgu=None):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=dolgu, outline=renk, width=kalin)


class Sahne:
    def __init__(self, v):
        self.v = v
        self.arka = saha_arka()

    def kare(self, dakika, saniye):
        """saniye: bir mac dakikasinin video saniyesi (animasyon sureleri icin)."""
        k = SS
        im = self.arka.copy()
        ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        for s in self.v["sutlar"]:
            if s["t"] > dakika:
                continue
            gecen = (dakika - s["t"]) * saniye                      # video saniyesi
            renk = KIRMIZI if s["ev"] else MAVI
            cx, cy = _px(s["x"], s["y"], k)
            r = (7 + 38 * math.sqrt(max(s["xg"], 0.0))) * k
            pop = min(1.0, gecen / 0.25)
            r *= 0.55 + 0.45 * (1 - (1 - pop) ** 3)
            # kaleye giden cizgi (gol ve kurtarilan): gol icin cizilerek uzar
            if s["kale"] and s["tur"] in ("gol", "kurtarilan"):
                ex, ey = _px(*s["kale"], k)
                oran = min(1.0, gecen / 0.45) if s["tur"] == "gol" else 1.0
                a = 235 if s["tur"] == "gol" else 80
                d.line([(cx, cy), (cx + (ex - cx) * oran, cy + (ey - cy) * oran)],
                       fill=(255, 255, 255, a) if s["tur"] == "gol" else renk + (a,),
                       width=int((4 if s["tur"] == "gol" else 2) * k))
            if s["tur"] == "gol":
                _halka(d, cx, cy, r, BEYAZ + (255,), int(4 * k), renk + (255,))
            elif s["tur"] == "kurtarilan":
                _halka(d, cx, cy, r, renk + (255,), int(2 * k), renk + (190,))
            else:
                _halka(d, cx, cy, r, renk + (235,), int(3 * k), renk + (45,))
            if gecen < 0.9:                                          # dalga halkasi
                p = gecen / 0.9
                big = 2.4 if s["tur"] == "gol" else 1.7
                rr = r * (1 + big * p)
                _halka(d, cx, cy, rr, renk + (int(200 * (1 - p)),), int(3 * k))
        im = Image.alpha_composite(im, ov).resize((W, H), Image.LANCZOS).convert("RGB")
        return self.bindir(im, dakika, saniye)

    def bindir(self, im, dakika, saniye):
        v = self.v
        d = ImageDraw.Draw(im, "RGBA")
        gecen = [s for s in v["sutlar"] if s["t"] <= dakika]
        goller = [s for s in gecen if s["tur"] == "gol"]
        skor_e = sum(1 for g in goller if g["ev"])
        skor_d = len(goller) - skor_e
        ad_e, ad_d = _kisa(v["ev"]), _kisa(v["dep"])
        for x, ad, sk, renk, ev in ((48, ad_e, skor_e, KIRMIZI, True), (300, ad_d, skor_d, MAVI, False)):
            d.rectangle([x, 54, x + 52, 60], fill=renk)
            d.text((x, 66), ad, font=_f(56), fill=BEYAZ)
            d.text((x, 120), str(sk), font=_f(150), fill=BEYAZ)
            ta = [s for s in gecen if s["ev"] == ev]
            xg = sum(s["xg"] for s in ta)
            d.text((x, 282), f"ŞUT {len(ta)}  ·  xG {xg:.2f}", font=_f(34), fill=GRI)
        # sag ust: dakika
        gosterim = f"{min(max(int(dakika), 1), 90)}'" if dakika <= 90 else f"90+{int(dakika - 90) + 1}'"
        w = d.textlength(gosterim, font=_f(120))
        d.text((W - 48 - w, 54), gosterim, font=_f(120), fill=BEYAZ)
        devre = "1. Yarı" if dakika <= 45.9 else "2. Yarı"
        d.text((W - 48 - d.textlength(devre, font=_f(34, False)), 176), devre, font=_f(34, False), fill=GRI)
        ust = f"SÜPER LİG · {v['tarih'][8:]}.{v['tarih'][5:7]}"
        d.text((W - 48 - d.textlength(ust, font=_f(30, False)), 218), ust, font=_f(30, False), fill=SOLUK)
        # aciklama
        ac = "Daire büyüklüğü = xG   ·   Beyaz halka = gol   ·   Dolu = isabetli   ·   Boş = isabetsiz / engellendi"
        d.text(((W - d.textlength(ac, font=_f(22, False))) / 2, 362), ac, font=_f(22, False), fill=SOLUK)
        # gol bildirimi
        for s in goller:
            gs = (dakika - s["t"]) * saniye
            if 0 <= gs <= 2.6:
                a = int(255 * min(1, (2.6 - gs) / 0.6))
                renk = KIRMIZI if s["ev"] else MAVI
                d.rounded_rectangle([W / 2 - 300, 610, W / 2 + 300, 720], 24, fill=(14, 17, 26, int(a * 0.92)),
                                    outline=renk + (a,), width=4)
                m = f"GOL  {s['dk']}'  {_soyad(s['oyuncu'])}"
                d.text((W / 2 - d.textlength(m, font=_f(64)) / 2, 630), m, font=_f(64), fill=(255, 255, 255, a))
        # alt: hesap
        f40 = _f(40)
        tw = d.textlength("@StatDuel", font=f40)
        ik, bos = 40, 14
        x = W / 2 - (tw + 2 * (ik + bos)) / 2
        _tiktok(d, x, 1024, ik)
        _x_logo(d, x + ik + bos, 1024, ik)
        d.text((x + 2 * (ik + bos), 1022), "@StatDuel", font=f40, fill=BEYAZ)
        return im


def _render(v, sahne, dk_sn):
    toplam = int((v["t2"] / dk_sn + 3.0) * FPS)
    yol = OUT / f"sut_{v['id']}.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                           "-preset", "medium", str(yol)], stdin=subprocess.PIPE)
    for n in range(toplam):
        dakika = min(n / FPS * dk_sn, v["t2"])
        ff.stdin.write(sahne.kare(dakika, 1 / dk_sn).tobytes())
        if n % 120 == 0:
            print(f"kare {n}/{toplam}", flush=True)
    ff.stdin.close()
    ff.wait()
    return yol



def uret(tarih, takim, dk_sn=2.2):
    """Otomasyon girisi: (mp4 yolu, gol dakikalari)."""
    v = veri_sut(tarih, takim)
    OUT.mkdir(exist_ok=True)
    yol = _render(v, Sahne(v), dk_sn)
    return yol, [s["t"] for s in v["sutlar"] if s["tur"] == "gol"]


def main():
    a = sys.argv[1:]
    tarih = a[a.index("--tarih") + 1] if "--tarih" in a else None
    takim = a[a.index("--takim") + 1] if "--takim" in a else None
    onizleme = float(a[a.index("--onizleme") + 1]) if "--onizleme" in a else None
    dk_sn = float(a[a.index("--dakika-saniye") + 1]) if "--dakika-saniye" in a else 2.2
    if not (tarih and takim):
        raise SystemExit(__doc__)
    v = veri_sut(tarih, takim)
    gol = [(s["dk"], s["oyuncu"]) for s in v["sutlar"] if s["tur"] == "gol"]
    print(v["ev"], v["skor"][0], "-", v["skor"][1], v["dep"], "| sut:", len(v["sutlar"]), "| goller:", gol)
    print("GOLLER_DK:", ",".join(str(g[0]) for g in gol))
    sahne = Sahne(v)
    OUT.mkdir(exist_ok=True)
    if onizleme is not None:
        yol = OUT / f"sut_onizleme_{int(onizleme)}.png"
        sahne.kare(onizleme, 1 / dk_sn).save(yol)
        print(yol)
        return
    print(_render(v, sahne, dk_sn))


if __name__ == "__main__":
    main()

"""Oyuncu isi haritasi karti ve videosu (GERCEK veri): PitchAPI /v1/matches/{id}/heatmaps (16x12 izgara).

Isi haritasi dakika dakika degil, maç toplamidir; kart ve video bunu acikca belirtir. Atak yonu hep saga dogrudur.
Videoda isi SABIT durur; saat akar, oyuncunun sutlari ve macin golleri gercek dakikalarinda belirir.

Kullanim:
  python isi_haritasi.py --tarih 2026-11-01 --takim "Real Madrid" --oyuncu "Arda Güler" [--video]
Ortam: PITCHAPI_API_KEY
"""
import math
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

import fotograf
from baski_video import (ARKA, BEYAZ, FPS, GRI, KIRMIZI, MAVI, OUT, SOLUK, W, H, _f, _pitch, _tiktok, _x_logo)
from sut_video import PH, PW, PX, PY, _px, saha_arka

SS = 2
DURAKLAR = [(0.00, (0, 0, 0, 0)), (0.12, (36, 52, 190, 90)), (0.35, (120, 40, 200, 170)),
            (0.60, (235, 70, 90, 215)), (0.82, (255, 160, 50, 235)), (1.00, (255, 238, 110, 250))]


def _renk(v):
    """0..1 -> RGBA (n,m,4)."""
    cikti = np.zeros(v.shape + (4,), float)
    xs = [d[0] for d in DURAKLAR]
    for k in range(4):
        cikti[..., k] = np.interp(v, xs, [d[1][k] for d in DURAKLAR])
    return cikti.astype(np.uint8)


def isi_matrisi(cells, grid_l=16, grid_w=12, cozunurluk=2.0, sigma_m=5.5):
    """Seyrek [cx, cy, adet] uclulari -> puruzsuz isi (0..1), boyut (68*c, 105*c)."""
    nx, ny = int(105 * cozunurluk), int(68 * cozunurluk)
    a = np.zeros((ny, nx))
    for cx, cy, n in cells:
        x = int((cx + 0.5) / grid_l * nx)
        y = int((cy + 0.5) / grid_w * ny)
        a[min(y, ny - 1), min(x, nx - 1)] += n
    s = sigma_m * cozunurluk
    r = int(s * 3)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / s) ** 2)
    k /= k.sum()
    a = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), 1, a)
    a = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), 0, a)
    return a / max(a.max(), 1e-9)


def veri(tarih, takim, oyuncu):
    """Mac + oyuncunun isi hucreleri, sutlari, oynadigi sure, macin golleri."""
    gun = _pitch(f"/v1/date/{tarih}")
    m = next((x for x in (gun["matches"] if isinstance(gun, dict) else gun)
              if takim.lower() in (x["home_team"]["name"] + " " + x["away_team"]["name"]).lower()), None)
    if not m:
        raise SystemExit(f"{tarih} tarihinde '{takim}' maci bulunamadi")
    mid = m["id"]
    h = _pitch(f"/v1/matches/{mid}/heatmaps")
    p = next((x for x in h["players"] if oyuncu.lower() in x["player"]["name"].lower()), None)
    if not p:
        raise SystemExit(f"{oyuncu} bu macta isi haritasi verisi yok (oynamamis olabilir)")
    pid = p["player"]["id"]
    sutlar = []
    try:
        for per in _pitch(f"/v1/matches/{mid}/shots")["periods"]:
            for s in per["shots"]:
                if s["player"]["id"] == pid:
                    sutlar.append(s)
    except Exception:
        pass
    ol = _pitch(f"/v1/matches/{mid}/events")["events"]
    cikis = next((e["minute"] for e in ol if e["event_type"].lower() == "substitution"
                  and e["player"]["id"] == pid), None)
    giris = next((e["minute"] for e in ol if e["event_type"].lower() == "substitution"
                  and (e.get("sub_in_player") or {}).get("id") == pid), 0)
    ev_id = m["home_team"]["id"]
    goller = [{"t": e["minute"] + 0.4 * (e.get("minute_added") or 0), "dk": e["minute"],
               "ev": e["team_id"] == ev_id, "oyuncu": e["player"]["name"]}
              for e in ol if e["event_type"].lower() == "goal"]
    goller.sort(key=lambda g: g["t"])
    return {"goller": goller, "mac": m, "oyuncu": p["player"]["name"], "takim": p["team"]["name"],
            "ev": p["side"] == "home", "aksiyon": p["actions"], "cells": p["cells"], "sutlar": sutlar,
            "dk": (cikis or 90) - giris, "giris": giris, "cikis": cikis}


def taban(v):
    """Sutsuz, dinamik yazisiz zemin: saha + isi + ust baslik (foto, isim). RGB 1080x1080."""
    k = SS
    im = saha_arka()
    mat = isi_matrisi(v["cells"])
    rgba = Image.fromarray(_renk(np.clip(mat ** 0.8, 0, 1)), "RGBA")
    rgba = rgba.resize((int(PW * k), int(PH * k)), Image.BICUBIC)
    im.alpha_composite(rgba, (int(PX * k), int(PY * k)))
    d = ImageDraw.Draw(im)
    renk = (255, 255, 255, 120)
    g = max(2, int(2 * k))

    def cz(pts):
        d.line([_px(x, y, k) for x, y in pts], fill=renk, width=g, joint="curve")
    cz([(0, 0), (105, 0), (105, 68), (0, 68), (0, 0)])
    cz([(52.5, 0), (52.5, 68)])
    cz([(52.5 + 9.15 * math.cos(a), 34 + 9.15 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 60)])
    for sol in (True, False):
        s_ = (lambda t: t) if sol else (lambda t: 105 - t)
        cz([(s_(0), 13.84), (s_(16.5), 13.84), (s_(16.5), 54.16), (s_(0), 54.16)])
        cz([(s_(0), 24.84), (s_(5.5), 24.84), (s_(5.5), 43.16), (s_(0), 43.16)])
    im = im.resize((W, H), Image.LANCZOS).convert("RGB")
    foto, _ = fotograf.foto_al(v["oyuncu"], v["takim"])
    fotograf.daire_yapistir(im, foto, 48, 44, 170, renk=KIRMIZI)
    d = ImageDraw.Draw(im, "RGBA")
    d.text((246, 48), v["oyuncu"].upper(), font=_f(78), fill=BEYAZ)
    m = v["mac"]
    tarih = m.get("date") or m["time_utc"][:10]
    d.text((248, 238), f"{tarih[8:]}.{tarih[5:7]}.{tarih[:4]}  ·  {m['league']['name']}", font=_f(30, False), fill=SOLUK)
    d.text((PX + 14, PY + 12), "ATAK YÖNÜ", font=_f(26), fill=(255, 255, 255, 190))
    ax = PX + 14 + d.textlength("ATAK YÖNÜ", font=_f(26)) + 12
    d.line([ax, PY + 28, ax + 34, PY + 28], fill=(255, 255, 255, 190), width=4)
    d.polygon([(ax + 44, PY + 28), (ax + 30, PY + 19), (ax + 30, PY + 37)], fill=(255, 255, 255, 190))
    bx, by, bw = PX + PW - 300, PY + 20, 270
    for i in range(bw):
        c = _renk(np.array([i / bw]))[0]
        d.line([bx + i, by, bx + i, by + 14], fill=tuple(int(x) for x in c[:3]) + (255,))
    d.text((bx, by + 18), "az", font=_f(24, False), fill=GRI)
    d.text((bx + bw - d.textlength("çok", font=_f(24, False)), by + 18), "çok", font=_f(24, False), fill=GRI)
    d.text((PX + 14, PY + PH - 36), f"Isı haritası: maç toplamı, {v['aksiyon']} aksiyon (dakika dakika değil)",
           font=_f(24, False), fill=(255, 255, 255, 150))
    f40 = _f(40)
    tw = d.textlength("@StatDuel", font=f40)
    ik, bos = 40, 14
    x = W / 2 - (tw + 2 * (ik + bos)) / 2
    _tiktok(d, x, 1024, ik)
    _x_logo(d, x + ik + bos, 1024, ik)
    d.text((x + 2 * (ik + bos), 1022), "@StatDuel", font=f40, fill=BEYAZ)
    return im


def _sutlari_ciz(im, v, dakika, saniye, hepsi=False):
    """Sutlari 2x ust ornekleme ile cizer; hepsi=True ise hepsi sabit, degilse dakikasinda animasyonlu belirir."""
    k = SS
    ov = Image.new("RGBA", (W * k, H * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for s in v["sutlar"]:
        t = s["minute"] + 0.4 * (s.get("minute_added") or 0)
        if not hepsi and t > dakika:
            continue
        gecen = 9.0 if hepsi else (dakika - t) * saniye
        cx, cy = _px(s["x"], s["y"], k)
        r = (8 + 36 * math.sqrt(max(s["expected_goals"] or 0, 0))) * k
        r *= 0.55 + 0.45 * (1 - (1 - min(1.0, gecen / 0.25)) ** 3)
        gol = s["event_type"] == "Goal"
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 235) if gol else (10, 12, 20, 170),
                  outline=(255, 255, 255, 255), width=int(3 * k))
        f = _f(24 * k)
        etiket = f"{s['minute']}'"
        d.text((cx - d.textlength(etiket, font=f) / 2, cy + r + 2 * k), etiket, font=f, fill=(255, 255, 255, 255))
        if gecen < 0.9:
            p = gecen / 0.9
            rr = r * (1 + 1.8 * p)
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(255, 255, 255, int(220 * (1 - p))),
                      width=int(3 * k))
    ov = ov.resize((W, H), Image.LANCZOS)
    im.paste(ov, (0, 0), ov)
    return im


def _skor_metni(v, dakika):
    m = v["mac"]
    sh = sum(1 for g in v["goller"] if g["t"] <= dakika and g["ev"])
    sa = sum(1 for g in v["goller"] if g["t"] <= dakika and not g["ev"])
    return f"{m['home_team']['name']} {sh}-{sa} {m['away_team']['name']}"


def kart(v, yol):
    im = taban(v)
    _sutlari_ciz(im, v, None, 1, hepsi=True)
    d = ImageDraw.Draw(im, "RGBA")
    m = v["mac"]
    d.text((248, 142), f"{m['home_team']['name']} {m['score_home']}-{m['score_away']} {m['away_team']['name']}",
           font=_f(40, False), fill=GRI)
    sure = f"{v['dk']} dk oynadı" + (f"  ·  {v['cikis']}' çıktı" if v["cikis"] else "")
    d.text((248, 192), sure, font=_f(34, False), fill=SOLUK)
    OUT.mkdir(exist_ok=True)
    im.save(yol)
    return yol


def video_kare(taban_im, v, dakika, saniye):
    """Isi sabit; saat akar, sutlar ve goller gercek dakikalarinda belirir."""
    im = taban_im.copy()
    _sutlari_ciz(im, v, dakika, saniye)
    d = ImageDraw.Draw(im, "RGBA")
    d.text((248, 142), _skor_metni(v, dakika), font=_f(40, False), fill=GRI)
    oyunda = dakika < (v["cikis"] or 999)
    durum = f"{v['dk']} dk oynadı" if not v["cikis"] else ("Oyunda" if oyunda else f"{v['cikis']}' çıktı")
    d.text((248, 192), durum, font=_f(34, False), fill=(120, 230, 150) if oyunda else SOLUK)
    gosterim = f"{min(max(int(dakika), 1), 90)}'" if dakika <= 90 else f"90+{int(dakika - 90) + 1}'"
    d.text((W - 48 - d.textlength(gosterim, font=_f(120)), 36), gosterim, font=_f(120), fill=BEYAZ)
    for g in v["goller"]:
        gs = (dakika - g["t"]) * saniye
        if 0 <= gs <= 2.6:
            a = int(255 * min(1, (2.6 - gs) / 0.6))
            renk = KIRMIZI if g["ev"] == v["ev"] else MAVI
            d.rounded_rectangle([W / 2 - 300, 610, W / 2 + 300, 720], 24, fill=(14, 17, 26, int(a * 0.92)),
                                outline=renk + (a,), width=4)
            t = f"GOL  {g['dk']}'  {g['oyuncu'].split()[-1]}"
            d.text((W / 2 - d.textlength(t, font=_f(64)) / 2, 630), t, font=_f(64), fill=(255, 255, 255, a))
    return im


def video(v, dk_sn=2.2):
    tb = taban(v)
    t2 = 90.0
    toplam = int((t2 / dk_sn + 3.0) * FPS)
    ad = "".join(c for c in v["oyuncu"].lower() if c.isalnum())
    yol = OUT / f"isi_{ad}.mp4"
    OUT.mkdir(exist_ok=True)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                           "-preset", "medium", str(yol)], stdin=subprocess.PIPE)
    for n in range(toplam):
        dakika = min(n / FPS * dk_sn, t2)
        ff.stdin.write(video_kare(tb, v, dakika, 1 / dk_sn).tobytes())
        if n % 120 == 0:
            print(f"kare {n}/{toplam}", flush=True)
    ff.stdin.close()
    ff.wait()
    return yol


def main():
    a = sys.argv[1:]
    try:
        tarih, takim, oyuncu = (a[a.index(x) + 1] for x in ("--tarih", "--takim", "--oyuncu"))
    except ValueError:
        raise SystemExit(__doc__)
    v = veri(tarih, takim, oyuncu)
    ad = "".join(c for c in v["oyuncu"].lower() if c.isalnum())
    print(v["oyuncu"], v["takim"], "| aksiyon", v["aksiyon"], "| sut", len(v["sutlar"]), "| dk", v["dk"],
          "| goller", [(g["dk"], g["oyuncu"]) for g in v["goller"]])
    if "--video" in a:
        print(video(v))
        print("GOLLER_DK:", ",".join(str(g["t"]) for g in v["goller"]))
    else:
        print(kart(v, OUT / f"isi_{ad}.png"))


if __name__ == "__main__":
    main()

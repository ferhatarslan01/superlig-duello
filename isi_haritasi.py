"""Oyuncu isi haritasi karti (GERCEK veri): PitchAPI /v1/matches/{id}/heatmaps (16x12 izgara, maç toplami).

Isi haritasi dakika dakika degil, maç toplamidir; kart bunu acikca belirtir. Atak yonu hep saga dogrudur.
Oyuncunun sutlari (varsa) dakikalariyla uzerine eklenir.

Kullanim:
  python isi_haritasi.py --tarih 2026-11-01 --takim "Real Madrid" --oyuncu "Arda Güler"
Ortam: PITCHAPI_API_KEY
"""
import math
import sys
from datetime import date, timedelta

import numpy as np
from PIL import Image, ImageDraw

import fotograf
from baski_video import ARKA, BEYAZ, GRI, KIRMIZI, OUT, SOLUK, W, H, _f, _pitch, _tiktok, _x_logo
from sut_video import CIM, PH, PW, PX, PY, _px, saha_arka

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
    """Seyrek [cx, cy, adet] uclulari -> pürüzsüz isi (0..1), boyut (68*c, 105*c)."""
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
    """Mac + oyuncunun isi hucreleri, sutlari, oynadigi sure."""
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
    ev_mi = p["side"] == "home"
    ol = _pitch(f"/v1/matches/{mid}/events")["events"]
    cikis = next((e["minute"] for e in ol if e["event_type"].lower() == "substitution"
                  and e["player"]["id"] == pid), None)
    giris = next((e["minute"] for e in ol if e["event_type"].lower() == "substitution"
                  and (e.get("sub_in_player") or {}).get("id") == pid), 0)
    return {"mac": m, "oyuncu": p["player"]["name"], "takim": p["team"]["name"], "ev": ev_mi,
            "aksiyon": p["actions"], "cells": p["cells"], "sutlar": sutlar,
            "dk": (cikis or 90) - giris, "giris": giris, "cikis": cikis}


def kart(v, yol):
    k = SS
    im = saha_arka()
    mat = isi_matrisi(v["cells"])
    rgba = Image.fromarray(_renk(np.clip(mat ** 0.8, 0, 1)), "RGBA")
    rgba = rgba.resize((int(PW * k), int(PH * k)), Image.BICUBIC)
    im.alpha_composite(rgba, (int(PX * k), int(PY * k)))
    # saha cizgilerini isinin ustunden bir kez daha ince ciz (okunurluk)
    cizgi = saha_arka()
    maske = Image.new("L", im.size, 0)
    ImageDraw.Draw(maske).rectangle([0, 0, *im.size], fill=0)
    d = ImageDraw.Draw(im)
    renk = (255, 255, 255, 120)
    g = max(2, int(2 * k))

    def cz(pts):
        d.line([_px(x, y, k) for x, y in pts], fill=renk, width=g, joint="curve")
    cz([(0, 0), (105, 0), (105, 68), (0, 68), (0, 0)])
    cz([(52.5, 0), (52.5, 68)])
    cz([(52.5 + 9.15 * math.cos(a), 34 + 9.15 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 60)])
    for sol in (True, False):
        s = (lambda t: t) if sol else (lambda t: 105 - t)
        cz([(s(0), 13.84), (s(16.5), 13.84), (s(16.5), 54.16), (s(0), 54.16)])
        cz([(s(0), 24.84), (s(5.5), 24.84), (s(5.5), 43.16), (s(0), 43.16)])
    # sutlar
    for s in v["sutlar"]:
        cx, cy = _px(s["x"], s["y"], k)
        r = (8 + 36 * math.sqrt(max(s["expected_goals"] or 0, 0))) * k
        gol = s["event_type"] == "Goal"
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 235) if gol else (10, 12, 20, 170),
                  outline=(255, 255, 255, 255), width=int(3 * k))
        t = f"{s['minute']}'"
        f = _f(24 * k)
        d.text((cx - d.textlength(t, font=f) / 2, cy + r + 2 * k), t, font=f, fill=(255, 255, 255, 255))
    im = im.resize((W, H), Image.LANCZOS).convert("RGB")
    d = ImageDraw.Draw(im, "RGBA")
    # ust: foto, isim, mac
    foto, _ = fotograf.foto_al(v["oyuncu"], v["takim"])
    fotograf.daire_yapistir(im, foto, 48, 44, 170, renk=KIRMIZI)
    d = ImageDraw.Draw(im, "RGBA")
    d.text((246, 48), v["oyuncu"].upper(), font=_f(84), fill=BEYAZ)
    m = v["mac"]
    skor = f"{m['home_team']['name']} {m['score_home']}-{m['score_away']} {m['away_team']['name']}"
    d.text((248, 142), skor, font=_f(40, False), fill=GRI)
    sure = f"{v['dk']} dk oynadı" + (f"  ·  {v['cikis']}' çıktı" if v["cikis"] else "")
    d.text((248, 192), sure, font=_f(34, False), fill=SOLUK)
    tarih = m.get("date") or m["time_utc"][:10]
    d.text((248, 238), f"{tarih[8:]}.{tarih[5:7]}.{tarih[:4]}  ·  {m['league']['name']}", font=_f(30, False), fill=SOLUK)
    # gosterge
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
    # alt: hesap
    f40 = _f(40)
    tw = d.textlength("@StatDuel", font=f40)
    ik, bos = 40, 14
    x = W / 2 - (tw + 2 * (ik + bos)) / 2
    _tiktok(d, x, 1024, ik)
    _x_logo(d, x + ik + bos, 1024, ik)
    d.text((x + 2 * (ik + bos), 1022), "@StatDuel", font=f40, fill=BEYAZ)
    OUT.mkdir(exist_ok=True)
    im.save(yol)
    return yol


def main():
    a = sys.argv[1:]
    try:
        tarih, takim, oyuncu = (a[a.index(x) + 1] for x in ("--tarih", "--takim", "--oyuncu"))
    except ValueError:
        raise SystemExit(__doc__)
    v = veri(tarih, takim, oyuncu)
    ad = "".join(c for c in v["oyuncu"].lower() if c.isalnum())
    print(v["oyuncu"], v["takim"], "| aksiyon", v["aksiyon"], "| sut", len(v["sutlar"]), "| dk", v["dk"])
    print(kart(v, OUT / f"isi_{ad}.png"))


if __name__ == "__main__":
    main()

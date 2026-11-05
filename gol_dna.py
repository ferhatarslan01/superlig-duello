"""Golun DNA'si karti (GERCEK veri): PitchAPI /v1/matches/{id}/shots.

Bir golun ozellikleri: dakika, mesafe, aci, xG/xGOT, ayak, oyun durumu, kalenin neresinden girdi, kaleci.
Asist ve oyunun kurulusu (pas zinciri) ucretsiz kaynaklarda yok; kartta yer almaz.

Kullanim:
  python gol_dna.py --tarih 2026-10-26 --takim Galatasaray --dakika 29
  python gol_dna.py --tarih 2026-10-26 --takim Galatasaray            # maçin tum golleri
  ... --video                                                          # 10 sn animasyon (MP4)
Ortam: PITCHAPI_API_KEY
"""
import math
import subprocess
import sys

from PIL import Image, ImageDraw

import fotograf
from baski_video import ARKA, BEYAZ, FPS, GRI, KIRMIZI, MAVI, OUT, SOLUK, W, H, _f, _pitch, _tiktok, _x_logo

CIM = (17, 24, 33)
CIZGI = (84, 98, 124)
SARI = (255, 214, 10)
AYAK = {"RightFoot": "Sağ ayak", "LeftFoot": "Sol ayak", "Head": "Kafa", "OtherBodyPart": "Diğer"}
DURUM = {"RegularPlay": "Açık oyun", "FastBreak": "Hızlı hücum", "FromCorner": "Korner", "Corner": "Korner",
         "FreeKick": "Serbest vuruş", "Penalty": "Penaltı", "SetPiece": "Duran top", "ThrowinSetPiece": "Taç sonrası",
         "ThrowIn": "Taç sonrası", "Assisted": "Asistli", "IndividualPlay": "Bireysel", "OwnGoal": "Kendi kalesine"}


def ozellikler(s):
    """Sut kaydindan gol ozellikleri (mesafe m, aci derece, hedef bolgesi...)."""
    dx, dy = 105 - s["x"], 34 - s["y"]
    mesafe = math.hypot(dx, dy)
    aci = math.degrees(math.atan2(7.32 * dx, dx * dx + dy * dy - 3.66 ** 2))
    if aci < 0:
        aci += 180
    gy, gz = s.get("goal_crossed_y"), s.get("goal_crossed_z")
    hedef = "—"
    if gy is not None and gz is not None:
        yatay = (gy - 30.34) / 7.32
        yy = "Sol" if yatay < 1 / 3 else ("Sağ" if yatay > 2 / 3 else "Orta")
        dd = "alt" if gz < 0.81 else ("üst" if gz > 1.63 else "orta")
        hedef = f"{yy} {dd}" if (yy, dd) != ("Orta", "orta") else "Tam orta"
    return {"mesafe": mesafe, "aci": aci, "hedef": hedef,
            "ayak": AYAK.get(s.get("shot_type"), s.get("shot_type") or "—"),
            "durum": DURUM.get(s.get("situation"), s.get("situation") or "—"),
            "xg": s.get("expected_goals") or 0.0, "xgot": s.get("expected_goals_on_target"),
            "kaleci": (s.get("keeper") or {}).get("name", "—"), "ceza": bool(s.get("is_inside_box"))}


def veri(tarih, takim, dakika=None):
    gun = _pitch(f"/v1/date/{tarih}")
    m = next((x for x in (gun["matches"] if isinstance(gun, dict) else gun)
              if takim.lower() in (x["home_team"]["name"] + " " + x["away_team"]["name"]).lower()), None)
    if not m:
        raise SystemExit(f"{tarih} tarihinde '{takim}' maci bulunamadi")
    goller = [s for p in _pitch(f"/v1/matches/{m['id']}/shots")["periods"] for s in p["shots"]
              if s["event_type"] == "Goal"]
    if dakika is not None:
        goller = [s for s in goller if s["minute"] == dakika]
    # her golun tum detaylari (kaleci vb.) tekil uctan
    tam = []
    for s in goller:
        try:
            d = _pitch(f"/v1/matches/{m['id']}/shots/{s['id']}")
            tam.append({**s, **{k: v for k, v in d.items() if v is not None}})
        except Exception:
            tam.append(s)
    return m, tam


def _kare(d, x, y, w, h, etiket, deger, renk=BEYAZ, alfa=255):
    d.rounded_rectangle([x, y, x + w, y + h], 18, fill=(21, 28, 40, alfa), outline=(48, 58, 78, alfa), width=2)
    d.text((x + 16, y + 10), etiket, font=_f(24, False), fill=GRI + (alfa,))
    fs = 56
    while d.textlength(deger, font=_f(fs)) > w - 28 and fs > 28:
        fs -= 2
    d.text((x + 16, y + 40 + (56 - fs) * 0.4), deger, font=_f(fs), fill=tuple(renk) + (alfa,))


def _helis(d, x0, x1, y, ilerleme=1.0, renk_a=KIRMIZI, renk_b=MAVI, n=26):
    """Sade cift sarmal serit (DNA dekoru): iki sinus egrisi, aralarinda basamaklar."""
    genlik = 24
    pts_a, pts_b = [], []
    for i in range(0, int(240 * ilerleme) + 1):
        t = i / 240
        x = x0 + (x1 - x0) * t
        ph = t * 2 * math.pi * 5.5
        pts_a.append((x, y + genlik * math.sin(ph)))
        pts_b.append((x, y - genlik * math.sin(ph)))
    for k in range(n):
        t = (k + 0.5) / n
        if t > ilerleme:
            break
        x = x0 + (x1 - x0) * t
        ph = t * 2 * math.pi * 5.5
        d.line([(x, y + genlik * math.sin(ph)), (x, y - genlik * math.sin(ph))], fill=(88, 100, 128), width=2)
    d.line(pts_a, fill=renk_a, width=5, joint="curve")
    d.line(pts_b, fill=renk_b, width=5, joint="curve")


def _vis(t, t0, sure):
    """0..1 ilerleme; t None ise (statik kart) hep 1."""
    if t is None:
        return 1.0
    return max(0.0, min(1.0, (t - t0) / sure))


def _ease(p):
    return 1 - (1 - p) ** 3


def render(m, s, t=None):
    """Golun DNA'si karti. t=None: tam kart; t saniye: animasyonun o anindaki kare."""
    o = ozellikler(s)
    im = Image.new("RGB", (W, H), ARKA)
    ad = s["player"]["name"]
    takim = m["home_team"]["name"] if s["team_id"] == m["home_team"]["id"] else m["away_team"]["name"]
    foto, _ = fotograf.foto_al(ad, takim)
    fotograf.daire_yapistir(im, foto, 48, 44, 170, renk=KIRMIZI)
    d = ImageDraw.Draw(im, "RGBA")
    d.text((246, 40), "GOLÜN DNA'SI", font=_f(40), fill=KIRMIZI)
    d.text((246, 86), ad.upper(), font=_f(78), fill=BEYAZ)
    d.text((248, 180), f"{m['home_team']['name']} {m['score_home']}-{m['score_away']} {m['away_team']['name']}",
           font=_f(36, False), fill=GRI)
    tarih = m.get("date") or m["time_utc"][:10]
    d.text((248, 224), f"{s['minute']}'. dakika  ·  {tarih[8:]}.{tarih[5:7]}.{tarih[:4]}", font=_f(30, False), fill=SOLUK)

    # sol: saha (kaleye bakis, son 45 m)
    X0, Y0, Wp = 48, 290, 520
    sc = Wp / 68
    Hp = 45 * sc
    d.rounded_rectangle([X0 - 10, Y0 - 10, X0 + Wp + 10, Y0 + Hp + 10], 18, fill=CIM)

    def P(x, y):
        return X0 + y * sc, Y0 + (105 - x) * sc
    for pts in ([(60, 0), (105, 0), (105, 68), (60, 68), (60, 0)],
                [(88.5, 13.84), (88.5, 54.16), (105, 54.16)], [(88.5, 13.84), (105, 13.84)],
                [(99.5, 24.84), (99.5, 43.16), (105, 43.16)], [(99.5, 24.84), (105, 24.84)]):
        d.line([P(*p) for p in pts], fill=CIZGI, width=3)
    d.line([P(105, 30.34), P(105, 37.66)], fill=BEYAZ, width=6)                     # kale
    sx, sy = P(s["x"], s["y"])
    kx, ky = P(105, s.get("goal_crossed_y") or 34)
    pm = _ease(_vis(t, 0.6, 0.45))                                                   # sut noktasi belirir
    pl = _ease(_vis(t, 1.5, 0.7))                                                    # kaleye cizgi
    if pl > 0:
        d.line([(sx, sy), (sx + (kx - sx) * pl, sy + (ky - sy) * pl)], fill=(255, 255, 255, 220), width=4)
    if pm > 0:
        r = (10 + 34 * math.sqrt(o["xg"])) * (0.4 + 0.6 * pm)
        if t is not None and 0.6 <= t < 1.6:                                          # dalga halkasi
            q = (t - 0.6) / 1.0
            rr = r * (1 + 1.6 * q)
            d.ellipse([sx - rr, sy - rr, sx + rr, sy + rr], outline=(255, 255, 255, int(200 * (1 - q))), width=3)
        d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=KIRMIZI + (int(255 * pm),), outline=BEYAZ + (int(255 * pm),), width=4)
    pe = _vis(t, 1.9, 0.4)
    if pe > 0:
        d.text((X0 + 10, Y0 + Hp - 38), f"{o['mesafe']:.1f} m  ·  {o['aci']:.0f}° açı", font=_f(30),
               fill=(255, 255, 255, int(220 * pe)))

    # sag: kale yuzu
    gx0, gw = 610, 420
    gsc = gw / 7.32
    gh = 2.44 * gsc
    gy0 = 340
    ph = _vis(t, 2.3, 0.4)
    d.text((gx0, 292), f"KALEYE GİRİŞ  ·  {o['hedef'].upper()}" if ph > 0 else "KALEYE GİRİŞ", font=_f(30), fill=BEYAZ)
    d.rectangle([gx0, gy0, gx0 + gw, gy0 + gh], fill=(18, 24, 34), outline=BEYAZ, width=6)
    for i in range(1, 12):
        d.line([gx0 + gw * i / 12, gy0, gx0 + gw * i / 12, gy0 + gh], fill=(255, 255, 255, 28), width=1)
    for j in range(1, 5):
        d.line([gx0, gy0 + gh * j / 5, gx0 + gw, gy0 + gh * j / 5], fill=(255, 255, 255, 28), width=1)
    gyv, gzv = s.get("goal_crossed_y"), s.get("goal_crossed_z")
    pb = _ease(_vis(t, 2.2, 0.25))                                                   # GOL ani
    if t is not None and 2.2 <= t < 2.9:                                               # kale parlar
        a = int(120 * (1 - (t - 2.2) / 0.7))
        d.rectangle([gx0, gy0, gx0 + gw, gy0 + gh], fill=(255, 255, 255, a))
    if gyv is not None and gzv is not None and pb > 0:
        bx = gx0 + (gyv - 30.34) * gsc
        by = gy0 + gh - gzv * gsc
        rb = 20 * (0.5 + 0.5 * pb)
        if t is not None and 2.2 <= t < 3.0:
            q = (t - 2.2) / 0.8
            rr = 20 + 60 * q
            d.ellipse([bx - rr, by - rr, bx + rr, by + rr], outline=(255, 255, 255, int(220 * (1 - q))), width=3)
        d.ellipse([bx - rb, by - rb, bx + rb, by + rb], fill=KIRMIZI + (255,), outline=BEYAZ, width=4)
    d.line([gx0 - 20, gy0 + gh, gx0 + gw + 20, gy0 + gh], fill=CIZGI, width=4)
    pk = _vis(t, 2.6, 0.4)
    if pk > 0:
        d.text((gx0, gy0 + gh + 18), f"Kaleci: {o['kaleci']}", font=_f(34), fill=(160, 168, 188, int(255 * pk)))
        if o["xgot"] is not None:
            d.text((gx0, gy0 + gh + 64), f"xGOT (kaleye giden şut): {o['xgot']:.2f}", font=_f(24, False),
                   fill=(110, 118, 140, int(255 * pk)))
        d.text((gx0, gy0 + gh + 98), "xG: şut anındaki gol olasılığı", font=_f(24, False),
               fill=(110, 118, 140, int(255 * pk)))

    # sarmal serit: soldan saga cizilir
    ps = _vis(t, 2.8, 2.6)
    if ps > 0:
        _helis(d, 60, W - 60, 678, ilerleme=ps)
    # ozellik kareleri (2 x 4): sirayla belirir, sayilar sayarak yukselir
    xs = [48 + i * 256 for i in range(4)]
    kw, kh = 240, 100
    satirlar = [
        [("DAKİKA", s["minute"], "{:.0f}'", None), ("MESAFE", o["mesafe"], "{:.1f} m", None),
         ("AÇI", o["aci"], "{:.0f}°", None), ("xG", o["xg"], "{:.2f}", SARI)],
        [("AYAK", o["ayak"], None, None), ("DURUM", o["durum"], None, None), ("HEDEF", o["hedef"], None, None),
         ("BÖLGE", "Ceza sahası içi" if o["ceza"] else "Ceza sahası dışı", None, None)],
    ]
    n = 0
    for ri, satir in enumerate(satirlar):
        for ci, (e, dg, bicim, renk) in enumerate(satir):
            pr = _ease(_vis(t, 3.1 + n * 0.42, 0.45))
            n += 1
            if pr <= 0:
                continue
            yy = 730 + ri * 114 + int((1 - pr) * 24)
            metin = bicim.format(dg * pr) if bicim else dg
            _kare(d, xs[ci], yy, kw, kh, e, metin, renk or BEYAZ, alfa=int(255 * pr))
    # alt
    f40 = _f(40)
    tw = d.textlength("@StatDuel", font=f40)
    ik, bos = 40, 14
    x = W / 2 - (tw + 2 * (ik + bos)) / 2
    _tiktok(d, x, 1024, ik)
    _x_logo(d, x + ik + bos, 1024, ik)
    d.text((x + 2 * (ik + bos), 1022), "@StatDuel", font=f40, fill=BEYAZ)
    return im


def kart(m, s, yol):
    OUT.mkdir(exist_ok=True)
    render(m, s).save(yol)
    return yol


def video(m, s, sure=10.0):
    """10 sn'lik animasyon; gol sesi t=2.2 sn'de. (mp4 yolu, [gol_zamani_sn]) doner."""
    ad = "".join(c for c in s["player"]["name"].lower() if c.isalnum())
    yol = OUT / f"dna_{ad}_{s['minute']}.mp4"
    OUT.mkdir(exist_ok=True)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                           "-preset", "medium", str(yol)], stdin=subprocess.PIPE)
    for n in range(int(sure * FPS)):
        ff.stdin.write(render(m, s, n / FPS).tobytes())
    ff.stdin.close()
    ff.wait()
    return yol, [2.2]


def main():
    a = sys.argv[1:]
    try:
        tarih, takim = (a[a.index(x) + 1] for x in ("--tarih", "--takim"))
    except ValueError:
        raise SystemExit(__doc__)
    dk = int(a[a.index("--dakika") + 1]) if "--dakika" in a else None
    m, goller = veri(tarih, takim, dk)
    if not goller:
        raise SystemExit("gol bulunamadi")
    for s in goller:
        ad = "".join(c for c in s["player"]["name"].lower() if c.isalnum())
        o = ozellikler(s)
        print(s["player"]["name"], s["minute"], "|", {k: (round(v, 2) if isinstance(v, float) else v) for k, v in o.items()})
        if "--video" in a:
            print(video(m, s)[0])
        else:
            print(kart(m, s, OUT / f"dna_{ad}_{s['minute']}.png"))


if __name__ == "__main__":
    main()

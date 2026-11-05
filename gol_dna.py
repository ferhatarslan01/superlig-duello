"""Golun DNA'si karti (GERCEK veri): PitchAPI /v1/matches/{id}/shots.

Bir golun ozellikleri: dakika, mesafe, aci, xG/xGOT, ayak, oyun durumu, kalenin neresinden girdi, kaleci.
Asist ve oyunun kurulusu (pas zinciri) ucretsiz kaynaklarda yok; kartta yer almaz.

Kullanim:
  python gol_dna.py --tarih 2026-10-26 --takim Galatasaray --dakika 29
  python gol_dna.py --tarih 2026-10-26 --takim Galatasaray            # maçin tum golleri
Ortam: PITCHAPI_API_KEY
"""
import math
import sys

from PIL import Image, ImageDraw

import fotograf
from baski_video import ARKA, BEYAZ, GRI, KIRMIZI, MAVI, OUT, SOLUK, W, H, _f, _pitch, _tiktok, _x_logo

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


def _kare(d, x, y, w, h, etiket, deger, renk=BEYAZ):
    d.rounded_rectangle([x, y, x + w, y + h], 18, fill=(21, 28, 40), outline=(48, 58, 78), width=2)
    d.text((x + 16, y + 10), etiket, font=_f(24, False), fill=GRI)
    fs = 56
    while d.textlength(deger, font=_f(fs)) > w - 28 and fs > 28:
        fs -= 2
    d.text((x + 16, y + 40 + (56 - fs) * 0.4), deger, font=_f(fs), fill=renk)


def _helis(d, x0, x1, y, genislik=1, renk_a=KIRMIZI, renk_b=MAVI, n=26):
    """Sade cift sarmal serit (DNA dekoru): iki sinus egrisi, aralarinda basamaklar."""
    genlik = 24
    pts_a, pts_b = [], []
    for i in range(0, 241):
        t = i / 240
        x = x0 + (x1 - x0) * t
        ph = t * 2 * math.pi * 5.5
        pts_a.append((x, y + genlik * math.sin(ph)))
        pts_b.append((x, y - genlik * math.sin(ph)))
    for k in range(n):
        t = (k + 0.5) / n
        x = x0 + (x1 - x0) * t
        ph = t * 2 * math.pi * 5.5
        d.line([(x, y + genlik * math.sin(ph)), (x, y - genlik * math.sin(ph))], fill=(88, 100, 128), width=2)
    d.line(pts_a, fill=renk_a, width=5, joint="curve")
    d.line(pts_b, fill=renk_b, width=5, joint="curve")


def kart(m, s, yol):
    o = ozellikler(s)
    im = Image.new("RGB", (W, H), ARKA)
    d = ImageDraw.Draw(im, "RGBA")
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
    d.line([(sx, sy), (kx, ky)], fill=(255, 255, 255, 220), width=4)
    r = 10 + 34 * math.sqrt(o["xg"])
    d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=KIRMIZI + (255,), outline=BEYAZ, width=4)
    d.text((X0 + 10, Y0 + Hp - 38), f"{o['mesafe']:.1f} m  ·  {o['aci']:.0f}° açı", font=_f(30), fill=(255, 255, 255, 220))

    # sag: kale yuzu
    gx0, gw = 610, 420
    gsc = gw / 7.32
    gh = 2.44 * gsc
    gy0 = 300 + 40
    d.text((gx0, 292), f"KALEYE GİRİŞ  ·  {o['hedef'].upper()}", font=_f(30), fill=BEYAZ)
    d.rectangle([gx0, gy0, gx0 + gw, gy0 + gh], fill=(18, 24, 34), outline=BEYAZ, width=6)
    for i in range(1, 12):
        d.line([gx0 + gw * i / 12, gy0, gx0 + gw * i / 12, gy0 + gh], fill=(255, 255, 255, 28), width=1)
    for j in range(1, 5):
        d.line([gx0, gy0 + gh * j / 5, gx0 + gw, gy0 + gh * j / 5], fill=(255, 255, 255, 28), width=1)
    gyv, gzv = s.get("goal_crossed_y"), s.get("goal_crossed_z")
    if gyv is not None and gzv is not None:
        bx = gx0 + (gyv - 30.34) * gsc
        by = gy0 + gh - gzv * gsc
        d.ellipse([bx - 20, by - 20, bx + 20, by + 20], fill=KIRMIZI + (255,), outline=BEYAZ, width=4)
    d.line([gx0 - 20, gy0 + gh, gx0 + gw + 20, gy0 + gh], fill=CIZGI, width=4)
    d.text((gx0, gy0 + gh + 18), f"Kaleci: {o['kaleci']}", font=_f(34), fill=GRI)
    if o["xgot"] is not None:
        d.text((gx0, gy0 + gh + 64), f"xGOT (kaleye giden şut): {o['xgot']:.2f}", font=_f(24, False), fill=SOLUK)
    d.text((gx0, gy0 + gh + 98), "xG: şut anındaki gol olasılığı", font=_f(24, False), fill=SOLUK)

    # sarmal serit
    _helis(d, 60, W - 60, 678)
    # ozellik kareleri (2 x 4)
    xs = [48 + i * 256 for i in range(4)]
    kw, kh = 240, 100
    satir1 = [("DAKİKA", f"{s['minute']}'"), ("MESAFE", f"{o['mesafe']:.1f} m"), ("AÇI", f"{o['aci']:.0f}°"),
              ("xG", f"{o['xg']:.2f}")]
    satir2 = [("AYAK", o["ayak"]), ("DURUM", o["durum"]), ("HEDEF", o["hedef"]),
              ("BÖLGE", "Ceza sahası içi" if o["ceza"] else "Ceza sahası dışı")]
    for i, (e, dg) in enumerate(satir1):
        _kare(d, xs[i], 730, kw, kh, e, dg, SARI if e == "xG" else BEYAZ)
    for i, (e, dg) in enumerate(satir2):
        _kare(d, xs[i], 844, kw, kh, e, dg)
    # alt
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
        print(kart(m, s, OUT / f"dna_{ad}_{s['minute']}.png"))


if __name__ == "__main__":
    main()

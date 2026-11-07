"""Mac oncesi: iki takimin birbirleriyle son 5 karsilasmasi (video). Mac gunu 1-2 gun oncesinde paylasilir.

Veri (PitchAPI, ucretsiz):
  /v1/leagues/{id}/matches?status=all   sezonun tum maclari: fikstur + sonuclar + takim kimlikleri
  /v1/matches/{id}/h2h                  iki takimin gecmis karsilasmalari (onceki sezonlar)
Bu sezonun sonuclari H2H listesinde gec gorunebildigi icin sezon verisiyle birlestirilir.
Takim logolari ESPN (500 px); yoksa PitchAPI logosu.

Gorsel dil duello_video ile ayni (4:5, takim renkleri, vurusa kilitli satirlar, TAKIP ET kapanisi).

Kullanim:
  python h2h_video.py                          # onumuzdeki 12-48 saatteki buyuk 4 maclari (liste)
  python h2h_video.py Galatasaray Fenerbahce   # o iki takimin ilk fikstur macini bulup video uretir
"""
import io
import math
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import duello
import duello_video as dv
import fotograf
import gelismis
import kart_v2
from baski_video import OUT, _pitch
from duello_video import (ARKA, B, BEYAZ, CARD_H, CARD_W, CARD_X, CARD_Y, CTA_B, ETIKET, F, FULL_B, H, HOOK_B,
                          SATIR_B, SOLUK, SONUC_B, W, _buyuk, _ease, _pop, _vis, harf_arali, isima, koy, renk_ayir,
                          sigan, takim_ikili, takim_rengi, yaz)

KLASOR = Path(__file__).parent
LIG_ID = "l_0S1uaf"                                   # PitchAPI: Super Lig
LOGO_ONBELLEK = KLASOR / "data" / "foto_cache"
GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
BUYUK4 = {"galatasaray", "fenerbahce", "besiktas", "trabzonspor"}


# ---------------- veri ----------------
def sezon_maclari():
    """Super Lig'in bu sezonki tum maclari (fikstur + sonuc)."""
    return _pitch(f"/v1/leagues/{LIG_ID}/matches?status=all")["matches"]


def buyuk_mu(m):
    return any(fotograf.norm(m[k]["name"]) in BUYUK4 for k in ("home_team", "away_team"))


def yaklasan(sadece_buyuk=True, min_saat=12, max_saat=48, maclar=None):
    """Baslamasina min_saat..max_saat kalan fikstur maclari (baslangic saatine gore)."""
    simdi = datetime.now(timezone.utc)
    sonuc = []
    for m in (maclar or sezon_maclari()):
        if m.get("status") != "not_started":
            continue
        kalan = (datetime.fromisoformat(m["time_utc"].replace("Z", "+00:00")) - simdi).total_seconds() / 3600
        if min_saat < kalan <= max_saat and (buyuk_mu(m) or not sadece_buyuk):
            sonuc.append(m)
    return sorted(sonuc, key=lambda m: m["time_utc"])


SEZONLAR = ("2025/2026", "2024/2025", "2023/2024", "2022/2023")


@lru_cache(maxsize=1)
def gecmis_maclar():
    """Onceki sezonlarin oynanmis Super Lig maclari (lig listesinden)."""
    out = []
    for sez in SEZONLAR:
        try:
            out += [x for x in _pitch(f"/v1/leagues/{LIG_ID}/matches?season={sez}")["matches"]
                    if x.get("status") == "finished"]
        except Exception as e:
            print(f"{sez} sezonu alinamadi ({e})")
    return out


def veri(m, maclar=None):
    """Mac icin son 5 karsilasma + ozet. m: sezon_maclari() ogesi (fikstur)."""
    a, b = m["home_team"], m["away_team"]
    ids = {a["id"], b["id"]}
    kayit = {}
    # Bu sezon + onceki 4 sezonun lig sonuclari (H2H uc noktasi oynanmamis fikstur icin bos doner)
    cift = sorted((x for x in list(maclar or sezon_maclari()) + gecmis_maclar()
                   if x.get("status") == "finished" and x.get("score_home") is not None
                   and {x["home_team"]["id"], x["away_team"]["id"]} == ids), key=lambda x: x["time_utc"], reverse=True)
    # Kupa vb. maclar icin H2H gecmisi: oynanmis en yeni macin kimligiyle sorgulanir
    sorgu_id = cift[0]["id"] if cift else m["id"]
    try:
        h = _pitch(f"/v1/matches/{sorgu_id}/h2h")
        for x in h.get("recent_matches", []):
            if x.get("finished") and x.get("score_home") is not None and {x["home"]["id"], x["away"]["id"]} == ids:
                kayit[x["time_utc"][:10]] = {"tarih": x["time_utc"][:10], "ev": x["home"], "dep": x["away"],
                                             "sh": x["score_home"], "sa": x["score_away"]}
    except Exception as e:
        print(f"h2h alinamadi ({e}); yalnizca sezon sonuclari kullanilacak")
    for x in cift:                                   # lig sonuclari H2H listesinin ustune yazilir (daha guncel/eksiksiz)
        kayit[x["date"]] = {"tarih": x["date"], "ev": x["home_team"], "dep": x["away_team"],
                            "sh": x["score_home"], "sa": x["score_away"]}
    son = sorted(kayit.values(), key=lambda r: r["tarih"], reverse=True)[:5]
    for r in son:
        if r["sh"] == r["sa"]:
            r["kazanan"] = None
        else:
            r["kazanan"] = r["ev"]["id"] if r["sh"] > r["sa"] else r["dep"]["id"]
    wa = sum(1 for r in son if r["kazanan"] == a["id"])
    wb = sum(1 for r in son if r["kazanan"] == b["id"])
    ga = sum((r["sh"] if r["ev"]["id"] == a["id"] else r["sa"]) for r in son)
    gb = sum((r["sh"] if r["ev"]["id"] == b["id"] else r["sa"]) for r in son)
    return {"mac": m, "a": a, "b": b, "eslesmeler": son, "wa": wa, "wb": wb, "d": len(son) - wa - wb, "ga": ga, "gb": gb}


def zaman_metni(m):
    """'Cumartesi 19:00' (TRT = UTC+3)."""
    t = datetime.fromisoformat(m["time_utc"].replace("Z", "+00:00")) + timedelta(hours=3)
    return f"{GUNLER[t.weekday()]} {t:%H:%M}"


# ---------------- logo ----------------
@lru_cache(maxsize=1)
def _espn_takimlar():
    tk = duello.get(f"{duello.API}/teams")["sports"][0]["leagues"][0]["teams"]
    return [(t["team"]["id"], t["team"]["displayName"]) for t in tk]


def logo(takim):
    """Takim logosu (RGBA). ESPN 500 px; olmazsa PitchAPI logosu; olmazsa None."""
    LOGO_ONBELLEK.mkdir(parents=True, exist_ok=True)
    adaylar = []
    try:
        for tid, ad in _espn_takimlar():
            if gelismis._takim_ayni(ad, takim["name"]):
                adaylar.append((LOGO_ONBELLEK / f"takim_{tid}.png", f"https://a.espncdn.com/i/teamlogos/soccer/500/{tid}.png"))
                break
    except Exception:
        pass
    if takim.get("image_url"):
        adaylar.append((LOGO_ONBELLEK / f"takim_pa_{takim['id']}.png", takim["image_url"]))
    for yol, url in adaylar:
        try:
            if not yol.exists():
                req = urllib.request.Request(url, headers={"User-Agent": "statduel-bot/0.1"})
                Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=30).read())).convert("RGBA").save(yol)
            return Image.open(yol).convert("RGBA")
        except Exception:
            continue
    return None


# ---------------- video ----------------
AYLAR = ["", "Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


def tarih_metni(iso):
    y, a, g = iso.split("-")
    return f"{int(g)} {AYLAR[int(a)]} {y}"


class H2HVideo(dv.Video):
    """duello_video.Video'nun zemini, isigi, kapanis karti ve sesiyle; icerik: son 5 karsilasma."""

    def __init__(self, h, ust=""):
        self.h = h
        self.m = h["mac"]
        self.sat = h["eslesmeler"]
        self.n = len(self.sat)
        a, b = h["a"], h["b"]
        self.ka = self.kb = None
        self.ca, self.cb = renk_ayir(takim_rengi(a["name"]), takim_rengi(b["name"]))
        self.renk = (self.ca, self.cb)
        self.renk2 = (takim_ikili(a["name"])[1], takim_ikili(b["name"])[1])
        self.ust = ust
        self.puan = (h["wa"], h["wb"])
        self.kazanan = None if h["wa"] == h["wb"] else (0 if h["wa"] > h["wb"] else 1)
        self.cta_soru = "Bu maçı kim alır?"
        self.cta_alt = "Tahminini yaz"
        self.r0 = HOOK_B
        self.landing = [(self.r0 + SATIR_B * i + 1) * B for i in range(self.n)]
        self.R = (self.r0 + SATIR_B * (self.n - 1) + 1 + FULL_B) * B
        self.C = self.R + SONUC_B * B
        self.bitis = self.C + CTA_B * B
        self.sure = self.bitis + 0.5
        self._hazirla_h2h()

    def _hazirla_h2h(self):
        a, b = self.h["a"], self.h["b"]
        self.kartlar = [self._takim_karti(a, self.ca, self.renk2[0], "EV SAHİBİ"),
                        self._takim_karti(b, self.cb, self.renk2[1], "DEPLASMAN")]
        self.kart_soluk = [self._soluk(k) for k in self.kartlar]
        self.vig = self._vinyet()
        self.vs = self._vs()
        self.st_hook = self._damga("SON 5 MAÇ", 200)
        self.sub_hook = "KARŞILIKLI SON 5 KARŞILAŞMA"
        if self.kazanan is None:
            self.ad_sonuc, self.renk_sonuc = "DENGEDE", BEYAZ
        else:
            self.ad_sonuc = _buyuk(kart_v2.takim_adi((a, b)[self.kazanan]["name"]))
            self.renk_sonuc = self.renk[self.kazanan]
        self.st_sonuc = self._damga(self.ad_sonuc, 150, self.renk_sonuc, max_w=900)
        self.sonuc_panel = self._sonuc_panel()
        self.marka_kucuk = dv.marka(62)
        self.marka_buyuk = dv.marka(330)

    def _takim_karti(self, takim, renk, renk2, etiket):
        S = 2
        w, h = CARD_W * S, CARD_H * S
        im = Image.new("RGBA", (w, h), (16, 20, 34, 255))
        yy, xx = np.mgrid[0:h, 0:w]                       # ustten takim rengi isik
        k = np.exp(-(((xx / w - 0.5) / 0.55) ** 2 + ((yy / h - 0.28) / 0.45) ** 2)) * 0.42
        rgb = np.clip(np.array((16, 20, 34), float) + k[..., None] * np.array(renk, float), 0, 255).astype("uint8")
        im = Image.fromarray(rgb, "RGB").convert("RGBA")
        lg = logo(takim)
        d = ImageDraw.Draw(im)
        if lg is not None:
            ls = int(270 * S)
            lg = lg.resize((ls, int(ls * lg.height / lg.width)), Image.LANCZOS)
            im.alpha_composite(lg, (int((w - lg.width) / 2), int(0.40 * h - lg.height / 2)))
        else:
            d.ellipse([w * 0.3, h * 0.18, w * 0.7, h * 0.58], fill=tuple(renk) + (255,))
            d.text((w / 2, h * 0.38), takim["name"][:1].upper(), font=F(150 * S), fill=BEYAZ + (255,), anchor="mm")
        rampa = np.zeros((h, w), dtype="uint8")
        k0 = int(h * 0.62)
        for y in range(k0, h):
            rampa[y, :] = int(150 * ((y - k0) / (h - k0)) ** 1.3)
        kap = Image.new("RGBA", (w, h), ARKA + (0,))
        kap.putalpha(Image.fromarray(rampa))
        im.alpha_composite(kap)
        d = ImageDraw.Draw(im)
        ad = _buyuk(kart_v2.takim_adi(takim["name"]))
        f = sigan(ad, CARD_W - 44, 62, True, 34)
        d.text((22 * S, (CARD_H - 132) * S), ad, font=F(f.size / 1.12 * S), fill=BEYAZ)
        d.text((22 * S, (CARD_H - 56) * S), etiket, font=F(24 * S, False), fill=ETIKET)
        d.rectangle([0, h - 8 * S, w // 2, h], fill=tuple(renk) + (255,))
        d.rectangle([w // 2, h - 8 * S, w, h], fill=tuple(renk2) + (255,))
        maske = Image.new("L", (w, h), 0)
        ImageDraw.Draw(maske).rounded_rectangle([0, 0, w - 1, h - 1], 34 * S, fill=255)
        halka = Image.new("L", (w, h), 0)
        ImageDraw.Draw(halka).rounded_rectangle([0, 0, w - 1, h - 1], 34 * S, outline=255, width=7 * S)
        u = (xx / w + yy / h) / 2
        kk = np.clip((u - 0.46) / 0.08, 0, 1)[..., None]
        ra = (np.array(renk, float) * (1 - kk) + np.array(renk2, float) * kk).astype("uint8")
        cer = Image.fromarray(ra, "RGB").convert("RGBA")
        cer.putalpha(halka)
        im.alpha_composite(cer)
        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        out.paste(im, (0, 0), maske)
        return out.resize((CARD_W, CARD_H), Image.LANCZOS)

    # ---- ana sahne ----
    def _ana(self, im, t, ana):
        self._ust_serit(im, ana)
        gir = _ease(_vis(t, 0.0, 0.32))
        sonuc_p = _ease(_vis(t, self.R, 0.4))
        for i in (0, 1):
            cx, cy = CARD_X[i] + CARD_W / 2, CARD_Y + CARD_H / 2
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
                koy(im, self.kartlar[i], cx + kayma, cy, a, olcek * (1 + 0.045 * sonuc_p if kazandi else 1), merkez=True)
        vs_p = _ease(_vis(t, 0.05, 0.3))
        koy(im, self.vs, W / 2, CARD_Y + CARD_H / 2 - 20, vs_p * ana, 0.6 + 0.4 * vs_p, merkez=True)
        ch = _ease(_vis(t, 2 * B, 0.35))
        self._ozet_hapi(im, t, ana * ch)
        if t < HOOK_B * B + 0.01:                        # hook damgasi
            p_in = _ease(_vis(t, 0.0, 0.26))
            cikis = _ease(_vis(t, (HOOK_B - 0.8) * B, 0.7 * B))
            a = (0.72 + 0.28 * p_in) * (1 - cikis)
            koy(im, self.st_hook, W / 2, 900 - 36 * cikis, a * ana, 1.30 - 0.30 * p_in, merkez=True)
            sd = ImageDraw.Draw(im, "RGBA")
            yaz(sd, (W / 2, 1040 - 36 * cikis), self.sub_hook, F(44, False), ETIKET + (int(255 * a * ana),), anchor="mm")
        self._satirlar_h2h(im, t, ana)
        if t >= self.R:
            self._sonuc_h2h(im, t, ana)
        self._hesap(im, ana)

    def _sayilar_t(self, t):
        wa = wb = d = 0
        son_t, taraf = -9, None
        a_id = self.h["a"]["id"]
        for i, r in enumerate(self.sat):
            if t >= self.landing[i]:
                if r["kazanan"] is None:
                    d += 1
                    taraf = 2
                elif r["kazanan"] == a_id:
                    wa += 1
                    taraf = 0
                else:
                    wb += 1
                    taraf = 1
                son_t = self.landing[i]
        return wa, d, wb, son_t, taraf

    def _ozet_hapi(self, im, t, ana):
        """Ortada: A galibiyeti - beraberlik - B galibiyeti (satir yerlestikce guncellenir)."""
        wa, d, wb, son_t, taraf = self._sayilar_t(t)
        p = _vis(t, son_t, 0.28)
        sc = _pop(p, 0.12)
        w, h, pad = 330, 132, 40
        k = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
        dd = ImageDraw.Draw(k)
        parla = (self.renk[taraf] if taraf in (0, 1) else (200, 205, 220)) if (taraf is not None and p < 1) else (255, 255, 255)
        kenar = 90 + int(150 * (1 - p)) if taraf is not None else 70
        dd.rounded_rectangle([pad, pad, pad + w, pad + h], 40, fill=(14, 17, 30, 236), outline=tuple(parla) + (kenar,), width=3)
        for j, (v, renk, ad) in enumerate(((wa, self.ca, "GALİBİYET"), (d, (170, 176, 196), "BERABERE"), (wb, self.cb, "GALİBİYET"))):
            cx = pad + w / 2 + (j - 1) * 105
            dd.text((cx, pad + 52), str(v), font=F(76), fill=tuple(renk) + (255,), anchor="mm")
            dd.text((cx, pad + 100), ad, font=F(19, False), fill=SOLUK + (255,), anchor="mm")
        koy(im, k, W / 2, CARD_Y + CARD_H + 60, ana, sc, merkez=True)

    def _satirlar_h2h(self, im, t, ana):
        n = self.n
        y0, y1 = 722, 1238
        h = min(104, (y1 - y0) // max(n, 1))
        ys = y0 + ((y1 - y0) - n * h) / 2
        sonuc_dim = 1 - 0.82 * _ease(_vis(t, self.R, 0.35))
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov, "RGBA")
        a_id = self.h["a"]["id"]
        for i, r in enumerate(self.sat):
            s = (self.r0 + SATIR_B * i) * B
            p_gir = _ease(_vis(t, s, 0.26))
            if p_gir <= 0:
                continue
            p_land = _vis(t, self.landing[i], 0.3)
            y = ys + i * h + (1 - p_gir) * 14
            al = p_gir * ana * sonuc_dim
            d.rounded_rectangle([40, y, W - 40, y + h - 12], 20, fill=(255, 255, 255, int(11 * p_gir)),
                                outline=(255, 255, 255, int(20 * al)), width=2)
            cy = y + (h - 12) / 2
            # solda kazanan serit
            if r["kazanan"] is None:
                sr = (150, 156, 176)
            else:
                sr = self.ca if r["kazanan"] == a_id else self.cb
            d.rounded_rectangle([40, y + 8, 50, y + h - 20], 5, fill=tuple(sr) + (int(255 * al * (0.35 + 0.65 * p_land)),))
            yaz(d, (72, cy), tarih_metni(r["tarih"]), F(32), BEYAZ + (int(255 * al),), anchor="lm")
            for taraf, takim, x, hiza in ((0, r["ev"], 528, "rm"), (1, r["dep"], 752, "lm")):
                kazandi = r["kazanan"] == takim["id"]
                kaybetti = r["kazanan"] is not None and not kazandi
                ad = kart_v2.takim_adi(takim["name"])
                f = sigan(ad, 236, 40, True, 24)
                renk = (BEYAZ if not kaybetti else (150, 158, 180)) + (int(255 * al * (1.0 if p_land > 0 or True else 1.0)),)
                if kazandi and p_land > 0:
                    tk_renk = self.ca if takim["id"] == a_id else self.cb
                    renk = tuple(tk_renk) + (int(255 * al),)
                yaz(d, (x, cy), ad, f, renk, anchor=hiza)
            # skor: yerlestiginde belirir
            if p_land > 0:
                sc = _pop(p_land, 0.2)
                sk = f"{r['sh']} - {r['sa']}"
                tw = d.textlength(sk, font=F(70))
                pw = tw + 40
                d.rounded_rectangle([640 - pw * sc / 2, cy - 36 * sc, 640 + pw * sc / 2, cy + 36 * sc], 18 * sc,
                                    fill=(255, 255, 255, int(24 * al)), outline=(255, 255, 255, int(60 * al)), width=2)
                yaz(d, (640, cy - 2), sk, F(70), BEYAZ + (int(255 * al * p_land),), anchor="mm")
            else:
                yaz(d, (640, cy - 2), "- -", F(60), (110, 118, 140, int(200 * al)), anchor="mm")
        im.alpha_composite(ov)

    def _sonuc_h2h(self, im, t, ana):
        h = self.h
        p = _ease(_vis(t, self.R + 0.05, 0.4))
        if p > 0:
            koy(im, self.sonuc_panel, W / 2, 954 + (1 - p) * 30, p * ana, merkez=True)
            ov = ImageDraw.Draw(im, "RGBA")
            harf_arali(ov, W / 2, 790 + (1 - p) * 30, "SON 5 KARŞILAŞMADA", F(38), SOLUK + (int(255 * p * ana),), 8)
            koy(im, self.st_sonuc, W / 2, 920 + (1 - p) * 40, p * ana, merkez=True)
            if self.kazanan is None:
                s1 = f"{h['wa']} - {h['d']} - {h['wb']}  (G - B - G)"
            else:
                w1, w2 = (h["wa"], h["wb"]) if self.kazanan == 0 else (h["wb"], h["wa"])
                s1 = f"{w1} GALİBİYET  ·  {h['d']} BERABERE  ·  {w2} MAĞLUBİYET"
            g1, g2 = (h["ga"], h["gb"]) if self.kazanan in (0, None) else (h["gb"], h["ga"])
            yaz(ov, (W / 2, 1060 + (1 - p) * 30), s1, F(44), BEYAZ + (int(255 * p * ana),), anchor="mm")
            yaz(ov, (W / 2, 1126 + (1 - p) * 30), f"Atılan gol: {g1} - {g2}", F(40, False), ETIKET + (int(255 * p * ana),), anchor="mm")
        if self.kazanan is not None and t < self.R + 2.2:
            self._kivilcim(im, t - self.R, ana)


# ---------------- cikti ----------------
def render(h, yol):
    from baski_video import OUT as _o
    v = H2HVideo(h, f"MAÇ ÖNCESİ  ·  {zaman_metni(h['mac'])}")
    import subprocess
    _o.mkdir(exist_ok=True)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(dv.FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "21",
                           "-preset", "medium", "-movflags", "+faststart", str(yol)], stdin=subprocess.PIPE)
    for n in range(int(v.sure * dv.FPS)):
        ff.stdin.write(v.kare(n / dv.FPS).tobytes())
    ff.stdin.close()
    ff.wait()
    return Path(yol), v


def uret(h):
    """h = veri(m); muzikli video yolunu doner."""
    yol, v = render(h, OUT / f"h2h_{h['mac']['id']}.mp4")
    return dv.muzik_ekle(yol, v)


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    maclar = sezon_maclari()
    if not a:
        for m in yaklasan(sadece_buyuk=True, min_saat=0, max_saat=96, maclar=maclar):
            print(m["id"], m["home_team"]["name"], "-", m["away_team"]["name"], zaman_metni(m))
        return
    t1, t2 = (fotograf.norm(x) for x in a[:2])
    m = next((x for x in sorted(maclar, key=lambda x: x["time_utc"]) if x.get("status") == "not_started"
              and t1 in fotograf.norm(x["home_team"]["name"] + " " + x["away_team"]["name"])
              and t2 in fotograf.norm(x["home_team"]["name"] + " " + x["away_team"]["name"])), None)
    if not m:
        raise SystemExit("o iki takimin yaklasan fiksturu bulunamadi")
    h = veri(m, maclar)
    print(m["home_team"]["name"], "-", m["away_team"]["name"], zaman_metni(m), "| son", len(h["eslesmeler"]), "karsilasma")
    for r in h["eslesmeler"]:
        print("  ", r["tarih"], r["ev"]["name"], r["sh"], "-", r["sa"], r["dep"]["name"])
    print(uret(h))


if __name__ == "__main__":
    main()

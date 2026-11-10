"""Ozgun 'rekabet' muzigi uretici (telifsiz; tamamen kodla sentezlenir) ve videoya ekleme.

Gergin, bas agirlikli 140 BPM elektronik ritim: kick, sub bas, klap, hi-hat, a-minor arpej, gol aninda
yukselen gerilim (riser) + dusuk darbe (impact) + kisa ses cekilmesi (sidechain).

Kullanim:
  python muzik.py out/baski_334a7356.mp4 --goller 29,44,62 --dk-sn 2.2      # <video>_muzikli.mp4
(--goller: mac dakikalari; --dk-sn: videoda saniye basina mac dakikasi; --stil rekabet|celestial|harici --dosya <wav> --lufs -22 --gol-ses <mp3/wav> --gol-ses-sn 2.5)
"""
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

SR = 44100
BPM = 140
BEAT = 60.0 / BPM


def _bos(sure):
    return np.zeros(int(SR * sure) + SR)


def _ekle(tampon, ses, t0, kazanc=1.0):
    i = int(t0 * SR)
    if i < 0 or i >= len(tampon):
        return
    n = min(len(ses), len(tampon) - i)
    tampon[i:i + n] += ses[:n] * kazanc


def _alcak_geciren(x, fc):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / (1 + (f / fc) ** 4)
    return np.fft.irfft(X, len(x))


def _yuksek_geciren(x, fc):
    return x - _alcak_geciren(x, fc)


def kick():
    t = np.arange(int(0.28 * SR)) / SR
    f = 45 + 95 * np.exp(-t * 28)
    faz = 2 * np.pi * np.cumsum(f) / SR
    ses = np.sin(faz) * np.exp(-t * 11)
    ses[:int(0.004 * SR)] += np.random.default_rng(1).normal(0, 0.6, int(0.004 * SR))   # tik
    return ses


def klap(rng):
    t = np.arange(int(0.22 * SR)) / SR
    g = _yuksek_geciren(rng.normal(0, 1, len(t)), 1200)
    return g * np.exp(-t * 20) * 0.7


def hat(rng, acik=False):
    t = np.arange(int((0.18 if acik else 0.05) * SR)) / SR
    g = _yuksek_geciren(rng.normal(0, 1, len(t)), 6500)
    return g * np.exp(-t * (14 if acik else 70)) * 0.35


def bas(f0, uzun=0.20):
    t = np.arange(int(uzun * SR)) / SR
    ses = sum(np.sin(2 * np.pi * f0 * k * t) / k for k in (1, 2, 3, 4))
    ses = _alcak_geciren(ses, 420)
    return ses * np.exp(-t * 7) * 0.9


def arpej_notasi(f, rng):
    t = np.arange(int(0.20 * SR)) / SR
    ses = (2 * ((f * t) % 1) - 1) * 0.5 + 0.5 * np.sin(2 * np.pi * f * 2 * t)      # testere + oktav
    ses = _alcak_geciren(ses, 2600)
    return ses * np.exp(-t * 10) * 0.30


def riser(sure, rng):
    n = int(sure * SR)
    t = np.arange(n) / SR
    gurultu = _yuksek_geciren(rng.normal(0, 1, n), 800)
    f = 200 * (14 ** (t / sure))
    ton = np.sin(2 * np.pi * np.cumsum(f) / SR)
    zarf = (t / sure) ** 2.2
    return (gurultu * 0.5 + ton * 0.5) * zarf * 0.55


def tik(rng):
    """Satir yerlestiginde keskin 'snap': 1.5/2.2/3.3 kHz kisa sinuslar + kisa gurultu (orta-ust bantta net)."""
    t = np.arange(int(0.10 * SR)) / SR
    ses = sum(np.sin(2 * np.pi * f * t) * np.exp(-t / d) * g
              for f, d, g in ((1500, 0.022, 1.0), (2200, 0.016, 0.9), (3300, 0.011, 0.7)))
    ses += _yuksek_geciren(rng.normal(0, 1, len(t)), 2500) * np.exp(-t / 0.004) * 0.9
    ses[:int(0.0008 * SR)] *= np.linspace(0, 1, int(0.0008 * SR))
    return ses / max(np.abs(ses).max(), 1e-9)


def whoosh(rng):
    """Kamera hareketi icin 'whoosh': bant filtreli gurultu + yukselen sinus, tepe ~0.3 sn."""
    sure = 0.7
    n = int(sure * SR)
    t = np.arange(n) / SR
    gur = _yuksek_geciren(_alcak_geciren(rng.normal(0, 1, n), 5200), 700)
    zarf = np.sin(np.pi * np.clip(t / sure, 0, 1)) ** 2.2
    f = 280 + 1700 * (t / sure) ** 1.6
    ton = np.sin(2 * np.pi * np.cumsum(f) / SR)
    ses = (gur * 0.9 + ton * 0.22) * zarf
    return ses / max(np.abs(ses).max(), 1e-9) * 0.7


def parilti(rng):
    """Parilti: yukselen kucuk can notalari (sonuc aninda darbenin ustune)."""
    sure = 1.8
    t = np.arange(int(sure * SR)) / SR
    ses = np.zeros(len(t))
    for k, f in enumerate((1318.5, 1760.0, 2093.0, 2637.0, 3136.0, 3520.0)):
        t0 = 0.05 * k
        m = t >= t0
        ses[m] += np.sin(2 * np.pi * f * (t[m] - t0)) * np.exp(-(t[m] - t0) / 0.28) * (0.9 - 0.08 * k)
    return ses / max(np.abs(ses).max(), 1e-9) * 0.5


def darbe(rng):
    t = np.arange(int(1.6 * SR)) / SR
    f = 28 + 90 * np.exp(-t * 9)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.4)
    gurultu = _yuksek_geciren(rng.normal(0, 1, len(t)), 1500) * np.exp(-t * 3.2) * 0.35
    return boom * 1.15 + gurultu


def uret(sure, goller_sn, yol_wav):
    """sure: saniye; goller_sn: gol anlarinin video saniyeleri."""
    rng = np.random.default_rng(7)
    mix = _bos(sure)
    kicker = kick()
    adim16 = BEAT / 4
    toplam16 = int(sure / adim16) + 2
    # a-minor: bas notalari (8'lik) ve arpej
    bas_notalari = [55.0, 55.0, 65.41, 55.0, 82.41, 55.0, 73.42, 65.41]      # A1 A1 C2 A1 E2 A1 D2 C2
    arp = [220.0, 261.63, 329.63, 440.0, 329.63, 261.63, 392.0, 329.63]       # A3 C4 E4 A4 E4 C4 G4 E4
    for n in range(toplam16):
        t0 = n * adim16
        if t0 >= sure:
            break
        beat_i, alt = divmod(n, 4)
        # kick her vurusta (dort-dortluk), girisin ilk bari daha sakin
        giris = 0.55 + 0.45 * min(t0 / 3.0, 1.0)
        if alt == 0:
            _ekle(mix, kicker, t0, 1.0 * giris)
        if alt == 0 and beat_i % 2 == 1:
            _ekle(mix, klap(rng), t0, 0.55 * giris)
        if alt in (0, 2):
            _ekle(mix, bas(bas_notalari[(n // 2) % len(bas_notalari)]), t0, 0.80 * giris)
        _ekle(mix, hat(rng, acik=(alt == 2)), t0, 0.9 if alt % 2 == 0 else 0.55)
        if t0 > 1.5:
            _ekle(mix, arpej_notasi(arp[n % len(arp)], rng), t0, 0.55)
    # gol anlari: muzik yatagi kisa sure cekilir; riser ve darbe SONRA, cekilmemis olarak eklenir
    sidechain = np.ones_like(mix)
    for g in goller_sn:
        a, b = int((g - 0.06) * SR), int((g + 0.45) * SR)
        sidechain[max(a, 0):b] *= 0.30
        sidechain[int(max(g - 0.25, 0) * SR):max(a, 0)] *= 0.55
    mix *= sidechain
    for g in goller_sn:
        _ekle(mix, riser(1.6, rng), max(g - 1.6, 0), 1.0)
        _ekle(mix, darbe(rng), g, 1.35)
    # yumusak doyma + normalizasyon + kapanis
    mix = np.tanh(mix * 0.9)
    n = int(sure * SR)
    mix = mix[:n]
    son = int(2.0 * SR)
    mix[-son:] *= np.linspace(1, 0, son) ** 1.5
    mix /= max(np.abs(mix).max(), 1e-9)
    mix *= 0.89                                                  # ~ -1 dBFS
    sol = mix
    sag = np.roll(mix, int(0.0004 * SR)) * 0.98                  # hafif stereo acikligi
    st = np.stack([sol, sag], axis=1)
    pcm = (st * 32767).astype("<i2")
    with wave.open(str(yol_wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return mix


# ---------------- "celestial phonk" stili ----------------
def _yanki(x, sure=1.8, agirlik=0.38):
    """Basit yapay yanki (reverb): sonlu, ussel sonen gurultu darbe yaniti, FFT ile."""
    rng = np.random.default_rng(3)
    n = int(sure * SR)
    t = np.arange(n) / SR
    ir = rng.normal(0, 1, n) * np.exp(-t * 3.0)
    ir = _alcak_geciren(ir, 5500)
    ir /= np.abs(ir).max()
    uz = len(x) + n
    y = np.fft.irfft(np.fft.rfft(x, uz) * np.fft.rfft(ir, uz), uz)[:len(x)]
    y *= np.abs(x).max() / max(np.abs(y).max(), 1e-9)
    return x * (1 - agirlik) + y * agirlik * 1.6


def _808(f0, uzun, rng):
    t = np.arange(int(uzun * SR)) / SR
    f = f0 * (1 + 1.6 * np.exp(-t * 35))                      # girisinde pes dusen kayma
    ses = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.6)
    return np.tanh(ses * 3.2) * 0.85                          # bozulma (phonk karakteri)


def _inek_zili(f, rng):
    t = np.arange(int(0.22 * SR)) / SR
    ses = np.sign(np.sin(2 * np.pi * f * t)) + 0.8 * np.sign(np.sin(2 * np.pi * f * 1.504 * t))
    ses = _yuksek_geciren(_alcak_geciren(ses, 4200), 380)
    return ses * np.exp(-t * 22) * 0.22


def _can(f, uzun=1.4):
    t = np.arange(int(uzun * SR)) / SR
    ses = sum(a * np.sin(2 * np.pi * f * k * t) * np.exp(-t * d)
              for k, a, d in ((1, 1.0, 2.2), (2.76, 0.45, 3.4), (5.4, 0.22, 5.0), (8.9, 0.10, 8.0)))
    return ses * 0.22


def _pad(frekanslar, sure):
    t = np.arange(int(sure * SR)) / SR
    ses = np.zeros_like(t)
    for f in frekanslar:
        for det in (-0.004, 0.0, 0.004):
            ses += np.sin(2 * np.pi * f * (1 + det) * t + np.random.default_rng(int(f)).uniform(0, 6.28))
    ses *= 0.5 + 0.5 * np.sin(2 * np.pi * 0.22 * t - 1.2)       # yavas dalgalanma
    zarf = np.minimum(t / 0.6, 1.0)
    return ses / len(frekanslar) / 3 * zarf * 0.95


def uret_celestial(sure, goller_sn, yol_wav):
    rng = np.random.default_rng(11)
    bpm = 130
    adim = 60.0 / bpm / 4
    mix = _bos(sure)
    gokyuzu = _bos(sure)        # yanki gonderilen kisim (pad + canlar)
    tum = int(sure / adim) + 2
    notalar_808 = {0: 43.65, 3: 43.65, 6: 51.91, 10: 38.89, 13: 43.65}          # F1 F1 Ab1 Eb1 F1
    can_dizisi = [698.5, 830.6, 1046.5, 1244.5, 1046.5, 830.6, 784.0, 830.6]    # F5 Ab5 C6 Eb6 ...
    zil = {0: 0, 2: 1, 3: 0, 6: 1, 8: 0, 10: 1, 11: 0, 14: 1}                   # inek zili ritmi
    akor = [174.6, 207.7, 261.6, 311.1, 392.0]                                    # Fm9
    _ekle(gokyuzu, _pad(akor, sure + 1), 0.0, 1.0)
    pad_oktav = _pad([f * 2 for f in akor[:3]], sure + 1)
    _ekle(gokyuzu, pad_oktav, 0.0, 0.45)
    kick_ses = kick()
    for n in range(tum):
        t0 = n * adim
        if t0 >= sure:
            break
        bar, k = divmod(n, 16)
        davul = t0 >= 1.85                                             # ilk barda sadece goksel katman
        if k % 2 == 0:
            _ekle(gokyuzu, _can(can_dizisi[(n // 2) % len(can_dizisi)]), t0, 1.0 if k % 4 == 0 else 0.6)
        if not davul:
            continue
        if k in (0, 3, 6, 10, 13):
            _ekle(mix, kick_ses, t0, 1.0)
        if k in notalar_808:
            _ekle(mix, _808(notalar_808[k], 0.36, rng), t0, 0.55)
        if k in (4, 12):
            _ekle(mix, klap(rng), t0, 0.6)
        if k in zil:
            _ekle(mix, _inek_zili(540.0 if zil[k] == 0 else 800.0, rng), t0, 1.0)
        if k % 2 == 0:
            _ekle(mix, hat(rng, acik=(k % 4 == 2)), t0, 0.65)
    gokyuzu = _yanki(gokyuzu)
    mix = (mix + gokyuzu * 0.55) * 0.62          # yatak geri cekilir: gol vuruslari one ciksin
    sidechain = np.ones_like(mix)
    for g in goller_sn:
        a, b = int((g - 0.06) * SR), int((g + 0.45) * SR)
        sidechain[max(a, 0):b] *= 0.30
        sidechain[int(max(g - 0.25, 0) * SR):max(a, 0)] *= 0.55
    mix *= sidechain
    for g in goller_sn:
        _ekle(mix, riser(1.6, rng), max(g - 1.6, 0), 1.0)
        _ekle(mix, darbe(rng), g, 1.35)
        # gokyuzu parlamasi: golde yuksek canlar
        for j, f in enumerate((1046.5, 1568.0, 2093.0)):
            _ekle(mix, _can(f, 1.8), g + 0.06 * j, 1.1)
    mix = np.tanh(mix * 0.9)
    n = int(sure * SR)
    mix = mix[:n]
    son = int(2.0 * SR)
    mix[-son:] *= np.linspace(1, 0, son) ** 1.5
    mix /= max(np.abs(mix).max(), 1e-9)
    mix *= 0.89
    st = np.stack([mix, np.roll(mix, int(0.0004 * SR)) * 0.98], axis=1)
    with wave.open(str(yol_wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype("<i2").tobytes())
    return mix


# ---------------- harici (lisansli) parca: dongu + gol vuruslari ----------------
def _wav_oku(yol):
    with wave.open(str(yol), "rb") as w:
        n, ch = w.getnframes(), w.getnchannels()
        x = np.frombuffer(w.readframes(n), dtype="<i2").reshape(-1, ch).astype(float) / 32768
        sr = w.getframerate()
    assert sr == SR, f"ornekleme hizi {sr} != {SR}"
    return x if ch == 2 else np.stack([x[:, 0], x[:, 0]], axis=1)


def bpm_bul(x, bas=60, son=200):
    """Basit tempo kestirimi: dusuk frekans enerji zarfi uzerinde otokorelasyon."""
    m = x.mean(axis=1)
    alcak = _alcak_geciren(m, 180)
    adim = int(0.01 * SR)
    zarf = np.array([np.sqrt((alcak[i:i + adim * 2] ** 2).mean()) for i in range(0, len(alcak) - adim * 2, adim)])
    fark = np.maximum(np.diff(zarf), 0)
    fark -= fark.mean()
    ac = np.correlate(fark, fark, "full")[len(fark) - 1:]
    en = (None, -1)
    for bpm10 in range(bas * 10, son * 10, 2):
        lag = 60.0 / (bpm10 / 10) / 0.01
        i = int(round(lag))
        if i + 1 >= len(ac):
            continue
        d = ac[i] * (1 - (lag - i)) + ac[i + 1] * (lag - i)
        if d > en[1]:
            en = (bpm10 / 10, d)
    return en[0]


def ilk_vurus(x, esik=0.35):
    """Ilk guclu alcak frekans vurusunun zamani (saniye): dongunun hizalanacagi nokta."""
    alcak = np.abs(_alcak_geciren(x.mean(axis=1), 150))
    adim = int(0.005 * SR)
    zarf = np.array([alcak[i:i + adim].max() for i in range(0, len(alcak) - adim, adim)])
    i = int(np.argmax(zarf > esik * zarf.max()))
    return i * 0.005


def kalabalik(rng, sure=3.6):
    """Sentezlenmis stadyum tezahurati: formant bantli gurultu, kalabalik dalgalanmasi,
    hizli yukselen ve yavas sonen zarf."""
    n = int(sure * SR)
    t = np.arange(n) / SR
    f = np.fft.rfftfreq(n, 1 / SR)
    toplam = np.zeros(n)
    for fc, bw, kazanc in ((520, 220, 1.0), (1150, 420, 0.9), (2300, 800, 0.6), (4200, 1500, 0.3)):
        gurultu = rng.normal(0, 1, n)
        spek = np.fft.rfft(gurultu) * np.exp(-0.5 * ((f - fc) / bw) ** 2)
        bant = np.fft.irfft(spek, n)
        # kalabalik titresimi: her bant kendi yavas, rastgele genlik dalgalanmasiyla
        titre = np.fft.irfft(np.fft.rfft(rng.normal(0, 1, n)) * np.exp(-0.5 * (f / 5.0) ** 2), n)
        titre = 1 + 0.45 * titre / max(np.abs(titre).max(), 1e-9)
        toplam += bant / max(np.abs(bant).max(), 1e-9) * kazanc * titre
    zarf = np.minimum((t / 0.28) ** 1.4, 1.0) * np.where(t < 1.3, 1.0, np.exp(-(t - 1.3) / 0.85))
    ses = toplam * zarf
    return ses / max(np.abs(ses).max(), 1e-9) * 0.9


def gol_sesi_yukle(yol, sn=2.5):
    """Kullanicinin verdigi ses dosyasinin ilk `sn` saniyesi (mono/stereo -> stereo, 44.1 kHz),
    basinda 15 ms, sonunda 0.5 sn yumusak kapanisla."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(yol), "-t", str(sn), "-f", "s16le", "-ac", "2",
                          "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype="<i2").reshape(-1, 2).astype(float) / 32768
    n = len(x)
    giris, cikis = int(0.015 * SR), int(0.5 * SR)
    x[:giris] *= np.linspace(0, 1, giris)[:, None]
    x[-cikis:] *= np.linspace(1, 0, cikis)[:, None] ** 1.3
    return x / max(np.abs(x).max(), 1e-9) * 0.9


def uret_harici(dosya, sure, goller_sn, yol_wav, gol_sesi=False, yukselis=False, ses_dosyasi=None, ses_sn=2.5,
                sfx=None):
    x = _wav_oku(dosya)
    bpm = bpm_bul(x)
    ilk = ilk_vurus(x)
    bar = 4 * 60.0 / bpm
    # enerji dususu: parcanin sonundaki kisilma (outro) dongu disinda kalsin
    m = x.mean(axis=1)
    pen = SR
    zarf = np.array([20 * np.log10(np.sqrt((m[i:i + pen] ** 2).mean()) + 1e-9)
                     for i in range(int(ilk * SR), len(m) - pen, int(0.25 * SR))])
    tepe = zarf.max()
    dus = np.where(zarf < tepe - 4.0)[0]
    t_son = ilk + (dus[0] * 0.25 if len(dus) else len(m) / SR - ilk)
    n_bar = max(int((t_son - ilk) // bar), 4)
    dongu = x[int(ilk * SR):int((ilk + n_bar * bar) * SR)]
    giris = x[:0]                       # sessiz giris atlanir: video dogrudan enerjiyle baslar
    print(f"tempo ~{bpm:.1f} BPM | ilk vurus {ilk:.2f}s | bar {bar:.2f}s | dongu {n_bar} bar ({len(dongu) / SR:.1f}s)")
    cf = int(0.03 * SR)
    cikis = [giris, dongu]
    toplam = len(giris) + len(dongu)
    while toplam < sure * SR + SR:
        cikis.append(dongu)
        toplam += len(dongu)
    y = cikis[0]
    for parca in cikis[1:]:
        k = min(cf, len(parca), len(y))
        w = np.linspace(0, 1, k)[:, None]
        y = np.concatenate([y[:-k], y[-k:] * np.sqrt(1 - w) + parca[:k] * np.sqrt(w), parca[k:]])
    n = int(sure * SR)
    mix = np.zeros((n + SR, 2))
    mix[:min(len(y), len(mix))] = y[:len(mix)]
    rng = np.random.default_rng(5)
    sc = np.ones(len(mix))
    for g in goller_sn:
        a, b = int((g - 0.06) * SR), int((g + 0.45) * SR)
        sc[max(a, 0):b] *= 0.40
        sc[int(max(g - 0.25, 0) * SR):max(a, 0)] *= 0.65
        if gol_sesi or ses_dosyasi:
            sc[b:int((g + 2.6) * SR)] *= 0.35             # gol sesi duyulsun diye muzik geri cekilir
    for t_sfx, tur, _ in (sfx or []):                     # tik: muzik cok kisa (0.14 sn) geri cekilir, tik onun ustunde duyulur
        if tur == "tik":
            sc[int(max(t_sfx - 0.02, 0) * SR):int((t_sfx + 0.14) * SR)] *= 0.45
        elif tur == "whoosh":                                 # kamera hareketi: muzik 0.6 sn boyunca geri cekilir
            sc[int(max(t_sfx - 0.05, 0) * SR):int((t_sfx + 0.6) * SR)] *= 0.5
    mix *= sc[:, None]
    gercek = gol_sesi_yukle(ses_dosyasi, ses_sn) if ses_dosyasi else None
    for g in goller_sn:
        r, d = riser(1.6, rng), darbe(rng)
        k = kalabalik(rng) if gol_sesi else None
        if gercek is not None:
            i0 = int(g * SR)
            m = min(len(gercek), len(mix) - i0)
            mix[i0:i0 + m] += gercek[:m] * 4.0              # muzik yatagi geri cekildigi icin net duyulur
        for ch in (0, 1):
            if yukselis:                                   # "viss" sesi: varsayilan kapali
                _ekle(mix[:, ch], r, max(g - 1.6, 0), 0.55)
            _ekle(mix[:, ch], d, g, 0.45 if gercek is not None else 0.75)
            if k is not None:
                _ekle(mix[:, ch], k, g + 0.05, 3.4)
    for t_sfx, tur, kazanc in (sfx or []):               # videoya ozel efektler: (saniye, 'tik'|'parilti'|'darbe', kazanc)
        snd = {"tik": tik, "parilti": parilti, "darbe": darbe, "whoosh": whoosh}[tur](rng)
        for ch in (0, 1):
            _ekle(mix[:, ch], snd, t_sfx, kazanc)
    mix = mix[:n]
    son = int(2.0 * SR)
    mix[-son:] *= (np.linspace(1, 0, son) ** 1.5)[:, None]
    mix = np.tanh(mix * 0.9)
    mix /= max(np.abs(mix).max(), 1e-9)
    mix *= 0.89
    with wave.open(str(yol_wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype("<i2").tobytes())
    return mix[:, 0]


def _lufs(yol):
    """Entegre ses siddeti (LUFS), ffmpeg ebur128 ile."""
    import re
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(yol), "-af", "ebur128=peak=true",
                        "-f", "null", "-"], capture_output=True, text=True)
    return float(re.findall(r"I:\s+(-?\d+\.\d+) LUFS", r.stderr)[-1])


def videoya_ekle(video, goller_dk, dk_sn=2.2, stil="rekabet", dosya=None, lufs=-22, gol_ses=None, gol_ses_sn=2.5,
                 sfx=None):
    video = Path(video)
    sure = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "default=nw=1:nk=1", str(video)]).decode().strip())
    goller_sn = [g / dk_sn for g in goller_dk]
    wav = video.with_suffix(".muzik.wav")
    if stil == "harici":
        mix = uret_harici(dosya, sure, goller_sn, wav, ses_dosyasi=gol_ses, ses_sn=gol_ses_sn, sfx=sfx)
    else:
        mix = (uret_celestial if stil == "celestial" else uret)(sure, goller_sn, wav)
    cikis = video.with_name(video.stem + f"_muzikli_{stil}.mp4")
    # dinamikleri bozmadan (loudnorm degil) sabit kazancla hedef seviyeye cek: gol vuruslari/tezahurat korunur
    kazanc = lufs - _lufs(wav)
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(wav),
                           "-c:v", "copy", "-af", f"volume={kazanc:.2f}dB,alimiter=limit=0.7:level=disabled",
                           "-c:a", "aac", "-b:a", "192k",
                           "-shortest", str(cikis)])
    print(f"tepe: {20 * np.log10(np.abs(mix).max()):.1f} dBFS | rms: {20 * np.log10(np.sqrt((mix ** 2).mean())):.1f} dBFS")
    return cikis


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    goller = [float(x) for x in a[a.index("--goller") + 1].split(",")] if "--goller" in a else []
    dk_sn = float(a[a.index("--dk-sn") + 1]) if "--dk-sn" in a else 2.2
    stil = a[a.index("--stil") + 1] if "--stil" in a else "rekabet"
    dosya = a[a.index("--dosya") + 1] if "--dosya" in a else None
    lufs = float(a[a.index("--lufs") + 1]) if "--lufs" in a else -22
    gol_ses = a[a.index("--gol-ses") + 1] if "--gol-ses" in a else None
    gol_ses_sn = float(a[a.index("--gol-ses-sn") + 1]) if "--gol-ses-sn" in a else 2.5
    print(videoya_ekle(a[0], goller, dk_sn, stil, dosya, lufs, gol_ses, gol_ses_sn))

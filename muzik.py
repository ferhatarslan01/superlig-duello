"""Ozgun 'rekabet' muzigi uretici (telifsiz; tamamen kodla sentezlenir) ve videoya ekleme.

Gergin, bas agirlikli 140 BPM elektronik ritim: kick, sub bas, klap, hi-hat, a-minor arpej, gol aninda
yukselen gerilim (riser) + dusuk darbe (impact) + kisa ses cekilmesi (sidechain).

Kullanim:
  python muzik.py out/baski_334a7356.mp4 --goller 29,44,62 --dk-sn 2.2      # <video>_muzikli.mp4
(--goller: mac dakikalari; --dk-sn: videoda saniye basina mac dakikasi)
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


def videoya_ekle(video, goller_dk, dk_sn=2.2):
    video = Path(video)
    sure = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "default=nw=1:nk=1", str(video)]).decode().strip())
    goller_sn = [g / dk_sn for g in goller_dk]
    wav = video.with_suffix(".muzik.wav")
    mix = uret(sure, goller_sn, wav)
    cikis = video.with_name(video.stem + "_muzikli.mp4")
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(wav),
                           "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=9", "-c:a", "aac", "-b:a", "192k",
                           "-shortest", str(cikis)])
    print(f"tepe: {20 * np.log10(np.abs(mix).max()):.1f} dBFS | rms: {20 * np.log10(np.sqrt((mix ** 2).mean())):.1f} dBFS")
    return cikis


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    goller = [float(x) for x in a[a.index("--goller") + 1].split(",")] if "--goller" in a else []
    dk_sn = float(a[a.index("--dk-sn") + 1]) if "--dk-sn" in a else 2.2
    print(videoya_ekle(a[0], goller, dk_sn))

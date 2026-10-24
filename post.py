"""Otomatik paylasim: kart uretir, `media` dalinda barindirir, Buffer ile X'e gonderir.

Kullanim:
  python post.py mac              # yeni biten maclar icin duello karti
  python post.py sezon            # haftalik sezon karsilastirmasi
  python post.py liderler         # sali: gol krali, asist krali, kartlar (3 gorsel)
  ... --dry-run                   # kart + metin uretir, hicbir sey gondermez / kaydetmez

Ortam degiskenleri (GitHub Actions secrets): BUFFER_API_KEY, BUFFER_CHANNEL_ID
GITHUB_REPOSITORY (owner/repo) Actions'ta otomatik gelir; medya URL'si icin gerekir.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duello
import fotograf
import sezon

KLASOR = Path(__file__).parent
STATE = KLASOR / "data" / "state.json"
MEDIA_BRANCH = "media"
MEDIA_KEEP_GUN = 3
MAX_MAC_PER_RUN = 2        # bir calismada en fazla bu kadar mac paylasilir
MAC_PENCERE_SAAT = int(os.environ.get("MAC_PENCERE_SAAT", "8"))  # bundan eski maclar atlanir (ilk calismada eski maclari basma)
BUFFER_URL = "https://api.buffer.com"


# ---------- durum ----------
def durum_oku():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"maclar": []}


def durum_yaz(d):
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------- medya barindirma (media dali, tek orphan commit) ----------
def git(cwd, *args, check=True):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r


def medya_yukle(yol: Path) -> str:
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise RuntimeError("GITHUB_REPOSITORY yok; medya URL'si uretilemez (yalnizca Actions'ta calisir)")
    git(KLASOR, "config", "user.name", "github-actions[bot]")
    git(KLASOR, "config", "user.email", "github-actions[bot]@users.noreply.github.com")
    var = git(KLASOR, "fetch", "origin", f"+{MEDIA_BRANCH}:refs/remotes/origin/{MEDIA_BRANCH}", check=False).returncode == 0

    dizin = Path(tempfile.mkdtemp(prefix="media-wt-")) / "wt"
    squash = f"media-squash-{os.getpid()}"
    ad = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + yol.name
    try:
        git(KLASOR, "worktree", "add", "--detach", str(dizin), f"origin/{MEDIA_BRANCH}" if var else "HEAD")
        git(dizin, "checkout", "--orphan", squash)
        if not var:
            git(dizin, "rm", "-rf", "--quiet", ".")
        sinir = datetime.now(timezone.utc) - timedelta(days=MEDIA_KEEP_GUN)
        for f in dizin.iterdir():
            if f.is_file() and f.name[:8].isdigit():
                try:
                    if datetime.strptime(f.name[:8], "%Y%m%d").replace(tzinfo=timezone.utc) < sinir:
                        f.unlink()
                except ValueError:
                    pass
        shutil.copy(yol, dizin / ad)
        git(dizin, "add", "-A")
        git(dizin, "commit", "-q", "-m", f"media {ad}")
        git(dizin, "push", "--force", "origin", f"{squash}:{MEDIA_BRANCH}")
    finally:
        git(KLASOR, "worktree", "remove", "--force", str(dizin), check=False)
        git(KLASOR, "worktree", "prune", check=False)
        git(KLASOR, "branch", "-D", squash, check=False)
    return f"https://raw.githubusercontent.com/{repo}/{MEDIA_BRANCH}/{ad}"


# ---------- Buffer ----------
def buffer_gonder(metin: str, gorsel_urller):
    anahtar, kanal = os.environ["BUFFER_API_KEY"], os.environ["BUFFER_CHANNEL_ID"]
    sorgu = """
      mutation CreatePost($text: String!, $channelId: ChannelId!, $assets: [AssetInput!]) {
        createPost(input: {text: $text, channelId: $channelId, schedulingType: automatic,
                           mode: shareNow, assets: $assets}) {
          ... on PostActionSuccess { post { id text } }
          ... on MutationError { message }
        }
      }"""
    govde = json.dumps({"query": sorgu, "variables": {
        "text": metin, "channelId": kanal, "assets": [{"image": {"url": u}} for u in gorsel_urller]}}).encode()
    istek = urllib.request.Request(BUFFER_URL, data=govde, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {anahtar}"})
    with urllib.request.urlopen(istek, timeout=60) as r:
        yanit = json.load(r)
    if yanit.get("errors"):
        raise RuntimeError(f"Buffer GraphQL hatasi: {yanit['errors']}")
    sonuc = yanit["data"]["createPost"]
    if "message" in sonuc:
        raise RuntimeError(f"Buffer: {sonuc['message']}")
    return sonuc["post"]["id"]


def paylas(metin, yol, dry):
    print("-" * 50)
    print(metin)
    yollar = list(yol) if isinstance(yol, (list, tuple)) else [yol]
    print(f"[{', '.join(str(y) for y in yollar)}]")
    if dry:
        print("(dry-run: gonderilmedi)")
        return True
    if not (os.environ.get("BUFFER_API_KEY") and os.environ.get("BUFFER_CHANNEL_ID")):
        raise SystemExit("HATA: BUFFER_API_KEY / BUFFER_CHANNEL_ID yok (depo secret'larini kontrol et); gonderilmedi")
    pid = buffer_gonder(metin, [medya_yukle(y) for y in yollar])
    print(f"Buffer gonderi id: {pid}")
    return True


# ---------- metinler ----------
def foto_notu(*oyuncular):
    k = sorted({o["_foto"] for o in oyuncular if o.get("_foto")})
    return "\n\nFotoğraf: " + ", ".join(k) if k else ""



def mac_metni(ev, rol, oa, ob):
    from kart_v2 import takim_adi
    c = ev["header"]["competitions"][0]["competitors"]
    ev_s = next(t for t in c if t["homeAway"] == "home")
    dep = next(t for t in c if t["homeAway"] == "away")
    skor = (f'{takim_adi(ev_s["team"]["displayName"])} {ev_s["score"]}-{dep["score"]} '
            f'{takim_adi(dep["team"]["displayName"])}')
    return "\n\n".join([
        skor,
        f"{oa['ad']} ({takim_adi(oa['_takim'])}) vs {ob['ad']} ({takim_adi(ob['_takim'])})",
        "Sence bu düelloyu kim kazandı? 👇",
        "#SüperLig #Futbol",
    ]) + foto_notu(oa, ob)


def sezon_metni(rol, a, b, benz):
    from kart_v2 import takim_adi
    return "\n\n".join([
        "Sezon karşılaştırması",
        f"{a['ad']} ({takim_adi(a['takim'])}) vs {b['ad']} ({takim_adi(b['takim'])})",
        "İkisinden hangisini seçerdin? 👇",
        "#SüperLig #Futbol",
    ]) + foto_notu(a, b)


# ---------- modlar ----------
def yeni_biten_maclar():
    simdi = datetime.now(timezone.utc)
    bulunan = []
    for g in range(MAC_PENCERE_SAAT // 24 + 2):
        gun = simdi - timedelta(days=g)
        v = duello.get(f"{duello.API}/scoreboard?dates={gun:%Y%m%d}")
        for e in v.get("events", []):
            if not e["status"]["type"]["completed"]:
                continue
            baslangic = datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
            if simdi - baslangic <= timedelta(hours=MAC_PENCERE_SAAT):
                bulunan.append(e["id"])
    return list(dict.fromkeys(bulunan))


def mod_mac(dry):
    durum = durum_oku()
    yeni = [e for e in yeni_biten_maclar() if e not in durum["maclar"]][:MAX_MAC_PER_RUN]
    if not yeni:
        print("Yeni biten mac yok")
        return
    for eid in yeni:
        try:
            sonuc = duello.kart_uret(eid)
        except Exception as e:
            print(f"{eid}: kart uretilemedi ({e}); sonraki calismada tekrar denenecek", file=sys.stderr)
            continue
        if sonuc is None:
            print(f"{eid}: eslesen oyuncu cifti yok, atlandi")
            if not dry:
                durum["maclar"].append(eid)
            continue
        yol, rol, oa, ob, ev = sonuc
        if paylas(mac_metni(ev, rol, oa, ob), yol, dry) and not dry:
            durum["maclar"].append(eid)
            durum["maclar"] = durum["maclar"][-200:]
            durum_yaz(durum)


def mod_sezon(dry):
    sonuc = sezon.sezon_kart()
    if not sonuc:
        print("Uygun oyuncu cifti yok")
        return
    yol, rol, a, b, benz = sonuc
    if paylas(sezon_metni(rol, a, b, benz), yol, dry) and not dry:
        sezon.paylasildi_isaretle(a, b)


def liderler_metni(l):
    from kart_v2 import takim_adi  # noqa: F401

    def kisa(o):
        return o["ad"].split()[-1]

    def liste(tur, f):
        return ", ".join(f"{kisa(o)} {f(o)}" for o in l[tur][:3])
    gol = liste("gol", lambda o: int(o["st"]["totalGoals"]))
    asist = liste("asist", lambda o: int(o["st"]["goalAssists"]))
    kart = liste("kart", lambda o: f"{int(o['st'].get('yellowCards', 0))}🟨{int(o['st'].get('redCards', 0))}🟥")
    return "\n\n".join([
        "Süper Lig liderleri · 2026-27",
        f"⚽ Gol krallığı: {gol}",
        f"🅰️ Asist krallığı: {asist}",
        f"🟨🟥 Kart liderleri: {kart}",
        "#SüperLig #Futbol",
    ])


def mod_liderler(dry, zorla=False):
    import kart_lider
    hafta = datetime.now(timezone.utc).strftime("%G-W%V")
    durum = durum_oku()
    if not dry and not zorla and durum.get("liderler_hafta") == hafta:
        print(f"{hafta} haftasinin liderleri zaten paylasildi")
        return
    yollar, l = kart_lider.uret()
    kaynaklar = sorted({fotograf.foto_al(o["ad"], o["takim"])[1] or "" for t in l.values() for o in t} - {""})
    metin = liderler_metni(l) + (f"\n\nFotoğraf: {', '.join(kaynaklar)}" if kaynaklar else "")
    if paylas(metin, yollar, dry) and not dry:
        durum["liderler_hafta"] = hafta
        durum_yaz(durum)


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    mod = next((a for a in args if not a.startswith("--")), None)
    if mod == "mac":
        mod_mac(dry)
    elif mod == "sezon":
        mod_sezon(dry)
    elif mod == "liderler":
        mod_liderler(dry, zorla="--zorla" in args)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()

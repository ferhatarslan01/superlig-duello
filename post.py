"""Otomatik paylasim: kart uretir, `media` dalinda barindirir, Buffer ile X'e gonderir.

Kullanim:
  python post.py mac              # yeni biten maclar icin duello karti
  python post.py sezon            # haftalik sezon duellosu
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
def buffer_gonder(metin: str, gorsel_url: str):
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
        "text": metin, "channelId": kanal, "assets": [{"image": {"url": gorsel_url}}]}}).encode()
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
    print(f"[{yol}]")
    if dry:
        print("(dry-run: gonderilmedi)")
        return True
    if not (os.environ.get("BUFFER_API_KEY") and os.environ.get("BUFFER_CHANNEL_ID")):
        raise SystemExit("HATA: BUFFER_API_KEY / BUFFER_CHANNEL_ID yok (depo secret'larini kontrol et); gonderilmedi")
    pid = buffer_gonder(metin, medya_yukle(yol))
    print(f"Buffer gonderi id: {pid}")
    return True


# ---------- metinler ----------
def mac_metni(ev, rol, oa, ob):
    c = ev["header"]["competitions"][0]["competitors"]
    ev_s = next(t for t in c if t["homeAway"] == "home")
    dep = next(t for t in c if t["homeAway"] == "away")
    skor = f'{ev_s["team"]["displayName"]} {ev_s["score"]}-{dep["score"]} {dep["team"]["displayName"]}'
    return (f"{skor}\n\n{rol} düellosu: {oa['ad']} ({oa['_takim']}) vs {ob['ad']} ({ob['_takim']})\n\n"
            f"Sence bu düelloyu kim kazandı? 👇\n\n#SüperLig #Futbol")


def sezon_metni(rol, a, b, benz):
    return (f"{rol} · sezon düellosu\n\n{a['ad']} ({a['takim']}) ile {b['ad']} ({b['takim']}) "
            f"sezon boyunca %{benz} benzer bir profil çiziyor.\n\n"
            f"İkisinden hangisini seçerdin? 👇\n\n#SüperLig #Futbol")


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


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    mod = next((a for a in args if not a.startswith("--")), None)
    if mod == "mac":
        mod_mac(dry)
    elif mod == "sezon":
        mod_sezon(dry)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()

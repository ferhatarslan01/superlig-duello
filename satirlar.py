"""Mevkiye gore kart satirlari (en fazla 8; basta oynanan mac ve dakika).

Her satir: (alan, etiket). Hesaplanan alanlar kart_v2._deger icinde tanimli:
  shotAcc (isabetli sut/sut %), minPerGoal (gol basina dakika), gcPerMatch (mac basina yenen gol),
  tackleSuccess (top calma basarisi %), saveRate (kurtaris orani %).
"""

# daha DUSUK olan kazanir (kutu vurgusu icin)
DUSUK_IYI = {"minPerGoal", "gcPerMatch"}
# yuksek olmasi "daha iyi" anlamina gelmeyenler: vurgu yok
VURGUSUZ = {"foulsCommitted", "yellowCards", "redCards", "offsides", "goalsConceded",
            "appearances", "minutes", "starts", "subIns"}

# --- SEZON ---
# xG, xA, kilit pas vb. PitchAPI'den (gelismis.py); veri yoksa satir kartta gizlenir.
_FORVET = [("totalGoals", "GOL"), ("goalAssists", "ASİST"), ("xG", "BEKLENEN GOL (xG)"),
           ("xgDiff", "GOL - xG FARKI"), ("totalShots", "ŞUT"), ("boxShotPct", "CEZA SAHASI İÇİ ŞUT")]
_KANAT = [("totalGoals", "GOL"), ("goalAssists", "ASİST"), ("xG", "BEKLENEN GOL (xG)"),
          ("xA", "BEKLENEN ASİST (xA)"), ("keyPasses", "KİLİT PAS"), ("takeOnsWon", "BAŞARILI ÇALIM")]
_OFANSIF_OS = [("totalGoals", "GOL"), ("goalAssists", "ASİST"), ("xA", "BEKLENEN ASİST (xA)"),
               ("keyPasses", "KİLİT PAS"), ("progPasses", "İLERLETİCİ PAS"), ("takeOnsWon", "BAŞARILI ÇALIM")]
_YAN_OS = [("totalGoals", "GOL"), ("goalAssists", "ASİST"), ("xA", "BEKLENEN ASİST (xA)"),
           ("keyPasses", "KİLİT PAS"), ("takeOnsWon", "BAŞARILI ÇALIM"), ("progPasses", "İLERLETİCİ PAS")]
_MERKEZ_OS = [("totalGoals", "GOL"), ("goalAssists", "ASİST"), ("xA", "BEKLENEN ASİST (xA)"),
              ("keyPasses", "KİLİT PAS"), ("progPasses", "İLERLETİCİ PAS"), ("passPct", "PAS İSABETİ")]
_SAVUNMA_OS = [("totalGoals", "GOL"), ("effectiveTackles", "TOP ÇALMA"), ("interceptions", "PAS ARASI"),
               ("progPasses", "İLERLETİCİ PAS"), ("aerialPct", "HAVA TOPU KAZANMA"), ("passPct", "PAS İSABETİ")]
_STOPER = [("effectiveTackles", "TOP ÇALMA"), ("interceptions", "PAS ARASI"), ("blocks", "BLOK"),
           ("totalClearance", "UZAKLAŞTIRMA"), ("aerialPct", "HAVA TOPU KAZANMA"), ("passPct", "PAS İSABETİ")]
_BEK = [("goalAssists", "ASİST"), ("keyPasses", "KİLİT PAS"), ("progPasses", "İLERLETİCİ PAS"),
        ("effectiveTackles", "TOP ÇALMA"), ("interceptions", "PAS ARASI"), ("takeOnsWon", "BAŞARILI ÇALIM")]
_KALECI = [("appearances", "MAÇ"), ("saves", "KURTARIŞ"), ("cleanSheet", "GOL YEMEDEN BİTEN MAÇ"),
           ("saveRate", "KURTARIŞ ORANI"), ("gcPerMatch", "MAÇ BAŞINA YENEN GOL"),
           ("penaltyKicksSaved", "PENALTI KURTARMA"), ("accuratePasses", "İSABETLİ PAS")]

SEZON = {
    "Forvet": _FORVET, "Kanat": _KANAT,
    "Ofansif orta saha": _OFANSIF_OS,
    "Yan orta saha": _YAN_OS, "Merkez orta saha": _MERKEZ_OS,
    "Defansif orta saha": _SAVUNMA_OS,
    "Stoper": _STOPER, "Bek": _BEK, "Kaleci": _KALECI,
}

# --- MAC SONU (tek macin istatistikleri) ---
# xG, kilit pas vb. PitchAPI'den (gelismis.mac_ekle); o macin verisi yoksa satir kartta gizlenir.
_MAC_FORVET = [("totalGoals", "GOL"), ("goalAssists", "ASİST"), ("xG", "BEKLENEN GOL (xG)"),
               ("totalShots", "ŞUT"), ("shotsOnTarget", "İSABETLİ ŞUT"), ("keyPasses", "KİLİT PAS"),
               ("passPct", "PAS İSABETİ")]
_MAC_KANAT = [("totalGoals", "GOL"), ("goalAssists", "ASİST"), ("xG", "BEKLENEN GOL (xG)"),
              ("xA", "BEKLENEN ASİST (xA)"), ("keyPasses", "KİLİT PAS"), ("takeOnsWon", "BAŞARILI ÇALIM"),
              ("totalShots", "ŞUT")]
_MAC_ORTA = [("totalGoals", "GOL"), ("goalAssists", "ASİST"), ("xA", "BEKLENEN ASİST (xA)"),
             ("keyPasses", "KİLİT PAS"), ("progPasses", "İLERLETİCİ PAS"), ("passPct", "PAS İSABETİ"),
             ("effectiveTackles", "TOP ÇALMA")]
_MAC_SAVUNMA = [("totalGoals", "GOL"), ("effectiveTackles", "TOP ÇALMA"), ("interceptions", "PAS ARASI"),
                ("blocks", "BLOK"), ("totalClearance", "UZAKLAŞTIRMA"), ("aerialsWon", "HAVA TOPU KAZANMA"),
                ("passPct", "PAS İSABETİ")]
_MAC_BEK = [("totalGoals", "GOL"), ("goalAssists", "ASİST"), ("keyPasses", "KİLİT PAS"),
            ("progPasses", "İLERLETİCİ PAS"), ("effectiveTackles", "TOP ÇALMA"), ("interceptions", "PAS ARASI"),
            ("passPct", "PAS İSABETİ")]
_MAC_KALECI = [("saves", "KURTARIŞ"), ("goalsConceded", "YENEN GOL"), ("saveRate", "KURTARIŞ ORANI"),
               ("accuratePasses", "İSABETLİ PAS"), ("passPct", "PAS İSABETİ")]

MAC = {
    "Forvet": _MAC_FORVET, "Kanat": _MAC_KANAT, "Ofansif orta saha": _MAC_KANAT,
    "Yan orta saha": _MAC_ORTA, "Merkez orta saha": _MAC_ORTA,
    "Defansif orta saha": _MAC_SAVUNMA,
    "Stoper": _MAC_SAVUNMA, "Bek": _MAC_BEK, "Kaleci": _MAC_KALECI,
}


MAX_SATIR = 8
# 8 satiri asinca bu sirayla dusurulur (en az onemliden baslayarak)
DUSURME_SIRASI = ["offsides", "yellowCards", "foulsCommitted", "foulsSuffered", "redCards"]
SEZON_ON = [("appearances", "OYNANAN MAÇ"), ("minutes", "OYNADIĞI SÜRE (DK)")]
MAC_ON = [("minutes", "OYNADIĞI SÜRE (DK)")]


def _birlestir(on, satirlar):
    liste = on + [r for r in satirlar if r[0] not in {a for a, _ in on}]
    for alan in DUSURME_SIRASI:
        if len(liste) <= MAX_SATIR:
            break
        liste = [r for r in liste if r[0] != alan]
    return liste


def sezon_satirlari(rol):
    return _birlestir(SEZON_ON, SEZON.get(rol, _MERKEZ_OS))


def mac_satirlari(rol):
    return _birlestir(MAC_ON, MAC.get(rol, _MAC_ORTA))

"""Mevkiye gore kart satirlari (en fazla 8 satir).

Her satir: (alan, etiket). Hesaplanan alanlar kart_v2._deger icinde tanimli:
  shotAcc (isabetli sut/sut %), minPerGoal (gol basina dakika), gcPerMatch (mac basina yenen gol),
  tackleSuccess (top calma basarisi %), saveRate (kurtaris orani %).
"puan": apifootball.com sezon ortalama puani (0-10). Her iki oyuncuda da yoksa satir gizlenir.
"""

# daha DUSUK olan kazanir (kutu vurgusu icin)
DUSUK_IYI = {"minPerGoal", "gcPerMatch"}
# yuksek olmasi "daha iyi" anlamina gelmeyenler: vurgu yok
VURGUSUZ = {"foulsCommitted", "yellowCards", "redCards", "offsides", "goalsConceded",
            "appearances", "minutes", "starts", "subIns"}

PUAN = ("puan", "ORTALAMA PUAN")

# --- SEZON ---
_UCLU = [PUAN, ("totalGoals", "GOL"), ("goalAssists", "ASİST"), ("totalShots", "ŞUT"),
         ("shotAcc", "ŞUT İSABETİ"), ("minPerGoal", "GOL BAŞINA DAKİKA"),
         ("foulsSuffered", "KAZANILAN FAUL")]
_OFANSIF_OS = [PUAN, ("totalGoals", "GOL"), ("goalAssists", "ASİST"), ("totalShots", "ŞUT"),
               ("shotAcc", "ŞUT İSABETİ"), ("passPct", "PAS İSABETİ"),
               ("foulsSuffered", "KAZANILAN FAUL")]
_ORTA_SAHA = [PUAN, ("totalGoals", "GOL"), ("goalAssists", "ASİST"), ("accuratePasses", "İSABETLİ PAS"),
              ("passPct", "PAS İSABETİ"), ("effectiveTackles", "TOP ÇALMA"),
              ("foulsSuffered", "KAZANILAN FAUL")]
_SAVUNMA_OS = [PUAN, ("totalGoals", "GOL"), ("goalAssists", "ASİST"), ("effectiveTackles", "TOP ÇALMA"),
               ("tackleSuccess", "TOP ÇALMA BAŞARISI"), ("totalClearance", "UZAKLAŞTIRMA"),
               ("passPct", "PAS İSABETİ"), ("foulsCommitted", "YAPILAN FAUL")]
_STOPER = [PUAN, ("totalGoals", "GOL"), ("goalAssists", "ASİST"), ("effectiveTackles", "TOP ÇALMA"),
           ("tackleSuccess", "TOP ÇALMA BAŞARISI"), ("totalClearance", "UZAKLAŞTIRMA"),
           ("passPct", "PAS İSABETİ"), ("foulsCommitted", "YAPILAN FAUL")]
_BEK = [PUAN, ("totalGoals", "GOL"), ("goalAssists", "ASİST"), ("effectiveTackles", "TOP ÇALMA"),
        ("tackleSuccess", "TOP ÇALMA BAŞARISI"), ("totalClearance", "UZAKLAŞTIRMA"),
        ("passPct", "PAS İSABETİ"), ("foulsSuffered", "KAZANILAN FAUL")]
_KALECI = [PUAN, ("saves", "KURTARIŞ"), ("cleanSheet", "GOL YEMEDEN BİTEN MAÇ"),
           ("saveRate", "KURTARIŞ ORANI"), ("gcPerMatch", "MAÇ BAŞINA YENEN GOL"),
           ("penaltyKicksSaved", "PENALTI KURTARMA"), ("accuratePasses", "İSABETLİ PAS")]

SEZON = {
    "Forvet": _UCLU, "Kanat": _UCLU,
    "Ofansif orta saha": _OFANSIF_OS,
    "Yan orta saha": _ORTA_SAHA, "Merkez orta saha": _ORTA_SAHA,
    "Defansif orta saha": _SAVUNMA_OS,
    "Stoper": _STOPER, "Bek": _BEK, "Kaleci": _KALECI,
}

# --- MAC SONU (tek macin istatistikleri; puan = sezon ortalamasi, mac bazli puan veri kaynaginda yok) ---
SEZON_PUANI = ("puan", "SEZON PUANI")
_MAC_UCLU = [SEZON_PUANI, ("totalGoals", "GOL"), ("goalAssists", "ASİST"), ("totalShots", "ŞUT"),
             ("shotsOnTarget", "İSABETLİ ŞUT"), ("passPct", "PAS İSABETİ"),
             ("foulsSuffered", "KAZANILAN FAUL")]
_MAC_ORTA = [SEZON_PUANI, ("totalGoals", "GOL"), ("goalAssists", "ASİST"), ("accuratePasses", "İSABETLİ PAS"),
             ("passPct", "PAS İSABETİ"), ("effectiveTackles", "TOP ÇALMA"),
             ("foulsSuffered", "KAZANILAN FAUL")]
_MAC_SAVUNMA = [SEZON_PUANI, ("totalGoals", "GOL"), ("goalAssists", "ASİST"), ("effectiveTackles", "TOP ÇALMA"),
                ("totalClearance", "UZAKLAŞTIRMA"), ("passPct", "PAS İSABETİ"),
                ("foulsCommitted", "YAPILAN FAUL")]
_MAC_KALECI = [SEZON_PUANI, ("saves", "KURTARIŞ"), ("goalsConceded", "YENEN GOL"), ("saveRate", "KURTARIŞ ORANI"),
               ("accuratePasses", "İSABETLİ PAS"), ("passPct", "PAS İSABETİ")]

MAC = {
    "Forvet": _MAC_UCLU, "Kanat": _MAC_UCLU, "Ofansif orta saha": _MAC_UCLU,
    "Yan orta saha": _MAC_ORTA, "Merkez orta saha": _MAC_ORTA,
    "Defansif orta saha": _MAC_SAVUNMA,
    "Stoper": _MAC_SAVUNMA, "Bek": _MAC_SAVUNMA, "Kaleci": _MAC_KALECI,
}


def sezon_satirlari(rol):
    return SEZON.get(rol, _ORTA_SAHA)


def mac_satirlari(rol):
    return MAC.get(rol, _MAC_ORTA)

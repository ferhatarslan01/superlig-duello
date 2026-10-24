# Süper Lig Düello Botu

ESPN'in açık verisinden Süper Lig oyuncu karşılaştırma kartları üretir ve Buffer ile X'e paylaşır.
Her şey GitHub Actions üzerinde çalışır.

| Ne | Ne zaman | Komut |
|---|---|---|
| **Maç sonu düellosu**: aynı rolde oynayan karşı oyuncular (gol, asist, şut, pas isabeti, top çalma...) | Maç saatlerinde 30 dakikada bir yeni biten maçı kontrol eder | `python post.py mac` |
| **Haftalık liderler**: gol krallığı, asist krallığı, kartlar (3 görsel) | Her salı 20:00 TRT | `python post.py liderler` |
| **Maç öncesi karşılaştırma**: o maçın iki takımından aynı mevkideki en dikkat çekici iki oyuncunun sezon karşılaştırması | Maça 1-4 saat kala (30 dk'da bir kontrol) | `python post.py oncesi` |
| **Sezon karşılaştırması** (elle, isteğe bağlı iki oyuncu) | Otomatik değil | `python post.py sezon Ad1 Ad2` |
| *(eski)* Sezon düellosu: 90 dk başına istatistiği en benzer iki oyuncu | Her perşembe 20:00 TRT | `python post.py sezon` |

`--dry-run` ekleyerek kart ve metin üretilir, hiçbir şey gönderilmez.

## Kurulum

1. Bu klasörü **herkese açık** (public) bir GitHub deposuna it. Görseller `media` dalında barındırılır ve Buffer'a
   `raw.githubusercontent.com` adresiyle verilir, bu yüzden depo public olmalı.
2. Depo → Settings → Secrets and variables → Actions → **Secrets**: `BUFFER_API_KEY`, `BUFFER_CHANNEL_ID`.
3. Actions sekmesinden iki workflow'u elle (Run workflow) bir kez çalıştır.

## Notlar

- Topla buluşma ve ikili mücadele ESPN'de Süper Lig için boş geliyor, kartlarda yok.
- Paylaşılan maçlar `data/state.json`, paylaşılan sezon çiftleri `data/paylasilan_sezon.json` içinde tutulur.
- Yazı tipi: Barlow (SIL Open Font License), `fonts/` içinde.
- Veri kaynağı: ESPN (resmî olmayan, herkese açık uç noktalar; kullanım koşulları değişebilir).

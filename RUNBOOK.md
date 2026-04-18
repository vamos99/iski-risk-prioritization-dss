# Runbook

Bu doküman operasyon kılavuzudur: pipeline çalıştırma sırası, beklenen çıktılar
ve üretim sonrası kontrol maddeleri burada tutulur.

## 1) Ortam
- Python 3.10+
- Bağımlılıklar: `pip install -r requirements.txt`
- Not: `scripts/reporting/generate_chapter4_assets.py` için `geopandas` gerekir; kurulu değilse harita görseli atlanır, diğer çıktılar üretilir.

## Veri Konumu Kuralı
- Ham CSV dosyaları sadece `data/bronze/` altında tutulur.
- Yardımcı mekânsal dosyalar `data/external/` ve `data/spatial/` altındadır.
- Proje kökünde geçici/tekrar eden kopya tutulmaz.

## 2) Uçtan Uca Çalıştırma
1. `python3 -m pipeline.00_data_prep`
2. `python3 -m pipeline.01_normalize_weight`
3. `python3 -m pipeline.03_04_score_cluster`  (Ar-Ge)
4. `python3 -m pipeline.05_advanced_scenarios` (Nihai)
5. `python3 scripts/reporting/generate_chapter4_assets.py`

## 2.1 Beklenen Durum Kontrolleri
- Adım 0 sonunda: `data/silver/karar_matrisi.csv` üretilmiş olmalı.
- Adım 5 sonunda: `data/gold/ileri_duzey_senaryolar_mahalle_bazli.csv` üretilmiş olmalı.
- Moran birleşik çıktı: `data/gold/morans_i_all_results.csv` içinde `ariza_2022`, `ariza_2023`, `risk_s11` satırları bulunmalı.
- Chapter4 scripti sonunda tablo dosyaları `outputs/chapter4/` altında güncel zaman damgasıyla bulunmalı.

## 3) Kritik Çıktılar
- `data/silver/karar_matrisi.csv`
- `data/gold/ileri_duzey_senaryolar_mahalle_bazli.csv`
- `data/gold/morans_i_results.csv` (arıza)
- `data/gold/morans_i_risk_results.csv` (risk_s11)
- `data/gold/morans_i_all_results.csv` (birleşik)
- `outputs/tek_dosya_degisim_notlari.txt`
- `outputs/chapter4/*.csv` ve `outputs/figures/chapter4/*.png`
  (Not: `geopandas` yoksa `risk_haritasi.png` ve `harita_join_kalite_ozeti.csv` üretilmez.)

## 4) Yorumlama Notları
- Nihai sınıflandırma K-Means değildir.
- K-Means çıktıları sadece karşılaştırma amaçlıdır.
- Tez/PDF güncellemelerinde değişiklik/uyum notları için
  `outputs/tek_dosya_degisim_notlari.txt` kullanılmalıdır.

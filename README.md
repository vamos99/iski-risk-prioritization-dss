# ISKI Risk Prioritization (KDS)

Bu proje, İstanbul mahalleleri için **AHP + Quantile + PoF/CoF** yaklaşımıyla
risk önceliklendirmesi üreten karar destek hattıdır.

## Bu Repo Ne Yapar?
- Su şebekesi bakım/yenileme önceliği için mahalle bazında risk skoru üretir.
- Nihai yaklaşım tahmin modeli değil, **karar destek önceliklendirme modeli**dir.
- Çıktılar yönetici özeti, harita, tablo, SQL view ve teknik doğrulama özetleri olarak üretilir.

## Portfolio Odağı
- Medallion yapısına yakın veri akışı: `bronze -> silver -> gold -> outputs`
- Mahalle/ilçe kırılımında açıklanabilir risk skorlama
- Streamlit üzerinde teknik olmayan okuyucuya uygun yönetici özeti
- SQLite + SQL view katmanı ile sorgulanabilir analitik çıktı
- Hafif CI ile Python compile, unit test ve SQLite build kontrolü
- Mimari ve veri akışı özeti: `docs/architecture.md`
- PoF/CoF, risk skoru ve harita join kalite sözlüğü: `docs/metrics.md`
- Ölçülen sonuçlar, risk dağılımı ve validation metrikleri: `docs/results.md`
- GitHub Issues/Projects için hafif sprint ve backlog akışı: [Live Project Board](https://github.com/users/vamos99/projects/2) / `docs/project-management.md`

## Nihai Metodoloji (Source of Truth)
- Nihai model: `pipeline/05_advanced_scenarios.py` (Senaryo 11)
- Ar-Ge karşılaştırma: `pipeline/03_04_score_cluster.py` (nihai değildir)
- Doğrulama: Moran's I (arıza_2022, arıza_2023, risk_s11)

## Aktif Giriş Noktaları
- `python3 -m pipeline.00_data_prep`
- `python3 -m pipeline.01_normalize_weight`
- `python3 -m pipeline.03_04_score_cluster`
- `python3 -m pipeline.05_advanced_scenarios`
- `python3 scripts/reporting/generate_chapter4_assets.py`
- `python3 scripts/build_analytics_sqlite.py`
- `python3 scripts/validate_pipeline_outputs.py`
- `python3 scripts/reconcile_analytics_sqlite.py`
- `streamlit run app/main.py`

## Hızlı Başlangıç
1. `python3 -m pip install -r requirements.txt`
2. `python3 -m pipeline.00_data_prep`
3. `python3 -m pipeline.01_normalize_weight`
4. `python3 -m pipeline.05_advanced_scenarios`
5. `python3 scripts/reporting/generate_chapter4_assets.py`
6. `python3 scripts/build_analytics_sqlite.py`
7. `python3 scripts/validate_pipeline_outputs.py --summary-output outputs/pipeline_run_summary.json --report-output outputs/pipeline_run_summary.md`
8. `python3 scripts/reconcile_analytics_sqlite.py --database outputs/iski_analytics.db`
9. `streamlit run app/main.py`

Detaylı, adım adım operasyon ve çıktı kontrolü için `RUNBOOK.md` dosyasına bakın.

## Dizin Yapısı (Temiz)
- `data/bronze/`: Ham veri CSV'leri (tek doğru konum)
- `data/external/`: Komşuluk ve POI yardımcı verileri
- `data/spatial/`: GeoJSON sınır dosyaları
- `data/silver/`: Adım 0/1 ara çıktıları
- `data/gold/`: Nihai model ve doğrulama çıktıları
- `outputs/`: Bölüm 4 tablo/görselleri ve tek not dosyası (`tek_dosya_degisim_notlari.txt`)
- `sql/`: SQLite view tanımları ve analitik sorgu örnekleri

Not: Proje kökünde ham CSV tutulmaz; veri dosyaları yalnızca `data/` altında tutulur.

## İsimlendirme Standardı
- Ham veri dosyaları `data/bronze/` altında ASCII + `snake_case` adlandırılır.
- Dosya adlarında Türkçe karakter, boşluk ve uzantı öncesi boşluk kullanılmaz.

## README ve RUNBOOK Farkı
- `README.md`: Projenin amacı, mimarisi ve hızlı başlangıç özeti.
- `RUNBOOK.md`: Operasyon sırasında hangi sırayla ne çalıştırılacağı, hangi çıktıların kontrol edileceği ve yorumlama notları.

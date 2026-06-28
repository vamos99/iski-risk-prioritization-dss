# Measured Results

Bu sayfa, mevcut ISKI karar destek hattının sayısal çıktılarını özetler. Proje
tahmin modeli değil, AHP + Quantile + PoF/CoF tabanlı mahalle önceliklendirme
modelidir. Değerler saha kararı veya gerçek operasyonel etki iddiası değildir;
analitik karar destek çıktısıdır.

Son ölçüm: 2026-06-28, mevcut curated CSV çıktıları.

## Pipeline Coverage

| Alan | Sonuç |
| --- | ---: |
| Mahalle sayısı | 963 |
| İlçe sayısı | 39 |
| En riskli mahalle listesi | 25 satır |
| SQLite analytics tables | 4 |
| SQLite analytics views | 3 |
| Pipeline failed checks | 0 |
| SQLite reconciliation failed checks | 0 |

Validation checks passed:

- `gold_keys_unique`: duplicate key = 0
- `city_total_matches_gold_rows`: 963 = 963
- `district_total_matches_city_total`: 963 = 963
- `district_risk_counts_match_city_total`: 963 = 963
- `top_neighborhoods_subset_of_gold`: missing key = 0
- `top_neighborhoods_sorted_by_risk`: 25 rows sorted descending

## Citywide Risk Distribution

| Risk band | Count | Share |
| --- | ---: | ---: |
| Critical / red | 176 | 18.28% |
| Medium / yellow | 356 | 36.97% |
| Low / green | 431 | 44.76% |

| Metrik | Sonuç |
| --- | ---: |
| Mean continuous risk score | 0.3073 |
| Median continuous risk score | 0.3251 |
| Min continuous risk score | 0.0311 |
| Max continuous risk score | 0.5359 |

## Highest-Risk Neighborhoods

| Rank | İlçe | Mahalle | Risk | PoF | CoF |
| ---: | --- | --- | ---: | ---: | ---: |
| 1 | ATAŞEHİR | İÇERENKÖY | 0.5359 | 0.6443 | 0.8318 |
| 2 | TUZLA | AYDINLI | 0.5168 | 0.5951 | 0.8684 |
| 3 | KÜÇÜKÇEKMECE | HALKALI MERKEZ | 0.4968 | 0.6198 | 0.8015 |
| 4 | ATAŞEHİR | KÜÇÜKBAKKALKÖY | 0.4929 | 0.6435 | 0.7660 |
| 5 | SULTANGAZİ | ESENTEPE | 0.4844 | 0.6195 | 0.7819 |
| 6 | ATAŞEHİR | MEVLANA | 0.4827 | 0.6480 | 0.7449 |
| 7 | PENDİK | SEYMEN | 0.4789 | 0.6334 | 0.7560 |
| 8 | KÜÇÜKÇEKMECE | İNÖNÜ | 0.4766 | 0.6222 | 0.7660 |
| 9 | KADIKÖY | MERDİVENKÖY | 0.4763 | 0.6577 | 0.7242 |
| 10 | EYÜPSULTAN | KARADOLAP | 0.4731 | 0.6395 | 0.7398 |

## District Concentration

Districts with the highest critical-risk share:

| İlçe | Mahalle | Critical count | Critical share |
| --- | ---: | ---: | ---: |
| SULTANGAZİ | 15 | 10 | 66.67% |
| ATAŞEHİR | 17 | 10 | 58.82% |
| GAZİOSMANPAŞA | 16 | 9 | 56.25% |
| BAĞCILAR | 22 | 11 | 50.00% |
| BAŞAKŞEHİR | 11 | 5 | 45.45% |
| KADIKÖY | 21 | 9 | 42.86% |
| AVCILAR | 10 | 4 | 40.00% |
| BEYLİKDÜZÜ | 10 | 4 | 40.00% |
| KÜÇÜKÇEKMECE | 21 | 8 | 38.10% |
| TUZLA | 17 | 6 | 35.29% |

## Spatial Validation

Moran's I results show spatial clustering rather than random spatial
dispersion.

| Metric | Moran's I | p-value | z-score | n | weights |
| --- | ---: | ---: | ---: | ---: | ---: |
| Failure count 2022 | 0.4682 | 0.002 | 24.7414 | 963 | 5,408 |
| Failure count 2023 | 0.4870 | 0.002 | 25.3195 | 963 | 5,408 |
| Scenario 11 risk | 0.6054 | 0.002 | 29.3467 | 963 | 5,556 |

Interpretation: the final risk score is spatially clustered and should be read
with neighboring-mahalle context. It is not a causal estimate of future failure.

## Data Quality And Map Join Signals

| Kontrol | Sonuç |
| --- | ---: |
| AHP PoF consistency ratio | 0.0003 |
| AHP CoF consistency ratio | 0.0003 |
| Model duplicate keys | 0 |
| Decision matrix key-year duplicates | 0 |
| Valid spatial key count | 963 |
| POI rows before filtering | 1,422 |
| POI rows after filtering | 1,417 |
| POI coverage | 99.65% |
| Neighborhood-edge rows before filtering | 5,833 |
| Neighborhood-edge rows after filtering | 5,408 |
| Neighborhood-edge coverage | 92.71% |

## Reproducibility Commands

```bash
python scripts/validate_pipeline_outputs.py \
  --summary-output outputs/pipeline_run_summary.json \
  --report-output outputs/pipeline_run_summary.md

python scripts/build_analytics_sqlite.py --output outputs/iski_analytics.db
python scripts/reconcile_analytics_sqlite.py --database outputs/iski_analytics.db
pytest -q
```

# SQL Analytics Layer

Bu klasör, Streamlit ekranındaki risk çıktılarının SQL ile de sorgulanabilir
olduğunu göstermek için eklenmiş hafif bir analitik katmandır.

## Üretim

```bash
python3 scripts/build_analytics_sqlite.py
```

Varsayılan çıktı:

```text
outputs/iski_analytics.db
```

## Kaynak Tablolar

- `gold_risk_neighborhoods`: mahalle bazlı nihai Senaryo 11 çıktısı
- `chapter4_district_risk_summary`: ilçe bazlı özet tablo
- `chapter4_city_risk_summary`: şehir geneli KPI özeti
- `chapter4_top_neighborhoods`: en riskli mahalle listesi

## View'lar

- `city_risk_summary`: şehir geneli KPI'lar
- `district_risk_summary`: ilçe bazlı kritik risk yoğunluğu
- `risk_priority_neighborhoods`: mahalle bazlı öncelik listesi ve öncelik nedeni

Örnek:

```sql
SELECT district, neighborhood, risk_score, priority_reason
FROM risk_priority_neighborhoods
WHERE priority_band = '01_critical'
ORDER BY risk_score DESC
LIMIT 10;
```

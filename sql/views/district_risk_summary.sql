DROP VIEW IF EXISTS district_risk_summary;

CREATE VIEW district_risk_summary AS
SELECT
    ilce AS district,
    mahalle_sayisi AS neighborhood_count,
    kirmizi_adet AS critical_neighborhoods,
    sari_adet AS medium_neighborhoods,
    yesil_adet AS low_neighborhoods,
    ROUND(kirmizi_oran * 100, 2) AS critical_rate_pct,
    ROUND(ortalama_surekli_risk, 4) AS average_risk_score,
    ROUND(ortalama_pof, 4) AS average_pof_score,
    ROUND(ortalama_cof, 4) AS average_cof_score
FROM chapter4_district_risk_summary;

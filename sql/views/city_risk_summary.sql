DROP VIEW IF EXISTS city_risk_summary;

CREATE VIEW city_risk_summary AS
SELECT
    toplam_mahalle AS total_neighborhoods,
    kritik_adet AS critical_neighborhoods,
    orta_adet AS medium_neighborhoods,
    dusuk_adet AS low_neighborhoods,
    ROUND(kritik_oran * 100, 2) AS critical_rate_pct,
    ROUND(ortalama_surekli_risk, 4) AS average_risk_score,
    ROUND(medyan_surekli_risk, 4) AS median_risk_score
FROM chapter4_city_risk_summary;

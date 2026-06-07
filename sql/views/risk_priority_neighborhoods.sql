DROP VIEW IF EXISTS risk_priority_neighborhoods;

CREATE VIEW risk_priority_neighborhoods AS
SELECT
    ilce AS district,
    mahalle AS neighborhood,
    anahtar AS neighborhood_key,
    S11_Risk_Seviyesi AS risk_level,
    ROUND(S11_Risk_Skoru_Surekli, 4) AS risk_score,
    ROUND(S11_PoF_Skor, 4) AS pof_score,
    ROUND(S11_CoF_Skor, 4) AS cof_score,
    CASE
        WHEN S11_Risk_Seviyesi LIKE '%Kırmızı%' THEN '01_critical'
        WHEN S11_Risk_Seviyesi LIKE '%Sarı%' THEN '02_medium'
        WHEN S11_Risk_Seviyesi LIKE '%Yeşil%' THEN '03_low'
        ELSE '99_unknown'
    END AS priority_band,
    CASE
        WHEN S11_PoF_Skor >= S11_CoF_Skor + 0.08 THEN 'Altyapı riski baskın'
        WHEN S11_CoF_Skor >= S11_PoF_Skor + 0.08 THEN 'Etki riski baskın'
        ELSE 'PoF/CoF birlikte yüksek'
    END AS priority_reason
FROM gold_risk_neighborhoods;

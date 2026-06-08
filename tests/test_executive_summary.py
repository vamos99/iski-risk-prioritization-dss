import pandas as pd

from src.analysis.executive_summary import (
    build_city_risk_summary,
    build_district_risk_summary,
    build_map_join_quality_table,
    build_top_priority_neighborhoods,
    normalize_risk_bucket,
)


def sample_risk_data() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "anahtar": "A|ONE",
                "ilce": "A",
                "mahalle": "ONE",
                "S11_Risk_Seviyesi": "Kritik Risk (Kırmızı Bölge)",
                "S11_Risk_Skoru_Surekli": 0.70,
                "S11_PoF_Skor": 0.80,
                "S11_CoF_Skor": 0.60,
            },
            {
                "anahtar": "A|TWO",
                "ilce": "A",
                "mahalle": "TWO",
                "S11_Risk_Seviyesi": "Orta Risk (Sarı Bölge)",
                "S11_Risk_Skoru_Surekli": 0.40,
                "S11_PoF_Skor": 0.40,
                "S11_CoF_Skor": 0.80,
            },
            {
                "anahtar": "B|ONE",
                "ilce": "B",
                "mahalle": "ONE",
                "S11_Risk_Seviyesi": "Düşük Risk (Yeşil Bölge)",
                "S11_Risk_Skoru_Surekli": 0.20,
                "S11_PoF_Skor": 0.30,
                "S11_CoF_Skor": 0.30,
            },
        ]
    )


def test_normalize_risk_bucket_handles_model_labels() -> None:
    assert normalize_risk_bucket("Kritik Risk (Kırmızı Bölge)") == "Kritik"
    assert normalize_risk_bucket("Orta Risk (Sarı Bölge)") == "Orta"
    assert normalize_risk_bucket("Düşük Risk (Yeşil Bölge)") == "Düşük"


def test_build_city_risk_summary_counts_buckets() -> None:
    summary = build_city_risk_summary(sample_risk_data())

    assert summary.total_neighborhoods == 3
    assert summary.critical_count == 1
    assert summary.medium_count == 1
    assert summary.low_count == 1
    assert summary.critical_ratio == 1 / 3


def test_build_district_risk_summary_sorts_by_critical_rate() -> None:
    district_summary = build_district_risk_summary(sample_risk_data())

    assert district_summary.iloc[0]["ilce"] == "A"
    assert district_summary.iloc[0]["kritik_adet"] == 1
    assert district_summary.iloc[0]["kritik_oran"] == 0.5


def test_build_top_priority_neighborhoods_adds_reason() -> None:
    top_rows = build_top_priority_neighborhoods(sample_risk_data(), limit=1)

    assert top_rows.iloc[0]["mahalle"] == "ONE"
    assert top_rows.iloc[0]["oncelik_nedeni"] == "Altyapı riski baskın"


def test_build_map_join_quality_table_formats_coverage() -> None:
    table = build_map_join_quality_table(
        {
            "both": 90,
            "left_only": 5,
            "right_only": 5,
            "both_ratio": 0.9,
            "left_only_ratio": 0.05,
            "right_only_ratio": 0.05,
            "dropped_geo_duplicates": 2,
            "filtered_geo_outside_model": 5,
        }
    )

    assert table.iloc[0]["Kontrol"] == "Eşleşen mahalle"
    assert table.iloc[0]["Adet"] == 90
    assert table.iloc[0]["Oran"] == "%90.0"
    assert table.iloc[3]["Kontrol"] == "Silinen geometri duplikasyonu"
    assert table.iloc[3]["Adet"] == 2

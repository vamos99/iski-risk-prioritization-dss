"""Executive dashboard helpers for the ISKI risk prioritization model."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


RISK_LABEL_COL = "S11_Risk_Seviyesi"
RISK_SCORE_COL = "S11_Risk_Skoru_Surekli"
POF_SCORE_COL = "S11_PoF_Skor"
COF_SCORE_COL = "S11_CoF_Skor"


@dataclass(frozen=True)
class CityRiskSummary:
    total_neighborhoods: int
    critical_count: int
    medium_count: int
    low_count: int
    critical_ratio: float
    average_risk_score: float
    median_risk_score: float
    average_pof_score: float
    average_cof_score: float


def normalize_risk_bucket(label: object) -> str:
    """Map model risk labels to stable dashboard buckets."""
    if not isinstance(label, str):
        return "Veri Yok"

    normalized = label.casefold()
    if "kırmızı" in normalized or "kritik" in normalized:
        return "Kritik"
    if "sarı" in normalized or "orta" in normalized:
        return "Orta"
    if "yeşil" in normalized or "düşük" in normalized:
        return "Düşük"
    return "Veri Yok"


def build_city_risk_summary(df: pd.DataFrame) -> CityRiskSummary:
    """Return the city-level KPIs shown at the top of the dashboard."""
    if df.empty:
        return CityRiskSummary(0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0)

    buckets = df[RISK_LABEL_COL].map(normalize_risk_bucket)
    total = len(df)
    critical_count = int((buckets == "Kritik").sum())
    medium_count = int((buckets == "Orta").sum())
    low_count = int((buckets == "Düşük").sum())

    return CityRiskSummary(
        total_neighborhoods=total,
        critical_count=critical_count,
        medium_count=medium_count,
        low_count=low_count,
        critical_ratio=critical_count / total if total else 0.0,
        average_risk_score=float(df[RISK_SCORE_COL].mean()),
        median_risk_score=float(df[RISK_SCORE_COL].median()),
        average_pof_score=float(df[POF_SCORE_COL].mean()),
        average_cof_score=float(df[COF_SCORE_COL].mean()),
    )


def build_risk_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Build a stable risk-bucket distribution table."""
    if df.empty:
        return pd.DataFrame(columns=["Risk Seviyesi", "Mahalle Sayısı"])

    bucket_order = ["Kritik", "Orta", "Düşük", "Veri Yok"]
    counts = df[RISK_LABEL_COL].map(normalize_risk_bucket).value_counts()
    rows = [
        {"Risk Seviyesi": bucket, "Mahalle Sayısı": int(counts.get(bucket, 0))}
        for bucket in bucket_order
        if counts.get(bucket, 0) > 0
    ]
    return pd.DataFrame(rows)


def build_district_risk_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate neighborhood-level risk into district-level action metrics."""
    if df.empty:
        return pd.DataFrame()

    work = df.copy()
    work["risk_bucket"] = work[RISK_LABEL_COL].map(normalize_risk_bucket)

    grouped = (
        work.groupby("ilce", dropna=False)
        .agg(
            mahalle_sayisi=("mahalle", "nunique"),
            ortalama_risk=(RISK_SCORE_COL, "mean"),
            ortalama_pof=(POF_SCORE_COL, "mean"),
            ortalama_cof=(COF_SCORE_COL, "mean"),
            kritik_adet=("risk_bucket", lambda values: int((values == "Kritik").sum())),
            orta_adet=("risk_bucket", lambda values: int((values == "Orta").sum())),
            dusuk_adet=("risk_bucket", lambda values: int((values == "Düşük").sum())),
        )
        .reset_index()
    )
    grouped["kritik_oran"] = grouped["kritik_adet"] / grouped["mahalle_sayisi"].clip(lower=1)

    return grouped.sort_values(
        ["kritik_oran", "ortalama_risk", "kritik_adet"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def build_top_priority_neighborhoods(df: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    """Return the highest-priority neighborhoods with non-technical reason labels."""
    if df.empty:
        return pd.DataFrame()

    columns = ["ilce", "mahalle", RISK_LABEL_COL, RISK_SCORE_COL, POF_SCORE_COL, COF_SCORE_COL]
    work = df[columns].copy()
    work["risk_bucket"] = work[RISK_LABEL_COL].map(normalize_risk_bucket)
    work["oncelik_nedeni"] = work.apply(_priority_reason, axis=1)

    return (
        work.sort_values([RISK_SCORE_COL, POF_SCORE_COL, COF_SCORE_COL], ascending=False)
        .head(limit)
        .reset_index(drop=True)
    )


def build_data_quality_summary(df: pd.DataFrame, join_report: dict[str, float] | None = None) -> dict[str, object]:
    """Summarize source coverage and key duplication for the dashboard footer."""
    if df.empty:
        return {
            "record_count": 0,
            "district_count": 0,
            "duplicate_key_count": 0,
            "missing_key_count": 0,
            "map_match_ratio": None,
        }

    duplicate_key_count = int(df["anahtar"].duplicated().sum()) if "anahtar" in df.columns else 0
    missing_key_count = int(df["anahtar"].isna().sum()) if "anahtar" in df.columns else 0

    return {
        "record_count": int(len(df)),
        "district_count": int(df["ilce"].nunique()) if "ilce" in df.columns else 0,
        "duplicate_key_count": duplicate_key_count,
        "missing_key_count": missing_key_count,
        "map_match_ratio": None if not join_report else join_report.get("both_ratio"),
    }


def _priority_reason(row: pd.Series) -> str:
    pof = row[POF_SCORE_COL]
    cof = row[COF_SCORE_COL]

    if pd.isna(pof) or pd.isna(cof):
        return "Eksik skor kontrolü"
    if pof >= cof + 0.08:
        return "Altyapı riski baskın"
    if cof >= pof + 0.08:
        return "Etki riski baskın"
    return "PoF/CoF birlikte yüksek"

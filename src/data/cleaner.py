"""
İSKİ Risk Önceliklendirme — Veri Temizleme Modülü.

IQR winsorization, eksik değer tamamlama ve kalite kontrolleri.
Bronze → Silver dönüşümünün temizlik katmanı.
"""

import logging

import numpy as np
import pandas as pd

from config.settings import IQR_MULTIPLIER

logger = logging.getLogger("iski.cleaner")


def winsorize_column(
    series: pd.Series,
    multiplier: float = IQR_MULTIPLIER,
) -> pd.Series:
    """Tek bir sütuna IQR tabanlı winsorization uygular.

    Üst sınır: Q3 + multiplier × IQR
    Alt sınır: Q1 - multiplier × IQR (negatif değer mantıksız ise 0'da kesilir)

    Args:
        series: Sayısal sütun.
        multiplier: IQR çarpanı (varsayılan 1.5).

    Returns:
        Winsorize edilmiş sütun.
    """
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1

    lower_bound = max(0, q1 - multiplier * iqr)
    upper_bound = q3 + multiplier * iqr

    original_outliers = ((series < lower_bound) | (series > upper_bound)).sum()
    result = series.clip(lower=lower_bound, upper=upper_bound)

    if original_outliers > 0:
        logger.info(
            "Winsorize: %s → %d aykırı değer baskılandı [%.2f, %.2f]",
            series.name, original_outliers, lower_bound, upper_bound,
        )
    return result


def winsorize_dataframe(
    df: pd.DataFrame,
    numeric_columns: list[str],
    multiplier: float = IQR_MULTIPLIER,
) -> pd.DataFrame:
    """DataFrame'deki belirtilen sayısal sütunlara winsorization uygular.

    Args:
        df: Giriş DataFrame.
        numeric_columns: Winsorize edilecek sütun isimleri.
        multiplier: IQR çarpanı.

    Returns:
        Winsorize edilmiş DataFrame (kopya).
    """
    df = df.copy()
    for col in numeric_columns:
        if col in df.columns:
            df[col] = winsorize_column(df[col], multiplier)
    return df


def impute_missing_by_district(
    df: pd.DataFrame,
    value_columns: list[str],
    district_col: str = "ilce",
) -> pd.DataFrame:
    """Eksik değerleri aynı ilçenin medyanı ile doldurur (spatial median imputation).

    Args:
        df: Giriş DataFrame.
        value_columns: Doldurulacak sütunlar.
        district_col: İlçe sütun ismi.

    Returns:
        Eksik değerleri doldurulmuş DataFrame (kopya).
    """
    df = df.copy()
    for col in value_columns:
        if col not in df.columns:
            continue
        missing_before = df[col].isna().sum()
        if missing_before == 0:
            continue

        # İlçe medyanları
        district_medians = df.groupby(district_col)[col].transform("median")
        df[col] = df[col].fillna(district_medians)

        # Hâlâ kalan NaN'lar (ilçenin tamamı NaN ise) → genel medyan
        global_median = df[col].median()
        df[col] = df[col].fillna(global_median)

        missing_after = df[col].isna().sum()
        logger.info(
            "Imputation: %s → %d NaN → %d NaN (ilçe medyanı ile dolduruldu)",
            col, missing_before, missing_after,
        )
    return df


def generate_quality_report(df: pd.DataFrame, name: str) -> dict:
    """Veri kalitesi özet raporu üretir.

    Args:
        df: İncelenecek DataFrame.
        name: Veri seti ismi (loglama için).

    Returns:
        Rapor sözlüğü: satır sayısı, sütun sayısı, eksik değer oranları,
        duplikasyon sayısı.
    """
    report = {
        "name": name,
        "rows": len(df),
        "columns": len(df.columns),
        "duplicates": df.duplicated().sum(),
        "missing": {},
    }

    for col in df.columns:
        missing_count = df[col].isna().sum()
        if missing_count > 0:
            report["missing"][col] = {
                "count": int(missing_count),
                "pct": round(missing_count / len(df) * 100, 2),
            }

    logger.info(
        "Kalite raporu [%s]: satır=%d, sütun=%d, duplikasyon=%d, eksik_sütun=%d",
        name, report["rows"], report["columns"],
        report["duplicates"], len(report["missing"]),
    )
    return report

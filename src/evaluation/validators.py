"""
İSKİ Risk Önceliklendirme — Doğrulama ve Kontrol Modülü.

Pipeline boyunca kullanılacak tüm assert'ler, sanity check'ler
ve kalite kontrolleri burada toplanmıştır.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger("iski.validators")


# ------------------------------------------------------------------
# Veri Bütünlüğü Kontrolleri
# ------------------------------------------------------------------

def validate_key_coverage(
    df: pd.DataFrame,
    reference_keys: set[str],
    df_name: str,
    key_col: str = "anahtar",
) -> dict[str, set[str]]:
    """Veri setindeki anahtarların referans setini kapsadığını kontrol eder.

    Args:
        df: Kontrol edilecek DataFrame.
        reference_keys: Beklenen anahtar seti.
        df_name: Veri seti adı (loglama için).
        key_col: Anahtar sütun ismi.

    Returns:
        {"missing": eksik anahtarlar, "extra": fazla anahtarlar}
    """
    actual_keys = set(df[key_col].unique())
    missing = reference_keys - actual_keys
    extra = actual_keys - reference_keys

    if missing:
        logger.warning("[%s] %d eksik anahtar: %s",
                       df_name, len(missing), list(missing)[:10])
    if extra:
        logger.info("[%s] %d ek anahtar (referansta yok): %s",
                    df_name, len(extra), list(extra)[:10])

    coverage = len(actual_keys & reference_keys) / max(len(reference_keys), 1)
    logger.info("[%s] Anahtar kapsam: %.1f%% (%d/%d)",
                df_name, coverage * 100, len(actual_keys & reference_keys),
                len(reference_keys))

    return {"missing": missing, "extra": extra}


def validate_no_duplicates(
    df: pd.DataFrame,
    subset: list[str],
    df_name: str,
) -> None:
    """Duplikasyon olmadığını doğrular.

    Args:
        df: Kontrol edilecek DataFrame.
        subset: Duplikasyonu kontrol edilecek sütunlar.
        df_name: Veri seti adı.

    Raises:
        AssertionError: Duplikasyon varsa.
    """
    dup_count = df.duplicated(subset=subset).sum()
    assert dup_count == 0, (
        f"[{df_name}] {dup_count} duplikasyon tespit edildi! (sütunlar: {subset})"
    )
    logger.info("[%s] Duplikasyon kontrolü geçildi ✓", df_name)


def validate_no_negative(
    df: pd.DataFrame,
    columns: list[str],
    df_name: str,
) -> None:
    """Negatif değer olmadığını doğrular.

    Args:
        df: Kontrol edilecek DataFrame.
        columns: Kontrol edilecek sütunlar.
        df_name: Veri seti adı.

    Raises:
        AssertionError: Negatif değer varsa.
    """
    for col in columns:
        if col not in df.columns:
            continue
        neg_count = (df[col] < 0).sum()
        assert neg_count == 0, (
            f"[{df_name}] {col} sütununda {neg_count} negatif değer!"
        )
    logger.info("[%s] Negatif değer kontrolü geçildi ✓", df_name)


# ------------------------------------------------------------------
# Data Leak Kontrolleri
# ------------------------------------------------------------------

def validate_no_data_leak(
    df: pd.DataFrame,
    year_col: str = "yil",
    expected_years: list[int] | None = None,
    df_name: str = "",
) -> None:
    """Yıllar arası veri sızıntısı olmadığını kontrol eder.

    Args:
        df: Kontrol edilecek DataFrame.
        year_col: Yıl sütun ismi.
        expected_years: Beklenen yıllar listesi.
        df_name: Veri seti adı.

    Raises:
        AssertionError: Beklenmeyen yıl varsa.
    """
    if expected_years is None:
        expected_years = [2022, 2023]

    actual_years = set(df[year_col].unique())
    unexpected = actual_years - set(expected_years)

    assert len(unexpected) == 0, (
        f"[{df_name}] DATA LEAK: beklenmeyen yıllar={unexpected} "
        f"(beklenen: {expected_years})"
    )
    logger.info("[%s] Data leak kontrolü geçildi ✓ (yıllar: %s)",
                df_name, sorted(actual_years))


# ------------------------------------------------------------------
# Adjacency Simetri Kontrolü
# ------------------------------------------------------------------

def validate_adjacency_symmetry(
    komsuluk_df: pd.DataFrame,
) -> int:
    """Komşuluk matrisinde simetriyi kontrol eder.

    A→B komşuysa B→A da komşu olmalı.

    Args:
        komsuluk_df: Sütunlar: anahtar, komsu_anahtar.

    Returns:
        Asimetrik çift sayısı.
    """
    forward = set(
        zip(komsuluk_df["anahtar"], komsuluk_df["komsu_anahtar"])
    )
    asymmetric = 0

    for a, b in forward:
        if (b, a) not in forward:
            asymmetric += 1

    if asymmetric == 0:
        logger.info("Komşuluk simetrisi doğrulandı ✓")
    else:
        logger.warning(
            "Komşuluk simetrisi UYARISI: %d asimetrik çift (A→B var, B→A yok)",
            asymmetric,
        )
    return asymmetric


# ------------------------------------------------------------------
# Spatial Lag Yıl-Tutarlılık Kontrolü
# ------------------------------------------------------------------

def validate_spatial_lag_year_variation(
    df: pd.DataFrame,
    key_col: str = "anahtar",
    year_col: str = "yil",
    lag_col: str = "komsu_ort_ariza",
    atol: float = 1e-10,
) -> float:
    """Spatial lag değişkeninin yıllar arasında tamamen sabit kalmadığını kontrol eder.

    Eğer tüm anahtarlar için lag değeri tüm yıllarda birebir aynıysa, bu genellikle
    yıl-duyarsız eşleme kaynaklı leakage/hesap hatasına işaret eder.

    Returns:
        same_ratio: Yıllar boyunca değişmeyen anahtar oranı.
    """
    required = {key_col, year_col, lag_col}
    if not required.issubset(df.columns):
        logger.warning(
            "Spatial lag yıl kontrolü atlandı: eksik sütun(lar) %s",
            sorted(required - set(df.columns)),
        )
        return 0.0

    pivot = df.pivot_table(index=key_col, columns=year_col, values=lag_col, aggfunc="first")
    if pivot.shape[1] < 2:
        logger.warning("Spatial lag yıl kontrolü atlandı: tek yıl bulundu.")
        return 0.0

    per_key_range = (pivot.max(axis=1) - pivot.min(axis=1)).fillna(0.0)
    same_mask = np.isclose(per_key_range.values, 0.0, atol=atol)
    same_ratio = float(same_mask.mean())

    assert not bool(same_mask.all()), (
        f"Spatial lag yıl kontrolü başarısız: {lag_col} tüm anahtarlarda yıllar boyunca aynı."
    )

    logger.info(
        "Spatial lag yıl fark kontrolü: değişmeyen oran=%.2f%% (hedef < 100%%) ✓",
        same_ratio * 100,
    )
    return same_ratio


# ------------------------------------------------------------------
# Sanity Check: Bilinen Kritik İlçeler
# ------------------------------------------------------------------

KNOWN_HIGH_RISK_DISTRICTS = [
    "ESENYURT", "BAĞCILAR", "ESENLER", "KÜÇÜKÇEKMECE",
    "SULTANGAZI", "GAZİOSMANPAŞA", "BAŞAKŞEHİR",
]

KNOWN_LOW_RISK_DISTRICTS = [
    "ADALAR", "BEYKOZ", "ÇATALCA", "SİLİVRİ", "ŞILE",
]


def sanity_check_districts(
    df: pd.DataFrame,
    risk_score_col: str = "risk_skoru",
    district_col: str = "ilce",
) -> dict[str, float]:
    """Bilinen kritik/güvenli ilçelerin risk sıralamasını kontrol eder.

    Args:
        df: Risk skorlu DataFrame.
        risk_score_col: Risk skoru sütunu.
        district_col: İlçe sütunu.

    Returns:
        İlçe ortalama risk skorları.
    """
    district_avg = df.groupby(district_col)[risk_score_col].mean().sort_values(
        ascending=False
    )

    top_10 = district_avg.head(10).index.tolist()
    bottom_5 = district_avg.tail(5).index.tolist()

    # Bilinen yüksek riskli ilçelerin üst yarıda olması beklenir
    found_high = [d for d in KNOWN_HIGH_RISK_DISTRICTS if d in top_10]
    found_low = [d for d in KNOWN_LOW_RISK_DISTRICTS if d in bottom_5]

    logger.info(
        "Sanity check — Top 10 ilçe: %s", top_10
    )
    logger.info(
        "Sanity check — Bottom 5 ilçe: %s", bottom_5
    )
    logger.info(
        "Bilinen riskli ilçe eşleşmesi: %d/%d (%s)",
        len(found_high), len(KNOWN_HIGH_RISK_DISTRICTS), found_high,
    )
    logger.info(
        "Bilinen güvenli ilçe eşleşmesi: %d/%d (%s)",
        len(found_low), len(KNOWN_LOW_RISK_DISTRICTS), found_low,
    )

    return district_avg.to_dict()

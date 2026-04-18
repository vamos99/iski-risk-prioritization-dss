"""
İSKİ Risk Önceliklendirme — Feature Engineering Modülü.

Mevcut verilerden türetilmiş değişkenler üretir.
Üç kategori: operasyonel, mekânsal (spatial lag), kurumsal (POI).

PDF Referans: Yeni ekleme (KARAR-004, KARAR-005)
"""

import logging

import numpy as np
import pandas as pd

from config.settings import EPSILON, CORRELATION_THRESHOLD

logger = logging.getLogger("iski.feature_engineer")


# ------------------------------------------------------------------
# Operasyonel Türev Değişkenler
# ------------------------------------------------------------------

def create_operational_features(df: pd.DataFrame) -> pd.DataFrame:
    """Mevcut operasyonel verilerden türetilmiş değişkenler üretir.

    Gerekli sütunlar: gelen_ariza, nufus, tuketim_dasimetrik,
                      gelen_sikayet, kesinti_toplam_saat, kesinti_adet

    Args:
        df: Birleştirilmiş karar matrisi.

    Returns:
        Türetilmiş sütunlar eklenmiş DataFrame (kopya).
    """
    df = df.copy()

    # Arıza yoğunluğu (kişi başı arıza × 1000)
    df["ariza_yogunlugu"] = np.where(
        df["nufus"] > 0,
        df["gelen_ariza"] / df["nufus"] * 1000,
        0,
    )

    # Boru stres endeksi (arıza × kişi başı tüketim)
    df["nufus_basi_tuketim"] = np.where(
        df["nufus"] > 0,
        df["tuketim_dasimetrik"] / df["nufus"],
        0,
    )
    df["boru_stres_endeksi"] = df["gelen_ariza"] * df["nufus_basi_tuketim"]

    # Şikayet / arıza oranı
    df["sikayet_ariza_orani"] = np.where(
        df["gelen_ariza"] > EPSILON,
        df["gelen_sikayet"] / df["gelen_ariza"],
        0,
    )

    # Ortalama kesinti süresi (saat/adet)
    df["ort_kesinti_suresi"] = np.where(
        df["kesinti_adet"] > 0,
        df["kesinti_toplam_saat"] / df["kesinti_adet"],
        0,
    )

    logger.info("Operasyonel türev değişkenler üretildi: 5 yeni sütun")
    return df


def create_trend_features(
    df_current: pd.DataFrame,
    df_previous: pd.DataFrame,
) -> pd.DataFrame:
    """Yıllar arası arıza trendi hesaplar.

    Args:
        df_current: Mevcut yıl verisi (2023).
        df_previous: Önceki yıl verisi (2022).

    Returns:
        df_current kopyası + ariza_trend sütunu.
    """
    df = df_current.copy()

    prev = df_previous[["anahtar", "gelen_ariza"]].rename(
        columns={"gelen_ariza": "ariza_onceki_yil"}
    )
    df = df.merge(prev, on="anahtar", how="left")

    df["ariza_trend"] = np.where(
        df["ariza_onceki_yil"] > EPSILON,
        (df["gelen_ariza"] - df["ariza_onceki_yil"]) / df["ariza_onceki_yil"],
        0,
    )

    df = df.drop(columns=["ariza_onceki_yil"])
    logger.info("Arıza trendi hesaplandı (2023 vs 2022)")
    return df


# ------------------------------------------------------------------
# Mekânsal (Spatial Lag) Değişkenler
# ------------------------------------------------------------------

def create_spatial_lag_features(
    df: pd.DataFrame,
    komsuluk_df: pd.DataFrame,
    value_column: str = "gelen_ariza",
) -> pd.DataFrame:
    """Komşu mahalle ortalamasını spatial lag olarak hesaplar.

    Args:
        df: Ana veri (anahtar, value_column sütunları gerekli).
        komsuluk_df: Komşuluk çiftleri (anahtar, komsu_anahtar).
        value_column: Ortalaması alınacak sütun.

    Returns:
        df kopyası + komsu_ort_{value_column} ve komsu_sayisi sütunları.
    """
    df = df.copy()

    # Yıl-duyarlı komşu eşlemesi:
    # Komşuluk tablosu yıllık değilse her yıla çoğaltılır.
    if "yil" not in df.columns:
        raise ValueError("Spatial lag için df içinde 'yil' sütunu zorunludur.")

    neighbor_pairs = komsuluk_df[["anahtar", "komsu_anahtar"]].drop_duplicates().copy()
    years = (
        df["yil"].dropna().astype(int).drop_duplicates().sort_values().to_frame(name="yil")
    )
    neighbor_pairs["__k__"] = 1
    years["__k__"] = 1
    neighbor_pairs = neighbor_pairs.merge(years, on="__k__", how="inner").drop(columns="__k__")

    neighbor_values = neighbor_pairs.merge(
        df[["anahtar", "yil", value_column]],
        left_on=["komsu_anahtar", "yil"],
        right_on=["anahtar", "yil"],
        how="left",
        suffixes=("", "_komsu"),
    )

    # Komşu ortalaması ve sayısı (anahtar + yıl)
    agg = (
        neighbor_values.groupby(["anahtar", "yil"], as_index=False)
        .agg(komsu_ort=(value_column, "mean"), komsu_sayisi=(value_column, "count"))
        .rename(columns={"komsu_ort": f"komsu_ort_{value_column}"})
    )

    df = df.merge(agg, on=["anahtar", "yil"], how="left")

    # Komşuluk verisi olmayan veya komşusu veride bulunmayan (farklı il) mahalleler
    # Bunların komsu_ortalaması NaN olacaktır ve eskiden 0'a atanıyordu (haksız ceza/ödül).
    # Yeni mantık: Eğer komşu ortalaması hesaplanamadıysa, o ilçe-yıl ortalamasını kullan.
    target_col = f"komsu_ort_{value_column}"
    missing_mask = df[target_col].isna()
    if missing_mask.any():
        ilce_ort = df.groupby(["ilce", "yil"])[value_column].transform("mean")
        df[target_col] = df[target_col].fillna(ilce_ort)

        # Eğer ilçe-yıl ortalaması da NaN ise (örneğin o kırılımda hiç veri yoksa), 0 yap.
        df[target_col] = df[target_col].fillna(0)

        logger.info(
            "Eksik komşu verisi olan %d kayıt için İlçe-Yıl ortalaması fallback uygulandı.",
            missing_mask.sum()
        )

    df["komsu_sayisi"] = df["komsu_sayisi"].fillna(0).astype(int)

    logger.info(
        "Spatial lag hesaplandı: %s → komşu ortalaması", value_column
    )
    return df


# ------------------------------------------------------------------
# Korelasyon Filtresi
# ------------------------------------------------------------------

def check_multicollinearity(
    df: pd.DataFrame,
    feature_columns: list[str],
    threshold: float = CORRELATION_THRESHOLD,
) -> tuple[pd.DataFrame, list[str]]:
    """Yüksek korelasyonlu feature çiftlerini tespit eder.

    Args:
        df: Veri seti.
        feature_columns: Kontrol edilecek sütunlar.
        threshold: Korelasyon eşiği (varsayılan 0.85).

    Returns:
        (korelasyon_matrisi, yüksek_korelasyon_uyarıları) tuple'ı.
    """
    corr_matrix = df[feature_columns].corr(method="spearman")

    warnings_list: list[str] = []
    checked: set[tuple[str, str]] = set()

    for i, col_a in enumerate(feature_columns):
        for j, col_b in enumerate(feature_columns):
            if i >= j:
                continue
            pair = (col_a, col_b)
            if pair in checked:
                continue
            checked.add(pair)

            r = abs(corr_matrix.loc[col_a, col_b])
            if r > threshold:
                msg = f"YÜKSEK KORELASYON: {col_a} ↔ {col_b} = {r:.3f} (eşik: {threshold})"
                warnings_list.append(msg)
                logger.warning(msg)

    if not warnings_list:
        logger.info(
            "Multicollinearity kontrolü geçildi: tüm çiftler |r| < %.2f",
            threshold,
        )

    return corr_matrix, warnings_list

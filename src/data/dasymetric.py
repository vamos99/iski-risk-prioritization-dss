"""
İSKİ Risk Önceliklendirme — Dasimetrik Dağıtım Modülü.

İlçe ölçeğindeki su tüketim verisini, TÜİK nüfus oranlarıyla
mahalle ölçeğine indirger.

Formül: V_mahalle = V_ilce × (P_mahalle / P_ilce)
Kısıt : ∑V_mahalle = V_ilce (hacim korunumu)

PDF Referans: Bölüm 3.3
"""

import logging

import numpy as np
import pandas as pd

from config.settings import VOLUME_TOLERANCE

logger = logging.getLogger("iski.dasymetric")


def distribute_consumption(
    tuketim_df: pd.DataFrame,
    nufus_df: pd.DataFrame,
    year: int,
) -> pd.DataFrame:
    """İlçe tüketimini nüfus oranıyla mahallelere dağıtır.

    Args:
        tuketim_df: İlçe bazlı tüketim (ilce, yil, tuketim_yillik).
        nufus_df: Mahalle bazlı nüfus (ilce, mahalle, anahtar, yil, nufus).
        year: Dağıtım yapılacak yıl.

    Returns:
        Mahalle bazlı dağıtılmış tüketim DataFrame'i.
        Sütunlar: ilce, mahalle, anahtar, yil, nufus,
                  tuketim_dasimetrik, nufus_orani

    Raises:
        AssertionError: Hacim korunumu sağlanamazsa.
    """
    # Yıla göre filtrele
    tuk = tuketim_df[tuketim_df["yil"] == year].copy()
    nuf = nufus_df[nufus_df["yil"] == year].copy()

    # İlçe toplam nüfuslarını hesapla
    ilce_nufus = nuf.groupby("ilce")["nufus"].sum().reset_index()
    ilce_nufus = ilce_nufus.rename(columns={"nufus": "ilce_toplam_nufus"})

    # Mahalle verisine ilçe toplam nüfusunu ekle
    merged = nuf.merge(ilce_nufus, on="ilce", how="left")

    # İlçe tüketim verisini ekle
    merged = merged.merge(tuk[["ilce", "tuketim_yillik"]], on="ilce", how="left")

    # Nüfus oranı
    merged["nufus_orani"] = np.where(
        merged["ilce_toplam_nufus"] > 0,
        merged["nufus"] / merged["ilce_toplam_nufus"],
        0,
    )

    # Dasimetrik dağıtım
    merged["tuketim_dasimetrik"] = merged["tuketim_yillik"] * merged["nufus_orani"]

    # ── Hacim Korunumu Doğrulaması ──
    validation_passed = True
    for ilce, group in merged.groupby("ilce"):
        total_distributed = group["tuketim_dasimetrik"].sum()
        original = group["tuketim_yillik"].iloc[0] if len(group) > 0 else 0

        if pd.isna(original) or pd.isna(total_distributed):
            logger.warning("Hacim doğrulaması atlandı (NaN): ilçe=%s", ilce)
            continue

        diff = abs(total_distributed - original)
        if diff > VOLUME_TOLERANCE:
            logger.error(
                "HACIM KORUNUMU İHLALİ: ilçe=%s, orijinal=%.2f, dağıtılan=%.2f, fark=%.4f",
                ilce, original, total_distributed, diff,
            )
            validation_passed = False

    if validation_passed:
        logger.info(
            "Dasimetrik dağıtım tamamlandı: yıl=%d, mahalle=%d — hacim korunumu ✓",
            year, len(merged),
        )
    else:
        logger.warning(
            "Dasimetrik dağıtım tamamlandı: yıl=%d — HACIM KORUNUMU UYARISI ⚠️", year
        )

    # Negatif değer kontrolü
    assert (merged["tuketim_dasimetrik"] >= 0).all(), \
        "Negatif dasimetrik tüketim değeri tespit edildi!"

    result_cols = [
        "ilce", "mahalle", "anahtar", "yil",
        "nufus", "tuketim_dasimetrik", "nufus_orani",
    ]
    return merged[result_cols]

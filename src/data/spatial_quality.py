"""
İSKİ Risk Önceliklendirme — Mekânsal Veri Kalite Katmanı.

POI ve komşuluk verilerini canonical (geçerli) mahalle anahtarlarıyla
hizalar; İstanbul dışı / model dışı kayıtları filtreler ve rapor üretir.
"""

import logging

import pandas as pd

logger = logging.getLogger("iski.spatial_quality")


def clean_external_spatial_inputs(
    poi_df: pd.DataFrame,
    komsuluk_df: pd.DataFrame,
    valid_keys: set[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """POI ve komşuluk tablolarını canonical mahalle anahtarlarıyla temizler.

    Args:
        poi_df: POI tablosu (anahtar, yil ve tesis sütunları beklenir).
        komsuluk_df: Komşuluk tablosu (anahtar, komsu_anahtar).
        valid_keys: Nüfus/karar matrisi iskeletinden gelen geçerli anahtar seti.

    Returns:
        (poi_temiz, komsuluk_temiz, kalite_raporu_df)
    """
    poi = poi_df.copy()
    kom = komsuluk_df.copy()

    # ---------- POI temizliği ----------
    poi_before = len(poi)
    poi_outside = (~poi["anahtar"].isin(valid_keys)).sum()
    poi = poi[poi["anahtar"].isin(valid_keys)].copy()

    group_cols = [c for c in ["ilce", "mahalle", "anahtar", "yil"] if c in poi.columns]
    numeric_cols = [c for c in poi.columns if c not in group_cols and pd.api.types.is_numeric_dtype(poi[c])]
    if group_cols and numeric_cols:
        poi = poi.groupby(group_cols, as_index=False)[numeric_cols].sum()

    poi_after = len(poi)

    # ---------- Komşuluk temizliği ----------
    kom_before = len(kom)
    mask_source_valid = kom["anahtar"].isin(valid_keys)
    mask_neighbor_valid = kom["komsu_anahtar"].isin(valid_keys)

    kom_outside_source = (~mask_source_valid).sum()
    kom_outside_neighbor = (~mask_neighbor_valid).sum()

    kom = kom[mask_source_valid & mask_neighbor_valid].copy()
    kom = kom[kom["anahtar"] != kom["komsu_anahtar"]].drop_duplicates()
    kom_after = len(kom)

    report = pd.DataFrame(
        [
            {
                "valid_key_count": len(valid_keys),
                "poi_rows_before": poi_before,
                "poi_rows_after": poi_after,
                "poi_rows_outside_keys": int(poi_outside),
                "poi_coverage_pct": round((poi_after / max(poi_before, 1)) * 100, 2),
                "komsuluk_rows_before": kom_before,
                "komsuluk_rows_after": kom_after,
                "komsuluk_outside_source": int(kom_outside_source),
                "komsuluk_outside_neighbor": int(kom_outside_neighbor),
                "komsuluk_coverage_pct": round((kom_after / max(kom_before, 1)) * 100, 2),
            }
        ]
    )

    logger.info(
        "Mekânsal kalite temizliği tamamlandı | POI: %d→%d, Komşuluk: %d→%d",
        poi_before,
        poi_after,
        kom_before,
        kom_after,
    )

    return poi, kom, report


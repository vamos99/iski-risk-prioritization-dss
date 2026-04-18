"""
İSKİ Risk Önceliklendirme — Veri Yükleme Modülü.

Ham CSV ve GeoJSON dosyalarını Bronze katmanından yükler.
Veri içeriğini değiştirmez, yalnızca yapısal standardizasyon yapar.

Her CSV dosyası farklı sütun isimlerine sahip olabileceğinden, loader
fonksiyonları esnek sütun eşleştirmesi yapar.
"""

import json
import logging
from pathlib import Path

import pandas as pd

from src.utils.naming import (
    create_composite_key,
    standardize_district_name,
    standardize_neighborhood_name,
)

logger = logging.getLogger("iski.loader")


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Verilen DataFrame'de ilk eşleşen sütun ismini bulur.

    Args:
        df: DataFrame.
        candidates: Olası sütun isimleri (büyük/küçük harf duyarsız).

    Returns:
        Eşleşen sütun ismi veya None.
    """
    col_upper = {c.upper().strip(): c for c in df.columns}
    for candidate in candidates:
        if candidate.upper().strip() in col_upper:
            return col_upper[candidate.upper().strip()]
    return None


# ------------------------------------------------------------------
# CSV Yükleyiciler
# ------------------------------------------------------------------

def load_ariza(filepath: Path, year: int) -> pd.DataFrame:
    """Mahalle bazlı su arıza CSV'sini yükler.

    2022 ve 2023 dosyaları farklı sütun isimleri kullanıyor:
      2022: 'Cevaplanan Ariza'
      2023: 'Giderilen Ariza'

    Args:
        filepath: CSV dosya yolu.
        year: Veri yılı (2022 veya 2023).

    Returns:
        Sütunlar: ilce, mahalle, anahtar, yil, gelen_ariza, cevaplanan_ariza
    """
    df = pd.read_csv(filepath, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()

    # Esnek sütun eşleştirmesi
    ilce_col = _find_column(df, ["Ilce", "ILCE", "İlçe", "İLÇE"])
    mahalle_col = _find_column(df, ["Mahalle", "MAHALLE", "MAHALLE_ADI"])
    gelen_col = _find_column(df, ["Gelen Ariza", "GELEN ARIZA", "Gelen_Ariza"])
    cevap_col = _find_column(df, ["Cevaplanan Ariza", "Giderilen Ariza",
                                   "CEVAPLANAN ARIZA", "GIDERILEN ARIZA"])

    rename_map = {}
    if ilce_col: rename_map[ilce_col] = "ilce_raw"
    if mahalle_col: rename_map[mahalle_col] = "mahalle_raw"
    if gelen_col: rename_map[gelen_col] = "gelen_ariza"
    if cevap_col: rename_map[cevap_col] = "cevaplanan_ariza"

    df = df.rename(columns=rename_map)

    # Sayısal dönüşüm
    for col in ["gelen_ariza", "cevaplanan_ariza"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if "mahalle_raw" in df.columns:
        df["mahalle_raw"] = df["mahalle_raw"].astype(str).str.split(",")
        df = df.explode("mahalle_raw")
        df["mahalle_raw"] = df["mahalle_raw"].str.strip()

    df["ilce"] = df["ilce_raw"].apply(standardize_district_name)
    df["mahalle"] = df["mahalle_raw"].apply(standardize_neighborhood_name)
    df["anahtar"] = df.apply(
        lambda r: create_composite_key(r["ilce_raw"], r["mahalle_raw"]), axis=1
    )
    df["yil"] = year

    cols = ["ilce", "mahalle", "anahtar", "yil", "gelen_ariza", "cevaplanan_ariza"]
    result = df[[c for c in cols if c in df.columns]]
    logger.info("Arıza verisi yüklendi: yıl=%d, satır=%d, sütunlar=%s",
                year, len(result), list(result.columns))
    return result


def load_tuketim(filepath: Path, year: int) -> pd.DataFrame:
    """İlçe bazlı su tüketim CSV'sini yükler.

    2015-2022: sütunlar '2022 (Tuketim-m3)' formatında
    2023: sütunlar '202301.0', '202302.0' ... formatında

    Args:
        filepath: CSV dosya yolu.
        year: Veri yılı.

    Returns:
        Sütunlar: ilce, yil, tuketim_yillik
    """
    df = pd.read_csv(filepath, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()

    ilce_col = _find_column(df, ["Ilce", "ILCE", "ILCELER", "İLCELER", "İlçe"])
    if ilce_col is None:
        raise ValueError(f"İlçe sütunu bulunamadı: {list(df.columns)}")
    df = df.rename(columns={ilce_col: "ilce_raw"})

    # Sayısal sütunları bul
    non_data_cols = {"_id", "ilce_raw", ilce_col}
    numeric_cols = [c for c in df.columns if c not in non_data_cols]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Yıla ait sütunları filtrele
    year_cols = [c for c in numeric_cols if str(year) in str(c)]
    if not year_cols:
        year_cols = numeric_cols

    df["tuketim_yillik"] = df[year_cols].sum(axis=1)
    df["ilce"] = df["ilce_raw"].apply(standardize_district_name)
    df["yil"] = year

    result = df[["ilce", "yil", "tuketim_yillik"]].copy()
    logger.info("Tüketim verisi yüklendi: yıl=%d, ilçe=%d, toplam=%s",
                year, len(result), f"{result['tuketim_yillik'].sum():,.0f}")
    return result


def load_sikayet(filepath: Path, year: int) -> pd.DataFrame:
    """Mahalle bazlı susuzluk şikayet CSV'sini yükler.

    2022: 'Ilce', 'Mahalle', 'Gelen Cagri Sayisi', 'Cevaplanan Cagri Sayisi'
    2023: 'ILCE', 'MAHALLE_ADI', 'GELEN ARIZA', 'GIDERILEN ARIZA'

    Args:
        filepath: CSV dosya yolu.
        year: Veri yılı.

    Returns:
        Sütunlar: ilce, mahalle, anahtar, yil, gelen_sikayet, cevaplanan_sikayet
    """
    df = pd.read_csv(filepath, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()

    # Esnek sütun eşleştirmesi
    ilce_col = _find_column(df, ["Ilce", "ILCE", "İlçe"])
    mahalle_col = _find_column(df, ["Mahalle", "MAHALLE", "MAHALLE_ADI"])
    gelen_col = _find_column(df, ["Gelen Cagri Sayisi", "GELEN ARIZA",
                                   "GELEN CAGRI SAYISI", "Gelen Ariza"])
    cevap_col = _find_column(df, ["Cevaplanan Cagri Sayisi", "GIDERILEN ARIZA",
                                   "CEVAPLANAN CAGRI SAYISI", "Giderilen Ariza"])

    rename_map = {}
    if ilce_col: rename_map[ilce_col] = "ilce_raw"
    if mahalle_col: rename_map[mahalle_col] = "mahalle_raw"
    if gelen_col: rename_map[gelen_col] = "gelen_sikayet"
    if cevap_col: rename_map[cevap_col] = "cevaplanan_sikayet"

    df = df.rename(columns=rename_map)

    for col in ["gelen_sikayet", "cevaplanan_sikayet"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if "mahalle_raw" in df.columns:
        df["mahalle_raw"] = df["mahalle_raw"].astype(str).str.split(",")
        df = df.explode("mahalle_raw")
        df["mahalle_raw"] = df["mahalle_raw"].str.strip()

    df["ilce"] = df["ilce_raw"].apply(standardize_district_name)
    df["mahalle"] = df["mahalle_raw"].apply(standardize_neighborhood_name)
    df["anahtar"] = df.apply(
        lambda r: create_composite_key(r["ilce_raw"], r["mahalle_raw"]), axis=1
    )
    df["yil"] = year

    cols = ["ilce", "mahalle", "anahtar", "yil", "gelen_sikayet", "cevaplanan_sikayet"]
    result = df[[c for c in cols if c in df.columns]]
    logger.info("Şikayet verisi yüklendi: yıl=%d, satır=%d", year, len(result))
    return result


def load_kesinti(filepath: Path) -> pd.DataFrame:
    """Su kesinti olayları CSV'sini yükler.

    İki farklı dosya formatı var:
      2022-2023: SAAT_FARK, DAKIKA_FARK sütunları mevcut
      2023-2024: Sadece tarih sütunları var, süre hesaplanmalı

    Args:
        filepath: CSV dosya yolu.

    Returns:
        Sütunlar: ilce, mahalle, anahtar, yil, kesinti_saat
    """
    df = pd.read_csv(filepath, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()

    ilce_col = _find_column(df, ["ILCE", "Ilce"])
    mahalle_col = _find_column(df, ["MAHALLE", "Mahalle"])
    baslangic_col = _find_column(df, ["BASLANGIC", "ARIZA KESINTI TARIHI"])
    bitis_col = _find_column(df, ["BITIS", "ARIZA BITIS TARIHI"])
    saat_col = _find_column(df, ["SAAT_FARK"])
    dakika_col = _find_column(df, ["DAKIKA_FARK"])

    if ilce_col: df = df.rename(columns={ilce_col: "ilce_raw"})
    if mahalle_col: df = df.rename(columns={mahalle_col: "mahalle_raw"})
    if baslangic_col: df = df.rename(columns={baslangic_col: "baslangic"})
    if bitis_col: df = df.rename(columns={bitis_col: "bitis"})

    # Yıl çıkarımı
    df["baslangic_dt"] = pd.to_datetime(df["baslangic"], errors="coerce")
    df["yil"] = df["baslangic_dt"].dt.year

    # Sadece analiz yıllarını tut
    df = df[df["yil"].isin([2022, 2023])].copy()

    if not len(df):
        logger.warning("Kesinti dosyasında 2022-2023 verisi yok: %s", filepath.name)
        return pd.DataFrame(columns=["ilce", "mahalle", "anahtar", "yil", "kesinti_saat"])

    # Kesinti süresini hesapla
    if saat_col and dakika_col:
        # Format 1: SAAT_FARK + DAKIKA_FARK mevcut
        df["saat_fark"] = pd.to_numeric(df[saat_col], errors="coerce").fillna(0)
        df["dak_fark"] = pd.to_numeric(df[dakika_col], errors="coerce").fillna(0)
        df["kesinti_saat"] = df["saat_fark"] + df["dak_fark"] / 60.0
    else:
        # Format 2: Tarihlerden hesapla
        df["bitis_dt"] = pd.to_datetime(df["bitis"], errors="coerce")
        df["kesinti_saat"] = (df["bitis_dt"] - df["baslangic_dt"]).dt.total_seconds() / 3600.0
        df["kesinti_saat"] = df["kesinti_saat"].fillna(0).clip(lower=0)

    # Çoklu mahalle virgüllü kayıtları çöz (explode) - Örn: "Mah1, Mah2" -> Row1(Mah1), Row2(Mah2)
    if "mahalle_raw" in df.columns:
        df["mahalle_raw"] = df["mahalle_raw"].astype(str).str.split(",")
        df = df.explode("mahalle_raw")
        df["mahalle_raw"] = df["mahalle_raw"].str.strip()

    df["ilce"] = df["ilce_raw"].apply(standardize_district_name)
    df["mahalle"] = df["mahalle_raw"].apply(standardize_neighborhood_name)
    df["anahtar"] = df.apply(
        lambda r: create_composite_key(r["ilce_raw"], r["mahalle_raw"]), axis=1
    )

    cols = ["ilce", "mahalle", "anahtar", "yil", "kesinti_saat"]
    logger.info("Kesinti verisi yüklendi: %s, satır=%d", filepath.name, len(df))
    return df[cols]


def load_nufus(filepath: Path) -> pd.DataFrame:
    """TÜİK mahalle nüfus CSV'sini yükler.

    Wide formatı (NUFUS_2022, NUFUS_2023) long formata çevirir.

    Args:
        filepath: CSV dosya yolu.

    Returns:
        Sütunlar: ilce, mahalle, anahtar, yil, nufus
    """
    df = pd.read_csv(filepath, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()

    df = df.rename(columns={
        "ILCE": "ilce_raw",
        "MAHALLE": "mahalle_raw",
        "NUFUS_2022": "nufus_2022",
        "NUFUS_2023": "nufus_2023",
    })

    # Nüfus sayısal dönüşümü
    for col in ["nufus_2022", "nufus_2023"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["ilce"] = df["ilce_raw"].apply(standardize_district_name)
    df["mahalle"] = df["mahalle_raw"].apply(standardize_neighborhood_name)
    df["anahtar"] = df.apply(
        lambda r: create_composite_key(r["ilce_raw"], r["mahalle_raw"]), axis=1
    )

    # Wide → Long (pd.melt kullanarak daha verimli)
    id_cols = ["ilce", "mahalle", "anahtar"]
    melted = df[id_cols + ["nufus_2022", "nufus_2023"]].melt(
        id_vars=id_cols,
        value_vars=["nufus_2022", "nufus_2023"],
        var_name="yil_raw",
        value_name="nufus",
    )
    melted["yil"] = melted["yil_raw"].str.extract(r"(\d{4})").astype(int)
    melted = melted.drop(columns=["yil_raw"])

    logger.info("Nüfus verisi yüklendi: satır=%d", len(melted))
    return melted


def load_poi(filepath: Path) -> pd.DataFrame:
    """POI (Point of Interest) istatistik CSV'sini yükler.

    Long formattan mahalle × tesis_türü pivot'a çevirir.

    Args:
        filepath: CSV dosya yolu.

    Returns:
        Sütunlar: ilce, mahalle, anahtar, yil,
                  egitim_tesisi_sayisi, sanayi_tesis_sayisi
    """
    df = pd.read_csv(filepath, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()

    df["ilce"] = df["ilce"].apply(standardize_district_name)
    df["mahalle"] = df["mahalle"].apply(standardize_neighborhood_name)
    df["anahtar"] = df.apply(
        lambda r: create_composite_key(r["ilce"], r["mahalle"]), axis=1
    )
    df["yil"] = df["yil"].astype(int)

    # Pivot: tesis_turu → sütunlar
    pivot = df.pivot_table(
        index=["ilce", "mahalle", "anahtar", "yil"],
        columns="tesis_turu",
        values="tesis_sayisi",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()

    pivot.columns.name = None

    # Sütun isimlerini standardize et
    col_map = {}
    for col in pivot.columns:
        col_lower = str(col).lower()
        if "eğitim" in col_lower or "egitim" in col_lower:
            col_map[col] = "egitim_tesisi_sayisi"
        elif "sanayi" in col_lower or "fabrika" in col_lower:
            col_map[col] = "sanayi_tesis_sayisi"
    pivot = pivot.rename(columns=col_map)

    logger.info("POI verisi yüklendi: satır=%d", len(pivot))
    return pivot


def load_komsuluk(filepath: Path) -> pd.DataFrame:
    """Mahalle komşuluk CSV'sini yükler ve standardize eder.

    Args:
        filepath: CSV dosya yolu.

    Returns:
        Sütunlar: anahtar, komsu_anahtar
    """
    df = pd.read_csv(filepath, encoding="utf-8-sig")
    df.columns = df.columns.str.strip()

    df["anahtar"] = df.apply(
        lambda r: create_composite_key(r["ilce"], r["mahalle"]), axis=1
    )
    df["komsu_anahtar"] = df.apply(
        lambda r: create_composite_key(
            r["komsu_mahalle_ilcesi"], r["komsu_mahalle"]
        ),
        axis=1,
    )

    result = df[["anahtar", "komsu_anahtar"]].drop_duplicates()
    logger.info("Komşuluk verisi yüklendi: çift=%d", len(result))
    return result


def load_geojson(filepath: Path) -> dict:
    """GeoJSON dosyasını yükler.

    Args:
        filepath: GeoJSON dosya yolu.

    Returns:
        GeoJSON dict nesnesi.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info("GeoJSON yüklendi: %s, feature=%d",
                filepath.name, len(data["features"]))
    return data

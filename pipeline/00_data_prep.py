"""
İSKİ Risk Önceliklendirme — Adım 0: Veri Hazırlık Pipeline'ı.

Bronze → Silver → Karar Matrisi akışı:
  1. Ham verileri yükle (Bronze)
  2. Temizle (IQR winsorization, eksik değer tamamlama)
  3. Dasimetrik dağıtım (ilçe tüketim → mahalle)
  4. Kesinti verisi aggregasyonu (event → mahalle-yıl toplamları)
  5. Tüm veri setlerini birleştir (mahalle × yıl karar matrisi)
  6. Feature engineering (operasyonel türevler + spatial lag)
  7. POI verisi entegrasyonu
  8. Korelasyon kontrolü
  9. Silver ve Gold çıktıları kaydet

Kullanım:
    python -m pipeline.00_data_prep
"""

import sys
from pathlib import Path

# Proje kökünü Python path'e ekle
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np

from config.settings import (
    ANALYSIS_YEARS,
    BASE_FEATURES,
    BRONZE_DIR,
    CORRELATION_THRESHOLD,
    DERIVED_FEATURES,
    GOLD_DIR,
    POI_FEATURES,
    RAW_FILES,
    SILVER_DIR,
    SPATIAL_FILES,
    SPATIAL_FEATURES,
)
from src.data.loader import (
    load_ariza,
    load_kesinti,
    load_komsuluk,
    load_nufus,
    load_poi,
    load_sikayet,
    load_tuketim,
)
from src.data.cleaner import (
    generate_quality_report,
    impute_missing_by_district,
    winsorize_dataframe,
)
from src.data.dasymetric import distribute_consumption
from src.data.feature_engineer import (
    check_multicollinearity,
    create_operational_features,
    create_spatial_lag_features,
    create_trend_features,
)
from src.data.spatial_quality import clean_external_spatial_inputs
from src.analysis.spatial import build_adjacency_dict, calculate_morans_i
from src.evaluation.validators import (
    validate_adjacency_symmetry,
    validate_key_coverage,
    validate_no_data_leak,
    validate_no_duplicates,
    validate_no_negative,
    validate_spatial_lag_year_variation,
)
from src.utils.logging_config import setup_logger

logger = setup_logger("iski.pipeline.00")


# ==================================================================
# ADIM 0.1: BRONZE — HAM VERİ YÜKLEME
# ==================================================================

def step_01_load_bronze() -> dict[str, pd.DataFrame]:
    """Tüm ham veri kaynaklarını yükler ve temel doğrulama yapar."""
    logger.info("=" * 60)
    logger.info("ADIM 0.1: Bronze — Ham Veri Yükleme")
    logger.info("=" * 60)

    data = {}

    # Arıza verileri
    data["ariza_2022"] = load_ariza(BRONZE_DIR / RAW_FILES["ariza_2022"], 2022)
    data["ariza_2023"] = load_ariza(BRONZE_DIR / RAW_FILES["ariza_2023"], 2023)

    # Tüketim verileri
    data["tuketim_2022"] = load_tuketim(BRONZE_DIR / RAW_FILES["tuketim_2022"], 2022)
    data["tuketim_2023"] = load_tuketim(BRONZE_DIR / RAW_FILES["tuketim_2023"], 2023)

    # Şikayet verileri
    data["sikayet_2022"] = load_sikayet(BRONZE_DIR / RAW_FILES["sikayet_2022"], 2022)
    data["sikayet_2023"] = load_sikayet(BRONZE_DIR / RAW_FILES["sikayet_2023"], 2023)

    # Kesinti verileri (birden fazla dosyadan)
    kesinti_1 = load_kesinti(BRONZE_DIR / RAW_FILES["kesinti_2022_2023"])
    kesinti_2 = load_kesinti(BRONZE_DIR / RAW_FILES["kesinti_2023_2024"])
    data["kesinti_raw"] = pd.concat([kesinti_1, kesinti_2], ignore_index=True)
    # Duplikasyonları temizle (aynı olay iki dosyada da olabilir)
    data["kesinti_raw"] = data["kesinti_raw"].drop_duplicates()

    # Nüfus verisi
    data["nufus"] = load_nufus(BRONZE_DIR / RAW_FILES["nufus"])

    # POI verisi
    data["poi"] = load_poi(SPATIAL_FILES["poi_istatistik"])

    # Komşuluk verisi
    data["komsuluk"] = load_komsuluk(SPATIAL_FILES["mahalle_komsuluklari"])

    # Mekânsal kalite katmanı (canonical key kontrolü)
    valid_keys = set(data["nufus"]["anahtar"].unique())
    data["poi"], data["komsuluk"], data["spatial_quality_report"] = clean_external_spatial_inputs(
        data["poi"],
        data["komsuluk"],
        valid_keys,
    )

    # Kapsama kontrolleri
    validate_key_coverage(data["poi"], valid_keys, "poi", key_col="anahtar")
    validate_key_coverage(data["komsuluk"], valid_keys, "komsuluk", key_col="anahtar")

    # ── Kalite Raporları ──
    for name, df in data.items():
        generate_quality_report(df, name)

    # ── Data leak kontrolü ──
    for name in ["ariza_2022", "ariza_2023", "sikayet_2022", "sikayet_2023"]:
        year = int(name.split("_")[1])
        validate_no_data_leak(data[name], expected_years=[year], df_name=name)

    # ── Komşuluk simetrisi ──
    validate_adjacency_symmetry(data["komsuluk"])

    logger.info("Bronze yükleme tamamlandı: %d veri seti", len(data))
    return data


# ==================================================================
# ADIM 0.2: SILVER — TEMİZLİK
# ==================================================================

def step_02_clean(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """IQR winsorization ve eksik değer tamamlama uygular."""
    logger.info("=" * 60)
    logger.info("ADIM 0.2: Silver — Temizlik")
    logger.info("=" * 60)

    # Arıza — winsorize
    ariza_all = pd.concat([data["ariza_2022"], data["ariza_2023"]], ignore_index=True)
    # Eksplode edilen virgüllü veriler nedeniyle aynı mahallenin birden fazla satırı olabilir, topla
    ariza_all = ariza_all.groupby(["ilce", "mahalle", "anahtar", "yil"]).sum(numeric_only=True).reset_index()
    ariza_all = winsorize_dataframe(ariza_all, ["gelen_ariza", "cevaplanan_ariza"])
    ariza_all = impute_missing_by_district(ariza_all, ["gelen_ariza", "cevaplanan_ariza"])
    data["ariza_clean"] = ariza_all

    # Şikayet — winsorize
    sikayet_all = pd.concat([data["sikayet_2022"], data["sikayet_2023"]], ignore_index=True)
    # Eksplode edilen virgüllü veriler nedeniyle aynı mahallenin birden fazla satırı olabilir, topla
    sikayet_all = sikayet_all.groupby(["ilce", "mahalle", "anahtar", "yil"]).sum(numeric_only=True).reset_index()
    sikayet_all = winsorize_dataframe(sikayet_all, ["gelen_sikayet", "cevaplanan_sikayet"])
    sikayet_all = impute_missing_by_district(sikayet_all, ["gelen_sikayet", "cevaplanan_sikayet"])
    data["sikayet_clean"] = sikayet_all

    # Nüfus — impute
    nufus = impute_missing_by_district(data["nufus"], ["nufus"])
    validate_no_negative(nufus, ["nufus"], "nufus")
    data["nufus_clean"] = nufus

    # Tüketim — birleştir
    tuketim_all = pd.concat([data["tuketim_2022"], data["tuketim_2023"]], ignore_index=True)
    data["tuketim_clean"] = tuketim_all

    logger.info("Temizlik tamamlandı")
    return data


# ==================================================================
# ADIM 0.3: DASİMETRİK DAĞITIM
# ==================================================================

def step_03_dasymetric(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """İlçe tüketimini nüfus oranıyla mahallelere dağıtır."""
    logger.info("=" * 60)
    logger.info("ADIM 0.3: Dasimetrik Dağıtım")
    logger.info("=" * 60)

    results = []
    for year in ANALYSIS_YEARS:
        distributed = distribute_consumption(
            data["tuketim_clean"],
            data["nufus_clean"],
            year,
        )
        results.append(distributed)

    data["dasimetrik"] = pd.concat(results, ignore_index=True)
    logger.info("Dasimetrik dağıtım çıktısı: %d satır", len(data["dasimetrik"]))
    return data


# ==================================================================
# ADIM 0.4: KESİNTİ AGGREGASYONU
# ==================================================================

def step_04_aggregate_kesinti(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Olay bazlı kesinti verisini mahalle × yıl toplamlarına dönüştürür."""
    logger.info("=" * 60)
    logger.info("ADIM 0.4: Kesinti Aggregasyonu")
    logger.info("=" * 60)

    kesinti = data["kesinti_raw"].copy()

    # Sadece analiz yıllarını tut
    kesinti = kesinti[kesinti["yil"].isin(ANALYSIS_YEARS)]

    # Mahalle × yıl toplam ve adet
    agg = kesinti.groupby(["ilce", "mahalle", "anahtar", "yil"]).agg(
        kesinti_toplam_saat=("kesinti_saat", "sum"),
        kesinti_adet=("kesinti_saat", "count"),
    ).reset_index()

    agg = winsorize_dataframe(agg, ["kesinti_toplam_saat"])
    data["kesinti_clean"] = agg

    logger.info("Kesinti aggregasyonu: %d mahalle×yıl satırı", len(agg))
    return data


# ==================================================================
# ADIM 0.5: BİRLEŞTİRME — KARAR MATRİSİ
# ==================================================================

def step_05_merge(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Tüm veri setlerini mahalle × yıl karar matrisine birleştirir."""
    logger.info("=" * 60)
    logger.info("ADIM 0.5: Birleştirme — Karar Matrisi")
    logger.info("=" * 60)

    # Dasimetrik (ana iskelet: ilce, mahalle, anahtar, yil, nufus, tuketim)
    matrix = data["dasimetrik"].copy()

    # Arıza
    ariza = data["ariza_clean"][["anahtar", "yil", "gelen_ariza", "cevaplanan_ariza"]]
    matrix = matrix.merge(ariza, on=["anahtar", "yil"], how="left")

    # Şikayet
    sikayet = data["sikayet_clean"][["anahtar", "yil", "gelen_sikayet", "cevaplanan_sikayet"]]
    matrix = matrix.merge(sikayet, on=["anahtar", "yil"], how="left")

    # Kesinti
    kesinti = data["kesinti_clean"][["anahtar", "yil", "kesinti_toplam_saat", "kesinti_adet"]]
    matrix = matrix.merge(kesinti, on=["anahtar", "yil"], how="left")

    # POI
    poi_cols = ["anahtar", "yil"]
    if "egitim_tesisi_sayisi" in data["poi"].columns:
        poi_cols.append("egitim_tesisi_sayisi")
    if "sanayi_tesis_sayisi" in data["poi"].columns:
        poi_cols.append("sanayi_tesis_sayisi")
    poi = data["poi"][[c for c in poi_cols if c in data["poi"].columns]]
    matrix = matrix.merge(poi, on=["anahtar", "yil"], how="left")

    # NaN doldurma — merge sonrası left join'den kalan NaN'lar
    fill_cols = [
        "gelen_ariza", "cevaplanan_ariza",
        "gelen_sikayet", "cevaplanan_sikayet",
        "kesinti_toplam_saat", "kesinti_adet",
    ]
    for col in fill_cols:
        if col in matrix.columns:
            matrix[col] = matrix[col].fillna(0)

    # POI NaN → 0 (POI verisi olmayan mahallede tesis yok)
    for col in ["egitim_tesisi_sayisi", "sanayi_tesis_sayisi"]:
        if col in matrix.columns:
            matrix[col] = matrix[col].fillna(0)

    # Duplikasyon kontrolü
    validate_no_duplicates(matrix, ["anahtar", "yil"], "karar_matrisi")

    logger.info("Karar matrisi: %d satır × %d sütun", matrix.shape[0], matrix.shape[1])
    logger.info("Sütunlar: %s", list(matrix.columns))
    return matrix


# ==================================================================
# ADIM 0.6: FEATURE ENGINEERING
# ==================================================================

def step_06_feature_engineering(
    matrix: pd.DataFrame,
    komsuluk_df: pd.DataFrame,
) -> pd.DataFrame:
    """Operasyonel türevler, spatial lag ve trend hesaplar."""
    logger.info("=" * 60)
    logger.info("ADIM 0.6: Feature Engineering")
    logger.info("=" * 60)

    # Operasyonel türevler
    matrix = create_operational_features(matrix)

    # Spatial lag (arıza)
    matrix = create_spatial_lag_features(matrix, komsuluk_df, "gelen_ariza")

    # Yıllar arası trend: sadece 2023 için hesaplanabilir
    mask_2023 = matrix["yil"] == 2023
    mask_2022 = matrix["yil"] == 2022

    if mask_2023.any() and mask_2022.any():
        df_2023 = matrix[mask_2023].copy()
        df_2022 = matrix[mask_2022].copy()
        df_2023 = create_trend_features(df_2023, df_2022)

        # 2022 yılı için trend = 0 (önceki yıl verisi yok)
        df_2022 = matrix[mask_2022].copy()
        df_2022["ariza_trend"] = 0.0

        matrix = pd.concat([df_2022, df_2023], ignore_index=True)

    logger.info("Feature engineering sonrası: %d sütun", len(matrix.columns))
    return matrix


# ==================================================================
# ADIM 0.7: KALİTE KONTROL & KORELASYON
# ==================================================================

def step_07_quality_checks(matrix: pd.DataFrame) -> pd.DataFrame:
    """Final kalite kontrolleri ve korelasyon analizi."""
    logger.info("=" * 60)
    logger.info("ADIM 0.7: Kalite Kontrol & Korelasyon")
    logger.info("=" * 60)

    # Negatif değer kontrolü
    numeric_cols = matrix.select_dtypes(include=[np.number]).columns.tolist()
    # Trend negatif olabilir, onu hariç tut
    non_negative_cols = [c for c in numeric_cols if c not in ["ariza_trend", "nufus_orani"]]
    validate_no_negative(matrix, non_negative_cols, "karar_matrisi")

    # Korelasyon kontrolü
    feature_cols = [c for c in BASE_FEATURES + DERIVED_FEATURES + POI_FEATURES + SPATIAL_FEATURES
                    if c in matrix.columns]

    # Sütun isim eşleme (loader isimleri vs settings isimleri)
    rename_map = {
        "gelen_ariza": "ariza_sayisi",
        "tuketim_dasimetrik": "tuketim_dasimetrik",
        "kesinti_toplam_saat": "kesinti_suresi_saat",
        "gelen_sikayet": "sikayet_sayisi",
        "komsu_ort_gelen_ariza": "komsu_ort_ariza",
    }
    matrix = matrix.rename(columns=rename_map)

    feature_cols = [c for c in BASE_FEATURES + DERIVED_FEATURES + POI_FEATURES + SPATIAL_FEATURES
                    if c in matrix.columns]

    if len(feature_cols) >= 2:
        corr_matrix, warnings = check_multicollinearity(
            matrix, feature_cols, CORRELATION_THRESHOLD
        )
        # Korelasyon matrisini kaydet
        corr_matrix.to_csv(SILVER_DIR / "korelasyon_matrisi.csv")
        logger.info("Korelasyon matrisi kaydedildi: %s", SILVER_DIR / "korelasyon_matrisi.csv")

        if warnings:
            logger.warning("⚠️ %d yüksek korelasyon uyarısı — inceleme gerekli", len(warnings))
    else:
        logger.warning("Korelasyon kontrolü atlandı: yeterli feature yok (%d)", len(feature_cols))

    # Leakage odaklı kontrol: spatial lag yıl kırılımında tamamen sabit olmamalı
    validate_spatial_lag_year_variation(
        matrix,
        key_col="anahtar",
        year_col="yil",
        lag_col="komsu_ort_ariza",
    )

    return matrix


# ==================================================================
# ADIM 0.8: MORAN'S I TESTİ
# ==================================================================

def step_08_morans_i(matrix: pd.DataFrame, komsuluk_df: pd.DataFrame) -> dict:
    """Mekânsal otokorelasyon testini çalıştırır."""
    logger.info("=" * 60)
    logger.info("ADIM 0.8: Moran's I Testi")
    logger.info("=" * 60)

    adj_dict = build_adjacency_dict(komsuluk_df)

    results = {}

    # Arıza sayısı için test (her yıl ayrı)
    for year in ANALYSIS_YEARS:
        year_data = matrix[matrix["yil"] == year]
        if "ariza_sayisi" in year_data.columns and len(year_data) > 0:
            moran = calculate_morans_i(
                year_data["ariza_sayisi"],
                year_data["anahtar"],
                adj_dict,
            )
            results[f"ariza_{year}"] = moran

    return results


# ==================================================================
# ADIM 0.9: KAYDETME
# ==================================================================

def step_09_save(
    matrix: pd.DataFrame,
    moran_results: dict[str, dict],
    spatial_quality_report: pd.DataFrame | None = None,
) -> None:
    """Silver ve Gold çıktılarını kaydeder."""
    logger.info("=" * 60)
    logger.info("ADIM 0.9: Kaydetme")
    logger.info("=" * 60)

    # Silver — karar matrisi
    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    matrix.to_csv(SILVER_DIR / "karar_matrisi.csv", index=False, encoding="utf-8-sig")
    logger.info("Karar matrisi kaydedildi: %s (%d satır × %d sütun)",
                SILVER_DIR / "karar_matrisi.csv", matrix.shape[0], matrix.shape[1])

    # Silver — Moran's I sonuçları
    if moran_results:
        moran_df = pd.DataFrame(
            [{"metric_key": key, **values} for key, values in moran_results.items()]
        )
        moran_path = SILVER_DIR / "morans_i_results.csv"
        moran_df.to_csv(moran_path, index=False, encoding="utf-8-sig")
        logger.info("Moran's I sonuçları kaydedildi: %s (%d satır)", moran_path, len(moran_df))
        moran_gold_path = GOLD_DIR / "morans_i_results.csv"
        moran_df.to_csv(moran_gold_path, index=False, encoding="utf-8-sig")
        logger.info("Moran's I sonuçları (gold) kaydedildi: %s", moran_gold_path)

    # Silver — mekânsal kalite raporu
    if spatial_quality_report is not None and not spatial_quality_report.empty:
        spatial_quality_path = SILVER_DIR / "spatial_quality_report.csv"
        spatial_quality_report.to_csv(spatial_quality_path, index=False, encoding="utf-8-sig")
        logger.info(
            "Mekânsal kalite raporu kaydedildi: %s (%d satır)",
            spatial_quality_path,
            len(spatial_quality_report),
        )

    # Özet istatistikler
    desc = matrix.describe()
    desc.to_csv(SILVER_DIR / "ozet_istatistik.csv", encoding="utf-8-sig")
    logger.info("Özet istatistikler kaydedildi")


# ==================================================================
# ANA ÇALIŞTIRICI
# ==================================================================

def main() -> None:
    """Adım 0 pipeline'ını sırayla çalıştırır."""
    logger.info("╔══════════════════════════════════════════════╗")
    logger.info("║  İSKİ Risk Önceliklendirme — Adım 0         ║")
    logger.info("║  Veri Hazırlık Pipeline'ı                    ║")
    logger.info("╚══════════════════════════════════════════════╝")

    # Dizinleri oluştur
    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    GOLD_DIR.mkdir(parents=True, exist_ok=True)

    # Pipeline adımları
    data = step_01_load_bronze()
    data = step_02_clean(data)
    data = step_03_dasymetric(data)
    data = step_04_aggregate_kesinti(data)
    matrix = step_05_merge(data)
    matrix = step_06_feature_engineering(matrix, data["komsuluk"])
    matrix = step_07_quality_checks(matrix)

    # Moran's I
    moran_results = step_08_morans_i(matrix, data["komsuluk"])
    for key, result in moran_results.items():
        logger.info(
            "Moran's I [%s]: I=%.4f, p=%.4f, z=%.3f",
            key,
            result["morans_i"],
            result.get("p_value", 1.0),
            result.get("z_score", 0.0),
        )

    # Kaydet
    step_09_save(matrix, moran_results, data.get("spatial_quality_report"))

    logger.info("═" * 60)
    logger.info("ADIM 0 TAMAMLANDI ✓")
    logger.info("Karar matrisi: %d mahalle × %d feature", matrix.shape[0], matrix.shape[1])
    logger.info("Kullanılabilir feature'lar: %s",
                [c for c in matrix.columns if c not in ["ilce", "mahalle", "anahtar", "yil"]])
    logger.info("═" * 60)

    return matrix


if __name__ == "__main__":
    main()

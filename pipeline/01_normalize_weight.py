"""
İSKİ Risk Önceliklendirme — Adım 1 & 2: Normalizasyon ve Ağırlıklandırma.

Track A (PDF Metodolojisi): Min-Max Normalizasyon + Shannon Entropi Ağırlıklandırması
Track B (Alternatif Yöntem): Log+Robust Normalizasyon + CRITIC Ağırlıklandırması

Veri sızıntısını ve multicollinearity'yi önlemek için, korelasyonu çok yüksek olan
bazı türev değişkenler (tuketim_dasimetrik, boru_stres_endeksi) analiz dışında bırakılır.
"""

import json
import sys
from pathlib import Path

# Proje kökünü Python path'e ekle
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from config.settings import (
    BASE_FEATURES,
    DERIVED_FEATURES,
    FEATURE_SETS,
    GOLD_DIR,
    POI_FEATURES,
    SILVER_DIR,
    SPATIAL_FEATURES,
)
from src.analysis.normalizer import (
    MinMaxNormalizer,
    RobustLogNormalizer,
    compute_skewness_report,
)
from src.analysis.weighter import CRITICWeighter, ShannonEntropyWeighter
from src.utils.logging_config import setup_logger

logger = setup_logger("iski.pipeline.01_02")


def get_active_features() -> list[str]:
    """Sızıntı ve yüksek korelasyon yapan değişkenleri filtreleyerek aktif seti döndürür."""
    all_features = set(
        BASE_FEATURES + DERIVED_FEATURES + POI_FEATURES + SPATIAL_FEATURES
    )

    # 1. tuketim_dasimetrik: Nüfus ile r=0.977 (dağıtım formülünden dolayı sızıntı)
    # 2. boru_stres_endeksi: Arıza sayısı ile r=0.969
    # 3. komsu_ort_risk: Henüz mevcut değil (adım 3'ten sonra hesaplanabilir)
    dropped = {"tuketim_dasimetrik", "boru_stres_endeksi", "komsu_ort_risk"}

    active = [f for f in all_features if f not in dropped]
    active.sort()
    
    logger.info("Aktif değişken seti belirlendi (%d adet): %s", len(active), active)
    return active


def main():
    logger.info("╔══════════════════════════════════════════════╗")
    logger.info("║  İSKİ Risk Önceliklendirme — Adım 1 & 2     ║")
    logger.info("║  Normalizasyon ve Ağırlıklandırma            ║")
    logger.info("╚══════════════════════════════════════════════╝")

    # 1. Veriyi Yükle
    matrix_path = SILVER_DIR / "karar_matrisi.csv"
    if not matrix_path.exists():
        logger.error("HATA: %s bulunamadı. Önce 00_data_prep.py çalıştırın.", matrix_path)
        sys.exit(1)

    df = pd.read_csv(matrix_path, encoding="utf-8-sig")
    logger.info("Karar matrisi yüklendi: %d mahalle×yıl", len(df))

    features = get_active_features()
    
    # Bazı feature'lar (ariza_trend) negatif olabilir, log dönüşümü için offset ekleyelim
    # Veya arıza trendini analiz dışında bırakalım/ayrı işleyelim
    # Log1p için x >= -1 olması gerekir, negatif değerler varsa MinMax (0-1 arasına çekme)
    # Tüm değerleri mutlak pozitif alana taşımak mantıklı olabilir.
    
    # Adım 1: NORMALİZASYON (A ve B)
    # Ağırlık hesaplarken sıfıra bölmeyi engellemek için tüm özelliklerde
    # eksik/hatalı sütunları filtrele
    valid_features = [f for f in features if f in df.columns]
    if not valid_features:
        logger.error("HATA: Aktif feature bulunamadı.")
        sys.exit(1)

    # Pre-normalizasyon veri kalite kontrolleri
    pre_na_total = int(df[valid_features].isna().sum().sum())
    if pre_na_total > 0:
        logger.error("HATA: Normalizasyon öncesi feature setinde %d adet NaN tespit edildi.", pre_na_total)
        sys.exit(1)
    
    # Negatifleri (örneğin ariza_trend) 0'ın üstüne ötele (sadece normalizasyon öncesi)
    df_pre_norm = df.copy()
    for col in valid_features:
        min_val = df_pre_norm[col].min()
        if min_val < 0:
            df_pre_norm[col] = df_pre_norm[col] - min_val

    # Log/MinMax öncesi negatif olmamalı
    neg_count = int((df_pre_norm[valid_features] < 0).sum().sum())
    if neg_count > 0:
        logger.error("HATA: Offset sonrası %d negatif değer kaldı.", neg_count)
        sys.exit(1)

    # Track A: Min-Max
    norm_A = MinMaxNormalizer().transform(df_pre_norm, valid_features)
    
    # Track B: Log + Robust (sıfırdan küçük olmaması için log1p)
    norm_B = RobustLogNormalizer().transform(df_pre_norm, valid_features)

    # Post-normalizasyon NaN kontrolü
    post_na_a = int(norm_A[valid_features].isna().sum().sum())
    post_na_b = int(norm_B[valid_features].isna().sum().sum())
    if post_na_a > 0 or post_na_b > 0:
        logger.error(
            "HATA: Normalizasyon sonrası NaN bulundu (A=%d, B=%d).",
            post_na_a,
            post_na_b,
        )
        sys.exit(1)

    # Skewness raporu (simetri karşılaştırması)
    skew_A = compute_skewness_report(norm_A, valid_features, label="MinMax (Track A)")
    skew_B = compute_skewness_report(norm_B, valid_features, label="Log+Robust (Track B)")
    
    skew_report = pd.concat([skew_A, skew_B], ignore_index=True)
    skew_report.to_csv(SILVER_DIR / "skewness_report.csv", index=False)
    logger.info("Çarpıklık (skewness) raporu kaydedildi.")

    # Adım 2: AĞIRLIKLANDIRMA (A ve B)
    
    # Tüm veriler üzerinden genel ağırlık çıkarılabilir, veya yıla göre ayrı ayrı.
    # Kararlılık için tüm matrix üzerinden ağırlıkları hesaplıyoruz.
    
    # Track A: Shannon Entropy
    weights_shannon = ShannonEntropyWeighter().calculate_weights(norm_A, valid_features)
    
    # Track B: CRITIC
    weights_critic = CRITICWeighter().calculate_weights(norm_B, valid_features)

    # DataFrame'leri kaydet
    norm_A.to_csv(SILVER_DIR / "norm_A_minmax.csv", index=False, encoding="utf-8-sig")
    norm_B.to_csv(SILVER_DIR / "norm_B_logrobust.csv", index=False, encoding="utf-8-sig")
    
    # Ağırlıkları JSON ve CSV olarak kaydet
    weights_dict = {
        "shannon_A": weights_shannon,
        "critic_B": weights_critic
    }
    
    with open(GOLD_DIR / "weights.json", "w", encoding="utf-8") as f:
        json.dump(weights_dict, f, indent=4, ensure_ascii=False)
        
    weights_df = pd.DataFrame([
        {"feature": k, "shannon_weight": weights_shannon[k], "critic_weight": weights_critic[k]}
        for k in valid_features
    ]).sort_values("shannon_weight", ascending=False)
    
    weights_df.to_csv(GOLD_DIR / "weights_comparison.csv", index=False)
    
    logger.info("═" * 60)
    logger.info("ADIM 1 & 2 TAMAMLANDI ✓")
    logger.info("Track A (Min-Max) ve Track B (Log+Robust) matrisleri üretildi.")
    logger.info("Ağırlıklar hesaplanıp %s klasörüne kaydedildi.", GOLD_DIR.name)
    logger.info("Top 3 Shannon Kriteri: %s", weights_df.head(3)["feature"].tolist())
    logger.info("Top 3 CRITIC Kriteri: %s", weights_df.sort_values("critic_weight", ascending=False).head(3)["feature"].tolist())
    logger.info("═" * 60)

if __name__ == "__main__":
    main()

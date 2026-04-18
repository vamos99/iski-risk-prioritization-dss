"""
İSKİ Risk Önceliklendirme — Adım 3 & 4: Ar-Ge Senaryo Karşılaştırma Hattı.

Bu dosya nihai sınıflandırma motoru değildir.
Amaç, farklı skor/kümeleme konfigürasyonlarını Ar-Ge amaçlı karşılaştırmaktır.

Nihai üretim metodolojisi:
  Adım 5'teki Senaryo 11 (AHP + Quantile + PoF/CoF matrisi).
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
    GOLD_DIR,
    POI_FEATURES,
    SILVER_DIR,
    SPATIAL_FEATURES,
)
from src.analysis.clusterer import (
    find_optimal_k,
    label_clusters_by_risk,
    run_kmeans,
    test_cluster_stability,
)
from src.analysis.scorer import MultiplicativeScorer, TOPSISScorer, WLCScorer
from src.utils.logging_config import setup_logger

logger = setup_logger("iski.pipeline.03_04")


def load_settings() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Gerekli verileri (matris, norm A/B, ağırlıklar) yükler."""
    raw = pd.read_csv(SILVER_DIR / "karar_matrisi.csv", encoding="utf-8-sig")
    norm_A = pd.read_csv(SILVER_DIR / "norm_A_minmax.csv", encoding="utf-8-sig")
    norm_B = pd.read_csv(SILVER_DIR / "norm_B_logrobust.csv", encoding="utf-8-sig")

    with open(GOLD_DIR / "weights.json", "r", encoding="utf-8") as f:
        weights = json.load(f)

    return raw, norm_A, norm_B, weights


def get_feature_subset(set_type: str, all_active: list[str]) -> list[str]:
    """İstenen konfigürasyona uygun feature listesini döndürür."""
    if set_type == "temel":
        features = BASE_FEATURES
    elif set_type == "temel_turev_poi":
        features = BASE_FEATURES + DERIVED_FEATURES + POI_FEATURES
    elif set_type == "full_spatial":
        features = BASE_FEATURES + DERIVED_FEATURES + POI_FEATURES + SPATIAL_FEATURES
    else:
        raise ValueError(f"Bilinmeyen feature set: {set_type}")

    # Aktif olanları (korelasyon nedeniyle elenmeyenleri) filtrele
    return sorted([f for f in features if f in all_active])


def run_scenario(
    scenario_id: int,
    name: str,
    raw_df: pd.DataFrame,
    norm_df: pd.DataFrame,
    weights_dict: dict[str, float],
    features: list[str],
    scorer_type: str,
    cluster_dim: str,
) -> dict:
    """Tek bir Ar-Ge konfigürasyonunu çalıştırır ve karşılaştırma metriklerini üretir."""
    logger.info("--- [Ar-Ge] Senaryo %d: %s ---", scenario_id, name)
    logger.info("Yöntem: %s Skor | %s Kümeleme | %d Feature", scorer_type, cluster_dim, len(features))

    # 1. BİLEŞİK SKOR HESAPLAMA
    if scorer_type == "WLC":
        scorer = WLCScorer()
    elif scorer_type == "Multi":
        scorer = MultiplicativeScorer()
    elif scorer_type == "TOPSIS":
        scorer = TOPSISScorer()
    else:
        raise ValueError(f"Bilinmeyen scorer: {scorer_type}")

    # Skor hesapla (sadece seçili özelliklerin ağırlıklarını dahil et)
    subset_weights = {f: weights_dict.get(f, 0.0) for f in features}
    
    # Ağırlıkları 1'e tamamla (alt küme seçtiysek)
    total_w = sum(subset_weights.values())
    if total_w > 0:
        subset_weights = {k: v / total_w for k, v in subset_weights.items()}

    scores = scorer.score(norm_df, features, subset_weights)

    # 2. KÜMELEME GİRDİSİ (1D veya nD)
    if cluster_dim == "1D":
        X = scores.values
    elif cluster_dim == "nD":
        # Ağırlıklandırılmış normalize matris
        weighted_df = norm_df[features].copy()
        for f in features:
            weighted_df[f] = weighted_df[f] * subset_weights[f]
        X = weighted_df.values
    else:
        raise ValueError(f"Bilinmeyen kümeleme boyutu: {cluster_dim}")

    # 3. OPTİMAL K BULMA & KÜMELEME
    # Tüm senaryoları k=3 sabitleyelim (karşılaştırılabilirlik için, veya ayrı ayrı bulalım)
    # Performans için doğrudan k=3 kullanıyoruz (Düşük/Orta/Yüksek klasik risk)
    # Ancak pipeline'ın find_optimal_k fonksiyonunu da kaydedelim.
    k_metrics = find_optimal_k(X)
    
    # Pratik Karşılaştırma için k=3, k=4 ve k=5 silhouette skorlarına bakalım
    sil_3 = k_metrics[k_metrics["k"] == 3]["silhouette"].values[0]
    
    # En iyi k'yı bul (Silhouette'e göre)
    best_k = k_metrics.sort_values("silhouette", ascending=False).iloc[0]["k"]
    best_k_sil = k_metrics.sort_values("silhouette", ascending=False).iloc[0]["silhouette"]
    
    logger.info("Optimal k: %d (Silhouette: %.4f) | k=3 için Silhouette: %.4f", best_k, best_k_sil, sil_3)

    # Karşılaştırılabilirlik için tüm modeller k=3 (Düşük, Orta, Yüksek) üzerinden değerlendirilecek
    # İSKİ'nin iş gereksinimlerine uyması için 3'lü kategorizasyon genelde istenir
    target_k = 3
    labels, _ = run_kmeans(X, k=target_k)

    # 4. ETİKETLEME
    temp_df = pd.DataFrame({"risk_skoru": scores})
    labeled_df = label_clusters_by_risk(temp_df, labels, "risk_skoru")

    # Kümelerin dağılımı
    dist = labeled_df["kume_etiket"].value_counts().to_dict()

    # Çıktı paketi
    return {
        "id": scenario_id,
        "name": name,
        "scorer": scorer_type,
        "cluster_dim": cluster_dim,
        "features": len(features),
        "sil_score_k3": round(float(sil_3), 4),
        "best_k": int(best_k),
        "best_sil_score": round(float(best_k_sil), 4),
        "cluster_distribution": dist,
        "scores": scores,               # Final CSV için
        "labels": labeled_df["kume_etiket"] # Final CSV için
    }


def main():
    logger.info("╔══════════════════════════════════════════════╗")
    logger.info("║  İSKİ Risk Önceliklendirme — Adım 3 & 4     ║")
    logger.info("║  Ar-Ge Skor/Kümeleme Karşılaştırması         ║")
    logger.info("╚══════════════════════════════════════════════╝")
    logger.info(
        "Not: Bu adım Ar-Ge/karşılaştırma içindir. Nihai risk sınıflandırması Adım 5 Senaryo 11'de üretilir."
    )

    raw, norm_A, norm_B, weights = load_settings()
    all_active = norm_A.columns.tolist()

    shannon = weights["shannon_A"]
    critic = weights["critic_B"]

    # Senaryo Tanımları (Ar-Ge karşılaştırma seti)
    # [Norm, Ağırlık, Skor, KümeDim, FeatureSet, Name]
    scenarios = [
        (norm_A, shannon, "WLC",    "1D", "temel",              "PDF Orijinal Yöntem (Kapsamlı)"),
        (norm_A, shannon, "WLC",    "1D", "temel_turev_poi",    "Orijinal Yöntem + Yeni Özellikler"),
        (norm_A, critic,  "WLC",    "1D", "temel_turev_poi",    "CRITIC Ağırlık + Özellikler"),
        (norm_A, shannon, "Multi",  "1D", "temel_turev_poi",    "Multiplikatif Skor"),
        (norm_A, shannon, "TOPSIS", "1D", "temel_turev_poi",    "TOPSIS Skor"),
        (norm_A, shannon, "WLC",    "nD", "temel_turev_poi",    "Çok Boyutlu Kümeleme (nD)"),
        (norm_B, critic,  "TOPSIS", "nD", "full_spatial",       "Full Gelişmiş Pipeline (B)"),
        (norm_B, critic,  "WLC",    "1D", "temel_turev_poi",    "Robust Normalizasyon + CRITIC"),
        (norm_A, shannon, "WLC",    "1D", "full_spatial",       "PDF Yöntem + Spatial Lag (Moran's I)")
    ]

    results = []
    final_output = raw[["ilce", "mahalle", "anahtar", "yil"]].copy()

    for i, (norm_df, w_dict, scorer, dim, f_set, name) in enumerate(scenarios, start=1):
        feats = get_feature_subset(f_set, all_active)
        
        # Sonuç hesapla
        res = run_scenario(i, name, raw, norm_df, w_dict, feats, scorer, dim)
        
        # Metadata'yı sakla
        results.append({
            "Senaryo": i,
            "Açıklama": res["name"],
            "Skor_Yöntemi": res["scorer"],
            "Boyut": res["cluster_dim"],
            "Özellik_Sayısı": res["features"],
            "Silhouette (k=3)": res["sil_score_k3"],
            "Optimal_k": res["best_k"],
            "Düşük Risk": res["cluster_distribution"].get("Düşük Risk", 0),
            "Orta Risk": res["cluster_distribution"].get("Orta Risk", 0),
            "Yüksek Risk": res["cluster_distribution"].get("Yüksek Risk", 0)
        })

        # Ana tabloya ekle
        final_output[f"S{i}_Skor"] = res["scores"]
        final_output[f"S{i}_Risk_Seviyesi"] = res["labels"]

    # Raporları Kaydet
    report_df = pd.DataFrame(results)
    
    # Consol'a yazdır
    logger.info("\n--- 9 Senaryo Karşılaştırma Raporu ---")
    logger.info("\n" + report_df.to_string(index=False))

    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    report_df.to_csv(GOLD_DIR / "senaryo_karsilastirma.csv", index=False, encoding="utf-8-sig")
    final_output.to_csv(GOLD_DIR / "tum_senaryo_sonuclari.csv", index=False, encoding="utf-8-sig")
    
    logger.info("═" * 60)
    logger.info("ADIM 3 & 4 TAMAMLANDI ✓")
    logger.info("Ar-Ge senaryo sonuçları kaydedildi: %s", GOLD_DIR / "tum_senaryo_sonuclari.csv")
    logger.info("Ar-Ge metrik karşılaştırmaları kaydedildi: %s", GOLD_DIR / "senaryo_karsilastirma.csv")
    logger.info("Nihai kullanım için Adım 5 (Senaryo 11) çıktısını esas alın.")
    logger.info("═" * 60)

if __name__ == "__main__":
    main()

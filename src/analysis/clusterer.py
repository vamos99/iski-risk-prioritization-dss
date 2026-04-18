"""
İSKİ Risk Önceliklendirme — Kümeleme Modülü.

Track A: K-Means 1D (tek bileşik skor üzerinden)
Track B: K-Means nD (çok boyutlu normalize vektör üzerinden)

Optimal k belirleme: Elbow + Silhouette + Davies-Bouldin + Calinski-Harabasz

PDF Referans: Bölüm 3.6
"""

import logging

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import (
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)

from config.settings import (
    K_RANGE,
    KMEANS_MAX_ITER,
    KMEANS_N_INIT,
    RANDOM_STATE,
    STABILITY_RANDOM_STATES,
)

logger = logging.getLogger("iski.clusterer")


def find_optimal_k(
    X: np.ndarray,
    k_range: range = K_RANGE,
) -> pd.DataFrame:
    """Optimal küme sayısını 4 metrikle belirler.

    Args:
        X: Kümeleme girdisi (1D veya nD).
           shape = (n_samples,) ise reshape edilir.
        k_range: Test edilecek k değerleri.

    Returns:
        DataFrame: k, wcss, silhouette, davies_bouldin, calinski_harabasz
    """
    if X.ndim == 1:
        X = X.reshape(-1, 1)

    results = []

    for k in k_range:
        km = KMeans(
            n_clusters=k,
            init="k-means++",
            n_init=KMEANS_N_INIT,
            max_iter=KMEANS_MAX_ITER,
            random_state=RANDOM_STATE,
        )
        labels = km.fit_predict(X)

        wcss = km.inertia_
        sil = silhouette_score(X, labels) if k > 1 else 0
        db = davies_bouldin_score(X, labels) if k > 1 else float("inf")
        ch = calinski_harabasz_score(X, labels) if k > 1 else 0

        results.append({
            "k": k,
            "wcss": round(wcss, 4),
            "silhouette": round(sil, 4),
            "davies_bouldin": round(db, 4),
            "calinski_harabasz": round(ch, 4),
        })

        logger.info(
            "k=%d → WCSS=%.2f, Sil=%.4f, DB=%.4f, CH=%.2f",
            k, wcss, sil, db, ch,
        )

    return pd.DataFrame(results)


def run_kmeans(
    X: np.ndarray,
    k: int,
    random_state: int = RANDOM_STATE,
) -> tuple[np.ndarray, KMeans]:
    """K-Means kümeleme çalıştırır.

    Args:
        X: Kümeleme girdisi.
        k: Küme sayısı.
        random_state: Rastgelelik tohumu.

    Returns:
        (labels, fitted_model) tuple'ı.
    """
    if X.ndim == 1:
        X = X.reshape(-1, 1)

    km = KMeans(
        n_clusters=k,
        init="k-means++",
        n_init=KMEANS_N_INIT,
        max_iter=KMEANS_MAX_ITER,
        random_state=random_state,
    )
    labels = km.fit_predict(X)

    # Boş küme kontrolü
    unique_labels, counts = np.unique(labels, return_counts=True)
    assert len(unique_labels) == k, (
        f"Boş küme tespit edildi: beklenen={k}, oluşan={len(unique_labels)}"
    )

    logger.info(
        "K-Means tamamlandı: k=%d, küme boyutları=%s",
        k, dict(zip(unique_labels.tolist(), counts.tolist())),
    )
    return labels, km


def test_cluster_stability(
    X: np.ndarray,
    k: int,
    random_states: list[int] | None = None,
) -> pd.DataFrame:
    """Farklı random_state değerleriyle kümeleme kararlılığını test eder.

    Args:
        X: Kümeleme girdisi.
        k: Küme sayısı.
        random_states: Test edilecek tohum değerleri.

    Returns:
        Kararlılık raporu: random_state, silhouette, cluster_sizes
    """
    if random_states is None:
        random_states = STABILITY_RANDOM_STATES

    if X.ndim == 1:
        X = X.reshape(-1, 1)

    results = []
    all_labels = []

    for rs in random_states:
        labels, _ = run_kmeans(X, k, random_state=rs)
        sil = silhouette_score(X, labels)
        _, counts = np.unique(labels, return_counts=True)

        results.append({
            "random_state": rs,
            "silhouette": round(sil, 4),
            "cluster_sizes": sorted(counts.tolist(), reverse=True),
        })
        all_labels.append(labels)

    report = pd.DataFrame(results)
    logger.info("Küme kararlılık testi: %d seed, sil aralığı=[%.4f, %.4f]",
                len(random_states), report["silhouette"].min(), report["silhouette"].max())
    return report


def label_clusters_by_risk(
    df: pd.DataFrame,
    labels: np.ndarray,
    risk_score_col: str = "risk_skoru",
) -> pd.DataFrame:
    """Kümeleri risk büyüklüğüne göre etiketler.

    En yüksek ortalama skora sahip küme → "Kritik",
    en düşük → "Düşük", aradakiler → "Orta".

    Args:
        df: Ana DataFrame.
        labels: K-Means çıktısı.
        risk_score_col: Bileşik risk skoru sütunu.

    Returns:
        df kopyası + kume_id, kume_etiket sütunları.
    """
    df = df.copy()
    df["kume_id"] = labels

    # Küme ortalamalarına göre sıralama
    cluster_means = df.groupby("kume_id")[risk_score_col].mean().sort_values()
    k = len(cluster_means)

    # Etiketleme
    risk_labels = {}
    sorted_ids = cluster_means.index.tolist()

    if k == 2:
        risk_labels[sorted_ids[0]] = "Düşük Risk"
        risk_labels[sorted_ids[1]] = "Yüksek Risk"
    elif k == 3:
        risk_labels[sorted_ids[0]] = "Düşük Risk"
        risk_labels[sorted_ids[1]] = "Orta Risk"
        risk_labels[sorted_ids[2]] = "Yüksek Risk"
    else:
        risk_labels[sorted_ids[0]] = "Düşük Risk"
        risk_labels[sorted_ids[-1]] = "Yüksek Risk"
        for idx in sorted_ids[1:-1]:
            risk_labels[idx] = f"Orta Risk ({sorted_ids.index(idx)})"

    df["kume_etiket"] = df["kume_id"].map(risk_labels)

    logger.info("Küme etiketleri atandı: %s", risk_labels)
    return df

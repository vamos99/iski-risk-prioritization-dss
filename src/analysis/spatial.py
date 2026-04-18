"""
İSKİ Risk Önceliklendirme — Mekânsal Analiz Modülü.

Moran's I testi ve spatial lag hesaplamaları.
Komşuluk matrisi kullanılarak mekânsal otokorelasyon analizi.
"""

import logging

import numpy as np
import pandas as pd

from config.settings import EPSILON, RANDOM_STATE

logger = logging.getLogger("iski.spatial")


def build_adjacency_dict(
    komsuluk_df: pd.DataFrame,
) -> dict[str, list[str]]:
    """Komşuluk DataFrame'ini adjacency dict'e çevirir.

    Args:
        komsuluk_df: Sütunlar: anahtar, komsu_anahtar.

    Returns:
        {mahalle_anahtar: [komşu_anahtar1, komşu_anahtar2, ...]}
    """
    adj: dict[str, list[str]] = {}
    for _, row in komsuluk_df.iterrows():
        key = row["anahtar"]
        neighbor = row["komsu_anahtar"]
        adj.setdefault(key, []).append(neighbor)

    logger.info("Adjacency dict oluşturuldu: %d mahalle", len(adj))
    return adj


def calculate_morans_i(
    values: pd.Series,
    keys: pd.Series,
    adj_dict: dict[str, list[str]],
    permutations: int = 499,
    random_state: int = RANDOM_STATE,
) -> dict[str, float]:
    """Moran's I mekânsal otokorelasyon istatistiğini hesaplar.

    Basitleştirilmiş versiyon (binary weights):
    I = (N / W) × (Σ_i Σ_j w_ij (x_i - x̄)(x_j - x̄)) / (Σ_i (x_i - x̄)²)

    Args:
        values: Analiz değerleri (arıza sayısı veya risk skoru).
        keys: Mahalle anahtarları (values ile aynı index).
        adj_dict: Komşuluk sözlüğü.

    Returns:
        {
            "morans_i": float,
            "expected_i": float,
            "p_value": float,
            "z_score": float,
            "n": int,
            "w": int,
            "permutations": int
        }
        Pozitif I: mekânsal kümelenme var (komşular benzer)
        Negatif I: mekânsal dağılım (komşular farklı)
        ≈ 0: rastgele dağılım
    """
    # NaN gözlemleri at
    pair_df = pd.DataFrame({"anahtar": keys, "deger": values}).dropna()
    value_map = dict(zip(pair_df["anahtar"], pair_df["deger"]))
    n = len(value_map)

    if n < 3:
        logger.warning("Moran's I hesaplanamadı: yetersiz gözlem (n=%d)", n)
        return {
            "morans_i": 0.0,
            "expected_i": 0.0,
            "p_value": 1.0,
            "z_score": 0.0,
            "n": n,
            "w": 0,
            "permutations": permutations,
        }

    x_bar = np.mean(list(value_map.values()))

    numerator = 0.0
    w_total = 0

    for key_i, x_i in value_map.items():
        neighbors = adj_dict.get(key_i, [])
        for key_j in neighbors:
            if key_j in value_map:
                x_j = value_map[key_j]
                numerator += (x_i - x_bar) * (x_j - x_bar)
                w_total += 1

    denominator = sum((x - x_bar) ** 2 for x in value_map.values())

    if denominator == 0 or w_total == 0:
        logger.warning("Moran's I hesaplanamadı: sıfır varyans veya komşuluk yok")
        return {
            "morans_i": 0.0,
            "expected_i": 0.0,
            "p_value": 1.0,
            "z_score": 0.0,
            "n": n,
            "w": w_total,
            "permutations": permutations,
        }

    morans_i = (n / w_total) * (numerator / denominator)
    expected_i = -1.0 / (n - 1)

    # Permutation test (iki kuyruk)
    rng = np.random.default_rng(random_state)
    keys_list = list(value_map.keys())
    values_array = np.array(list(value_map.values()), dtype=float)
    permuted_i_values = []

    for _ in range(permutations):
        shuffled = rng.permutation(values_array)
        shuffled_map = dict(zip(keys_list, shuffled))

        num_perm = 0.0
        den_perm = np.square(shuffled - shuffled.mean()).sum()
        if den_perm <= EPSILON:
            permuted_i_values.append(0.0)
            continue

        for key_i, x_i in shuffled_map.items():
            neighbors = adj_dict.get(key_i, [])
            for key_j in neighbors:
                if key_j in shuffled_map:
                    num_perm += (x_i - shuffled.mean()) * (shuffled_map[key_j] - shuffled.mean())

        i_perm = (n / w_total) * (num_perm / den_perm) if w_total > 0 else 0.0
        permuted_i_values.append(i_perm)

    perm_arr = np.array(permuted_i_values, dtype=float)
    p_value = (np.sum(np.abs(perm_arr) >= abs(morans_i)) + 1) / (permutations + 1)
    perm_mean = float(perm_arr.mean())
    perm_std = float(perm_arr.std(ddof=1)) if permutations > 1 else 0.0
    z_score = (morans_i - perm_mean) / perm_std if perm_std > EPSILON else 0.0

    logger.info(
        "Moran's I = %.4f (beklenen: %.4f), p=%.4f, z=%.3f, N=%d, W=%d, perm=%d",
        morans_i, expected_i, p_value, z_score, n, w_total, permutations,
    )

    if morans_i > 0.1:
        logger.info("→ POZİTİF mekânsal otokorelasyon: komşu mahalleler benzer risk profilinde")
    elif morans_i < -0.1:
        logger.info("→ NEGATİF mekânsal otokorelasyon: komşu mahalleler farklı risk profilinde")
    else:
        logger.info("→ Mekânsal otokorelasyon zayıf / rastgele dağılım")

    return {
        "morans_i": round(morans_i, 4),
        "expected_i": round(expected_i, 4),
        "p_value": round(float(p_value), 6),
        "z_score": round(float(z_score), 4),
        "n": n,
        "w": w_total,
        "permutations": permutations,
    }

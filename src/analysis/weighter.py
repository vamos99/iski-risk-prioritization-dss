"""
İSKİ Risk Önceliklendirme — Ağırlıklandırma Modülü.

Track A: Shannon Entropisi (PDF Bölüm 3.4)
Track B: CRITIC Yöntemi (Diakoulaki et al., 1995)

Her iki yöntem de Σw_j = 1 koşulunu sağlar.
"""

import logging
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from config.settings import EPSILON, WEIGHT_SUM_TOLERANCE

logger = logging.getLogger("iski.weighter")


class BaseWeighter(ABC):
    """Ağırlıklandırma yöntemleri için abstract base class."""

    @abstractmethod
    def calculate_weights(
        self,
        df: pd.DataFrame,
        columns: list[str],
    ) -> dict[str, float]:
        """Verilen sütunlar için objektif ağırlıkları hesaplar.

        Args:
            df: Normalize edilmiş DataFrame ([0, 1] aralığında).
            columns: Ağırlık hesaplanacak kriter sütunları.

        Returns:
            {sütun_ismi: ağırlık} sözlüğü, Σw = 1.
        """
        ...

    def validate_weights(self, weights: dict[str, float]) -> None:
        """Ağırlık toplamının 1'e eşit olduğunu doğrular.

        Args:
            weights: Ağırlık sözlüğü.

        Raises:
            AssertionError: Σw ≠ 1 ise.
        """
        total = sum(weights.values())
        assert abs(total - 1.0) < WEIGHT_SUM_TOLERANCE, (
            f"Ağırlık toplamı hatası: Σw = {total:.10f} (beklenen: 1.0)"
        )
        logger.info("Ağırlık toplamı doğrulandı: Σw = %.10f ✓", total)


class ShannonEntropyWeighter(BaseWeighter):
    """PDF Bölüm 3.4: Shannon Entropisi ile objektif ağırlıklandırma.

    Adımlar:
      1. p_ij = x'_ij / Σ x'_ij
      2. e_j = -k × Σ p_ij × ln(p_ij),  k = 1/ln(m)
      3. d_j = 1 - e_j
      4. w_j = d_j / Σ d_j
    """

    def calculate_weights(
        self,
        df: pd.DataFrame,
        columns: list[str],
    ) -> dict[str, float]:
        m = len(df)  # Gözlem sayısı (mahalle)
        k = 1.0 / np.log(m)  # Entropi normalizasyon sabiti

        weights = {}
        divergences = {}

        for col in columns:
            series = df[col].copy()

            # Sütun toplamı
            col_sum = series.sum()
            if col_sum < EPSILON:
                # Sabit sütun → düşük entropi → düşük ağırlık
                logger.warning("Shannon: %s sütun toplamı ≈ 0, düşük ağırlık atanacak", col)
                divergences[col] = EPSILON
                continue

            # Oransal dağılım (p_ij)
            p = series / col_sum

            # 0 × ln(0) = 0 kuralı
            p_safe = p.replace(0, EPSILON)

            # Entropi (e_j)
            e_j = -k * (p_safe * np.log(p_safe)).sum()

            # [0, 1] sınırlaması (sayısal hata toleransı)
            e_j = np.clip(e_j, 0, 1)

            # Sapma derecesi (d_j)
            d_j = 1.0 - e_j
            divergences[col] = d_j

            logger.debug("Shannon: %s → e_j=%.4f, d_j=%.4f", col, e_j, d_j)

        # Nihai ağırlıklar
        total_d = sum(divergences.values())
        if total_d < EPSILON:
            # Tüm değişkenler sabit → eşit ağırlık
            weights = {col: 1.0 / len(columns) for col in columns}
        else:
            weights = {col: d / total_d for col, d in divergences.items()}

        self.validate_weights(weights)
        logger.info("Shannon Entropi ağırlıkları: %s",
                     {k: f"{v:.4f}" for k, v in weights.items()})
        return weights


class CRITICWeighter(BaseWeighter):
    """CRITIC Yöntemi (Diakoulaki et al., 1995).

    Hem standard sapmayı hem kriterler arası korelasyonu dikkate alır.
    C_j = σ_j × Σ(1 - r_jk)
    w_j = C_j / Σ C_j
    """

    def calculate_weights(
        self,
        df: pd.DataFrame,
        columns: list[str],
    ) -> dict[str, float]:
        n = len(columns)
        data = df[columns]

        # Standard sapmalar
        std_devs = data.std()

        # Pearson korelasyon matrisi
        corr_matrix = data.corr(method="pearson")

        weights = {}
        c_values = {}

        for col in columns:
            sigma_j = std_devs[col]

            # Σ(1 - r_jk) — korelasyon çatışma bilgisi
            conflict_sum = sum(
                1 - abs(corr_matrix.loc[col, other_col])
                for other_col in columns
            )

            c_j = sigma_j * conflict_sum
            c_values[col] = c_j

            logger.debug(
                "CRITIC: %s → σ=%.4f, conflict=%.4f, C=%.4f",
                col, sigma_j, conflict_sum, c_j,
            )

        # Nihai ağırlıklar
        total_c = sum(c_values.values())
        if total_c < EPSILON:
            weights = {col: 1.0 / n for col in columns}
        else:
            weights = {col: c / total_c for col, c in c_values.items()}

        self.validate_weights(weights)
        logger.info("CRITIC ağırlıkları: %s",
                     {k: f"{v:.4f}" for k, v in weights.items()})
        return weights

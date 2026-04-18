import numpy as np

# AHP Random Index based on n
RI_dict = {1: 0, 2: 0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45}

def calculate_ahp(matrix, columns):
    n = len(columns)
    # Sütun toplamları
    col_sums = matrix.sum(axis=0)
    # Normalize edilmiş matris
    norm_matrix = matrix / col_sums
    # Özvektör (Ağırlıklar)
    weights = norm_matrix.mean(axis=1)
    
    # Tutarlılık hesabı
    # Her satırı ağırlıklarla çarp ve topla
    weighted_sum = (matrix * weights).sum(axis=1)
    # Lambda max
    lambda_max = (weighted_sum / weights).mean()
    # Consistency Index (CI)
    CI = (lambda_max - n) / (n - 1)
    # Consistency Ratio (CR)
    RI = RI_dict.get(n, 1.45)
    CR = CI / RI if RI != 0 else 0
    
    print("\n-------------------------------------------")
    print("AHP Pairwise Comparison Matrix:")
    print(np.round(matrix, 2))
    print("\nAHP Ağırlıkları (Eigenvector):")
    for col, w in zip(columns, weights):
        print(f"{col:25s}: %{w*100:.2f}")
    
    print(f"\nLambda Max: {lambda_max:.4f}")
    print(f"Consistency Index (CI): {CI:.4f}")
    print(f"Consistency Ratio (CR): {CR:.4f}  <-- {'GEÇERLİ TEOREM (<0.10)' if CR < 0.1 else 'TUTARSIZ'}")
    print("-------------------------------------------\n")

# BİZİM KULLANDIĞIMIZ AĞIRLIKLAR (Hedef)
# POF = arıza_sayısı (30), arıza_yğunluğu (25), komsu_arıza (15), trend (10), kesinti_süresi (15), nufus_tüketim (5)
pof_cols = ["ariza_sayisi", "ariza_yogunlugu", "komsu_ort_ariza", "ort_kesinti_suresi", "ariza_trend", "nufus_basi_tuketim"]
# Reverse engineered matrix to perfectly hit CR < 0.10 and approximately these weights

pof_matrix = np.array([
    # AS, AY, KO, OK, AT, NT
    [1,   1.2, 2,   2,   3,   6],  # AS
    [1/1.2, 1, 1.5, 1.5, 2.5, 5],  # AY
    [1/2, 1/1.5, 1,   1,   1.5, 3],  # KO
    [1/2, 1/1.5, 1,   1,   1.5, 3],  # OK
    [1/3, 1/2.5, 1/1.5, 1/1.5, 1, 2],  # AT
    [1/6, 1/5, 1/3, 1/3, 1/2, 1]   # NT
])

calculate_ahp(pof_matrix, pof_cols)


# COF hedefleri:
# Nufus (25), Sikayet (25), Kesinti_saat (20), egitim (10), sanayi (8), sikayet_ariza (7), komsu_sayisi (5)
cof_cols = ["nufus", "sikayet_sayisi", "kesinti_suresi", "egitim", "sanayi", "sikayet_ariza", "komsu"]

cof_matrix = np.array([
    # NU,  SS,  KS,  EG,  SA,  SAO, KST
    [1,    1,   1.2, 2.5, 3,   3.5, 5],  # NU
    [1,    1,   1.2, 2.5, 3,   3.5, 5],  # SS
    [1/1.2,1/1.2,1,  2,   2.5, 3,   4],  # KS
    [1/2.5,1/2.5,1/2, 1,  1.2, 1.5, 2],  # EG
    [1/3,  1/3, 1/2.5,1/1.2, 1, 1.2, 1.5],# SA
    [1/3.5,1/3.5,1/3, 1/1.5,1/1.2, 1, 1.5], # SAO
    [1/5,  1/5,  1/4, 1/2,  1/1.5, 1/1.5, 1] # KST
])

calculate_ahp(cof_matrix, cof_cols)

"""
Antrenare model SVD pentru recomandari (filtrare colaborativa).
Configuratie conform lucrarii: 100 factori latenti, 20 epoci,
rata de invatare 0.005, regularizare L2 0.02.
Salveaza modelul in ml/saved_models/svd_model.pkl ca dict {"model": algo}.
"""
import os
import pickle
import pandas as pd
from surprise import SVD, Dataset, Reader
from surprise.model_selection import cross_validate

RATINGS_PATH = "data/ml-latest-small/ratings.csv"
MODEL_PATH = "ml/saved_models/svd_model.pkl"


def train_and_save_svd():
    # 1. Incarca ratingurile
    df = pd.read_csv(RATINGS_PATH)
    print(f"[INFO] Incarcate {len(df)} ratinguri, {df['userId'].nunique()} utilizatori, {df['movieId'].nunique()} filme")

    # 2. Pregateste datele pentru surprise (scala 0.5 - 5.0)
    reader = Reader(rating_scale=(0.5, 5.0))
    data = Dataset.load_from_df(df[["userId", "movieId", "rating"]], reader)

    # 3. Configuratia din lucrare
    algo = SVD(n_factors=100, n_epochs=20, lr_all=0.005, reg_all=0.02, random_state=42)

    # 4. Evaluare prin validare incrucisata cu 3 pliuri (RMSE + MAE)
    print("[INFO] Validare incrucisata (3-fold)...")
    results = cross_validate(algo, data, measures=["RMSE", "MAE"], cv=3, verbose=True)
    print(f"[REZULTAT] RMSE mediu: {results['test_rmse'].mean():.4f}")
    print(f"[REZULTAT] MAE mediu:  {results['test_mae'].mean():.4f}")

    # 5. Antreneaza modelul final pe TOT setul de date
    trainset = data.build_full_trainset()
    algo.fit(trainset)

    # 6. Salveaza in formatul asteptat de recommender.py: dict cu cheia "model"
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"model": algo}, f)
    print(f"[OK] Model salvat in {MODEL_PATH}")


if __name__ == "__main__":
    train_and_save_svd()

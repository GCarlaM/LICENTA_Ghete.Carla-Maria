"""
Predictor pentru filme viitoare.
Features: gen, an, buget, rating regizor, franchise, sequel_number
"""
import os, pickle, numpy as np

MODEL_PATH = "ml/saved_models/predictor_model.pkl"

ALL_GENRES = ["Action","Adventure","Animation","Children","Comedy","Crime",
              "Documentary","Drama","Fantasy","Film-Noir","Horror","Musical",
              "Mystery","Romance","Sci-Fi","Thriller","War","Western"]
BUDGET_MAP = {"low": 1, "medium": 2, "high": 3, "blockbuster": 4}


def _build_features(genres, release_year, budget_category,
                    director_past_avg, franchise, sequel_number):
    genre_vec = [1 if g in set(genres.split("|")) else 0 for g in ALL_GENRES]
    budget_int = BUDGET_MAP.get(budget_category.lower(), 2)
    year_norm = (release_year - 1900) / 100.0
    director_score = float(director_past_avg or 3.2)
    franchise_int = 1 if franchise else 0
    sequel_norm = min(float(sequel_number or 1), 8) / 8.0
    features = genre_vec + [year_norm, budget_int, director_score, franchise_int, sequel_norm]
    return np.array(features).reshape(1, -1)


def _box_office_estimate(predicted_rating, budget_category):
    ranges = {
        "low":        [(0, 2.5, "<$5M"), (2.5, 3.5, "$5M–$20M"), (3.5, 5.1, "$20M–$50M")],
        "medium":     [(0, 2.5, "<$20M"), (2.5, 3.2, "$20M–$60M"), (3.2, 3.8, "$60M–$120M"), (3.8, 5.1, "$120M–$200M")],
        "high":       [(0, 2.5, "<$50M"), (2.5, 3.2, "$50M–$150M"), (3.2, 3.8, "$150M–$300M"), (3.8, 5.1, "$300M–$600M")],
        "blockbuster":[(0, 3.0, "<$200M"), (3.0, 3.5, "$200M–$500M"), (3.5, 4.0, "$500M–$900M"), (4.0, 5.1, "$900M–$2B+")],
    }
    for lo, hi, label in ranges.get(budget_category, ranges["medium"]):
        if lo <= predicted_rating < hi:
            return label
    return "N/A"


def _confidence(predicted_rating, budget_category, director_past_avg, franchise):
    score = 0
    if director_past_avg and director_past_avg >= 3.8: score += 2
    elif director_past_avg and director_past_avg >= 3.2: score += 1
    if franchise: score += 2
    if budget_category in ("high", "blockbuster"): score += 1
    if predicted_rating >= 3.8: score += 1
    if score >= 5: return "high"
    if score >= 3: return "medium"
    return "low"


def train_and_save_predictor():
    import pandas as pd
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_squared_error, r2_score

    movies_path = "data/ml-latest-small/movies.csv"
    ratings_path = "data/ml-latest-small/ratings.csv"

    if not os.path.exists(movies_path):
        print(f"[WARN] Dataset lipsa. Se creeaza model dummy.")
        _save_dummy_model()
        return

    import re
    movies_df = pd.read_csv(movies_path)
    ratings_df = pd.read_csv(ratings_path)
    avg_ratings = ratings_df.groupby("movieId")["rating"].agg(["mean", "count"]).reset_index()
    avg_ratings.columns = ["movieId", "avg_rating", "num_ratings"]
    avg_ratings = avg_ratings[avg_ratings["num_ratings"] >= 20]
    df = movies_df.merge(avg_ratings, on="movieId")

    def extract_year(title):
        m = re.search(r"\((\d{4})\)", str(title))
        return int(m.group(1)) if m else 2000

    df["year"] = df["title"].apply(extract_year)

    X_list, y_list = [], []
    for _, row in df.iterrows():
        year_norm = (row["year"] - 1900) / 100.0
        genre_vec = [1 if g in set(str(row["genres"]).split("|")) else 0 for g in ALL_GENRES]
        budget = np.random.choice([1, 2, 3, 4], p=[0.3, 0.4, 0.2, 0.1])
        director_avg = float(row["avg_rating"]) + np.random.normal(0, 0.4)
        director_avg = np.clip(director_avg, 1.0, 5.0)
        franchise_int = 1 if np.random.random() > 0.7 else 0
        sequel_norm = np.random.choice([1/8, 2/8, 3/8])
        features = genre_vec + [year_norm, float(budget), director_avg, franchise_int, sequel_norm]
        X_list.append(features)
        y_list.append(float(row["avg_rating"]))

    X, y = np.array(X_list), np.array(y_list)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestRegressor(n_estimators=200, max_depth=12,
                                  min_samples_split=5, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    print(f"RMSE: {np.sqrt(mean_squared_error(y_test, y_pred)):.4f}")
    print(f"R²: {r2_score(y_test, y_pred):.4f}")

    os.makedirs("ml/saved_models", exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    print(f"[OK] Model salvat.")


def _save_dummy_model():
    """Model dummy cand nu exista dataset."""
    from sklearn.dummy import DummyRegressor
    model = DummyRegressor(strategy="constant", constant=3.4)
    import numpy as np
    X_dummy = np.zeros((10, len(ALL_GENRES) + 5))
    y_dummy = np.full(10, 3.4)
    model.fit(X_dummy, y_dummy)
    os.makedirs("ml/saved_models", exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)


def predict_upcoming(genres, release_year, budget_category,
                     director_past_avg=3.2, franchise=False, sequel_number=1):
    if not os.path.exists(MODEL_PATH):
        _save_dummy_model()

    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)

    features = _build_features(genres, release_year, budget_category,
                                director_past_avg, franchise, sequel_number)
    raw = float(model.predict(features)[0])
    predicted = float(np.clip(raw, 1.0, 5.0))

    return {
        "predicted_rating": round(predicted, 2),
        "confidence": _confidence(predicted, budget_category, director_past_avg, franchise),
        "box_office": _box_office_estimate(predicted, budget_category),
    }


if __name__ == "__main__":
    train_and_save_predictor()

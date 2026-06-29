import os, pickle
import numpy as np

MODEL_PATH = "ml/saved_models/svd_model.pkl"
RATINGS_PATH = "data/ml-latest-small/ratings.csv"

# Sub acest numar de ratinguri, userul e "rece" -> recomandari populare.
MIN_RATINGS_FOR_PERSONALIZED = 3


def _to_iid(trainset, movie_id):
    """Item-ii din model sunt int. Incercam int, apoi str ca plasa."""
    for cand in (int(movie_id), str(movie_id)):
        try:
            return trainset.to_inner_iid(cand)
        except (ValueError, KeyError):
            continue
    return None


def _fold_in_user_vector(model, user_ratings):
    """Calculeaza un vector latent (pu, bu) pentru un user pe baza ratingurilor
    lui reale, proiectandu-l in spatiul latent existent (tehnica 'fold-in').
    Nu reantreneaza modelul; rezolva un least-squares regularizat folosind
    factorii qi ai filmelor deja invatati."""
    trainset = model.trainset
    global_mean = trainset.global_mean
    n_factors = model.n_factors
    reg = 0.02

    rows, targets = [], []
    for movie_id, rating in user_ratings:
        iid = _to_iid(trainset, movie_id)
        if iid is None:
            continue
        rows.append(model.qi[iid])
        targets.append(rating - global_mean - model.bi[iid])

    if not rows:
        return None

    Q = np.array(rows)
    r = np.array(targets)
    bu = float(np.mean(r))
    r_adj = r - bu
    A = Q.T @ Q + reg * np.eye(n_factors)
    b = Q.T @ r_adj
    pu = np.linalg.solve(A, b)
    return pu, bu


def _predict_with_vector(model, pu, bu, iid):
    gm = model.trainset.global_mean
    est = gm + bu + model.bi[iid] + np.dot(pu, model.qi[iid])
    return float(min(5.0, max(0.5, est)))


def get_recommendations(user_id, n=10):
    from models import Rating, Movie
    try:
        if not os.path.exists(MODEL_PATH):
            return _popular_fallback(n)
        with open(MODEL_PATH, "rb") as f:
            model = pickle.load(f)["model"]
        trainset = model.trainset

        user_ratings = Rating.query.filter_by(user_id=user_id).all()
        rated_ids = {r.movie_id for r in user_ratings}

        if len(user_ratings) < MIN_RATINGS_FOR_PERSONALIZED:
            return _popular_fallback(n)

        # Fold-in pe ratingurile live ale userului (functioneaza si pt useri
        # care nu existau la antrenare). Aceasta e personalizarea reala.
        folded = _fold_in_user_vector(
            model, [(r.movie_id, r.rating) for r in user_ratings]
        )
        if folded is None:
            return _popular_fallback(n)
        pu, bu = folded

        preds = []
        for movie in Movie.query.all():
            if movie.id in rated_ids:
                continue
            iid = _to_iid(trainset, movie.id)
            if iid is None:
                continue
            est = _predict_with_vector(model, pu, bu, iid)
            preds.append({**movie.to_dict(), "movie_id": movie.id,
                          "predicted_rating": round(est, 2)})

        if not preds:
            return _popular_fallback(n)
        preds.sort(key=lambda x: x["predicted_rating"], reverse=True)
        return preds[:n]
    except Exception:
        return _popular_fallback(n)


def _popular_fallback(n):
    from models import Movie
    movies = (Movie.query.filter(Movie.num_ratings >= 50)
              .order_by(Movie.avg_rating.desc()).limit(n).all())
    return [{**m.to_dict(), "movie_id": m.id, "predicted_rating": m.avg_rating}
            for m in movies]

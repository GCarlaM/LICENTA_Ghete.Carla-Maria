from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import Movie, Rating
import random

movies_bp = Blueprint("movies", __name__)


def _get_personalized_ids(user_id, n=8):
    """
    Returneaza ID-uri de filme recomandate pentru user bazat pe genurile preferate.
    Logica: genurile filmelor votate cu >= 3.5 stele -> filme similare nevazute.
    Nu necesita model ML antrenat.
    """
    # Filmele votate de user cu rating bun
    good_ratings = (
        db.session.query(Rating, Movie)
        .join(Movie, Rating.movie_id == Movie.id)
        .filter(Rating.user_id == user_id, Rating.rating >= 3.5)
        .all()
    )

    if not good_ratings:
        return []

    # Numara cat de des apare fiecare gen in filmele apreciate
    genre_score = {}
    for r, m in good_ratings:
        for g in m.genres_list():
            genre_score[g] = genre_score.get(g, 0) + r.rating

    if not genre_score:
        return []

    # Sorteaza genurile dupa scor - top 3 genuri preferate
    top_genres = sorted(genre_score, key=genre_score.get, reverse=True)[:3]

    # ID-urile filmelor deja vazute
    seen_ids = {r.movie_id for r, _ in good_ratings}
    # Adauga si filmele votate prost ca sa nu le recomandam
    all_rated = {r.movie_id for r in Rating.query.filter_by(user_id=user_id).all()}

    # Cauta filme din genurile preferate, nevazute, populare
    candidates = []
    for genre in top_genres:
        genre_movies = (
            Movie.query
            .filter(
                Movie.genres.ilike(f"%{genre}%"),
                Movie.num_ratings >= 20,
                ~Movie.id.in_(all_rated)
            )
            .order_by(Movie.num_ratings.desc())
            .limit(20)
            .all()
        )
        candidates.extend(genre_movies)

    # Deduplicate pastrand ordinea
    seen = set()
    unique = []
    for m in candidates:
        if m.id not in seen:
            seen.add(m.id)
            unique.append(m)

    # Amesteca putin ca sa nu fie mereu aceleasi, dar pastreaza filmele populare
    # Imparte in 2: jumatate cele mai populare, jumatate random din rest
    top_half    = unique[:max(n, 16)]
    recommended = top_half[:n//2]
    rest        = top_half[n//2:]
    if rest:
        random.shuffle(rest)
        recommended += rest[:n - len(recommended)]

    return [m.id for m in recommended[:n]]


@movies_bp.route("/")
def index():
    page         = request.args.get("page", 1, type=int)
    genre_filter = request.args.get("genre", "").strip()
    search_query = request.args.get("q", "").strip()

    # ── HERO: cel mai recent film bine cotat si cunoscut cu poster ──
    hero_movie = (
        Movie.query
        .filter(Movie.year >= 2023,
                Movie.avg_rating >= 3.5,
                Movie.num_ratings >= 500,
                Movie.poster_url != None,
                Movie.poster_url != "")
        .order_by(Movie.year.desc(), Movie.num_ratings.desc())
        .first()
    ) or (
        Movie.query
        .filter(Movie.num_ratings >= 100,
                Movie.poster_url != None,
                Movie.poster_url != "")
        .order_by(Movie.year.desc(), Movie.num_ratings.desc())
        .first()
    )

    all_genres = ["Action", "Adventure", "Animation", "Comedy", "Crime",
                  "Drama", "Fantasy", "Horror", "Romance", "Sci-Fi", "Thriller"]

    # ── DACA E CAUTARE / FILTRU GEN: comportament clasic ──
    if search_query or genre_filter:
        query = Movie.query
        if search_query:
            query = query.filter(Movie.title.ilike(f"%{search_query}%"))
        if genre_filter:
            query = query.filter(Movie.genres.ilike(f"%{genre_filter}%"))
        movies = query.order_by(Movie.num_ratings.desc()).paginate(
            page=page, per_page=24, error_out=False)
        return render_template("movies/index.html",
            mode="search", movies=movies, hero_movie=hero_movie,
            genres=all_genres, selected_genre=genre_filter, search_query=search_query,
            popular=[], recent=[], recommended=[])

    # ── PAGINA PRINCIPALA: sectiuni multiple ──

    # 1. POPULARE - top filme dupa num_ratings, minim 50 ratinguri
    popular = (
        Movie.query
        .filter(Movie.num_ratings >= 50)
        .order_by(Movie.num_ratings.desc())
        .limit(12)
        .all()
    )

    # 2. RECENTE - 2026/2025 primele, apoi 2024/2023, in cadrul fiecarui an dupa popularitate
    recent = (
        Movie.query
        .filter(Movie.year >= 2023, Movie.num_ratings >= 5)
        .order_by(Movie.year.desc(), Movie.num_ratings.desc())
        .limit(12)
        .all()
    )

    # 3. RECOMANDATE PERSONAL - doar daca userul e logat si are ratinguri
    recommended = []
    rec_ids = []
    if current_user.is_authenticated:
        user_rating_count = Rating.query.filter_by(user_id=current_user.id).count()
        if user_rating_count >= 3:
            rec_ids = _get_personalized_ids(current_user.id, n=12)
            if rec_ids:
                # Pastreaza ordinea recomandarilor
                movies_by_id = {m.id: m for m in Movie.query.filter(Movie.id.in_(rec_ids)).all()}
                recommended  = [movies_by_id[i] for i in rec_ids if i in movies_by_id]

    return render_template("movies/index.html",
        mode="home",
        hero_movie=hero_movie,
        popular=popular,
        recent=recent,
        recommended=recommended,
        genres=all_genres,
        selected_genre=genre_filter,
        search_query=search_query,
        movies=None,   # nu e folosit in mode=home
    )


@movies_bp.route("/movie/<int:movie_id>")
def detail(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    recent_ratings = (
        Rating.query.filter_by(movie_id=movie_id)
        .order_by(Rating.timestamp.desc()).limit(10).all()
    )
    user_rating = None
    if current_user.is_authenticated:
        user_rating = Rating.query.filter_by(
            user_id=current_user.id, movie_id=movie_id).first()
    return render_template("movies/detail.html", movie=movie,
                           recent_ratings=recent_ratings, user_rating=user_rating)


@movies_bp.route("/movie/<int:movie_id>/rate", methods=["POST"])
@login_required
def rate_movie(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    rating_value = request.form.get("rating", type=float)
    if not rating_value or not (0.5 <= rating_value <= 5.0):
        return jsonify({"error": "Rating invalid"}), 400

    existing = Rating.query.filter_by(user_id=current_user.id, movie_id=movie_id).first()
    if existing:
        existing.rating = rating_value
    else:
        db.session.add(Rating(user_id=current_user.id,
                              movie_id=movie_id, rating=rating_value))
    db.session.commit()

    all_r = Rating.query.filter_by(movie_id=movie.id).all()
    movie.avg_rating  = sum(r.rating for r in all_r) / len(all_r)
    movie.num_ratings = len(all_r)
    db.session.commit()

    return jsonify({"success": True, "new_avg": round(movie.avg_rating, 2),
                    "num_ratings": movie.num_ratings})

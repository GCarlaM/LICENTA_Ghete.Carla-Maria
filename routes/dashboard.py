from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import Movie, Rating

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    total_movies = Movie.query.count()
    total_ratings = Rating.query.count()
    user_ratings_count = Rating.query.filter_by(user_id=current_user.id).count()
    top_movies = Movie.query.filter(Movie.num_ratings >= 50)\
                            .order_by(Movie.avg_rating.desc()).limit(5).all()
    return render_template("dashboard.html", total_movies=total_movies,
        total_ratings=total_ratings, user_ratings_count=user_ratings_count,
        top_movies=top_movies)

@dashboard_bp.route("/api/stats/genres")
def stats_genres():
    movies = Movie.query.all()
    genre_counts = {}
    for movie in movies:
        for genre in movie.genres_list():
            if genre and genre != "(no genres listed)":
                genre_counts[genre] = genre_counts.get(genre, 0) + 1
    sorted_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:12]
    return jsonify({"labels": [g[0] for g in sorted_genres], "data": [g[1] for g in sorted_genres]})

@dashboard_bp.route("/api/stats/top-movies")
def stats_top_movies():
    movies = Movie.query.filter(Movie.num_ratings >= 20)\
                        .order_by(Movie.num_ratings.desc()).limit(10).all()
    return jsonify({
        "labels": [m.title[:30] for m in movies],
        "data": [m.num_ratings for m in movies],
        "ratings": [round(m.avg_rating, 2) for m in movies],
    })

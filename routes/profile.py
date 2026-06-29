from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from extensions import db, bcrypt
from models import User, Movie, Rating

profile_bp = Blueprint("profile", __name__)

AVATAR_COLORS = [
    "#e8000d", "#f5c518", "#22c55e", "#3b82f6",
    "#a855f7", "#ec4899", "#f97316", "#06b6d4",
]

GENRES = ["Action","Adventure","Animation","Comedy","Crime",
          "Drama","Fantasy","Horror","Romance","Sci-Fi","Thriller"]


@profile_bp.route("/profile")
@login_required
def profile():
    return redirect(url_for("profile.profile_user", username=current_user.username))


@profile_bp.route("/user/<username>")
def profile_user(username):
    user = User.query.filter_by(username=username).first_or_404()

    # Ultimele 12 ratinguri
    recent = (
        db.session.query(Rating, Movie)
        .join(Movie, Rating.movie_id == Movie.id)
        .filter(Rating.user_id == user.id)
        .order_by(Rating.timestamp.desc())
        .limit(12)
        .all()
    )

    # Statistici
    all_ratings = Rating.query.filter_by(user_id=user.id).all()
    total       = len(all_ratings)
    avg_given   = round(sum(r.rating for r in all_ratings) / total, 2) if total else 0

    # Gen preferat
    genre_counts = {}
    for r in all_ratings:
        movie = Movie.query.get(r.movie_id)
        if movie:
            for g in movie.genres_list():
                genre_counts[g] = genre_counts.get(g, 0) + 1
    fav_genre = max(genre_counts, key=genre_counts.get) if genre_counts else "—"

    # Distributia ratingurilor 1-5
    dist = {str(i): 0 for i in range(1, 6)}
    for r in all_ratings:
        key = str(int(r.rating))
        if key in dist:
            dist[key] += 1

    return render_template("profile/profile.html",
        user=user,
        recent=recent,
        total_ratings=total,
        avg_given=avg_given,
        fav_genre=fav_genre,
        rating_dist=dist,
        is_own=current_user.is_authenticated and current_user.id == user.id,
        avatar_colors=AVATAR_COLORS,
    )


@profile_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        action = request.form.get("action", "profile")

        if action == "profile":
            username = request.form.get("username", "").strip()
            bio      = request.form.get("bio", "").strip()
            location = request.form.get("location", "").strip()
            fav_genre = request.form.get("favorite_genre", "").strip()
            avatar_color = request.form.get("avatar_color", current_user.avatar_color)

            if username and username != current_user.username:
                if User.query.filter_by(username=username).first():
                    flash("Username-ul este deja folosit.", "danger")
                    return redirect(url_for("profile.settings"))
                current_user.username = username

            current_user.bio           = bio[:300] if bio else None
            current_user.location      = location[:100] if location else None
            current_user.favorite_genre = fav_genre if fav_genre in GENRES else None
            current_user.avatar_color  = avatar_color if avatar_color in AVATAR_COLORS else current_user.avatar_color

            db.session.commit()
            flash("Profil actualizat!", "success")

        elif action == "email":
            new_email = request.form.get("email", "").strip()
            password  = request.form.get("password_confirm", "")

            if not bcrypt.check_password_hash(current_user.password_hash, password):
                flash("Parola incorectă.", "danger")
                return redirect(url_for("profile.settings"))

            if User.query.filter_by(email=new_email).first():
                flash("Email-ul este deja folosit.", "danger")
                return redirect(url_for("profile.settings"))

            current_user.email = new_email
            db.session.commit()
            flash("Email actualizat!", "success")

        elif action == "password":
            current_pw  = request.form.get("current_password", "")
            new_pw      = request.form.get("new_password", "")
            confirm_pw  = request.form.get("confirm_password", "")

            if not bcrypt.check_password_hash(current_user.password_hash, current_pw):
                flash("Parola curentă este greșită.", "danger")
                return redirect(url_for("profile.settings"))

            if len(new_pw) < 6:
                flash("Parola nouă trebuie să aibă minim 6 caractere.", "danger")
                return redirect(url_for("profile.settings"))

            if new_pw != confirm_pw:
                flash("Parolele nu coincid.", "danger")
                return redirect(url_for("profile.settings"))

            current_user.password_hash = bcrypt.generate_password_hash(new_pw).decode("utf-8")
            db.session.commit()
            flash("Parolă schimbată cu succes!", "success")

        return redirect(url_for("profile.settings"))

    return render_template("profile/settings.html",
        genres=GENRES,
        avatar_colors=AVATAR_COLORS,
    )


@profile_bp.route("/api/profile/delete-rating/<int:movie_id>", methods=["DELETE"])
@login_required
def delete_rating(movie_id):
    rating = Rating.query.filter_by(
        user_id=current_user.id, movie_id=movie_id
    ).first_or_404()
    db.session.delete(rating)
    db.session.commit()

    # Recalculează media filmului
    movie = Movie.query.get(movie_id)
    if movie:
        all_r = Rating.query.filter_by(movie_id=movie_id).all()
        movie.avg_rating  = sum(r.rating for r in all_r) / len(all_r) if all_r else 0
        movie.num_ratings = len(all_r)
        db.session.commit()

    return jsonify({"success": True})


@profile_bp.route("/api/profile/stats")
@login_required
def stats_api():
    """Date pentru graficul radar de pe profil."""
    ratings = (
        db.session.query(Rating, Movie)
        .join(Movie, Rating.movie_id == Movie.id)
        .filter(Rating.user_id == current_user.id)
        .all()
    )

    genre_sums   = {}
    genre_counts = {}
    for r, m in ratings:
        for g in m.genres_list():
            genre_sums[g]   = genre_sums.get(g, 0) + r.rating
            genre_counts[g] = genre_counts.get(g, 0) + 1

    result = {g: round(genre_sums[g] / genre_counts[g], 2) for g in genre_sums}
    sorted_r = dict(sorted(result.items(), key=lambda x: x[1], reverse=True)[:10])

    return jsonify({"labels": list(sorted_r.keys()), "data": list(sorted_r.values())})

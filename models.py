from extensions import db, login_manager
from flask_login import UserMixin
from datetime import datetime


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    # Profil
    bio            = db.Column(db.Text)
    avatar_color   = db.Column(db.String(7), default="#e8000d")
    favorite_genre = db.Column(db.String(50))
    location       = db.Column(db.String(100))

    ratings = db.relationship("Rating", backref="user", lazy=True)

    @property
    def initials(self):
        parts = self.username.split("_")
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return self.username[:2].upper()

    def rating_count(self):
        return Rating.query.filter_by(user_id=self.id).count()

    def avg_given_rating(self):
        ratings = Rating.query.filter_by(user_id=self.id).all()
        if not ratings:
            return 0.0
        return round(sum(r.rating for r in ratings) / len(ratings), 2)


class Movie(db.Model):
    __tablename__ = "movies"
    id            = db.Column(db.Integer, primary_key=True)
    title         = db.Column(db.String(200), nullable=False)
    genres        = db.Column(db.String(200))
    year          = db.Column(db.Integer)
    avg_rating    = db.Column(db.Float, default=0.0)
    num_ratings   = db.Column(db.Integer, default=0)
    poster_url    = db.Column(db.String(500))
    overview      = db.Column(db.Text)
    cast          = db.Column(db.String(400))
    director_name = db.Column(db.String(150))

    ratings = db.relationship("Rating", backref="movie", lazy=True)

    def genres_list(self):
        return self.genres.split("|") if self.genres else []

    def clean_title(self):
        import re
        return re.sub(r'\s*\(\d{4}\)\s*$', '', self.title).strip()

    def to_dict(self):
        return {
            "id": self.id, "title": self.title,
            "genres": self.genres_list(), "year": self.year,
            "avg_rating": round(self.avg_rating, 2),
            "num_ratings": self.num_ratings,
            "poster_url": self.poster_url or "",
        }


class Rating(db.Model):
    __tablename__ = "ratings"
    id       = db.Column(db.Integer, primary_key=True)
    user_id  = db.Column(db.Integer, db.ForeignKey("users.id"),  nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.id"), nullable=False)
    rating   = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "movie_id"),)


class UpcomingMovie(db.Model):
    __tablename__ = "upcoming_movies"
    id           = db.Column(db.Integer, primary_key=True)
    title        = db.Column(db.String(200), nullable=False)
    tagline      = db.Column(db.String(300))
    description  = db.Column(db.Text)
    genres       = db.Column(db.String(200))
    release_date = db.Column(db.String(20))
    release_year = db.Column(db.Integer)

    director         = db.Column(db.String(150))
    director_past_avg = db.Column(db.Float)
    lead_actors      = db.Column(db.String(300))
    studio           = db.Column(db.String(100))
    budget_category  = db.Column(db.String(20))
    franchise        = db.Column(db.Boolean, default=False)
    sequel_number    = db.Column(db.Integer, default=1)

    predicted_rating      = db.Column(db.Float)
    prediction_confidence = db.Column(db.String(20))
    predicted_box_office  = db.Column(db.String(50))
    poster_color          = db.Column(db.String(7), default="#1a1a2e")
    poster_url            = db.Column(db.String(500))
    release_date_iso      = db.Column(db.String(10))  # YYYY-MM-DD for sorting
    added_at              = db.Column(db.DateTime, default=datetime.utcnow)

    def genres_list(self):
        return self.genres.split("|") if self.genres else []

    def to_dict(self):
        return {
            "id": self.id, "title": self.title, "tagline": self.tagline,
            "description": self.description, "genres": self.genres_list(),
            "release_date": self.release_date, "release_year": self.release_year,
            "director": self.director, "lead_actors": self.lead_actors,
            "studio": self.studio, "budget_category": self.budget_category,
            "franchise": self.franchise, "sequel_number": self.sequel_number,
            "predicted_rating": self.predicted_rating,
            "prediction_confidence": self.prediction_confidence,
            "predicted_box_office": self.predicted_box_office,
            "poster_color": self.poster_color,
        }

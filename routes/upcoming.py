from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from extensions import db
from models import UpcomingMovie
from ml.predictor import predict_upcoming

upcoming_bp = Blueprint("upcoming", __name__)


@upcoming_bp.route("/upcoming")
def upcoming():
    movies = UpcomingMovie.query.order_by(UpcomingMovie.release_date_iso.desc()).all()
    return render_template("upcoming.html", movies=movies)


@upcoming_bp.route("/upcoming/<int:movie_id>")
def upcoming_detail(movie_id):
    movie = UpcomingMovie.query.get_or_404(movie_id)
    return render_template("upcoming_detail.html", movie=movie)


@upcoming_bp.route("/api/upcoming/predict/<int:movie_id>", methods=["POST"])
def run_prediction(movie_id):
    """Ruleaza predictia pentru un film upcoming specific."""
    movie = UpcomingMovie.query.get_or_404(movie_id)

    result = predict_upcoming(
        genres=movie.genres,
        release_year=movie.release_year,
        budget_category=movie.budget_category,
        director_past_avg=movie.director_past_avg or 3.2,
        franchise=movie.franchise,
        sequel_number=movie.sequel_number or 1,
    )

    movie.predicted_rating = result["predicted_rating"]
    movie.prediction_confidence = result["confidence"]
    movie.predicted_box_office = result["box_office"]
    db.session.commit()

    return jsonify(result)


@upcoming_bp.route("/api/upcoming/add", methods=["POST"])
def add_upcoming():
    """Adauga un film viitor nou (pentru demo/testing)."""
    data = request.get_json()
    if not data or not data.get("title"):
        return jsonify({"error": "Titlul este obligatoriu"}), 400

    movie = UpcomingMovie(
        title=data["title"],
        tagline=data.get("tagline", ""),
        description=data.get("description", ""),
        genres=data.get("genres", "Drama"),
        release_date=data.get("release_date", "2026"),
        release_year=data.get("release_year", 2026),
        director=data.get("director", ""),
        director_past_avg=data.get("director_past_avg", 3.2),
        lead_actors=data.get("lead_actors", ""),
        studio=data.get("studio", ""),
        budget_category=data.get("budget_category", "medium"),
        franchise=data.get("franchise", False),
        sequel_number=data.get("sequel_number", 1),
        poster_color=data.get("poster_color", "#1a1a2e"),
    )

    # Ruleaza predictia automat la adaugare
    result = predict_upcoming(
        genres=movie.genres,
        release_year=movie.release_year,
        budget_category=movie.budget_category,
        director_past_avg=movie.director_past_avg,
        franchise=movie.franchise,
        sequel_number=movie.sequel_number,
    )
    movie.predicted_rating = result["predicted_rating"]
    movie.prediction_confidence = result["confidence"]
    movie.predicted_box_office = result["box_office"]

    db.session.add(movie)
    db.session.commit()
    return jsonify({"success": True, "id": movie.id, **result})


@upcoming_bp.route("/api/upcoming/seed", methods=["POST"])
def seed_upcoming():
    """Populeaza tabela cu filme upcoming REALE din TMDB.
    Daca TMDB nu e disponibil (fara internet/cheie), cade pe 6 filme demo fixe."""
    # 1) Incercam generarea reala din TMDB (cum era butonul initial)
    try:
        from setup_upcoming import run_seed
        added = run_seed(pages=5)
        if added > 0:
            return jsonify({"success": True, "added": added, "source": "tmdb"})
        # daca TMDB n-a intors nimic, cadem pe demo
    except Exception as e:
        # nu blocam butonul: logam si trecem la fallback-ul demo
        print(f"[seed] TMDB indisponibil, folosesc demo. Motiv: {e}")

    # 2) Fallback: cele 6 filme demo fixe (instant, fara internet)
    demo_films = [
        {
            "title": "Dune: Messiah",
            "tagline": "Imperiul va cadea. Profetul va arde.",
            "description": "Continuarea epopei sci-fi care urmareste ascensiunea si transformarea lui Paul Atreides intr-un lider mesianic al planetei Arrakis.",
            "genres": "Sci-Fi|Adventure|Drama",
            "release_date": "15 Noiembrie 2026",
            "release_year": 2026,
            "director": "Denis Villeneuve",
            "director_past_avg": 4.3,
            "lead_actors": "Timothée Chalamet, Zendaya, Florence Pugh",
            "studio": "Legendary Pictures",
            "budget_category": "blockbuster",
            "franchise": True,
            "sequel_number": 3,
            "poster_color": "#c8860a",
        },
        {
            "title": "The Midnight Atlas",
            "tagline": "Unele harti duc spre locuri din care nu te mai intorci.",
            "description": "O exploratoare descopereste un atlas secret care redeseneaza realitatea in jurul ei.",
            "genres": "Mystery|Thriller|Fantasy",
            "release_date": "7 Martie 2026",
            "release_year": 2026,
            "director": "Chloe Zhao",
            "director_past_avg": 3.9,
            "lead_actors": "Lupita Nyong'o, Oscar Isaac, Tilda Swinton",
            "studio": "A24",
            "budget_category": "medium",
            "franchise": False,
            "sequel_number": 1,
            "poster_color": "#1a3a5c",
        },
        {
            "title": "Avengers: Secret Wars",
            "tagline": "Toate universurile. Un singur razboi.",
            "description": "Eroii din toate universurile Marvel se confrunta cu amenintarea care ameninta sa stearga realitatea insasi.",
            "genres": "Action|Adventure|Sci-Fi",
            "release_date": "1 Mai 2027",
            "release_year": 2027,
            "director": "The Russo Brothers",
            "director_past_avg": 4.1,
            "lead_actors": "Robert Downey Jr., Chris Evans, Scarlett Johansson",
            "studio": "Marvel Studios",
            "budget_category": "blockbuster",
            "franchise": True,
            "sequel_number": 6,
            "poster_color": "#8b0000",
        },
        {
            "title": "Neon Requiem",
            "tagline": "In orasul care nu doarme niciodata, cineva trebuie sa plateasca.",
            "description": "Un detectiv din Neo-Tokyo investigheaza o serie de crime ce par imposibile intr-o lume in care amintirile pot fi vandute.",
            "genres": "Crime|Thriller|Sci-Fi",
            "release_date": "22 August 2026",
            "release_year": 2026,
            "director": "Park Chan-wook",
            "director_past_avg": 4.2,
            "lead_actors": "Mahershala Ali, Rinko Kikuchi, Dev Patel",
            "studio": "Focus Features",
            "budget_category": "high",
            "franchise": False,
            "sequel_number": 1,
            "poster_color": "#0d2137",
        },
        {
            "title": "The Last Cartographer",
            "tagline": "Ultimul care stie adevarul.",
            "description": "In secolul al XIX-lea, un cartograf descopera ca hartile pe care le deseneaza nu reprezinta lumea reala, ci o lume paralela.",
            "genres": "Adventure|Mystery|Drama",
            "release_date": "20 Februarie 2026",
            "release_year": 2026,
            "director": "Yorgos Lanthimos",
            "director_past_avg": 3.7,
            "lead_actors": "Olivia Colman, Andrew Garfield, Willem Dafoe",
            "studio": "Searchlight Pictures",
            "budget_category": "medium",
            "franchise": False,
            "sequel_number": 1,
            "poster_color": "#3d2b1f",
        },
        {
            "title": "Pulsar",
            "tagline": "Prima misiune. Ultima sansa.",
            "description": "O echipa de astronauti descopereste ca un pulsar misterios transmite un mesaj care schimba tot ce stiam despre originea vietii.",
            "genres": "Sci-Fi|Drama|Thriller",
            "release_date": "10 Iulie 2026",
            "release_year": 2026,
            "director": "Christopher Nolan",
            "director_past_avg": 4.4,
            "lead_actors": "Cillian Murphy, Anne Hathaway, Idris Elba",
            "studio": "Warner Bros",
            "budget_category": "blockbuster",
            "franchise": False,
            "sequel_number": 1,
            "poster_color": "#0a0a1a",
        },
    ]

    UpcomingMovie.query.delete()
    db.session.commit()

    for film_data in demo_films:
        result = predict_upcoming(
            genres=film_data["genres"],
            release_year=film_data["release_year"],
            budget_category=film_data["budget_category"],
            director_past_avg=film_data["director_past_avg"],
            franchise=film_data["franchise"],
            sequel_number=film_data["sequel_number"],
        )
        iso = f"{film_data['release_year']}-01-01"
        movie = UpcomingMovie(
            **{k: v for k, v in film_data.items()},
            release_date_iso=iso,
            predicted_rating=result["predicted_rating"],
            prediction_confidence=result["confidence"],
            predicted_box_office=result["box_office"],
        )
        db.session.add(movie)

    db.session.commit()
    return jsonify({"success": True, "added": len(demo_films), "source": "demo"})

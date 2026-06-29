"""
Fetch real upcoming movies from TMDB (release_date >= 2026-01-01) and populate
the upcoming_movies table with ML predictions.
Run from the cinematch directory: python setup_upcoming.py
"""
import os, sys, re, time, requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app import app
from extensions import db
from models import UpcomingMovie
from ml.predictor import predict_upcoming

API_KEY  = os.getenv("TMDB_API_KEY", "").strip()
BASE_URL = "https://api.themoviedb.org/3"
BASE_IMG = "https://image.tmdb.org/t/p/w500"
MIN_DATE = "2026-01-01"

GENRE_MAP = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy",
    80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Children",
    14: "Fantasy", 27: "Horror", 10402: "Musical", 9648: "Mystery",
    10749: "Romance", 878: "Sci-Fi", 53: "Thriller", 10752: "War", 37: "Western",
}

MONTHS_RO = {
    "01": "Ianuarie", "02": "Februarie", "03": "Martie", "04": "Aprilie",
    "05": "Mai", "06": "Iunie", "07": "Iulie", "08": "August",
    "09": "Septembrie", "10": "Octombrie", "11": "Noiembrie", "12": "Decembrie",
}

_ROMAN = {"II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}
_SEQUEL_RE = re.compile(r'\b(?:Part\s+)?([2-9]|II+|III|IV|V|VI|VII|VIII|IX|X)\b')


def detect_sequel_number(title):
    m = _SEQUEL_RE.search(title)
    if not m:
        return 1
    s = m.group(1)
    if s in _ROMAN:
        return _ROMAN[s]
    try:
        return int(s)
    except ValueError:
        return 2


def budget_from_tmdb(budget_usd, popularity):
    """Prefer actual TMDB budget; fall back to popularity heuristic."""
    if budget_usd and budget_usd > 0:
        if budget_usd >= 150_000_000: return "blockbuster"
        if budget_usd >= 60_000_000:  return "high"
        if budget_usd >= 15_000_000:  return "medium"
        return "low"
    if popularity >= 200: return "blockbuster"
    if popularity >= 80:  return "high"
    if popularity >= 30:  return "medium"
    return "low"


def format_date(iso_date):
    try:
        y, m, d = iso_date.split("-")
        return f"{int(d)} {MONTHS_RO[m]} {y}"
    except Exception:
        return iso_date


def fetch_pages(pages=5):
    results = []
    for page in range(1, pages + 1):
        resp = requests.get(
            f"{BASE_URL}/discover/movie",
            params={
                "api_key": API_KEY,
                "sort_by": "popularity.desc",
                "primary_release_date.gte": MIN_DATE,
                "page": page,
            },
            timeout=8,
        )
        if resp.status_code != 200:
            print(f"  [WARN] Page {page} returned {resp.status_code}")
            break
        data = resp.json()
        results.extend(data.get("results", []))
        if page >= data.get("total_pages", 1):
            break
        time.sleep(0.25)
    return results


def fetch_details(tmdb_id):
    """Single call: movie details + credits. Returns enriched dict."""
    resp = requests.get(
        f"{BASE_URL}/movie/{tmdb_id}",
        params={"api_key": API_KEY, "append_to_response": "credits"},
        timeout=8,
    )
    if resp.status_code != 200:
        return {}
    return resp.json()


def director_past_avg(director_name):
    if not director_name:
        return 3.2
    from models import Movie
    movies = Movie.query.filter(
        Movie.director_name == director_name, Movie.avg_rating > 0
    ).all()
    if movies:
        return round(sum(m.avg_rating for m in movies) / len(movies), 2)
    return 3.2


def run():
    if not API_KEY:
        print("[ERROR] TMDB_API_KEY not set in .env")
        sys.exit(1)

    print(f"[TMDB] Fetching upcoming movies (release >= {MIN_DATE})...")
    candidates = fetch_pages(pages=5)
    upcoming = [m for m in candidates if m.get("release_date", "") >= MIN_DATE]
    print(f"  {len(candidates)} total, {len(upcoming)} with release >= {MIN_DATE}")

    seen_ids, deduped = set(), []
    for item in upcoming:
        tid = item.get("id")
        if tid and tid not in seen_ids:
            seen_ids.add(tid)
            deduped.append(item)
    upcoming = deduped
    print(f"  After dedup: {len(upcoming)} unique movies")

    with app.app_context():
        UpcomingMovie.query.delete()
        db.session.commit()
        print("  Cleared existing upcoming_movies.")

        added = 0
        for item in upcoming:
            release_date = item.get("release_date", "")
            if not release_date or release_date < MIN_DATE:
                continue
            title = item.get("title", "").strip()
            if not title:
                continue

            # --- enriched details in one API call ---
            details = fetch_details(item["id"])
            time.sleep(0.25)

            release_year = int(release_date[:4])

            # Genres — prefer detailed genre list from /movie/{id}
            genre_objs  = details.get("genres") or []
            genre_ids   = item.get("genre_ids", [])
            if genre_objs:
                genres_str = "|".join(
                    GENRE_MAP[g["id"]] for g in genre_objs if g["id"] in GENRE_MAP
                ) or "Drama"
            else:
                genres_str = "|".join(
                    GENRE_MAP[g] for g in genre_ids if g in GENRE_MAP
                ) or "Drama"

            overview = (details.get("overview") or item.get("overview") or "")
            tagline  = details.get("tagline") or ""

            # Budget / studio
            budget_usd = details.get("budget") or 0
            popularity  = item.get("popularity", 10)
            bcat = budget_from_tmdb(budget_usd, popularity)

            studios = details.get("production_companies") or []
            studio  = studios[0]["name"] if studios else ""

            # Franchise & sequel
            collection   = details.get("belongs_to_collection")
            franchise    = collection is not None
            sequel_number = detect_sequel_number(title)

            # Credits
            credits   = details.get("credits") or {}
            cast_list = credits.get("cast") or []
            crew_list = credits.get("crew") or []
            cast      = ", ".join(m["name"] for m in cast_list[:3])
            director  = next(
                (m["name"] for m in crew_list if m.get("job") == "Director"), ""
            )
            past_avg = director_past_avg(director)

            # Poster
            poster_path = item.get("poster_path") or details.get("poster_path")
            poster_url  = (BASE_IMG + poster_path) if poster_path else None

            result = predict_upcoming(
                genres=genres_str,
                release_year=release_year,
                budget_category=bcat,
                director_past_avg=past_avg,
                franchise=franchise,
                sequel_number=sequel_number,
            )

            db.session.add(UpcomingMovie(
                title=title,
                tagline=tagline[:300] if tagline else "",
                description=overview[:500],
                genres=genres_str,
                release_date=format_date(release_date),
                release_date_iso=release_date,
                release_year=release_year,
                director=director,
                director_past_avg=past_avg,
                lead_actors=cast,
                studio=studio[:100] if studio else "",
                budget_category=bcat,
                franchise=franchise,
                sequel_number=sequel_number,
                predicted_rating=result["predicted_rating"],
                prediction_confidence=result["confidence"],
                predicted_box_office=result["box_office"],
                poster_color="#1a1a2e",
                poster_url=poster_url,
            ))
            added += 1
            if added % 20 == 0:
                db.session.commit()
                print(f"  Added {added} so far...")

        db.session.commit()
        print(f"\n[DONE] Added {added} upcoming movies.")

        print("\n[CHECK] Predictions sample (sorted by predicted rating):")
        samples = UpcomingMovie.query.order_by(UpcomingMovie.predicted_rating.desc()).limit(10).all()
        for m in samples:
            print(f"  {m.predicted_rating:.2f} ({m.prediction_confidence:6s}) | {m.budget_category:12s} | seq={m.sequel_number} | franchise={m.franchise} | {m.title}")


def run_seed(pages=5):
    """Versiune refolosibila din ruta Flask: aduce filme upcoming reale din
    TMDB si populeaza tabela. Presupune ca ruleaza deja intr-un app context.
    Returneaza numarul de filme adaugate. Ridica RuntimeError daca lipseste cheia."""
    if not API_KEY:
        raise RuntimeError("TMDB_API_KEY nu este setat in .env")

    candidates = fetch_pages(pages=pages)
    upcoming = [m for m in candidates if m.get("release_date", "") >= MIN_DATE]

    seen_ids, deduped = set(), []
    for item in upcoming:
        tid = item.get("id")
        if tid and tid not in seen_ids:
            seen_ids.add(tid)
            deduped.append(item)
    upcoming = deduped

    UpcomingMovie.query.delete()
    db.session.commit()

    added = 0
    for item in upcoming:
        release_date = item.get("release_date", "")
        if not release_date or release_date < MIN_DATE:
            continue
        title = item.get("title", "").strip()
        if not title:
            continue

        details = fetch_details(item["id"])
        time.sleep(0.25)

        release_year = int(release_date[:4])

        genre_objs = details.get("genres") or []
        genre_ids = item.get("genre_ids", [])
        if genre_objs:
            genres_str = "|".join(
                GENRE_MAP[g["id"]] for g in genre_objs if g["id"] in GENRE_MAP
            ) or "Drama"
        else:
            genres_str = "|".join(
                GENRE_MAP[g] for g in genre_ids if g in GENRE_MAP
            ) or "Drama"

        overview = (details.get("overview") or item.get("overview") or "")
        tagline = details.get("tagline") or ""

        budget_usd = details.get("budget") or 0
        popularity = item.get("popularity", 10)
        bcat = budget_from_tmdb(budget_usd, popularity)

        studios = details.get("production_companies") or []
        studio = studios[0]["name"] if studios else ""

        collection = details.get("belongs_to_collection")
        franchise = collection is not None
        sequel_number = detect_sequel_number(title)

        credits = details.get("credits") or {}
        cast_list = credits.get("cast") or []
        crew_list = credits.get("crew") or []
        cast = ", ".join(m["name"] for m in cast_list[:3])
        director = next(
            (m["name"] for m in crew_list if m.get("job") == "Director"), ""
        )
        past_avg = director_past_avg(director)

        poster_path = item.get("poster_path") or details.get("poster_path")
        poster_url = (BASE_IMG + poster_path) if poster_path else None

        result = predict_upcoming(
            genres=genres_str,
            release_year=release_year,
            budget_category=bcat,
            director_past_avg=past_avg,
            franchise=franchise,
            sequel_number=sequel_number,
        )

        db.session.add(UpcomingMovie(
            title=title,
            tagline=tagline[:300] if tagline else "",
            description=overview[:500],
            genres=genres_str,
            release_date=format_date(release_date),
            release_date_iso=release_date,
            release_year=release_year,
            director=director,
            director_past_avg=past_avg,
            lead_actors=cast,
            studio=studio[:100] if studio else "",
            budget_category=bcat,
            franchise=franchise,
            sequel_number=sequel_number,
            predicted_rating=result["predicted_rating"],
            prediction_confidence=result["confidence"],
            predicted_box_office=result["box_office"],
            poster_color="#1a1a2e",
            poster_url=poster_url,
        ))
        added += 1
        if added % 20 == 0:
            db.session.commit()

    db.session.commit()
    return added


if __name__ == "__main__":
    run()

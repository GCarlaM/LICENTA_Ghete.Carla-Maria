"""
Fetch popular recent movies (2023-2026) from TMDB and add them to the database.
Movies are assigned IDs starting at 2_000_000 to avoid conflicts with MovieLens IDs.
Run from the cinematch directory: python fetch_recent_movies.py
"""
import os, sys, time, requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app import app
from extensions import db
from models import Movie

API_KEY  = os.getenv("TMDB_API_KEY", "").strip()
BASE_IMG = "https://image.tmdb.org/t/p/w500"
BASE_URL = "https://api.themoviedb.org/3"
ID_OFFSET = 2_000_000  # keeps these IDs separate from MovieLens (max ~200k)

GENRE_MAP = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy",
    80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Children",
    14: "Fantasy", 36: "History", 27: "Horror", 10402: "Musical",
    9648: "Mystery", 10749: "Romance", 878: "Sci-Fi", 53: "Thriller",
    10752: "War", 37: "Western",
}


def get_pages(year, pages=5):
    movies = []
    for page in range(1, pages + 1):
        resp = requests.get(
            f"{BASE_URL}/discover/movie",
            params={
                "api_key": API_KEY,
                "sort_by": "popularity.desc",
                "primary_release_year": year,
                "vote_count.gte": 50,
                "vote_average.gte": 5.0,
                "page": page,
            },
            timeout=8,
        )
        if resp.status_code != 200:
            break
        data = resp.json()
        movies.extend(data.get("results", []))
        if page >= data.get("total_pages", 1):
            break
        time.sleep(0.25)
    return movies


def get_credits(tmdb_id):
    resp = requests.get(
        f"{BASE_URL}/movie/{tmdb_id}/credits",
        params={"api_key": API_KEY},
        timeout=8,
    )
    if resp.status_code != 200:
        return "", ""
    data = resp.json()
    cast = ", ".join(m["name"] for m in data.get("cast", [])[:5])
    director = next(
        (m["name"] for m in data.get("crew", []) if m.get("job") == "Director"), ""
    )
    return cast, director


def run():
    if not API_KEY:
        print("[ERROR] TMDB_API_KEY not set in .env")
        sys.exit(1)

    with app.app_context():
        added = skipped = 0

        for year in range(2023, 2027):
            print(f"\n[TMDB] Fetching {year} movies...")
            results = get_pages(year, pages=5)
            print(f"  Found {len(results)} candidates")

            for item in results:
                tmdb_id = item.get("id")
                if not tmdb_id:
                    continue

                movie_id = ID_OFFSET + tmdb_id
                if Movie.query.get(movie_id):
                    skipped += 1
                    continue

                release_date = item.get("release_date", "")
                release_year = int(release_date[:4]) if release_date and len(release_date) >= 4 else year

                genre_ids = item.get("genre_ids", [])
                genres_str = "|".join(GENRE_MAP[g] for g in genre_ids if g in GENRE_MAP)

                poster_path = item.get("poster_path")
                poster_url = (BASE_IMG + poster_path) if poster_path else None

                # TMDB uses 10-point scale; convert to 5-star
                avg_rating = round(item.get("vote_average", 0) / 2, 2)
                num_ratings = item.get("vote_count", 0)

                overview = item.get("overview", "") or ""
                title = f"{item['title']} ({release_year})"

                cast, director = get_credits(tmdb_id)
                time.sleep(0.25)

                movie = Movie(
                    id=movie_id,
                    title=title,
                    genres=genres_str,
                    year=release_year,
                    avg_rating=avg_rating,
                    num_ratings=num_ratings,
                    poster_url=poster_url,
                    overview=overview,
                    cast=cast,
                    director_name=director,
                )
                db.session.add(movie)
                added += 1

                if added % 20 == 0:
                    db.session.commit()
                    print(f"  Committed {added} so far...")

        db.session.commit()
        print(f"\n[DONE] Added: {added} | Already existed: {skipped}")


if __name__ == "__main__":
    run()

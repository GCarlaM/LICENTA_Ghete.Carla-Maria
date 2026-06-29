"""
Fetch poster_url + overview + cast de la TMDB folosind ID-urile din links.csv.
Foloseste direct tmdbId (mai rapid si mai precis decat search by name).

Rulare:
    cd cinematch
    python ml/poster_fetcher.py

Argumente optionale:
    --limit 500       (fetch doar primele N filme, default = toate)
    --batch 50        (dimensiunea batch-ului de commit, default = 50)
    --no-skip         (re-fetch chiar daca filmul are deja poster)
"""

import os, sys, time, argparse, requests, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app import app
from extensions import db
from models import Movie

API_KEY    = os.getenv("TMDB_API_KEY", "").strip()
BASE_IMG   = "https://image.tmdb.org/t/p/w500"
DETAIL_URL = "https://api.themoviedb.org/3/movie/{tmdb_id}"
LINKS_CSV  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "data", "ml-latest-small", "links.csv")


def fetch_movie_data(tmdb_id):
    try:
        resp = requests.get(
            DETAIL_URL.format(tmdb_id=tmdb_id),
            params={"api_key": API_KEY, "append_to_response": "credits", "language": "en-US"},
            timeout=8,
        )
        if resp.status_code == 429:
            print("  [RATE LIMIT] Astept 10s...")
            time.sleep(10)
            resp = requests.get(
                DETAIL_URL.format(tmdb_id=tmdb_id),
                params={"api_key": API_KEY, "append_to_response": "credits", "language": "en-US"},
                timeout=8,
            )
        if resp.status_code != 200:
            return None

        data = resp.json()
        poster_url = (BASE_IMG + data["poster_path"]) if data.get("poster_path") else None
        overview   = data.get("overview", "") or ""

        cast_list = [m.get("name","") for m in (data.get("credits",{}).get("cast") or [])[:5]]
        director  = next(
            (m.get("name","") for m in (data.get("credits",{}).get("crew") or []) if m.get("job")=="Director"),
            ""
        )

        return {"poster_url": poster_url, "overview": overview,
                "cast": ", ".join(cast_list), "director": director}
    except Exception as e:
        print(f"    [ERR] tmdb_id={tmdb_id}: {e}")
        return None


def run(limit=0, batch_size=50, skip_existing=True):
    if not API_KEY:
        print("[ERROR] TMDB_API_KEY nu e setat in .env"); sys.exit(1)

    if not os.path.exists(LINKS_CSV):
        print(f"[ERROR] Nu gasesc {LINKS_CSV}"); sys.exit(1)

    links_df = pd.read_csv(LINKS_CSV).dropna(subset=["tmdbId"])
    links_df["tmdbId"] = links_df["tmdbId"].astype(int)
    id_map = dict(zip(links_df["movieId"].astype(int), links_df["tmdbId"]))
    print(f"[OK] {len(id_map)} filme cu TMDB ID in links.csv")

    with app.app_context():
        query = Movie.query
        if skip_existing:
            query = query.filter((Movie.poster_url == None) | (Movie.poster_url == ""))
        if limit > 0:
            query = query.limit(limit)

        movies = query.all()
        total = len(movies)
        print(f"[OK] {total} filme de procesat")

        updated, skipped, batch = 0, 0, []

        for i, movie in enumerate(movies, 1):
            tmdb_id = id_map.get(movie.id)
            if not tmdb_id:
                skipped += 1
                continue

            data = fetch_movie_data(tmdb_id)
            if data:
                if data["poster_url"]:
                    movie.poster_url = data["poster_url"]
                if data["overview"]:
                    movie.overview = data["overview"]
                if hasattr(movie, "cast") and data["cast"]:
                    movie.cast = data["cast"]
                if hasattr(movie, "director_name") and data["director"]:
                    movie.director_name = data["director"]
                updated += 1
                batch.append(movie)
            else:
                skipped += 1

            if len(batch) >= batch_size:
                db.session.commit()
                batch = []
                print(f"  [{i}/{total}] Commit. Updated: {updated}, Skipped: {skipped}")

            time.sleep(0.26)

        if batch:
            db.session.commit()

        print(f"\n[DONE] Updated: {updated} | No TMDB ID: {skipped} | Total: {total}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit",   type=int, default=0)
    parser.add_argument("--batch",   type=int, default=50)
    parser.add_argument("--no-skip", action="store_true")
    args = parser.parse_args()
    run(limit=args.limit, batch_size=args.batch, skip_existing=not args.no_skip)

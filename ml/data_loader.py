import pandas as pd, os, re

_ARTICLE_RE = re.compile(
    r'^(.*?),\s*(The|A|An|Les|Le|La|El|Los|Las|Das|Der|Die|Den|Det|Il|Lo|Une|Un)\s+(\(.*\))$'
)

def normalize_title(title):
    m = _ARTICLE_RE.match(title)
    if m:
        return f"{m.group(2)} {m.group(1)} {m.group(3)}"
    return title

def load_movielens(app, db, Movie, data_path="data/ml-latest-small"):
    movies_path = os.path.join(data_path, "movies.csv")
    ratings_path = os.path.join(data_path, "ratings.csv")
    if not os.path.exists(movies_path):
        print(f"[ERROR] Nu gasesc {movies_path}. Descarca MovieLens!")
        return
    movies_df = pd.read_csv(movies_path)
    ratings_df = pd.read_csv(ratings_path)
    stats = ratings_df.groupby("movieId")["rating"].agg(["mean","count"]).reset_index()
    stats.columns = ["movieId","avg_rating","num_ratings"]
    df = movies_df.merge(stats, on="movieId", how="left")
    df["avg_rating"] = df["avg_rating"].fillna(0.0)
    df["num_ratings"] = df["num_ratings"].fillna(0).astype(int)
    with app.app_context():
        Movie.query.delete()
        db.session.commit()
        batch = []
        for _, row in df.iterrows():
            year_match = re.search(r"\((\d{4})\)", str(row["title"]))
            year = int(year_match.group(1)) if year_match else None
            batch.append(Movie(id=int(row["movieId"]), title=normalize_title(str(row["title"])),
                genres=str(row["genres"]), year=year,
                avg_rating=float(row["avg_rating"]), num_ratings=int(row["num_ratings"])))
            if len(batch) >= 500:
                db.session.bulk_save_objects(batch); db.session.commit(); batch = []
        if batch:
            db.session.bulk_save_objects(batch); db.session.commit()
    print(f"[OK] Importate {len(df)} filme.")

if __name__ == "__main__":
    import sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app import app
    from extensions import db
    from models import Movie
    with app.app_context():
      db.create_all()
      load_movielens(app, db, Movie)
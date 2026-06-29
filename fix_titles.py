"""
Fix movie titles in the existing database:
  "Shawshank Redemption, The (1994)" → "The Shawshank Redemption (1994)"
Preserves all other columns (poster_url, overview, cast, director_name, etc).
Run from the cinematch directory: python fix_titles.py
"""
import re, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from extensions import db
from models import Movie

_ARTICLE_RE = re.compile(
    r'^(.*?),\s*(The|A|An|Les|Le|La|El|Los|Las|Das|Der|Die|Den|Det|Il|Lo|Une|Un)\s+(\(.*\))$'
)

def normalize_title(title):
    m = _ARTICLE_RE.match(title)
    if m:
        return f"{m.group(2)} {m.group(1)} {m.group(3)}"
    return title

with app.app_context():
    movies = Movie.query.all()
    changed = 0
    for movie in movies:
        fixed = normalize_title(movie.title)
        if fixed != movie.title:
            movie.title = fixed
            changed += 1
    db.session.commit()
    print(f"Fixed {changed} titles out of {len(movies)} total.")

# Cum să adaugi postere la filme

## Setup rapid (recomandat)

Foloseste `setup_posters.py` — **nu necesita venv activ**, foloseste doar stdlib Python:

```bash
# Din folderul cinematch/
python setup_posters.py --limit 200
```

Aceasta fetch-uieste posterele pentru primele 200 de filme fara poster.

### Optiuni:
```bash
python setup_posters.py --limit 500     # primele 500 filme
python setup_posters.py --all           # TOATE filmele (~9700, dureaza ~45 min)
python setup_posters.py --no-skip       # re-fetch chiar daca au deja poster
```

## Setup complet (cu venv)

Daca ai venv activat:

```bash
# Activeaza venv
venv\Scripts\activate          # Windows
source venv/bin/activate        # Linux/Mac

# Fetch cu librarii Python
python ml/poster_fetcher.py --limit 500
python ml/poster_fetcher.py --all
```

## Ce face scriptul

1. Citeste `data/ml-latest-small/links.csv` pentru TMDB ID-urile filmelor
2. Fetch de la TMDB API: poster, descriere, cast (primii 5 actori), regizor
3. Salveaza in DB: `poster_url`, `overview`, `cast`, `director_name`

## Note

- API key TMDB trebuie sa fie in `.env`: `TMDB_API_KEY=cheia_ta`
- Rate limit: ~40 req/10s — scriptul asteapta 0.27s intre cereri (sigur)
- Filmele cu poster sunt afisate cu imagine; celelalte au placeholder 🎬
- Hero section afiseaza automat filmul cu cel mai bun rating care ARE poster

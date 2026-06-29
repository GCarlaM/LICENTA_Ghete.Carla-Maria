"""
Fetch postere + overview + cast + regizor de la TMDB pentru TOATE filmele.
Foloseste tmdbId din links.csv (precis, fara search).

RULARE (din folderul cinematch/, fara venv necesar):

    python setup_posters.py                  # fetch 500 filme (recomandat pt inceput)
    python setup_posters.py --limit 2000     # fetch 2000 filme
    python setup_posters.py --all            # fetch TOATE ~9700 filme (~45 min)
    python setup_posters.py --status         # arata cate filme au poster acum

TMDB rate limit: 40 req/10s. Scriptul asteapta 0.26s intre cereri (sigur).
Poti intrerupe oricand cu Ctrl+C - progresul e salvat automat dupa fiecare 100 filme.
"""

import os, sys, csv, json, time, sqlite3, argparse, urllib.request, urllib.error

ROOT      = os.path.dirname(os.path.abspath(__file__))
DB_PATH   = os.path.join(ROOT, "instance", "cinematch.db")
LINKS_CSV = os.path.join(ROOT, "data", "ml-latest-small", "links.csv")
ENV_FILE  = os.path.join(ROOT, ".env")
BASE_IMG  = "https://image.tmdb.org/t/p/w500"
API_URL   = "https://api.themoviedb.org/3/movie/{id}?api_key={key}&append_to_response=credits&language=en-US"


def get_api_key():
    if os.path.exists(ENV_FILE):
        for line in open(ENV_FILE).read().splitlines():
            if "TMDB_API_KEY" in line and "=" in line:
                return line.split("=", 1)[1].strip()
    return os.environ.get("TMDB_API_KEY", "").strip()


def load_links():
    result = {}
    with open(LINKS_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                mid = int(row["movieId"])
                tid = int(float(row["tmdbId"])) if row.get("tmdbId", "") else None
                if tid:
                    result[mid] = tid
            except (ValueError, KeyError):
                pass
    return result


def ensure_columns(conn):
    c = conn.cursor()
    for col, typ in [("cast", "VARCHAR(400)"), ("director_name", "VARCHAR(150)")]:
        try:
            c.execute(f"ALTER TABLE movies ADD COLUMN {col} {typ}")
            conn.commit()
        except Exception:
            pass


def fetch_tmdb(tmdb_id, api_key, retries=2):
    url = API_URL.format(id=tmdb_id, key=api_key)
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CineMatch/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())

            poster_url = (BASE_IMG + data["poster_path"]) if data.get("poster_path") else None
            overview   = (data.get("overview") or "").strip()
            credits    = data.get("credits") or {}
            cast_list  = [m["name"] for m in (credits.get("cast") or [])[:5] if m.get("name")]
            director   = next(
                (m["name"] for m in (credits.get("crew") or []) if m.get("job") == "Director"),
                ""
            )
            return {
                "poster_url":    poster_url,
                "overview":      overview or None,
                "cast":          ", ".join(cast_list) or None,
                "director_name": director or None,
            }

        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 12 * (attempt + 1)
                print(f"\n  [429] Rate limited. Astept {wait}s...", flush=True)
                time.sleep(wait)
            elif e.code == 404:
                return None
            else:
                if attempt < retries:
                    time.sleep(2)
                else:
                    return None
        except Exception:
            if attempt < retries:
                time.sleep(1)
            else:
                return None
    return None


def bar(done, total, width=30):
    pct  = done / total if total else 0
    fill = int(pct * width)
    return f"[{'█' * fill}{'░' * (width - fill)}] {done}/{total} ({pct*100:.1f}%)"


def show_status():
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("SELECT COUNT(*) FROM movies")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM movies WHERE poster_url IS NOT NULL AND poster_url != ''")
    with_poster = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM movies WHERE overview IS NOT NULL AND overview != ''")
    with_overview = c.fetchone()[0]
    conn.close()
    print(f"Total filme:      {total:>6}")
    print(f"Cu poster:        {with_poster:>6}  ({with_poster/total*100:.1f}%)")
    print(f"Cu descriere:     {with_overview:>6}  ({with_overview/total*100:.1f}%)")
    print(f"Fara poster:      {total - with_poster:>6}")


def run(limit=500, skip_existing=True, batch_size=100, delay=0.26):
    api_key = get_api_key()
    if not api_key:
        print("[ERROR] TMDB_API_KEY lipseste din .env")
        sys.exit(1)

    links = load_links()
    print(f"[OK] {len(links)} filme cu TMDB ID in links.csv")

    conn = sqlite3.connect(DB_PATH)
    ensure_columns(conn)
    c = conn.cursor()

    if skip_existing:
        c.execute("""
            SELECT id FROM movies
            WHERE (poster_url IS NULL OR poster_url = '')
            ORDER BY num_ratings DESC
        """)
    else:
        c.execute("SELECT id FROM movies ORDER BY num_ratings DESC")

    all_ids = [row[0] for row in c.fetchall()]
    if limit > 0:
        all_ids = all_ids[:limit]

    total         = len(all_ids)
    updated       = 0
    failed        = 0
    pending_count = 0
    start         = time.time()

    print(f"[OK] {total} filme de procesat (sortate dupa popularitate)")
    print(f"     Timp estimat: ~{total * delay / 60:.0f} minute\n")

    try:
        for i, movie_id in enumerate(all_ids, 1):                  # ← bucla for
            tmdb_id = links.get(movie_id)
            if not tmdb_id:                                         # ← in bucla
                failed += 1
            else:                                                   # ← in bucla
                data = fetch_tmdb(tmdb_id, api_key, retries=2)

                if data and (data["poster_url"] or data["overview"]):   # ← in bucla
                    c.execute("""
                        UPDATE movies SET
                            poster_url    = COALESCE(?, poster_url),
                            overview      = COALESCE(?, overview),
                            [cast]        = COALESCE(?, [cast]),
                            director_name = COALESCE(?, director_name)
                        WHERE id = ?
                    """, (
                        data["poster_url"],
                        data["overview"],
                        data["cast"],
                        data["director_name"],
                        movie_id,
                    ))
                    updated       += 1
                    pending_count += 1
                else:                                               # ← in bucla
                    failed += 1

                # Commit periodic - la fiecare batch_size filme reușite
                if pending_count >= batch_size:                     # ← in bucla
                    conn.commit()
                    pending_count = 0

            # Progress - la fiecare film (in sau out of tmdb)
            elapsed = time.time() - start                          # ← in bucla
            rate    = i / elapsed if elapsed > 0 else 1
            eta_s   = int((total - i) / rate)
            eta     = f"{eta_s // 60}m{eta_s % 60:02d}s"
            print(
                f"\r  {bar(i, total)}  updated={updated}  failed={failed}  ETA={eta}  ",
                end="", flush=True,
            )

            time.sleep(delay)                                       # ← in bucla

    except KeyboardInterrupt:
        print("\n\n[!] Intrerupt de utilizator. Salvez progresul...")

    # Commit final pentru ce a ramas nesalvat
    if pending_count > 0:
        conn.commit()

    conn.close()

    elapsed = int(time.time() - start)
    print(f"\n\n[DONE] Updated: {updated} | Failed/no-TMDB: {failed} | Timp: {elapsed // 60}m{elapsed % 60:02d}s")
    print("\nStatus curent:")
    show_status()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch postere TMDB pentru toate filmele",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--limit",   type=int,   default=500,
                        help="Max filme de procesat (default: 500)")
    parser.add_argument("--all",     action="store_true",
                        help="Fetch TOATE filmele (~9700, ~45 min)")
    parser.add_argument("--refetch", action="store_true",
                        help="Re-fetch chiar daca filmul are deja poster")
    parser.add_argument("--status",  action="store_true",
                        help="Arata statistici si iese")
    parser.add_argument("--delay",   type=float, default=0.26,
                        help="Delay intre cereri in secunde (default: 0.26)")
    args = parser.parse_args()

    if args.status:
        show_status()
        sys.exit(0)

    run(
        limit=0 if args.all else args.limit,
        skip_existing=not args.refetch,
        delay=args.delay,
    )

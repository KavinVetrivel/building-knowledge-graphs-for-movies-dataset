import kagglehub
import os
import pandas as pd
import ast
import json

# ── Load ──────────────────────────────────────────────────────────────────────
path = kagglehub.dataset_download("tmdb/tmdb-movie-metadata")

for name in os.listdir(path):
    filepath = os.path.join(path, name)
    if "movies" in name:
        movies = pd.read_csv(filepath)
    elif "credits" in name:
        credits = pd.read_csv(filepath)

# ── Merge on movie id ─────────────────────────────────────────────────────────
# movies uses 'id', credits uses 'movie_id'
df = movies.merge(credits, left_on="id", right_on="movie_id")
print(f"Merged: {df.shape}")

# ── Helper to parse JSON string columns ───────────────────────────────────────
def parse_col(val):
    try:
        return ast.literal_eval(val)
    except:
        return []

# ── 1. Movies table ───────────────────────────────────────────────────────────
movies_clean = df[["id", "title_x", "release_date", "vote_average", "vote_count", "popularity"]].copy()
movies_clean = movies_clean.rename(columns={"title_x": "title"})
movies_clean["year"] = pd.to_datetime(df["release_date"], errors="coerce").dt.year
movies_clean = movies_clean.drop(columns=["release_date"])
movies_clean = movies_clean.rename(columns={"id": "movie_id"})
movies_clean = movies_clean.dropna(subset=["movie_id"])
movies_clean["movie_id"] = movies_clean["movie_id"].astype(int)
print(f"Movies: {len(movies_clean)}")

# ── 2. Genres table + relationship table ─────────────────────────────────────
genres_rows = []
movie_genre_rows = []

for _, row in df.iterrows():
    for g in parse_col(row["genres"]):
        genres_rows.append({"genre_id": g["id"], "name": g["name"]})
        movie_genre_rows.append({"movie_id": int(row["id"]), "genre_id": g["id"]})

genres_clean = pd.DataFrame(genres_rows).drop_duplicates(subset=["genre_id"])
movie_genre = pd.DataFrame(movie_genre_rows).drop_duplicates()
print(f"Genres: {len(genres_clean)} | Movie-Genre links: {len(movie_genre)}")

# ── 3. Cast table + acted_in relationship ─────────────────────────────────────
persons_rows = []
acted_in_rows = []

for _, row in df.iterrows():
    for p in parse_col(row["cast"])[:10]:  # top 10 cast only — don't go crazy
        persons_rows.append({"person_id": p["id"], "name": p["name"]})
        acted_in_rows.append({
            "movie_id": int(row["id"]),
            "person_id": p["id"],
            "character": p.get("character", ""),
            "cast_order": p.get("order", 99)
        })

# ── 4. Crew table — directors only for now ────────────────────────────────────
directed_rows = []

for _, row in df.iterrows():
    for p in parse_col(row["crew"]):
        if p.get("job") == "Director":
            persons_rows.append({"person_id": p["id"], "name": p["name"]})
            directed_rows.append({
                "movie_id": int(row["id"]),
                "person_id": p["id"]
            })

persons_clean = pd.DataFrame(persons_rows).drop_duplicates(subset=["person_id"])
acted_in = pd.DataFrame(acted_in_rows).drop_duplicates()
directed = pd.DataFrame(directed_rows).drop_duplicates()

print(f"Persons: {len(persons_clean)}")
print(f"Acted-in links: {len(acted_in)}")
print(f"Directed links: {len(directed)}")

# ── Save to CSV ───────────────────────────────────────────────────────────────
out = "data"
os.makedirs(out, exist_ok=True)

movies_clean.to_csv(f"{out}/movies.csv", index=False)
genres_clean.to_csv(f"{out}/genres.csv", index=False)
persons_clean.to_csv(f"{out}/persons.csv", index=False)
movie_genre.to_csv(f"{out}/movie_genre.csv", index=False)
acted_in.to_csv(f"{out}/acted_in.csv", index=False)
directed.to_csv(f"{out}/directed.csv", index=False)

print("\nAll CSVs saved to /data folder")
print("\nSample movies:")
print(movies_clean.head(3))
print("\nSample acted_in:")
print(acted_in.head(3))




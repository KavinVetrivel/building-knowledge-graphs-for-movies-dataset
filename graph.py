from neo4j import GraphDatabase
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")

if not URI:
    raise ValueError("Missing NEO4J_URI in .env")

if not USER or not PASSWORD:
    raise ValueError("Missing NEO4J_USERNAME or NEO4J_PASSWORD in .env")

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def run(query, **kwargs):
    with driver.session() as session:
        session.run(query, **kwargs)

def run_read(query):
    with driver.session() as session:
        return session.run(query).data()

def load_batch(tx, query, batch):
    tx.run(query, rows=batch)

def load_df(df, query, batch_size=500):
    records = df.to_dict("records")
    with driver.session() as session:
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            session.execute_write(load_batch, query, batch)
            print(f"  loaded {min(i+batch_size, len(records))}/{len(records)}")

def run_query(query,data,**kwargs):
    with driver.session() as session:
        return session.run(query,name=name).data()

# ── Constraints ───────────────────────────────────────────────────────────────
print("Creating constraints...")
run("CREATE CONSTRAINT movie_id IF NOT EXISTS FOR (m:Movie) REQUIRE m.id IS UNIQUE")
run("CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE")
run("CREATE CONSTRAINT genre_id IF NOT EXISTS FOR (g:Genre) REQUIRE g.id IS UNIQUE")

# ── Load CSVs from disk into pandas ──────────────────────────────────────────
movies   = pd.read_csv(f"{DATA_DIR}/movies.csv")
genres   = pd.read_csv(f"{DATA_DIR}/genres.csv")
persons  = pd.read_csv(f"{DATA_DIR}/persons.csv")
mg       = pd.read_csv(f"{DATA_DIR}/movie_genre.csv")
acted_in = pd.read_csv(f"{DATA_DIR}/acted_in.csv")
directed = pd.read_csv(f"{DATA_DIR}/directed.csv")

# fix NaN → None so Neo4j doesn't choke
def clean(df):
    return df.where(pd.notnull(df), None)

movies   = clean(movies)
genres   = clean(genres)
persons  = clean(persons)
mg       = clean(mg)
acted_in = clean(acted_in)
directed = clean(directed)

# ── Movie nodes ───────────────────────────────────────────────────────────────
print("Loading Movies...")
load_df(movies, """
UNWIND $rows AS row
MERGE (m:Movie {id: toInteger(row.movie_id)})
SET m.title        = row.title,
    m.year         = toInteger(row.year),
    m.vote_average = toFloat(row.vote_average),
    m.popularity   = toFloat(row.popularity)
""")

# ── Genre nodes ───────────────────────────────────────────────────────────────
print("Loading Genres...")
load_df(genres, """
UNWIND $rows AS row
MERGE (g:Genre {id: toInteger(row.genre_id)})
SET g.name = row.name
""")

# ── Person nodes ──────────────────────────────────────────────────────────────
print("Loading Persons...")
load_df(persons, """
UNWIND $rows AS row
MERGE (p:Person {id: toInteger(row.person_id)})
SET p.name = row.name
""")

# ── HAS_GENRE relationships ───────────────────────────────────────────────────
print("Loading HAS_GENRE...")
load_df(mg, """
UNWIND $rows AS row
MATCH (m:Movie {id: toInteger(row.movie_id)})
MATCH (g:Genre {id: toInteger(row.genre_id)})
MERGE (m)-[:HAS_GENRE]->(g)
""")

# ── ACTED_IN relationships ────────────────────────────────────────────────────
print("Loading ACTED_IN...")
load_df(acted_in, """
UNWIND $rows AS row
MATCH (p:Person {id: toInteger(row.person_id)})
MATCH (m:Movie {id: toInteger(row.movie_id)})
MERGE (p)-[r:ACTED_IN]->(m)
SET r.character = row.character,
    r.order = toInteger(row.cast_order)
""")

# ── DIRECTED relationships ────────────────────────────────────────────────────
print("Loading DIRECTED...")
load_df(directed, """
UNWIND $rows AS row
MATCH (p:Person {id: toInteger(row.person_id)})
MATCH (m:Movie {id: toInteger(row.movie_id)})
MERGE (p)-[:DIRECTED]->(m)
""")

# ── Counts ────────────────────────────────────────────────────────────────────
print("\n── Node counts ──")
for label in ["Movie", "Person", "Genre"]:
    r = run_read(f"MATCH (n:{label}) RETURN count(n) AS count")
    print(f"  {label}: {r[0]['count']}")

print("\n── Relationship counts ──")
for rel in ["ACTED_IN", "DIRECTED", "HAS_GENRE"]:
    r = run_read(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS count")
    print(f"  {rel}: {r[0]['count']}")

# ── Test query ────────────────────────────────────────────────────────────────
print("\n── Test: The Dark Knight ──")
result = run_read("""
MATCH (m:Movie {title: 'The Dark Knight'})
OPTIONAL MATCH (p:Person)-[:ACTED_IN]->(m)
OPTIONAL MATCH (d:Person)-[:DIRECTED]->(m)
OPTIONAL MATCH (m)-[:HAS_GENRE]->(g:Genre)
RETURN m.title AS title,
       collect(DISTINCT p.name) AS cast,
       collect(DISTINCT d.name) AS directors,
       collect(DISTINCT g.name) AS genres
""")

if result:
    r = result[0]
    print(f"Title: {r['title']}")
    print(f"Directors: {r['directors']}")
    print(f"Cast: {r['cast']}")
    print(f"Genres: {r['genres']}")
else:
    print("Not found")

name = input("enter a actor name:")
print("costars of "+name+":")
response = run_query(
    '''match (p:Person {name: $name})-[:ACTED_IN]->(m:Movie)<-[:ACTED_IN]-(costar:Person) return DISTINCT costar.name limit 10''',name
)

print(response)
driver.close()
print("\nDone.")
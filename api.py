from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv


load_dotenv()

URI=os.getenv("URI")
AUTH=os.getenv("AUTH")

if not URI:
    raise RuntimeError("Missing required environment variable: URI")

if not AUTH:
    raise RuntimeError("Missing required environment variable: AUTH (expected user:password)")

if ":" not in AUTH:
    raise RuntimeError("Invalid AUTH format. Expected user:password")

auth_user, auth_password = AUTH.split(":", 1)

if not auth_user or not auth_password:
    raise RuntimeError("Invalid AUTH format. Both username and password are required")

driver = GraphDatabase.driver(URI,auth=(auth_user,auth_password))
app = FastAPI()


def query_run(query, **kwargs):
    with driver.session() as session:
        return session.run(query, **kwargs).data()


@app.get("/search")
def search_movie(title: str):
    response = query_run(
        '''match (m:Movie) where toLower(m.title) CONTAINS toLower($title) 
        return m.title as MovieTitle, m.year as Year, m.vote_average as Rating
        order by m.vote_average desc limit 100''',title=title
    )
    return response

@app.get("/details")
def movie_details(title: str):
    response = query_run(
        '''MATCH (m:Movie {title: $title})
        OPTIONAL MATCH (p:Person)-[r:ACTED_IN]->(m) WHERE r.order < 5
        OPTIONAL MATCH (d:Person)-[:DIRECTED]->(m)
        OPTIONAL MATCH (m)-[:HAS_GENRE]->(g:Genre)
        RETURN m.title AS MovieTitle, m.year AS Year, m.vote_average AS Rating,
               collect(DISTINCT p.name) AS Cast,
               collect(DISTINCT d.name) AS Directors,
               collect(DISTINCT g.name) AS Genres''',title=title
    )
    if not response:
        return {"error": "Movie not found"}
    return response[0]

@app.get("/recommend")
def recommend_movies(title:str):
    response = query_run(
        '''MATCH (m:Movie {title: $title})<-[:ACTED_IN]-(p:Person)-[:ACTED_IN]->(rec:Movie)
        WHERE rec <> m
        WITH rec, count(p) AS actor_overlap
        MATCH (m)-[:HAS_GENRE]->(g:Genre)<-[:HAS_GENRE]-(rec)
        WITH rec, actor_overlap, count(g) AS genre_overlap
        RETURN rec.title AS title,
               rec.vote_average AS rating,
               actor_overlap,
               genre_overlap,
               (actor_overlap * 2 + genre_overlap * 3) AS score
        ORDER BY score DESC LIMIT 100
    ''', title=title)
    return response

@app.get("/actor_info")
def actor_info(name:str):
    response = query_run(
        '''Match (p:Person {name:$name})-[r:ACTED_IN]->(m:Movie)
        WITH p, r, m
        ORDER BY m.year DESC
        WITH p, collect(m.title) as Movies, collect(r.character) as Characters
        RETURN p.name as Actor, Movies, Characters
        ''', name = name
    )
    return response

@app.get("/genre_list")
def genre_list():
    response = query_run(
        ''' Match (g:Genre)<-[:HAS_GENRE]-(m:Movie)
        return g.name as Genre, count(m) as MovieCount
        order by MovieCount desc
        ''')
    return response

@app.get("/movie_by_genre")
def movie_by_genre(genre:str):
    response = query_run(
        '''match (m:Movie)-[:HAS_GENRE]->(g:Genre {name:$genre})
        RETURN m.title AS title, m.year AS year, m.vote_average AS rating
        ORDER BY m.vote_average DESC LIMIT 100
    ''', genre=genre)
    return response

app.mount("/static", StaticFiles(directory="static"),name="static")

@app.get("/")
def root():
    return FileResponse("static/index.html")

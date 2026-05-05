from neo4j import GraphDatabase
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

URI = os.getenv("URI")
AUTH = os.getenv("AUTH")
auth_user,sep,auth_password = AUTH.partition(":")

driver = GraphDatabase.driver(URI,auth=(auth_user,auth_password))

DATA_DIR = os.path.join(os.path.dirname(__file__),"data")

def run(query,**kwargs):
    with driver.session() as session:
        return session.run(query,**kwargs).data()


def search_movie(title):
    response = run(
        '''match (m:Movie) where toLower(m.title)=toLower($title) return m.title, m.year''',title=title
    )
    print("Is this the movie you are looking for?")
    for r in response:
        print(f"{r['m.title']} ({r['m.year']})")

def fetch_movie_details(title):
    response = run(
        '''MATCH (m:Movie {title: $title})
        OPTIONAL MATCH (p:Person)-[r:ACTED_IN]->(m) WHERE r.order < 5
        OPTIONAL MATCH (d:Person)-[:DIRECTED]->(m)
        OPTIONAL MATCH (m)-[:HAS_GENRE]->(g:Genre)
        RETURN m.title, m.year, m.vote_average,
               collect(DISTINCT p.name) AS cast,
               collect(DISTINCT d.name) AS directors,
               collect(DISTINCT g.name) AS genres''',title=title
    )
    if not response:
        print("Not found")
        return
    r = response[0]
    print(f"\n{r['m.title']} ({r['m.year']}) ⭐ {r['m.vote_average']}")
    print(f"Directors : {', '.join(r['directors'])}")
    print(f"Cast      : {', '.join(r['cast'])}")
    print(f"Genres    : {', '.join(r['genres'])}")

def recommendor(title):
    response = run(
        '''MATCH (m:Movie {title: $title})<-[:ACTED_IN]-(p:Person)-[:ACTED_IN]->(rec:Movie)
        WHERE rec <> m
        WITH rec, count(p) AS shared
        RETURN rec.title AS title, rec.vote_average AS rating, shared
        ORDER BY shared DESC, rating DESC
        LIMIT 5''',
        title=title
    )
    
    print(f"If you liked {title}, you might also like:\n")
    
    for r in response:
        print(f"{r['title']} (Rating: {r['rating']})")

print("Movie explorer graph")
print("CMDS: Search, Details, Recommend, Exit\n")

while True:
    cmd = input("> ").strip().lower()
    if cmd == "exit":
        break
    elif cmd == "search":
        title = input("Enter the movie title: ")
        search_movie(title)
    elif cmd == "details":
        title = input("Enter the movie title: ")
        fetch_movie_details(title)
    elif cmd == "recommend":
        title = input("Enter the movie title: ")
        recommendor(title)
    else:
        print("Unknown command. Please try again.")

driver.close()
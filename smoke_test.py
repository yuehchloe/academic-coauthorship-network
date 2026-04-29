"""Smoke test: verify the class skeletons wire up correctly using synthetic data.

This is NOT the test suite — that comes later. This is just a sanity check
that the imports work and the classes interact as designed.
"""

import sys
sys.path.insert(0, "/home/claude/intellectual_monopolies")

from src.researcher import Researcher
from src.publication import Publication
from src.graph import CollaborationGraph
from src.query_engine import QueryEngine

# Build a tiny synthetic information-economics network.
# Akerlof <-> Stiglitz <-> Spence (the Nobel trio), plus a few satellites.
authors = {
    "akerlof":  Researcher("akerlof",  "George Akerlof",   "Berkeley",       50000, 60),
    "stiglitz": Researcher("stiglitz", "Joseph Stiglitz",  "Columbia",      120000, 80),
    "spence":   Researcher("spence",   "Michael Spence",   "Stanford",       40000, 55),
    "rothschild": Researcher("rothschild", "Michael Rothschild", "Princeton", 12000, 40),
    "myerson":  Researcher("myerson",  "Roger Myerson",    "Chicago",        25000, 50),
    "satellite_a": Researcher("satellite_a", "A. Coauthor", "MIT",            2000, 20),
}

papers = [
    Publication("p1", "Asymmetric Information Reconsidered", 2018,
                ["akerlof", "stiglitz"], "AER", 200,
                "We revisit the lemons problem..."),
    Publication("p2", "Signaling in Modern Markets", 2019,
                ["stiglitz", "spence"], "QJE", 150,
                "Job market signaling extended..."),
    Publication("p3", "Adverse Selection and Equilibrium", 2020,
                ["stiglitz", "rothschild"], "Econometrica", 100,
                "The classic 1976 framework..."),
    Publication("p4", "Mechanism Design Survey", 2021,
                ["myerson", "satellite_a"], "JEL", 80, None),
    Publication("p5", "Solo Paper", 2022, ["akerlof"], "AER", 30, None),
    Publication("p6", "Three-author Collaboration", 2017,
                ["akerlof", "stiglitz", "spence"], "AER", 250, None),
]

# --- Build the graph ---
g = CollaborationGraph()
for a in authors.values():
    g.add_researcher(a)
for p in papers:
    g.add_publication(p)

print("=== Graph stats ===")
print(g)
print(g.stats())
print()

# --- QueryEngine round trip ---
engine = QueryEngine(g)

print("=== Search 'stigli' ===")
for r in engine.search("stigli"):
    print(" ", r)
print()

print("=== Profile of Stiglitz ===")
profile = engine.profile("stiglitz")
print("  Researcher:", profile.researcher)
print("  Centrality:", {k: round(v, 3) for k, v in profile.researcher.centrality.items()})
print("  Centrality ranks:", profile.centrality_rank)
print("  Top collaborators:")
for r, w in profile.top_collaborators:
    print(f"    {r.name} ({w} shared papers)")
print()

print("=== Path: Akerlof -> Myerson ===")
path = engine.find_path("akerlof", "myerson")
if path.found:
    print(f"  Distance: {path.distance}")
    for i, r in enumerate(path.researchers):
        print(f"    [{i}] {r.name}")
    for i, papers_on_edge in enumerate(path.bridging_papers):
        titles = [p.title for p in papers_on_edge]
        print(f"  Edge {i}: {titles}")
else:
    print("  No path found.")
print()

print("=== Top 5 by betweenness ===")
for r in engine.top_central("betweenness", 5):
    print(f"  {r.name}: {r.centrality['betweenness']:.4f}")
print()

print("=== Year filter 2018-2020 ===")
filtered = engine.filter_by_year(2018, 2020)
print("  Filtered stats:", filtered.corpus_summary())
print()

print("=== Serialization round trip ===")
r_dict = authors["stiglitz"].to_dict()
r_back = Researcher.from_dict(r_dict)
assert r_back == authors["stiglitz"]
print("  Researcher round-trips:", r_back)

p_dict = papers[0].to_dict()
p_back = Publication.from_dict(p_dict)
assert p_back == papers[0]
print("  Publication round-trips:", p_back)
print()

print("All smoke tests passed.")

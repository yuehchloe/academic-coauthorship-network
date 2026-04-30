# Information Economics Co-authorship Network

A network analysis tool for the co-authorship structure of information
economics research, 2015–2025. Nodes are individual researchers. Edges
connect any two researchers who co-authored at least one paper in the
corpus, weighted by the number of shared papers.

Built for SI 507 (Intermediate Programming) at University of Michigan.

---

## What it does

The app provides four interaction modes for exploring the network:

**Search & Query**: look up any researcher in the corpus. Displays
citation count, h-index, centrality ranks across four measures (degree,
betweenness, eigenvector, closeness), top collaborators, and papers.

**Pathfinding**: find the shortest collaboration chain between two
researchers (Erdős-number style). Renders the path as a visual chain
with the bridging papers on each hop. Restricted to the core network
(largest connected component) where paths exist. Includes a year filter
to see how the network changes across time periods.

**Rankings**: top researchers by each centrality measure, side by side.
The divergence between betweenness and degree rankings is the headline
finding: researchers who bridge subfields are not the same people as
those who collaborate most prolifically.

**Overview**: corpus statistics and a summary of the network structure.

---
## Streamlit App

https://academic-collaboration-network.streamlit.app/

If the link doesn't work, please follow the instructions below to run a local version of the app.
---

## Installation

Requires Python 3.10+.

```bash
git clone <your-repo-url>
cd academic-coauthorship-network
pip install -r requirements.txt
```

---

## Quick start (with included corpus)

The repository ships with a pre-built corpus at `data/corpus.json` and
cached Semantic Scholar API responses at `data/cache/`. To run the app
without rebuilding anything:

\```bash
pip install -r requirements.txt
streamlit run app.py
\```

The corpus contains roughly N papers and N researchers spanning 2015 to
2025, built via the pipeline described in METHODOLOGY.md. The cache is
included so that anyone who wants to verify the pipeline can re-run
`scripts/pull_corpus.py` without needing an API key. All cache hits are
instant; no API calls will be made unless the cache is missing entries.

---

## Rebuilding the corpus from scratch

You only need this if you want to verify the pipeline against a fresh
S2 fetch, or if you want to extend the corpus with new seed authors
or a different year range.

1. Get a Semantic Scholar API key at
   https://www.semanticscholar.org/product/api#api-key-form
2. Set it as an environment variable: `export S2_API_KEY="your-key"`
3. Delete the cache: `rm -rf data/cache/`
4. Run: `python scripts/pull_corpus.py`

This takes 20 to 40 minutes and makes 500 to 800 API calls. The script
respects S2's 1 RPS rate limit but you may still encounter occasional
429 responses, especially if running shortly after a previous attempt.
The script will retry with exponential backoff.

---

**What the corpus builder does:**

The pipeline has five stages:

1. Resolves 22 seed authors (the canonical information-economics
   researchers — Akerlof, Spence, Stiglitz, Holmström, Myerson, and
   others) to Semantic Scholar author IDs.
2. Fetches each seed author's papers, filtered to top-tier economics
   journals and the 2015–2025 window.
3. Expands to the seed authors' co-authors and fetches their papers
   under the same strict filter (second-hop expansion). This connects
   the seed authors' neighborhoods to the broader field.
4. Fetches papers that cite each seed paper, filtered by year only
   (venue filter relaxed at this stage to avoid over-pruning).
5. Builds and persists the graph with centrality measures pre-computed.

See `METHODOLOGY.md` for a full account of the design decisions,
including three corpus-building strategies that were tried and failed
before the current approach.

---

## Running the app

```bash
streamlit run app.py
```

Opens at http://localhost:8501.

On first load the corpus is read and the graph is built in memory.
This takes a few seconds. Subsequent navigation is instant.

---

## Running the tests

```bash
python -m pytest tests/ -v
```

244 tests across 6 files. No network calls — all API interactions are
mocked. Tests cover class behavior, graph construction, pathfinding edge
cases, venue matching, and the full query engine. Reading the test suite
is a good way to understand what the system does.

---

## Project structure

```
academic-coauthorship-network/
├── app.py                  Streamlit application
├── validate.py             Single-author API validation script
├── smoke_test.py           Synthetic-data sanity check
├── METHODOLOGY.md          Corpus construction methodology and findings
├── README.md               This file
├── requirements.txt
│
├── src/
│   ├── researcher.py       Researcher class (graph node)
│   ├── publication.py      Publication class (edge source)
│   ├── graph.py            CollaborationGraph (wraps networkx)
│   ├── data_loader.py      Semantic Scholar API layer with caching
│   ├── query_engine.py     Facade over the graph — four interaction modes
│   ├── venues.py           Economics venue allowlist with match modes
│   └── seed_authors.py     22 seed authors with annotations
│
├── scripts/
│   └── pull_corpus.py      Five-stage corpus builder
│
├── tests/
│   ├── test_researcher.py
│   ├── test_publication.py
│   ├── test_graph.py
│   ├── test_data_loader.py
│   ├── test_query_engine.py
│   └── test_venues.py
│
└── data/
    ├── corpus.json         Built by pull_corpus.py — gitignored
    └── cache/              API response cache — gitignored
```

---

## Interpreting the findings

**Centrality measures** capture different kinds of structural importance:

- **Degree** counts direct collaborators. High-degree authors are
  prolific collaborators.
- **Betweenness** measures how often an author sits on the shortest
  path between two other authors. High-betweenness authors bridge
  otherwise-disconnected subfields — these are the structural
  gatekeepers.
- **Eigenvector** weights connections by the importance of collaborators.
  High-eigenvector authors collaborate with the most-connected people.
- **Closeness** measures how quickly an author can reach anyone else
  in the network. High-closeness authors are the most efficient
  broadcasters of ideas.

**The key finding:** the top-10 by betweenness and the top-10 by degree
are largely different people. Researchers who bridge subfields are not
the same as researchers who collaborate most. This argues against a
simple "monopoly" model of the field: there is no single elite whose
members dominate on every dimension. Instead, information economics has
structurally distinct roles — prolific collaborators, subfield bridges,
and status hubs — occupied by different researchers.

**The fragmented graph** (roughly 11–15% of researchers in the main
connected component) is itself a finding. Information economics is not
one tightly-knit community but a collection of overlapping clusters,
each anchored by different methodological traditions (mechanism design,
information design, contract theory, rational inattention).

**The core network** (largest connected component) represents the
contemporary active frontier of the field. Researchers outside it —
including some Nobel laureates — publish in the field but are not
connected to the main collaborative cluster via papers in this
corpus's time window. The founding generation and the active frontier
have diverged.

---

## Data source

Paper and author metadata from the
[Semantic Scholar Academic Graph API](https://www.semanticscholar.org/product/api).
Semantic Scholar is a free, AI-powered research tool from the Allen
Institute for AI.

Venue filtering uses a curated allowlist of ~36 top-tier economics
journals. See `src/venues.py` for the full list and `METHODOLOGY.md`
for the justification.

---

## Known limitations

- **Author disambiguation.** Semantic Scholar sometimes splits one
  researcher into multiple records. The loader picks the most-cited
  candidate for seed authors, but duplicates may remain for others.
- **Affiliation data.** S2 affiliation records are sparse. Many
  researchers show "affiliation unknown" even when they are
  well-known faculty.
- **Seed-list bias.** Centrality scores for seed authors are elevated
  by construction — the corpus is built from their output. Non-seed
  authors with high centrality are the more informative finding.
- **Year window.** The 2015–2025 window captures the contemporary
  frontier but excludes foundational papers (Akerlof 1970, Spence
  1973, Mirrlees 1971). Older authors whose active period preceded
  this window are underrepresented.

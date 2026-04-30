# Corpus Construction Methodology

This document describes the data pipeline used to build the co-authorship network for this project, including the strategies that failed, why they failed, and the rationale for the final approach. Written as part of the project submission to document methodological decisions and their tradeoffs.

---

## What the corpus is trying to represent

The project studies the co-authorship network of **information economics**: the subfield of microeconomic theory that studies how the distribution of information across agents affects behavior, contracts, market outcomes, and welfare. The five canonical problem types are:

1. **Hidden information** — adverse selection, screening, market unraveling
   (Akerlof, Rothschild-Stiglitz)
2. **Hidden action** — moral hazard, principal-agent problems
   (Holmström, Mirrlees)
3. **Signaling and communication** — job market signaling, cheap talk
   (Spence, Crawford-Sobel)
4. **Mechanism design** — auction theory, revelation principle, optimal
   contracts (Myerson, Maskin, Milgrom, Wilson)
5. **Information design** — Bayesian persuasion, rational inattention
   (Kamenica-Gentzkow, Bergemann-Morris, Sims, Matějka)

The corpus should contain papers that belong to this subfield, published in legitimate economics venues, within a 2015–2025 window that captures the active research frontier.

---

## Strategy 1 — Keyword search, no filter

**What we tried:** Semantic Scholar's `/paper/search/bulk` endpoint with queries like `"asymmetric information"`, `"adverse selection"`, `"mechanism design"`. Limit of 1,000 papers per query.

**What happened:** The top result for `"asymmetric information"` was *"When Are Two Lists Better than One?: Benefits and Harms in Joint
Decision-making"* from the **AAAI Conference on Artificial Intelligence**.
Inspection of the first 20 results showed papers from machine learning,
signal processing, communications engineering, and operations research —
all of which use the phrase "asymmetric information" in non-economics senses.

**Why it failed:** Semantic Scholar's relevance ranking treats queries as
bag-of-words matches across all disciplines. The phrase "asymmetric
information" is shared across many fields. Without a discipline filter, the
1,000-result cap fills with off-topic papers before reaching much of the
economics literature.

---

## Strategy 2 — Keyword search with `fields_of_study=Economics`

**What we tried:** Added `fields_of_study=["Economics"]` as a server-side
filter, relying on Semantic Scholar's automatic field-of-study tagging.

**What happened:** Fetching 1,000 papers for `"moral hazard"` with the
Economics tag returned 1,000 results. Inspection of the venue distribution
showed:
- 547/1000 papers had **no venue at all** (preprints, working papers,
  theses, gray literature from SSRN, institutional repositories)
- Remaining named venues included *PLoS ONE*, *Sustainability*,
  *At-tijaroh: Jurnal Ilmu Manajemen*, and similar non-economics outlets

**Why it failed:** Semantic Scholar's `Economics` field tag is imprecise.
It is applied to any paper with economic themes, including business school
working papers, finance preprints, regional development studies, health
economics from medical journals, and papers from low-tier or predatory
journals. The tag does not distinguish between top-tier economic theory
and adjacent applied work.

---

## Strategy 3 — Keyword search with venue allowlist

**What we tried:** Maintained the `fields_of_study=["Economics"]` filter
and added a client-side venue allowlist: a set of ~36 patterns matching
the names of top-tier economics journals (AER, Econometrica, QJE, JPE,
RES, JET, Games and Economic Behavior, RAND Journal of Economics, and
approximately 30 others). Papers whose `publicationVenue.name` or `venue`
field did not match any allowlist pattern were dropped after fetch.

The allowlist used three match modes to handle naming variants:
- `exact` — for journals where substring matching risks false positives
  (e.g., `"Theoretical Economics"` must not match
  `"Theoretical Economics Letters"`)
- `prefix` — for journals with trailing variants
  (e.g., `"American Economic Review"` should match
  `"American Economic Review: Insights"`)
- `substring` — for journal families
  (e.g., `"American Economic Journal"` matches all four AEJ subtitles)

The allowlist also strips leading `"The "` before matching, after
discovering that Semantic Scholar inconsistently includes and omits it
(e.g., `"The American Economic Review"` and `"American Economic Review"`
refer to the same journal but would fail exact or prefix matching without
this normalization).

**Specific false positives caught and excluded during development:**
- *Theoretical Economics Letters* — a separate, lower-quality journal
  that is not the same as *Theoretical Economics*
- *Economic Theory Bulletin* — not the same as *Economic Theory*
- *Eastern Economic Journal* — not a target venue; leaked through
  under an earlier substring-only matching scheme

**What happened:** Applied across 12 keyword queries, the strategy
produced **331 unique papers** from 658 unique authors. Venue distribution
was clean — AER, JPE, Econometrica, Theoretical Economics, AEJ:
Microeconomics, Journal of Public Economics, and similar outlets dominated.
Paper titles were recognizably information-economics work.

**Why it still failed:** Despite the clean corpus, the resulting graph had
**269 connected components on 658 nodes**, with a largest component of only
19 authors (3% of the graph). Betweenness centrality scores were all near
zero. The four interaction modes required by the project — particularly
pathfinding and meaningful centrality rankings — depend on a reasonably
connected graph.

**Root cause:** Information economics is a theory-heavy subfield where a
prolific author might publish 3–8 papers per year but collaborate with
different co-authors on each. In a 10-year window, most authors appear in
only one paper within the corpus, forming isolated dyads or singletons.
Keyword search retrieves a sparse, cross-sectional sample; it does not
retrieve the full collaboration neighborhood of any given researcher.

Broadening the keyword set (from 6 to 12 queries) and widening the venue
allowlist (from ~20 to ~36 patterns) increased the corpus modestly but
did not improve graph connectivity, confirming that the fragmentation was
structural rather than a filtering artifact.

---

## Final strategy — Author-anchored citation-graph expansion

**Rationale:** The fragmentation problem has a structural cause that keyword
search cannot fix. To build a connected graph, we need not a cross-sectional
sample of the literature but the *collaboration neighborhood* of a defined
research community. Citation expansion achieves this: starting from a set of
seed authors, we pull all their papers, then pull the papers that cite each
seed paper. Authors who cite the same foundational work are likely to know
each other and collaborate, producing denser connectivity than a keyword
sample.

**Acknowledged limitation:** Because the corpus is built around seed author
output, seed authors will tend to rank highly on centrality measures. The
more interesting finding is which *non-seed* authors rise to high centrality
— those are the researchers who are central to the field without being
among its Nobel-recognized founders.

**Seed author selection (22 authors):**

| Author | Rationale |
|--------|-----------|
| George Akerlof | Lemons paper; foundational adverse selection; Nobel 2001 |
| Michael Spence | Job market signaling; Nobel 2001 |
| Joseph Stiglitz | Screening, credit rationing, Grossman-Stiglitz; Nobel 2001 |
| Roger Myerson | Revelation principle, optimal auctions; Nobel 2007 |
| Eric Maskin | Implementation theory; Nobel 2007 |
| Paul Milgrom | Auction theory, mechanism design; Nobel 2020 |
| Robert Wilson | Auction theory; Nobel 2020 |
| Bengt Holmström | Moral hazard, contract theory; Nobel 2016 |
| Oliver Hart | Incomplete contracts; Nobel 2016 |
| Jean Tirole | Contract theory, regulation, IO; Nobel 2014 |
| Vijay Krishna | Auction theory; canonical textbook author |
| Emir Kamenica | Kamenica-Gentzkow Bayesian persuasion |
| Dirk Bergemann | Information design, robust mechanism design |
| Stephen Morris | Global games, information design |
| Filip Matějka | Rational inattention |
| Ilya Segal | Mechanism design, contract theory |
| Philipp Strack | Information design, mechanism design |
| Doron Ravid | Information design (Chicago Booth) |
| Susan Athey | Mechanism design and applied work |
| Jean-Charles Rochet | Insurance, contract theory, two-sided markets |
| Yan Chen | Experimental mechanism design (name disambiguation risk noted) |
| Alain Cohn | Behavioral economics adjacent to information and trust |

Akerlof and Spence are included for completeness despite their limited
recent output: the Nobel trio (Akerlof, Spence, Stiglitz) defines the
founding of the field and their absence from the seed list would be
a notable gap.

The following were considered and excluded:
- **Tim Roughgarden, Noam Nisan** — algorithmic mechanism design; publish
  primarily in CS venues outside the economics allowlist
- **Christopher Sims** — most output is macroeconometrics; rational
  inattention covered by Matějka

**Pipeline (four stages):**

1. **Resolve** each seed author name to a Semantic Scholar `authorId` via
   `/author/search`. Disambiguation uses citation count as a proxy for
   the most prominent researcher with a given name.

2. **Fetch seed papers** via `/author/{id}/papers` for each resolved
   author, filtered to 2015–2025 and to the economics venue allowlist.

3. **Expand via citations** via `/paper/{id}/citations` for each seed
   paper, filtered to 2015–2025 and the venue allowlist. This is the
   step that creates graph density: a seed paper with 100 citations in
   econ venues adds up to 100 new papers and their author sets.

4. **Build and analyze** the graph: construct `CollaborationGraph` from
   all deduplicated papers, batch-fetch author metadata, compute
   centrality.

---

## Corpus definition

A paper is included if and only if:
- It is authored by a seed author, OR it cites a paper authored by a seed
  author
- Its venue name matches the economics allowlist (exact/prefix/substring
  match with leading-`"The"`-stripped normalization, as described above)
- Its publication year is in [2015, 2025]
- Its Semantic Scholar record includes a `paperId` and `title`

---

## Venue allowlist

The allowlist covers approximately 36 journals where information-economics,
game theory, mechanism design, contract theory, and adjacent applied work
appears. It is defined in `src/venues.py` and tested in
`tests/test_venues.py`.

Explicitly excluded by design:
- Pure macroeconomics journals (*Journal of Monetary Economics*)
- Pure labor economics (*Journal of Labor Economics*)
- Pure development economics (*Journal of Development Economics*)
- Pure econometrics (*Journal of Econometrics*)
- Computer science venues (*FOCS*, *STOC*, *EC — ACM Conference on
  Economics and Computation*)

The top finance journals (*Journal of Finance*, *Journal of Financial
Economics*, *Review of Financial Studies*) are included because
information-asymmetry work appears there with regularity.

---

## Known limitations

**Author disambiguation.** Semantic Scholar's `authorId` is more stable
than name-matching, but duplicate or split records for the same researcher
remain a known issue. The loader uses citation count to pick the most
prominent candidate when multiple S2 records share a name.

**Venue string inconsistency.** Semantic Scholar's `venue` field is
free-text and inconsistently populated. The loader prefers the structured
`publicationVenue.name` field, introduced in a later API version, and falls
back to `venue` only when `publicationVenue` is absent.

**Year window.** The 2015–2025 window captures recent and active
information-economics research. It excludes foundational work (Akerlof
1970, Spence 1973, Mirrlees 1971) and therefore underrepresents older
authors whose active publication period preceded the window.

**Seed-list bias.** Centrality measures for seed authors are elevated by
construction. Findings about seed-author centrality should be interpreted
cautiously. Non-seed authors with high centrality are the more informative
finding.

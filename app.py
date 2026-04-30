"""
app.py — Streamlit interface for the Information Economics Co-authorship Network.

Run from project root:
    streamlit run app.py

Loads the corpus from data/corpus.json on startup (cached). All four
interaction modes are implemented as separate pages via st.sidebar navigation.
"""

import json
from collections import Counter
import streamlit as st
from pathlib import Path

from src.researcher import Researcher
from src.publication import Publication
from src.graph import CollaborationGraph
from src.query_engine import QueryEngine


# -------------------------------------------------------------------
# Page config — must be first Streamlit call
# -------------------------------------------------------------------

st.set_page_config(
    page_title="Info-Econ Network",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)


# -------------------------------------------------------------------
# Global styles
# -------------------------------------------------------------------

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=IBM+Plex+Mono:wght@300;400;500&family=IBM+Plex+Sans:wght@300;400;500&display=swap');

/* Base */
html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    background-color: #0e0f11;
    color: #d4cfc7;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #13141a;
    border-right: 1px solid #2a2b32;
}

/* Headers */
h1, h2, h3 {
    font-family: 'Playfair Display', serif;
    color: #e8e2d8;
    letter-spacing: -0.02em;
}

/* Metric cards */
[data-testid="stMetric"] {
    background: #16171d;
    border: 1px solid #2a2b32;
    border-radius: 4px;
    padding: 16px;
}
[data-testid="stMetricLabel"] {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #7a7672;
}
[data-testid="stMetricValue"] {
    font-family: 'IBM Plex Mono', monospace;
    color: #c9b97a;
    font-size: 1.6rem;
}

/* Buttons */
.stButton > button {
    background: transparent;
    border: 1px solid #c9b97a;
    color: #c9b97a;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.8rem;
    letter-spacing: 0.05em;
    border-radius: 2px;
    transition: all 0.15s ease;
}
.stButton > button:hover {
    background: #c9b97a;
    color: #0e0f11;
}

/* Sidebar nav radio labels */
[data-testid="stRadio"] label p {
    color: #d4cfc7;
    font-family: 'IBM Plex Sans', sans-serif;
}

/* Selectbox, text input */
.stSelectbox > div > div,
.stTextInput > div > div > input {
    background: #16171d;
    border: 1px solid #2a2b32;
    color: #d4cfc7;
    font-family: 'IBM Plex Sans', sans-serif;
    border-radius: 2px;
}
.stTextInput > div > div > input::placeholder {
    color: #9a948e;
    opacity: 1;
}

/* Dataframe / table */
[data-testid="stDataFrame"] {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.8rem;
}

/* Divider */
hr {
    border-color: #2a2b32;
}

/* Badges */
.badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 2px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}
.badge-gold { background: #2a2410; color: #c9b97a; border: 1px solid #3d3418; }
.badge-gray { background: #1e1f25; color: #7a7672; border: 1px solid #2a2b32; }
.badge-green { background: #0f1f12; color: #6dbd7a; border: 1px solid #1a3320; }

/* Path chain */
.path-chain {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0;
    margin: 24px 0;
}
.path-node {
    background: #16171d;
    border: 1px solid #c9b97a;
    border-radius: 4px;
    padding: 12px 16px;
    min-width: 140px;
    text-align: center;
}
.path-node-name {
    font-family: 'IBM Plex Sans', sans-serif;
    font-weight: 500;
    font-size: 0.85rem;
    color: #e8e2d8;
    margin-bottom: 4px;
}
.path-node-detail {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.68rem;
    color: #7a7672;
}
.path-arrow {
    padding: 0 8px;
    color: #c9b97a;
    font-size: 1.2rem;
    font-family: monospace;
}
.path-edge-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.68rem;
    color: #7a7672;
    text-align: center;
    max-width: 160px;
    padding: 4px;
    font-style: italic;
}

/* Researcher card */
.researcher-card {
    background: #16171d;
    border: 1px solid #2a2b32;
    border-left: 3px solid #c9b97a;
    border-radius: 0 4px 4px 0;
    padding: 16px 20px;
    margin-bottom: 12px;
}
.researcher-name {
    font-family: 'Playfair Display', serif;
    font-size: 1.1rem;
    color: #e8e2d8;
    margin-bottom: 4px;
}
.researcher-affil {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.75rem;
    color: #7a7672;
}

/* Section label */
.section-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #7a7672;
    margin-bottom: 12px;
    padding-bottom: 6px;
    border-bottom: 1px solid #2a2b32;
}

/* Ranking row */
.rank-row {
    display: flex;
    align-items: center;
    padding: 10px 12px;
    border-bottom: 1px solid #2a2b32;
    gap: 16px;
    background: #16171d;
}
.rank-num {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.75rem;
    color: #7a7672;
    width: 24px;
    flex-shrink: 0;
}
.rank-name {
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 0.9rem;
    color: #ffffff;
    flex: 1;
}
.rank-score {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.8rem;
    color: #c9b97a;
}
.rank-bar-bg {
    width: 80px;
    height: 4px;
    background: #1e1f25;
    border-radius: 2px;
    overflow: hidden;
}
.rank-bar-fill {
    height: 100%;
    background: #c9b97a;
    border-radius: 2px;
}
</style>
""",
    unsafe_allow_html=True,
)


# -------------------------------------------------------------------
# Corpus loading (cached so it only runs once per session)
# -------------------------------------------------------------------


@st.cache_resource(show_spinner="Loading corpus…")
def load_engine() -> QueryEngine | None:
    corpus_path = Path("data/corpus.json")
    if not corpus_path.exists():
        return None
    with open(corpus_path) as f:
        payload = json.load(f)

    graph = CollaborationGraph()
    for rd in payload.get("researchers", []):
        graph.add_researcher(Researcher.from_dict(rd))
    for pd in payload.get("publications", []):
        pub = Publication.from_dict(pd)
        # Re-attach publications without re-triggering edge recomputation.
        graph.publications[pub.paper_id] = pub
        for aid in pub.author_ids:
            if aid in graph.researchers:
                graph.researchers[aid].add_paper(pub.paper_id)

    # Rebuild edges from publications.
    for pub in graph.publications.values():
        for a, b in pub.coauthor_pairs():
            if a not in graph.researchers or b not in graph.researchers:
                continue
            if graph._g.has_edge(a, b):
                if pub.paper_id not in graph._g[a][b]["paper_ids"]:
                    graph._g[a][b]["weight"] += 1
                    graph._g[a][b]["paper_ids"].append(pub.paper_id)
            else:
                graph._g.add_edge(a, b, weight=1, paper_ids=[pub.paper_id])

    return QueryEngine(graph)


# -------------------------------------------------------------------
# Sidebar
# -------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        """
    <div style="padding: 8px 0 24px 0">
        <div style="font-family: 'Playfair Display', serif; font-size: 1.4rem;
                    color: #e8e2d8; line-height: 1.2;">
            Information<br>Economics<br>Network
        </div>
        <div style="font-family: 'IBM Plex Mono', monospace; font-size: 0.65rem;
                    color: #7a7672; margin-top: 8px; letter-spacing: 0.08em;">
            CO-AUTHORSHIP ANALYSIS · 2015–2025
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    page = st.radio(
        "Navigation",
        ["Overview", "Search & Query", "Pathfinding", "Rankings"],
        label_visibility="collapsed",
    )
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(
        """
    <div style="font-family: 'IBM Plex Mono', monospace; font-size: 0.65rem;
                color: #7a7672; line-height: 1.8;">
        MODE 1 · Search & Query<br>
        MODE 2 · Pathfinding<br>
        MODE 3 · Year Filter<br>
        MODE 4 · Rankings
    </div>
    """,
        unsafe_allow_html=True,
    )


# -------------------------------------------------------------------
# Load engine (once)
# -------------------------------------------------------------------

engine = load_engine()

if engine is None:
    st.error(
        "Corpus not found at `data/corpus.json`. "
        "Run `python scripts/pull_corpus.py` first."
    )
    st.stop()

summary = engine.corpus_summary()


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


def fmt_int(n: int) -> str:
    return f"{n:,}"


def fmt_score(f: float) -> str:
    return f"{f:.4f}"


def researcher_badge(r: Researcher, in_main: bool) -> str:
    cls = "badge-green" if in_main else "badge-gray"
    label = "core network" if in_main else "peripheral"
    return f'<span class="badge {cls}">{label}</span>'


def bar_html(score: float, max_score: float) -> str:
    pct = int(100 * score / max_score) if max_score > 0 else 0
    return (
        f'<div class="rank-bar-bg">'
        f'<div class="rank-bar-fill" style="width:{pct}%"></div>'
        f"</div>"
    )


# ===================================================================
# PAGE: Overview
# ===================================================================

if page == "Overview":
    st.markdown("## Corpus Overview")
    st.markdown(
        "<div class='section-label'>Network Statistics</div>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Papers", fmt_int(summary["publications"]))
    c2.metric("Researchers", fmt_int(summary["researchers"]))
    c3.metric("Co-author Edges", fmt_int(summary["edges"]))
    c4.metric("Core Network", fmt_int(summary["main_component_size"]))
    c5.metric("Components", fmt_int(summary["connected_components"]))

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        "<div class='section-label'>About this corpus</div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"""
The corpus covers **{summary["publications"]:,} papers** published in
top-tier economics journals between 2015 and 2025, anchored by 22 seed
authors from the information-economics canon (Akerlof, Spence, Stiglitz,
Holmström, Myerson, and others) and expanded via citation links.

Nodes are individual researchers. Edges connect any two researchers who
co-authored at least one paper in the corpus, weighted by the number of
shared papers.

The graph has **{summary["connected_components"]:,} connected components**.
The largest component, the **core network**, contains
**{summary["main_component_size"]:,} researchers**
({summary["main_component_pct"]:.1f}% of the total).
Pathfinding operates within the core network.
    """)

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(
        "<div class='section-label'>Top 5 by betweenness centrality</div>",
        unsafe_allow_html=True,
    )
    top5 = engine.top_central("betweenness", 5)
    max_score = top5[0].centrality["betweenness"] if top5 else 1.0
    for i, r in enumerate(top5, 1):
        score = r.centrality["betweenness"]
        affil_html = (
            f"<span style=\"font-family:'IBM Plex Mono',monospace;font-size:0.72rem;"
            f'color:#7a7672;flex:1">{r.affiliation}</span>'
            if r.affiliation
            else '<span style="flex:1"></span>'
        )
        st.markdown(
            f'<div class="rank-row">'
            f'<span class="rank-num">{i:02d}</span>'
            f'<span class="rank-name">{r.name}</span>'
            f"{affil_html}"
            f"{bar_html(score, max_score)}"
            f'<span class="rank-score">{fmt_score(score)}</span>'
            f"</div>",
            unsafe_allow_html=True,
        )


# ===================================================================
# PAGE: Search & Query  (Mode 1)
# ===================================================================

elif page == "Search & Query":
    st.markdown("## Search & Query")
    st.markdown(
        "<div class='section-label'>Mode 1 · Look up a researcher</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Note: Semantic Scholar occasionally splits a single researcher "
        "across multiple author records. Records with similar names may "
        "represent the same person."
    )
    query = st.text_input("Name", placeholder="e.g. Bergemann, Kamenica, Strack…")

    if query:
        results = engine.search(query)
        if not results:
            st.warning(f"No researchers found matching '{query}'.")
        else:
            st.markdown(
                f"<div class='section-label'>{len(results)} result(s)</div>",
                unsafe_allow_html=True,
            )
            # Sort by papers in corpus (most prolific first) so the canonical
            # researcher is the default dropdown selection.
            ranked = sorted(results[:20], key=lambda r: -r.paper_count_in_corpus)

            # Disambiguate when multiple researchers share a display name.
            name_counts = Counter(r.name for r in ranked)
            options: dict[str, str] = {}
            for r in ranked:
                label = r.name
                if name_counts[r.name] > 1:
                    n = r.paper_count_in_corpus
                    suffix = r.affiliation or f"{n} paper{'s' if n != 1 else ''}"
                    label = f"{r.name} ({suffix})"
                # If labels still collide (same name + same affiliation/count),
                # leave duplicates in the dropdown rather than fabricating an index.
                if label not in options:
                    options[label] = r.author_id
            selected_name = st.selectbox(
                "Select researcher",
                list(options.keys()),
                label_visibility="collapsed",
            )
            selected_id = options[selected_name]
            profile = engine.profile(selected_id)

            if profile:
                r = profile.researcher
                in_main = profile.in_main_component

                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown(
                    f'<div class="researcher-card">'
                    f'<div class="researcher-name">{r.name}</div>'
                    f'<div class="researcher-affil">'
                    f"{r.affiliation or 'Affiliation unknown'}"
                    f"</div>"
                    f'<div style="margin-top:8px">'
                    f"{researcher_badge(r, in_main)}"
                    f"</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                # Stats row
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Citations", fmt_int(r.citation_count))
                c2.metric("h-index", r.h_index)
                c3.metric("Papers in corpus", r.paper_count_in_corpus)
                c4.metric(
                    "Collaborators",
                    len(engine.graph.collaborators_of(r.author_id)),
                )

                # Centrality ranks
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown(
                    "<div class='section-label'>Centrality ranks (out of "
                    f"{fmt_int(engine.graph.num_researchers)} researchers)</div>",
                    unsafe_allow_html=True,
                )
                cr = profile.centrality_rank
                rc1, rc2, rc3, rc4 = st.columns(4)
                rc1.metric("Degree rank", f"#{cr.get('degree', '—')}")
                rc2.metric("Betweenness rank", f"#{cr.get('betweenness', '—')}")
                rc3.metric("Eigenvector rank", f"#{cr.get('eigenvector', '—')}")
                rc4.metric("Closeness rank", f"#{cr.get('closeness', '—')}")

                # Top collaborators
                if profile.top_collaborators:
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown(
                        "<div class='section-label'>Top collaborators</div>",
                        unsafe_allow_html=True,
                    )
                    for collab, weight in profile.top_collaborators[:5]:
                        papers_word = "paper" if weight == 1 else "papers"
                        st.markdown(
                            f'<div class="rank-row">'
                            f'<span class="rank-name">{collab.name}</span>'
                            f"<span style=\"font-family:'IBM Plex Mono',monospace;"
                            f'font-size:0.75rem;color:#c9b97a">'
                            f"{weight} shared {papers_word}</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

                # Publications
                if profile.publications:
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown(
                        "<div class='section-label'>Papers in corpus</div>",
                        unsafe_allow_html=True,
                    )
                    for pub in profile.publications[:10]:
                        venue_str = pub.venue or "venue unknown"
                        st.markdown(
                            f'<div style="padding: 8px 0; border-bottom: '
                            f'1px solid #1e1f25;">'
                            f"<div style=\"font-family:'IBM Plex Sans',sans-serif;"
                            f'font-size:0.88rem;color:#d4cfc7;">{pub.title}</div>'
                            f"<div style=\"font-family:'IBM Plex Mono',monospace;"
                            f'font-size:0.7rem;color:#7a7672;margin-top:3px;">'
                            f"{pub.year} · {venue_str} · "
                            f"{pub.citation_count:,} citations</div>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )


# ===================================================================
# PAGE: Pathfinding  (Mode 2 — also covers Mode 3 via year filter)
# ===================================================================

elif page == "Pathfinding":
    st.markdown("## Pathfinding")
    st.markdown(
        "<div class='section-label'>"
        "Mode 2 · Find the shortest collaboration path between two researchers"
        "</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Pathfinding operates within the core network "
        f"({summary['main_component_size']:,} researchers). "
        "Researchers outside the core network are not reachable."
    )

    # Year filter (Mode 3) lives here as a sidebar control
    st.markdown("<br>", unsafe_allow_html=True)
    col_filter, _ = st.columns([2, 3])
    with col_filter:
        st.markdown(
            "<div class='section-label'>Mode 3 · Filter by year</div>",
            unsafe_allow_html=True,
        )
        year_range = st.slider(
            "Publication year range",
            min_value=2015,
            max_value=2025,
            value=(2015, 2025),
            label_visibility="collapsed",
        )

    # Apply year filter if not full range
    active_engine = engine
    if year_range != (2015, 2025):
        active_engine = engine.filter_by_year(*year_range)
        filtered_summary = active_engine.corpus_summary()
        st.caption(
            f"Filtered: {filtered_summary['publications']:,} papers · "
            f"{filtered_summary['researchers']:,} researchers · "
            f"core network: {filtered_summary['main_component_size']:,}"
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Researcher selection — dropdowns from core network members
    component_researchers = active_engine.main_component_researchers()
    name_to_id = {r.name: r.author_id for r in component_researchers}
    names = list(name_to_id.keys())

    if len(names) < 2:
        st.warning("Not enough researchers in the core network for pathfinding.")
        st.stop()

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(
            "<div class='section-label'>Source researcher</div>",
            unsafe_allow_html=True,
        )
        source_name = st.selectbox(
            "Source", names, key="src", label_visibility="collapsed"
        )
    with col_b:
        st.markdown(
            "<div class='section-label'>Target researcher</div>",
            unsafe_allow_html=True,
        )
        # Default to a different researcher
        default_idx = min(1, len(names) - 1)
        target_name = st.selectbox(
            "Target", names, index=default_idx, key="tgt", label_visibility="collapsed"
        )

    find_clicked = st.button("Find path →")

    if find_clicked:
        source_id = name_to_id[source_name]
        target_id = name_to_id[target_name]

        if source_id == target_id:
            st.info("Source and target are the same researcher.")
        else:
            result = active_engine.find_path(source_id, target_id)

            if result.out_of_scope:
                st.warning(
                    "One or both researchers are outside the core network "
                    "and cannot be connected by pathfinding."
                )
            elif not result.found:
                st.warning(
                    f"No path found between {source_name} and {target_name} "
                    "within the current year filter."
                )
            else:
                st.markdown("<br>", unsafe_allow_html=True)
                dist_word = "hop" if result.distance == 1 else "hops"
                st.markdown(
                    f"<div style=\"font-family:'IBM Plex Mono',monospace;"
                    f'font-size:0.8rem;color:#c9b97a;margin-bottom:16px;">'
                    f"DISTANCE · {result.distance} {dist_word}</div>",
                    unsafe_allow_html=True,
                )

                # Path chain visualization
                chain_parts = []
                for i, researcher in enumerate(result.researchers):
                    affil = (researcher.affiliation or "")[:28]
                    chain_parts.append(
                        f'<div class="path-node">'
                        f'<div class="path-node-name">{researcher.name}</div>'
                        f'<div class="path-node-detail">{affil}</div>'
                        f"</div>"
                    )
                    if i < len(result.researchers) - 1:
                        edge_pubs = result.bridging_papers[i]
                        if edge_pubs:
                            paper_label = edge_pubs[0].title[:30] + "…"
                        else:
                            paper_label = ""
                        chain_parts.append(
                            f'<div style="display:flex;flex-direction:column;'
                            f'align-items:center;">'
                            f'<span class="path-arrow">——▶</span>'
                            f'<span class="path-edge-label">{paper_label}</span>'
                            f"</div>"
                        )

                st.markdown(
                    f'<div class="path-chain">{"".join(chain_parts)}</div>',
                    unsafe_allow_html=True,
                )

                # Edge details
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown(
                    "<div class='section-label'>Bridging papers</div>",
                    unsafe_allow_html=True,
                )
                for i, (edge_pubs) in enumerate(result.bridging_papers):
                    a = result.researchers[i].name
                    b = result.researchers[i + 1].name
                    st.markdown(
                        f"<div style=\"font-family:'IBM Plex Mono',monospace;"
                        f'font-size:0.72rem;color:#7a7672;margin:12px 0 6px 0;">'
                        f"{a} → {b}</div>",
                        unsafe_allow_html=True,
                    )
                    for pub in edge_pubs[:3]:
                        venue_str = pub.venue or "venue unknown"
                        st.markdown(
                            f'<div style="padding:6px 0 6px 12px;'
                            f'border-left:2px solid #2a2b32;">'
                            f'<div style="font-size:0.85rem;color:#d4cfc7;">'
                            f"{pub.title}</div>"
                            f"<div style=\"font-family:'IBM Plex Mono',monospace;"
                            f'font-size:0.68rem;color:#7a7672;margin-top:2px;">'
                            f"{pub.year} · {venue_str}</div>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )


# ===================================================================
# PAGE: Rankings  (Mode 4)
# ===================================================================

elif page == "Rankings":
    st.markdown("## Rankings")
    st.markdown(
        "<div class='section-label'>Mode 4 · Top researchers by centrality measure</div>",
        unsafe_allow_html=True,
    )
    st.markdown("""
Centrality measures capture different kinds of structural importance.
**Degree** counts direct collaborators.
**Betweenness** identifies researchers who bridge otherwise-disconnected clusters.
**Eigenvector** weights connections by the importance of collaborators.
**Closeness** measures how quickly a researcher can reach the rest of the network.
    """)

    k = st.slider("Number of researchers to show", 5, 25, 10)
    table = engine.rankings_table(k=k)

    tabs = st.tabs(["Betweenness", "Degree", "Eigenvector", "Closeness"])
    measure_keys = ["betweenness", "degree", "eigenvector", "closeness"]

    for tab, measure in zip(tabs, measure_keys):
        with tab:
            researchers = table[measure]
            if not researchers:
                st.write("No data.")
                continue

            max_score = researchers[0].centrality.get(measure, 1.0) or 1.0

            st.markdown(
                f"<div class='section-label'>Top {k} by {measure} centrality</div>",
                unsafe_allow_html=True,
            )
            for i, r in enumerate(researchers, 1):
                score = r.centrality.get(measure, 0.0)
                in_main = engine.in_main_component(r.author_id)
                badge = (
                    '<span class="badge badge-gold">core</span>'
                    if in_main
                    else '<span class="badge badge-gray">peripheral</span>'
                )
                affil_html = (
                    f"<div style=\"font-family:'IBM Plex Mono',monospace;"
                    f'font-size:0.68rem;color:#7a7672">{r.affiliation}</div>'
                    if r.affiliation
                    else ""
                )
                st.markdown(
                    f'<div class="rank-row">'
                    f'<span class="rank-num">{i:02d}</span>'
                    f'<div style="flex:1">'
                    f'<div class="rank-name">{r.name} {badge}</div>'
                    f"{affil_html}"
                    f"</div>"
                    f"{bar_html(score, max_score)}"
                    f'<span class="rank-score">{fmt_score(score)}</span>'
                    f"</div>",
                    unsafe_allow_html=True,
                )

            # Overlap note
            degree_ids = {r.author_id for r in table["degree"]}
            btw_ids = {r.author_id for r in table["betweenness"]}
            overlap = len(degree_ids & btw_ids)
            if measure == "betweenness":
                st.markdown("<br>", unsafe_allow_html=True)
                st.caption(
                    f"{overlap} of the top-{k} by betweenness also appear "
                    f"in the top-{k} by degree. "
                    "Researchers who rank highly on betweenness but not degree "
                    "are pure bridge nodes — central by position, not by volume."
                )

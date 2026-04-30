"""
Seed authors for the citation-graph expansion strategy.

Each entry: (display_name, optional_s2_author_id, brief_annotation).
The author_id is None where we want the loader to resolve it via author
search at runtime; supplying a hard-coded ID is more reliable when
multiple economists share a name (Y. Chen is the obvious case).

The corpus boundary follows the working definition in METHODOLOGY.md:
information economics studies how the distribution of information
across economic agents affects behavior, contracts, market outcomes,
and welfare. The five canonical problem types are hidden information
(adverse selection), hidden action (moral hazard), signaling and
communication, mechanism design, and information design.

Excluded on purpose:
  - Algorithmic mechanism design (Roughgarden, Nisan): publishes in
    CS venues outside our econ allowlist; would muddy the corpus.
  - Macro information frictions (Sims pre-rational-inattention): most
    output is macro-econometric, not info-econ. Matejka covers
    rational inattention adequately.
"""

# (display_name, s2_author_id_or_None, annotation)
SEED_AUTHORS: list[tuple[str, str | None, str]] = [
    # ----- Founders / Nobel trio for asymmetric information -----
    ("George Akerlof",        None, "Lemons paper; foundational adverse selection."),
    ("Michael Spence",        None, "Job market signaling; foundational signaling."),
    ("Joseph Stiglitz",       None, "Screening, credit rationing, Grossman-Stiglitz."),

    # ----- Mechanism design / contract theory canon -----
    ("Roger Myerson",         None, "Revelation principle, optimal auctions; Nobel 2007."),
    ("Eric Maskin",           None, "Implementation theory, mechanism design; Nobel 2007."),
    ("Paul Milgrom",          None, "Auction theory, mechanism design; Nobel 2020."),
    ("Robert Wilson",         None, "Auction theory; Nobel 2020."),
    ("Bengt Holmstrom",       None, "Moral hazard, contract theory; Nobel 2016."),
    ("Oliver Hart",           None, "Incomplete contracts; Nobel 2016."),
    ("Jean Tirole",           None, "Contract theory, regulation, IO; Nobel 2014."),
    ("Vijay Krishna",         None, "Auction theory; canonical textbook author."),

    # ----- Information design / Bayesian persuasion frontier -----
    ("Emir Kamenica",         None, "Kamenica-Gentzkow Bayesian persuasion."),
    ("Dirk Bergemann",        None, "Information design, robust mechanism design."),
    ("Stephen Morris",        None, "Global games, information design."),
    ("Filip Matejka",         None, "Rational inattention."),

    # ----- Contemporary theorists -----
    ("Ilya Segal",            None, "Mechanism design, contract theory."),
    ("Philipp Strack",        None, "Information design, mechanism design."),
    ("Doron Ravid",           None, "Information design (Chicago Booth)."),
    ("Susan Athey",           None, "Mechanism design + applied work."),
    ("Jean-Charles Rochet",   None, "Insurance, contract theory, two-sided markets."),

    # ----- Boundary / experimental cases -----
    ("Yan Chen",              None, "Experimental mechanism design (UMich). Note: name disambiguation risk."),
    ("Alain Cohn",            None, "Behavioral econ adjacent (signaling honesty/trust)."),
]


def seed_names() -> list[str]:
    """Just the display names, in canonical order."""
    return [name for name, _, _ in SEED_AUTHORS]


def seed_ids() -> list[str]:
    """Pre-supplied S2 author IDs, if any. Most are None at write time and
    will be resolved on first run via the author-search endpoint."""
    return [aid for _, aid, _ in SEED_AUTHORS if aid is not None]

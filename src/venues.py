"""
Top-tier economics venue allowlist for the strict corpus.

Each entry is a (pattern, mode) tuple. Modes:
    "exact"     — case-insensitive exact match against full venue name.
                  Use for journals with ambiguous-substring names where a
                  predatory or unrelated journal could sneak in.
    "substring" — case-insensitive substring match. Use for journal
                  families like "American Economic Journal" that span
                  multiple sub-titles (AEJ: Microeconomics, AEJ: Applied,
                  AEJ: Macroeconomics, AEJ: Policy).
    "prefix"    — case-insensitive startswith. Use for journals where
                  the canonical name should anchor at the start, but
                  trailing variants are OK.

Coverage goal: ~50 journals where information-economics, game theory,
mechanism design, contract theory, and adjacent applied work appears.
Built from the NYU Stern faculty list and standard top-30 econ rankings.

Excluded on purpose: pure macro (e.g., J. Monetary Economics), pure
development (J. Development Economics), pure labor (J. Labor Economics),
pure econometrics (J. Econometrics) — these subfields don't publish
information-economics work in volume.

Included: top-5 + general-interest, theory and game-theory journals,
field journals where info-econ appears (insurance, IO, finance with
asymmetric info, public econ, law & econ), plus the AEJ family.
"""

# (pattern, mode)
TOP_ECON_VENUE_PATTERNS: list[tuple[str, str]] = [
    # ----- Top 5 / general-interest -----
    (
        "American Economic Review",
        "prefix",
    ),  # catches "American Economic Review: Insights"
    ("Econometrica", "exact"),
    ("Quarterly Journal of Economics", "prefix"),  # tolerates "The Quarterly..."
    (
        "Journal of Political Economy",
        "prefix",
    ),  # catches "Journal of Political Economy Microeconomics"
    ("Review of Economic Studies", "prefix"),  # tolerates "The Review..."
    ("Journal of the European Economic Association", "exact"),
    # ----- AEJ family (one substring catches all four AEJs) -----
    ("American Economic Journal", "substring"),
    # ----- Theory / game theory / mechanism design -----
    # Theoretical Economics is exact-match because "Theoretical Economics
    # Letters" is a separate, lower-quality journal we want to exclude.
    ("Theoretical Economics", "exact"),
    ("Quantitative Economics", "exact"),
    ("Journal of Economic Theory", "prefix"),
    ("Games and Economic Behavior", "exact"),
    ("International Journal of Game Theory", "exact"),
    ("Economic Theory", "exact"),  # exact to avoid Economic Theory Bulletin etc
    # ----- Field journals where info-econ regularly appears -----
    ("RAND Journal of Economics", "prefix"),
    ("Journal of Industrial Economics", "exact"),
    ("Journal of Law", "substring"),  # catches J. Law & Econ. + J. Law Econ. & Org.
    ("Journal of Public Economics", "exact"),
    ("Journal of Public Economic Theory", "exact"),
    ("Journal of Risk and Uncertainty", "exact"),
    ("Journal of Health Economics", "exact"),
    ("American Journal of Health Economics", "exact"),
    ("International Economic Review", "exact"),
    # ----- Survey + perspectives -----
    ("Journal of Economic Literature", "exact"),
    ("Journal of Economic Perspectives", "exact"),
    # ----- General field journals (broader; info-econ work appears here) -----
    ("Economic Journal", "exact"),  # exact to avoid AEJ double-count
    ("Review of Economics and Statistics", "prefix"),
    ("Economic Inquiry", "exact"),
    ("Experimental Economics", "exact"),
    ("Journal of Mathematical Economics", "exact"),
    # ----- Top finance journals (asymmetric-info work appears here) -----
    ("Journal of Finance", "exact"),
    ("Journal of Financial Economics", "exact"),
    ("Review of Financial Studies", "prefix"),
    # ----- IO / management adjacent -----
    ("Marketing Science", "exact"),
    ("Management Science", "exact"),
    # ----- AER: Papers and Proceedings -----
    ("AEA Papers and Proceedings", "exact"),
]


def venue_matches(venue_string: str | None, patterns=TOP_ECON_VENUE_PATTERNS) -> bool:
    """Check whether a venue string matches any allowlist entry under the
    appropriate match mode."""
    if not venue_string:
        return False
    v = venue_string.strip().lower()
    # Strip leading "the " — S2 inconsistently includes/excludes it.
    if v.startswith("the "):
        v = v[4:]
    for pattern, mode in patterns:
        p = pattern.lower()
        if p.startswith("the "):
            p = p[4:]
        if mode == "exact" and v == p:
            return True
        if mode == "prefix" and v.startswith(p):
            return True
        if mode == "substring" and p in v:
            return True
    return False


# Backward-compat: older code that imports TOP_ECON_VENUES as a flat list
# of substrings still works, but prefer venue_matches() for new code
# because it respects the per-pattern match mode.
TOP_ECON_VENUES: list[str] = [pattern for pattern, _ in TOP_ECON_VENUE_PATTERNS]

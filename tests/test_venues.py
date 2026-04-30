"""Tests for venue matching logic in src/venues.py.

These tests document the exact failure modes we caught during development:
  - "The American Economic Review" wasn't matching (leading "The" bug)
  - "Theoretical Economics Letters" was matching (substring too broad)
  - "Economic Theory Bulletin" was matching (same issue)
  - "Eastern Economic Journal" was leaking through

If any of these fail after future venue-list edits, something regressed.
"""

import pytest
from src.venues import venue_matches, TOP_ECON_VENUE_PATTERNS


# -------------------------------------------------------------------
# Should match (known legitimate econ venues)
# -------------------------------------------------------------------

class TestShouldMatch:
    @pytest.mark.parametrize("venue", [
        # Top 5 general-interest
        "American Economic Review",
        "The American Economic Review",          # leading "The" bug — was failing
        "American Economic Review: Insights",
        "Econometrica",
        "Quarterly Journal of Economics",
        "The Quarterly Journal of Economics",    # leading "The" bug — was failing
        "Journal of Political Economy",
        "Journal of Political Economy Microeconomics",
        "Review of Economic Studies",
        "The Review of Economic Studies",        # leading "The" bug — was failing
        "Journal of the European Economic Association",
        # AEJ family
        "American Economic Journal: Microeconomics",
        "American Economic Journal: Applied Economics",
        "American Economic Journal: Macroeconomics",
        "American Economic Journal: Economic Policy",
        # Theory / game theory
        "Theoretical Economics",
        "Journal of Economic Theory",
        "Games and Economic Behavior",
        "International Journal of Game Theory",
        "Economic Theory",
        "Quantitative Economics",
        # Field journals
        "RAND Journal of Economics",
        "Journal of Industrial Economics",
        "Journal of Law and Economics",
        "Journal of Law, Economics, and Organization",
        "Journal of Public Economics",
        "Journal of Public Economic Theory",
        "Journal of Risk and Uncertainty",
        "Journal of Health Economics",
        "American Journal of Health Economics",
        "International Economic Review",
        "Journal of Economic Literature",
        "Journal of Economic Perspectives",
        "Economic Journal",
        "Review of Economics and Statistics",
        "Economic Inquiry",
        "Experimental Economics",
        "Journal of Mathematical Economics",
        # Finance (asymmetric-info work)
        "Journal of Finance",
        "Journal of Financial Economics",
        "Review of Financial Studies",
        # IO / management
        "Management Science",
        "Marketing Science",
        # AEA P&P
        "AEA Papers and Proceedings",
    ])
    def test_valid_venue_matches(self, venue):
        assert venue_matches(venue), f"Expected {venue!r} to match but it didn't"


# -------------------------------------------------------------------
# Should NOT match (false-positive risks we've already seen)
# -------------------------------------------------------------------

class TestShouldNotMatch:
    @pytest.mark.parametrize("venue", [
        # The exact false positives we caught during development
        "Theoretical Economics Letters",         # predatory; different from Theoretical Economics
        "Economic Theory Bulletin",              # different journal
        "Eastern Economic Journal",              # not on our allowlist; leaked through before
        # Non-econ venues that caused the original corpus noise problem
        "AAAI Conference on Artificial Intelligence",
        "Nature",
        "PLoS ONE",
        "arXiv.org",
        "Social Science Research Network",
        "Sustainability",
        "At-tijaroh: Jurnal Ilmu Manajemen",
        # Plausible-sounding but not on list
        "European Economic Review",
        "Journal of Economic History",
        "Journal of Development Economics",
        "Journal of Labor Economics",
        "Journal of Monetary Economics",
        "Journal of Econometrics",
        # Edge cases
        "",
        "   ",
    ])
    def test_invalid_venue_does_not_match(self, venue):
        assert not venue_matches(venue), f"Expected {venue!r} NOT to match but it did"


# -------------------------------------------------------------------
# None / missing input
# -------------------------------------------------------------------

class TestNoneAndMissing:
    def test_none_returns_false(self):
        assert not venue_matches(None)

    def test_empty_string_returns_false(self):
        assert not venue_matches("")

    def test_whitespace_only_returns_false(self):
        assert not venue_matches("   ")


# -------------------------------------------------------------------
# Match mode correctness
# -------------------------------------------------------------------

class TestMatchModes:
    def test_exact_mode_rejects_substring(self):
        # "Econometrica" is exact; "New Econometrica" should not match
        assert not venue_matches("New Econometrica")

    def test_exact_mode_rejects_superstring(self):
        assert not venue_matches("Econometrica Letters")

    def test_prefix_mode_accepts_trailing_variant(self):
        # "American Economic Review" is prefix; trailing ": Insights" is fine
        assert venue_matches("American Economic Review: Insights")

    def test_prefix_mode_rejects_leading_extra(self):
        # "New American Economic Review" should NOT match — prefix requires
        # the name to start at position 0 (after stripping "The ")
        assert not venue_matches("New American Economic Review")

    def test_substring_mode_catches_full_family(self):
        # "American Economic Journal" is substring, so all AEJ variants match
        for variant in [
            "American Economic Journal: Microeconomics",
            "American Economic Journal: Applied Economics",
            "American Economic Journal: Macroeconomics",
        ]:
            assert venue_matches(variant)

    def test_the_prefix_stripped_before_matching(self):
        # Confirm the "The " stripping applies symmetrically
        assert venue_matches("The Quarterly Journal of Economics")
        assert venue_matches("The Review of Economic Studies")
        assert venue_matches("The American Economic Review")


# -------------------------------------------------------------------
# allowlist structure sanity
# -------------------------------------------------------------------

class TestAllowlistStructure:
    def test_all_entries_are_tuples(self):
        for entry in TOP_ECON_VENUE_PATTERNS:
            assert isinstance(entry, tuple), f"Entry {entry!r} is not a tuple"

    def test_all_entries_have_two_elements(self):
        for entry in TOP_ECON_VENUE_PATTERNS:
            assert len(entry) == 2, f"Entry {entry!r} doesn't have 2 elements"

    def test_all_modes_are_valid(self):
        valid_modes = {"exact", "prefix", "substring"}
        for pattern, mode in TOP_ECON_VENUE_PATTERNS:
            assert mode in valid_modes, (
                f"Pattern {pattern!r} has invalid mode {mode!r}"
            )

    def test_no_empty_patterns(self):
        for pattern, _ in TOP_ECON_VENUE_PATTERNS:
            assert pattern.strip(), f"Empty pattern found in allowlist"

"""Region normalisation — the input layer every jurisdiction rule depends on."""

from __future__ import annotations

import pytest

from app.services.regions import (
    EU_MEMBER_STATES,
    collapse_regions,
    expand_region,
    normalize_region,
    normalize_regions,
    regions_intersect,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("eu", "EU"),
        ("  EU  ", "EU"),
        ("European Union", "EU"),
        ("Germany", "DE"),
        ("de", "DE"),
        ("California", "US-CA"),
        ("us_ca", "US-CA"),
        ("CA-US", "US-CA"),
        ("PRC", "CN"),
        ("mainland china", "CN"),
        ("India", "IN"),
        ("worldwide", "GLOBAL"),
        ("DE-BY", "DE"),
    ],
)
def test_normalizes_common_spellings(raw: str, expected: str):
    assert normalize_region(raw) == expected


def test_bare_ca_resolves_to_california_by_default():
    # ISO says Canada, this domain says California. The default is documented and
    # overridable rather than silently guessed.
    assert normalize_region("CA") == "US-CA"
    assert normalize_region("CA", ambiguous_ca="CA-COUNTRY") == "CA-COUNTRY"
    assert normalize_region("Canada") == "CA-COUNTRY"


def test_normalize_regions_drops_blanks():
    assert normalize_regions(["EU", "", "  ", None]) == frozenset({"EU"})  # type: ignore[list-item]
    assert normalize_regions(None) == frozenset()


def test_expand_region_covers_member_states():
    assert "DE" in expand_region("EU")
    assert expand_region("IN") == frozenset({"IN"})


def test_member_state_matches_group_and_vice_versa():
    assert regions_intersect(frozenset({"DE"}), frozenset({"EU"}))
    assert regions_intersect(frozenset({"EU"}), frozenset({"FR"}))
    assert not regions_intersect(frozenset({"BR"}), frozenset({"EU"}))


def test_global_reaches_every_territory():
    assert regions_intersect(frozenset({"GLOBAL"}), frozenset({"CN"})) == frozenset({"CN"})


def test_empty_sets_never_match():
    assert regions_intersect(frozenset(), frozenset({"EU"})) == frozenset()
    assert regions_intersect(frozenset({"EU"}), frozenset()) == frozenset()


def test_collapse_folds_member_states_into_group():
    assert collapse_regions(EU_MEMBER_STATES) == ["EU"]
    assert collapse_regions({"DE", "EU"}) == ["EU"]
    assert collapse_regions(EU_MEMBER_STATES | {"IN"}) == ["EU", "IN"]
    assert collapse_regions({"IS", "LI", "NO", *EU_MEMBER_STATES}) == ["EEA"]
    assert collapse_regions({"US-CA", "IN"}) == ["IN", "US-CA"]


# ---------------------------------------------------------------------------
# Canada, Korea, Brazil, UK — added ahead of the new jurisdictions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("South Korea", "KR"),
        ("korea", "KR"),
        ("KOR", "KR"),
        ("Republic of Korea", "KR"),
        ("Brasil", "BR"),
        ("BRA", "BR"),
        ("England", "GB"),
        ("GBR", "GB"),
        ("Quebec", "CA-QC"),
        ("Québec", "CA-QC"),
        ("Ontario", "CA-ON"),
    ],
)
def test_new_jurisdiction_aliases(raw: str, expected: str):
    assert normalize_region(raw) == expected


def test_canadian_province_is_not_mistaken_for_california():
    """Regression: "CA-QC" used to collapse to "CA", i.e. California."""
    assert normalize_region("CA-QC") == "CA-QC"
    assert normalize_region("ca-on") == "CA-ON"


def test_canada_code_survives_renormalisation():
    """Regression: the client offers "CA-COUNTRY"; normalising it again gave "CA"."""
    assert normalize_region("CA-COUNTRY") == "CA-COUNTRY"
    assert normalize_region(normalize_region("Canada")) == "CA-COUNTRY"


def test_province_matches_canada_territory_and_vice_versa():
    assert regions_intersect(frozenset({"CA-QC"}), frozenset({"CA-COUNTRY"})) == frozenset(
        {"CA-QC"}
    )
    assert "CA-QC" in regions_intersect(frozenset({"CA-COUNTRY"}), frozenset({"CA-QC"}))


def test_province_does_not_reach_california():
    assert not regions_intersect(frozenset({"CA-QC"}), frozenset({"US-CA"}))


def test_all_provinces_collapse_to_canada():
    from app.services.regions import CANADA_SUBDIVISIONS

    assert collapse_regions(CANADA_SUBDIVISIONS) == ["CA-COUNTRY"]
    assert collapse_regions({"CA-QC"}) == ["CA-QC"]

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

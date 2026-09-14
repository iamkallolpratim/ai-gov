"""Region code normalisation shared by the jurisdiction rules.

Inventory data arrives from spreadsheets, vendor questionnaires and self-service forms,
so the same place shows up as ``EU``, ``eu``, ``Germany``, ``DE``, ``US-CA``,
``California``. Everything is folded to a canonical upper-case code before any rule looks
at it: ISO 3166-1 alpha-2 for countries, ISO 3166-2 style ``US-XX`` for US states, and the
supranational pseudo-codes ``EU``/``EEA``.
"""

from __future__ import annotations

from collections.abc import Iterable

# --- supranational groupings ---

EU_MEMBER_STATES: frozenset[str] = frozenset(
    {
        "AT",
        "BE",
        "BG",
        "HR",
        "CY",
        "CZ",
        "DK",
        "EE",
        "FI",
        "FR",
        "DE",
        "GR",
        "HU",
        "IE",
        "IT",
        "LV",
        "LT",
        "LU",
        "MT",
        "NL",
        "PL",
        "PT",
        "RO",
        "SK",
        "SI",
        "ES",
        "SE",
    }
)
# EEA adds Iceland, Liechtenstein and Norway to the EU 27.
EEA_ONLY_STATES: frozenset[str] = frozenset({"IS", "LI", "NO"})
EEA_STATES: frozenset[str] = EU_MEMBER_STATES | EEA_ONLY_STATES

#: Pseudo-codes that stand for a set of member states.
REGION_GROUPS: dict[str, frozenset[str]] = {
    "EU": EU_MEMBER_STATES | {"EU"},
    "EEA": EEA_STATES | {"EEA", "EU"},
}

# --- aliases ---

_COUNTRY_ALIASES: dict[str, str] = {
    "EUROPEAN UNION": "EU",
    "EUROPE": "EU",
    "EU27": "EU",
    "EU-27": "EU",
    "EEA": "EEA",
    "EUROPEAN ECONOMIC AREA": "EEA",
    "GERMANY": "DE",
    "FRANCE": "FR",
    "IRELAND": "IE",
    "NETHERLANDS": "NL",
    "SPAIN": "ES",
    "ITALY": "IT",
    "POLAND": "PL",
    "SWEDEN": "SE",
    "CHINA": "CN",
    "PRC": "CN",
    "PEOPLES REPUBLIC OF CHINA": "CN",
    "PEOPLE'S REPUBLIC OF CHINA": "CN",
    "MAINLAND CHINA": "CN",
    "CHN": "CN",
    "INDIA": "IN",
    "IND": "IN",
    "BHARAT": "IN",
    "UNITED STATES": "US",
    "UNITED STATES OF AMERICA": "US",
    "USA": "US",
    "US": "US",
    "UNITED KINGDOM": "GB",
    "UK": "GB",
    "BRAZIL": "BR",
    "CANADA": "CA-COUNTRY",
    "CAN": "CA-COUNTRY",
    "WORLDWIDE": "GLOBAL",
    "GLOBAL": "GLOBAL",
    "ANYWHERE": "GLOBAL",
    "PUBLIC_INTERNET": "GLOBAL",
    "PUBLIC INTERNET": "GLOBAL",
}

_US_STATE_ALIASES: dict[str, str] = {
    "CALIFORNIA": "US-CA",
    "CALIF": "US-CA",
    "US-CA": "US-CA",
    "US_CA": "US-CA",
    "USA-CA": "US-CA",
    "CA-US": "US-CA",
    "CA/US": "US-CA",
    "NEW YORK": "US-NY",
    "US-NY": "US-NY",
    "COLORADO": "US-CO",
    "US-CO": "US-CO",
    "ILLINOIS": "US-IL",
    "US-IL": "US-IL",
    "TEXAS": "US-TX",
    "US-TX": "US-TX",
}

#: ``CA`` is genuinely ambiguous: ISO 3166-1 says Canada, while this console (and most
#: AI-governance tooling) uses it for California. Bare ``CA`` therefore resolves to
#: California, and Canada must be written ``CA-COUNTRY`` or ``Canada``. Callers that need
#: the opposite convention can pass ``ambiguous_ca`` to :func:`normalize_region`.
DEFAULT_AMBIGUOUS_CA = "US-CA"


def normalize_region(value: str, *, ambiguous_ca: str = DEFAULT_AMBIGUOUS_CA) -> str:
    """Fold one free-form region string to its canonical code."""
    token = value.strip().upper().replace("_", "-")
    if not token:
        return ""
    if token == "CA":
        return ambiguous_ca
    if token in _US_STATE_ALIASES:
        return _US_STATE_ALIASES[token]
    if token in _COUNTRY_ALIASES:
        return _COUNTRY_ALIASES[token]
    # "DE-BY" style subdivisions collapse to their country unless we know the state.
    if "-" in token and not token.startswith("US-"):
        head = token.split("-", 1)[0]
        if len(head) == 2:
            return head
    return token


def normalize_regions(
    values: Iterable[str] | None, *, ambiguous_ca: str = DEFAULT_AMBIGUOUS_CA
) -> frozenset[str]:
    """Normalise a collection of region strings, dropping blanks."""
    if not values:
        return frozenset()
    return frozenset(
        code
        for code in (normalize_region(v, ambiguous_ca=ambiguous_ca) for v in values if v)
        if code
    )


def expand_region(code: str) -> frozenset[str]:
    """Expand a group pseudo-code (``EU``, ``EEA``) into its member states."""
    return REGION_GROUPS.get(code, frozenset({code}))


def expand_regions(codes: Iterable[str]) -> frozenset[str]:
    expanded: set[str] = set()
    for code in codes:
        expanded |= expand_region(code)
    return frozenset(expanded)


def regions_intersect(declared: frozenset[str], territories: frozenset[str]) -> frozenset[str]:
    """Territories matched by a declared region set, honouring group membership.

    ``{"DE"}`` matches the EU territory set, and a declared ``{"EU"}`` matches the
    individual member states a jurisdiction lists. ``GLOBAL`` matches everything: a
    service on the public internet reaches every territory.
    """
    if not declared or not territories:
        return frozenset()
    if "GLOBAL" in declared:
        return territories
    return expand_regions(declared) & expand_regions(territories)


def collapse_regions(codes: Iterable[str]) -> list[str]:
    """Fold a matched territory set back into the tersest readable form.

    All 27 member states collapse to ``EU`` so explanations read "Offered to users in EU"
    rather than listing every country.
    """
    remaining = set(codes)
    collapsed: list[str] = []
    # Largest group first, so EEA wins over EU when both are fully covered.
    for group, members in (("EEA", EEA_STATES), ("EU", EU_MEMBER_STATES)):
        if not members:
            continue
        # Emit the group when every member is present, or when the group code itself is.
        if members <= remaining or group in remaining:
            collapsed.append(group)
            remaining -= members
            remaining.discard(group)
    collapsed.extend(sorted(remaining))
    return collapsed

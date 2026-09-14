"""JurisdictionEngine — decide which regulatory regimes apply to an AI system.

The engine is **pure**: :class:`JurisdictionEngine` holds a set of
:class:`JurisdictionRule` values and evaluates them against a :class:`SystemProfile`, a
frozen snapshot of the metadata that matters for applicability. No database session, no
network, no clock. Everything the rules need is on the profile, so the whole decision
surface is unit-testable with plain dataclasses.

Two adapters sit at the edges and are the only impure parts of this module:

* :meth:`SystemProfile.from_system` reads an already-loaded ORM object (no queries).
* :func:`rules_from_jurisdiction_rows` turns already-loaded ``Jurisdiction`` rows into
  rules, and :func:`load_engine` performs the single query that fetches them.

Applicability model
-------------------
Every rule lists **triggers** by name. A trigger is a pure function that inspects the
profile and either returns a reason or returns ``None``. Triggers come in two kinds:

``NEXUS``
    Establishes jurisdiction on its own — deployment, offering, data subjects, data
    residency, reachability, consequential decisions.
``AMPLIFIER``
    Never establishes jurisdiction by itself; it raises confidence and records extra
    reasoning once some nexus has already fired. Processing biometrics does not drag the
    EU AI Act over a US-only system, but it is worth recording once the EU already
    applies.

That split is the main correctness property here: a jurisdiction is applicable only if at
least one territorial nexus fired.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger
from app.services.regions import (
    collapse_regions,
    normalize_region,
    normalize_regions,
    regions_intersect,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from sqlalchemy.orm import Session

    from app.models.ai_system import AISystem, SystemMetadata
    from app.models.jurisdiction import Jurisdiction

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SystemProfile:
    """Normalised, immutable view of the metadata applicability depends on."""

    deployment_regions: frozenset[str] = frozenset()
    data_subject_regions: frozenset[str] = frozenset()
    data_residency_regions: frozenset[str] = frozenset()
    offered_in_regions: frozenset[str] = frozenset()
    service_accessible_regions: frozenset[str] = frozenset()
    content_accessible_regions: frozenset[str] = frozenset()
    use_case: str | None = None
    industry: str | None = None
    autonomy_level: str | None = None
    data_categories: frozenset[str] = frozenset()
    third_party_models: tuple[str, ...] = ()
    uses_generative_ai: bool = False
    uses_biometrics: bool = False
    affects_minors: bool = False
    makes_automated_decisions: bool = False
    is_safety_component: bool = False
    attributes: Mapping[str, Any] = field(default_factory=dict)
    system_id: str | None = None
    system_name: str | None = None

    # -- convenience accessors used by triggers --

    @property
    def audience_regions(self) -> frozenset[str]:
        """Everywhere real people meet this system: offered to, or subjects of."""
        return self.offered_in_regions | self.data_subject_regions

    @property
    def reachable_regions(self) -> frozenset[str]:
        """Everywhere the service can be used, whether or not it is marketed there."""
        return self.service_accessible_regions | self.offered_in_regions

    @classmethod
    def from_metadata(
        cls,
        metadata: SystemMetadata | None,
        *,
        system_id: str | None = None,
        system_name: str | None = None,
    ) -> SystemProfile:
        """Build a profile from a ``SystemMetadata`` row (or nothing at all)."""
        if metadata is None:
            return cls(system_id=system_id, system_name=system_name)
        return cls(
            deployment_regions=normalize_regions(metadata.deployment_regions),
            data_subject_regions=normalize_regions(metadata.data_subject_regions),
            data_residency_regions=normalize_regions(metadata.data_residency),
            offered_in_regions=normalize_regions(metadata.offered_in_regions),
            service_accessible_regions=normalize_regions(metadata.service_accessible_regions),
            content_accessible_regions=normalize_regions(metadata.content_accessible_regions),
            use_case=(metadata.use_case or "").strip().lower() or None,
            industry=(metadata.industry or "").strip().lower() or None,
            autonomy_level=str(metadata.autonomy_level) if metadata.autonomy_level else None,
            data_categories=frozenset(
                c.strip().lower() for c in (metadata.data_categories or []) if c
            ),
            third_party_models=tuple(metadata.third_party_models or []),
            uses_generative_ai=bool(metadata.uses_generative_ai),
            uses_biometrics=bool(metadata.uses_biometrics),
            affects_minors=bool(metadata.affects_minors),
            makes_automated_decisions=bool(metadata.makes_automated_decisions),
            is_safety_component=bool(metadata.is_safety_component),
            attributes=dict(metadata.attributes or {}),
            system_id=system_id,
            system_name=system_name,
        )

    @classmethod
    def from_system(cls, system: AISystem) -> SystemProfile:
        """Adapter over a loaded ``AISystem``. Issues no queries of its own."""
        return cls.from_metadata(
            system.system_metadata,
            system_id=str(system.id),
            system_name=system.name,
        )


# ---------------------------------------------------------------------------
# Rules and triggers
# ---------------------------------------------------------------------------


class TriggerKind(StrEnum):
    NEXUS = "nexus"
    AMPLIFIER = "amplifier"


@dataclass(frozen=True, slots=True)
class TriggerOutcome:
    """What one trigger found."""

    signal: str
    reason: str
    confidence: float
    kind: TriggerKind = TriggerKind.NEXUS
    matched_territories: tuple[str, ...] = ()


TriggerFn = Callable[[SystemProfile, "JurisdictionRule"], TriggerOutcome | None]


@dataclass(frozen=True, slots=True)
class Trigger:
    name: str
    kind: TriggerKind
    fn: TriggerFn
    description: str = ""

    def __call__(self, profile: SystemProfile, rule: JurisdictionRule) -> TriggerOutcome | None:
        return self.fn(profile, rule)


TRIGGER_REGISTRY: dict[str, Trigger] = {}


def register_trigger(
    name: str, kind: TriggerKind, description: str = ""
) -> Callable[[TriggerFn], TriggerFn]:
    """Register a named trigger so rules (and stored config) can reference it."""

    def decorator(fn: TriggerFn) -> TriggerFn:
        TRIGGER_REGISTRY[name] = Trigger(name=name, kind=kind, fn=fn, description=description)
        return fn

    return decorator


@dataclass(frozen=True, slots=True)
class JurisdictionRule:
    """Configuration for one regulatory regime."""

    code: str
    name: str
    territories: frozenset[str] = frozenset()
    #: Higher wins when regimes conflict. Drives evaluation order and "most restrictive".
    strictness: int = 50
    triggers: tuple[str, ...] = ()
    #: Applies to every system regardless of location (internal baselines).
    always_applicable: bool = False
    #: Decisions that materially affect a person's life, for consequential-decision rules.
    consequential_use_cases: frozenset[str] = frozenset()
    regulation_name: str | None = None
    #: Free-form knobs individual triggers read.
    options: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> JurisdictionRule:
        """Build a rule from a plain mapping (stored JSON, YAML, a fixture)."""
        unknown = [t for t in config.get("triggers", ()) if t not in TRIGGER_REGISTRY]
        if unknown:
            raise ValueError(
                f"Jurisdiction '{config.get('code')}' references unknown triggers: {unknown}. "
                f"Known triggers: {sorted(TRIGGER_REGISTRY)}"
            )
        return cls(
            code=str(config["code"]).upper(),
            name=str(config.get("name") or config["code"]),
            territories=normalize_regions(config.get("territories") or []),
            strictness=int(config.get("strictness", 50)),
            triggers=tuple(config.get("triggers") or DEFAULT_TRIGGERS),
            always_applicable=bool(config.get("always_applicable", False)),
            consequential_use_cases=frozenset(
                str(u).lower() for u in config.get("consequential_use_cases") or ()
            ),
            regulation_name=config.get("regulation_name"),
            options=dict(config.get("options") or {}),
        )


# ---------------------------------------------------------------------------
# Built-in triggers
# ---------------------------------------------------------------------------


def _fmt(territories: Iterable[str]) -> str:
    """Render matched territories for humans, collapsing groups (27 states -> "EU")."""
    return ", ".join(collapse_regions(territories))


@register_trigger("deployment_nexus", TriggerKind.NEXUS, "The system runs inside the territory.")
def _deployment_nexus(p: SystemProfile, rule: JurisdictionRule) -> TriggerOutcome | None:
    matched = regions_intersect(p.deployment_regions, rule.territories)
    if not matched:
        return None
    return TriggerOutcome(
        signal="deployment_nexus",
        reason=f"Deployed in {_fmt(matched)}",
        confidence=0.98,
        matched_territories=tuple(collapse_regions(matched)),
    )


@register_trigger(
    "offering_nexus", TriggerKind.NEXUS, "The system is offered to users in the territory."
)
def _offering_nexus(p: SystemProfile, rule: JurisdictionRule) -> TriggerOutcome | None:
    matched = regions_intersect(p.offered_in_regions, rule.territories)
    if not matched:
        return None
    return TriggerOutcome(
        signal="offering_nexus",
        reason=f"Offered to users in {_fmt(matched)}",
        confidence=0.95,
        matched_territories=tuple(collapse_regions(matched)),
    )


@register_trigger(
    "data_subject_nexus", TriggerKind.NEXUS, "Data subjects are located in the territory."
)
def _data_subject_nexus(p: SystemProfile, rule: JurisdictionRule) -> TriggerOutcome | None:
    matched = regions_intersect(p.data_subject_regions, rule.territories)
    if not matched:
        return None
    return TriggerOutcome(
        signal="data_subject_nexus",
        reason=f"Data subjects located in {_fmt(matched)}",
        confidence=0.92,
        matched_territories=tuple(collapse_regions(matched)),
    )


@register_trigger(
    "data_residency_nexus", TriggerKind.NEXUS, "Data is stored or processed in the territory."
)
def _data_residency_nexus(p: SystemProfile, rule: JurisdictionRule) -> TriggerOutcome | None:
    matched = regions_intersect(p.data_residency_regions, rule.territories)
    if not matched:
        return None
    return TriggerOutcome(
        signal="data_residency_nexus",
        reason=f"Data processed or stored in {_fmt(matched)}",
        confidence=0.9,
        matched_territories=tuple(collapse_regions(matched)),
    )


@register_trigger(
    "service_accessibility_nexus",
    TriggerKind.NEXUS,
    "The service can be reached from the territory even if not marketed there.",
)
def _service_accessibility_nexus(p: SystemProfile, rule: JurisdictionRule) -> TriggerOutcome | None:
    matched = regions_intersect(p.service_accessible_regions, rule.territories)
    if not matched:
        return None
    return TriggerOutcome(
        signal="service_accessibility_nexus",
        reason=f"Service is accessible from {_fmt(matched)}",
        confidence=0.75,
        matched_territories=tuple(collapse_regions(matched)),
    )


@register_trigger(
    "generated_content_accessibility_nexus",
    TriggerKind.NEXUS,
    "Generated output can be viewed from the territory.",
)
def _content_accessibility_nexus(p: SystemProfile, rule: JurisdictionRule) -> TriggerOutcome | None:
    if not p.uses_generative_ai:
        return None
    matched = regions_intersect(p.content_accessible_regions, rule.territories)
    if not matched:
        return None
    return TriggerOutcome(
        signal="generated_content_accessibility_nexus",
        reason=f"Generated content is accessible from {_fmt(matched)}",
        confidence=0.72,
        matched_territories=tuple(collapse_regions(matched)),
    )


@register_trigger(
    "consequential_decision_nexus",
    TriggerKind.NEXUS,
    "Automated consequential decisions are made about residents of the territory.",
)
def _consequential_decision_nexus(
    p: SystemProfile, rule: JurisdictionRule
) -> TriggerOutcome | None:
    if not p.makes_automated_decisions:
        return None
    consequential = rule.consequential_use_cases or DEFAULT_CONSEQUENTIAL_USE_CASES
    if p.use_case not in consequential:
        return None
    matched = regions_intersect(p.audience_regions, rule.territories)
    if not matched:
        return None
    return TriggerOutcome(
        signal="consequential_decision_nexus",
        reason=(f"Makes automated '{p.use_case}' decisions about residents of {_fmt(matched)}"),
        confidence=0.9,
        matched_territories=tuple(collapse_regions(matched)),
    )


@register_trigger(
    "biometric_processing",
    TriggerKind.AMPLIFIER,
    "Biometric processing attracts heightened scrutiny once a regime applies.",
)
def _biometric_amplifier(p: SystemProfile, _: JurisdictionRule) -> TriggerOutcome | None:
    if not (p.uses_biometrics or "biometric" in p.data_categories):
        return None
    return TriggerOutcome(
        signal="biometric_processing",
        reason="Processes biometric data, which attracts heightened obligations",
        confidence=0.05,
        kind=TriggerKind.AMPLIFIER,
    )


@register_trigger(
    "childrens_data",
    TriggerKind.AMPLIFIER,
    "Processing children's data raises duties in most regimes.",
)
def _minors_amplifier(p: SystemProfile, _: JurisdictionRule) -> TriggerOutcome | None:
    if not (p.affects_minors or "children" in p.data_categories):
        return None
    return TriggerOutcome(
        signal="childrens_data",
        reason="Affects minors, which raises additional duties",
        confidence=0.05,
        kind=TriggerKind.AMPLIFIER,
    )


@register_trigger(
    "generative_ai_service",
    TriggerKind.AMPLIFIER,
    "Generative services carry extra transparency and filing duties.",
)
def _generative_amplifier(p: SystemProfile, _: JurisdictionRule) -> TriggerOutcome | None:
    if not p.uses_generative_ai:
        return None
    return TriggerOutcome(
        signal="generative_ai_service",
        reason="Generative AI service, subject to content and transparency duties",
        confidence=0.05,
        kind=TriggerKind.AMPLIFIER,
    )


@register_trigger(
    "always_applicable",
    TriggerKind.NEXUS,
    "Baseline regime that applies to every system.",
)
def _always_applicable(_: SystemProfile, rule: JurisdictionRule) -> TriggerOutcome | None:
    if not rule.always_applicable:
        return None
    return TriggerOutcome(
        signal="always_applicable",
        reason="Baseline regime applies to every system in the inventory",
        confidence=0.6,
    )


DEFAULT_TRIGGERS: tuple[str, ...] = (
    "always_applicable",
    "deployment_nexus",
    "offering_nexus",
    "data_subject_nexus",
    "data_residency_nexus",
)

#: Decisions materially affecting access to employment, credit, housing, healthcare,
#: education or essential services. Overridable per jurisdiction.
DEFAULT_CONSEQUENTIAL_USE_CASES: frozenset[str] = frozenset(
    {
        "employment_screening",
        "credit_scoring",
        "insurance_underwriting",
        "housing_allocation",
        "education_assessment",
        "medical_diagnosis",
        "essential_services",
        "benefits_eligibility",
        "criminal_sentencing",
    }
)


# ---------------------------------------------------------------------------
# Default rule set
# ---------------------------------------------------------------------------

DEFAULT_RULES: tuple[JurisdictionRule, ...] = (
    JurisdictionRule(
        code="GLOBAL",
        name="Global baseline",
        regulation_name="Organisation-wide AI governance baseline",
        territories=frozenset(),
        strictness=10,
        always_applicable=True,
        triggers=("always_applicable",),
    ),
    JurisdictionRule(
        code="EU",
        name="European Union",
        regulation_name="EU AI Act (Regulation (EU) 2024/1689)",
        # Group codes expand to member states, so a system in "DE" matches.
        territories=frozenset({"EU", "EEA"}),
        strictness=100,
        triggers=(
            "deployment_nexus",
            "offering_nexus",
            "data_subject_nexus",
            "data_residency_nexus",
            "consequential_decision_nexus",
            "biometric_processing",
            "childrens_data",
            "generative_ai_service",
        ),
    ),
    JurisdictionRule(
        code="CN",
        name="People's Republic of China",
        regulation_name="Interim Measures for Generative AI Services; PIPL",
        territories=frozenset({"CN"}),
        strictness=90,
        triggers=(
            "deployment_nexus",
            "offering_nexus",
            "data_subject_nexus",
            "data_residency_nexus",
            "service_accessibility_nexus",
            "generated_content_accessibility_nexus",
            "generative_ai_service",
            "biometric_processing",
        ),
    ),
    JurisdictionRule(
        code="CA",
        name="California, USA",
        regulation_name="California AI Transparency Act; CCPA/CPRA ADMT rules",
        territories=frozenset({"US-CA"}),
        strictness=70,
        triggers=(
            "deployment_nexus",
            "offering_nexus",
            "data_subject_nexus",
            "data_residency_nexus",
            "consequential_decision_nexus",
            "childrens_data",
        ),
    ),
    JurisdictionRule(
        code="IN",
        name="India",
        regulation_name="Digital Personal Data Protection Act 2023",
        territories=frozenset({"IN"}),
        strictness=60,
        triggers=(
            "deployment_nexus",
            "offering_nexus",
            "data_subject_nexus",
            "data_residency_nexus",
            "childrens_data",
        ),
    ),
)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class JurisdictionVerdict:
    """Why one jurisdiction did or did not apply."""

    code: str
    name: str
    applicable: bool
    confidence: float
    reasons: tuple[str, ...]
    signals: tuple[str, ...]
    strictness: int
    regulation_name: str | None = None
    matched_territories: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class JurisdictionAssessment:
    """Full result of one evaluation."""

    verdicts: tuple[JurisdictionVerdict, ...]
    #: Codes in the order risk should be evaluated: strictest regime first.
    evaluation_order: tuple[str, ...]
    #: Codes that win when obligations conflict (all sharing the top strictness).
    most_restrictive: tuple[str, ...]
    #: True when more than one regime applies, so conflicts are possible.
    apply_most_restrictive: bool
    conflict_notes: tuple[str, ...] = ()

    @property
    def applicable(self) -> tuple[JurisdictionVerdict, ...]:
        return tuple(v for v in self.verdicts if v.applicable)

    @property
    def applicable_codes(self) -> tuple[str, ...]:
        return tuple(v.code for v in self.applicable)

    @property
    def primary(self) -> str | None:
        """Single strictest regime, or ``None`` when nothing applies."""
        return self.most_restrictive[0] if self.most_restrictive else None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class JurisdictionEngine:
    """Pure applicability engine over a configurable rule set."""

    def __init__(
        self,
        rules: Sequence[JurisdictionRule] | None = None,
        *,
        registry: Mapping[str, Trigger] | None = None,
    ) -> None:
        self.rules: tuple[JurisdictionRule, ...] = tuple(
            rules if rules is not None else DEFAULT_RULES
        )
        self.registry: Mapping[str, Trigger] = (
            registry if registry is not None else TRIGGER_REGISTRY
        )

    # -- construction helpers --

    @classmethod
    def from_config(cls, configs: Iterable[Mapping[str, Any]]) -> JurisdictionEngine:
        return cls([JurisdictionRule.from_config(c) for c in configs])

    # -- core evaluation --

    def evaluate(self, profile: SystemProfile) -> JurisdictionAssessment:
        """Evaluate every rule against ``profile``. Deterministic and side-effect free."""
        verdicts = tuple(self._evaluate_rule(rule, profile) for rule in self.rules)
        applicable = [v for v in verdicts if v.applicable]

        # Strictest first, then by confidence, then by code so ties are deterministic.
        ordered = sorted(applicable, key=lambda v: (-v.strictness, -v.confidence, v.code))
        evaluation_order = tuple(v.code for v in ordered)
        most_restrictive = self._top_by_strictness(applicable)
        conflict_notes = self._conflict_notes(ordered)

        assessment = JurisdictionAssessment(
            verdicts=tuple(sorted(verdicts, key=lambda v: (-v.strictness, v.code))),
            evaluation_order=evaluation_order,
            most_restrictive=most_restrictive,
            apply_most_restrictive=len(applicable) > 1,
            conflict_notes=conflict_notes,
        )
        logger.info(
            "jurisdictions_evaluated",
            ai_system_id=profile.system_id,
            applicable=list(evaluation_order),
            most_restrictive=list(most_restrictive),
        )
        return assessment

    def _evaluate_rule(self, rule: JurisdictionRule, profile: SystemProfile) -> JurisdictionVerdict:
        nexus_outcomes: list[TriggerOutcome] = []
        amplifier_outcomes: list[TriggerOutcome] = []

        for name in rule.triggers:
            trigger = self.registry.get(name)
            if trigger is None:
                # Configuration drift should be loud but must not break evaluation.
                logger.warning("unknown_trigger", trigger=name, jurisdiction=rule.code)
                continue
            outcome = trigger(profile, rule)
            if outcome is None:
                continue
            if trigger.kind is TriggerKind.AMPLIFIER:
                amplifier_outcomes.append(outcome)
            else:
                nexus_outcomes.append(outcome)

        # An amplifier alone can never establish jurisdiction.
        if not nexus_outcomes:
            return JurisdictionVerdict(
                code=rule.code,
                name=rule.name,
                applicable=False,
                confidence=0.0,
                reasons=(
                    "No deployment, offering, data-subject, residency or "
                    "accessibility nexus detected",
                ),
                signals=(),
                strictness=rule.strictness,
                regulation_name=rule.regulation_name,
            )

        base = max(o.confidence for o in nexus_outcomes)
        boost = sum(o.confidence for o in amplifier_outcomes)
        outcomes = sorted(nexus_outcomes + amplifier_outcomes, key=lambda o: -o.confidence)
        territories = collapse_regions({t for o in nexus_outcomes for t in o.matched_territories})

        return JurisdictionVerdict(
            code=rule.code,
            name=rule.name,
            applicable=True,
            confidence=round(min(base + boost, 1.0), 2),
            reasons=tuple(o.reason for o in outcomes),
            signals=tuple(o.signal for o in outcomes),
            strictness=rule.strictness,
            regulation_name=rule.regulation_name,
            matched_territories=tuple(territories),
        )

    # -- priority helpers --

    def get_most_restrictive_jurisdictions(
        self, assessment: JurisdictionAssessment | Sequence[JurisdictionVerdict]
    ) -> list[str]:
        """Jurisdictions that take priority when obligations conflict.

        Returns every code sharing the highest strictness — ties are real (two regimes
        can be equally strict) and callers must satisfy all of them, so the answer is a
        list rather than a single winner.
        """
        verdicts = (
            assessment.applicable
            if isinstance(assessment, JurisdictionAssessment)
            else [v for v in assessment if v.applicable]
        )
        return list(self._top_by_strictness(verdicts))

    @staticmethod
    def _top_by_strictness(verdicts: Sequence[JurisdictionVerdict]) -> tuple[str, ...]:
        if not verdicts:
            return ()
        top = max(v.strictness for v in verdicts)
        return tuple(sorted(v.code for v in verdicts if v.strictness == top))

    @staticmethod
    def _conflict_notes(ordered: Sequence[JurisdictionVerdict]) -> tuple[str, ...]:
        if len(ordered) < 2:
            return ()
        notes = [
            f"{len(ordered)} regimes apply ({', '.join(v.code for v in ordered)}); "
            f"apply the strictest obligation wherever they differ."
        ]
        top = ordered[0]
        peers = [v for v in ordered[1:] if v.strictness == top.strictness]
        if peers:
            tied = ", ".join([top.code, *(v.code for v in peers)])
            notes.append(f"{tied} are equally strict; all of their obligations must be met.")
        return tuple(notes)


# ---------------------------------------------------------------------------
# Persistence adapters (the only impure code in this module)
# ---------------------------------------------------------------------------


def _coerce_triggers(configured: Any, fallback: tuple[str, ...], code: str) -> tuple[str, ...]:
    """Accept a stored trigger list, ignoring anything the registry does not know.

    Older configurations stored triggers as a ``{field: reason}`` mapping. Those names are
    not registered triggers, so they are dropped and the built-in defaults are used
    instead — a stale row must not silently switch a jurisdiction off.
    """
    if not configured:
        return fallback
    names = list(configured) if isinstance(configured, list | tuple | set) else list(configured)
    known = tuple(n for n in names if n in TRIGGER_REGISTRY)
    if not known:
        logger.warning(
            "jurisdiction_triggers_unrecognised_using_defaults",
            jurisdiction=code,
            configured=names,
        )
        return fallback
    if len(known) != len(names):
        logger.warning(
            "jurisdiction_triggers_partially_unrecognised",
            jurisdiction=code,
            dropped=[n for n in names if n not in TRIGGER_REGISTRY],
        )
    return known


def rules_from_jurisdiction_rows(rows: Iterable[Jurisdiction]) -> list[JurisdictionRule]:
    """Translate loaded ``Jurisdiction`` rows into rules. Pure: no queries here.

    Falls back to the built-in defaults for any regime whose stored ``overlay_config``
    does not name its own triggers, so a freshly seeded database behaves correctly
    before anybody tunes the configuration.
    """
    defaults = {r.code: r for r in DEFAULT_RULES}
    rules: list[JurisdictionRule] = []
    for row in rows:
        code = row.code.upper()
        overlay: Mapping[str, Any] = row.overlay_config or {}
        fallback = defaults.get(code)
        triggers = _coerce_triggers(
            overlay.get("triggers"),
            fallback.triggers if fallback else DEFAULT_TRIGGERS,
            code,
        )
        territories = normalize_regions(row.territories or []) or (
            fallback.territories if fallback else frozenset({normalize_region(code)})
        )
        strictness = int(overlay.get("strictness", fallback.strictness if fallback else 50))
        consequential = overlay.get("consequential_use_cases")
        rules.append(
            JurisdictionRule(
                code=code,
                name=row.name,
                regulation_name=row.regulation_name,
                territories=territories,
                strictness=strictness,
                triggers=tuple(triggers),
                always_applicable=bool(
                    overlay.get(
                        "always_applicable",
                        fallback.always_applicable if fallback else False,
                    )
                ),
                consequential_use_cases=(
                    frozenset(str(u).lower() for u in consequential)
                    if consequential
                    else (fallback.consequential_use_cases if fallback else frozenset())
                ),
                options=dict(overlay.get("options") or {}),
            )
        )
    return rules


def load_engine(db: Session) -> JurisdictionEngine:
    """Build an engine from the active jurisdictions. The single DB touch point."""
    from sqlalchemy import select

    from app.models.jurisdiction import Jurisdiction as JurisdictionModel

    rows = (
        db.execute(
            select(JurisdictionModel)
            .where(JurisdictionModel.is_active.is_(True))
            .order_by(JurisdictionModel.code)
        )
        .scalars()
        .all()
    )
    rules = rules_from_jurisdiction_rows(rows)
    if not rules:
        logger.warning("no_active_jurisdictions_configured_using_defaults")
        return JurisdictionEngine()
    return JurisdictionEngine(rules)

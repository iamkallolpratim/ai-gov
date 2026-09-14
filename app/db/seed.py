"""Idempotent seed data: jurisdictions, risk taxonomies, policies, users, sample systems."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import hash_password
from app.db.session import session_scope
from app.models.ai_system import AISystem, SystemMetadata, SystemMetadataVersion
from app.models.enums import AutonomyLevel, PolicySeverity, SystemStatus, UserRole
from app.models.jurisdiction import Jurisdiction
from app.models.policy import Policy
from app.models.user import User

logger = get_logger(__name__)

POLICY_DIR = Path(__file__).resolve().parents[2] / "policies"

JURISDICTIONS: list[dict[str, Any]] = [
    {
        "code": "GLOBAL",
        "name": "Global baseline",
        "regulation_name": "Organisation-wide AI governance baseline",
        "description": (
            "Applies to every system regardless of location. Regional overlays add to, "
            "and never subtract from, this baseline."
        ),
        "territories": [],
        "overlay_config": {
            "strictness": 10,
            "always_applicable": True,
            "triggers": ["always_applicable"],
        },
        "risk_taxonomy": {
            "tier_labels": {
                "prohibited": "Banned internally",
                "high": "High risk",
                "limited": "Limited risk",
                "minimal": "Minimal risk",
            },
            "obligations": {
                "high": ["Internal AI review board sign-off", "Documented human oversight"],
                "limited": ["Disclose AI use to affected people"],
            },
        },
    },
    {
        "code": "EU",
        "name": "European Union",
        "regulation_name": "EU AI Act (Regulation (EU) 2024/1689)",
        "description": "Risk-based horizontal AI regulation with extraterritorial reach.",
        "territories": [
            "EU",
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
        ],
        "overlay_config": {
            "strictness": 100,
            "triggers": [
                "deployment_nexus",
                "offering_nexus",
                "data_subject_nexus",
                "data_residency_nexus",
                "consequential_decision_nexus",
                "biometric_processing",
                "childrens_data",
                "generative_ai_service",
            ],
        },
        "risk_taxonomy": {
            "tier_labels": {
                "prohibited": "Prohibited practice (Art. 5)",
                "high": "High-risk (Annex III / Art. 6)",
                "limited": "Limited risk — transparency obligations (Art. 50)",
                "minimal": "Minimal risk",
            },
            "prohibited_use_cases": [
                "social_scoring",
                "subliminal_manipulation",
                "emotion_recognition_workplace",
                "untargeted_face_scraping",
                "predictive_policing_individual",
            ],
            "high_risk_use_cases": [
                "employment_screening",
                "credit_scoring",
                "biometric_identification",
                "law_enforcement",
                "critical_infrastructure",
                "education_assessment",
                "migration_asylum",
                "essential_services",
                "medical_diagnosis",
            ],
            "escalate_if": {"is_safety_component": "high"},
            "obligations": {
                "high": [
                    "Risk management system (Art. 9)",
                    "Data governance (Art. 10)",
                    "Technical documentation (Art. 11)",
                    "Record keeping (Art. 12)",
                    "Human oversight (Art. 14)",
                    "Conformity assessment (Art. 43)",
                ],
                "limited": ["Transparency disclosure to users (Art. 50)"],
            },
        },
    },
    {
        "code": "CA",
        "name": "California, USA",
        "regulation_name": "California AI Transparency Act / CCPA-CPRA ADMT regulations",
        "description": "Sectoral US state rules on automated decision-making and AI disclosure.",
        "territories": ["US-CA", "CA-US", "CALIFORNIA"],
        "overlay_config": {
            "strictness": 70,
            "triggers": [
                "deployment_nexus",
                "offering_nexus",
                "data_subject_nexus",
                "data_residency_nexus",
                "consequential_decision_nexus",
                "childrens_data",
            ],
            "consequential_use_cases": [
                "employment_screening",
                "credit_scoring",
                "housing_allocation",
                "insurance_underwriting",
                "education_assessment",
                "essential_services",
            ],
        },
        "risk_taxonomy": {
            "tier_labels": {
                "high": "Significant-decision ADMT",
                "limited": "Disclosure-required AI",
                "minimal": "Minimal risk",
            },
            "high_risk_use_cases": [
                "employment_screening",
                "credit_scoring",
                "essential_services",
                "education_assessment",
            ],
            "escalate_if": {"makes_automated_decisions": "limited"},
            "obligations": {
                "high": [
                    "Pre-use notice to consumers",
                    "Opt-out and human appeal route",
                    "Annual risk assessment filed with the CPPA",
                ],
                "limited": ["Disclose that content or interaction is AI-generated"],
            },
        },
    },
    {
        "code": "CN",
        "name": "People's Republic of China",
        "regulation_name": (
            "Interim Measures for Generative AI Services; PIPL; Algorithm Filing rules"
        ),
        "description": "Filing, security assessment, and data localisation obligations.",
        "territories": ["CN", "PRC", "CHINA"],
        "overlay_config": {
            "strictness": 90,
            "triggers": [
                "deployment_nexus",
                "offering_nexus",
                "data_subject_nexus",
                "data_residency_nexus",
                "service_accessibility_nexus",
                "generated_content_accessibility_nexus",
                "generative_ai_service",
                "biometric_processing",
            ],
        },
        "risk_taxonomy": {
            "tier_labels": {
                "prohibited": "Prohibited service",
                "high": "Service with public-opinion attributes",
                "limited": "Filing-only service",
                "minimal": "Minimal risk",
            },
            "prohibited_use_cases": ["untargeted_face_scraping", "social_scoring"],
            "high_risk_use_cases": [
                "biometric_identification",
                "law_enforcement",
                "medical_diagnosis",
            ],
            "escalate_if": {"uses_generative_ai": "high"},
            "minimum_tier": "limited",
            "obligations": {
                "high": [
                    "Algorithm filing with the CAC",
                    "Security assessment before public launch",
                    "Content labelling of synthetic media",
                    "Data localisation for personal information",
                ],
                "limited": ["Algorithm filing", "Content labelling"],
            },
        },
    },
    {
        "code": "IN",
        "name": "India",
        "regulation_name": "Digital Personal Data Protection Act 2023; MeitY AI guidelines",
        "description": "Consent-centric data protection with emerging AI governance guidance.",
        "territories": ["IN", "INDIA"],
        "overlay_config": {
            "strictness": 60,
            "triggers": [
                "deployment_nexus",
                "offering_nexus",
                "data_subject_nexus",
                "data_residency_nexus",
                "childrens_data",
            ],
        },
        "risk_taxonomy": {
            "tier_labels": {
                "high": "Significant data fiduciary workload",
                "limited": "Standard data fiduciary workload",
                "minimal": "Minimal risk",
            },
            "high_risk_use_cases": ["credit_scoring", "employment_screening", "medical_diagnosis"],
            "escalate_if": {"affects_minors": "high"},
            "obligations": {
                "high": [
                    "Data Protection Impact Assessment",
                    "Appoint a Data Protection Officer in India",
                    "Independent data audit",
                ],
                "limited": ["Consent notice", "Grievance redressal mechanism"],
            },
        },
    },
]


def _rego(filename: str) -> str | None:
    """Read a Rego file from the filesystem source of record."""
    path = POLICY_DIR / filename
    return path.read_text() if path.exists() else None


POLICIES: list[dict[str, Any]] = [
    {
        "key": "eu_ai_act_high_risk",
        "name": "EU AI Act — high-risk system obligations",
        "description": (
            "Chapter III Section 2 obligations (Art. 9-15) plus conformity assessment, "
            "EU database registration, post-market monitoring and incident reporting."
        ),
        "jurisdiction_code": "EU",
        "version": "1.0.0",
        "severity": PolicySeverity.CRITICAL,
        "opa_package": "aigov.eu.high_risk",
        "rego_file": "eu/eu_high_risk.rego",
        "applies_to_risk_tiers": ["high", "prohibited"],
        "remediation": (
            "Complete the Chapter III Section 2 obligations before placing the system on "
            "the EU market."
        ),
        # Declarative fallback used only when OPA is unreachable.
        "rules": {
            "require_true": [
                "human_oversight_documented",
                "conformity_assessment_done",
                "training_data_documented",
            ],
            "require_present": ["technical_documentation_url"],
        },
    },
    {
        "key": "eu_ai_act_prohibited",
        "name": "EU AI Act — prohibited practices (Art. 5)",
        "description": (
            "Bans on manipulation, social scoring, individual predictive policing, "
            "untargeted face scraping, workplace emotion recognition, sensitive "
            "biometric categorisation and unauthorised real-time biometric ID."
        ),
        "jurisdiction_code": "EU",
        "version": "1.0.0",
        "severity": PolicySeverity.CRITICAL,
        "opa_package": "aigov.eu.prohibited",
        "rego_file": "eu/eu_prohibited.rego",
        # Applies to every tier: a prohibited practice is not a tiering question.
        "applies_to_risk_tiers": [],
        "remediation": (
            "Withdraw the practice from the EU market or re-scope the use case so it no "
            "longer falls under Art. 5."
        ),
        "rules": {},
    },
    {
        "key": "eu_ai_act_transparency",
        "name": "EU AI Act — transparency duties (Art. 50)",
        "description": (
            "Disclosure of AI interaction, machine-readable marking of synthetic "
            "content, biometric processing notices, deep fake labelling and GPAI "
            "documentation."
        ),
        "jurisdiction_code": "EU",
        "version": "1.0.0",
        "severity": PolicySeverity.MEDIUM,
        "opa_package": "aigov.eu.transparency",
        "rego_file": "eu/eu_transparency.rego",
        "applies_to_risk_tiers": [],
        "remediation": (
            "Publish the required disclosures and enable machine-readable marking of "
            "generated content."
        ),
        "rules": {},
    },
    {
        "key": "global_transparency_baseline",
        "name": "Global baseline — AI transparency and vendor diligence",
        "description": "Content labelling, subject notice, and third-party model diligence.",
        "jurisdiction_code": "GLOBAL",
        "version": "1.0.0",
        "severity": PolicySeverity.MEDIUM,
        "opa_package": "aigov.global.transparency",
        "rego_file": "global/global_transparency.rego",
        "applies_to_risk_tiers": [],
        "remediation": (
            "Enable content provenance marking, publish subject notices, and sign vendor DPAs."
        ),
        "rules": {},
    },
]

#: Demo accounts. The password is public (it is in this file and the README), so the
#: seeder refuses to create them outside local/test unless SEED_DEMO_USERS is set
#: explicitly, and SEED_ADMIN_PASSWORD overrides it when it is.
DEMO_PASSWORD = "ChangeMe123!"

#: `example.com` is reserved by RFC 2606, so these addresses are valid syntax and can
#: never route anywhere. An earlier version used `@aigov.local`; `.local` is a reserved
#: special-use name that `email-validator` rejects, which made the demo accounts
#: impossible to log in with and broke every response that serialised one.
DEMO_EMAIL_DOMAIN = "aigov.example.com"
LEGACY_DEMO_EMAIL_DOMAIN = "aigov.local"

ADMIN_EMAIL = f"admin@{DEMO_EMAIL_DOMAIN}"

USERS: list[dict[str, Any]] = [
    {
        "email": ADMIN_EMAIL,
        "full_name": "Ada Admin",
        "password": DEMO_PASSWORD,
        "role": UserRole.ADMIN,
    },
    {
        "email": f"risk@{DEMO_EMAIL_DOMAIN}",
        "full_name": "Rosa Risk Officer",
        "password": DEMO_PASSWORD,
        "role": UserRole.RISK_OFFICER,
    },
    {
        "email": f"viewer@{DEMO_EMAIL_DOMAIN}",
        "full_name": "Vic Viewer",
        "password": DEMO_PASSWORD,
        "role": UserRole.VIEWER,
    },
]

SYSTEMS: list[dict[str, Any]] = [
    {
        "name": "Resume Screening Assistant",
        "description": (
            "Ranks and shortlists job applicants for recruiters across the EU and California."
        ),
        "status": SystemStatus.ACTIVE,
        "metadata": {
            "purpose": "Shortlist job applicants from submitted CVs.",
            "use_case": "employment_screening",
            "industry": "hr_tech",
            "autonomy_level": AutonomyLevel.HUMAN_IN_THE_LOOP,
            "data_categories": ["personal_data", "employment_history"],
            "deployment_regions": ["EU", "US-CA"],
            "data_subject_regions": ["EU", "US-CA"],
            "data_residency": ["EU"],
            "offered_in_regions": ["EU", "US-CA"],
            "service_accessible_regions": ["EU", "US-CA"],
            "content_accessible_regions": [],
            "third_party_models": ["claude-opus-5"],
            "makes_automated_decisions": True,
            "human_oversight_documented": True,
            "conformity_assessment_done": False,
            "training_data_documented": False,
            "incident_response_plan": True,
            "attributes": {"subject_notice_provided": True, "vendor_dpa_signed": False},
        },
    },
    {
        "name": "Customer Support Copilot",
        "description": "Generative assistant drafting replies for support agents worldwide.",
        "status": SystemStatus.ACTIVE,
        "metadata": {
            "purpose": "Draft support replies for human agents to review.",
            "use_case": "customer_support",
            "industry": "saas",
            "autonomy_level": AutonomyLevel.HUMAN_IN_THE_LOOP,
            "data_categories": ["personal_data", "support_tickets"],
            "deployment_regions": ["EU", "IN", "US-CA"],
            "data_subject_regions": ["EU", "IN"],
            "data_residency": ["EU"],
            "offered_in_regions": ["EU", "IN", "US-CA"],
            "service_accessible_regions": ["GLOBAL"],
            "content_accessible_regions": ["GLOBAL"],
            "third_party_models": ["claude-sonnet-5"],
            "uses_generative_ai": True,
            "human_oversight_documented": True,
            "training_data_documented": True,
            "incident_response_plan": True,
            "technical_documentation_url": "https://docs.internal/ai/support-copilot",
            "attributes": {"ai_content_labelled": False, "vendor_dpa_signed": True},
        },
    },
    {
        "name": "Storefront Face Analytics",
        "description": "Biometric footfall analytics piloted in retail stores in China and the EU.",
        "status": SystemStatus.DRAFT,
        "metadata": {
            "purpose": "Measure footfall and dwell time from in-store cameras.",
            "use_case": "biometric_identification",
            "industry": "retail",
            "autonomy_level": AutonomyLevel.FULLY_AUTONOMOUS,
            "data_categories": ["biometric", "personal_data"],
            "deployment_regions": ["CN", "EU"],
            "data_subject_regions": ["CN", "EU"],
            "data_residency": ["CN"],
            "offered_in_regions": ["CN", "EU"],
            "service_accessible_regions": ["CN", "EU"],
            "content_accessible_regions": [],
            "third_party_models": [],
            "uses_biometrics": True,
            "is_safety_component": False,
            "makes_automated_decisions": True,
            "human_oversight_documented": False,
            "conformity_assessment_done": False,
            "training_data_documented": False,
            "incident_response_plan": False,
            "attributes": {},
        },
    },
    {
        "name": "Warehouse Demand Forecaster",
        "description": "Forecasts stock replenishment; no personal data involved.",
        "status": SystemStatus.ACTIVE,
        "metadata": {
            "purpose": "Predict weekly SKU demand per warehouse.",
            "use_case": "demand_forecasting",
            "industry": "logistics",
            "autonomy_level": AutonomyLevel.HUMAN_ON_THE_LOOP,
            "data_categories": ["operational_data"],
            "deployment_regions": ["IN"],
            "data_subject_regions": [],
            "data_residency": ["IN"],
            "offered_in_regions": ["IN"],
            "service_accessible_regions": ["IN"],
            "content_accessible_regions": [],
            "third_party_models": [],
            "human_oversight_documented": True,
            "training_data_documented": True,
            "incident_response_plan": True,
            "attributes": {},
        },
    },
]


def seed_jurisdictions(db: Session) -> int:
    created = 0
    for payload in JURISDICTIONS:
        existing = db.execute(
            select(Jurisdiction).where(Jurisdiction.code == payload["code"])
        ).scalar_one_or_none()
        if existing:
            existing.risk_taxonomy = payload.get("risk_taxonomy", {})
            existing.overlay_config = payload.get("overlay_config", {})
            existing.territories = payload.get("territories", [])
            continue
        db.add(Jurisdiction(**payload, is_active=True))
        created += 1
    db.flush()
    return created


def seed_policies(db: Session) -> int:
    created = 0
    for payload in POLICIES:
        data = dict(payload)
        rego_file = data.pop("rego_file", None)
        existing = db.execute(
            select(Policy).where(Policy.key == data["key"], Policy.version == data["version"])
        ).scalar_one_or_none()
        rego = _rego(rego_file) if rego_file else None
        if existing:
            existing.rego_code = rego
            continue
        db.add(Policy(**data, rego_code=rego, is_active=True))
        created += 1
    db.flush()
    return created


def demo_users_allowed() -> bool:
    """Demo accounts are safe in local/test only, unless explicitly forced."""
    if settings.ENVIRONMENT in ("local", "test"):
        return True
    return os.getenv("SEED_DEMO_USERS", "").lower() in ("1", "true", "yes")


def migrate_legacy_demo_emails(db: Session) -> int:
    """Repair demo accounts seeded under the unusable `@aigov.local` domain.

    Those rows cannot be logged in with and raise a validation error whenever a response
    serialises them, so an existing database has to be healed rather than left alongside
    the new accounts. Only seeded demo rows can have this domain: the API rejects it on
    create, so nothing user-generated is touched.
    """
    legacy = list(
        db.execute(select(User).where(User.email.like(f"%@{LEGACY_DEMO_EMAIL_DOMAIN}")))
        .scalars()
        .all()
    )
    repaired = 0
    for user in legacy:
        local_part = user.email.split("@", 1)[0]
        replacement = f"{local_part}@{DEMO_EMAIL_DOMAIN}"
        existing = db.execute(select(User).where(User.email == replacement)).scalar_one_or_none()
        if existing is None:
            user.email = replacement
        else:
            # The new account already exists; retire the broken duplicate so it stops
            # breaking listings. Its audit history stays intact.
            user.is_deleted = True
            user.is_active = False
        repaired += 1
    if repaired:
        db.flush()
        logger.info("legacy_demo_emails_migrated", count=repaired)
    return repaired


def seed_users(db: Session) -> dict[str, User]:
    if not demo_users_allowed():
        raise RuntimeError(
            f"Refusing to seed demo accounts with a public password in "
            f"{settings.ENVIRONMENT}. Set SEED_DEMO_USERS=true together with "
            "SEED_ADMIN_PASSWORD if you really want them."
        )
    migrate_legacy_demo_emails(db)
    password = os.getenv("SEED_ADMIN_PASSWORD") or DEMO_PASSWORD
    users: dict[str, User] = {}
    for payload in USERS:
        user = db.execute(select(User).where(User.email == payload["email"])).scalar_one_or_none()
        if user is None:
            user = User(
                email=payload["email"],
                full_name=payload["full_name"],
                role=payload["role"],
                hashed_password=hash_password(password),
            )
            db.add(user)
        users[payload["email"]] = user
    db.flush()
    return users


def seed_systems(db: Session, owner: User) -> int:
    created = 0
    for payload in SYSTEMS:
        existing = db.execute(
            select(AISystem).where(AISystem.name == payload["name"])
        ).scalar_one_or_none()
        if existing:
            continue
        system = AISystem(
            name=payload["name"],
            description=payload["description"],
            status=payload["status"],
            owner_id=owner.id,
            extra_metadata={},
            metadata_version=1,
        )
        system.system_metadata = SystemMetadata(**payload["metadata"])
        db.add(system)
        db.flush()
        db.add(
            SystemMetadataVersion(
                ai_system_id=system.id,
                version=1,
                changed_by_id=owner.id,
                change_summary="Seeded",
                snapshot={"name": system.name, "seeded": True},
                diff={},
            )
        )
        created += 1
    db.flush()
    return created


def run_seed() -> dict[str, int]:
    with session_scope() as db:
        jurisdictions = seed_jurisdictions(db)
        policies = seed_policies(db)
        users = seed_users(db)
        systems = seed_systems(db, users[ADMIN_EMAIL])
        result = {
            "jurisdictions": jurisdictions,
            "policies": policies,
            "users": len(users),
            "systems": systems,
        }
    logger.info("seed_completed", **result)
    return result


if __name__ == "__main__":  # pragma: no cover
    print(run_seed())

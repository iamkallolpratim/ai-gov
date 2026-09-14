"""PolicyService: manage policies and evaluate systems against them via OPA.

Each policy is evaluated by POSTing an input document to its OPA package. The package
is expected to expose ``allow`` (bool) and ``violations`` (array of objects with
``msg`` and optional ``remediation``). If OPA is unreachable or the package is not
loaded, the service falls back to the policy's declarative ``rules`` document so a
check always produces an auditable record.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, PolicyEvaluationError
from app.core.logging import get_logger
from app.models.ai_system import AISystem
from app.models.enums import AuditAction, PolicyResult, PolicySeverity, RiskTier
from app.models.policy import Policy, PolicyCheck
from app.models.user import User
from app.schemas.policy import PolicyCreate, PolicyUpdate
from app.services.audit import record_audit
from app.services.opa import OPAClient, get_opa_client
from app.services.risk import RiskClassificationService

logger = get_logger(__name__)

# Severities that make a failing check block compliance rather than just warn.
BLOCKING_SEVERITIES = {PolicySeverity.CRITICAL, PolicySeverity.HIGH, PolicySeverity.MEDIUM}

SEVERITY_ORDER: dict[PolicySeverity, int] = {
    PolicySeverity.INFO: 0,
    PolicySeverity.LOW: 1,
    PolicySeverity.MEDIUM: 2,
    PolicySeverity.HIGH: 3,
    PolicySeverity.CRITICAL: 4,
}


class PolicyService:
    def __init__(self, db: Session, opa: OPAClient | None = None) -> None:
        self.db = db
        self.opa = opa or get_opa_client()
        self.risk_service = RiskClassificationService(db)

    # ---------- policy CRUD ----------

    def get(self, policy_id: uuid.UUID) -> Policy:
        policy = self.db.execute(
            select(Policy).where(Policy.id == policy_id, Policy.is_deleted.is_(False))
        ).scalar_one_or_none()
        if policy is None:
            raise NotFoundError(f"Policy {policy_id} not found.")
        return policy

    def list_policies(
        self,
        *,
        jurisdiction_code: str | None = None,
        is_active: bool | None = None,
        severity: PolicySeverity | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[Policy], int]:
        from sqlalchemy import func

        stmt = select(Policy).where(Policy.is_deleted.is_(False))
        if jurisdiction_code:
            stmt = stmt.where(Policy.jurisdiction_code == jurisdiction_code.upper())
        if is_active is not None:
            stmt = stmt.where(Policy.is_active.is_(is_active))
        if severity:
            stmt = stmt.where(Policy.severity == severity)
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(Policy.jurisdiction_code, Policy.key).offset(offset).limit(limit)
        return list(self.db.execute(stmt).scalars().all()), total

    def create(self, payload: PolicyCreate, actor: User, *, sync_opa: bool = True) -> Policy:
        policy = Policy(
            **payload.model_dump(exclude={"applies_to_risk_tiers", "jurisdiction_code"}),
            jurisdiction_code=payload.jurisdiction_code.upper(),
            applies_to_risk_tiers=[str(t) for t in payload.applies_to_risk_tiers],
        )
        self.db.add(policy)
        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                f"Policy '{payload.key}' version '{payload.version}' already exists."
            ) from exc
        if sync_opa and policy.rego_code:
            self._safe_push(policy)
        record_audit(
            self.db,
            resource_type="policy",
            resource_id=policy.id,
            action=AuditAction.CREATE,
            actor=actor,
            new_values={"key": policy.key, "version": policy.version},
        )
        return policy

    def update(
        self, policy_id: uuid.UUID, payload: PolicyUpdate, actor: User, *, sync_opa: bool = True
    ) -> Policy:
        policy = self.get(policy_id)
        data = payload.model_dump(exclude_unset=True)
        if "applies_to_risk_tiers" in data and data["applies_to_risk_tiers"] is not None:
            data["applies_to_risk_tiers"] = [str(t) for t in data["applies_to_risk_tiers"]]
        for field, value in data.items():
            setattr(policy, field, value)
        self.db.flush()
        if sync_opa and policy.rego_code:
            self._safe_push(policy)
        record_audit(
            self.db,
            resource_type="policy",
            resource_id=policy.id,
            action=AuditAction.UPDATE,
            actor=actor,
            new_values=data,
        )
        return policy

    def soft_delete(self, policy_id: uuid.UUID, actor: User) -> None:
        policy = self.get(policy_id)
        policy.soft_delete()
        policy.is_active = False
        self.db.flush()
        record_audit(
            self.db,
            resource_type="policy",
            resource_id=policy.id,
            action=AuditAction.DELETE,
            actor=actor,
        )

    def sync_all_to_opa(self) -> dict[str, int]:
        """Push shared libraries and every active policy's Rego into OPA.

        Libraries go first: a policy that imports ``data.aigov.eu.base`` will not
        compile in OPA until the base package is loaded.
        """
        libraries = self.sync_libraries_to_opa()
        policies, _ = self.list_policies(is_active=True, limit=1000)
        pushed = 0
        for policy in policies:
            if policy.rego_code and self._safe_push(policy):
                pushed += 1
        return {"libraries": libraries, "policies": pushed}

    def sync_libraries_to_opa(self) -> int:
        """Push helper packages that have no policy row of their own."""
        root = Path(settings.POLICY_DIR)
        pushed = 0
        for relative in settings.POLICY_LIBRARY_FILES:
            path = root / relative
            if not path.exists():
                logger.warning("policy_library_missing", path=str(path))
                continue
            try:
                self.opa.upsert_policy(
                    f"lib__{relative.replace('/', '__').removesuffix('.rego')}",
                    path.read_text(),
                )
                pushed += 1
            except PolicyEvaluationError as exc:
                logger.warning("opa_library_sync_failed", path=str(path), error=str(exc))
        return pushed

    def _safe_push(self, policy: Policy) -> bool:
        try:
            self.opa.upsert_policy(f"{policy.key}__{policy.version}", policy.rego_code or "")
            return True
        except PolicyEvaluationError as exc:
            logger.warning("opa_sync_failed", policy_key=policy.key, error=str(exc))
            return False

    # ---------- evaluation ----------

    def applicable_policies(
        self,
        jurisdiction_codes: list[str],
        risk_tiers: dict[str, str],
        policy_keys: list[str] | None,
    ) -> list[Policy]:
        if not jurisdiction_codes:
            return []
        stmt = select(Policy).where(
            Policy.is_deleted.is_(False),
            Policy.is_active.is_(True),
            Policy.jurisdiction_code.in_([c.upper() for c in jurisdiction_codes]),
        )
        if policy_keys:
            stmt = stmt.where(Policy.key.in_(policy_keys))
        policies = list(self.db.execute(stmt).scalars().all())

        selected: list[Policy] = []
        for policy in policies:
            tiers = policy.applies_to_risk_tiers or []
            if not tiers:
                selected.append(policy)
                continue
            tier = risk_tiers.get(policy.jurisdiction_code)
            if tier and tier in tiers:
                selected.append(policy)
        return selected

    def build_input(
        self, system: AISystem, jurisdiction_code: str, risk_tier: str
    ) -> dict[str, Any]:
        meta = system.system_metadata
        return {
            "system": {
                "id": str(system.id),
                "name": system.name,
                "status": str(system.status),
                "metadata_version": system.metadata_version,
                "extra": system.extra_metadata,
            },
            "metadata": {
                "purpose": meta.purpose if meta else None,
                "use_case": meta.use_case if meta else None,
                "industry": meta.industry if meta else None,
                "autonomy_level": str(meta.autonomy_level) if meta else None,
                "data_categories": meta.data_categories if meta else [],
                "deployment_regions": meta.deployment_regions if meta else [],
                "data_subject_regions": meta.data_subject_regions if meta else [],
                "data_residency": meta.data_residency if meta else [],
                "third_party_models": meta.third_party_models if meta else [],
                "affects_minors": bool(meta and meta.affects_minors),
                "uses_biometrics": bool(meta and meta.uses_biometrics),
                "uses_generative_ai": bool(meta and meta.uses_generative_ai),
                "is_safety_component": bool(meta and meta.is_safety_component),
                "makes_automated_decisions": bool(meta and meta.makes_automated_decisions),
                "human_oversight_documented": bool(meta and meta.human_oversight_documented),
                "conformity_assessment_done": bool(meta and meta.conformity_assessment_done),
                "technical_documentation_url": meta.technical_documentation_url if meta else None,
                "training_data_documented": bool(meta and meta.training_data_documented),
                "incident_response_plan": bool(meta and meta.incident_response_plan),
                "attributes": meta.attributes if meta else {},
            },
            "jurisdiction": jurisdiction_code,
            "risk_tier": risk_tier,
        }

    def evaluate_system(
        self,
        system: AISystem,
        *,
        jurisdiction_codes: list[str] | None = None,
        policy_keys: list[str] | None = None,
        reclassify: bool = True,
        actor: User | None = None,
    ) -> list[PolicyCheck]:
        if reclassify:
            _assessment, classifications = self.risk_service.classify(
                system, jurisdiction_codes=jurisdiction_codes, actor=actor
            )
            latest = {c.jurisdiction_code: c for c in classifications}
        else:
            latest = self.risk_service.latest_for_system(system.id)
            if jurisdiction_codes:
                wanted = {c.upper() for c in jurisdiction_codes}
                latest = {k: v for k, v in latest.items() if k in wanted}

        risk_tiers = {code: str(c.risk_tier) for code, c in latest.items()}
        codes = jurisdiction_codes or list(latest.keys())
        policies = self.applicable_policies(codes, risk_tiers, policy_keys)

        checks: list[PolicyCheck] = []
        now = datetime.now(UTC)
        for policy in policies:
            tier = risk_tiers.get(policy.jurisdiction_code, str(RiskTier.UNKNOWN))
            input_doc = self.build_input(system, policy.jurisdiction_code, tier)
            outcome = self._evaluate_one(policy, input_doc)
            check = PolicyCheck(
                ai_system_id=system.id,
                policy_id=policy.id,
                policy_key=policy.key,
                policy_version=policy.version,
                jurisdiction_code=policy.jurisdiction_code,
                # Severity of what was actually found, not of the policy that looked.
                severity=outcome.get("severity", policy.severity),
                result=outcome["result"],
                explanation=outcome["explanation"],
                violations=outcome["violations"],
                remediation=outcome["remediation"],
                evaluated_input=input_doc,
                raw_opa_response=outcome["raw"],
                engine=outcome["engine"],
                checked_at=now,
                checked_by_id=actor.id if actor else None,
            )
            self.db.add(check)
            checks.append(check)

        self.db.flush()
        record_audit(
            self.db,
            resource_type="ai_system",
            resource_id=system.id,
            action=AuditAction.POLICY_CHECK,
            actor=actor,
            new_values={
                "checks": len(checks),
                "failed": sum(1 for c in checks if c.result == PolicyResult.FAIL),
            },
        )
        logger.info(
            "policies_evaluated",
            ai_system_id=str(system.id),
            count=len(checks),
            failed=sum(1 for c in checks if c.result == PolicyResult.FAIL),
        )
        return checks

    def evaluate_batch(
        self,
        systems: list[AISystem],
        *,
        jurisdiction_codes: list[str] | None = None,
        policy_keys: list[str] | None = None,
        reclassify: bool = True,
        actor: User | None = None,
    ) -> dict[uuid.UUID, list[PolicyCheck]]:
        return {
            system.id: self.evaluate_system(
                system,
                jurisdiction_codes=jurisdiction_codes,
                policy_keys=policy_keys,
                reclassify=reclassify,
                actor=actor,
            )
            for system in systems
        }

    def _evaluate_one(self, policy: Policy, input_doc: dict[str, Any]) -> dict[str, Any]:
        try:
            raw = self.opa.evaluate(policy.opa_package, input_doc)
            return self._interpret_opa(policy, raw)
        except PolicyEvaluationError as exc:
            if policy.rules:
                logger.info("policy_fallback_rules", policy_key=policy.key)
                return self._evaluate_rules(policy, input_doc, str(exc))
            return {
                "result": PolicyResult.ERROR,
                "explanation": f"Policy could not be evaluated: {exc}",
                "violations": [],
                "remediation": [policy.remediation] if policy.remediation else [],
                "severity": policy.severity,
                "raw": {"error": str(exc)},
                "engine": "none",
            }

    def _interpret_opa(self, policy: Policy, raw: dict[str, Any]) -> dict[str, Any]:
        """Normalise an OPA package document into a structured check result.

        EU packages emit ``{allow, decision, in_scope, severity, rule_ids, violations}``
        where each violation carries ``rule_id``, ``article``, ``severity``, ``msg`` and
        ``remediation``. Older or third-party packages may expose only ``allow`` and
        ``violations``, or a bare boolean; all three shapes are accepted so a policy
        author is never forced into our schema.
        """
        result = raw.get("result") or {}
        if isinstance(result, bool):  # package exposes a bare boolean
            result = {"allow": result, "violations": []}

        violations = [
            self._normalise_violation(v, policy) for v in (result.get("violations") or [])
        ]
        allow = bool(result.get("allow", not violations))
        # A package that declares itself out of scope has nothing to say about this
        # system; that is a pass, not a silent success.
        in_scope = result.get("in_scope")

        remediation = [v["remediation"] for v in violations if v.get("remediation")]
        if policy.remediation and not remediation:
            remediation = [policy.remediation]

        effective = self._effective_severity(violations, policy)

        if allow and not violations:
            outcome = PolicyResult.PASS
            explanation = (
                f"{policy.name}: not applicable to this system."
                if in_scope is False
                else f"{policy.name}: all obligations satisfied."
            )
        elif effective in BLOCKING_SEVERITIES:
            outcome = PolicyResult.FAIL
            explanation = self._format_violations(policy, violations)
        else:
            outcome = PolicyResult.WARNING
            explanation = self._format_violations(policy, violations)

        return {
            "result": outcome,
            "explanation": explanation,
            "violations": violations,
            "remediation": [r for r in remediation if r],
            "severity": effective,
            "raw": raw,
            "engine": "opa",
        }

    @staticmethod
    def _normalise_violation(raw: Any, policy: Policy) -> dict[str, Any]:
        """Coerce one violation into the shape the API and PDF renderer expect."""
        if not isinstance(raw, dict):
            return {
                "rule_id": policy.key,
                "article": None,
                "severity": str(policy.severity),
                "msg": str(raw),
                "remediation": policy.remediation,
            }
        severity = str(raw.get("severity") or policy.severity).lower()
        if severity not in set(PolicySeverity):
            severity = str(policy.severity)
        return {
            **raw,
            "rule_id": raw.get("rule_id") or policy.key,
            "article": raw.get("article"),
            "severity": severity,
            "msg": raw.get("msg") or raw.get("message") or "Policy denied without a message.",
            "remediation": raw.get("remediation") or policy.remediation,
        }

    @staticmethod
    def _effective_severity(violations: list[dict[str, Any]], policy: Policy) -> PolicySeverity:
        """Worst severity actually raised, falling back to the policy's own severity.

        A policy registered as ``critical`` can still raise only a ``low`` finding, and
        the check should be reported at the severity of what was found rather than at
        the severity of the policy that looked.
        """
        found = [
            PolicySeverity(v["severity"])
            for v in violations
            if v.get("severity") in set(PolicySeverity)
        ]
        if not found:
            return policy.severity
        return max(found, key=lambda s: SEVERITY_ORDER[s])

    def _evaluate_rules(
        self, policy: Policy, input_doc: dict[str, Any], opa_error: str
    ) -> dict[str, Any]:
        """Declarative fallback: ``rules.require_true`` / ``rules.require_false`` on metadata."""
        metadata = input_doc.get("metadata", {})
        violations: list[dict[str, Any]] = []
        for field in policy.rules.get("require_true", []):
            if not bool(metadata.get(field)):
                violations.append(
                    self._fallback_violation(
                        policy, field, f"'{field}' must be true for this system."
                    )
                )
        for field in policy.rules.get("require_false", []):
            if bool(metadata.get(field)):
                violations.append(
                    self._fallback_violation(
                        policy, field, f"'{field}' must not be true for this system."
                    )
                )
        for field in policy.rules.get("require_present", []):
            if not metadata.get(field):
                violations.append(
                    self._fallback_violation(policy, field, f"'{field}' must be documented.")
                )

        if not violations:
            outcome = PolicyResult.PASS
            explanation = f"{policy.name}: all obligations satisfied (declarative fallback)."
        else:
            outcome = (
                PolicyResult.FAIL
                if policy.severity in BLOCKING_SEVERITIES
                else PolicyResult.WARNING
            )
            explanation = self._format_violations(policy, violations)

        return {
            "result": outcome,
            "explanation": explanation,
            "violations": violations,
            "remediation": [policy.remediation] if policy.remediation else [],
            "severity": policy.severity,
            "raw": {"fallback": True, "opa_error": opa_error},
            "engine": "rules",
        }

    @staticmethod
    def _fallback_violation(policy: Policy, field: str, message: str) -> dict[str, Any]:
        return {
            "rule_id": f"{policy.key}.{field}",
            "article": None,
            "severity": str(policy.severity),
            "msg": message,
            "field": field,
            "remediation": policy.remediation,
        }

    @staticmethod
    def _format_violations(policy: Policy, violations: list[Any]) -> str:
        if not violations:
            return f"{policy.name}: policy denied without an explicit violation message."
        lines = []
        for v in violations:
            if not isinstance(v, dict):
                lines.append(str(v))
                continue
            article = f"[{v['article']}] " if v.get("article") else ""
            lines.append(f"{article}{v.get('msg', '')}".strip())
        joined = " ".join(lines)
        return f"{policy.name} — {len(violations)} finding(s): {joined}"

    # ---------- reads ----------

    def latest_checks(self, system_id: uuid.UUID) -> list[PolicyCheck]:
        stmt = (
            select(PolicyCheck)
            .where(PolicyCheck.ai_system_id == system_id)
            .order_by(PolicyCheck.checked_at.desc())
        )
        seen: dict[tuple[str, str], PolicyCheck] = {}
        for check in self.db.execute(stmt).unique().scalars().all():
            seen.setdefault((check.jurisdiction_code, check.policy_key), check)
        return list(seen.values())

    def check_history(
        self, system_id: uuid.UUID, *, offset: int = 0, limit: int = 100
    ) -> tuple[list[PolicyCheck], int]:
        from sqlalchemy import func

        stmt = select(PolicyCheck).where(PolicyCheck.ai_system_id == system_id)
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(PolicyCheck.checked_at.desc()).offset(offset).limit(limit)
        return list(self.db.execute(stmt).unique().scalars().all()), total

    @staticmethod
    def summarize(checks: list[PolicyCheck]) -> dict[str, Any]:
        passed = sum(1 for c in checks if c.result == PolicyResult.PASS)
        failed = sum(1 for c in checks if c.result == PolicyResult.FAIL)
        warnings = sum(1 for c in checks if c.result == PolicyResult.WARNING)
        errors = sum(1 for c in checks if c.result == PolicyResult.ERROR)
        return {
            "total": len(checks),
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "errors": errors,
            "compliant": failed == 0 and errors == 0,
        }

"""Open Policy Agent REST client.

Uses the Data API (``POST /v1/data/<package path>``) for evaluation and the Policy API
(``PUT /v1/policies/<id>``) to push Rego stored in the database.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import PolicyEvaluationError
from app.core.logging import get_logger

logger = get_logger(__name__)


class OPAClient:
    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self.base_url = (base_url or settings.OPA_URL).rstrip("/")
        self.timeout = timeout or settings.OPA_TIMEOUT_SECONDS

    def health(self) -> bool:
        try:
            resp = httpx.get(f"{self.base_url}/health", timeout=self.timeout)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    def evaluate(self, package: str, input_doc: dict[str, Any]) -> dict[str, Any]:
        """Evaluate a package and return its ``result`` document.

        Raises PolicyEvaluationError so callers can fall back to declarative rules.
        """
        path = package.replace(".", "/")
        url = f"{self.base_url}/v1/data/{path}"
        try:
            resp = httpx.post(url, json={"input": input_doc}, timeout=self.timeout)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("opa_evaluate_failed", package=package, error=str(exc))
            raise PolicyEvaluationError(f"OPA evaluation failed for '{package}': {exc}") from exc

        body = resp.json()
        if "result" not in body:
            raise PolicyEvaluationError(
                f"OPA returned no result for '{package}'; is the package loaded?",
                details=body,
            )
        return body

    def upsert_policy(self, policy_id: str, rego_code: str) -> None:
        url = f"{self.base_url}/v1/policies/{policy_id}"
        try:
            resp = httpx.put(
                url,
                content=rego_code.encode(),
                headers={"Content-Type": "text/plain"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise PolicyEvaluationError(
                f"Failed to push policy '{policy_id}' to OPA: {exc}"
            ) from exc
        logger.info("opa_policy_upserted", policy_id=policy_id)

    def delete_policy(self, policy_id: str) -> None:
        try:
            httpx.delete(f"{self.base_url}/v1/policies/{policy_id}", timeout=self.timeout)
        except httpx.HTTPError as exc:  # pragma: no cover - best effort
            logger.warning("opa_policy_delete_failed", policy_id=policy_id, error=str(exc))


def get_opa_client() -> OPAClient:
    return OPAClient()

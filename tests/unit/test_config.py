"""Settings parsing.

These guard a failure mode that only shows up outside the test suite: pydantic-settings
JSON-decodes complex (list/dict) fields straight from the environment, so a plain
comma-separated `CORS_ORIGINS=http://localhost:3000` raised `SettingsError` at import
time and took down every container. Fields declared `NoDecode` parse in our validator
instead.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from app.core.config import Settings

COMPOSE_FILE = Path(__file__).resolve().parents[2] / "docker-compose.yml"
ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"

LIST_FIELDS = ("CORS_ORIGINS", "POLICY_LIBRARY_FILES")


def build(monkeypatch: pytest.MonkeyPatch, **env: str) -> Settings:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return Settings()


class TestListFieldParsing:
    @pytest.mark.parametrize("field", LIST_FIELDS)
    def test_single_bare_value(self, monkeypatch, field):
        """The exact form that broke `docker compose up`."""
        settings = build(monkeypatch, **{field: "one-value"})
        assert getattr(settings, field) == ["one-value"]

    @pytest.mark.parametrize("field", LIST_FIELDS)
    def test_comma_separated(self, monkeypatch, field):
        settings = build(monkeypatch, **{field: "a,b , c"})
        assert getattr(settings, field) == ["a", "b", "c"]

    @pytest.mark.parametrize("field", LIST_FIELDS)
    def test_json_array_still_works(self, monkeypatch, field):
        settings = build(monkeypatch, **{field: '["a", "b"]'})
        assert getattr(settings, field) == ["a", "b"]

    @pytest.mark.parametrize("field", LIST_FIELDS)
    def test_empty_value(self, monkeypatch, field):
        assert getattr(build(monkeypatch, **{field: ""}), field) == []

    def test_url_with_port_is_not_mistaken_for_json(self, monkeypatch):
        settings = build(monkeypatch, CORS_ORIGINS="http://localhost:3000,https://app.example.com")
        assert settings.CORS_ORIGINS == ["http://localhost:3000", "https://app.example.com"]

    def test_malformed_json_reports_clearly(self, monkeypatch):
        with pytest.raises(Exception, match="does not parse"):
            build(monkeypatch, CORS_ORIGINS='["unterminated')

    def test_defaults_hold_when_unset(self, monkeypatch):
        for field in LIST_FIELDS:
            monkeypatch.delenv(field, raising=False)
        settings = Settings()
        assert settings.CORS_ORIGINS == ["http://localhost:3000"]
        assert settings.POLICY_LIBRARY_FILES == ["eu/eu_ai_act_base.rego"]

    def test_every_list_field_is_covered_by_this_test(self):
        """Fail loudly if someone adds a list setting without adding it here."""
        source = (Path(__file__).resolve().parents[2] / "app/core/config.py").read_text()
        declared = set(
            re.findall(r"^\s+([A-Z_]+):\s*(?:Annotated\[)?(?:list|dict)\[", source, re.M)
        )
        assert declared == set(LIST_FIELDS), (
            f"Complex settings without parse coverage: {declared - set(LIST_FIELDS)}. "
            "Annotate them with NoDecode and add them to LIST_FIELDS."
        )


class TestDeploymentEnvironments:
    """The settings each shipped environment actually provides must construct."""

    def _compose_env(self) -> dict[str, str]:
        compose = yaml.safe_load(COMPOSE_FILE.read_text())
        raw = compose["services"]["api"]["environment"]
        resolved: dict[str, str] = {}
        for key, value in raw.items():
            text = str(value)
            # Resolve ${VAR:-default} / ${VAR} the way Compose would with no .env present.
            match = re.fullmatch(r"\$\{([A-Z_]+)(?::-(.*))?\}", text)
            if match:
                text = match.group(2) or ""
            resolved[key] = text
        return resolved

    def test_docker_compose_environment_constructs_settings(self, monkeypatch):
        env = self._compose_env()
        assert "CORS_ORIGINS" in env, "compose no longer sets CORS_ORIGINS; update this test"
        settings = build(monkeypatch, **env)
        assert settings.CORS_ORIGINS == ["http://localhost:3000"]
        assert settings.POSTGRES_HOST == "postgres"
        assert settings.auth_enabled is True
        # An empty override must fall back rather than become a literal empty URI.
        assert settings.rate_limit_storage_uri.startswith("redis://")

    def test_env_example_constructs_settings(self, monkeypatch):
        env = {}
        for line in ENV_EXAMPLE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.split("#")[0].strip()
        settings = build(monkeypatch, **env)
        assert settings.CORS_ORIGINS == ["http://localhost:3000"]
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 30
        assert settings.AUTH_DISABLED is False

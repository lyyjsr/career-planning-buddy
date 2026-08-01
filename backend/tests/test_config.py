"""Settings validation and environment precedence tests."""

import pytest
from pydantic import ValidationError
from pytest import MonkeyPatch

from app.core.config import Settings


def test_settings_load_safe_defaults(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("BACKEND_PORT", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.app_env == "local"
    assert settings.backend_port == 8000
    assert settings.database_url == "postgresql+asyncpg://localhost:5432/career_buddy"
    assert settings.llm_provider == "mock"


def test_environment_overrides_settings(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("BACKEND_PORT", "9001")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://test_user:test_password@localhost:5432/test_db",
    )

    settings = Settings(_env_file=None)

    assert settings.app_env == "test"
    assert settings.backend_port == 9001
    assert settings.database_url.endswith("/test_db")


def test_synchronous_database_url_is_rejected() -> None:
    with pytest.raises(ValidationError, match=r"postgresql\+asyncpg"):
        Settings(_env_file=None, database_url="postgresql://localhost:5432/career_buddy")


def test_production_requires_explicit_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET is required"):
        Settings(_env_file=None, app_env="production", jwt_secret=None)


def test_openai_compatible_requires_complete_configuration() -> None:
    with pytest.raises(
        ValidationError,
        match="LLM_API_KEY, LLM_BASE_URL, LLM_MODEL",
    ):
        Settings(
            _env_file=None,
            llm_provider="openai_compatible",
            llm_api_key="",
            llm_base_url="",
            llm_model="",
        )


def test_openai_compatible_configuration_is_validated_without_exposing_key() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="openai_compatible",
        llm_api_key="unit-test-secret",
        llm_base_url="https://llm.example.test/v1",
        llm_model="career-model",
    )

    assert settings.llm_provider == "openai_compatible"
    assert settings.llm_api_key is not None
    assert settings.llm_api_key.get_secret_value() == "unit-test-secret"
    assert "unit-test-secret" not in repr(settings)


def test_embedding_dimension_must_match_pgvector_migration() -> None:
    with pytest.raises(ValidationError, match="EMBEDDING_DIM must be 1024"):
        Settings(_env_file=None, embedding_dim=768)

"""C6 — env-driven CORS origin resolution."""
import pytest

from core import config as core_config
from core.cors import CorsConfigurationError, resolve_cors_origins


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    """Every test sets ENVIRONMENT/CORS_ALLOWED_ORIGINS explicitly —
    this just guarantees no leakage from the real process env."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    yield


def test_development_default_is_localhost_3000(monkeypatch):
    monkeypatch.setattr(core_config, "ENVIRONMENT", "development")
    monkeypatch.setattr(core_config, "CORS_ALLOWED_ORIGINS_RAW", "")
    assert resolve_cors_origins() == ["http://localhost:3000"]


def test_production_without_origins_fails_loudly(monkeypatch):
    monkeypatch.setattr(core_config, "ENVIRONMENT", "production")
    monkeypatch.setattr(core_config, "CORS_ALLOWED_ORIGINS_RAW", "")
    with pytest.raises(CorsConfigurationError):
        resolve_cors_origins()


def test_staging_without_origins_fails_loudly(monkeypatch):
    monkeypatch.setattr(core_config, "ENVIRONMENT", "staging")
    monkeypatch.setattr(core_config, "CORS_ALLOWED_ORIGINS_RAW", "")
    with pytest.raises(CorsConfigurationError):
        resolve_cors_origins()


def test_never_defaults_to_wildcard():
    """Whatever the resolution path, '*' must never come out of this
    function — that would be a real CORS vulnerability, not a convenience."""
    import inspect
    source = inspect.getsource(resolve_cors_origins)
    assert '"*"' not in source and "'*'" not in source


def test_explicit_origins_used_in_production(monkeypatch):
    monkeypatch.setattr(core_config, "ENVIRONMENT", "production")
    monkeypatch.setattr(core_config, "CORS_ALLOWED_ORIGINS_RAW", "https://app.notaflop.com,https://notaflop.com")
    assert resolve_cors_origins() == ["https://app.notaflop.com", "https://notaflop.com"]


def test_explicit_origins_trimmed_of_whitespace(monkeypatch):
    monkeypatch.setattr(core_config, "ENVIRONMENT", "production")
    monkeypatch.setattr(core_config, "CORS_ALLOWED_ORIGINS_RAW", " https://a.com , https://b.com ")
    assert resolve_cors_origins() == ["https://a.com", "https://b.com"]


def test_explicit_origins_override_development_default(monkeypatch):
    """Setting CORS_ALLOWED_ORIGINS always wins, even in development —
    it's never treated as a production-only override."""
    monkeypatch.setattr(core_config, "ENVIRONMENT", "development")
    monkeypatch.setattr(core_config, "CORS_ALLOWED_ORIGINS_RAW", "https://staging.notaflop.com")
    assert resolve_cors_origins() == ["https://staging.notaflop.com"]


def test_origins_set_to_only_commas_fails_loudly(monkeypatch):
    monkeypatch.setattr(core_config, "ENVIRONMENT", "production")
    monkeypatch.setattr(core_config, "CORS_ALLOWED_ORIGINS_RAW", " , , ")
    with pytest.raises(CorsConfigurationError):
        resolve_cors_origins()


def test_main_app_imports_cleanly_with_development_default():
    """main.py resolves CORS at import time — must not raise under the
    default (unset ENVIRONMENT -> 'development') test/dev configuration."""
    import main
    cors_middleware = [m for m in main.app.user_middleware if m.cls.__name__ == "CORSMiddleware"]
    assert len(cors_middleware) == 1

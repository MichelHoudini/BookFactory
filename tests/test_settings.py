import subprocess
import sys

import pytest

from bookfactory.config.settings import DEFAULT_OPENAI_MODEL, Settings, SettingsError


def test_loads_dotenv_once_when_settings_module_is_imported() -> None:
    script = """
from unittest.mock import patch

with patch("dotenv.load_dotenv") as loader:
    import bookfactory.config.settings
    loader.assert_called_once_with()
"""

    subprocess.run([sys.executable, "-c", script], check=True)


def test_loads_api_key_and_default_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    settings = Settings.from_environment()

    assert settings.openai_api_key == "test-key"
    assert settings.openai_model == DEFAULT_OPENAI_MODEL


def test_loads_model_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "configured-model")

    settings = Settings.from_environment()

    assert settings.openai_model == "configured-model"


def test_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(SettingsError, match="OPENAI_API_KEY is required"):
        Settings.from_environment()


def test_rejects_empty_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "  ")

    with pytest.raises(SettingsError, match="OPENAI_MODEL must not be empty"):
        Settings.from_environment()


def test_api_key_is_hidden_from_repr() -> None:
    settings = Settings(openai_api_key="secret-key", openai_model="model")

    assert "secret-key" not in repr(settings)

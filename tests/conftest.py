import pytest


@pytest.fixture(autouse=True)
def no_real_microphone(monkeypatch):
    """Tests never open the real microphone; voice tests inject fake listeners instead."""
    import cua.voice
    monkeypatch.setattr(cua.voice, "model_installed", lambda name: False)


@pytest.fixture(autouse=True)
def no_real_settings_file(monkeypatch, tmp_path):
    """Tests never read or write the person's real settings file (in %LOCALAPPDATA%, folder Klicky)."""
    import cua.config
    monkeypatch.setattr(cua.config, "settings_path", lambda: tmp_path / "Klicky" / "settings.json")

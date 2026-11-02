import pytest


@pytest.fixture(autouse=True)
def no_real_microphone(monkeypatch):
    """Tests never open the real microphone; voice tests inject fake listeners instead."""
    import cua.voice
    monkeypatch.setattr(cua.voice, "model_installed", lambda name: False)

"""The optional key file: only known names, comments ignored, the environment wins, a fresh file has no keys."""
from cua.keys import KEY_NAMES, TEMPLATE, ensure_file, load_keys


def test_fresh_file_has_every_name_and_no_keys(tmp_path):
    path = ensure_file(tmp_path / "Klicky" / "keys.env")
    assert path.read_text(encoding="utf-8") == TEMPLATE
    assert all(f"{name}=\n" in TEMPLATE for name in KEY_NAMES)
    env = {}
    assert load_keys(path, env) == [] and env == {}
    path.write_text("OPENROUTER_API_KEY=changed\n", encoding="utf-8")
    assert ensure_file(path).read_text(encoding="utf-8") == "OPENROUTER_API_KEY=changed\n"   # never overwritten


def test_only_filled_known_keys_load_and_the_environment_wins(tmp_path):
    path = tmp_path / "keys.env"
    path.write_text("\ufeff# OPENROUTER_API_KEY=commented-out\n"
                    "OPENROUTER_API_KEY = \"or-test\" \n"
                    "HF_TOKEN=\n"
                    "ANTHROPIC_API_KEY=from-file\n"
                    "PATH=C:\\evil\n"
                    "not a key line\n", encoding="utf-8")
    env = {"ANTHROPIC_API_KEY": "from-environment"}
    assert load_keys(path, env) == ["OPENROUTER_API_KEY"]
    assert env == {"ANTHROPIC_API_KEY": "from-environment", "OPENROUTER_API_KEY": "or-test"}


def test_a_missing_file_loads_nothing(tmp_path):
    assert load_keys(tmp_path / "nope.env", {}) == []

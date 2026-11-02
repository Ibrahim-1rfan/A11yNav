from dataclasses import replace
import pytest
from cua.config import Settings, UserError
from cua import profiles


def test_every_profile_is_complete_and_applies_valid_settings():
    for key, profile in profiles.PROFILES.items():
        assert profile.key == key and profile.answer_style and profile.fonts
        assert set(profile.states) == {"inactive", "processing", "action", "success", "error"}
        assert {"background", "text", "accent", "focus", "border"} <= set(profile.colors)
        settings = profiles.apply_to(Settings(), key)
        assert settings.profile == key and settings.font_px == profile.font_px


def test_profiles_differ_where_they_should():
    low, cog, motor = (profiles.get(k) for k in ("low_vision", "cognitive", "motor"))
    assert low.font_px >= 28 and low.focus_px >= 5 and low.speech and low.max_steps <= 5
    assert cog.one_step and cog.confirm_search and not cog.upper_labels and cog.line_height >= 150
    assert motor.button_px >= 56 and motor.settle_seconds > profiles.get("default").settle_seconds
    assert profiles.state_label(cog, "error") == "Needs help" and profiles.state_label(low, "error") == "NEEDS HELP"
    assert profiles.get("unknown").key == "default"


@pytest.mark.parametrize("patch", [{"profile": "expert"}, {"rag_app": "safari"}, {"text_model": 5}, {"embed_model": "x"*201}, {"font_px": 41}])
def test_new_settings_are_validated(patch):
    with pytest.raises(UserError):
        replace(Settings(), **patch).validate()


def test_large_low_vision_text_is_allowed():
    assert replace(Settings(), font_px=40).validate().font_px == 40


@pytest.mark.parametrize("text,expected", [("Ctrl+Alt+K", (0x3, ord("K"))), ("win+shift+f2", (0xC, 0x71)), ("Alt+1", (0x1, ord("1")))])
def test_hotkey_parsing(text, expected):
    from cua.config import parse_hotkey
    assert parse_hotkey(text) == expected


@pytest.mark.parametrize("text", ["K", "Shift+K", "Ctrl+Ctrl+K", "Ctrl+Alt+Enter", "Ctrl+Alt+F13", "Hyper+K", "Ctrl+Alt+é"])
def test_bad_hotkeys_are_rejected(text):
    with pytest.raises(UserError):
        replace(Settings(), hotkey=text).validate()
    assert replace(Settings(), hotkey="").validate().hotkey == ""

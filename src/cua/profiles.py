"""Access-need profiles. Each one shapes how Klicky looks, paces itself and words its guidance.

Profiles change presentation and answer style only. They never widen what the search agent may do.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Profile:
    key: str
    label: str
    description: str
    fonts: tuple[str, ...]
    font_px: int
    input_px: int
    colors: dict = field(default_factory=dict)
    states: dict = field(default_factory=dict)
    focus_px: int = 3
    button_px: int = 44
    spacing: int = 14
    letter_spacing: float = 0
    line_height: int = 120
    upper_labels: bool = True
    speech: bool = False
    one_step: bool = False
    confirm_search: bool = False
    enter_starts: bool = False
    max_steps: int = 8
    settle_seconds: float = 1.0
    answer_style: str = ""
    input_mode: str = "speak"  # how the hotkey opens: "type" for people who don't use their voice or hearing


DARK = {"background": "#0b202b", "surface": "#15323f", "text": "#f2f7f9", "muted": "#b8cbd4",
        "accent": "#68e3b5", "on_accent": "#0a202b", "focus": "#ffcf70", "border": "#54717e", "disabled": "#203743"}
DARK_STATES = {"inactive": "#a9bbc6", "processing": "#ffcf70", "action": "#57dbe0", "success": "#68e3b5", "error": "#ffadad"}
MONO = ("Intel One Mono", "IntelOne Mono", "Consolas", "DejaVu Sans Mono")

PROFILES = {
    "default": Profile(
        "default", "Standard", "Klicky's original large-text dark layout.",
        MONO, 18, 22, DARK, DARK_STATES,
        answer_style="Write clear numbered steps. Name the exact menu items and keyboard shortcuts."),
    "low_vision": Profile(
        "low_vision", "Low vision",
        "Very large text, yellow-on-black high contrast, thick focus outline, spoken answers and short guides.",
        ("Atkinson Hyperlegible", "Segoe UI", "Verdana", "Arial"), 30, 34,
        {"background": "#000000", "surface": "#000000", "text": "#ffffff", "muted": "#ffff66",
         "accent": "#ffe600", "on_accent": "#000000", "focus": "#00e5ff", "border": "#ffffff", "disabled": "#333333"},
        {"inactive": "#ffffff", "processing": "#ffe600", "action": "#00e5ff", "success": "#7dff7d", "error": "#ff8080"},
        focus_px=5, button_px=60, spacing=18, speech=True, max_steps=5,
        answer_style=("The reader has low vision. Use at most 5 short steps. Spell out every key name, for example "
                      "'press Control and plus together'. Prefer keyboard shortcuts and built-in zoom over finding small "
                      "icons. When an icon must be used, describe where it is, for example 'top right corner'.")),
    "cognitive": Profile(
        "cognitive", "Cognitive and learning",
        "Calm light colours, extra letter and line spacing, plain language and one step at a time.",
        ("OpenDyslexic", "Lexend", "Verdana", "Segoe UI"), 20, 24,
        {"background": "#fbf7ee", "surface": "#ffffff", "text": "#1d2b36", "muted": "#43525d",
         "accent": "#1f6f78", "on_accent": "#ffffff", "focus": "#c2410c", "border": "#8a9aa5", "disabled": "#e3ded3"},
        {"inactive": "#43525d", "processing": "#8a5a00", "action": "#1f6f78", "success": "#2f7d32", "error": "#b3261e"},
        focus_px=4, button_px=52, spacing=18, letter_spacing=1.5, line_height=160, upper_labels=False,
        one_step=True, confirm_search=True, max_steps=6,
        answer_style=("The reader prefers plain language. Use short sentences of at most 12 words. One action per step. "
                      "Avoid jargon; if a technical word is needed, explain it in a few words. Be encouraging and calm.")),
    "motor": Profile(
        "motor", "Motor and dexterity",
        "Big buttons with wide spacing, Enter to start, quick-pick examples and guides with the fewest key presses.",
        MONO, 20, 24, DARK, DARK_STATES,
        button_px=68, spacing=22, settle_seconds=1.5, enter_starts=True,
        answer_style=("The reader has limited hand movement. Choose the way with the fewest key presses and no precise "
                      "mouse pointing. Avoid shortcuts that need three keys at once when a menu or single key works. "
                      "Mention a keyboard-only option whenever one exists.")),
    "deaf": Profile(
        "deaf", "Deaf and hard of hearing",
        "Klicky opens ready to type, answers in text and captions without sound, and points at each step on screen.",
        MONO, 18, 22, DARK, DARK_STATES, input_mode="type",
        answer_style=("The reader is Deaf or hard of hearing. Never rely on sounds, beeps or spoken cues: say what "
                      "appears on screen instead, for example 'a red badge appears' rather than 'you'll hear a chime'.")),
}


def get(key):
    return PROFILES.get(key, PROFILES["default"])


def state_label(profile, state):
    word = {"inactive": "Ready", "processing": "Looking", "action": "Working", "success": "Done", "error": "Needs help"}[state]
    return word.upper() if profile.upper_labels else word


def apply_to(settings, key):
    """Return settings switched to a profile, adopting its suggested text size, speech and pacing."""
    from dataclasses import replace
    profile = get(key)
    return replace(settings, profile=profile.key, font_px=profile.font_px, speech=profile.speech,
                   settle_seconds=profile.settle_seconds, input_mode=profile.input_mode).validate()

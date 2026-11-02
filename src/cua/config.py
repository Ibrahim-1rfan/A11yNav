"""Validated, local-only configuration. No secrets or screenshots are persisted."""
from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
from urllib.parse import urlsplit


class UserError(Exception):
    """A safe, actionable message that may be displayed directly."""


@dataclass(frozen=True)
class Settings:
    endpoint: str = "http://127.0.0.1:1234/v1"
    model: str = "ui-tars-2b-sft"
    adapter: str = "ui_tars"
    browser: str = "default"
    engine: str = "bing"
    request_timeout: float = 45
    task_timeout: float = 240
    max_actions: int = 12
    max_retries: int = 2
    settle_seconds: float = 1.0
    max_image_edge: int = 1280
    max_tokens: int = 512
    temperature: float = 0.0
    font_px: int = 18
    speech: bool = False
    prompt_extra: str = ""
    profile: str = "default"
    text_model: str = ""
    embed_model: str = ""
    rag_app: str = "auto"
    hotkey: str = "Win+Shift+K"

    def validate(self):
        u = urlsplit(self.endpoint)
        if (u.scheme != "http" or u.hostname not in {"localhost", "127.0.0.1", "::1"}
                or u.username or u.password or u.query or u.fragment or u.path.rstrip('/') != '/v1'):
            raise UserError("Use a local server address such as http://127.0.0.1:1234/v1.")
        try:
            u.port
        except ValueError as exc:
            raise UserError("The server port must be a number between 1 and 65535.") from exc
        if not isinstance(self.model, str) or not self.model.strip() or len(self.model) > 200:
            raise UserError("Enter the model identifier shown in your local server.")
        for key in ("text_model", "embed_model"):
            value = getattr(self, key)
            if not isinstance(value, str) or len(value) > 200:
                raise UserError(f"Enter the {key.replace('_', ' ')} identifier shown in your local server, or leave it empty.")
        for key, choices in {"adapter": {"ui_tars", "json"}, "browser": {"default", "edge", "chrome", "firefox"}, "engine": {"bing", "google", "duckduckgo"},
                             "profile": {"default", "low_vision", "cognitive", "motor"}, "rag_app": {"auto", "edge", "chrome", "firefox"}}.items():
            if getattr(self, key) not in choices:
                raise UserError(f"Unsupported {key} setting.")
        for key, lo, hi, integer in [
            ("request_timeout", 1, 120, False), ("task_timeout", 10, 600, False),
            ("max_actions", 3, 30, True), ("max_retries", 0, 3, True),
            ("settle_seconds", .1, 5, False), ("max_image_edge", 640, 1920, True),
            ("max_tokens", 128, 2048, True), ("temperature", 0, 1, False), ("font_px", 16, 40, True),
        ]:
            value = getattr(self, key)
            if type(value) not in (int, float) or not math.isfinite(value) or not lo <= value <= hi or (integer and type(value) is not int):
                raise UserError(f"{key} must be between {lo} and {hi}.")
        if type(self.speech) is not bool or not isinstance(self.prompt_extra, str) or len(self.prompt_extra) > 2000:
            raise UserError("Invalid speech or prompt setting.")
        if not isinstance(self.hotkey, str):
            raise UserError("Invalid shortcut setting.")
        if self.hotkey:
            parse_hotkey(self.hotkey)
        return self


MODIFIERS = {"alt": 0x1, "ctrl": 0x2, "control": 0x2, "shift": 0x4, "win": 0x8}


def parse_hotkey(text: str):
    """Return Windows (modifiers, virtual key) for shortcuts like "Ctrl+Alt+K". Shift alone is not enough."""
    parts = [p.strip().lower() for p in text.split("+")]
    *mods, key = parts
    flags = 0
    for mod in mods:
        if mod not in MODIFIERS or flags & MODIFIERS[mod]:
            raise UserError('Write the shortcut like "Ctrl+Alt+K", using Ctrl, Alt, Shift or Win and one letter, digit or F-key.')
        flags |= MODIFIERS[mod]
    if not flags & 0xB:
        raise UserError("The shortcut needs Ctrl, Alt or Win so it does not interrupt normal typing.")
    if len(key) == 1 and (key.isascii() and key.isalnum()):
        return flags, ord(key.upper())
    if key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 12:
        return flags, 0x6F + int(key[1:])
    raise UserError('Write the shortcut like "Ctrl+Alt+K", using Ctrl, Alt, Shift or Win and one letter, digit or F-key.')


def settings_path() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Klicky" / "settings.json"


def load(path: Path | None = None) -> Settings:
    path = path or settings_path()
    try:
        return Settings(**json.loads(path.read_text(encoding="utf-8"))).validate() if path.exists() else Settings().validate()
    except (ValueError, TypeError, OSError) as exc:
        raise UserError("Settings could not be read. Open Settings and save valid values.") from exc


def save(settings: Settings, path: Path | None = None):
    settings.validate()
    path = path or settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    temporary.replace(path)

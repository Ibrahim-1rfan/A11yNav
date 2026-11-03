"""API keys for the optional hosted vision fallback, in keys.env in the project folder (next to launch.pyw).

keys.env is listed in .gitignore, so it is never committed. It holds lines like OPENROUTER_API_KEY=sk-or-... Only the
names below are read, and a key already set in the environment wins. Keys are never logged, shown or sent anywhere
except their own provider. A packaged Klicky reads keys.env next to Klicky.exe.
"""
import os
from pathlib import Path
import sys

KEY_NAMES = ("OPENROUTER_API_KEY", "HF_TOKEN", "ANTHROPIC_API_KEY")
TEMPLATE = """# Klicky API keys for finding buttons by looking (optional). Put a key after the = sign, no spaces or quotes needed.
# Only one is needed. Klicky uses the first one that is filled in: OpenRouter, then Hugging Face, then Anthropic.
# This file is in .gitignore: it stays on this PC and is never committed. Klicky reads it at each guided walkthrough.
OPENROUTER_API_KEY=
HF_TOKEN=
ANTHROPIC_API_KEY=
"""


def keys_path():
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
    return base / "keys.env"


def ensure_file(path=None):
    """Create the key file with empty entries if it isn't there yet. Returns its path."""
    path = path or keys_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(TEMPLATE, encoding="utf-8")
    return path


def old_keys_path():
    """Where keys.env lived before it moved into the project folder; still read if it holds a key."""
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Klicky" / "keys.env"


def load_keys(path=None, environ=os.environ):
    """Copy filled-in keys from the file into the environment. Returns the names that were loaded."""
    if path is None:  # the project's keys.env first, then the old location
        return load_keys(keys_path(), environ) + load_keys(old_keys_path(), environ)
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return []
    loaded = []
    for line in lines:
        name, sep, value = line.partition("=")
        name, value = name.strip(), value.strip().strip('"').strip("'")
        if sep and name in KEY_NAMES and value and not line.lstrip().startswith("#") and not environ.get(name):
            environ[name] = value
            loaded.append(name)
    return loaded

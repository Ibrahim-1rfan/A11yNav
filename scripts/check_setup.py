"""Checks that Klicky is installed and its keys work, without ever showing a key.

Usage: python scripts/check_setup.py  (or double-click scripts\\check_setup.bat)
Each line says OK, or what to fix. The key checks cost nothing: they ask OpenRouter for the key's spending limit and
Groq for its list of models.
"""
from pathlib import Path
import importlib
import platform
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

PACKAGES = ["PySide6", "pywinauto", "faster_whisper", "sounddevice", "edge_tts", "requests", "numpy", "PIL"]
problems = 0


def report(ok, text, fix=""):
    global problems
    problems += 0 if ok else 1
    print(("  OK    " if ok else "  FIX   ") + text + ("" if ok or not fix else f"\n        -> {fix}"))


def main():
    print("Klicky setup check\n")
    version = sys.version_info
    report(sys.platform == "win32", f"Windows ({platform.platform()})", "Klicky only runs on Windows 10 or 11.")
    report((3, 10) <= version[:2] <= (3, 13), f"Python {version.major}.{version.minor}.{version.micro}",
           "Install Python 3.13 from python.org, then run scripts\\setup.bat again.")
    for name in PACKAGES:
        try:
            importlib.import_module(name)
            report(True, f"package {name}")
        except Exception:
            report(False, f"package {name}", "Run scripts\\setup.bat again.")

    from cua.voice import model_installed
    report(model_installed("base.en"), "speech model base.en (live captions, and voice when Groq is down)",
           "Double-click scripts\\get_speech_model.bat once.")

    from cua.keys import keys_path, load_keys
    path = keys_path()
    report(path.exists(), f"keys file {path.name}", "Start Klicky once (it creates keys.env), or create it as SETUP.md shows.")
    loaded = set(load_keys())
    import os
    import requests
    from dotenv import load_dotenv

    load_dotenv("keys.env", override=True)

    if os.environ.get("OPENROUTER_API_KEY"):
        try:
            # print(f"Key starts with: {str(os.environ.get('OPENROUTER_API_KEY'))[:15]}")
            r = requests.get("https://openrouter.ai/api/v1/key", timeout=20,
                             headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"})
            # print(r.status_code, r.text)
            data = r.json().get("data", {}) if r.ok else {}
            left = data.get("limit_remaining")
            report(r.ok, "OPENROUTER_API_KEY works" + (f" (${left:.2f} of its limit left)" if isinstance(left, (int, float)) else ""),
                   "The key was refused: check it was pasted whole, or ask for a new one.")
        except requests.RequestException:
            report(False, "OPENROUTER_API_KEY could not be checked", "Check the internet connection.")
    else:
        report(False, "OPENROUTER_API_KEY is empty", "Paste the key you were given into keys.env (see SETUP.md, step 5).")
    if os.environ.get("GROQ_API_KEY"):
        try:
            r = requests.get("https://api.groq.com/openai/v1/models", timeout=20,
                             headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"})
            report(r.ok, "GROQ_API_KEY works", "The key was refused: make a new one at console.groq.com/keys.")
        except requests.RequestException:
            report(False, "GROQ_API_KEY could not be checked", "Check the internet connection.")
    else:
        report(False, "GROQ_API_KEY is empty", "Make your own free key at console.groq.com/keys and paste it into keys.env.")

    import subprocess
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "keys.env"], capture_output=True,
                             cwd=Path(__file__).resolve().parents[1]).returncode == 0
    report(not tracked, "keys.env is not tracked by git", "Run: git rm --cached keys.env  (and tell the project lead).")
    print("\nAll good. Start Klicky with scripts\\run.bat." if not problems else f"\n{problems} thing(s) to fix, see above.")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Try the vision fallback once: find a named link or button in a browser window by looking at a screenshot.

The key comes from keys.env in the project folder (or the environment); this script never asks for it.
A screenshot of the chosen browser window is sent to that provider, so use a page with nothing private on it.
It saves the screenshot with the found spot circled to %LOCALAPPDATA%\\Klicky\\vision-test.png.

Usage: python scripts/try_vision.py "<part of the window title>" "<target>"
Example: python scripts/try_vision.py "Google" "link: Gmail"
Targets: "link: <name>", "button: <name>" or "control: <name>".
"""
from pathlib import Path
import ctypes
from ctypes import wintypes
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cua.browser import enable_dpi_awareness, window_title
from cua.config import Settings, settings_path
from cua import vision


def find_window(part):
    user32, found = ctypes.windll.user32, []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        title = window_title(hwnd)
        if user32.IsWindowVisible(hwnd) and part.lower() in title.lower() and title.endswith(("Google Chrome", "Microsoft Edge", "Microsoft​ Edge")):
            found.append(hwnd)
        return True
    user32.EnumWindows(visit, 0)
    return found[0] if found else None


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 1
    enable_dpi_awareness()
    from cua.keys import keys_path, load_keys
    load_keys()
    settings = Settings()
    name = vision.backend(settings)
    if name in (None, "local"):
        print(f"No vision key is set. Put your key after OPENROUTER_API_KEY= in {keys_path()} and save it.")
        return 1
    hwnd = find_window(sys.argv[1])
    if not hwnd:
        print(f'No Chrome or Edge window with "{sys.argv[1]}" in its title.')
        return 1
    print(f"Window: {window_title(hwnd)}\nAsking {name} for {sys.argv[2]} ...", flush=True)
    shots = []
    def grab(hwnd, max_edge, factor):
        shot = vision.capture(hwnd, max_edge, factor)
        shots.append(shot)
        return shot
    start = time.monotonic()
    seen = vision.see(hwnd, sys.argv[2], "", f"Select {sys.argv[2].partition(':')[2].strip()}.", settings, grab=grab)
    print(f"Answer in {time.monotonic() - start:.1f} s: " + (f"desktop rectangle {seen.rect}" if seen else "not found (or the request failed)"))
    if shots:
        from io import BytesIO
        from PIL import Image, ImageDraw
        png, width, height, (left, top, right, bottom) = shots[0]
        image = Image.open(BytesIO(png)).convert("RGB")
        if seen:
            sx, sy = width / (right - left), height / (bottom - top)
            l, t, r, b = seen.rect
            ImageDraw.Draw(image).rectangle(((l - left) * sx, (t - top) * sy, (r - left) * sx, (b - top) * sy), outline=(0, 160, 120), width=4)
        out = settings_path().parent / "vision-test.png"
        image.save(out)
        print(f"Saved: {out}")
    return 0 if seen else 2


if __name__ == "__main__":
    sys.exit(main())

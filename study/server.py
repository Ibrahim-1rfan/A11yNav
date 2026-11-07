"""Serves Klicky Mart on this PC only (127.0.0.1) and saves study results to study/results/.

POST /api/task  one task's result: appended as a row to summary.csv (the click log goes in the round file)
POST /api/round the whole round (tasks, NASA-TLX, SUS): saved as <participant>_<version>_<klicky>_<time>.json
Usage: python study/server.py [--port 8765] [--no-browser]
"""
import argparse
import csv
import json
import re
import threading
import time
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = HERE / "klicky-mart"
RESULTS = HERE / "results"
MAX_BODY = 1_000_000
FIELDS = ("saved", "participant", "group", "version", "klicky", "task", "text", "success", "skipped", "seconds",
          "first_click_seconds", "clicks", "wrong_actions", "paas")
CODE = re.compile(r"^[A-Z0-9_-]{1,12}$")
CHOICES = {"group": {"deaf", "speak", "comparison"}, "version": {"A", "B"}, "klicky": {"with", "without"}}
_lock = threading.Lock()


def check(data):
    """The round's identity, checked: it names the result file, so nothing else may get into the path."""
    if not isinstance(data, dict) or not CODE.match(str(data.get("participant", ""))):
        raise ValueError("bad participant code")
    for key, allowed in CHOICES.items():
        if data.get(key) not in allowed:
            raise ValueError(f"bad {key}")
    return data


def save_task(data, results=RESULTS):
    check(data)
    results.mkdir(parents=True, exist_ok=True)
    path = results / "summary.csv"
    row = {key: data.get(key) for key in FIELDS}
    row["saved"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with _lock:
        new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            if new:
                writer.writeheader()
            writer.writerow(row)
    return path


def save_round(data, results=RESULTS):
    check(data)
    results.mkdir(parents=True, exist_ok=True)
    path = results / f"{data['participant']}_{data['version']}_{data['klicky']}_{time.strftime('%Y%m%d-%H%M%S')}.json"
    with _lock:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


class Handler(SimpleHTTPRequestHandler):
    results = RESULTS

    def do_POST(self):
        saver = {"/api/task": save_task, "/api/round": save_round}.get(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        if not saver or not 0 < length <= MAX_BODY:
            self.send_error(404 if not saver else 413)
            return
        try:
            saver(json.loads(self.rfile.read(length)), self.results)
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_error(400, str(exc))
            return
        body = b'{"saved": true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")  # a fresh copy each round
        super().end_headers()

    def log_message(self, fmt, *args):
        pass  # keep the console quiet during sessions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(Handler, directory=str(APP)))
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Klicky Mart is running at {url}  (results go to {RESULTS})  Press Ctrl+C to stop.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

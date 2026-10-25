"""Test local vision and action formatting on a synthetic image, without desktop input."""
import argparse
from dataclasses import replace
from pathlib import Path
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from PIL import Image, ImageDraw
from cua.config import Settings, UserError
from cua.models import LocalModel
from cua.perception import preprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--adapter", choices=["json", "ui_tars"], default="json")
    args = parser.parse_args()
    settings = replace(Settings(), model=args.model, adapter=args.adapter,
                       request_timeout=120, max_tokens=256, max_image_edge=960)
    model = LocalModel(settings)
    model.health(threading.Event())
    image = Image.new("RGB", (640, 360), "white")
    ImageDraw.Draw(image).rectangle((180, 80, 460, 280), fill="red")
    frame = preprocess(image, (0, 0, 640, 360), 960)
    start = time.monotonic()
    try:
        action = model.propose(frame, "This is an image test, not a browser task. If the large rectangle is red, return wait. If it is blue, return call_user (request_user_help in JSON). Do not finish a task.", threading.Event(), 120)
        print(f"Vision response: {action.kind}; elapsed: {time.monotonic()-start:.1f}s", flush=True)
        return 0 if action.kind == "wait" else 1
    except UserError as exc:
        print(f"Vision test failed after {time.monotonic()-start:.1f}s: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

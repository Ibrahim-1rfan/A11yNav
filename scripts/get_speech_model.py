"""Explicit one-time download of the local Whisper speech model (base.en is about 145 MB).

Klicky never downloads models by itself. Usage: python scripts/get_speech_model.py [tiny.en|base.en|small.en]
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cua.voice import MODELS, model_dir, model_installed


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "base.en"
    if name not in MODELS:
        print(f"Choose one of: {', '.join(MODELS)}")
        return 1
    if model_installed(name):
        print(f"The {name} speech model is already installed at {model_dir(name)}")
        return 0
    from huggingface_hub import snapshot_download
    print(f"Downloading {MODELS[name]} to {model_dir(name)} ...", flush=True)
    snapshot_download(MODELS[name], local_dir=str(model_dir(name)),
                      allow_patterns=["config.json", "model.bin", "tokenizer.json", "vocabulary.*", "preprocessor_config.json"])
    print("Done. Voice input is ready." if model_installed(name) else "The download did not complete. Please try again.")
    return 0 if model_installed(name) else 1


if __name__ == "__main__":
    raise SystemExit(main())

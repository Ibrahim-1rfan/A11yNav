"""Microphone check for voice questions: is the problem the microphone, where listening stops, or the speech model?

Records 8 seconds while you say one sentence, then shows how loud your voice and the room were, where Klicky would
have stopped listening, and what each speech model heard. The recording stays in memory and is never saved; it is
sent only to Groq (with GROQ_API_KEY in keys.env), like a normal voice question.
Usage: python scripts/mic_test.py  (or double-click scripts\\mic_test.bat)
"""
from pathlib import Path
import sys
import threading
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
import sounddevice as sd
from cua.keys import load_keys
from cua import voice

SECONDS = 8
SENTENCE = "Hey Klicky, which assignment is due next in Human Computer Interaction?"


def groq(audio, model, prompt):
    import os
    import requests
    data = {"model": model, "language": "en", "temperature": "0", "response_format": "json"}
    if prompt:
        data["prompt"] = voice.VOCABULARY
    response = requests.post(voice.GROQ_URL, headers={"Authorization": f"Bearer {os.environ.get('GROQ_API_KEY', '')}"},
                             files={"file": ("question.wav", voice.wav_bytes(audio), "audio/wav")}, data=data,
                             timeout=20, allow_redirects=False)
    response.raise_for_status()
    return " ".join(str(response.json().get("text", "")).split())


def main():
    load_keys()
    print(f"Microphone: {sd.query_devices(kind='input')['name']}")
    print(f'\nWhen you see "Speak now", say this sentence in your normal voice:\n\n    {SENTENCE}\n')
    input("Press Enter when you are ready...")
    print("Speak now (8 seconds)...", flush=True)
    audio = sd.rec(int(SECONDS * voice.RATE), samplerate=voice.RATE, channels=1, dtype="float32")
    sd.wait()
    audio = audio[:, 0]
    print("Done.\n")

    # How loud: per 50 ms chunk, the same readings Klicky's listening uses.
    levels = [float(np.sqrt(np.mean(c * c))) for c in np.array_split(audio, len(audio) // voice.CHUNK)]
    room = float(np.median(levels[:3]))
    voice_level = float(np.percentile(levels, 90))
    peak = float(np.max(np.abs(audio)))
    print(f"Room noise level:  {room:.4f}")
    print(f"Your voice level:  {voice_level:.4f}   (peak {peak:.2f}; 1.00 means clipped)")
    if voice_level < 0.02:
        print("  -> Your voice is very quiet. Move closer, or raise the microphone level in Windows Sound settings.")
    if peak >= 0.99:
        print("  -> The sound is clipping (too loud). Lower the microphone level a little.")
    if room > 0.01:
        print("  -> The room is noisy (fan, AC, people). Klicky may stop listening early or hear noise as words.")

    # Where Klicky's listening would have stopped.
    ep = voice.Endpointer()
    stop = None
    for i, level in enumerate(levels):
        if ep.feed(level):
            stop = (i + 1) * voice.CHUNK_MS / 1000
            break
    spoken = [i for i, level in enumerate(levels) if level >= ep.threshold]
    last = (spoken[-1] + 1) * voice.CHUNK_MS / 1000 if spoken else 0
    print(f"\nYou stopped speaking at about {last:.1f} s; Klicky would stop listening at "
          f"{stop:.1f} s." if stop else f"\nYou stopped speaking at about {last:.1f} s; Klicky would still be listening at 8 s.")
    if stop and stop < last:
        print("  -> Klicky would have CUT YOU OFF before you finished.")
    clip = audio[: int((stop or SECONDS) * voice.RATE)]

    print("\nWhat each speech model heard (from what Klicky would have recorded):")
    tests = [("Groq Whisper large v3 turbo (now)", lambda a: groq(a, "whisper-large-v3-turbo", True)),
             ("Groq turbo, without Klicky's word list", lambda a: groq(a, "whisper-large-v3-turbo", False)),
             ("Groq Whisper large v3 (full)", lambda a: groq(a, "whisper-large-v3", True)),
             ("Groq large v3, without the word list", lambda a: groq(a, "whisper-large-v3", False)),
             ("On this PC (base.en)", lambda a: voice.Transcriber("base.en").transcribe(a, threading.Event()))]
    for name, run in tests:
        started = time.perf_counter()
        try:
            text = run(clip)
        except Exception as exc:
            text = f"(failed: {type(exc).__name__})"
        print(f"  {name:40} {time.perf_counter() - started:4.1f} s  {text}")
    print(f"\nYou were asked to say:                         {SENTENCE}")


if __name__ == "__main__":
    main()

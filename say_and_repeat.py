#!/usr/bin/env python3
"""
Say & Repeat (minimal): Microphone -> SpeechRecognition -> pyttsx3 TTS

What it does:
- Continuously listens for short phrases from your default microphone.
- Transcribes speech to text with SpeechRecognition (Google Web Speech API).
- Immediately reads the text back using offline TTS (pyttsx3).
- Exit by pressing Ctrl+C or saying one of the stop words (configurable).

Why this version?
- Trimmed to the essentials (no wake word, no LLM, no extra tools).
- Uses a single loop with automatic phrase segmentation (pause_threshold).
- Keeps the TTS engine warm to reduce latency.
- Optional: works offline if PocketSphinx is installed and you pass --sphinx.

Install:
    pip install SpeechRecognition pyttsx3
    # Microphone backend (PyAudio). On Windows with uv:
    #   uv pip install pyaudio
    #   (If that fails, install a prebuilt wheel from Gohlke, then: uv pip install <wheel>)
    # macOS:
    #   brew install portaudio && pip install pyaudio
    # Linux (Debian/Ubuntu):
    #   sudo apt-get update && sudo apt-get install -y portaudio19-dev python3-pyaudio && pip install pyaudio
    # Optional offline STT:
    #   pip install pocketsphinx

Run:
    python say_and_repeat.py
    python say_and_repeat.py --lang ar-LB            # Arabic (Lebanon)
    python say_and_repeat.py --rate 180 --volume 1.0 # TTS tuning
    python say_and_repeat.py --mic 1                 # choose mic index
    python say_and_repeat.py --sphinx                # force offline STT (if installed)

Notes:
- Google recognizer requires internet and has usage limits.
- For better chunking, tweak --pause and --limit.
"""

import argparse
import sys
import time

import speech_recognition as sr

try:
    import pyttsx3
except Exception as e:
    print("pyttsx3 is required for TTS. Install with: pip install pyttsx3", file=sys.stderr)
    raise


def init_tts(lang: str, rate: int, volume: float):
    engine = pyttsx3.init()
    engine.setProperty("rate", rate)
    engine.setProperty("volume", max(0.0, min(1.0, volume)))
    # Try to pick a voice matching language (best-effort)
    try:
        voices = engine.getProperty("voices") or []
        lang_norm = (lang or "en-US").replace("_", "-").lower()
        short = lang_norm.split("-")[0]
        chosen = None
        for v in voices:
            langs = []
            try:
                langs = [l.decode("utf-8") if isinstance(l, (bytes, bytearray)) else str(l) for l in getattr(v, "languages", [])]
            except Exception:
                pass
            joined = " ".join(langs).lower()
            if lang_norm in joined or short in joined:
                chosen = v.id
                break
        if not chosen:
            for v in voices:
                name_id = f"{getattr(v, 'name', '')} {getattr(v, 'id', '')}".lower()
                if lang_norm in name_id or short in name_id:
                    chosen = v.id
                    break
        if chosen:
            engine.setProperty("voice", chosen)
    except Exception:
        # Ignore voice selection errors; use default
        pass
    return engine


def speak(engine, text: str):
    """Speak text using TTS engine with fresh instance for reliability."""
    try:
        # Create a fresh engine instance for each speak call to avoid state issues
        fresh_engine = pyttsx3.init()
        # Copy settings from the original engine
        fresh_engine.setProperty("rate", engine.getProperty("rate"))
        fresh_engine.setProperty("volume", engine.getProperty("volume"))
        
        # Try to copy voice setting if available
        try:
            current_voice = engine.getProperty("voice")
            if current_voice:
                fresh_engine.setProperty("voice", current_voice)
        except Exception:
            pass  # Use default voice if setting fails
        
        fresh_engine.say(text)
        fresh_engine.runAndWait()
        time.sleep(0.1)  # Brief pause for stability
    except Exception as e:
        print(f"TTS Error: {e}")
        # Fallback: try with the original engine
        try:
            engine.say(text)
            engine.runAndWait()
        except Exception as fallback_error:
            print(f"TTS Fallback Error: {fallback_error}")


def transcribe(recognizer: sr.Recognizer, audio: sr.AudioData, language: str, force_sphinx: bool = False) -> str:
    # Try Google first (unless forcing Sphinx), then fallback to Sphinx if available.
    if not force_sphinx:
        try:
            return recognizer.recognize_google(audio, language=language)
        except sr.RequestError:
            # no internet/quota; try Sphinx
            pass
        except sr.UnknownValueError:
            raise
    try:
        import pocketsphinx  # noqa: F401
        return recognizer.recognize_sphinx(audio, language=language)
    except Exception:
        # If Sphinx not available, propagate a request error to be handled by caller.
        raise sr.RequestError("No online service and PocketSphinx not installed")


def main():
    ap = argparse.ArgumentParser(description="Say & Repeat: listen -> transcribe -> speak")
    ap.add_argument("--mic", type=int, default=None, help="Microphone device index (use --list-mics to inspect)")
    ap.add_argument("--list-mics", action="store_true", help="List microphone device names and exit")
    ap.add_argument("--lang", default="en-US", help="Language code for STT & TTS (e.g., en-US, ar-LB, fr-FR)")
    ap.add_argument("--rate", type=int, default=170, help="TTS speaking rate (default 170)")
    ap.add_argument("--volume", type=float, default=1.0, help="TTS volume 0.0–1.0 (default 1.0)")
    ap.add_argument("--pause", type=float, default=0.6, help="Seconds of silence to consider phrase complete (pause_threshold)")
    ap.add_argument("--limit", type=float, default=12.0, help="Max seconds to listen per phrase (phrase_time_limit)")
    ap.add_argument("--timeout", type=float, default=None, help="Max seconds to wait for speech start (None = no timeout)")
    ap.add_argument("--sphinx", action="store_true", help="Force offline STT with PocketSphinx (if installed)")
    ap.add_argument("--stop-words", nargs="*", default=["stop", "quit", "exit"], help="Words that end the program when spoken")

    args = ap.parse_args()

    if args.list_mics:
        print("Available microphones:")
        for i, name in enumerate(sr.Microphone.list_microphone_names() or []):
            print(f"[{i}] {name}")
        return 0

    # Prepare TTS
    tts = init_tts(args.lang, args.rate, args.volume)

    # Prepare recognizer & mic
    r = sr.Recognizer()
    # Make phrase segmentation snappier - set to 2 seconds for silence detection
    r.pause_threshold = 2.0  # Stop transcribing after 2 seconds of silence
    r.dynamic_energy_threshold = True
    # r.energy_threshold can be set manually if needed (e.g., in very noisy rooms)

    try:
        mic = sr.Microphone(device_index=args.mic)
    except OSError as e:
        print("Microphone not found. Use --list-mics to pick a valid device.", file=sys.stderr)
        return 2

    print("=" * 60)
    print("Say & Repeat — SpeechRecognition + pyttsx3")
    print("Speak a phrase; I'll repeat it. Starts when voice detected, stops after 2s silence.")
    print("Ctrl+C to quit.")
    print(f"Language={args.lang}  Silence timeout=2.0s  Limit={args.limit}s  Mic={'default' if args.mic is None else args.mic}")
    print("=" * 60)

    # Calibrate a bit for ambient noise
    with mic as source:
        print("Calibrating for ambient noise (1s)...")
        r.adjust_for_ambient_noise(source, duration=1.0)

    try:
        while True:
            with mic as source:
                print("\nWaiting for voice...")
                # Wait for voice activity to start transcribing
                try:
                    # Listen for voice activity without timeout, will automatically start when voice detected
                    # and stop after 2 seconds of silence (pause_threshold)
                    audio = r.listen(source, timeout=None, phrase_time_limit=args.limit)
                    print("Voice detected, transcribing...")
                except sr.WaitTimeoutError:
                    # This shouldn't happen with timeout=None, but handle it just in case
                    print("...no speech detected, continuing.")
                    continue

            # Transcribe
            try:
                text = transcribe(r, audio, args.lang, force_sphinx=args.sphinx).strip()
            except sr.UnknownValueError:
                print("I couldn't understand that.")
                speak(tts, "Sorry, I couldn't understand that.")
                continue
            except sr.RequestError as e:
                print(f"Transcription error: {e}")
                speak(tts, "I couldn't transcribe that. Check your internet or install Pocket Sphinx.")
                continue

            if not text:
                print("(empty)")
                continue

            print(f"You said: {text}")
            # Exit if a stop word is spoken exactly
            if text.lower() in [w.lower() for w in args.stop_words]:
                speak(tts, "Goodbye.")
                break

            # Speak back
            speak(tts, text)

    except KeyboardInterrupt:
        print("\nExiting... Goodbye.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

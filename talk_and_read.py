#!/usr/bin/env python3
"""
Talk & Read: Microphone -> SpeechRecognition -> TTS

Features
- Press Enter to record, or type 'q' + Enter to quit.
- Uses SpeechRecognition (Google Web Speech API by default) to transcribe.
- Speaks the recognized text aloud using pyttsx3 (offline TTS).
- Optional: list and choose microphone device, change language, rate, and volume.
- Optional: offline fallback with PocketSphinx if installed (pass --sphinx).

Install (choose the commands right for your OS):
    pip install SpeechRecognition pyttsx3
    # Microphone backend (PyAudio) — pick your platform:
    # Windows:
    #   pip install pipwin && pipwin install pyaudio
    # macOS:
    #   brew install portaudio && pip install pyaudio
    # Linux (Debian/Ubuntu):
    #   sudo apt-get update && sudo apt-get install -y portaudio19-dev python3-pyaudio && pip install pyaudio
    #
    # Optional offline STT:
    #   pip install pocketsphinx

Run:
    python talk_and_read.py               # default: Google STT, system default mic, en-US
    python talk_and_read.py --list-mics   # list microphones and exit
    python talk_and_read.py --mic 1       # pick a specific mic index
    python talk_and_read.py --lang ar-LB  # Arabic (Lebanon) example
    python talk_and_read.py --sphinx      # force offline STT with PocketSphinx (if installed)

Notes:
- Google recognizer requires internet and is usage-limited without an API key.
- If Google STT fails (no internet / quota), the script will try PocketSphinx automatically if available.
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

# ----------- Utilities -----------

def list_mics() -> None:
    print("Available microphones:")
    for idx, name in enumerate(sr.Microphone.list_microphone_names() or []):
        print(f"  [{idx}] {name}")


def choose_tts_voice(engine, lang: str) -> None:
    """
    Try to pick a voice matching the language hint (e.g., 'en-US', 'ar-LB', 'fr-FR').
    Falls back to whatever default voice is available.
    """
    lang = (lang or "en-US").replace("_", "-").lower()
    short = lang.split("-")[0]

    try:
        voices = engine.getProperty("voices") or []
    except Exception:
        voices = []

    # Prefer exact/contains match on languages, then on voice name/id.
    for v in voices:
        langs = []
        try:
            langs = [l.decode("utf-8") if isinstance(l, (bytes, bytearray)) else str(l) for l in getattr(v, "languages", [])]
        except Exception:
            pass

        joined = " ".join(langs).lower()
        if lang in joined or short in joined:
            engine.setProperty("voice", v.id)
            return

    for v in voices:
        name_id = f"{getattr(v, 'name', '')} {getattr(v, 'id', '')}".lower()
        if lang in name_id or short in name_id:
            engine.setProperty("voice", v.id)
            return
    # No change if nothing matched.


def init_tts(lang: str, rate: int = 170, volume: float = 1.0):
    engine = pyttsx3.init()
    engine.setProperty("rate", rate)
    engine.setProperty("volume", max(0.0, min(1.0, volume)))
    choose_tts_voice(engine, lang)
    return engine


def speak(engine, text: str) -> None:
    engine.say(text)
    engine.runAndWait()


def recognize_google_with_fallback(recognizer: sr.Recognizer, audio: sr.AudioData, language: str) -> str:
    """
    Try Google STT first; if it fails (RequestError), try PocketSphinx if available.
    """
    try:
        return recognizer.recognize_google(audio, language=language)
    except sr.RequestError as e:
        # Possibly offline or quota. Try Sphinx if present.
        try:
            import pocketsphinx  # noqa: F401
            return recognizer.recognize_sphinx(audio, language=language)
        except Exception as sphinx_err:
            raise RuntimeError(f"Online STT failed and PocketSphinx is unavailable: {e}") from sphinx_err


def recognize_sphinx_only(recognizer: sr.Recognizer, audio: sr.AudioData, language: str) -> str:
    import pocketsphinx  # noqa: F401
    return recognizer.recognize_sphinx(audio, language=language)


# ----------- Main -----------

def main():
    parser = argparse.ArgumentParser(description="Talk & Read (SpeechRecognition + TTS)")
    parser.add_argument("--list-mics", action="store_true", help="List microphone devices and exit")
    parser.add_argument("--mic", type=int, default=None, help="Microphone device index (see --list-mics)")
    parser.add_argument("--lang", default="en-US", help="Recognition & TTS language hint (e.g., en-US, ar-LB, fr-FR)")
    parser.add_argument("--rate", type=int, default=170, help="TTS speech rate (default 170)")
    parser.add_argument("--volume", type=float, default=1.0, help="TTS volume 0.0–1.0 (default 1.0)")
    parser.add_argument("--timeout", type=float, default=5.0, help="Seconds to wait for speech start (default 5)")
    parser.add_argument("--limit", type=float, default=15.0, help="Max seconds per phrase (default 15)")
    parser.add_argument("--sphinx", action="store_true", help="Use offline PocketSphinx only (requires pocketsphinx)")

    args = parser.parse_args()

    if args.list_mics:
        list_mics()
        return 0

    # Init TTS
    engine = init_tts(args.lang, rate=args.rate, volume=args.volume)

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True  # better in noisy rooms

    # Create / select microphone
    try:
        mic = sr.Microphone(device_index=args.mic)
    except OSError as e:
        print("Microphone not found. Try --list-mics to see available devices.", file=sys.stderr)
        raise

    print("=" * 60)
    print("Talk & Read — SpeechRecognition + TTS")
    print("Tip: say 'stop', 'quit', or 'exit' to end the session.")
    print(f"Language: {args.lang} | Mic: {'default' if args.mic is None else args.mic}")
    print("=" * 60)

    # Calibrate for ambient noise
    with mic as source:
        print("Calibrating microphone for ambient noise (1s)...")
        recognizer.adjust_for_ambient_noise(source, duration=1.0)

    STOP_WORDS = {"stop", "quit", "exit", "end", "close"}

    while True:
        user = input("\nPress Enter and speak (type 'q' to quit) > ").strip().lower()
        if user in {"q", "quit", "exit"}:
            break

        with mic as source:
            print("Listening... (start speaking)")
            try:
                audio = recognizer.listen(source, timeout=args.timeout, phrase_time_limit=args.limit)
            except sr.WaitTimeoutError:
                print("No speech detected (timeout). Try again.")
                continue

        print("Transcribing...")
        try:
            if args.sphinx:
                # Force offline
                text = recognize_sphinx_only(recognizer, audio, args.lang)
            else:
                # Try Google, fallback to Sphinx if available
                text = recognize_google_with_fallback(recognizer, audio, args.lang)

            clean = text.strip()
            if not clean:
                print("Heard silence / empty result.")
                speak(engine, "I didn't catch that. Please try again.")
                continue

            print(f"You said: {clean}")
            # Stop on keyword
            if clean.lower() in STOP_WORDS:
                speak(engine, "Goodbye.")
                break

            # Read back
            speak(engine, clean)

        except sr.UnknownValueError:
            print("Couldn't understand the audio.")
            speak(engine, "Sorry, I couldn't understand.")
        except sr.RequestError as e:
            print(f"Speech service request error: {e}")
            speak(engine, "Speech service error.")
        except RuntimeError as e:
            print(str(e))
            speak(engine, "I couldn't transcribe that. Check your internet or install Pocket Sphinx.")
        except Exception as e:
            print(f"Unexpected error: {e}")
            speak(engine, "An unexpected error occurred.")

    print("Exiting. Have a great day!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

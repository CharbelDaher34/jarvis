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

Notes:
- Google recognizer requires internet and has usage limits.
- To change settings, edit the configuration variables at the top of the file.
"""

import sys
import time

import speech_recognition as sr

try:
    import pyttsx3
except Exception as e:
    print("pyttsx3 is required for TTS. Install with: pip install pyttsx3", file=sys.stderr)
    raise


# Configuration variables
MIC_DEVICE_INDEX = None  # Microphone device index (None = default)
LANGUAGE = "en-US"       # Language code for STT & TTS
TTS_RATE = 170          # TTS speaking rate
TTS_VOLUME = 1.0        # TTS volume 0.0–1.0
PAUSE_THRESHOLD = 0.6   # Seconds of silence to consider phrase complete
PHRASE_TIME_LIMIT = 12.0 # Max seconds to listen per phrase
TIMEOUT = None          # Max seconds to wait for speech start (None = no timeout)
FORCE_SPHINX = False    # Force offline STT with PocketSphinx
STOP_WORDS = ["stop", "quit", "exit"]  # Words that end the program when spoken


def speak(text: str):
    """Speak text using TTS engine - simplified approach like main.py"""
    try:
        engine = pyttsx3.init()
        # Set voice preference (try to find Jamie voice like in main.py)
        for voice in engine.getProperty("voices"):
            if "jamie" in voice.name.lower():
                engine.setProperty("voice", voice.id)
                break
        engine.setProperty("rate", TTS_RATE)
        engine.setProperty("volume", TTS_VOLUME)
        engine.say(text)
        engine.runAndWait()
        time.sleep(0.3)  # Brief pause like in main.py
    except Exception as e:
        print(f"TTS Error: {e}")


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
    except Exception as exc:
        # If Sphinx not available, propagate a request error to be handled by caller.
        raise sr.RequestError("No online service and PocketSphinx not installed") from exc


## needed variables
# Prepare recognizer & mic
r = sr.Recognizer()
# Make phrase segmentation snappier - set to 2 seconds for silence detection
r.pause_threshold = 2.0  # Stop transcribing after 2 seconds of silence
r.dynamic_energy_threshold = True
# r.energy_threshold can be set manually if needed (e.g., in very noisy rooms)
mic = sr.Microphone(device_index=MIC_DEVICE_INDEX)
def main():



    print("=" * 60)
    print("Say & Repeat — SpeechRecognition + pyttsx3")
    print("Speak a phrase; I'll repeat it. Starts when voice detected, stops after 2s silence.")
    print("Ctrl+C to quit.")
    print(f"Language={LANGUAGE}  Silence timeout=2.0s  Limit={PHRASE_TIME_LIMIT}s  Mic={'default' if MIC_DEVICE_INDEX is None else MIC_DEVICE_INDEX}")
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
                    audio = r.listen(source, timeout=None, phrase_time_limit=PHRASE_TIME_LIMIT)
                    print("Voice detected, transcribing...")
                except sr.WaitTimeoutError:
                    # This shouldn't happen with timeout=None, but handle it just in case
                    print("...no speech detected, continuing.")
                    continue

            # Transcribe
            try:
                text = transcribe(r, audio, LANGUAGE, force_sphinx=FORCE_SPHINX).strip()
            except sr.UnknownValueError:
                print("I couldn't understand that.")
                speak("Sorry, I couldn't understand that.")
                continue
            except sr.RequestError as e:
                print(f"Transcription error: {e}")
                speak("I couldn't transcribe that. Check your internet or install Pocket Sphinx.")
                continue

            if not text:
                print("(empty)")
                continue

            print(f"You said: {text}")
            # Exit if a stop word is spoken exactly
            if text.lower() in [w.lower() for w in STOP_WORDS]:
                speak("Goodbye.")
                break

            # Speak back
            speak(text)

    except KeyboardInterrupt:
        print("\nExiting... Goodbye.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

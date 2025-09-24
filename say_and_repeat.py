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
- To change settings, edit the .env file or modify config.py.
"""

import sys
import time
import torch
import whisper
import speech_recognition as sr
import numpy as np
from config import settings

try:
    import pyttsx3
except Exception as e:
    print("pyttsx3 is required for TTS. Install with: pip install pyttsx3", file=sys.stderr)
    raise

# Load all configuration variables
MIC_DEVICE_INDEX = settings.mic_device_index
LANGUAGE = settings.language
TTS_RATE = settings.tts_rate
TTS_VOLUME = settings.tts_volume
PAUSE_THRESHOLD = settings.pause_threshold
PHRASE_TIME_LIMIT = settings.phrase_time_limit
TIMEOUT = settings.timeout
FORCE_SPHINX = settings.force_sphinx
STOP_WORDS = settings.get_stop_words_list()
USE_WHISPER = settings.use_whisper
WHISPER_MODEL = settings.whisper_model
TTS_VOICE_PREFERENCE = settings.tts_voice_preference

# Load Whisper model based on configuration
device = "cuda" if torch.cuda.is_available() else "cpu"
model = whisper.load_model(WHISPER_MODEL, device=device)

def speak(text: str):
    """Speak text using TTS engine - simplified approach like main.py"""
    try:
        engine = pyttsx3.init()
        # Set voice preference (try to find configured voice)
        for voice in engine.getProperty("voices"):
            if TTS_VOICE_PREFERENCE.lower() in voice.name.lower():
                engine.setProperty("voice", voice.id)
                break
        engine.setProperty("rate", TTS_RATE)
        engine.setProperty("volume", TTS_VOLUME)
        engine.say(text)
        engine.runAndWait()
        time.sleep(1)  # Brief pause like in main.py
    except Exception as e:
        print(f"TTS Error: {e}")


# def transcribe(recognizer: sr.Recognizer, audio: sr.AudioData, language: str, force_sphinx: bool = False) -> str:
#     # Try Google first (unless forcing Sphinx), then fallback to Sphinx if available.
#     if not force_sphinx:
#         try:
#             return recognizer.recognize_google(audio, language=language)
#         except sr.RequestError:
#             # no internet/quota; try Sphinx
#             pass
#         except sr.UnknownValueError:
#             raise
#     try:
#         import pocketsphinx  # noqa: F401
#         return recognizer.recognize_sphinx(audio, language=language)
#     except Exception as exc:
#         # If Sphinx not available, propagate a request error to be handled by caller.
#         raise sr.RequestError("No online service and PocketSphinx not installed") from exc

def transcribe(
    recognizer: sr.Recognizer,
    audio: sr.AudioData,
    language: str,
    force_sphinx: bool = False,
    use_whisper: bool = USE_WHISPER,
) -> str:
    # Try Google first (unless forcing Sphinx), then Whisper, then fallback to Sphinx if available.
    # if not force_sphinx:
    #     try:
    #         return recognizer.recognize_google(audio, language=language)
    #     except sr.RequestError:
    #         # no internet/quota; try Whisper or Sphinx
    #         pass
    #     except sr.UnknownValueError:
    #         raise

    if use_whisper:
        try:
            import io
            import soundfile as sf

            print("Using Whisper")

            # Normalize language (e.g. 'en-US' → 'en')
            wlang = (language or "en").split("-")[0]

            # Get WAV data at 16kHz mono from SpeechRecognition
            wav_bytes = audio.get_wav_data(convert_rate=16000, convert_width=2)

            # Convert bytes → numpy float32
            wav_stream = io.BytesIO(wav_bytes)
            audio_np, sr_rate = sf.read(wav_stream, dtype="float32")

            # Ensure 16kHz mono
            if sr_rate != 16000:
                raise ValueError(f"Unexpected sample rate {sr_rate}, expected 16kHz")
            if audio_np.ndim > 1:  # stereo → mono
                audio_np = np.mean(audio_np, axis=1)

            # Run Whisper transcription
            result = model.transcribe(
                audio_np,
                language=wlang,
                fp16=torch.cuda.is_available(),  # only use fp16 on GPU
                temperature=0.0,
                without_timestamps=True,
            )
            text = (result.get("text") or "").strip()
            print(f"Whisper result: {text}")
            if text:
                return text
            else:
                print("Whisper returned empty text; falling back…")

        except Exception as exc:
            print(f"Whisper error: {exc}")



    try:
        print("Using Sphinx")
        return recognizer.recognize_sphinx(audio, language=language)
    except Exception as exc:
        raise sr.RequestError(
            "No online service and neither Whisper nor PocketSphinx available"
        ) from exc


# Prepare recognizer & mic using configuration
r = sr.Recognizer()
# Set pause threshold based on configuration
r.pause_threshold = PAUSE_THRESHOLD
r.dynamic_energy_threshold = True
# r.energy_threshold can be set manually if needed (e.g., in very noisy rooms)
mic = sr.Microphone(device_index=MIC_DEVICE_INDEX)
def main():

    
    for i in range(1):
        speak("Hello how are you?")
        time.sleep(0.01)
    print("=" * 60)
    print("Say & Repeat — SpeechRecognition + pyttsx3")
    print(f"Speak a phrase; I'll repeat it. Starts when voice detected, stops after {PAUSE_THRESHOLD}s silence.")
    print("Ctrl+C to quit.")
    print(f"Language={LANGUAGE}  Silence timeout={PAUSE_THRESHOLD}s  Limit={PHRASE_TIME_LIMIT}s  Mic={'default' if MIC_DEVICE_INDEX is None else MIC_DEVICE_INDEX}")
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
                    # and stop after configured seconds of silence (pause_threshold)
                    audio = r.listen(source, timeout=TIMEOUT, phrase_time_limit=PHRASE_TIME_LIMIT)
                    print("Voice detected, transcribing...")
                except sr.WaitTimeoutError:
                    # This shouldn't happen with timeout=None, but handle it just in case
                    print("...no speech detected, continuing.")
                    continue

            # Transcribe
            try:
                text = transcribe(r, audio, LANGUAGE, force_sphinx=FORCE_SPHINX, use_whisper=USE_WHISPER).strip()
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
            for i in text.lower().split():
                if i.lower() in [w.lower() for w in STOP_WORDS]:
                    speak("Goodbye.")
                    return 0

            # Speak back
            speak(text)

    except KeyboardInterrupt:
        print("\nExiting... Goodbye.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

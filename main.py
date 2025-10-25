#!/usr/bin/env python3
"""
Jarvis Voice Assistant - Modular voice-controlled agent

Features:
- Continuous listening with automatic phrase segmentation
- Speech-to-Text with Whisper/Sphinx support
- Text-to-Speech with pyttsx3
- Extensible tool system (playwright_agent, more coming)
- Easy to add/remove tools via configuration

Install:
    uv add SpeechRecognition pyttsx3 pyaudio
    # Optional: uv add torch whisper soundfile

Run:
    uv run main.py

Config:
    Edit .env file or config.py for settings
"""

import asyncio
import speech_recognition as sr
from config import settings
from voice import SpeechRecognizer, TextToSpeech
from tools import ToolProcessor
from tools.playwright_tool import PlaywrightTool
from tools.calculator_tool import CalculatorTool
from tools.datetime_tool import DateTimeTool
from tools.gmail_tool import GmailTool
from tools.search_tool import SearchTool


async def main():
    """Main voice assistant loop."""
    
    # Initialize components
    stt = SpeechRecognizer()
    tts = TextToSpeech()
    
    # Initialize tool processor
    processor = ToolProcessor()
    
    # Register tools based on configuration
    print(f"Enabled tools: {settings.enabled_tools}")
    
    if "playwright_agent" in settings.enabled_tools:
        playwright_tool = PlaywrightTool(
            enabled=True,
            headless=settings.playwright_headless
        )
        processor.register(playwright_tool)
        print("Registered playwright_agent")
    
    if "calculator" in settings.enabled_tools:
        calculator_tool = CalculatorTool(enabled=True)
        processor.register(calculator_tool)
        print("Registered calculator")
    
    if "datetime" in settings.enabled_tools:
        datetime_tool = DateTimeTool(enabled=True)
        processor.register(datetime_tool)
        print("Registered datetime")
    
    if "gmail" in settings.enabled_tools:
        gmail_tool = GmailTool(enabled=True)
        processor.register(gmail_tool)
        print("Registered gmail")
    
    if "search_tool" in settings.enabled_tools:
        search_tool = SearchTool(enabled=True)
        processor.register(search_tool)
        print("Registered search_tool")
    
    # Set up microphone
    mic = sr.Microphone(device_index=settings.mic_device_index)
    
    # Print startup info
    print("=" * 60)
    print("Jarvis Voice Assistant")
    print(f"Language: {settings.language}")
    print(f"Pause threshold: {settings.pause_threshold}s")
    print(f"Enabled tools: {', '.join(processor.get_enabled_tools())}")
    print(f"Stop words: {', '.join(settings.get_stop_words_list())}")
    print("=" * 60)
    
    # Calibrate for ambient noise
    with mic as source:
        print("Calibrating for ambient noise (1s)...")
        stt.recognizer.adjust_for_ambient_noise(source, duration=1.0)
    
    try:
        while True:
            with mic as source:
                print("\nWaiting for voice...")
                
                try:
                    audio = stt.recognizer.listen(
                        source,
                        timeout=settings.timeout,
                        phrase_time_limit=settings.phrase_time_limit
                    )
                    print("Voice detected, transcribing...")
                except sr.WaitTimeoutError:
                    print("...no speech detected, continuing.")
                    continue
            
            # Transcribe
            try:
                text = stt.transcribe(audio).strip()
            except sr.UnknownValueError:
                print("I couldn't understand that.")
                tts.speak("Sorry, I couldn't understand that.")
                continue
            except sr.RequestError as e:
                print(f"Transcription error: {e}")
                tts.speak("I couldn't transcribe that. Check your internet or install Pocket Sphinx.")
                continue
            
            if not text:
                print("(empty)")
                continue
            
            print(f"You said: {text}")
            
            # Check for stop words
            stop_words = [w.lower() for w in settings.get_stop_words_list()]
            for word in text.lower().split():
                if word in stop_words:
                    tts.speak("Goodbye.")
                    return 0
            
            # Process text through tools
            result = await processor.process(text)
            
            # Speak result
            tts.speak(result)
    
    except KeyboardInterrupt:
        print("\nExiting... Goodbye.")
    
    return 0


if __name__ == "__main__":
    asyncio.run(main())



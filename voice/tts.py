"""Text-to-Speech module using pyttsx3."""

import time
import pyttsx3
from config import settings


class TextToSpeech:
    """Text-to-speech wrapper using pyttsx3."""
    
    def __init__(
        self,
        rate: int = None,
        volume: float = None,
        voice_preference: str = None
    ):
        self.rate = rate or settings.tts_rate
        self.volume = volume or settings.tts_volume
        self.voice_preference = voice_preference or settings.tts_voice_preference
    
    def speak(self, text: str):
        """
        Speak text using TTS engine.
        
        Args:
            text: Text to speak
        """
        try:
            engine = pyttsx3.init()
            
            # Set voice preference (try to find configured voice)
            for voice in engine.getProperty("voices"):
                if self.voice_preference.lower() in voice.name.lower():
                    engine.setProperty("voice", voice.id)
                    break
            
            engine.setProperty("rate", self.rate)
            engine.setProperty("volume", self.volume)
            engine.say(text)
            engine.runAndWait()
            time.sleep(1)  # Brief pause
        except Exception as e:
            print(f"TTS Error: {e}")



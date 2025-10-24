"""Speech-to-Text module supporting Whisper, Sphinx, and Google Web Speech."""

import io
import speech_recognition as sr
from config import settings


class SpeechRecognizer:
    """Speech recognition wrapper supporting multiple backends."""
    
    def __init__(
        self,
        language: str = None,
        use_whisper: bool = None,
        whisper_model: str = None
    ):
        self.language = language or settings.language
        self.use_whisper = use_whisper if use_whisper is not None else settings.use_whisper
        self.whisper_model = whisper_model or settings.whisper_model
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = settings.pause_threshold
        self.recognizer.dynamic_energy_threshold = True
        
    def transcribe(self, audio: sr.AudioData) -> str:
        """
        Transcribe audio to text using configured backend.
        
        Args:
            audio: AudioData from speech_recognition
            
        Returns:
            Transcribed text string
            
        Raises:
            sr.UnknownValueError: Speech was unintelligible
            sr.RequestError: Service unavailable
        """
        if self.use_whisper:
            try:
                return self._transcribe_whisper(audio)
            except Exception as exc:
                print(f"Whisper error: {exc}")
        
        try:
            print("Using Sphinx")
            return self.recognizer.recognize_sphinx(audio, language=self.language)
        except Exception as exc:
            raise sr.RequestError(
                "No online service and neither Whisper nor PocketSphinx available"
            ) from exc
    
    def _transcribe_whisper(self, audio: sr.AudioData) -> str:
        """Transcribe using Whisper model."""
        import torch
        import whisper
        import soundfile as sf
        import numpy as np
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = whisper.load_model(self.whisper_model, device=device)
        
        print("Using Whisper")
        
        # Normalize language (e.g. 'en-US' → 'en')
        wlang = (self.language or "en").split("-")[0]
        
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
            fp16=torch.cuda.is_available(),
            temperature=0.0,
            without_timestamps=True,
        )
        text = (result.get("text") or "").strip()
        print(f"Whisper result: {text}")
        
        if text:
            return text
        else:
            print("Whisper returned empty text; falling back…")
            raise ValueError("Empty transcription")



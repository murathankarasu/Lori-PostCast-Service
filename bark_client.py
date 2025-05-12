# Bark ile metni sese çeviren fonksiyon
# Eğer bark pip ile kuruluysa:
# pip install bark

from typing import Optional
import os
import numpy as np
import io
import asyncio

def text_to_speech_bark(text: str, output_path: str = "static/audio/output.mp3", voice_preset: Optional[str] = None):
    """
    Bark ile verilen metni sese çevirir ve .mp3 dosyasına kaydeder.
    Geçici .wav dosyası oluşturmadan bellekte mp3 olarak kaydeder.
    """
    try:
        from bark import SAMPLE_RATE, generate_audio, preload_models
    except ImportError:
        raise ImportError("Bark kütüphanesi yüklü değil! Lütfen 'pip install bark' ile yükleyin.")

    preload_models()
    audio_array = generate_audio(text)

    # Numpy array'i bellekte wav olarak kaydet
    from scipy.io.wavfile import write as write_wav
    wav_buffer = io.BytesIO()
    write_wav(wav_buffer, SAMPLE_RATE, audio_array)
    wav_buffer.seek(0)

    # Bellekteki wav'ı mp3 olarak kaydet
    from pydub import AudioSegment
    audio = AudioSegment.from_wav(wav_buffer)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    audio.export(output_path, format="mp3")
    return output_path

async def _edge_tts_async(text: str, output_path: str, voice: str = "en-US-GuyNeural"):
    from edge_tts import Communicate
    communicate = Communicate(text, voice)
    await communicate.save(output_path)

def text_to_speech_edge_tts(text: str, output_path: str = "static/audio/output.mp3", voice: str = "en-US-GuyNeural"):
    """
    Edge-TTS ile verilen metni sese çevirir ve .mp3 dosyasına kaydeder.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    asyncio.run(_edge_tts_async(text, output_path, voice=voice))
    return output_path

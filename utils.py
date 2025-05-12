import json
from typing import List, Dict, Tuple
import requests
from pydub import AudioSegment
import os
import re

def extract_contents_and_emotions(filename: str) -> List[Tuple[str, str]]:
    """
    Verilen dosyadan recommendation'ları okuyup, her birinin content ve emotion alanlarını döndürür.
    """
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    results = []
    for rec in data.get('recommendations', []):
        content = rec.get('content', '')
        emotion = rec.get('emotion', '')
        results.append((content, emotion))
    return results


def remove_emojis(text: str) -> str:
    """
    Unicode emojileri metinden temizler.
    """
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002700-\U000027BF"  # Dingbats
        "\U000024C2-\U0001F251"  # Enclosed characters
        "]+",
        flags=re.UNICODE
    )
    return emoji_pattern.sub(r'', text)

def remove_ssml_tags(text: str) -> str:
    """
    SSML etiketlerini (örn. <speak>, <break>, <emphasis>, <prosody> vb.) metinden temizler.
    """
    return re.sub(r'<[^>]+>', '', text)

def remove_host_labels(text: str) -> str:
    """
    Metinden sadece satır başında ve iki nokta/etiket şeklinde olan 'Mert:', '*Mert:*', 'Host:', '*Host:*' gibi rol etiketlerini temizler.
    Metin içinde geçen 'Mert' kelimesi silinmez.
    """
    # Satır başında veya boşluk+başlangıçta, ardından Mert: veya Host: veya *Mert:* veya *Host:*
    return re.sub(r'(^|\n)[ \t]*\*?(Mert|Host):\*?[ ]*', r'\1', text, flags=re.IGNORECASE)

def remove_emotion_and_parens(text: str) -> str:
    """
    Parantez içinde 'emotion:', 'duygu:', numara veya benzeri etiketleri temizler.
    """
    # (emotion: ...), (duygu: ...), (emotion ...), (duygu ...), (#32), (32), vb.
    text = re.sub(r'\((\s*(emotion|duygu)\s*:?[^)]*)\)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\(\s*#?\d+\s*\)', '', text)  # (32), (#32) gibi
    return text

def fetch_recommendations_and_extract(user_id: str) -> List[Tuple[str, str, str]]:
    """
    API'den verilen user_id ile recommendation'ları çekip, content, emotion ve username döndürür.
    Content'ten emojiler ve parantezli emotion/duygu/numara etiketleri temizlenir.
    """
    url = f"https://recommend-service-main-services.up.railway.app/api/recommendations/{user_id}"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    results = []
    for rec in data.get('recommendations', []):
        content = rec.get('content', '')
        emotion = rec.get('emotion', '')
        username = rec.get('username', 'Someone')
        content = remove_emojis(content)
        content = remove_emotion_and_parens(content)
        results.append((content, emotion, username))
    return results

def mix_podcast_with_music(podcast_path, music_path, output_path, fade_in_ms=3000, fade_out_ms=5000, music_volume_db=-3):
    podcast = AudioSegment.from_file(podcast_path)
    music = AudioSegment.from_file(music_path)
    podcast_duration = len(podcast)
    # Müziği podcast uzunluğuna göre kırp (sondan)
    if len(music) > podcast_duration:
        music = music[-podcast_duration:]
    else:
        music = music * (podcast_duration // len(music) + 1)
        music = music[:podcast_duration]
    # Fade in/out uygula
    music = music.fade_in(fade_in_ms).fade_out(fade_out_ms)
    # Sabit volume uygula
    music = music + music_volume_db
    # Mixle
    mixed = podcast.overlay(music)
    mixed.export(output_path, format="mp3")
    return output_path

import torch
torch.serialization.add_safe_globals(['numpy.core.multiarray.scalar'])
from flask import Flask, request, jsonify
from utils import fetch_recommendations_and_extract, mix_podcast_with_music, remove_ssml_tags, remove_host_labels
from gpt_client import generate_podcast_script
from bark_client import text_to_speech_edge_tts
import os

try:
    from config import OPENROUTER_API_KEY
    GOOGLE_APPLICATION_CREDENTIALS_PATH = getattr(__import__('config'), 'GOOGLE_APPLICATION_CREDENTIALS_PATH', None)
except ImportError:
    OPENROUTER_API_KEY = None
    GOOGLE_APPLICATION_CREDENTIALS_PATH = None

if GOOGLE_APPLICATION_CREDENTIALS_PATH:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS_PATH

DEFAULT_MODEL = "mistralai/mistral-7b-instruct"
VOICE = "en-US-GuyNeural"
GCP_BUCKET_NAME = "lorien-app-tr.firebasestorage.app"
GCP_FIRESTORE_COLLECTION = "audio_urls"

app = Flask(__name__)

# Google Cloud Storage ve Firestore setup
from google.cloud import storage, firestore

# GCP servisleri için kimlik dosyası ayarlanmalı (GOOGLE_APPLICATION_CREDENTIALS env ile)

def upload_to_gcs(local_path, dest_blob_name, bucket_name):
    print(f"[LOG] Dosya GCS'ye yükleniyor: {local_path} -> {bucket_name}/{dest_blob_name}")
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(dest_blob_name)
    blob.upload_from_filename(local_path)
    blob.make_public()
    print(f"[LOG] Dosya GCS'de herkese açık: {blob.public_url}")
    return blob.public_url

def save_audio_url_to_firestore(user_id, audio_url, collection_name):
    print(f"[LOG] Firestore'a kaydediliyor: user_id={user_id}, url={audio_url}")
    db = firestore.Client()
    doc_ref = db.collection(collection_name).document(user_id)
    doc_ref.set({"podcast_audio_url": audio_url}, merge=True)
    print(f"[LOG] Firestore güncellendi.")

def delete_from_gcs(blob_name, bucket_name):
    print(f"[LOG] GCS'den siliniyor: {bucket_name}/{blob_name}")
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    if blob.exists():
        blob.delete()
        print(f"[LOG] GCS'den silindi: {blob_name}")
    else:
        print(f"[LOG] GCS'de dosya bulunamadı: {blob_name}")

def get_audio_url_from_firestore(user_id, collection_name):
    db = firestore.Client()
    doc_ref = db.collection(collection_name).document(user_id)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get("podcast_audio_url")
    return None

@app.route('/generate_audio', methods=['POST'])
def generate_audio():
    print("[LOG] /generate_audio isteği alındı.")
    data = request.get_json()
    user_id = data.get('user_id')
    api_key = data.get('api_key') or OPENROUTER_API_KEY
    model = data.get('model') or DEFAULT_MODEL
    username = data.get('username', 'dear listener')
    if not user_id:
        print("[ERROR] user_id zorunlu!")
        return jsonify({'error': 'user_id zorunlu!'}), 400
    if not api_key:
        print("[ERROR] api_key zorunlu!")
        return jsonify({'error': 'api_key zorunlu!'}), 400
    try:
        # Önce Firestore'dan eski audio URL'sini bul ve GCS'den sil
        old_audio_url = get_audio_url_from_firestore(user_id, GCP_FIRESTORE_COLLECTION)
        if old_audio_url:
            # GCS blob adını URL'den çıkar
            from urllib.parse import urlparse
            parsed = urlparse(old_audio_url)
            blob_name = parsed.path.lstrip('/')
            delete_from_gcs(blob_name, GCP_BUCKET_NAME)
        print(f"[LOG] Postlar çekiliyor: user_id={user_id}")
        posts = fetch_recommendations_and_extract(user_id)
        if not posts:
            print("[ERROR] Hiç post bulunamadı!")
            return jsonify({'error': 'Hiç post bulunamadı!'}), 404
        print(f"[LOG] {len(posts)} post bulundu.")
        print("[LOG] GPT'den podcast metni isteniyor...")
        podcast_text = generate_podcast_script(posts, api_key, model, username=username)
        print("[LOG] Podcast metni alındı. Metin:")
        print(podcast_text)
        # SSML etiketlerini ve host label'larını temizle
        podcast_text_clean = remove_ssml_tags(podcast_text)
        podcast_text_clean = remove_host_labels(podcast_text_clean)
        audio_path = f"static/audio/{user_id}_podcast.mp3"
        print(f"[LOG] Edge-TTS ile ses üretiliyor: {audio_path}")
        text_to_speech_edge_tts(podcast_text_clean, audio_path, voice=VOICE)
        if os.path.exists(audio_path):
            print(f"[LOG] MP3 dosyası başarıyla oluşturuldu: {audio_path}")
        else:
            print(f"[ERROR] MP3 dosyası oluşturulamadı: {audio_path}")
        # Arka plan müziği ile birleştir
        music_path = "static/music.mp3"
        final_audio_path = f"static/audio/{user_id}_podcast_with_music.mp3"
        print(f"[LOG] Arka plan müziği ile birleştiriliyor: {final_audio_path}")
        mix_podcast_with_music(audio_path, music_path, final_audio_path)
        # GCS'ye bu dosyayı yükle
        gcs_blob_name = f"podcasts/{user_id}_podcast_with_music.mp3"
        audio_url = upload_to_gcs(final_audio_path, gcs_blob_name, GCP_BUCKET_NAME)
        if audio_url:
            print(f"[LOG] Dosya GCS'ye başarıyla yüklendi: {audio_url}")
        else:
            print(f"[ERROR] Dosya GCS'ye yüklenemedi!")
        save_audio_url_to_firestore(user_id, audio_url, GCP_FIRESTORE_COLLECTION)
        print(f"[LOG] İşlem tamamlandı. URL: {audio_url}")
        # Local dosyaları sil
        for path in [audio_path, final_audio_path]:
            if os.path.exists(path):
                os.remove(path)
                print(f"[LOG] Local dosya silindi: {path}")
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return jsonify({'error': str(e)}), 500
    return jsonify({'audio_url': audio_url})

if __name__ == '__main__':
    print("[LOG] Flask sunucusu başlatılıyor...")
    app.run(debug=True)

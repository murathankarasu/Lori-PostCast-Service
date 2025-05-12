import torch
torch.serialization.add_safe_globals(['numpy.core.multiarray.scalar'])
from flask import Flask, request, jsonify
from utils import fetch_recommendations_and_extract, mix_podcast_with_music, remove_ssml_tags, remove_host_labels
from gpt_client import generate_podcast_script
from bark_client import text_to_speech_edge_tts
import os
import traceback

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

GCP_PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")

def upload_to_gcs(local_path, dest_blob_name, bucket_name):
    print(f"[LOG] Dosya GCS'ye yükleniyor: {local_path} -> {bucket_name}/{dest_blob_name}")
    storage_client = storage.Client(project=GCP_PROJECT_ID)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(dest_blob_name)
    blob.upload_from_filename(local_path, timeout=15)
    blob.make_public()
    print(f"[LOG] Dosya GCS'de herkese açık: {blob.public_url}")
    return blob.public_url

def save_audio_url_to_firestore(user_id, audio_url, collection_name):
    print(f"[LOG] Firestore'a kaydediliyor: user_id={user_id}, url={audio_url}")
    db = firestore.Client(project=GCP_PROJECT_ID)
    doc_ref = db.collection(collection_name).document(user_id)
    doc_ref.set({"podcast_audio_url": audio_url}, merge=True, timeout=15)
    print(f"[LOG] Firestore güncellendi.")

def delete_from_gcs(blob_name, bucket_name):
    print(f"[LOG] GCS'den siliniyor: {bucket_name}/{blob_name}")
    storage_client = storage.Client(project=GCP_PROJECT_ID)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    if blob.exists(timeout=10):
        blob.delete(timeout=10)
        print(f"[LOG] GCS'den silindi: {blob_name}")
    else:
        print(f"[LOG] GCS'de dosya bulunamadı: {blob_name}")

def get_audio_url_from_firestore(user_id, collection_name):
    db = firestore.Client(project=GCP_PROJECT_ID)
    doc_ref = db.collection(collection_name).document(user_id)
    doc = doc_ref.get(timeout=10)
    if doc.exists:
        return doc.to_dict().get("podcast_audio_url")
    return None

@app.route('/generate_audio', methods=['POST'])
def generate_audio():
    print("[LOG] /generate_audio isteği alındı.")
    print(f"[LOG] request.headers: {dict(request.headers)}")
    print(f"[LOG] request.data: {request.data}")
    print(f"[LOG] request.json: {request.get_json(silent=True)}")
    data = request.get_json()
    print(f"[LOG] data: {data}")
    user_id = data.get('user_id')
    api_key = data.get('api_key') or OPENROUTER_API_KEY
    model = data.get('model') or DEFAULT_MODEL
    username = data.get('username', 'dear listener')
    print(f"[LOG] user_id: {user_id}, api_key: {api_key}, model: {model}, username: {username}")
    if not user_id:
        print("[ERROR] user_id zorunlu!")
        return jsonify({'error': 'user_id zorunlu!'}), 400
    if not api_key:
        print("[ERROR] api_key zorunlu!")
        return jsonify({'error': 'api_key zorunlu!'}), 400
    try:
        print("[LOG] Firestore'dan eski audio URL'si alınıyor...")
        old_audio_url = get_audio_url_from_firestore(user_id, GCP_FIRESTORE_COLLECTION)
        print(f"[LOG] Eski audio URL: {old_audio_url}")
        if old_audio_url:
            from urllib.parse import urlparse
            parsed = urlparse(old_audio_url)
            blob_name = parsed.path.lstrip('/')
            print(f"[LOG] Eski audio GCS'den siliniyor: {blob_name}")
            delete_from_gcs(blob_name, GCP_BUCKET_NAME)
        print(f"[LOG] Postlar çekiliyor: user_id={user_id}")
        posts = fetch_recommendations_and_extract(user_id)
        print(f"[LOG] Postlar: {posts}")
        if not posts:
            print("[ERROR] Hiç post bulunamadı!")
            return jsonify({'error': 'Hiç post bulunamadı!'}), 404
        print(f"[LOG] {len(posts)} post bulundu.")
        print("[LOG] GPT'den podcast metni isteniyor...")
        podcast_text = generate_podcast_script(posts, api_key, model, username=username)
        print("[LOG] Podcast metni alındı. Metin:")
        print(podcast_text)
        print("[LOG] SSML ve host label temizleniyor...")
        podcast_text_clean = remove_ssml_tags(podcast_text)
        podcast_text_clean = remove_host_labels(podcast_text_clean)
        audio_path = f"static/audio/{user_id}_podcast.mp3"
        print(f"[LOG] Edge-TTS ile ses üretiliyor: {audio_path}")
        text_to_speech_edge_tts(podcast_text_clean, audio_path, voice=VOICE)
        if os.path.exists(audio_path):
            print(f"[LOG] MP3 dosyası başarıyla oluşturuldu: {audio_path}")
        else:
            print(f"[ERROR] MP3 dosyası oluşturulamadı: {audio_path}")
        music_path = "static/music.mp3"
        final_audio_path = f"static/audio/{user_id}_podcast_with_music.mp3"
        print(f"[LOG] Arka plan müziği ile birleştiriliyor: {final_audio_path}")
        mix_podcast_with_music(audio_path, music_path, final_audio_path)
        print(f"[LOG] GCS'ye dosya yükleniyor: {final_audio_path}")
        gcs_blob_name = f"podcasts/{user_id}_podcast_with_music.mp3"
        audio_url = upload_to_gcs(final_audio_path, gcs_blob_name, GCP_BUCKET_NAME)
        print(f"[LOG] GCS'ye yüklenen dosya URL: {audio_url}")
        if audio_url:
            print(f"[LOG] Dosya GCS'ye başarıyla yüklendi: {audio_url}")
        else:
            print(f"[ERROR] Dosya GCS'ye yüklenemedi!")
        print(f"[LOG] Firestore'a audio URL kaydediliyor...")
        save_audio_url_to_firestore(user_id, audio_url, GCP_FIRESTORE_COLLECTION)
        print(f"[LOG] İşlem tamamlandı. URL: {audio_url}")
        for path in [audio_path, final_audio_path]:
            if os.path.exists(path):
                os.remove(path)
                print(f"[LOG] Local dosya silindi: {path}")
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    return jsonify({'audio_url': audio_url})

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    print(f"[LOG] Flask sunucusu başlatılıyor... Port: {port}")
    app.run(host="0.0.0.0", port=port, debug=True)

import torch
torch.serialization.add_safe_globals(['numpy.core.multiarray.scalar'])
from flask import Flask, request, jsonify
from utils import fetch_recommendations_and_extract, mix_podcast_with_music, remove_ssml_tags, remove_host_labels
from gpt_client import generate_podcast_script
from bark_client import text_to_speech_edge_tts
import os
import traceback
from google.cloud import firestore

try:
    from config import OPENROUTER_API_KEY
    GOOGLE_APPLICATION_CREDENTIALS_PATH = getattr(__import__('config'), 'GOOGLE_APPLICATION_CREDENTIALS_PATH', None)
except ImportError:
    OPENROUTER_API_KEY = None
    GOOGLE_APPLICATION_CREDENTIALS_PATH = None

# GOOGLE_APPLICATION_CREDENTIALS environment variable'ı varsa dosya olarak yaz
json_env = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if json_env and json_env.strip().startswith('{'):
    credentials_path = "/tmp/credentials.json"
    with open(credentials_path, "w") as f:
        f.write(json_env)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    print("[LOG] Service account JSON dosyası /tmp/credentials.json olarak yazıldı ve ortam değişkeni ayarlandı.", flush=True)
else:
    print("[WARN] GOOGLE_APPLICATION_CREDENTIALS environment variable'ı bulunamadı veya JSON formatında değil.", flush=True)

if GOOGLE_APPLICATION_CREDENTIALS_PATH:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS_PATH

DEFAULT_MODEL = "mistralai/mistral-7b-instruct"
VOICE = "en-US-GuyNeural"
GCP_BUCKET_NAME = "lorien-app-tr.firebasestorage.app"
GCP_FIRESTORE_COLLECTION = "audio_urls"

app = Flask(__name__)

GCP_PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")

def save_audio_url_to_firestore(user_id, collection_name):
    print(f"[LOG] save_audio_url_to_firestore başladı: user_id={user_id}, collection={collection_name}", flush=True)
    gs_url = f"gs://lorien-app-tr.firebasestorage.app/podcasts/{user_id}_podcast_with_music.mp3"
    print(f"[LOG] Firestore'a kaydediliyor: user_id={user_id}, url={gs_url}", flush=True)
    db = firestore.Client(project=GCP_PROJECT_ID)
    doc_ref = db.collection(collection_name).document(user_id)
    doc_ref.set({"podcast_audio_url": gs_url}, merge=True)
    print(f"[LOG] Firestore güncellendi.", flush=True)
    print(f"[LOG] save_audio_url_to_firestore bitti", flush=True)

def get_audio_url_from_firestore(user_id, collection_name):
    print(f"[LOG] get_audio_url_from_firestore başladı: user_id={user_id}, collection={collection_name}", flush=True)
    db = firestore.Client(project=GCP_PROJECT_ID)
    doc_ref = db.collection(collection_name).document(user_id)
    doc = doc_ref.get()
    if doc.exists:
        print(f"[LOG] Firestore'dan podcast_audio_url bulundu", flush=True)
        return doc.to_dict().get("podcast_audio_url")
    print(f"[LOG] Firestore'da podcast_audio_url bulunamadı", flush=True)
    return None

@app.route('/generate_audio', methods=['POST'])
def generate_audio():
    print("[LOG] /generate_audio isteği alındı.", flush=True)
    print(f"[LOG] request.headers: {dict(request.headers)}", flush=True)
    print(f"[LOG] request.data: {request.data}", flush=True)
    print(f"[LOG] request.json: {request.get_json(silent=True)}", flush=True)
    data = request.get_json()
    print(f"[LOG] data: {data}", flush=True)
    user_id = data.get('user_id')
    api_key = data.get('api_key') or OPENROUTER_API_KEY
    model = data.get('model') or DEFAULT_MODEL
    username = data.get('username', 'dear listener')
    print(f"[LOG] user_id: {user_id}, api_key: {api_key}, model: {model}, username: {username}", flush=True)
    if not user_id:
        print("[ERROR] user_id zorunlu!", flush=True)
        return jsonify({'error': 'user_id zorunlu!'}), 400
    if not api_key:
        print("[ERROR] api_key zorunlu!", flush=True)
        return jsonify({'error': 'api_key zorunlu!'}), 400
    try:
        print("[LOG] Firestore'dan eski audio URL'si alınıyor...", flush=True)
        old_audio_url = get_audio_url_from_firestore(user_id, GCP_FIRESTORE_COLLECTION)
        print(f"[LOG] Eski audio URL: {old_audio_url}", flush=True)
        print(f"[LOG] Postlar çekiliyor: user_id={user_id}", flush=True)
        posts = fetch_recommendations_and_extract(user_id)
        print(f"[LOG] Postlar: {posts}", flush=True)
        if not posts:
            print("[ERROR] Hiç post bulunamadı!", flush=True)
            return jsonify({'error': 'Hiç post bulunamadı!'}), 404
        print(f"[LOG] {len(posts)} post bulundu.", flush=True)
        print("[LOG] GPT'den podcast metni isteniyor...", flush=True)
        podcast_text = generate_podcast_script(posts, api_key, model, username=username)
        print("[LOG] Podcast metni alındı. Metin:", flush=True)
        print(podcast_text, flush=True)
        print("[LOG] SSML ve host label temizleniyor...", flush=True)
        podcast_text_clean = remove_ssml_tags(podcast_text)
        podcast_text_clean = remove_host_labels(podcast_text_clean)
        audio_path = f"static/audio/{user_id}_podcast.mp3"
        print(f"[LOG] Edge-TTS ile ses üretiliyor: {audio_path}", flush=True)
        text_to_speech_edge_tts(podcast_text_clean, audio_path, voice=VOICE)
        if os.path.exists(audio_path):
            print(f"[LOG] MP3 dosyası başarıyla oluşturuldu: {audio_path}", flush=True)
        else:
            print(f"[ERROR] MP3 dosyası oluşturulamadı: {audio_path}", flush=True)
        music_path = "static/music.mp3"
        final_audio_path = f"static/audio/{user_id}_podcast_with_music.mp3"
        print(f"[LOG] Arka plan müziği ile birleştiriliyor: {final_audio_path}", flush=True)
        mix_podcast_with_music(audio_path, music_path, final_audio_path)
        print(f"[LOG] Firestore'a audio URL kaydediliyor...", flush=True)
        save_audio_url_to_firestore(user_id, GCP_FIRESTORE_COLLECTION)
        print(f"[LOG] İşlem tamamlandı. gs://... yolu Firestore'a kaydedildi.", flush=True)
        for path in [audio_path, final_audio_path]:
            if old_audio_url and os.path.exists(path):
                os.remove(path)
                print(f"[LOG] Local dosya silindi: {path}", flush=True)
    except Exception as e:
        print(f"[ERROR] {str(e)}", flush=True)
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    gs_url = f"gs://lorien-app-tr.firebasestorage.app/podcasts/{user_id}_podcast_with_music.mp3"
    print(f"[LOG] /generate_audio isteği başarıyla tamamlandı. gs_url: {gs_url}", flush=True)
    return jsonify({'audio_url': gs_url})

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    print(f"[LOG] Flask sunucusu başlatılıyor... Port: {port}", flush=True)
    app.run(host="0.0.0.0", port=port, debug=True)

# Lori Post Cast Service

This project is an AI-powered podcast generator that creates personalized podcast episodes from social media posts. It uses LLMs (via OpenRouter), Edge-TTS, and Google Cloud (Firestore & Storage) to generate, voice, and store podcast audio files. The service is designed for easy deployment on Railway or Docker.

## Features
- Fetches social media recommendations for a user
- Generates a podcast script in English using LLMs (OpenRouter API)
- Converts the script to speech using Edge-TTS
- Mixes the podcast with background music
- Uploads the final audio to Google Cloud Storage
- Stores the audio URL in Firestore
- Deletes previous audio files for the user on new requests (keeps storage clean)
- All configuration via environment variables (no secrets in code)

## Requirements
- Python 3.11+
- Google Cloud project with Firestore and Storage enabled
- OpenRouter API key
- Railway or Docker for deployment

## Environment Variables
| Variable                        | Description                                      |
|----------------------------------|--------------------------------------------------|
| `OPENROUTER_API_KEY`            | Your OpenRouter API key                          |
| `GOOGLE_APPLICATION_CREDENTIALS_PATH` | Path to your Google service account JSON file |

## Google Service Account Setup
1. Create a service account in Google Cloud Console with access to Firestore and Storage.
2. Download the JSON key file.
3. On Railway, upload this file as a Secret File (e.g. `/app/lorien-app-tr-firebase-adminsdk.json`).
4. Set the environment variable `GOOGLE_APPLICATION_CREDENTIALS_PATH` to the file path.

## Installation & Local Development
```bash
# Clone the repository
$ git clone <repo-url>
$ cd <repo-folder>

# Install dependencies
$ pip install -r requirements.txt

# Set environment variables (or use a .env file)
$ export OPENROUTER_API_KEY=your_key
$ export GOOGLE_APPLICATION_CREDENTIALS_PATH=/path/to/your/service-account.json

# Run the app
$ python app.py
```

## Docker Deployment
```bash
# Build the Docker image
$ docker build -t lori-postcast .

# Run the container
$ docker run -p 5000:5000 \
  -e OPENROUTER_API_KEY=your_key \
  -e GOOGLE_APPLICATION_CREDENTIALS_PATH=/app/lorien-app-tr-firebase-adminsdk.json \
  -v /path/to/lorien-app-tr-firebase-adminsdk.json:/app/lorien-app-tr-firebase-adminsdk.json \
  lori-postcast
```

## Railway Deployment
1. Push your code to GitHub.
2. Create a new Railway project and connect your repo.
3. Add your environment variables in the Railway dashboard.
4. Upload your Google service account JSON as a Secret File.
5. Deploy!

## API Usage
### Endpoint: `/generate_audio` (POST)
**Request JSON:**
```json
{
  "user_id": "USER_ID",
  "api_key": "<optional, overrides env>",
  "model": "<optional, default: mistralai/mistral-7b-instruct>",
  "username": "<the listener's name>"
}
```
**Response JSON:**
```json
{
  "audio_url": "https://.../podcasts/USER_ID_podcast_with_music.mp3"
}
```

## Notes
- All podcast scripts and audio are generated in English.
- Old audio files are deleted from GCS and Firestore on new requests for the same user.
- No audio files are stored locally after upload.

## License
MIT

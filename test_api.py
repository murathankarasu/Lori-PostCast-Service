import requests

url = "https://lori-postcast-service-main-services.up.railway.app/generate_audio"
data = {
    "user_id": "isRKPOpG4zVFmULHJjrsvY8t1Nb2",
    "username": "Murathan"
}
headers = {"Content-Type": "application/json"}

response = requests.post(url, json=data, headers=headers)
print("Status code:", response.status_code)
print("Response:", response.json()) 
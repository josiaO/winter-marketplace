import requests
import os

token_cmd = "sqlite3 db.sqlite3 \"SELECT t.key FROM authtoken_token t JOIN auth_user u ON t.user_id = u.id LIMIT 1;\""
token = os.popen(token_cmd).read().strip()

print(f"Token: {token}")

headers = {
    'Authorization': f'Bearer {token}', 
    'Content-Type': 'application/json'
}

print("Trying with POST...")
res = requests.post('http://127.0.0.1:8000/api/v1/marketplace/favorites/', headers=headers, json={'listingId': 1})
print(f"POST Status: {res.status_code}")
print(f"POST Response: {res.text}")


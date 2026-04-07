import requests
import time

time.sleep(8) # Wait for backend to completely bootstrap the embedding model
try:
    res = requests.post('http://127.0.0.1:8001/api/auth/register', json={'email': 'test_bcrypt@example.com', 'password': 'password123'})
    print('STATUS:', res.status_code)
    print('RESPONSE:', res.json())
except Exception as e:
    print('Error:', e)

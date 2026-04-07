import subprocess
import time
import requests

with open('server.log', 'w') as f:
    proc = subprocess.Popen(['uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8001'], stdout=f, stderr=f)

time.sleep(8)
try:
    res = requests.post('http://127.0.0.1:8001/api/auth/register', json={'email': 'test7@example.com', 'password': 'password123'})
    print('Response Code:', res.status_code)
except Exception as e:
    print('Failed to hit API:', e)

time.sleep(2)
proc.terminate()

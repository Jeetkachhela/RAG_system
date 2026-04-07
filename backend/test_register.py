from auth import RegisterRequest
from main import register_endpoint
import traceback
try:
    req = RegisterRequest(email='test6@example.com', password='password123')
    res = register_endpoint(req, current_user=None)
    print(res)
except Exception as e:
    traceback.print_exc()

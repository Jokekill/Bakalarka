import os

ENGINE_URL = os.getenv('ENGINE_URL', 'http://localhost:8000/analyze')
REQUEST_TIMEOUT_S = float(os.getenv('ENGINE_TIMEOUT', '12'))

CHESSGROUND_VERSION = os.getenv('CHESSGROUND_VERSION', '8.2.0')

HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '8080'))

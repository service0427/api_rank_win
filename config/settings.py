import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# API Server Configuration
API_HOST = "0.0.0.0"
API_PORT = 8888

# Database Configurations
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER", "rank")
DB_PASS = os.getenv("DB_PASS", "Tech1324")
DB_NAME = os.getenv("DB_NAME", "rank")

# Concurrency Controls
MAX_CONCURRENT_BROWSERS = int(os.getenv("MAX_CONCURRENT_BROWSERS", 5))

# Proxy Configuration
PROXY_STATUS_API = "http://127.0.0.1:9999/api/proxy/status"
USE_PROXY_POOL = os.getenv("USE_PROXY_POOL", "1" if os.name == "posix" else "0") == "1"
PROXY_TIMEOUT = 8.0

# User Agents
MOBILE_USER_AGENT = "Mozilla/5.0 (Linux; Android 14; SM-S928N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"
DESKTOP_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

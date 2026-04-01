# ==========================================
# config.py — Environment & Logging Setup
# ==========================================
import os
import logging
from dotenv import load_dotenv
from openai import OpenAI

# Load .env
load_dotenv()

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
MONGO_URI    = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME      = os.getenv("DB_NAME", "medimitra")
PORT         = int(os.getenv("PORT", 5000))
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Groq / OpenAI client
client = None
if not GROQ_API_KEY:
    logger.warning("GROQ_API_KEY not found in .env — AI features will be disabled.")
else:
    client = OpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1"
    )
    logger.info("Groq API configured.")

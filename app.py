# ==========================================
# app.py — Application Entry Point
# ==========================================
import os
from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pymongo import MongoClient

from config import BASE_DIR, MONGO_URI, DB_NAME, PORT, logger
from routes.api import api_bp

# Flask Setup
app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "static"),
    template_folder=os.path.join(BASE_DIR, "templates")
)

# Rate Limiting — 30 requests/minute per IP on chat endpoint
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://"
)

# Database
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[DB_NAME]

# Register Blueprint
app.register_blueprint(api_bp)

# Apply rate limit to the chat endpoint after Blueprint registration
limiter.limit("30 per minute")(app.view_functions["api.chat_api"])

if __name__ == "__main__":
    flask_debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    logger.info(f"Starting MediMitra on port {PORT} (debug={flask_debug})")
    app.run(debug=flask_debug, host="0.0.0.0", port=PORT)

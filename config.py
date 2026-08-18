"""
Application configuration module.

Reads settings from environment variables (.env file) with sensible defaults.
Tokens are never hard-coded and only kept in memory during the session.
"""

import os
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()


class Config:
    """Application configuration."""

    # Flask settings
    FLASK_HOST = '127.0.0.1'
    FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'

    # Webhook settings
    WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', '5001'))
    WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', '')

    # Bot settings (can also be provided via UI)
    BOT_TOKEN = os.getenv('BOT_TOKEN', '')
    NGROK_AUTHTOKEN = os.getenv('NGROK_AUTHTOKEN', '')

    # Filter defaults
    REMOVE_TIMESTAMP = True
    REMOVE_SENDER = True
    DEDUPLICATE = True
    NORMALIZE_WHITESPACE = True
    CASE_SENSITIVE = True

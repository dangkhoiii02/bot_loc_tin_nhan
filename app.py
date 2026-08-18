"""
Main Flask application.

Serves the local admin UI on 127.0.0.1:5000 and provides API endpoints
for message filtering and bot management.
"""

import atexit
import logging
from flask import Flask, render_template, request, jsonify

from config import Config
from core.filter import MessageFilter
from bot.manager import BotManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize components
bot_manager = BotManager()


# ────────────────────────────────────────────
# Routes — UI
# ────────────────────────────────────────────

@app.route('/')
def index():
    """Serve the main admin UI."""
    return render_template('index.html')


# ────────────────────────────────────────────
# Routes — Filter API
# ────────────────────────────────────────────

@app.route('/api/filter', methods=['POST'])
def api_filter():
    """
    Filter raw chat text.

    Request JSON:
        { "text": "...", "options": { ... } }

    Response JSON:
        { "result": "...", "input_count": N, "output_count": N,
          "duplicate_count": N, "invalid_count": N }
    """
    data = request.get_json(force=True, silent=True)
    if not data or 'text' not in data:
        return jsonify({'error': 'Missing "text" field.'}), 400

    raw_text = data['text']
    options = data.get('options', {})

    # Build filter with options
    msg_filter = MessageFilter(
        remove_timestamp=options.get('remove_timestamp', True),
        remove_sender=options.get('remove_sender', True),
        deduplicate=options.get('deduplicate', True),
        do_normalize_whitespace=options.get('normalize_whitespace', True),
        case_sensitive=options.get('case_sensitive', True),
    )

    result = msg_filter.filter_text(raw_text)

    return jsonify({
        'result': result.result_text,
        'input_count': result.input_count,
        'output_count': result.output_count,
        'duplicate_count': result.duplicate_count,
        'invalid_count': result.invalid_count,
    })


# ────────────────────────────────────────────
# Routes — Bot API
# ────────────────────────────────────────────

@app.route('/api/bot/connect', methods=['POST'])
def api_bot_connect():
    """
    Connect bot with provided configuration.

    Request JSON:
        { "bot_token": "...", "ngrok_authtoken": "...",
          "webhook_port": 5001, "webhook_secret": "..." }
    """
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({'error': 'Missing configuration.'}), 400

    result = bot_manager.connect(data)
    status_code = 200 if result.get('error') is None else 400
    return jsonify(result), status_code


@app.route('/api/bot/disconnect', methods=['POST'])
def api_bot_disconnect():
    """Disconnect bot and cleanup resources."""
    result = bot_manager.disconnect()
    return jsonify(result)


@app.route('/api/bot/status', methods=['GET'])
def api_bot_status():
    """Get current bot status."""
    return jsonify(bot_manager.get_status())


@app.route('/api/bot/defaults', methods=['GET'])
def api_bot_defaults():
    """Return pre-configured defaults from .env for auto-filling the UI."""
    return jsonify({
        'bot_token': Config.BOT_TOKEN,
        'ngrok_authtoken': Config.NGROK_AUTHTOKEN,
        'webhook_port': Config.WEBHOOK_PORT,
        'webhook_secret': Config.WEBHOOK_SECRET,
    })


# ────────────────────────────────────────────
# Cleanup
# ────────────────────────────────────────────

def cleanup():
    """Graceful shutdown: disconnect bot if connected."""
    logger.info('Shutting down...')
    try:
        bot_manager.disconnect()
    except Exception as e:
        logger.warning('Cleanup error: %s', str(e))


atexit.register(cleanup)


# ────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────

if __name__ == '__main__':
    logger.info('Starting Message Filter Bot...')
    logger.info('Open http://%s:%d in your browser.', Config.FLASK_HOST, Config.FLASK_PORT)
    app.run(
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=Config.FLASK_DEBUG,
    )

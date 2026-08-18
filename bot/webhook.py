"""
Webhook server module.

Provides a Flask Blueprint for receiving webhook requests from bot platforms.
Runs on a separate port (default 5001) to isolate from the admin UI.
"""

import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

webhook_bp = Blueprint('webhook', __name__)

# These will be set by BotManager when connecting
_webhook_secret = None
_message_handler = None


def configure_webhook(secret: str, handler):
    """
    Configure webhook with secret and message handler.

    Args:
        secret: Expected secret in webhook URL path.
        handler: Callable(chat_id: str, text: str) to process incoming messages.
    """
    global _webhook_secret, _message_handler
    _webhook_secret = secret
    _message_handler = handler
    logger.info('Webhook configured with secret.')


def reset_webhook():
    """Reset webhook configuration."""
    global _webhook_secret, _message_handler
    _webhook_secret = None
    _message_handler = None
    logger.info('Webhook configuration reset.')


@webhook_bp.route('/webhook/<secret>', methods=['POST'])
def handle_webhook(secret):
    """
    Handle incoming webhook requests from Bot API.

    Validates the secret, extracts message text, and delegates to the handler.
    """
    # Validate secret
    if _webhook_secret is None or secret != _webhook_secret:
        logger.warning('Webhook request with invalid secret.')
        return jsonify({'status': 'forbidden'}), 403

    if _message_handler is None:
        logger.error('No message handler configured.')
        return jsonify({'status': 'error', 'message': 'Handler not configured'}), 500

    try:
        update = request.get_json(force=True, silent=True)
        if not update:
            return jsonify({'status': 'ok'}), 200

        # Extract message from Telegram update
        message = update.get('message') or update.get('edited_message')
        if not message:
            # Not a message update (could be callback, inline, etc.)
            return jsonify({'status': 'ok'}), 200

        text = message.get('text')
        if not text:
            # Not a text message (photo, sticker, etc.) — skip
            return jsonify({'status': 'ok'}), 200

        chat_id = str(message['chat']['id'])

        # Delegate to message handler
        _message_handler(chat_id, text)

        return jsonify({'status': 'ok'}), 200

    except Exception as e:
        logger.error('Error processing webhook: %s', str(e))
        return jsonify({'status': 'error'}), 500

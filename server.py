"""
Production server for Render.com deployment.

Simplified single-app architecture:
- One Flask app handling webhook endpoint
- Auto-registers webhook on startup
- Health check endpoint for Render
- No ngrok, no admin UI needed
"""

import logging
import os
import secrets

from flask import Flask, request, jsonify

from core.filter import MessageFilter
from bot.telegram import TelegramBot

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

# ── Configuration ──
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', '') or secrets.token_urlsafe(32)
PORT = int(os.environ.get('PORT', '10000'))  # Render assigns PORT

# ── Initialize ──
app = Flask(__name__)
bot = TelegramBot()
msg_filter = MessageFilter()

_is_connected = False


# ═══════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════

@app.route('/')
def health():
    """Health check endpoint for Render."""
    return jsonify({
        'status': 'ok',
        'bot': _is_connected,
        'name': 'BiBoom Bot - Message Filter',
    })


@app.route(f'/webhook/{WEBHOOK_SECRET}', methods=['POST'])
def handle_webhook():
    """Handle incoming Telegram webhook updates."""
    try:
        update = request.get_json(force=True, silent=True)
        if not update:
            return jsonify({'status': 'ok'}), 200

        # Extract message
        message = update.get('message') or update.get('edited_message')
        if not message:
            return jsonify({'status': 'ok'}), 200

        text = message.get('text', '')
        chat_id = str(message['chat']['id'])

        # Handle commands
        if text.startswith('/'):
            _handle_command(chat_id, text, message)
        else:
            # Process as filter input
            _handle_filter(chat_id, text)

        return jsonify({'status': 'ok'}), 200

    except Exception as e:
        logger.error('Webhook error: %s', str(e))
        return jsonify({'status': 'error'}), 500


# ═══════════════════════════════════════════
# Message Handlers
# ═══════════════════════════════════════════

def _handle_command(chat_id: str, text: str, message: dict):
    """Handle bot commands."""
    command = text.split()[0].split('@')[0].lower()  # Remove @botname suffix

    if command == '/start':
        first_name = message.get('from', {}).get('first_name', 'bạn')
        reply = (
            f'👋 Xin chào {first_name}!\n\n'
            f'Tôi là **BiBoom Bot** — bot lọc tin nhắn tự động.\n\n'
            f'📋 **Cách dùng:**\n'
            f'Gửi hoặc dán tin nhắn có format:\n'
            f'`[17/08/2026 18:16] Mike: nội dung`\n\n'
            f'Tôi sẽ:\n'
            f'• Loại bỏ timestamp & tên người gửi\n'
            f'• Chuẩn hóa khoảng trắng\n'
            f'• Lọc các dòng trùng lặp\n'
            f'• Trả về kết quả sạch\n\n'
            f'📌 Thêm tôi vào nhóm để lọc tin nhắn cho cả team!\n\n'
            f'Gõ /help để xem thêm.'
        )
        bot.send_message(chat_id, reply)

    elif command == '/help':
        reply = (
            '📖 **Hướng dẫn sử dụng BiBoom Bot**\n\n'
            '**Lọc tin nhắn:**\n'
            'Dán tin nhắn có timestamp vào chat, bot sẽ tự động lọc.\n\n'
            '**Ví dụ input:**\n'
            '```\n'
            '[17/08/2026 18:16] Mike: cuu cái b\n'
            '[17/08/2026 18:18] Boy Bad: sao b\n'
            '[17/08/2026 18:18] Mike: tui chạy r b\n'
            '[17/08/2026 18:16] Mike: cuu cái b\n'
            '```\n\n'
            '**Kết quả:**\n'
            '```\n'
            'cuu cái b\n'
            'sao b\n'
            'tui chạy r b\n'
            '```\n'
            '(Loại 1 dòng trùng)\n\n'
            '**Lệnh:**\n'
            '/start — Giới thiệu bot\n'
            '/help — Hướng dẫn này\n'
            '/filter — Lọc tin nhắn (reply tin nhắn cần lọc)\n\n'
            '**Trong nhóm:**\n'
            'Bot tự động lọc mọi tin nhắn có format timestamp.\n'
            'Hoặc reply tin nhắn cần lọc với lệnh /filter.'
        )
        bot.send_message(chat_id, reply)

    elif command == '/filter':
        # Check if this is a reply to another message
        reply_to = message.get('reply_to_message')
        if reply_to and reply_to.get('text'):
            _handle_filter(chat_id, reply_to['text'])
        else:
            bot.send_message(
                chat_id,
                '💡 Hãy reply (trả lời) tin nhắn cần lọc với lệnh /filter\n'
                'Hoặc dán trực tiếp nội dung cần lọc.'
            )

    else:
        # Unknown command — ignore silently in groups
        chat_type = message.get('chat', {}).get('type', 'private')
        if chat_type == 'private':
            bot.send_message(chat_id, '❓ Lệnh không hợp lệ. Gõ /help để xem hướng dẫn.')


def _handle_filter(chat_id: str, text: str):
    """Process text through filter engine and reply."""
    if not text or not text.strip():
        return

    result = msg_filter.filter_text(text)

    if result.result_text:
        reply = result.result_text

        # Only show stats if there were meaningful changes
        if result.duplicate_count > 0 or result.invalid_count > 0:
            stats = (
                f'\n\n📊 Thống kê:\n'
                f'• Dòng nhập: {result.input_count}\n'
                f'• Dòng xuất: {result.output_count}\n'
                f'• Trùng lặp: {result.duplicate_count}'
            )
            if result.invalid_count > 0:
                stats += f'\n• Sai format: {result.invalid_count}'
            reply += stats

        bot.send_message(chat_id, reply)
    # If no result, don't reply (could be normal chat in groups)


# ═══════════════════════════════════════════
# Startup — Register Webhook
# ═══════════════════════════════════════════

def register_webhook():
    """Register webhook with Telegram on startup."""
    global _is_connected

    bot_token = os.environ.get('BOT_TOKEN', '').strip()
    render_url = os.environ.get('RENDER_EXTERNAL_URL', '').strip()

    if not bot_token:
        logger.error('BOT_TOKEN not set! Set it in Environment Variables on Render dashboard.')
        return False

    # Connect to bot
    if not bot.connect(bot_token):
        logger.error('Failed to connect to Telegram bot. Check BOT_TOKEN.')
        return False

    # Build webhook URL
    if render_url:
        webhook_url = f'{render_url}/webhook/{WEBHOOK_SECRET}'
    else:
        logger.warning('RENDER_EXTERNAL_URL not set yet. Will register webhook when URL is available.')
        _is_connected = True
        return True

    # Register webhook
    if bot.set_webhook(webhook_url):
        _is_connected = True
        logger.info('✅ Bot online! Webhook: %s', webhook_url)
        return True
    else:
        logger.error('Failed to register webhook.')
        return False


# Register on import (when gunicorn loads)
register_webhook()


# ═══════════════════════════════════════════
# Direct run (for local testing)
# ═══════════════════════════════════════════

if __name__ == '__main__':
    if not _is_connected:
        logger.error('Bot failed to start. Check configuration.')
    else:
        logger.info('Starting server on port %d...', PORT)

    app.run(host='0.0.0.0', port=PORT, debug=False)

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
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8767746273:AAHspW03yr722PEH0q2OXUJofWBkxLBwfz0').strip()
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', 'bot_loc_tin_nhan_secret_key_2026').strip()
PORT = int(os.environ.get('PORT', '10000'))  # Render assigns PORT
DEFAULT_RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://bot-loc-tin-nhan.onrender.com').strip()

# ── Initialize ──
app = Flask(__name__)
bot = TelegramBot()
msg_filter = MessageFilter()

_is_connected = False


def _register_bot_webhook(domain: str = None):
    """Register webhook URL with Telegram API."""
    global _is_connected

    token = os.environ.get('BOT_TOKEN', BOT_TOKEN).strip() or BOT_TOKEN
    target_url = (domain or os.environ.get('RENDER_EXTERNAL_URL', DEFAULT_RENDER_URL)).strip().rstrip('/')

    if not target_url.startswith('https://'):
        if target_url.startswith('http://'):
            target_url = target_url.replace('http://', 'https://')
        else:
            target_url = f'https://{target_url}'

    # Don't register local addresses with Telegram
    if 'localhost' in target_url or '127.0.0.1' in target_url or '0.0.0.0' in target_url:
        return False

    webhook_endpoint = f'{target_url}/webhook/{WEBHOOK_SECRET}'
    logger.info('Registering Telegram Webhook: %s', webhook_endpoint)

    if not bot.token:
        if not bot.connect(token):
            logger.error('Failed to connect to Telegram API.')
            return False

    if bot.set_webhook(webhook_endpoint):
        _is_connected = True
        logger.info('✅ Telegram Webhook successfully set to: %s', webhook_endpoint)
        return True
    else:
        logger.error('❌ Failed to set Telegram Webhook.')
        return False


# ═══════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════

@app.before_request
def ensure_webhook():
    """Ensure webhook is registered on first incoming HTTP request."""
    global _is_connected
    if not _is_connected:
        host = request.headers.get('X-Forwarded-Host') or request.host
        if host and 'localhost' not in host and '127.0.0.1' not in host:
            _register_bot_webhook(f'https://{host}')


@app.route('/')
def health():
    """Health check endpoint for Render."""
    return jsonify({
        'status': 'ok',
        'bot_connected': bot.token is not None,
        'webhook_registered': _is_connected,
        'name': 'Bot_loc_tin_nhan',
    })


@app.route('/webhook', methods=['POST'])
@app.route(f'/webhook/{WEBHOOK_SECRET}', methods=['POST'])
def handle_webhook(secret=None):
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
            f'Tôi là **Bot_loc_tin_nhan** — bot lọc tin nhắn tự động.\n\n'
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
            '📖 **Hướng dẫn sử dụng Bot_loc_tin_nhan**\n\n'
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


# Initial registration on module import
_register_bot_webhook()


# ═══════════════════════════════════════════
# Direct run (for local testing)
# ═══════════════════════════════════════════

if __name__ == '__main__':
    logger.info('Starting server on port %d...', PORT)
    app.run(host='0.0.0.0', port=PORT, debug=False)

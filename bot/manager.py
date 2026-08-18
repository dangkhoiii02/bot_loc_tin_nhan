"""
Bot Manager module.

Orchestrates the full connect/disconnect lifecycle:
- Validate configuration
- Start/stop webhook server
- Start/stop ngrok tunnel
- Register/delete webhook with bot platform
- Process incoming messages through Filter Engine
"""

import logging
import secrets
import threading
from dataclasses import dataclass, field
from typing import Optional

from flask import Flask

from .telegram import TelegramBot
from .webhook import webhook_bp, configure_webhook, reset_webhook
from core.filter import MessageFilter
from tunnel.ngrok_manager import NgrokManager

logger = logging.getLogger(__name__)


@dataclass
class BotConfig:
    """Configuration for bot connection."""
    platform: str = 'telegram'
    bot_token: str = ''
    webhook_secret: str = ''
    webhook_port: int = 5001
    ngrok_authtoken: str = ''


@dataclass
class BotStatus:
    """Current status of bot components."""
    local_server: bool = False
    bot_connected: bool = False
    ngrok_online: bool = False
    public_url: Optional[str] = None
    bot_username: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self):
        return {
            'local_server': self.local_server,
            'bot_connected': self.bot_connected,
            'ngrok_online': self.ngrok_online,
            'public_url': self.public_url,
            'bot_username': self.bot_username,
            'error': self.error,
        }


class BotManager:
    """Manages bot lifecycle: connect, disconnect, and message processing."""

    def __init__(self):
        self.config: Optional[BotConfig] = None
        self.status = BotStatus()
        self.bot: Optional[TelegramBot] = None
        self.ngrok = NgrokManager()
        self.filter = MessageFilter()
        self._webhook_app: Optional[Flask] = None
        self._webhook_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def connect(self, config: dict) -> dict:
        """
        Start the full connection sequence.

        Args:
            config: Dict with bot_token, ngrok_authtoken, webhook_port, webhook_secret.

        Returns:
            Status dict with connection result.
        """
        with self._lock:
            try:
                # Reset any previous state
                self._cleanup()

                # Parse config
                self.config = BotConfig(
                    platform=config.get('platform', 'telegram'),
                    bot_token=config.get('bot_token', ''),
                    webhook_secret=config.get('webhook_secret', '') or secrets.token_urlsafe(32),
                    webhook_port=int(config.get('webhook_port', 5001)),
                    ngrok_authtoken=config.get('ngrok_authtoken', ''),
                )

                # Validate required fields
                if not self.config.bot_token:
                    self.status.error = 'Bot Token is required.'
                    return self.status.to_dict()

                if not self.config.ngrok_authtoken:
                    self.status.error = 'Ngrok Authtoken is required.'
                    return self.status.to_dict()

                # Step 1: Connect to bot platform
                logger.info('Step 1: Connecting to bot...')
                self.bot = TelegramBot()
                if not self.bot.connect(self.config.bot_token):
                    self.status.error = 'Invalid Bot Token. Please check and try again.'
                    return self.status.to_dict()

                self.status.bot_connected = True
                self.status.bot_username = self.bot.bot_info.get('username', '')

                # Step 2: Start webhook server
                logger.info('Step 2: Starting webhook server on port %d...', self.config.webhook_port)
                configure_webhook(self.config.webhook_secret, self._handle_message)
                self._start_webhook_server()
                self.status.local_server = True

                # Step 3: Start ngrok tunnel
                logger.info('Step 3: Starting ngrok tunnel...')
                public_url = self.ngrok.start(
                    port=self.config.webhook_port,
                    authtoken=self.config.ngrok_authtoken,
                )
                if not public_url:
                    self.status.error = 'Failed to start ngrok. Check your authtoken.'
                    self._cleanup()
                    return self.status.to_dict()

                self.status.ngrok_online = True
                webhook_url = f'{public_url}/webhook/{self.config.webhook_secret}'
                self.status.public_url = webhook_url

                # Step 4: Register webhook with bot platform
                logger.info('Step 4: Registering webhook...')
                if not self.bot.set_webhook(webhook_url):
                    self.status.error = 'Failed to register webhook with Bot API.'
                    self._cleanup()
                    return self.status.to_dict()

                self.status.error = None
                logger.info('Bot connected successfully! Webhook: %s', webhook_url)
                return self.status.to_dict()

            except Exception as e:
                logger.error('Connection failed: %s', str(e))
                self.status.error = f'Connection failed: {str(e)}'
                self._cleanup()
                return self.status.to_dict()

    def disconnect(self) -> dict:
        """
        Disconnect bot and cleanup all resources.

        Returns:
            Status dict after disconnection.
        """
        with self._lock:
            try:
                self._cleanup()
                self.status = BotStatus()
                logger.info('Bot disconnected successfully.')
                return self.status.to_dict()
            except Exception as e:
                logger.error('Disconnection error: %s', str(e))
                self.status = BotStatus(error=f'Disconnect error: {str(e)}')
                return self.status.to_dict()

    def get_status(self) -> dict:
        """Get current bot status."""
        return self.status.to_dict()

    def _handle_message(self, chat_id: str, text: str):
        """
        Process incoming message through Filter Engine and reply.

        Args:
            chat_id: Source chat ID.
            text: Raw message text.
        """
        try:
            result = self.filter.filter_text(text)

            if result.result_text:
                reply = result.result_text
                stats = (
                    f'\n\n📊 Thống kê:\n'
                    f'• Dòng nhập: {result.input_count}\n'
                    f'• Dòng xuất: {result.output_count}\n'
                    f'• Trùng lặp: {result.duplicate_count}\n'
                    f'• Sai format: {result.invalid_count}'
                )
                reply += stats
            else:
                reply = '⚠️ Không tìm thấy nội dung hợp lệ để lọc.'

            if self.bot:
                self.bot.send_message(chat_id, reply)
        except Exception as e:
            logger.error('Error handling message: %s', str(e))
            if self.bot:
                self.bot.send_message(chat_id, f'❌ Lỗi xử lý: {str(e)}')

    def _start_webhook_server(self):
        """Start webhook Flask app in a background thread."""
        self._webhook_app = Flask(__name__)
        self._webhook_app.register_blueprint(webhook_bp)

        self._webhook_thread = threading.Thread(
            target=self._webhook_app.run,
            kwargs={
                'host': '0.0.0.0',
                'port': self.config.webhook_port,
                'debug': False,
                'use_reloader': False,
            },
            daemon=True,
        )
        self._webhook_thread.start()
        logger.info('Webhook server started on port %d.', self.config.webhook_port)

    def _cleanup(self):
        """Cleanup all resources in reverse order."""
        # Delete webhook from bot API
        if self.bot and self.status.bot_connected:
            try:
                self.bot.delete_webhook()
            except Exception as e:
                logger.warning('Error deleting webhook: %s', str(e))

        # Stop ngrok
        if self.status.ngrok_online:
            try:
                self.ngrok.stop()
            except Exception as e:
                logger.warning('Error stopping ngrok: %s', str(e))

        # Reset webhook handler
        reset_webhook()

        # Disconnect bot
        if self.bot:
            try:
                self.bot.disconnect()
            except Exception as e:
                logger.warning('Error disconnecting bot: %s', str(e))

        self.bot = None
        self._webhook_app = None
        self._webhook_thread = None

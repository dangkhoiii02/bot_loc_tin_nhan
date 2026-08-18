"""
Telegram Bot adapter implementation.

Communicates with the Telegram Bot API via HTTP requests.
Handles message sending with automatic text splitting for long messages.
"""

import logging
from typing import Any, Dict, List, Optional

import requests

from .adapter import BotAdapter

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = 'https://api.telegram.org/bot{token}'
MAX_MESSAGE_LENGTH = 4096  # Telegram limit


class TelegramBot(BotAdapter):
    """Telegram Bot API adapter."""

    def __init__(self):
        self.token: Optional[str] = None
        self.bot_info: Optional[Dict[str, Any]] = None
        self._api_base: Optional[str] = None

    def _api_url(self, method: str) -> str:
        """Build API URL for a given method."""
        if not self._api_base:
            raise RuntimeError('Bot not connected. Call connect() first.')
        return f'{self._api_base}/{method}'

    def connect(self, token: str) -> bool:
        """Verify token and connect to Telegram Bot API."""
        self.token = token
        self._api_base = TELEGRAM_API_BASE.format(token=token)

        bot_info = self.get_me()
        if bot_info is None:
            self.token = None
            self._api_base = None
            return False

        self.bot_info = bot_info
        logger.info('Connected to Telegram bot: @%s', bot_info.get('username', 'unknown'))
        return True

    def disconnect(self) -> bool:
        """Disconnect from Telegram Bot API."""
        self.token = None
        self.bot_info = None
        self._api_base = None
        logger.info('Disconnected from Telegram bot.')
        return True

    def get_me(self) -> Optional[Dict[str, Any]]:
        """Get bot info using getMe API method."""
        try:
            resp = requests.get(
                self._api_url('getMe'),
                timeout=10,
            )
            data = resp.json()
            if data.get('ok'):
                return data.get('result')
            logger.error('getMe failed: %s', data.get('description', 'Unknown error'))
            return None
        except requests.RequestException as e:
            logger.error('getMe request failed: %s', str(e))
            return None

    def set_webhook(self, url: str) -> bool:
        """Register webhook URL with Telegram."""
        try:
            resp = requests.post(
                self._api_url('setWebhook'),
                json={'url': url},
                timeout=10,
            )
            data = resp.json()
            if data.get('ok'):
                logger.info('Webhook set: %s', url)
                return True
            logger.error('setWebhook failed: %s', data.get('description', 'Unknown error'))
            return False
        except requests.RequestException as e:
            logger.error('setWebhook request failed: %s', str(e))
            return False

    def delete_webhook(self) -> bool:
        """Remove webhook from Telegram."""
        try:
            resp = requests.post(
                self._api_url('deleteWebhook'),
                timeout=10,
            )
            data = resp.json()
            if data.get('ok'):
                logger.info('Webhook deleted.')
                return True
            logger.error('deleteWebhook failed: %s', data.get('description', 'Unknown error'))
            return False
        except requests.RequestException as e:
            logger.error('deleteWebhook request failed: %s', str(e))
            return False

    def send_message(self, chat_id: str, text: str) -> bool:
        """
        Send message to a chat. Automatically splits long messages.

        Args:
            chat_id: Telegram chat ID.
            text: Message text.

        Returns:
            True if all message parts sent successfully.
        """
        if not text or not text.strip():
            return True

        chunks = self._split_message(text)
        success = True

        for chunk in chunks:
            if not self._send_single(chat_id, chunk):
                success = False

        return success

    def _send_single(self, chat_id: str, text: str) -> bool:
        """Send a single message chunk."""
        try:
            resp = requests.post(
                self._api_url('sendMessage'),
                json={
                    'chat_id': chat_id,
                    'text': text,
                },
                timeout=10,
            )
            data = resp.json()
            if data.get('ok'):
                return True
            logger.error('sendMessage failed: %s', data.get('description', 'Unknown error'))
            return False
        except requests.RequestException as e:
            logger.error('sendMessage request failed: %s', str(e))
            return False

    @staticmethod
    def _split_message(text: str) -> List[str]:
        """
        Split text into chunks that fit within Telegram's message limit.
        Tries to split at newlines for cleaner output.
        """
        if len(text) <= MAX_MESSAGE_LENGTH:
            return [text]

        chunks = []
        while text:
            if len(text) <= MAX_MESSAGE_LENGTH:
                chunks.append(text)
                break

            # Try to find a newline to split at
            split_pos = text.rfind('\n', 0, MAX_MESSAGE_LENGTH)
            if split_pos == -1:
                # No newline found, hard split
                split_pos = MAX_MESSAGE_LENGTH

            chunks.append(text[:split_pos])
            text = text[split_pos:].lstrip('\n')

        return chunks

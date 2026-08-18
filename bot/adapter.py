"""
Abstract bot adapter interface.

Defines the contract that all bot platform implementations must follow.
Designed for extensibility — add Discord, Zalo, etc. by subclassing.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BotAdapter(ABC):
    """Abstract base class for bot platform adapters."""

    @abstractmethod
    def connect(self, token: str) -> bool:
        """
        Verify bot token and establish connection.

        Args:
            token: Bot API token.

        Returns:
            True if connection successful, False otherwise.
        """
        ...

    @abstractmethod
    def disconnect(self) -> bool:
        """
        Disconnect from the bot platform.

        Returns:
            True if disconnection successful.
        """
        ...

    @abstractmethod
    def send_message(self, chat_id: str, text: str) -> bool:
        """
        Send a text message to a chat/channel.

        Args:
            chat_id: Target chat or channel ID.
            text: Message text to send.

        Returns:
            True if message sent successfully.
        """
        ...

    @abstractmethod
    def set_webhook(self, url: str) -> bool:
        """
        Register webhook URL with the bot platform API.

        Args:
            url: Public HTTPS URL for webhook.

        Returns:
            True if webhook set successfully.
        """
        ...

    @abstractmethod
    def delete_webhook(self) -> bool:
        """
        Remove webhook registration from the bot platform API.

        Returns:
            True if webhook deleted successfully.
        """
        ...

    @abstractmethod
    def get_me(self) -> Optional[Dict[str, Any]]:
        """
        Get bot information to verify token validity.

        Returns:
            Dict with bot info, or None if token is invalid.
        """
        ...

"""
Message parser module.

Parses chat messages in the format:
    [dd/mm/yyyy HH:MM] Username: message content

Supports Vietnamese text with diacritics and messages containing colons.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedMessage:
    """Represents a parsed chat message."""
    date: str
    time: str
    sender: str
    content: str


# Pattern explanation:
# \[(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})\]  — captures date and time inside brackets
# \s+([^:]+):\s*                              — captures sender name (everything before first colon)
# (.*)$                                        — captures message content (rest of line, may contain colons)
MESSAGE_PATTERN = re.compile(
    r'^\[(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})\]\s+([^:]+):\s*(.*)$'
)


class MessageParser:
    """Parses raw chat message lines into structured ParsedMessage objects."""

    def __init__(self):
        self.pattern = MESSAGE_PATTERN

    def parse_line(self, line: str) -> Optional[ParsedMessage]:
        """
        Parse a single line of chat text.

        Args:
            line: Raw text line, e.g. '[17/08/2026 18:16] Mike: hello world'

        Returns:
            ParsedMessage if the line matches the expected format, None otherwise.
        """
        if not line or not line.strip():
            return None

        match = self.pattern.match(line.strip())
        if not match:
            return None

        date, time, sender, content = match.groups()
        return ParsedMessage(
            date=date.strip(),
            time=time.strip(),
            sender=sender.strip(),
            content=content,  # Keep original content spacing for normalizer
        )

    def extract_content(self, line: str) -> Optional[str]:
        """
        Extract only the message content from a line.

        Args:
            line: Raw text line.

        Returns:
            Message content string, or None if the line doesn't match.
        """
        parsed = self.parse_line(line)
        if parsed is None:
            return None
        return parsed.content

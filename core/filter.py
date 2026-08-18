"""
Message filter module.

Combines parser, normalizer and deduplication logic to process
raw chat text and return filtered results with statistics.
"""

from dataclasses import dataclass
from typing import Optional

from .parser import MessageParser
from .normalizer import normalize_whitespace, normalize_for_comparison


@dataclass
class FilterResult:
    """Result of filtering operation with statistics."""
    result_text: str
    input_count: int
    output_count: int
    duplicate_count: int
    invalid_count: int


class MessageFilter:
    """
    Filters chat messages by removing timestamps, usernames,
    normalizing whitespace, and deduplicating content.
    """

    def __init__(
        self,
        remove_timestamp: bool = True,
        remove_sender: bool = True,
        deduplicate: bool = True,
        do_normalize_whitespace: bool = True,
        case_sensitive: bool = True,
    ):
        """
        Initialize filter with processing options.

        Args:
            remove_timestamp: Remove date/time from matched lines.
            remove_sender: Remove sender name from matched lines.
            deduplicate: Remove duplicate messages (keeps first occurrence).
            do_normalize_whitespace: Collapse extra whitespace.
            case_sensitive: If False, treat 'Hello' and 'hello' as duplicates.
        """
        self.remove_timestamp = remove_timestamp
        self.remove_sender = remove_sender
        self.deduplicate = deduplicate
        self.do_normalize_whitespace = do_normalize_whitespace
        self.case_sensitive = case_sensitive
        self.parser = MessageParser()

    def filter_text(self, raw_text: str) -> FilterResult:
        """
        Process raw chat text and return filtered result.

        Args:
            raw_text: Multi-line string of chat messages.

        Returns:
            FilterResult with processed text and statistics.
        """
        if not raw_text or not raw_text.strip():
            return FilterResult(
                result_text='',
                input_count=0,
                output_count=0,
                duplicate_count=0,
                invalid_count=0,
            )

        lines = raw_text.splitlines()
        input_count = len(lines)
        output_lines = []
        seen = set()
        duplicate_count = 0
        invalid_count = 0

        for line in lines:
            # Skip empty lines
            if not line.strip():
                continue

            # Try to parse the line
            parsed = self.parser.parse_line(line)

            if parsed is not None:
                # Successfully parsed — extract content based on options
                content = self._build_output(parsed)
            else:
                # Line doesn't match format — keep as-is and count as invalid
                invalid_count += 1
                content = line.strip()

            # Normalize whitespace if enabled
            if self.do_normalize_whitespace:
                content = normalize_whitespace(content)

            # Deduplicate if enabled
            if self.deduplicate:
                comparison_key = normalize_for_comparison(
                    content, self.case_sensitive
                )
                if comparison_key in seen:
                    duplicate_count += 1
                    continue
                seen.add(comparison_key)

            output_lines.append(content)

        result_text = '\n'.join(output_lines)
        output_count = len(output_lines)

        return FilterResult(
            result_text=result_text,
            input_count=input_count,
            output_count=output_count,
            duplicate_count=duplicate_count,
            invalid_count=invalid_count,
        )

    def _build_output(self, parsed) -> str:
        """
        Build output string from parsed message based on filter options.

        Args:
            parsed: ParsedMessage object.

        Returns:
            Formatted output string.
        """
        parts = []

        if not self.remove_timestamp:
            parts.append(f'[{parsed.date} {parsed.time}]')

        if not self.remove_sender:
            parts.append(f'{parsed.sender}:')

        parts.append(parsed.content)

        return ' '.join(parts)

    def filter_single(self, message: str) -> Optional[str]:
        """
        Filter a single message line. Used by bot webhook handler.

        Args:
            message: Single message string (already extracted from bot update).

        Returns:
            Normalized message or None if empty.
        """
        if not message or not message.strip():
            return None

        content = message.strip()

        if self.do_normalize_whitespace:
            content = normalize_whitespace(content)

        return content if content else None

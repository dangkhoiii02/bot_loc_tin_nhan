"""
Unit tests for core.parser module.
"""

import pytest
from core.parser import MessageParser, ParsedMessage


@pytest.fixture
def parser():
    return MessageParser()


class TestParseLineBasic:
    """Test basic parsing of well-formatted messages."""

    def test_standard_message(self, parser):
        line = '[17/08/2026 18:16] Mike: cuu cái b'
        result = parser.parse_line(line)
        assert result is not None
        assert result.date == '17/08/2026'
        assert result.time == '18:16'
        assert result.sender == 'Mike'
        assert result.content == 'cuu cái b'

    def test_message_with_spaces_in_name(self, parser):
        line = '[17/08/2026 18:18] Boy Bad: sao b'
        result = parser.parse_line(line)
        assert result is not None
        assert result.sender == 'Boy Bad'
        assert result.content == 'sao b'

    def test_message_with_colon_in_content(self, parser):
        line = '[17/08/2026 18:20] Mike: link: https://example.com'
        result = parser.parse_line(line)
        assert result is not None
        assert result.content == 'link: https://example.com'

    def test_message_with_multiple_colons(self, parser):
        line = '[17/08/2026 18:20] Mike: time is 10:30:45'
        result = parser.parse_line(line)
        assert result is not None
        assert result.content == 'time is 10:30:45'


class TestParseLineVietnamese:
    """Test Vietnamese text with diacritics."""

    def test_vietnamese_content(self, parser):
        line = '[17/08/2026 18:16] Khôi: Xin chào các bạn!'
        result = parser.parse_line(line)
        assert result is not None
        assert result.sender == 'Khôi'
        assert result.content == 'Xin chào các bạn!'

    def test_vietnamese_name_and_content(self, parser):
        line = '[17/08/2026 18:16] Nguyễn Văn A: Tôi đang ở Đà Nẵng'
        result = parser.parse_line(line)
        assert result is not None
        assert result.sender == 'Nguyễn Văn A'
        assert result.content == 'Tôi đang ở Đà Nẵng'


class TestParseLineEdgeCases:
    """Test edge cases and invalid formats."""

    def test_empty_string(self, parser):
        assert parser.parse_line('') is None

    def test_whitespace_only(self, parser):
        assert parser.parse_line('   ') is None

    def test_none_input(self, parser):
        assert parser.parse_line(None) is None

    def test_no_timestamp(self, parser):
        assert parser.parse_line('Mike: hello') is None

    def test_incomplete_timestamp(self, parser):
        assert parser.parse_line('[17/08/2026] Mike: hello') is None

    def test_empty_content(self, parser):
        line = '[17/08/2026 18:16] Mike: '
        result = parser.parse_line(line)
        assert result is not None
        assert result.content == ''

    def test_leading_trailing_whitespace(self, parser):
        line = '  [17/08/2026 18:16] Mike: hello world  '
        result = parser.parse_line(line)
        assert result is not None
        assert result.sender == 'Mike'
        # strip() is applied before regex, so trailing spaces are removed
        assert result.content == 'hello world'


class TestExtractContent:
    """Test the extract_content convenience method."""

    def test_extract_valid(self, parser):
        line = '[17/08/2026 18:16] Mike: hello'
        assert parser.extract_content(line) == 'hello'

    def test_extract_invalid(self, parser):
        assert parser.extract_content('no format here') is None

    def test_extract_empty(self, parser):
        assert parser.extract_content('') is None

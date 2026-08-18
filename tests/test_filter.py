"""
Unit tests for core.filter module.
"""

import pytest
from core.filter import MessageFilter


@pytest.fixture
def default_filter():
    return MessageFilter()


class TestFilterDuplicates:
    """Test deduplication logic."""

    def test_exact_duplicate(self, default_filter):
        text = (
            '[17/08/2026 18:16] Mike: cuu cái b\n'
            '[17/08/2026 18:18] Boy Bad: sao b\n'
            '[17/08/2026 18:16] Mike: cuu cái b'
        )
        result = default_filter.filter_text(text)
        assert result.output_count == 2
        assert result.duplicate_count == 1
        lines = result.result_text.split('\n')
        assert lines[0] == 'cuu cái b'
        assert lines[1] == 'sao b'

    def test_duplicate_different_timestamp(self, default_filter):
        text = (
            '[17/08/2026 18:16] Mike: hello\n'
            '[17/08/2026 19:00] Mike: hello'
        )
        result = default_filter.filter_text(text)
        assert result.output_count == 1
        assert result.duplicate_count == 1

    def test_duplicate_different_sender(self, default_filter):
        text = (
            '[17/08/2026 18:16] Mike: hello\n'
            '[17/08/2026 18:18] Alice: hello'
        )
        result = default_filter.filter_text(text)
        assert result.output_count == 1
        assert result.duplicate_count == 1

    def test_no_duplicates(self, default_filter):
        text = (
            '[17/08/2026 18:16] Mike: hello\n'
            '[17/08/2026 18:18] Alice: world'
        )
        result = default_filter.filter_text(text)
        assert result.output_count == 2
        assert result.duplicate_count == 0


class TestFilterOrder:
    """Test that original order is preserved."""

    def test_preserves_first_occurrence(self, default_filter):
        text = (
            '[17/08/2026 18:16] Mike: alpha\n'
            '[17/08/2026 18:17] Alice: beta\n'
            '[17/08/2026 18:18] Bob: gamma\n'
            '[17/08/2026 18:19] Mike: alpha\n'
            '[17/08/2026 18:20] Alice: beta'
        )
        result = default_filter.filter_text(text)
        lines = result.result_text.split('\n')
        assert lines == ['alpha', 'beta', 'gamma']
        assert result.duplicate_count == 2


class TestFilterWhitespace:
    """Test whitespace normalization."""

    def test_extra_spaces(self, default_filter):
        text = '[17/08/2026 18:16] Mike: hello    world'
        result = default_filter.filter_text(text)
        assert result.result_text == 'hello world'

    def test_tabs_and_spaces(self, default_filter):
        text = '[17/08/2026 18:16] Mike: hello\t\tworld  test'
        result = default_filter.filter_text(text)
        assert result.result_text == 'hello world test'

    def test_whitespace_duplicate_detection(self, default_filter):
        text = (
            '[17/08/2026 18:16] Mike: hello  world\n'
            '[17/08/2026 18:18] Alice: hello world'
        )
        result = default_filter.filter_text(text)
        assert result.output_count == 1
        assert result.duplicate_count == 1


class TestFilterCaseSensitivity:
    """Test case-sensitive and case-insensitive modes."""

    def test_case_sensitive_by_default(self, default_filter):
        text = (
            '[17/08/2026 18:16] Mike: Hello\n'
            '[17/08/2026 18:18] Alice: hello'
        )
        result = default_filter.filter_text(text)
        assert result.output_count == 2  # Different because case-sensitive

    def test_case_insensitive(self):
        f = MessageFilter(case_sensitive=False)
        text = (
            '[17/08/2026 18:16] Mike: Hello\n'
            '[17/08/2026 18:18] Alice: hello'
        )
        result = f.filter_text(text)
        assert result.output_count == 1
        assert result.duplicate_count == 1


class TestFilterOptions:
    """Test different filter option combinations."""

    def test_keep_timestamp(self):
        f = MessageFilter(remove_timestamp=False, remove_sender=True)
        text = '[17/08/2026 18:16] Mike: hello'
        result = f.filter_text(text)
        assert result.result_text == '[17/08/2026 18:16] hello'

    def test_keep_sender(self):
        f = MessageFilter(remove_timestamp=True, remove_sender=False)
        text = '[17/08/2026 18:16] Mike: hello'
        result = f.filter_text(text)
        assert result.result_text == 'Mike: hello'

    def test_keep_all(self):
        f = MessageFilter(remove_timestamp=False, remove_sender=False)
        text = '[17/08/2026 18:16] Mike: hello'
        result = f.filter_text(text)
        assert result.result_text == '[17/08/2026 18:16] Mike: hello'

    def test_no_dedup(self):
        f = MessageFilter(deduplicate=False)
        text = (
            '[17/08/2026 18:16] Mike: hello\n'
            '[17/08/2026 18:18] Alice: hello'
        )
        result = f.filter_text(text)
        assert result.output_count == 2
        assert result.duplicate_count == 0


class TestFilterEdgeCases:
    """Test edge cases."""

    def test_empty_input(self, default_filter):
        result = default_filter.filter_text('')
        assert result.input_count == 0
        assert result.output_count == 0

    def test_whitespace_only(self, default_filter):
        result = default_filter.filter_text('   \n  \n  ')
        assert result.output_count == 0

    def test_none_input(self, default_filter):
        result = default_filter.filter_text(None)
        assert result.input_count == 0

    def test_invalid_format_lines(self, default_filter):
        text = 'this is not a chat message'
        result = default_filter.filter_text(text)
        assert result.output_count == 1
        assert result.invalid_count == 1
        assert result.result_text == 'this is not a chat message'

    def test_mixed_valid_invalid(self, default_filter):
        text = (
            '[17/08/2026 18:16] Mike: hello\n'
            'invalid line\n'
            '[17/08/2026 18:18] Alice: world'
        )
        result = default_filter.filter_text(text)
        assert result.output_count == 3
        assert result.invalid_count == 1

    def test_empty_lines_skipped(self, default_filter):
        text = (
            '[17/08/2026 18:16] Mike: hello\n'
            '\n'
            '\n'
            '[17/08/2026 18:18] Alice: world'
        )
        result = default_filter.filter_text(text)
        assert result.output_count == 2

    def test_many_duplicates(self, default_filter):
        lines = ['[17/08/2026 18:16] Mike: same message'] * 100
        text = '\n'.join(lines)
        result = default_filter.filter_text(text)
        assert result.output_count == 1
        assert result.duplicate_count == 99

    def test_vietnamese_content(self, default_filter):
        text = (
            '[17/08/2026 18:16] Khôi: Xin chào\n'
            '[17/08/2026 18:17] Mai: Tạm biệt\n'
            '[17/08/2026 18:18] Khôi: Xin chào'
        )
        result = default_filter.filter_text(text)
        assert result.output_count == 2
        assert result.duplicate_count == 1
        assert 'Xin chào' in result.result_text
        assert 'Tạm biệt' in result.result_text


class TestFilterSingle:
    """Test single message filtering (used by bot webhook)."""

    def test_normal_message(self, default_filter):
        assert default_filter.filter_single('hello world') == 'hello world'

    def test_whitespace_normalization(self, default_filter):
        assert default_filter.filter_single('hello   world') == 'hello world'

    def test_empty_message(self, default_filter):
        assert default_filter.filter_single('') is None
        assert default_filter.filter_single('   ') is None
        assert default_filter.filter_single(None) is None

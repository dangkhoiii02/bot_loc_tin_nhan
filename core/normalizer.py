"""
Text normalizer module.

Handles whitespace normalization and text comparison preparation.
"""


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace in text by collapsing multiple spaces/tabs into single spaces
    and stripping leading/trailing whitespace.

    Args:
        text: Raw text string.

    Returns:
        Text with normalized whitespace.
    """
    return ' '.join(text.split())


def normalize_for_comparison(text: str, case_sensitive: bool = True) -> str:
    """
    Normalize text for duplicate comparison.

    Applies whitespace normalization and optionally case folding.

    Args:
        text: Raw text string.
        case_sensitive: If False, converts text to lowercase for comparison.

    Returns:
        Normalized text string suitable for comparison.
    """
    normalized = normalize_whitespace(text)
    if not case_sensitive:
        normalized = normalized.lower()
    return normalized

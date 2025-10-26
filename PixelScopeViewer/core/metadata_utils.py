"""Utilities for processing image metadata and EXIF data.

This module provides helper functions for handling metadata extraction,
text encoding detection, and binary data filtering.
"""


def is_binary_tag(tag: str) -> bool:
    """Check if a tag contains binary data that should be skipped.

    Args:
        tag: EXIF tag name

    Returns:
        True if tag should be skipped (binary/thumbnail data)
    """
    skip_keywords = ["thumbnail", "makernote", "printim"]
    return any(keyword in tag.lower() for keyword in skip_keywords) or tag.startswith("Info.")


def is_printable_text(text: str, min_ratio: float = 0.7) -> bool:
    """Check if text is mostly printable characters.

    Args:
        text: Text to check
        min_ratio: Minimum ratio of printable characters (0.0-1.0)

    Returns:
        True if text has enough printable characters
    """
    if not text:
        return False
    printable_count = sum(1 for c in text if c.isprintable() or c in "\r\n\t")
    return printable_count / len(text) >= min_ratio


def decode_bytes(data: bytes) -> str:
    """Attempt to decode bytes using multiple encodings.

    Args:
        data: Bytes to decode

    Returns:
        Decoded string, or empty string if all attempts fail
    """
    for encoding in ["utf-8", "shift-jis", "cp932", "latin-1"]:
        try:
            decoded = data.decode(encoding)
            if is_printable_text(decoded):
                return decoded
        except (UnicodeDecodeError, LookupError):
            continue
    return ""

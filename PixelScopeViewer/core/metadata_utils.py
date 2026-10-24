"""Utilities for processing image metadata and EXIF data.

This module provides helper functions for handling metadata extraction,
text encoding detection, and binary data filtering.
"""

import struct
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import exifread
import png


def is_binary_tag(tag: str) -> bool:
    """Check if a tag contains binary data that should be skipped.

    Args:
        tag: EXIF tag name

    Returns:
        True if tag should be skipped (binary/thumbnail data)
    """
    skip_keywords = ["thumbnail", "makernote", "printim"]
    return any(keyword in tag.lower() for keyword in skip_keywords) or tag.startswith(
        "Info."
    )


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


def extract_exif(path: str | Path) -> dict:
    """Extract EXIF metadata
    Args:
        path: Path to the file

    Returns:
        Dictionary containing metadata
    """
    metadata = {}
    with open(path, "rb") as f:
        # Suppress exifread's debug messages
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            tags = exifread.process_file(f, details=False)

        for tag, value in tags.items():
            # Skip binary/thumbnail data
            if is_binary_tag(tag):
                continue

            try:
                value_str = str(value)

                # Handle byte data with multiple encoding attempts
                if isinstance(value.values, bytes):
                    # Skip large binary data
                    if len(value.values) > 1000:
                        continue

                    # Try decoding with multiple encodings
                    decoded = decode_bytes(value.values)
                    if not decoded:
                        continue
                    value_str = decoded

                # Skip fields with excessive control characters
                if not is_printable_text(value_str, min_ratio=0.8):
                    continue

                # Store with cleaned tag name
                clean_tag = tag.replace(" ", "_")
                metadata[clean_tag] = value_str

            except Exception as e:
                print(f"Error: {e}")
                continue
    return metadata


def extract_png_metadata(path: str | Path) -> dict:
    """Extract metadata from a PNG file.

    Args:
        path: Path to the PNG file

    Returns:
        Dictionary containing metadata
    """
    metadata = {}
    reader = png.Reader(filename=str(path))
    chunk_types = set()

    for ctype, data in reader.chunks():
        chunk_types.add(ctype.decode("ascii"))

        # chunk : Header
        if ctype == b"IHDR":
            width, height, bitdepth, colortype, comp, filt, interlace = struct.unpack(
                ">IIBBBBB", data
            )
            metadata["IHDR width"] = width
            metadata["IHDR height"] = height
            metadata["IHDR bitdepth"] = bitdepth
            metadata["IHDR color type"] = colortype
            metadata["IHDR compression"] = comp
            metadata["IHDR filter"] = filt
            metadata["IHDR interlace"] = interlace

        # chunk : Physical pixel resolution
        elif ctype == b"pHYs":
            xppm, yppm, unit = struct.unpack(">IIB", data)
            metadata["pHYs xppm"] = xppm
            metadata["pHYs yppm"] = yppm
            metadata["pHYs unit"] = "meter" if unit == 1 else "unknown"

        # chunk : gamma
        elif ctype == b"gAMA":
            gamma = struct.unpack(">I", data)[0] / 100000
            metadata["gAMA gamma"] = gamma

        # chunk : Color space
        elif ctype == b"sRGB":
            intent = data[0]
            metadata["sRGB rendering intent"] = intent

        # chunk : Image data, eof tag
        elif ctype == b"IDAT" or ctype == b"IEND":
            pass

        # chunk : Text
        elif ctype == b"tEXt":
            key, value = data.split(b"\x00", 1)
            metadata[key.decode()] = value.decode(errors="ignore")

        # chunk : Text (unicode)
        elif ctype == b"iTXt":
            parts = data.split(b"\x00", 5)
            key = parts[0].decode()
            value = parts[-1].decode(errors="ignore")
            metadata[key] = value

        # chunk : unknown
        else:
            print(f"unknown: {ctype}, data_len: {len(data)}")

    metadata["chunk_types"] = sorted(chunk_types)

    return metadata

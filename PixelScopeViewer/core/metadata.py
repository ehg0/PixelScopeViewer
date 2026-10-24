"""画像 metadata（EXIF, PNG chunk）の抽出処理。"""

import struct
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import exifread
import png


def is_binary_tag(tag: str) -> bool:
    """thumbnail などの binary データを持つ EXIF tag かを判定する。"""
    skip_keywords = ["thumbnail", "makernote", "printim"]
    return any(keyword in tag.lower() for keyword in skip_keywords) or tag.startswith("Info.")


def is_printable_text(text: str, min_ratio: float = 0.7) -> bool:
    """表示可能な文字の割合が min_ratio 以上かを判定する。"""
    if not text:
        return False
    printable_count = sum(1 for c in text if c.isprintable() or c in "\r\n\t")
    return printable_count / len(text) >= min_ratio


def decode_bytes(data: bytes) -> str:
    """複数の encoding を試して bytes を decode する。失敗時は空文字を返す。"""
    for encoding in ["utf-8", "shift-jis", "cp932", "latin-1"]:
        try:
            decoded = data.decode(encoding)
            if is_printable_text(decoded):
                return decoded
        except (UnicodeDecodeError, LookupError):
            continue
    return ""


def extract_exif(path: str | Path) -> dict:
    """EXIF metadata を抽出する。

    Returns:
        tag 名の空白を "_" に置換した key と値文字列の dict。
    """
    metadata = {}
    with open(path, "rb") as f:
        # exifread の debug 出力を抑制する
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            tags = exifread.process_file(f, details=False)

        for tag, value in tags.items():
            if is_binary_tag(tag):
                continue

            try:
                value_str = str(value)

                if isinstance(value.values, bytes):
                    # 大きな binary データは除外する
                    if len(value.values) > 1000:
                        continue

                    decoded = decode_bytes(value.values)
                    if not decoded:
                        continue
                    value_str = decoded

                # 制御文字が多い値は除外する
                if not is_printable_text(value_str, min_ratio=0.8):
                    continue

                clean_tag = tag.replace(" ", "_")
                metadata[clean_tag] = value_str

            except Exception as e:  # tag の値の形式は file ごとに様々なため、読めない tag は飛ばす
                print(f"Error: {e}")
                continue
    return metadata


def extract_png_metadata(path: str | Path) -> dict:
    """PNG の chunk から metadata を抽出する。"""
    metadata = {}
    reader = png.Reader(filename=str(path))
    chunk_types = set()

    for ctype, data in reader.chunks():
        chunk_types.add(ctype.decode("ascii"))

        # header
        if ctype == b"IHDR":
            width, height, bitdepth, colortype, comp, filt, interlace = struct.unpack(">IIBBBBB", data)
            metadata["IHDR width"] = width
            metadata["IHDR height"] = height
            metadata["IHDR bitdepth"] = bitdepth
            metadata["IHDR color type"] = colortype
            metadata["IHDR compression"] = comp
            metadata["IHDR filter"] = filt
            metadata["IHDR interlace"] = interlace

        # 物理 pixel 解像度
        elif ctype == b"pHYs":
            xppm, yppm, unit = struct.unpack(">IIB", data)
            metadata["pHYs xppm"] = xppm
            metadata["pHYs yppm"] = yppm
            metadata["pHYs unit"] = "meter" if unit == 1 else "unknown"

        elif ctype == b"gAMA":
            gamma = struct.unpack(">I", data)[0] / 100000
            metadata["gAMA gamma"] = gamma

        # color space
        elif ctype == b"sRGB":
            intent = data[0]
            metadata["sRGB rendering intent"] = intent

        # 画像データと終端
        elif ctype == b"IDAT" or ctype == b"IEND":
            pass

        elif ctype == b"tEXt":
            key, value = data.split(b"\x00", 1)
            metadata[key.decode()] = value.decode(errors="ignore")

        # Unicode text
        elif ctype == b"iTXt":
            parts = data.split(b"\x00", 5)
            key = parts[0].decode()
            value = parts[-1].decode(errors="ignore")
            metadata[key] = value

        else:
            print(f"unknown: {ctype}, data_len: {len(data)}")

    metadata["chunk_types"] = sorted(chunk_types)

    return metadata

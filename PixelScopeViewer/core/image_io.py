"""画像の読み込み・変換・metadata 取得。"""

import struct
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np
import OpenImageIO as oiio

from PixelScopeViewer.core.constants import OIIO_EXTENSIONS, OPENCV_EXTENSIONS, STANDARD_IMAGE_EXTENSIONS
from PixelScopeViewer.core.metadata import extract_exif, extract_png_metadata


class ImageLoaderRegistry:
    """custom image loader を管理する singleton の registry。"""

    _instance = None

    @classmethod
    def get_instance(cls) -> "ImageLoaderRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.custom_loaders = []

    def register(
        self,
        loader_func: Callable[[str], np.ndarray | None],
        extensions: list[str] | None = None,
        priority: int = 0,
    ):
        """custom image loader を登録する。

        Args:
            loader_func: ファイルパスを受け取り画像配列を返す関数。対応できない場合は None を返す。
            extensions: 対象の拡張子（例: [".dat"]）。None または ["*"] で全拡張子を対象にする。
            priority: 優先度。標準 loader は 0。正の値は標準 loader より先、負の値は全 loader 失敗後に試す。
        """
        if extensions is None:
            extensions = ["*"]

        is_wildcard = "*" in extensions

        self.custom_loaders.append(
            {
                "func": loader_func,
                "extensions": [e.lower() for e in extensions] if not is_wildcard else ["*"],
                "priority": priority,
                "is_wildcard": is_wildcard,
            }
        )

        # 優先度の高い順に並べる
        self.custom_loaders.sort(key=lambda x: x["priority"], reverse=True)

    def get_supported_extensions(self) -> tuple[list[str], bool]:
        """custom loader が対応する拡張子を返す。

        Returns:
            拡張子のリストと、wildcard loader が登録されているかの tuple。
        """
        exts = set()
        has_wildcard = False

        for loader_info in self.custom_loaders:
            if loader_info["is_wildcard"]:
                has_wildcard = True
            else:
                exts.update(loader_info["extensions"])

        return sorted(exts), has_wildcard


def cv2_imread_unicode(path: str):
    """日本語を含むパスでも読めるよう、cv2.imdecode で画像を読み込む。"""
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_UNCHANGED)


def read_bin(filename: Path, has_header: bool = True) -> np.ndarray:
    """16bit little-endian の binary ファイルを読み込む。

    Args:
        filename: 読み込むファイルパス。
        has_header: 先頭 4byte に (width, height) の header があるか。

    Returns:
        uint16 の画像配列。header がない場合は 1 次元配列。
    """
    with open(filename, "rb") as f:
        if has_header:
            header = f.read(4)
            width, height = struct.unpack("<HH", header)
            data = np.frombuffer(f.read(), dtype="<u2")
            img = data.reshape((height, width))
        else:
            data = np.frombuffer(f.read(), dtype="<u2")
            img = data
    return img


def load_image(path: str | Path) -> np.ndarray:
    """画像ファイルを読み込む。

    custom loader は priority > 0 → 標準 loader → priority == 0 → priority < 0 の順に試す。
    EXR/HDR は OpenImageIO で元の dtype のまま、npy/bin はそのまま、
    その他は OpenCV で読み込み RGB/RGBA に変換して返す。

    Raises:
        RuntimeError: 画像を開けない、または対応する loader がない場合。
    """
    path_str = str(path)
    ext = Path(path_str).suffix.lower()

    registry = ImageLoaderRegistry.get_instance()

    result = _try_custom_loaders(registry, path_str, ext, lambda p: p > 0)
    if result is not None:
        return result

    if ext in OIIO_EXTENSIONS:
        img = oiio.ImageInput.open(path_str)
        arr = img.read_image()
        img.close()
        return arr
    elif ext == ".npy":
        return np.load(path)
    elif ext == ".bin":
        return read_bin(path)
    elif ext in OPENCV_EXTENSIONS:
        img = cv2_imread_unicode(path_str)
        if img is None:
            raise RuntimeError(f"Cannot open image: {path_str}")

        # OpenCV の BGR(A) を RGB(A) に変換する
        if img.ndim == 3 and img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
        elif img.ndim == 3 and img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return img

    for accept in (lambda p: p == 0, lambda p: p < 0):
        result = _try_custom_loaders(registry, path_str, ext, accept)
        if result is not None:
            return result

    raise RuntimeError(f"Cannot open image: {path_str} (unsupported format)")


def _try_custom_loaders(
    registry: ImageLoaderRegistry, path_str: str, ext: str, accept_priority: Callable[[int], bool]
) -> np.ndarray | None:
    """priority が accept_priority を満たす custom loader を順に試し、最初に成功した結果を返す。"""
    for loader_info in registry.custom_loaders:
        if not accept_priority(loader_info["priority"]):
            continue
        if loader_info["is_wildcard"] or ext in loader_info["extensions"]:
            try:
                result = loader_info["func"](path_str)
                if result is not None:
                    return result
            except Exception as e:
                print(f"Error: {e}")
    return None


def is_image_file(path: str | Path) -> bool:
    """拡張子から読み込み可能な画像ファイルかを判定する（custom loader の拡張子を含む）。"""
    ext = Path(path).suffix.lower()
    if ext in STANDARD_IMAGE_EXTENSIONS:
        return True

    registry = ImageLoaderRegistry.get_instance()
    custom_exts, has_wildcard = registry.get_supported_extensions()

    if has_wildcard:
        return True

    return ext in custom_exts


def format_file_size(size: int, sep: str = " ") -> str:
    """byte 数を B / KB / MB / GB の表記にする。sep は数値と単位の間の文字列。"""
    if size < 1024:
        return f"{size}{sep}B"
    if size < 1024**2:
        return f"{size / 1024:.1f}{sep}KB"
    if size < 1024**3:
        return f"{size / 1024**2:.1f}{sep}MB"
    return f"{size / 1024**3:.2f}{sep}GB"


def get_image_metadata(path: str | Path, arr: np.ndarray = None) -> dict:
    """画像の metadata を取得する。

    Args:
        path: 画像ファイルのパス。
        arr: 読み込み済みの画像配列。EXR 以外で size や dtype の取得に使う。

    Returns:
        Filepath, FileSize, Format, Size, Channels, DataType などに加え、
        EXIF と PNG chunk の情報を含む dict。
    """
    metadata = {}

    if path:
        path_obj = Path(path)

        try:
            metadata["Filepath"] = str(path_obj.resolve())
            metadata["FileSize"] = format_file_size(path_obj.stat().st_size)
        except Exception:
            pass

        ext = path_obj.suffix.lower()
        if ext == ".exr":
            try:
                img = oiio.ImageInput.open(str(path_obj))
                spec = img.spec()
                metadata["Format"] = "EXR"
                metadata["Size"] = f"{spec.width} x {spec.height}"
                metadata["Channels"] = spec.nchannels
                metadata["DataType"] = str(spec.format).split()[-1]
                if spec.get_string_attribute("compression"):
                    metadata["Compression"] = spec.get_string_attribute("compression")
                if spec.get_string_attribute("Software"):
                    metadata["Software"] = spec.get_string_attribute("Software")
                img.close()
            except Exception as e:
                metadata["Error"] = str(e)
        else:
            try:
                h, w = arr.shape[:2]
                metadata["Format"] = Path(path).suffix.lstrip(".").upper() or "Unknown"
                metadata["Size"] = f"{w} x {h}"
                metadata["DataType"] = str(arr.dtype)

                if arr.ndim == 2:
                    metadata["Channels"] = 1
                    metadata["Mode"] = "GRAY"
                else:
                    channels = arr.shape[2]
                    metadata["Channels"] = channels
                    if channels == 3:
                        metadata["Mode"] = "RGB"
                    elif channels == 4:
                        metadata["Mode"] = "RGBA"
                    else:
                        metadata["Mode"] = f"{channels}-channel"
            except Exception as e:
                metadata["Error (OpenCV)"] = str(e)

            try:
                exif_metadata = extract_exif(path_obj)
                for k, v in exif_metadata.items():
                    metadata[k] = v
            except Exception as e:
                metadata["Error (EXIF)"] = str(e)

            if ext == ".png":
                try:
                    png_metadata = extract_png_metadata(path_obj)
                    for k, v in png_metadata.items():
                        metadata[k] = v
                except Exception as e:
                    metadata["Error (PNG chunks)"] = str(e)

    return metadata

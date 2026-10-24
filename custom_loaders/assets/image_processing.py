from typing import Literal

import numpy as np
from scipy.interpolate import RectBivariateSpline


def _split_channels(img: np.array, cfa: str = "rggb") -> dict:
    """
    return dict[ch_name, img]
    """
    if cfa.lower() == "grbg":
        return {
            "all": img,
            "gr": img[0::2, 0::2],
            "r": img[0::2, 1::2],
            "b": img[1::2, 0::2],
            "gb": img[1::2, 1::2],
        }
    elif cfa.lower() == "gbrg":
        return {
            "all": img,
            "gb": img[0::2, 0::2],
            "b": img[0::2, 1::2],
            "r": img[1::2, 0::2],
            "gr": img[1::2, 1::2],
        }
    elif cfa.lower() == "bggr":
        return {
            "all": img,
            "b": img[0::2, 0::2],
            "gb": img[0::2, 1::2],
            "gr": img[1::2, 0::2],
            "r": img[1::2, 1::2],
        }
    else:  # rggb
        return {
            "all": img,
            "r": img[0::2, 0::2],
            "gr": img[0::2, 1::2],
            "gb": img[1::2, 0::2],
            "b": img[1::2, 1::2],
        }


def _merge_channels(
    img_r: np.array, img_gr: np.array, img_gb: np.array, img_b: np.array, cfa: str = "rggb"
) -> np.ndarray:
    h, w = img_r.shape
    img = np.zeros((h * 2, w * 2)).astype(img_r.dtype)
    if cfa.lower() == "rggb":
        img[0::2, 0::2] = img_r
        img[0::2, 1::2] = img_gr
        img[1::2, 0::2] = img_gb
        img[1::2, 1::2] = img_b
    elif cfa.lower() == "grbg":
        img[0::2, 0::2] = img_gr
        img[0::2, 1::2] = img_r
        img[1::2, 0::2] = img_b
        img[1::2, 1::2] = img_gb
    elif cfa.lower() == "gbrg":
        img[0::2, 0::2] = img_gb
        img[0::2, 1::2] = img_b
        img[1::2, 0::2] = img_r
        img[1::2, 1::2] = img_gr
    elif cfa.lower() == "bggr":
        img[0::2, 0::2] = img_b
        img[0::2, 1::2] = img_gb
        img[1::2, 0::2] = img_gr
        img[1::2, 1::2] = img_r
    return img


def split_channels(
    img: np.ndarray,
    cfa: str | np.ndarray = "rggb",
    full_size: bool = False,
    subpix: bool = False,
    to_array: bool = False,
) -> dict[str, np.ndarray | list[np.ndarray]] | tuple[np.ndarray, list[str]]:
    """RAW画像からCFAパターンに基づいてチャンネルを分離抽出する。

    Args:
        img (np.ndarray): 入力RAW画像。形状は (H, W)。
        cfa (str| np.ndarray, optional): CFAパターン。
            文字列指定（例: "rggb", "grbg"）または2次元配列指定
            （e.g. np.array([['R', 'GR'], ['GB', 'B']])）。
            デフォルトは "rggb"。
        full_size (bool, optional): True の場合、元画像サイズ (H, W) の全域マスク画像を返す。
            False の場合、スライスされた小画像 (H/cfa_h, W/cfa_w) を返す。
            デフォルトは False。
        subpix (bool, optional): full_size=False の時のみ有効。
            True の場合、'r00', 'r01' のようにCFA内の相対位置Suffixを付与して
            すべてのサブピクセルを独立したキーとして抽出する。
            デフォルトは False。
        to_array (bool, optional): True の場合、辞書ではなく (C, H, W) の 3D NumPy 配列と
            チャンネル名リストのタプル (array, channel_names) を返す。
            デフォルトは False。

    Returns:
        dict[str, np.ndarray | list[np.ndarray]]:
            分離されたチャンネル名をキーとし、対応する画像または画像のリストを値に持つ辞書。
            to_array=False の場合は dict (key: channel(小文字), value: 2D画像)
            to_array=True の場合は ((C, H, W) 配列, チャンネル名リスト) のタプル。
    Raises:
        ValueError: 未対応のCFA文字列パターンが指定された場合。
    """
    if isinstance(cfa, str):
        cfa_str = cfa.lower()
        if cfa_str == "rggb":
            cfa_pattern = np.array([["r", "gr"], ["gb", "b"]])
        elif cfa_str == "grbg":
            cfa_pattern = np.array([["gr", "r"], ["b", "gb"]])
        elif cfa_str == "bggr":
            cfa_pattern = np.array([["b", "gb"], ["gr", "r"]])
        elif cfa_str == "gbrg":
            cfa_pattern = np.array([["g", "b"], ["r", "gr"]])
        else:
            raise ValueError(f"未対応のCFA文字列パターンです: {cfa}")
    else:
        cfa_pattern = np.array(cfa)

    cfa_h, cfa_w = cfa_pattern.shape
    h, w = img.shape
    cfa_pattern_lower = np.char.lower(cfa_pattern.astype(str))
    result: dict[str, np.ndarray] = {}

    # 1. full_size=True, subpix=True
    # -> 元画像サイズ (H, W) で、位置Suffix付き (r00, r01...) の全域マスク画像
    if full_size and subpix:
        for y in range(cfa_h):
            for x in range(cfa_w):
                base_key = cfa_pattern_lower[y, x]
                key_name = f"{base_key}{y}{x}"

                mask_img = np.zeros_like(img)
                mask_img[y::cfa_h, x::cfa_w] = img[y::cfa_h, x::cfa_w]
                result[key_name] = mask_img

    # 2. full_size=True, subpix=False
    # -> 元画像サイズ (H, W) で、同名を全域マスク画像として合算集約 (r, g, b)
    elif full_size:
        tile_h = (h + cfa_h - 1) // cfa_h
        tile_w = (w + cfa_w - 1) // cfa_w
        full_cfa = np.tile(cfa_pattern_lower, (tile_h, tile_w))[:h, :w]

        unique_keys = np.unique(full_cfa)
        for key in unique_keys:
            mask = full_cfa == key
            ch_img = np.zeros_like(img)
            ch_img[mask] = img[mask]
            result[key] = ch_img

    # 3. full_size=False, subpix=True
    # -> 縮小スライス画像 (H/cfa_h, W/cfa_w) で、位置Suffix付き (r00, r01...)
    elif subpix:
        for y in range(cfa_h):
            for x in range(cfa_w):
                base_key = cfa_pattern_lower[y, x]
                key_name = f"{base_key}{y}{x}"
                result[key_name] = img[y::cfa_h, x::cfa_w]

    # 4. full_size=False, subpix=False
    # -> 縮小スライス画像 (H/cfa_h, W/cfa_w) で、単純スライス (同名は上書き)
    else:
        for y in range(cfa_h):
            for x in range(cfa_w):
                key_name = cfa_pattern_lower[y, x]
                result[key_name] = img[y::cfa_h, x::cfa_w]

    # to_array=True 時の処理
    if to_array:
        channel_names = list(result.keys())
        stacked_array = np.stack(list(result.values()), axis=0)
        return stacked_array, channel_names

    return result


def merge_channels(
    channels: dict[str, np.ndarray] | np.ndarray,
    channel_names: list[str] | None = None,
    cfa: str | np.ndarray = "rggb",
    full_size: bool = False,
    subpix: bool = False,
) -> np.ndarray:
    """_split_channels で分離されたチャンネルデータから元のRAW画像 (H, W) を再構成・復元する。

    Args:
        channels (dict[str, np.ndarray] | np.ndarray):
            分離されたチャンネルデータ。
            dict の場合は {キー名: 2D配列}、
            np.ndarray の場合は (C, H, W) の 3D 配列。
        channel_names (list[str] | None, optional):
            channels が (C, H, W) 配列の場合に必須となる各チャンネル名のリスト。
            to_array=True の第二戻り値をそのまま渡す。 Defaults to None.
        cfa (str | np.ndarray, optional):
            CFAパターン。_split_channels で使用したものと同じパターンを指定する。
            Defaults to "rggb".
        full_size (bool, optional):
            入力チャンネルが元画像サイズ (H, W) のマスク画像の場合は True、
            縮小スライス画像の場合は False。 Defaults to False.
        subpix (bool, optional):
            subpix=True で分離されたデータ（キー名に位置Suffix 'r00' 等が含まれる）の場合 True。
            Defaults to False.

    Returns:
        np.ndarray: 再構成された RAW 画像。形状は (H, W)。入力配列と同じ dtype を保持する。

    Raises:
        ValueError: 引数の不整合や入力フォーマットエラーがある場合。
        TypeError: channels の型が不適切の場合。
    """
    # 0. CFAパターンの解析
    if isinstance(cfa, str):
        cfa_str = cfa.lower()
        if cfa_str == "rggb":
            cfa_pattern = np.array([["r", "gr"], ["gb", "b"]])
        elif cfa_str == "grbg":
            cfa_pattern = np.array([["gr", "r"], ["b", "gb"]])
        elif cfa_str == "bggr":
            cfa_pattern = np.array([["b", "gb"], ["gr", "r"]])
        elif cfa_str == "gbrg":
            cfa_pattern = np.array([["g", "b"], ["r", "gr"]])
        else:
            raise ValueError(f"未対応のCFA文字列パターンです: {cfa}")
    else:
        cfa_pattern = np.array(cfa)

    cfa_h, cfa_w = cfa_pattern.shape
    cfa_pattern_lower = np.char.lower(cfa_pattern.astype(str))

    # 1. 入力形式 (dict か (C, H, W) 配列か) の正規化 -> ch_dict に統一
    if isinstance(channels, np.ndarray):
        if channels.ndim != 3:
            raise ValueError(f"配列指定の場合、(C, H, W) の 3D 配列である必要があります。(入力次元: {channels.ndim})")
        if channel_names is None or len(channel_names) != channels.shape[0]:
            raise ValueError("channels が 3D 配列の場合、チャンネル数と一致する channel_names が必要です。")

        ch_dict = {name: channels[i] for i, name in enumerate(channel_names)}
    elif isinstance(channels, dict):
        ch_dict = channels
    else:
        raise TypeError("channels は dict または (C, H, W) の np.ndarray である必要があります。")

    # 2. 入力データの dtype と形状の取得
    first_img = next(iter(ch_dict.values()))
    target_dtype = first_img.dtype

    # 3. 再構成処理 (full_size の有無で分岐)
    # A. full_size=True (全域マスク画像からの復元)
    if full_size:
        h, w = first_img.shape
        raw_img = np.zeros((h, w), dtype=target_dtype)

        # マスク画像を単純加算（各画素で排他的に値が存在するため np.bitwise_or や + でOK）
        for img in ch_dict.values():
            raw_img |= img if np.issubdtype(target_dtype, np.integer) else raw_img + img

        return raw_img

    # B. full_size=False (縮小スライス画像からの復元)
    else:
        sub_h, sub_w = first_img.shape
        h, w = sub_h * cfa_h, sub_w * cfa_w
        raw_img = np.zeros((h, w), dtype=target_dtype)

        for y in range(cfa_h):
            for x in range(cfa_w):
                base_key = cfa_pattern_lower[y, x]
                key_name = f"{base_key}{y}{x}" if subpix else base_key

                if key_name in ch_dict:
                    raw_img[y::cfa_h, x::cfa_w] = ch_dict[key_name]

        return raw_img


def rggb_tiling(img: np.array, cfa: str = "rggb") -> np.ndarray:
    if img.ndim == 2:
        h, w = img.shape
        img_dict = _split_channels(img, cfa=cfa)
        o_img = np.zeros_like(img)
        h_half = h // 2
        w_half = w // 2

        o_img[0:h_half, 0:w_half] = img_dict["r"]
        o_img[h_half:h, 0:w_half] = img_dict["gr"]
        o_img[0:h_half, w_half:w] = img_dict["gb"]
        o_img[h_half:h, w_half:w] = img_dict["b"]
        return o_img
    else:
        return None


def _calc_r_mod(cfa="rggb"):
    if cfa.lower() == "grbg":
        return 0, 1
    elif cfa.lower() == "gbrg":
        return 1, 0
    elif cfa.lower() == "bggr":
        return 1, 1
    else:  # rggb
        return 0, 0


def black(img: np.ndarray, black_level: float | np.ndarray) -> np.ndarray:
    return img - black_level


def demosic(img: np.array, cfa: str = "rggb", is_debug: bool = True) -> dict:
    if img.ndim == 2:
        height, width = img.shape
        img = img.astype(np.float32, copy=False)
        offset = 1

        img_r = np.zeros((height, width))
        img_g = np.zeros((height, width))
        img_b = np.zeros((height, width))
        img_dir = np.zeros((height, width)) + 128
        img_dir_allpix = np.zeros((height, width)) if is_debug else None

        r_mod_y, r_mod_x = _calc_r_mod(cfa)
        for y in range(offset, height - offset):
            for x in range(offset, width - offset):
                if x % 2 == r_mod_x and y % 2 == r_mod_y:
                    # B  G  B
                    # G [R] G
                    # B  G  B
                    img_r[y, x] = img[y, x]

                    dirirection = _detect_direction(img, (x, y))
                    img_dir[y, x] = dirirection["val"]
                    if dirirection["dir"] == "h":
                        img_g[y, x] = (img[y - 1, x] + img[y + 1, x]) / 2
                    elif dirirection["dir"] == "v":
                        img_g[y, x] = (img[y, x - 1] + img[y, x + 1]) / 2
                    else:
                        img_g[y, x] = (img[y, x - 1] + img[y, x + 1] + img[y - 1, x] + img[y + 1, x]) / 4

                    img_b[y, x] = (img[y - 1, x - 1] + img[y - 1, x + 1] + img[y + 1, x - 1] + img[y + 1, x + 1]) / 4

                elif x % 2 != r_mod_x and y % 2 == r_mod_y:
                    # G  B  G
                    # R [G] R
                    # G  B  G
                    img_r[y, x] = (img[y, x - 1] + img[y, x + 1]) / 2
                    img_g[y, x] = img[y, x]
                    img_b[y, x] = (img[y - 1, x] + img[y + 1, x]) / 2

                elif x % 2 == r_mod_x and y % 2 != r_mod_y:
                    # G  R  G
                    # B [G] B
                    # G  R  G
                    img_r[y, x] = (img[y - 1, x] + img[y + 1, x]) / 2
                    img_g[y, x] = img[y, x]
                    img_b[y, x] = (img[y, x - 1] + img[y, x + 1]) / 2

                else:
                    # R  G  R
                    # G [B] G
                    # R  G  R
                    img_r[y, x] = (img[y - 1, x - 1] + img[y - 1, x + 1] + img[y + 1, x - 1] + img[y + 1, x + 1]) / 4

                    dirirection = _detect_direction(img, (x, y))
                    img_dir[y, x] = dirirection["val"]
                    if dirirection["dir"] == "h":
                        img_g[y, x] = (img[y - 1, x] + img[y + 1, x]) / 2
                    elif dirirection["dir"] == "v":
                        img_g[y, x] = (img[y, x - 1] + img[y, x + 1]) / 2
                    else:
                        img_g[y, x] = (img[y, x - 1] + img[y, x + 1] + img[y - 1, x] + img[y + 1, x]) / 4

                    img_b[y, x] = img[y, x]

                if is_debug:
                    img_dir_allpix[y, x] = _detect_direction(img, (x, y))["val"]
        return np.stack([img_r, img_g, img_b], axis=2), img_dir, img_dir_allpix

    else:
        return img, None, None


def _detect_direction(img: np.array, addr: tuple[int, int]) -> float:
    # dir_result
    # h : 0
    # na : 127
    # v : 255
    x, y = addr
    dir_result = {"dir": "na", "val": 127}
    dir_th = 0.5

    dir_h = np.abs(img[y, x - 1] - img[y, x + 1])
    dir_v = np.abs(img[y - 1, x] - img[y + 1, x])

    if dir_h <= dir_th and dir_v <= dir_th:
        dir_result = {"dir": "na", "val": 127}
    elif dir_h > dir_v:
        dir_result = {"dir": "h", "val": 0}
    elif dir_h < dir_v:
        dir_result = {"dir": "v", "val": 255}
    elif dir_h == dir_v:
        dir_result = {"dir": "na", "val": 127}
    return dir_result


def wb(img: np.ndarray, wb_gain: np.ndarray = None, roi: list | np.ndarray = None, cfa: str = "rggb") -> np.ndarray:
    """
    ホワイトバランス補正
    Args:
        img (ndarray): 入力画像（Bayer画像 or RGB 3ch）
        wb_gain (ndarray): ホワイトバランスゲイン。Noneの場合、自動計算。
        roi (ndarray, list): wb_gain計算時のROI設定。配列長4で、(cx, cy, w, h)の順。入力画サイズベース。Noneだと画像全体から算出。
        cfa (str): カラーフィルタ配列

    Returns:
        img (ndarray): ホワイトバランス補正後の画像（float32）
        wb_gain (ndarray): シェーディング補正 ゲインマップ（float）
    """
    if img.ndim == 2:
        img_dict = _split_channels(img.astype(np.float32), cfa=cfa)
        if wb_gain is None:
            _img_r = img_dict["r"]
            _img_g = (img_dict["gr"] + img_dict["gb"]) / 2
            _img_b = img_dict["b"]

            roi_half = np.asarray(roi) // 2
            wb_gain = _calc_wb_gain(_img_r, _img_g, _img_b, roi_half)

        img_r = wb_gain[0] * img_dict["r"]
        img_gr = wb_gain[1] * img_dict["gr"]
        img_gb = wb_gain[1] * img_dict["gb"]
        img_b = wb_gain[2] * img_dict["b"]
        return _merge_channels(img_r, img_gr, img_gb, img_b, cfa=cfa), wb_gain

    elif img.ndim == 3:
        if wb_gain is None:
            img = img.astype(np.float32, copy=False)
            _img_r = img[:, :, 0]
            _img_g = img[:, :, 1]
            _img_b = img[:, :, 2]

            wb_gain = _calc_wb_gain(_img_r, _img_g, _img_b, roi)

        img_r = wb_gain[0] * img[:, :, 0]
        img_g = wb_gain[1] * img[:, :, 1]
        img_b = wb_gain[2] * img[:, :, 2]
        return np.stack([img_r, img_g, img_b], axis=2), wb_gain
    else:
        # 4ch以上の入力の時の取り扱いは必要になったら追加
        return None


def _calc_wb_gain(img_r: np.ndarray, img_g: np.ndarray, img_b: np.ndarray, roi: list | np.ndarray = None) -> np.ndarray:
    wb_gain = np.ones(3)
    if roi is None:
        r_mean = np.mean(img_r)
        g_mean = np.mean(img_g)
        b_mean = np.mean(img_b)
    else:
        r_mean = _calc_roi_mean(img_r, roi)
        g_mean = _calc_roi_mean(img_g, roi)
        b_mean = _calc_roi_mean(img_b, roi)

    wb_gain[0] = g_mean / r_mean
    wb_gain[1] = 1.0
    wb_gain[2] = g_mean / b_mean
    return wb_gain


def _calc_roi_mean(img: np.ndarray, roi: list | np.ndarray) -> np.floating:
    cx, cy, w, h = roi
    h_img, w_img = img.shape[:2]

    # 端面処理
    x1 = max(0, cx - w // 2)
    x2 = min(w_img, cx + w // 2)
    y1 = max(0, cy - h // 2)
    y2 = min(h_img, cy + h // 2)

    roi_mean = np.mean(img[y1:y2, x1:x2])
    return roi_mean


def color_matrix(img: np.array, ccm: np.array) -> np.ndarray:
    img[img < 0] = 0
    img_r = ccm[0, 0] * img[:, :, 0] + ccm[0, 1] * img[:, :, 1] + ccm[0, 2] * img[:, :, 2]  # R
    img_g = ccm[1, 0] * img[:, :, 0] + ccm[1, 1] * img[:, :, 1] + ccm[1, 2] * img[:, :, 2]  # G
    img_b = ccm[2, 0] * img[:, :, 0] + ccm[2, 1] * img[:, :, 1] + ccm[2, 2] * img[:, :, 2]  # B
    return np.stack([img_r, img_g, img_b], axis=2)


def gamma(img: np.array, white_level: float, method: Literal["srgb", "bt709"] = "srgb") -> np.ndarray:
    # normalization
    img = img / white_level
    img[img < 0] = 0
    img[img > 1] = 1

    # gammma correction
    if method == "bt709":
        # BT.709
        alpha = 1.09929683
        beta = 0.01805397
        out_img = np.where(img < beta, 4.5 * img, alpha * (img**0.45) - (alpha - 1))
    elif method == "srgb":
        # sRGB規格（IEC 61966-2-1:1999）
        out_img = np.where(img <= 0.0031308, img * 12.92, 1.055 * (img ** (1.0 / 2.4)) - 0.055)
    return out_img


def calib_lens_shading(
    img: np.array,
    grid_cols: int = 11,
    grid_rows: int = 11,
    win_w: int = 64,
    win_h: int = 64,
    stat_type: str = "median",
    method: str = "spline",
    cfa: str = "rggb",
) -> np.ndarray:
    """代表点（ノット点）サンプリングと関数近似を組み合わせたシェーディング補正関数
    静的なキャリブレーションでのゲインマップ取得用途

    Args:
        img (ndarray): 入力画像（Bayer画像前提, 2次元配列）
        grid_cols (int): 横方向のノット（サンプリング点）の数
        grid_rows (int): 縦方向のノット（サンプリング点）の数
        win_w (int): サンプリング窓（カーネル）の横幅
        win_h (int): サンプリング窓（カーネル）の縦幅
        stat_type (str): ノット輝度の計算方法 ('median' または 'mean')
        method (str): 近似手法 ('spline' [3次B-スプライン] または 'poly4' [4次多項式])

    Returns:
        img_shading (ndarray): シェーディング補正後の画像（float32）
        img_lpf (ndarray): シェーディング成分の画像（float32）
        img_gain (ndarray): シェーディング補正 ゲインマップ（float32）
    """
    img_dict = _split_channels(img.astype(np.float32), cfa=cfa)
    luma = (img_dict["r"] + img_dict["gr"] + img_dict["gb"] + img_dict["b"]) / 4
    # 縦（axis=0）に2倍、横（axis=1）に2倍、各要素を繰り返す
    luma_img = np.repeat(np.repeat(luma, 2, axis=0), 2, axis=1)

    img_lpf = _lpf_from_knots(luma_img, grid_cols, grid_rows, win_w, win_h, stat_type, method)

    img_gain = 1.0 / (img_lpf / np.max(img_lpf))
    img_shading = img.astype(np.float32) * img_gain

    return img_shading, img_lpf, img_gain


def calib_color_shading(
    img: np.array,
    grid_cols: int = 11,
    grid_rows: int = 11,
    win_w: int = 64,
    win_h: int = 64,
    stat_type: str = "median",
    method: str = "spline",
    cfa: str = "rggb",
) -> np.ndarray:
    """代表点（ノット点）サンプリングと関数近似を組み合わせたカラーシェーディング補正関数
    静的なキャリブレーションでのゲインマップ取得用途

    Args:
        img (ndarray): 入力画像（Bayer画像前提, 2次元配列）
        grid_cols (int): 横方向のノット（サンプリング点）の数
        grid_rows (int): 縦方向のノット（サンプリング点）の数
        win_w (int): サンプリング窓（カーネル）の横幅（imgの画サイズベース）
        win_h (int): サンプリング窓（カーネル）の縦幅（imgの画サイズベース）
        stat_type (str): ノット輝度の計算方法 ('median' または 'mean')
        method (str): 近似手法 ('spline' [3次B-スプライン] または 'poly4' [4次多項式])

    Returns:
        img_color_shading (ndarray): カラーシェーディング補正後の画像（float32）
        img_lpf (ndarray): カラーシェーディング成分の画像（float32）
        img_gain (ndarray): カラーシェーディング補正 ゲインマップ（float32）
    """
    img_dict = _split_channels(img.astype(np.float32), cfa=cfa)
    img_g = (img_dict["gr"] + img_dict["gb"]) / 2

    img_lpf_r = _lpf_from_knots(img_dict["r"], grid_cols, grid_rows, win_w // 2, win_h // 2, stat_type, method)
    img_lpf_g = _lpf_from_knots(img_g, grid_cols, grid_rows, win_w // 2, win_h // 2, stat_type, method)
    img_lpf_b = _lpf_from_knots(img_dict["b"], grid_cols, grid_rows, win_w // 2, win_h // 2, stat_type, method)

    peak_x, peak_y = np.unravel_index(np.argmax(img_lpf_g), img_lpf_g.shape)
    img_gain_r = img_lpf_g / img_lpf_r * (img_lpf_r[peak_y, peak_x] / img_lpf_g[peak_y, peak_x])
    img_gain_b = img_lpf_g / img_lpf_b * (img_lpf_b[peak_y, peak_x] / img_lpf_g[peak_y, peak_x])

    img_r = img_dict["r"] * img_gain_r
    img_gr = img_dict["gr"]
    img_gb = img_dict["gb"]
    img_b = img_dict["b"] * img_gain_b

    img_color_shading = _merge_channels(img_r, img_gr, img_gb, img_b, cfa=cfa)
    img_lpf = _merge_channels(img_lpf_r, img_lpf_g, img_lpf_g, img_lpf_b, cfa=cfa)
    img_gain = _merge_channels(img_gain_r, np.ones_like(img_gain_r), np.ones_like(img_gain_r), img_gain_b, cfa=cfa)

    return img_color_shading, img_lpf, img_gain


def _lpf_from_knots(
    img: np.array,
    grid_cols: int = 11,
    grid_rows: int = 11,
    win_w: int = 64,
    win_h: int = 64,
    stat_type: str = "median",
    method: str = "spline",
) -> np.ndarray:

    h, w = img.shape[:2]

    # 1. 各グリッドの中心座標を計算し、スプライン補正の「ノット（結節点）座標」とする
    # 画角の最端部 [0, w-1] を必ず含むようにノットを配置
    x_knots = np.linspace(0, w - 1, grid_cols)
    y_knots = np.linspace(0, h - 1, grid_rows)

    # 各ノット位置における代表輝度値を格納する配列
    z_knots = np.zeros((grid_rows, grid_cols))

    # 2. 各ノットの周辺窓（カーネル）から代表輝度を算出
    for r, y in enumerate(y_knots):
        for c, x in enumerate(x_knots):
            # カーネルの範囲を計算（画像外にはみ出さないようにクリップ）
            y1 = max(0, int(y - win_h // 2))
            y2 = min(h, int(y + win_h // 2 + 1))
            x1 = max(0, int(x - win_w // 2))
            x2 = min(w, int(x + win_w // 2 + 1))

            window_pixels = img[y1:y2, x1:x2]

            # メディアン or 平均 の選択（横長のゴミ対策には 'median' を推奨）
            if stat_type == "median":
                z_knots[r, c] = np.median(window_pixels)
            else:
                z_knots[r, c] = np.mean(window_pixels)

    # 全画素の出力用座標グリッドを用意
    all_x = np.arange(w)
    all_y = np.arange(h)

    # 3. 近似手法の適用
    if method == "spline":
        # --- 3次B-スプライン補正（RectBivariateSpline） ---
        # 引数の kx, ky はB-スプラインの次数。デフォルトで3（3次B-スプライン）
        # ノット数が不足してエラーになるのを防ぐため、設定値に応じて次数を自動調整
        kx = min(3, grid_cols - 1)
        ky = min(3, grid_rows - 1)

        # scipyのRectBivariateSplineは内部で高速な3次B-スプライン（FITPACK）を適用
        # z_knots（各ノットの輝度）を通り、境界で滑らかに繋がる曲線を全画素へ展開
        spline_func = RectBivariateSpline(y_knots, x_knots, z_knots, kx=kx, ky=ky)
        img_lpf = spline_func(all_y, all_x)

    elif method == "poly4":
        # --- 4次多項式近似 ---
        # コサイン4乗則等の光学特性を模擬するため、XとYのそれぞれ独立した4次多項式で全面に広げる
        img_lpf = np.zeros((h, w), dtype=np.float32)

        # 横方向（X）の4次フィッティング（各行共通のXプロファイルをノット点から算出）
        x_profile_knots = np.mean(z_knots, axis=0) if grid_rows > 1 else z_knots
        poly_coef_x = np.polyfit(x_knots, x_profile_knots, 4)
        shading_x = np.polyval(poly_coef_x, all_x)  # 2000要素の1次元配列

        if grid_rows > 1:
            # 2次元拡張時：縦方向（Y）の4次フィッティングも行う
            y_profile_knots = np.mean(z_knots, axis=1)
            poly_coef_y = np.polyfit(y_knots, y_profile_knots, 4)
            shading_y = np.polyval(poly_coef_y, all_y)  # 60要素の1次元配列

            # Yのうねりとxのうねりを合成（2次元画像として展開）
            grid_x, grid_y = np.meshgrid(shading_x, shading_y)
            img_lpf = (grid_x * grid_y) / np.mean(z_knots)
        else:
            # 1次元時：横方向の4次曲線を縦に60回コピーして2次元化
            img_lpf = np.tile(shading_x, (h, 1))

    else:
        raise ValueError("Invalid method. Choose 'spline' or 'poly4'.")

    return img_lpf.astype(np.float32)


def alpha_blend(
    images: list[np.ndarray], expo_ratios: list[float], ths: list[float]
) -> tuple[np.ndarray, list[np.ndarray]]:
    """alpha blendによるHDR合成

    Args:
        images (list[np.ndarray]): 「長蓄->短蓄 (Long -> Short)」に並んだRAW画像のリスト.
        expo_ratios (list[float]): 最長露光画像を 1.0 としたときの各画像の相対露光倍率リスト
        ths (list[float]): alphaブレンド領域の切り替えポイント。
            奇数番目(ths[2k]):   第kの長蓄画像(images[k])が飽和し始め、次の短蓄へブレンドし始める輝度 (例: 0.7)
            偶数番目(ths[2k+1]): 第kの長蓄画像(images[k])が完全飽和し、次の短蓄へ100%切り替わる輝度 (例: 0.9)

    Returns:
        hdr_image (np.ndarray): 最長露光スケールに揃えられた合成後のHDR画像
        map_alphas (list[np.ndarray]): 各画像の合成重み (ウェイトマップ) のリスト
    """
    num_images = len(images)

    # 各画像に割り当てるアルファマップの初期化 (全て 0.0)
    map_alphas = [np.zeros_like(images[0], dtype=np.float32) for _ in range(num_images)]

    # 1.0 の初期ウェイト（残存ウェイト）からスタート
    remaining_weight = np.ones_like(images[0], dtype=np.float32)

    # 隣り合う画像間で順にブレンド率を判定
    for i in range(num_images - 1):
        img_long = images[i]  # Long(長蓄)側の画像で判定
        th_min = ths[2 * i]
        th_max = ths[2 * i + 1]

        # 長蓄画像 (img_long) の飽和度から、次の短蓄へ渡す割合 alpha_short_step (0.0 ~ 1.0) を計算
        alpha_short_step = np.clip((img_long - th_min) / (th_max - th_min), 0.0, 1.0)

        # 現在の長蓄画像 (images[i]) が受け持つアルファを確定
        map_alphas[i] = remaining_weight * (1.0 - alpha_short_step)

        # 次のステップ（さらに短蓄側）へ引き継ぐウェイトを更新
        remaining_weight = remaining_weight * alpha_short_step

    # 最後の画像（最も短蓄）に残ったウェイトをすべて割り当てる
    map_alphas[-1] = remaining_weight

    # 加重合成 (各画像を expo_ratio でスケーリングして足し合わせる)
    hdr_image = np.zeros_like(images[0], dtype=np.float32)
    for i in range(num_images):
        hdr_image += images[i] * expo_ratios[i] * map_alphas[i]

    return hdr_image, map_alphas


def image_processing(img: np.array, img_black: np.array = None) -> dict:
    # parameters
    black_level = 0 if img_black is None else img_black
    white_level = 1023
    # cfa = "bggr"
    cfa = "rggb"
    wb_gain = None  # [1.061, 1.0, 1.590]
    ccm = (
        np.array(
            [
                [1177, -211, 91],
                [-54, 1267, -159],
                [72, -232, 1216],
            ]
        )
        / 1024
    )
    is_ccm = False
    is_gamma = False

    # processing
    img_black = black(img, black_level)
    img_demosic, img_dir, img_dir_allpix = demosic(img_black, cfa)
    img_wb, wb_gain = wb(img_demosic, wb_gain)
    img_ccm = color_matrix(img_wb, ccm) if is_ccm else None

    in_gamma = img_ccm if is_ccm else img_wb
    img_gamma = gamma(in_gamma, white_level) if is_gamma else None

    return {
        "black": img_black,
        "demosic": img_demosic,
        "dir": img_dir,
        "dir_allpix": img_dir_allpix,
        "wb": img_wb,
        "wb_gain": wb_gain,
        "ccm": img_ccm,
        "gamma": img_gamma,
    }


if __name__ == "__main__":
    from pathlib import Path

    img_path = Path(".\\data\\spad_aplha\\shading\\260611_shading_streaking_0300_mean_0.0_x1.0.npy")
    img = np.load(img_path)

    # lnearization
    img = np.clip(img, 0, 254).astype(np.float16)
    img_linear = -np.log(1 - img / 255) * 255
    np.save(img_path.parent / "img_linear.npy", img_linear)

    ## 工場でのキャリブレーションでのゲインマップ取得
    # color shading補正
    img_color_shading, img_lpf, img_gain = calib_color_shading(
        img_linear,
        grid_cols=11,
        grid_rows=11,
        win_w=92,
        win_h=92,
        stat_type="median",
        method="spline",
        cfa="bggr",
    )
    np.save(img_path.parent / "img_color_shading.npy", img_color_shading)
    np.save(img_path.parent / "img_color_shading_lpf.npy", img_lpf)
    np.save(img_path.parent / "img_color_shading_gain.npy", img_gain)

    # shading補正
    img_shading, img_lpf, img_shading_gain = calib_lens_shading(
        img_color_shading,
        grid_cols=11,
        grid_rows=11,
        win_w=92,
        win_h=92,
        stat_type="median",
        method="spline",
        cfa="bggr",
    )
    np.save(img_path.parent / "img_shading.npy", img_shading)
    np.save(img_path.parent / "img_shading_lpf.npy", img_lpf)
    np.save(img_path.parent / "img_shading_gain.npy", img_shading_gain)

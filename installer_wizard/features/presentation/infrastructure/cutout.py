from typing import Optional

import cv2
import numpy as np

MAX_SIDE = 900
BORDER_FLAT_RATIO = 0.82
TOLERANCE = 26
MARGIN_RATIO = 0.04


def _decode(data: bytes) -> Optional[np.ndarray]:
    if not data:
        return None
    try:
        image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    except cv2.error:
        return None
    if image is None or image.ndim < 2 or min(image.shape[:2]) < 2:
        return None
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
    if image.shape[2] == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
    return image[:, :, :4].copy()


def _resize(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    scale = MAX_SIDE / max(height, width)
    if scale >= 1:
        return image
    return cv2.resize(image, (max(2, int(width * scale)), max(2, int(height * scale))), interpolation=cv2.INTER_AREA)


def _encode(image: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("image could not be encoded")
    return buffer.tobytes()


def normalise(data: bytes) -> Optional[bytes]:
    image = _decode(data)
    return None if image is None else _encode(_resize(image))


def _border(image: np.ndarray) -> np.ndarray:
    bgr = image[:, :, :3]
    return np.concatenate([bgr[0], bgr[-1], bgr[:, 0], bgr[:, -1]]).astype(np.int16)


def flat_background(image: np.ndarray) -> Optional[np.ndarray]:
    if image[:, :, 3].min() < 255:
        return None
    border = _border(image)
    colour = np.median(border, axis=0)
    close = np.abs(border - colour).max(axis=1) <= TOLERANCE
    return colour.astype(np.uint8) if close.mean() >= BORDER_FLAT_RATIO else None


def cut_out(data: bytes) -> Optional[bytes]:
    image = _decode(data)
    if image is None:
        return None
    image = _resize(image)
    colour = flat_background(image)
    if colour is None:
        return _encode(image)
    height, width = image.shape[:2]
    bgr = np.ascontiguousarray(image[:, :, :3])
    mask = np.zeros((height + 2, width + 2), np.uint8)
    tolerance = (TOLERANCE,) * 3
    seeds = [(x, y) for x in range(0, width, max(1, width // 12)) for y in (0, height - 1)]
    seeds += [(x, y) for y in range(0, height, max(1, height // 12)) for x in (0, width - 1)]
    for seed in seeds:
        if mask[seed[1] + 1, seed[0] + 1] == 0 and np.abs(bgr[seed[1], seed[0]].astype(np.int16) - colour).max() <= TOLERANCE:
            cv2.floodFill(bgr, mask, seed, 0, tolerance, tolerance, cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE | (255 << 8) | 4)
    background = mask[1:-1, 1:-1] > 0
    if background.mean() > 0.97 or background.mean() < 0.03:
        return _encode(image)
    alpha = np.where(background, 0, 255).astype(np.uint8)
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
    image[:, :, 3] = alpha
    ys, xs = np.where(alpha > 40)
    if len(xs) == 0:
        return _encode(image)
    pad = int(max(height, width) * MARGIN_RATIO)
    top, bottom = max(0, ys.min() - pad), min(height, ys.max() + pad + 1)
    left, right = max(0, xs.min() - pad), min(width, xs.max() + pad + 1)
    return _encode(image[top:bottom, left:right])

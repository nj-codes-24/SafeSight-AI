"""Deterministic synthetic scenes for camera view-change tests: SIMULATED camera movement, not physical cameras.

A textured "world" (rectangles, circles, lines and text, fixed seed) is seen through a virtual camera whose centre,
rotation and zoom can change; workers and vehicles are textured sprites drawn in front of it in image coordinates, the
way people and forklifts occlude a fixed camera's background. Sensor noise is added per frame (seeded by frame number).
The red channel of the scene is kept below 200 so that tests/test_runtime.py's BoxDetector only finds a "person" box
drawn deliberately in pure red.
"""
import math

import cv2
import numpy as np

OUT = (640, 360)  # rendered frame (width, height)
FOV_W = 960  # world pixels across the view at zoom 1


def world(seed=1, size=(1800, 1100)) -> np.ndarray:
    rng = np.random.default_rng(seed)
    w, h = size
    im = np.zeros((h, w, 3), np.uint8)
    im[:] = np.linspace(60, 140, w, dtype=np.uint8)[None, :, None]
    for _ in range(260):
        x, y = int(rng.integers(0, w)), int(rng.integers(0, h))
        c = tuple(int(v) for v in rng.integers(20, 235, 3))
        k = rng.integers(0, 4)
        if k == 0:
            cv2.rectangle(im, (x, y), (x + int(rng.integers(15, 140)), y + int(rng.integers(15, 140))), c, -1)
        elif k == 1:
            cv2.circle(im, (x, y), int(rng.integers(6, 60)), c, -1)
        elif k == 2:
            cv2.line(im, (x, y), (x + int(rng.integers(-200, 200)), y + int(rng.integers(-200, 200))), c, int(rng.integers(2, 7)))
        else:
            cv2.putText(im, "".join(chr(int(v)) for v in rng.integers(65, 90, 4)), (x, y), 0, float(rng.uniform(0.8, 2.2)), c, 3)
    im = cv2.GaussianBlur(im, (3, 3), 0)
    im[:, :, 2] = np.minimum(im[:, :, 2], 190)
    return im


def camera(w, cx=900.0, cy=550.0, angle=0.0, zoom=1.0) -> np.ndarray:
    """The view of world w from a camera centred on (cx, cy), rotated by angle degrees and zoomed by zoom."""
    s = FOV_W / OUT[0] / zoom
    a = math.radians(angle)
    ou, ov = OUT[0] / 2, OUT[1] / 2
    ca, sa = s * math.cos(a), s * math.sin(a)
    A = np.float32([[ca, -sa, cx - (ca * ou - sa * ov)], [sa, ca, cy - (sa * ou + ca * ov)]])  # output -> world
    return cv2.warpAffine(w, A, OUT, flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT)


def sprite(seed, w, h) -> np.ndarray:
    rng = np.random.default_rng(1000 + seed)
    s = np.zeros((h, w, 3), np.uint8)
    s[:] = rng.integers(30, 200, 3)
    for _ in range(max(4, w * h // 400)):
        x, y = int(rng.integers(0, w)), int(rng.integers(0, h))
        cv2.rectangle(s, (x, y), (x + int(rng.integers(3, 20)), y + int(rng.integers(3, 20))),
                      tuple(int(v) for v in rng.integers(10, 240, 3)), -1)
    s[:, :, 2] = np.minimum(s[:, :, 2], 190)
    return s


def paste(im, spr, x, y):
    h, w = spr.shape[:2]
    H, W = im.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 > x0 and y1 > y0:
        im[y0:y1, x0:x1] = spr[y0 - y:y1 - y, x0 - x:x1 - x]


def walkers(im, t, n=4, speed=60.0, seed=0):
    """n textured workers (36 x 90 px) walking back and forth across the image at different heights."""
    W, H = OUT
    for i in range(n):
        span = W + 80
        p = (t * speed * (1 + 0.3 * i) + i * 170) % (2 * span)
        x = int(p - 40 if p < span else 2 * span - p - 40)
        paste(im, sprite(seed + i, 36, 90), x, 120 + (i * 53) % (H - 200))


def forklift(im, t, period=8.0, size=(230, 170)):
    """A large vehicle (over a third of the width) crossing the image, then away for the rest of the period."""
    W, H = OUT
    k = (t % period) / period
    x = int(-size[0] + k * (W + size[0]) * 2)
    paste(im, sprite(99, *size), x, H - size[1] - 20)


def person_box(im, x=100, y=150, w=40, h=120):
    """A pure-red box that tests/test_runtime.py's BoxDetector reports as a person."""
    im[y:y + h, x:x + w] = (0, 0, 255)


def noise(im, i, sigma=3.0):
    rng = np.random.default_rng(i)
    return np.clip(im.astype(np.float32) + rng.normal(0, sigma, im.shape), 0, 255).astype(np.uint8)


def covered(i):
    """A lens covered by a hand or cap: dark, nearly uniform, a little noise."""
    g = np.full((OUT[1], OUT[0], 3), 22, np.uint8)
    g[:] += np.linspace(0, 6, OUT[0], dtype=np.uint8)[None, :, None]
    return noise(g, i, 1.5)


def defocused(im):
    """An object right against the lens (or the focus ring knocked): only very low spatial frequencies remain."""
    return cv2.GaussianBlur(im, (0, 0), 18)


def lighting(im, gain=0.35, gamma=1.4):
    f = (im.astype(np.float32) / 255.0) ** gamma * gain
    return np.clip(f * 255, 0, 255).astype(np.uint8)

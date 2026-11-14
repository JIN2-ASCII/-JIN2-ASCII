# GOOD LUCK
# JIN2 · @jin_22ee · 2026    Free to use for personal projects, see LICENSE.txt.
#
# run:   pip install -r requirements.txt
#        python good_luck.py
# keys:  Space pause · R restart · S screenshot · Esc quit

import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import pygame

LOOP, BUILD = 20.0, 3.0
TRAIL = 0.35
HERE = Path(__file__).parent
PHRASES = json.loads((HERE / "sprites" / "phrases.json").read_text(encoding="utf-8"))


def trim(a):
    # cut the empty margin around each phrase so they can sit close together
    ys, xs = np.nonzero(a > 0.05)
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


SPRITES = [trim(cv2.imread(str(HERE / "sprites" / f"{i:02d}.png"), cv2.IMREAD_UNCHANGED)[:, :, 3].astype(np.float32) / 255)
           for i in range(len(PHRASES))]
RTL = {"Arabic", "Hebrew", "Persian", "Pashto", "Urdu", "Yiddish", "Uyghur"}
N = len(PHRASES)

W, H = 1080, 960
CX, CY = 540, 420                 # where the four leaves meet; the clover turns around this point
LEAF = 385                        # length of one leaf, from the middle to its far edge
LEAF_W = 0.80                     # width of a leaf, as a share of its length
SPLIT = 8                         # small gap between the leaf tips in the middle
ANGLES = (-144, -52, 140, 45)     # which way each leaf points, in degrees (0 = right, 90 = down)
STEM = ((0, 30), (25, 260), (-75, 460))   # the stem bends from the middle down to here
STEM_W = 44
TEXT_PX = 14                      # text height
PITCH = 16                        # one row of text every this many pixels
GAP = 9                           # space between phrases in a row
TURN = 10.0                       # seconds for one full turn to the right
WALL = 22                         # half the thickness of the clover's side, in pixels
DOME = 58                         # how much the leaves bulge out beyond the side

# the right half of a heart (x, y as fractions of its width), top dip to bottom tip; each leaf is one heart
HALF = [(0.0, -0.3575), (0.0301, -0.3662), (0.0563, -0.3844), (0.0825, -0.4024), (0.109, -0.4199),
        (0.1373, -0.4328), (0.1671, -0.4422), (0.1981, -0.4489), (0.231, -0.4507), (0.264, -0.4489),
        (0.2947, -0.4418), (0.3236, -0.43), (0.349, -0.41), (0.3738, -0.3887), (0.3993, -0.3687),
        (0.4241, -0.3474), (0.4442, -0.322), (0.4604, -0.295), (0.4741, -0.267), (0.4852, -0.2379),
        (0.4928, -0.2073), (0.4964, -0.1751), (0.4982, -0.1421), (0.4969, -0.109), (0.4928, -0.077),
        (0.4857, -0.0462), (0.4767, -0.0162), (0.465, 0.0126), (0.4513, 0.0406), (0.4351, 0.0676),
        (0.4176, 0.0941), (0.3988, 0.12), (0.3788, 0.1454), (0.3562, 0.1698), (0.3319, 0.1923),
        (0.3075, 0.2149), (0.2826, 0.2362), (0.2577, 0.2575), (0.2329, 0.2788), (0.208, 0.3001),
        (0.1831, 0.3214), (0.1577, 0.3414), (0.1323, 0.3614), (0.1069, 0.3815), (0.0809, 0.4002),
        (0.0548, 0.4185), (0.028, 0.4352), (0.0, 0.4489)]


def leaf(deg):
    # one heart with its tip in the middle of the clover, pointing outwards
    right = np.array(HALF)
    pts = np.concatenate([right, right[::-1] * [-1, 1]])
    along = (0.4489 - pts[:, 1]) / 0.8996 * LEAF + SPLIT
    across = pts[:, 0] * LEAF * LEAF_W
    a = np.radians(deg)
    x = CX + along * np.cos(a) - across * np.sin(a)
    y = CY + along * np.sin(a) + across * np.cos(a)
    m = np.zeros((H, W), np.uint8)
    cv2.fillPoly(m, [np.round(np.stack([x, y], 1) * 4).astype(np.int32)], 255, lineType=cv2.LINE_AA, shift=2)
    return m > 127


def stem():
    # a curved glass rod from the middle down
    (x0, y0), (x1, y1), (x2, y2) = STEM
    u = np.linspace(0, 1, 60)[:, None]
    p = (1 - u) ** 2 * [x0, y0] + 2 * u * (1 - u) * [x1, y1] + u ** 2 * [x2, y2] + [CX, CY]
    m = np.zeros((H, W), np.uint8)
    cv2.polylines(m, [np.round(p * 4).astype(np.int32)], False, 255, STEM_W, cv2.LINE_AA, shift=2)
    return m > 127


PARTS = [leaf(a) for a in ANGLES] + [stem()]
INSIDE = np.zeros((H, W), bool)
DIST = np.zeros((H, W), np.float32)
RAD = np.ones((H, W), np.float32)
Z = np.zeros((H, W), np.float32)
for i, part in enumerate(PARTS):
    part = part & ~INSIDE                          # the stem tucks under the leaves
    d = cv2.distanceTransform(part.astype(np.uint8), cv2.DIST_L2, 5)
    r = 1 - d / max(d.max(), 1)                    # 0 in the middle of the part, 1 on its edge
    is_leaf = i < 4
    lip = np.exp(-((d - 14) / 5.0) ** 2) * 10 - np.exp(-((d - 34) / 7.0) ** 2) * 7
    z = WALL * (1 if is_leaf else 0.8) + DOME * (1 if is_leaf else 0.3) * np.sqrt(np.clip(1 - r ** 2, 0, 1)) + lip * is_leaf
    INSIDE |= part
    DIST = np.where(part, d, DIST)
    RAD = np.where(part, r, RAD)
    Z = np.where(part, z, Z).astype(np.float32)
MASK = INSIDE.astype(np.float32)


_CACHE = {}


def sprite(idx, k):
    key = (idx, round(k * 200))
    if key not in _CACHE:
        a = SPRITES[idx]
        _CACHE[key] = cv2.resize(a, (max(1, round(a.shape[1] * k)), max(1, round(a.shape[0] * k))),
                                 interpolation=cv2.INTER_AREA)
    return _CACHE[key]


def stamp(img, idx, x, y, k, shown):
    # one phrase, centred on (x, y); only the typed part is visible
    a = sprite(idx, k)
    h, w = a.shape
    if shown < 1:
        cut = int(w * shown)
        a = a.copy()
        if PHRASES[idx][0] in RTL:
            a[:, :w - cut] = 0
        else:
            a[:, cut:] = 0
    x0, y0 = int(x - w / 2), int(y - h / 2)
    cx0, cy0, cx1, cy1 = max(x0, 0), max(y0, 0), min(x0 + w, W), min(y0 + h, H)
    if cx1 <= cx0 or cy1 <= cy0:
        return
    p = a[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0]
    img[cy0:cy1, cx0:cx1] = np.maximum(img[cy0:cy1, cx0:cx1], p)


def smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


Z = cv2.GaussianBlur(Z, (0, 0), 2.0) * INSIDE
ZX, ZY = np.gradient(Z, axis=1), np.gradient(Z, axis=0)

# green glass: pale and clear in the middle, deep green at the thick edge, white where it catches the light
PALE = np.array([150, 222, 168]) / 255
DEEP = np.array([58, 156, 86]) / 255
SHINE = np.array([245, 255, 248]) / 255


def glass(ry, rx, edge):
    base = PALE[None] * (1 - edge)[:, None] + DEEP[None] * edge[:, None]
    shine = smooth((ry - 0.42) / 0.3) * 0.75 + np.exp(-((rx + 0.35) / 0.08) ** 2) * smooth((ry + 0.1) / 0.3) * 0.5
    return base * (1 - 0.6 * shine)[:, None] + SHINE[None] * shine[:, None]


# rows of the clover, cut into the stretches that lie inside it
RUNS = []
for y in range(H):
    cols = np.nonzero(MASK[y] > 0)[0]
    if len(cols):
        for run in np.split(cols, np.nonzero(np.diff(cols) > 1)[0] + 1):
            RUNS.append((y, run))

def fit_row(xl, xr, first, k):
    # pick phrases that fill [xl, xr] exactly, like justified text, so the edge is made of letters
    span = xr - xl
    picks, used, j = [], 0.0, first
    for n in range(40):
        home = [(first + n // 4) % 2] if (n + first) % 4 == 0 else []   # English or Korean comes up every fourth phrase
        for idx in home + [(j + tries * 5) % N for tries in range(12)]:   # if one is too long, look for a shorter one
            w = SPRITES[idx].shape[1] * k
            if used + w + (GAP if picks else 0) <= span:
                break
        else:
            break
        used += w + (GAP if picks else 0)
        picks.append((idx, w))
        if idx > 1:
            j = idx + 7
    if not picks:
        return []
    picks = [(idx, w, k) for idx, w in picks]
    for _ in range(3):                             # leftover room gets one more phrase, a little smaller
        room = span - sum(w for _, w, _ in picks) - GAP * len(picks)
        cands = [i for i in range(N) if SPRITES[i].shape[1] * k * 0.6 <= room]
        if not cands:
            break
        idx = max(cands, key=lambda i: min(SPRITES[i].shape[1] * k, room) - ((i * 31 + int(xl)) % 7))
        kk = min(k, room / SPRITES[idx].shape[1])
        picks.insert((len(picks) * 7 + int(xl)) % (len(picks) + 1), (idx, SPRITES[idx].shape[1] * kk, kk))
    gap = (span - sum(w for _, w, _ in picks)) / max(len(picks) - 1, 1)
    out, x = [], xl if len(picks) > 1 else xl + (span - picks[0][1]) / 2
    for idx, w, kk in picks:
        out.append((idx, x, w, kk))
        x += w + gap
    return out


LAYOUT = {0: [], 1: []}
_k = TEXT_PX / SPRITES[0].shape[0]
_rows = np.nonzero(INSIDE.any(1))[0]
for r, y in enumerate(range(int(_rows[0]) + TEXT_PX // 2, int(_rows[-1]) - TEXT_PX // 2, PITCH)):
    for side in (0, 1):
        rad = RAD if side == 0 else RAD[:, ::-1]      # the back is laid out as seen from behind
        band = rad[max(y - TEXT_PX // 2, 0):min(y + TEXT_PX // 2, H - 1)].max(0)    # the whole letter height must fit
        cols = np.nonzero(band < 0.985)[0]
        if len(cols) < 20:
            continue
        for run in np.split(cols, np.nonzero(np.diff(cols) > 1)[0] + 1):
            if len(run) < 20:
                continue
            picks = fit_row(run[0], run[-1], r * 13 + side * 29 + int(run[0]), _k)
            if not picks:                              # narrow parts like the stem: one short phrase, a little smaller
                span = run[-1] - run[0]
                fits = [i for i in range(N) if SPRITES[i].shape[1] * _k * 0.6 <= span]
                if fits:
                    idx = fits[(r * 3 + side * 5) % len(fits)]
                    ks = min(_k, span / SPRITES[idx].shape[1])
                    w = SPRITES[idx].shape[1] * ks
                    picks = [(idx, run[0] + (span - w) / 2, w, ks)]
            for j, (idx, x, w, k) in enumerate(picks):
                LAYOUT[side].append((r * 50 + int(run[0]) // 25, j, idx, x, w, y, k))


def texture(t, side):
    # a flat sheet of text for one face of the clover (side 0 = front, 1 = back)
    layer = np.zeros((H, W), np.float32)
    count = 0
    for r, j, idx, x, w, y, k in LAYOUT[side]:
        start = 0.1 + ((r * 7919 + j * 104729 + side * 31) % 997) / 997 * (BUILD - 0.6)
        shown = smooth((t - start) / 0.3)
        if shown > 0:
            stamp(layer, idx, x + w / 2, y, k, shown)
            count += 1
    return layer, count


WD = 2 * WALL + 8                         # the side, unrolled: its width is the clover's thickness
SIDE_ROWS = sorted({y for _, _, _, _, _, y, _ in LAYOUT[0]})


def side_texture(t):
    # short phrases written across the side of the clover (end 0 = left side, 1 = right side)
    tex = np.zeros((2, H, WD), np.float32)
    count = 0
    for end in (0, 1):
        for r, y in enumerate(SIDE_ROWS):
            for tries in range(N):
                idx = (r * 17 + end * 41 + tries * 3) % N
                ks = min(_k, (WD - 6) / SPRITES[idx].shape[1])
                if ks >= _k * 0.55:                   # long phrases shrink a little to fit across the side
                    break
            start = 0.1 + ((r * 6007 + end * 911) % 997) / 997 * (BUILD - 0.6)
            shown = smooth((t - start) / 0.3)
            if shown > 0:
                a_ = sprite(idx, ks)
                hh, ww = a_.shape
                x0, y0 = int(WD / 2 - ww / 2), int(y - hh / 2)
                if 0 <= y0 and y0 + hh <= H and x0 >= 0:
                    tex[end, y0:y0 + hh, x0:x0 + ww] = np.maximum(tex[end, y0:y0 + hh, x0:x0 + ww], a_)
                    count += 1
    return tex, count


def render(t):
    # a green glass clover made of text, turning to the right in place, forever
    front, n1 = texture(t, 0)
    back, n2 = texture(t, 1)
    side, n3 = side_texture(t)
    th = 2 * np.pi * t / TURN
    c, s = np.cos(th), np.sin(th)
    out = np.zeros((H, W, 3), np.float32)
    for y, run in RUNS:
        fx = np.arange(run[0], run[-1] + 1, 0.5, dtype=np.float32)   # half-pixel steps, so the turned faces have no holes
        ix = np.round(fx).astype(int).clip(run[0], run[-1])
        x = fx - CX
        z, zx, zy = Z[y, ix], ZX[y, ix], ZY[y, ix]
        norm = np.sqrt(zx * zx + zy * zy + 1)
        # front face and back face of this row of the clover
        X = np.concatenate([x, x])
        D = np.concatenate([z, -z])
        tex = np.concatenate([front[y, ix], back[y, (2 * CX - ix).clip(0, W - 1)]])
        edge = np.concatenate([smooth((RAD[y, ix] - 0.55) / 0.4)] * 2)   # thick glass edge is deeper green
        nx = np.concatenate([-zx, zx]) / np.concatenate([norm, norm])
        ny = np.concatenate([zy, zy]) / np.concatenate([norm, norm])
        nz = np.concatenate([1 / norm, -1 / norm])
        sx = X * c + D * s + CX                      # where it lands on screen
        depth = -X * s + D * c                       # how near it is to us
        # the flat side at each end of this row
        for end, xe in ((0, run[0]), (1, run[-1])):
            ze = max(float(Z[y, xe]), WALL * 0.8)
            zs = np.arange(-ze, ze, 0.7, dtype=np.float32)
            u = ((ze - zs) if end == 0 else (zs + ze)) / (2 * ze) * (WD - 1)
            X = np.concatenate([X, np.full(len(zs), xe - CX, np.float32)])
            D = np.concatenate([D, zs])
            tex = np.concatenate([tex, side[end, y, u.astype(int)]])
            nx = np.concatenate([nx, np.full(len(zs), -1.0 if end == 0 else 1.0)])
            ny = np.concatenate([ny, np.full(len(zs), 0.12)])
            nz = np.concatenate([nz, np.zeros(len(zs))])
            edge = np.concatenate([edge, np.ones(len(zs))])
        sx = X * c + D * s + CX
        depth = -X * s + D * c
        nxr, nzr = nx * c + nz * s, -nx * s + nz * c # the surface direction after turning
        ry, rx = 2 * nzr * ny, 2 * nzr * nxr         # the mirrored view direction
        ry = np.where(nz == 0, 0.25, ry)             # the sides catch a softer light
        col_ = glass(ry, rx, edge)
        rim = np.clip(1 - np.abs(nzr), 0, 1)
        val = col_ * (tex * (0.8 + 0.7 * rim))[:, None]          # only the letters carry the clover
        cols = np.round(sx).astype(int)
        ok = (cols >= 0) & (cols < W) & (nzr > -0.05)
        order = np.argsort(depth[ok])                # far first, near paints over
        out[y, cols[ok][order]] = val[ok][order]
    out = sweep(out, t)
    sparkle(out, t)
    return out, {"languages": N, "phrases": n1 + n2 + n3}, n1 + n2 + n3


_YY, _XX = np.mgrid[0:H, 0:W].astype(np.float32)


def sweep(img, t):
    # a band of light runs across the glass every few seconds
    pos = (t - BUILD) % 4.0 / 4.0 * 1900 - 300
    band = np.exp(-((_XX + _YY * 0.7 - pos) / 45) ** 2) * (t > BUILD)
    lit = img.max(2, keepdims=True)
    return img * (1 + 0.9 * band[..., None]) + lit * band[..., None] * np.array([0.35, 0.6, 0.4])


GLINTS = np.random.default_rng(7).random((70, 4))     # x, height, twinkle phase, size
GLINT = np.array([150, 255, 185]) / 255


def sparkle(img, t):
    # small green stars rise slowly around the clover and twinkle
    fade = smooth((t - BUILD + 1.0) / 1.5)
    for gx, gy, ph, sz in GLINTS:
        x = int(80 + gx * 920)
        y = int((40 + gy * 880 - t * (10 + 20 * sz)) % 900 + 20)
        tw = max(0.0, np.sin(2 * np.pi * (t * 0.5 + ph))) ** 3 * fade
        if tw < 0.04:
            continue
        r = int(2 + 10 * sz * tw)
        col = tuple(float(v) for v in GLINT * tw * 1.3)
        cv2.line(img, (x - r, y), (x + r, y), col, 1, cv2.LINE_AA)
        cv2.line(img, (x, y - r), (x, y + r), col, 1, cv2.LINE_AA)
        d = max(1, r // 3)
        cv2.line(img, (x - d, y - d), (x + d, y + d), col, 1, cv2.LINE_AA)
        cv2.line(img, (x - d, y + d), (x + d, y - d), col, 1, cv2.LINE_AA)


# window

TITLE = "GOOD LUCK · JIN2"
SIGN = "@jin_22ee · 2026"
DIM, PINK = (120, 112, 128), (255, 122, 182)


def to_surface(img):
    return pygame.surfarray.make_surface((np.clip(img, 0, 1) * 255).astype(np.uint8).transpose(1, 0, 2))


def glow(img, k, radius, amount):
    small = cv2.resize(img, (W // k, H // k), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), max(1, radius / k))
    return cv2.resize(small, (W, H), interpolation=cv2.INTER_LINEAR) * amount


def window_size():
    # shrink to fit small or scaled screens
    info = pygame.display.Info()
    k = 1.0
    if info.current_w > 0 and info.current_h > 0:
        k = min(1.0, 0.85 * info.current_h / H, 0.95 * info.current_w / W)
    return int(W * k), int(H * k)


def main():
    pygame.init()
    size = window_size()
    window = pygame.display.set_mode(size)
    pygame.display.set_caption(TITLE)
    small = pygame.font.SysFont("consolas,menlo,dejavusansmono,couriernew,monospace", 17)
    clock = pygame.time.Clock()
    t, paused, trail, info, count = 0.0, False, None, {}, 0
    screen = pygame.Surface((W, H))
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                pygame.quit()
                return
            if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                paused = not paused
            if e.type == pygame.KEYDOWN and e.key == pygame.K_r:
                t, trail = 0.0, None
            if e.type == pygame.KEYDOWN and e.key == pygame.K_s:
                pygame.image.save(screen, str(Path(__file__).with_name(f"good_luck_{int(time.time())}.png")))
        dt = clock.tick(30) / 1000
        if not paused or trail is None:
            if not paused:
                t += min(dt, 1 / 15)
            if t > LOOP:
                t -= LOOP
            img, info, count = render(t)
            trail = img if trail is None else np.maximum(trail * TRAIL, img)
        shown = trail + glow(trail, 4, 5, 0.75) + glow(trail, 8, 22, 0.45)
        screen.blit(to_surface(shown), (0, 0))
        y = H - 70
        screen.blit(small.render(SIGN, True, DIM), (64, y - 26))
        screen.blit(small.render(f"languages {info.get('languages', N)}   phrases {info.get('phrases', 0)}", True, DIM), (64, y))
        screen.blit(small.render(f"letters {count:05,d}", True, DIM), (64, y + 26))
        tt = small.render(f"{'●' if int(t * 2) % 2 == 0 else ' '} t {t:05.2f}s", True, PINK)
        screen.blit(tt, (W - 64 - tt.get_width(), 30))
        window.blit(screen if size == (W, H) else pygame.transform.smoothscale(screen, size), (0, 0))
        pygame.display.flip()


if __name__ == "__main__":
    sys.exit(main())

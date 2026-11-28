# Watching
# JIN2 · @jin_22ee · 2026. Free for learning and personal projects. See LICENSE.txt.
# Don't repost it or sell it as your own, and don't use it to train AI models.
#
# run:   pip install -r requirements.txt
#        python watching.py
# keys:  Space pause · R restart · S screenshot · Esc quit

import sys
import time
from pathlib import Path

import numpy as np
import pygame

LOOP = 18.0
TRAIL = 0.14
GLOW = 0.5
WHITE, HI, GRAY = 0, 4, 9
CW, CH, FONT_PX = 8, 12, 14
W, H = 1080, 960
COLS, ROWS = W // CW, H // CH
TAG_COLOR = [[240, 242, 248], [236, 178, 202], [205, 200, 230], [255, 214, 232], [255, 255, 255],
             [196, 134, 156], [255, 236, 190], [246, 220, 230], [214, 44, 66], [170, 172, 182]]

# letters, dark to bright
POOLS = ["1il!;:", "rtfjcvxz=+", "aeoun0{}[]<>", "08B$#&%Q"]
CHARS = "".join(dict.fromkeys(" .,:~+*^01|/\\-_#()x" + "1il!;:rtfjcvxz=+aeoun0{}[]<>08B$#&%Q"))
AT = {c: i for i, c in enumerate(CHARS)}
FILL = np.array([[AT[p[k % len(p)]] for k in range(12)] for p in POOLS])

# eyelid shapes: corner sharpness (pl, pr), curve of the upper and lower lid (pt, pb),
# depth of the lower lid, hood over the upper lid, slant of the outer corner, iris size
SHAPES = [
    dict(pl=2.0, pr=2.0, pt=0.75, pb=0.85, low=0.75, hood=0.00, shear=0.00, rf=0.78),    # almond
    dict(pl=1.6, pr=1.6, pt=0.55, pb=0.55, low=0.95, hood=0.00, shear=0.00, rf=0.84),    # round
    dict(pl=2.6, pr=1.7, pt=0.85, pb=0.90, low=0.60, hood=0.22, shear=0.10, rf=0.74),    # hooded
    dict(pl=1.8, pr=3.0, pt=0.70, pb=0.90, low=0.55, hood=0.10, shear=-0.12, rf=0.76),   # outer corner up
    dict(pl=3.0, pr=3.0, pt=1.00, pb=1.10, low=0.50, hood=0.00, shear=0.00, rf=0.70),    # narrow, flat
    dict(pl=1.7, pr=2.3, pt=0.60, pb=0.70, low=0.90, hood=0.00, shear=0.06, rf=0.80),    # deep lower lid
    dict(pl=2.2, pr=1.5, pt=0.90, pb=0.60, low=0.80, hood=0.28, shear=-0.05, rf=0.77),   # one heavy lid
    dict(pl=1.3, pr=1.3, pt=0.45, pb=0.45, low=1.00, hood=0.00, shear=0.00, rf=0.88),    # almost a circle
    dict(pl=3.2, pr=3.2, pt=1.10, pb=1.10, low=0.60, hood=0.00, shear=0.00, rf=0.80),    # narrow, iris visible
    dict(pl=1.5, pr=3.4, pt=0.50, pb=1.00, low=0.45, hood=0.35, shear=0.18, rf=0.72),    # teardrop
    dict(pl=3.4, pr=1.4, pt=1.20, pb=0.50, low=0.95, hood=0.00, shear=-0.20, rf=0.80),   # heavy lower lid
]


def eye(x, y, a, b, shape=0, tilt=0.0, show=0.0, shake=1.0, open=((0, 1.0),), blink=(), gaze=((0, 0, 0, 1),), scale=((0, 1.0),)):
    sh = SHAPES[shape % len(SHAPES)]
    return dict(x=x, y=y, a=a, b=b, sh=sh, tilt=tilt, shake=shake, show=show, r=sh["rf"] * b,
                open=list(open), blink=list(blink), gaze=list(gaze), scale=list(scale))


def last(keys, t, default):
    v = default
    for k in keys:
        if k[0] > t:
            break
        v = k[1:]
    return v


def state(e, t):
    o = last(e["open"], t, (1.0,))[0]
    for b in e["blink"]:
        d = (t - b) / 0.20
        if 0 <= d < 1:
            o = min(o, round(abs(2 * d - 1) * 4) / 4)
    gx, gy, p = last(e["gaze"], t, (0, 0, 1))
    return o, gx, gy, p


# timeline: (start, end, eyes), shots overlap in time

rng = np.random.default_rng(11)
SCENES = []
BUSY = []                  # (start, end, x, y, a, b) of every placed eye
LAST = [9999, 9999]        # position of the previous shot


def darts(t0, t1, lo=0.1, hi=0.32, reach=1.0):
    out, t, side = [], t0, 1
    while t < t1:
        side = -side if rng.random() < 0.7 else side
        out.append((t, side * rng.uniform(0.45, 1.0) * reach, rng.uniform(-0.6, 0.6), 1.0))
        t += rng.uniform(lo, hi)
    return out


def clash(t0, t1, x, y, a, b):
    return any(t0 < u1 and u0 < t1 and ((x - px) / (a + pa + 24)) ** 2 + ((y - py) / (b + pb + 24)) ** 2 < 1
               for u0, u1, px, py, pa, pb in BUSY)


def shot(t0, t1, x, y, a, ratio, shape, tilt=0.0, blinks=1, wide=1.0):
    a *= 0.80
    lean = abs(tilt) + abs(SHAPES[shape]["shear"])
    for size in (1.0, 0.88, 0.76, 0.66, 0.56):
        aa = a * size
        bb = aa * ratio + aa * 0.2 * lean
        px, py = x, y
        for _ in range(3000):
            if not clash(t0, t1, px, py, aa, bb) and np.hypot(px - LAST[0], py - LAST[1]) > 380:
                break
            px, py = rng.uniform(-430 + aa, 430 - aa), rng.uniform(-330 + bb, 330 - bb)
        else:
            continue
        break
    BUSY.append((t0, t1, px, py, aa, bb))
    LAST[:] = [px, py]
    bl = sorted(rng.uniform(t0 + 0.25, t1 - 0.2, blinks)) if blinks else []
    g = [(t0, rng.choice([-1, 1]) * rng.uniform(0.5, 1.0), rng.uniform(-0.5, 0.5), 1.0)] + darts(t0 + 0.12, t1)
    SCENES.append((t0, t1, [eye(px, py, aa, aa * ratio, shape, tilt, open=[(t0, wide)], blink=bl, gaze=g)]))


# shut lid, twitching
SCENES.append((0.0, 2.7, [eye(0, -20, 280, 160, 0, open=[(0, 0), (1.25, 0.2), (1.4, 0), (2.05, 0.18), (2.2, 0)],
                              gaze=[(0, -0.6, 0.5, 1), (1.25, -0.9, 0.2, 1), (2.05, 0.7, 0.3, 1)])]))

# the eye opens, then one new eye per cut
shot(3.0, 4.0, 0, 10, 270, 0.57, 0, -0.03, 2)
shot(3.9, 4.8, 250, -70, 170, 0.80, 7, 0.0)
shot(4.6, 5.5, -240, 90, 230, 0.52, 8, -0.10, 2)
shot(5.4, 6.3, 30, 110, 150, 0.62, 3, 0.15, 2)
shot(6.2, 6.7, -120, -120, 200, 0.70, 9, -0.20)

# close up: wide open, no blink, then other eyes glance in
BUSY.append((6.9, 8.7, 0, 0, 230, 162))
LAST[:] = [0, 0]
SCENES.append((6.9, 8.7, [eye(0, 0, 230, 162, 1, open=[(6.9, 1.25)], blink=[8.2], shake=2.5,
                              gaze=[(6.9, 0, 0, 1), (7.5, -0.8, -0.3, 1), (7.62, 0, 0, 1), (8.0, 0.9, 0.2, 1), (8.12, 0, 0, 1)])]))
shot(8.4, 9.2, -250, -150, 120, 0.70, 4)
shot(9.0, 9.8, 230, 140, 210, 0.50, 10, 0.20)
shot(9.6, 10.3, -60, 170, 140, 0.80, 2, -0.10)
shot(10.1, 10.8, 150, -170, 180, 0.45, 6, 0.25)
shot(10.6, 11.3, -200, 40, 110, 0.70, 5)
shot(11.1, 11.8, 0, 0, 160, 0.55, 1, 0.08, 1)
shot(11.6, 12.3, 100, -100, 100, 0.75, 9, -0.1, 1)

# many eyes gather, then every one looks at the viewer and grows
M0, FLASH = 12.4, 16.3
mr = np.random.default_rng(11)
GROW = 1.18
SIZES = [175, 145, 122, 104, 90, 78, 68, 60, 54, 48, 44, 40, 38]
placed = []
order = [int(i) for i in mr.permutation(len(SHAPES))] * 2
for n, a in enumerate(SIZES):
    shape, tilt = order[n], mr.uniform(-0.28, 0.28) * (1 if n % 2 else -1)
    ratio = mr.uniform(0.42, 0.85)
    lean = abs(tilt) + abs(SHAPES[shape]["shear"])
    ea = a * GROW + 14
    eb = a * ratio * 1.2 * GROW + a * 0.2 * lean + 14
    for _ in range(40000):
        x, y = mr.uniform(-420 + ea, 420 - ea), mr.uniform(-340 + eb, 340 - eb)
        if all(((x - p[0]) / (ea + p[2] + 6)) ** 2 + ((y - p[1]) / (eb + p[3] + 6)) ** 2 > 1 for p in placed):
            placed.append((x, y, ea, eb, shape, tilt, ratio, a))
            break
REVEAL = [0, .4, .7, .95, 1.2, 1.4, 1.6, 1.75, 1.9, 2.05, 2.2, 2.35, 2.47, 2.59, 2.7, 2.8]
MANY = []
for (x, y, _, _, shape, tilt, ratio, a), when in zip((placed[i] for i in mr.permutation(len(placed))), REVEAL):
    s = M0 + when
    g = [(s, mr.uniform(-1, 1), mr.uniform(-0.7, 0.7), 1.0)] + darts(s + 0.15, FLASH - 0.1, 0.08, 0.3)
    g += [(FLASH + 0.1, 0, 0, 1.1), (FLASH + 0.45, 0, 0, 1.22)]
    MANY.append(eye(x, y, a, a * ratio, shape=shape, tilt=tilt, show=s,
                    open=[(s, 1.0), (FLASH + 0.1, 1.2)], shake=1.6,
                    scale=[(s, 1.0), (FLASH + 0.1, 1.09), (FLASH + 0.45, GROW)],
                    blink=sorted(mr.uniform(s + 0.4, FLASH - 0.2, 3)), gaze=g))
SCENES.append((M0, FLASH, MANY))
SCENES.append((FLASH + 0.1, 18.0, MANY))


# drawing an eye into the letter grid

_GRID = {}


def grid():
    if not _GRID:
        X = np.broadcast_to((np.arange(COLS) + 0.5) * CW - COLS * CW / 2, (ROWS, COLS))
        Y = np.broadcast_to(((np.arange(ROWS) + 0.5) * CH - ROWS * CH / 2)[:, None], (ROWS, COLS))
        r = np.random.default_rng(5)
        _GRID["g"] = (X, Y, r.random((ROWS, COLS)), r.random((ROWS, COLS)))
    return _GRID["g"]


def paint(e, t, G, X, Y, RND, RND2):
    ch, lum, tag = G
    sh = e["sh"]
    o, gx, gy, p = state(e, t)
    jx = ((int(t * 12) * 7919 + int(e["x"])) % 7 - 3) * e["shake"]
    jy = ((int(t * 12) * 104729 + int(e["y"])) % 5 - 2) * e["shake"]
    dx, dy = X - e["x"] - jx, Y - e["y"] - jy
    c, s = np.cos(e["tilt"]), np.sin(e["tilt"])
    x, y = c * dx + s * dy, -s * dx + c * dy
    y = y - sh["shear"] * x
    sc = last(e["scale"], t, (1.0,))[0]
    a, b = e["a"] * sc, e["b"] * sc
    u = x / a
    k = np.clip(1 - np.abs(u) ** np.where(u < 0, sh["pl"], sh["pr"]), 0, 1)

    if o < 0.1:                                                    # shut: a lid line with a few lashes
        d = y - 0.30 * b * k ** 0.9
        line = (np.abs(u) < 1) & (np.abs(d) < 6)
        lash = (np.abs(u) < 0.95) & (d > 6) & (d < 28) & (RND2 < 0.30 * (1 - (d - 6) / 22))
        ch[line], lum[line], tag[line] = AT["-"], 0.45 + 0.12 * np.sin(t * 2.2), WHITE
        ch[lash], lum[lash], tag[lash] = AT["+"], 0.34, WHITE
        return

    n = (RND - 0.5) * 18
    top = b * o * (1 - sh["hood"]) * k ** sh["pt"]
    bot = b * o * sh["low"] * k ** sh["pb"]
    inside = (np.abs(u) < 1) & (y > -top + n) & (y < bot + n)
    r = e["r"] * p * sc
    ix, iy = gx * 0.42 * a, gy * 0.40 * b
    dist = np.hypot(x - ix, y - iy)
    iris = inside & (dist < r)
    white = inside & ~iris

    # eyeball: darker toward the lids, with grain
    edge_d = np.minimum(y + top - n, bot + n - y)
    shade = np.clip(edge_d / (0.4 * b), 0, 1) ** 0.55
    wl = np.clip((0.6 + 0.45 * k ** 0.4) * (0.55 + 0.45 * shade) + (RND2 - 0.5) * 0.2, 0.18, 1.0)
    pool = np.clip((wl * 4.6).astype(int), 0, 3)
    pick = ((RND * 12 + t * 2.2).astype(int)) % 12
    ch[white], lum[white], tag[white] = FILL[pool, pick][white], wl[white], WHITE

    # iris: black, grey rim that is brighter along the bottom
    q = np.clip((dist / r - 0.60) / 0.40, 0, 1)
    rim = np.minimum(0.30 * q * q * (3 - 2 * q) * (1 + 1.3 * np.clip((y - iy) / r, 0, 1)), 0.7)
    dark = iris & (rim < 0.04)
    ch[iris], lum[iris], tag[iris] = FILL[2, pick][iris], rim[iris], GRAY
    ch[dark], lum[dark] = 0, 0

    # lashes outside the lids
    d_up, d_dn = -top + n - y, y - bot - n
    fd = np.where(d_up > 0, d_up, d_dn)
    fringe = ~inside & (np.abs(u) < 0.98) & (fd > 0) & (fd < 30) & (RND2 < 0.5 * (1 - fd / 30))
    ch[fringe], lum[fringe], tag[fringe] = AT["+"], 0.42, WHITE

    # two highlights
    for hx, hy, size in ((0.16, -0.42, 0.085), (0.40, -0.40, 0.055)):
        rr = max(size * r / 7, 0.9)
        dot = iris & (((x - ix - hx * r) / CW) ** 2 + ((y - iy - hy * r) / CH) ** 2 < rr * rr)
        ch[dot], lum[dot], tag[dot] = AT["8"], 1.0, HI


def frame(t):
    X, Y, RND, RND2 = grid()
    G = (np.zeros((ROWS, COLS), int), np.zeros((ROWS, COLS), np.float32), np.zeros((ROWS, COLS), int))
    live = [(t0, eyes) for t0, t1, eyes in SCENES if t0 <= t < t1]
    since = min((t - t0 for t0, _ in live), default=9.0)
    calm = since < 0.5                                             # no glitch right after a cut
    flicker = t > 3.0 and not calm and np.random.default_rng(int(t * 30) + 7).random() < 0.025
    seen, lid, gaze = 0, 0.0, (0.0, 0.0)
    if not flicker:
        for _, eyes in live:
            for e in eyes:
                if t >= e["show"]:
                    paint(e, t, G, X, Y, RND, RND2)
                    o, gx, gy, _ = state(e, t)
                    seen, lid, gaze = seen + 1, o, (gx, gy)
    if not flicker and not calm and np.random.default_rng(int(t * 30) + 99).random() < 0.07:
        gr = np.random.default_rng(int(t * 30))                    # rows slip sideways
        for _ in range(8):
            r0, shift = int(gr.integers(0, ROWS - 8)), int(gr.integers(-10, 11))
            for A in G:
                A[r0:r0 + 5] = np.roll(A[r0:r0 + 5], shift, 1)
    return G[0], G[1], G[2], dict(eyes=seen, lid=lid, gx=gaze[0], gy=gaze[1]), int((G[1] > 0).sum())


# window

TITLE = "Watching - JIN2"
SIGN = "@jin_22ee · 2026"
COLORS = np.array(TAG_COLOR, np.float32) / 255
DIM, PINK = (110, 104, 120), (255, 122, 182)
MONO = "consolas,menlo,dejavusansmono,couriernew,monospace"


def hud(info):
    return f"eyes {info['eyes']:02d}   lid {info['lid']:.2f}   gaze {info['gx']:+.2f} {info['gy']:+.2f}"


def glyphs():
    font = pygame.font.SysFont(MONO, FONT_PX)
    atlas = []
    for ch in CHARS:
        s = pygame.Surface((CW, CH))
        g = font.render(ch, True, (255, 255, 255))
        s.blit(g, ((CW - g.get_width()) // 2, (CH - g.get_height()) // 2))
        atlas.append(pygame.surfarray.array3d(s)[:, :, 0].T.astype(np.float32) / 255)
    return np.stack(atlas)


class Canvas:
    def __init__(self, atlas):
        self.atlas = (atlas * 255).astype(np.uint8)
        self.shape = pygame.Surface((COLS * CW, ROWS * CH))
        self.trail = pygame.Surface((W, H))
        self.fade = (int(TRAIL * 255),) * 3

    def reset(self):
        self.trail.fill((0, 0, 0))

    def draw(self, t):
        char, lum, tag, info, count = frame(t)
        mask = self.atlas[char.T].transpose(0, 3, 1, 2).reshape(COLS * CW, ROWS * CH)
        pygame.surfarray.blit_array(self.shape, np.repeat(mask[..., None], 3, 2))
        col = np.clip(COLORS[np.clip(tag, 0, len(COLORS) - 1)] * lum[..., None] * 255, 0, 255).astype(np.uint8)
        tint = pygame.transform.scale(pygame.surfarray.make_surface(col.transpose(1, 0, 2)), self.shape.get_size())
        self.shape.blit(tint, (0, 0), special_flags=pygame.BLEND_MULT)
        self.trail.fill(self.fade, special_flags=pygame.BLEND_MULT)
        self.trail.blit(self.shape, (0, 0), special_flags=pygame.BLEND_MAX)
        return self.trail, info, count


def blur(surf, k, radius):
    small = pygame.transform.smoothscale(surf, (W // k, H // k))
    if hasattr(pygame.transform, "gaussian_blur"):
        small = pygame.transform.gaussian_blur(small, max(1, radius // k))
    return pygame.transform.smoothscale(small, (W, H))


def glow_layer(surf, amount):
    layer = surf.copy()
    layer.fill((int(255 * amount),) * 3, special_flags=pygame.BLEND_MULT)
    return layer


def window_size():
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
    screen = pygame.Surface((W, H))
    small = pygame.font.SysFont(MONO, 17)
    canvas, clock = Canvas(glyphs()), pygame.time.Clock()
    t, paused = 0.0, False
    art, info, count = canvas.draw(t)
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                pygame.quit()
                return
            if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                paused = not paused
            if e.type == pygame.KEYDOWN and e.key == pygame.K_r:
                t = 0.0
                canvas.reset()
            if e.type == pygame.KEYDOWN and e.key == pygame.K_s:
                pygame.image.save(screen, str(Path(__file__).with_name(f"watching_{int(time.time())}.png")))
        dt = clock.tick(30) / 1000
        if not paused:
            t += min(dt, 1 / 15)
            if t > LOOP:
                t = 0.0
                canvas.reset()
            art, info, count = canvas.draw(t)
        screen.fill((0, 0, 0))
        screen.blit(art, (0, 0))
        screen.blit(glow_layer(blur(art, 4, 5), 0.75 * GLOW), (0, 0), special_flags=pygame.BLEND_ADD)
        screen.blit(glow_layer(blur(art, 8, 22), 0.45 * GLOW), (0, 0), special_flags=pygame.BLEND_ADD)
        y = H - 70
        screen.blit(small.render(SIGN, True, (120, 112, 128)), (64, y - 26))
        screen.blit(small.render(hud(info), True, DIM), (64, y))
        screen.blit(small.render(f"letters {count:05,d}", True, DIM), (64, y + 26))
        tt = small.render(f"{'●' if int(t * 2) % 2 == 0 else ' '} t {t:05.2f}s", True, PINK)
        screen.blit(tt, (W - 64 - tt.get_width(), 30))
        window.blit(screen if size == (W, H) else pygame.transform.smoothscale(screen, size), (0, 0))
        pygame.display.flip()


if __name__ == "__main__":
    sys.exit(main())

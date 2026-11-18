# Flip Phone
# JIN2 (@jin_22ee), 2026. Full code, shared for personal projects. No redistribution, no commercial use, no AI training. See LICENSE.txt.
# Do not repost this code or a changed version of it as your own, or post videos made from it as your own art.
# If you see it posted as someone else's, please report it and let me know (@jin_22ee).
#
#   pip install -r requirements.txt
#   python flip_phone.py
#
# Space pause, R restart, S screenshot, Esc quit

# Change these four lines to make it your own.
CALLER = "babydoll"              # name on the screen (english, 5 letters max shows best)
OPEN = (5.0, 6.4)                # (lid starts moving, lid fully open) in seconds. it rings at 3.2
SCREEN_COLOR = (110, 255, 140)   # screen light (red, green, blue), each 0-255
PHONE_COLOR = (120, 122, 132)    # phone body (red, green, blue), each 0-255

import sys
import time
from pathlib import Path

import numpy as np
import pygame

TITLE = "Flip Phone - JIN2"
SIGN = "@jin_22ee · 2026"
FPS = 30
CW, CH, FONT_PX = 5, 7, 8                # one letter cell, in pixels
W, H = 1080, 960
COLS, ROWS = W // CW, H // CH
ASPECT = (COLS * CW) / (ROWS * CH)
TRAIL = 0.25                             # how much of the last frame stays behind
LOOP, BUILD = 16.0, 3.0
RING = 3.2                               # the call comes in while it is still shut
DIM, PINK = (110, 104, 120), (255, 122, 182)
MONO = "consolas,menlo,dejavusansmono,couriernew,monospace"
TAU = np.pi * 2

POOLS = ["1il!;:", "rtfjcvxz=+", "aeoun0{}[]<>", "08B$#&%Q"]   # dark -> bright
CHARS = " .,:~+*^01|/\\-_#()x" + "".join(POOLS)
AT = {c: i for i, c in enumerate(CHARS)}
FILL = np.array([[AT[p[k % len(p)]] for k in range(12)] for p in POOLS])

BODY, EDGE, KEY, SCREEN, DARK, ANT, SHINE, GLINT, LED, TINT1, TINT2, TINT3 = range(12)
SCREEN_BASE, PHONE_BASE = (110, 255, 140), (120, 122, 132)


def tint(rgb, new, base):
    # scale a color by how far your pick is from the original green / grey
    return [min(255.0, c * n / b) for c, n, b in zip(rgb, new, base)]


S, P = (SCREEN_COLOR, SCREEN_BASE), (PHONE_COLOR, PHONE_BASE)
COLORS = np.array([tint([120, 122, 132], *P), tint([190, 192, 204], *P), tint([176, 178, 190], *P),
                   tint([110, 255, 140], *S), tint([40, 64, 48], *S), tint([150, 152, 164], *P),
                   tint([214, 255, 226], *S), [255, 255, 255], tint([140, 255, 160], *S),
                   tint([146, 172, 156], *S), tint([128, 204, 150], *S), tint([116, 232, 146], *S)], np.float32) / 255
GLOW_RGB = [c * n / b for c, n, b in zip([0.02, 0.13, 0.045], SCREEN_COLOR, SCREEN_BASE)]
FLASH_RGB = [c * n / b for c, n, b in zip([0.05, 0.14, 0.07], SCREEN_COLOR, SCREEN_BASE)]

rng = np.random.default_rng(3)


def smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def rot(axis, a):
    c, s = np.cos(a), np.sin(a)
    i, j = [(1, 2), (2, 0), (0, 1)][axis]
    m = np.eye(3)
    m[i, i], m[i, j], m[j, i], m[j, j] = c, -s, s, c
    return m


def camera(eye, target):
    eye, target = np.asarray(eye, float), np.asarray(target, float)
    fwd = (target - eye) / np.linalg.norm(target - eye)
    right = np.cross(fwd, [0, 1.0, 0])
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    return lambda P: ((P - eye) @ right, (P - eye) @ up, (P - eye) @ fwd)


look = camera(eye=(0.200222, 0.35, 3.35), target=(0.0, 0.02, 0.0))
F = 2.900222


def to_grid(P):
    x, y, z = look(np.atleast_2d(P))
    z = np.maximum(z, 0.2)
    return (0.5 + x / z * F * 0.5) * COLS, (0.5 - y / z * F * 0.5 * ASPECT) * ROWS, z


# ---- the screen: a handset, and the caller's name scrolling by
TEX_W, TEX_H = 200, 290
NAME_Y0, NAME_H = 178, 76
SCROLL = 85                                 # texture pixels per second


def screen_art():
    pygame.font.init()
    icon = pygame.Surface((TEX_W, TEX_H))
    icon.fill((255, 255, 255))
    for ang in np.radians(np.linspace(200, 340, 60)):       # the curved grip
        pygame.draw.circle(icon, (0, 0, 0), (100 + 60 * np.cos(ang), 100 + 60 * np.sin(ang)), 13)
    for ang in (200, 340):                                   # ear and mouth piece
        ex, ey = 100 + 60 * np.cos(np.radians(ang)), 100 + 60 * np.sin(np.radians(ang))
        pygame.draw.ellipse(icon, (0, 0, 0), (ex - 22, ey - 16, 44, 38))
    font = pygame.font.SysFont("impact,arialblack,arial", 80)
    text = font.render(CALLER, True, (0, 0, 0), (255, 255, 255))
    strip = pygame.Surface((text.get_width() + 140, NAME_H))
    strip.fill((255, 255, 255))
    strip.blit(text, (10, (NAME_H - text.get_height()) // 2))
    ink = lambda s: pygame.surfarray.array3d(s)[:, :, 0].T < 128
    return ink(icon), ink(strip)


# ---- the phone, in two halves joined at the hinge
PW, PL = 0.5, 0.92
LOWER = rot(0, -0.62)                       # the keypad half lies toward us
OPEN_A, SHUT_A = -0.12, np.pi - 0.62 - 0.07  # the screen half: open / folded down on the keys


def plate(x0, x1, y0, y1, step, r=0.0):
    xs, ys = np.meshgrid(np.arange(x0, x1, step), np.arange(y0, y1, step))
    p = np.stack([xs.ravel(), ys.ravel()], 1)
    if r > 0:
        cx, cy = np.clip(p[:, 0], x0 + r, x1 - r), np.clip(p[:, 1], y0 + r, y1 - r)
        p = p[np.hypot(p[:, 0] - cx, p[:, 1] - cy) <= r]
    return p


def build_phone():
    P, tag, part, kind, upper = [], [], [], [], []

    def add(p, t, k, what="", up=False):
        P.append(p), tag.append(np.full(len(p), t)), part.append(np.full(len(p), k))
        kind.append(np.full(len(p), what, dtype=object)), upper.append(np.full(len(p), up))

    flat = lambda p2, z: np.c_[p2, np.full(len(p2), z)]
    # screen half: shell, screen, speaker, antenna, a small light on the lid
    add(flat(plate(-PW / 2, PW / 2, 0.04, PL, 0.007, 0.07), 0.03), BODY, 1, up=True)
    sx, sy = np.meshgrid(np.linspace(-0.190222, 0.19, 110), np.linspace(0.22, 0.79, 160))
    add(flat(np.stack([sx.ravel(), sy.ravel()], 1), 0.034), SCREEN, 2, "screen", True)
    add(flat(plate(-0.06, 0.06, 0.845, 0.865, 0.004, 0.009), 0.036), EDGE, 3, up=True)
    for k, x in enumerate((-0.17, 0.17)):
        a = rng.uniform(0, TAU, 120)
        add(flat(np.c_[x + 0.018 * np.cos(a), 0.855 + 0.018 * np.sin(a)], 0.036), EDGE, 4 + k, up=True)
    a, h = rng.uniform(0, TAU, 900), rng.uniform(0, 0.17, 900)
    add(np.c_[0.215 + 0.022 * np.cos(a), PL + h - 0.02, -0.01 + 0.022 * np.sin(a)], ANT, 6, "antenna", True)
    a = rng.uniform(0, TAU, 160)
    add(np.c_[0.016 * np.cos(a), 0.7 + 0.016 * np.sin(a), np.full(160, 0.024)], LED, 9, "led", True)
    # hinge
    a, x = rng.uniform(0, TAU, 1500), rng.uniform(-0.2, 0.2, 1500)
    add(np.c_[x, 0.045 * np.cos(a), 0.045 * np.sin(a)], EDGE, 7)
    # keypad half: shell, 1-9 * 0 #, two soft keys, the round d-pad
    add(flat(plate(-PW / 2, PW / 2, -PL, -0.04, 0.007, 0.08), 0.03) @ LOWER.T, BODY, 8)
    pid = 20
    for row in range(4):
        for col in range(3):
            cx, cy = -0.15 + col * 0.15, -0.5 - row * 0.1
            add(flat(plate(cx - 0.055, cx + 0.055, cy - 0.032, cy + 0.032, 0.005, 0.022), 0.042) @ LOWER.T, KEY, pid, "key")
            pid += 1
    for cx in (-0.17, 0.17):
        add(flat(plate(cx - 0.05, cx + 0.05, -0.2, -0.16, 0.005, 0.018), 0.04) @ LOWER.T, KEY, pid, "key")
        pid += 1
    a = rng.uniform(0, TAU, 1600)
    r = np.sqrt(rng.uniform(0.045 ** 2, 0.085 ** 2, 1600))
    add(flat(np.c_[r * np.cos(a), -0.3 + r * np.sin(a)], 0.042) @ LOWER.T, KEY, pid, "key")
    add(flat(plate(-0.03, 0.03, -0.33, -0.27, 0.005, 0.03), 0.044) @ LOWER.T, EDGE, pid + 1)
    return (np.concatenate(P), np.concatenate(tag), np.concatenate(part), np.concatenate(kind), np.concatenate(upper))


PTS, TAGS, PARTS, KIND, UP = build_phone()
SCR = KIND == "screen"
SCR_UV = PTS[SCR][:, :2]
SCR_RIM = np.minimum.reduce([SCR_UV[:, 0] + 0.19, 0.19 - SCR_UV[:, 0], SCR_UV[:, 1] - 0.22, 0.79 - SCR_UV[:, 1]])
SPARK = np.nonzero(SCR)[0][rng.random(SCR.sum()) < 0.0012]
MOTES = rng.random((70, 5))


def timeline():
    # the ring (buzz 1.2 s, rest 0.8 s), the lid swinging open with a small bounce, the screen waking up
    dt = 1 / 240
    t = np.arange(0, LOOP + dt, dt)
    buzz = ((t - RING) % 2.0 < 1.2) & (t > RING)
    buzz = np.convolve(buzz.astype(float), np.ones(12) / 12, "same")
    u = np.clip((t - OPEN[0]) / (OPEN[1] - OPEN[0]), 0, 1)
    lid = SHUT_A + (OPEN_A - SHUT_A) * (1 + 2.2 * (u - 1) ** 3 + 1.2 * (u - 1) ** 2)
    flicker = (t > OPEN[1] - 0.35) & (t < OPEN[1] + 0.15) & (np.sin(t * 70) < -0.2)
    lit = np.where(flicker, 0.15, smooth((t - OPEN[1] + 0.35) / 0.5))
    return buzz, lid, lit


BUZZ, LID, LIT = timeline()


def at(t, arr):
    return arr[min(int(t * 240), len(arr) - 1)]


def scene(t):
    lit, buzz, lid = at(t, LIT), at(t, BUZZ), at(t, LID)
    shake = buzz * np.array([0.007 * np.sin(t * TAU * 27), 0.004 * np.sin(t * TAU * 31), 0])
    turn = rot(1, buzz * 0.012 * np.sin(t * TAU * 23))
    upper = rot(0, lid)
    closed = np.clip((lid - OPEN_A) / (SHUT_A - OPEN_A), 0, 1)
    lift = (LOWER @ [0, 0, 1.0]) * 0.07 * closed            # shut, the lid lies on top of the keys
    P = np.where(UP[:, None], PTS @ upper.T + lift, PTS) @ turn.T + shake
    tag = TAGS.copy()
    shade = np.where(TAGS == KEY, 0.75, np.where(TAGS == EDGE, 0.8, 0.42))
    # the screen: dark, then bright green, a little brighter at its rim, a band of light drifting across
    glare = np.exp(-((SCR_UV[:, 0] * 0.8 + SCR_UV[:, 1] - 0.1 - ((t * 0.18) % 1.4)) / 0.035) ** 2)
    shade[SCR] = (0.2 + 0.72 * lit) + 0.12 * lit * (SCR_RIM < 0.015) + 0.2 * glare * lit
    tag[SCR] = np.where(lit > 0.05, np.where(glare > 0.5, SHINE, SCREEN), DARK)
    if lit > 0.6:
        tag[SPARK[np.sin(t * 3 + SPARK * 0.7) > 0.93]] = GLINT
    # its light falls on the keys near the hinge
    spill = lit * np.exp(-np.linalg.norm(PTS - [0, 0.45, 0], axis=1) / 0.32) * (~UP & (KIND != "led"))
    spill = spill * np.where(TAGS == KEY, 1.3, 0.9)
    tag[spill > 0.12], tag[spill > 0.22], tag[spill > 0.34] = TINT1, TINT2, TINT3
    shade = shade + 0.35 * spill
    led = KIND == "led"
    shade[led] = np.where((t > RING) & (np.sin(t * 9) > 0), 1.0, 0.2)
    tip = (KIND == "antenna") & (PTS[:, 1] > PL + 0.12)
    tag[tip & (np.sin(t * 2.2 + PTS[:, 0] * 50) > 0.97)] = GLINT
    corners = np.array([[-0.19, 0.79, 0.034], [0.19, 0.79, 0.034], [0.19, 0.22, 0.034], [-0.19, 0.22, 0.034]])
    screen = dict(corners=(corners @ upper.T) @ turn.T + shake, lit=lit, t=t - OPEN[1])
    # at the start the letters gather from the bottom up, one in seven flying in from around
    head = (t - 0.1) / (BUILD - 0.1)
    k = smooth((head - (P[:, 1] + 1.0) / 1.6) / 0.12)
    fly = np.arange(len(P)) % 7 == 0
    scatter = (np.arange(len(P))[:, None] * [0.7548, 0.5698, 0.3141] % 1 - 0.5) * [3.4, 3.0, 1.0]
    P = np.where(fly[:, None], scatter + (P - scatter) * smooth(k)[:, None], P)
    keep = k > 0.03
    P, shade, tag, part = P[keep], shade[keep], tag[keep], PARTS[keep]
    if lit > 0.3:                                            # green dust rising in front of the screen
        h = (MOTES[:, 1] + (t - OPEN[1]) * (0.04 + 0.05 * MOTES[:, 3])) % 1
        mp = np.c_[(MOTES[:, 0] - 0.5) * 0.9, 0.1 + h * 1.1, 0.08 + MOTES[:, 2] * 0.35] @ rot(0, OPEN_A).T
        tw = (0.5 + 0.5 * np.sin(t * (2 + 3 * MOTES[:, 3]) + MOTES[:, 4] * 30)) * np.sin(np.pi * h) * lit
        P, shade = np.concatenate([P, mp]), np.concatenate([shade, 0.9 * tw])
        tag, part = np.concatenate([tag, np.full(len(mp), SHINE)]), np.concatenate([part, -np.ones(len(mp), int)])
    return P, shade, tag, part, screen


def outline_letter(gx, gy):
    ax, ay = np.abs(gx), np.abs(gy)
    c = np.where(ax > 2 * ay, AT["|"], np.where(ay > 2 * ax, np.where(gy > 0, AT["_"], AT["-"]),
                 np.where(gx * gy > 0, AT["/"], AT["\\"])))
    return np.where((ax + ay) == 0, AT["+"], c)


def letters(t, P, shade, tag, part):
    # points -> one letter per cell: outlines where a part ends, filler letters inside
    sx, sy, z = to_grid(P)
    order = np.argsort(-z)
    sx, sy, z, shade, tag, part = sx[order], sy[order], z[order], shade[order], tag[order], part[order]
    ix, iy = sx.astype(int), sy.astype(int)
    ok = (ix >= 0) & (ix < COLS) & (iy >= 0) & (iy < ROWS)
    owner = np.full((ROWS, COLS), -1)
    depth = np.full((ROWS, COLS), 99.0)
    lum = np.zeros((ROWS, COLS))
    tone = np.zeros((ROWS, COLS), int)
    b = ok & (part >= 0)
    owner[iy[b], ix[b]], depth[iy[b], ix[b]] = part[b], z[b]
    lum[iy[b], ix[b]], tone[iy[b], ix[b]] = shade[b], tag[b]
    body = owner >= 0
    po, pd = np.pad(owner, 1, constant_values=-1), np.pad(depth, 1, constant_values=99)
    edge = np.zeros_like(body)
    gx, gy = np.zeros((ROWS, COLS)), np.zeros((ROWS, COLS))
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == dy == 0:
                continue
            nb, nz = po[1 + dy:ROWS + 1 + dy, 1 + dx:COLS + 1 + dx], pd[1 + dy:ROWS + 1 + dy, 1 + dx:COLS + 1 + dx]
            out = body & ((nb < 0) | ((nb != owner) & (nz > depth + 0.006)))
            gx, gy = gx + dx * out, gy + dy * out
            if dx == 0 or dy == 0:
                edge |= out
    r, c = np.mgrid[0:ROWS, 0:COLS]
    hsh = (r * 7919 + c * 104729) % 9973
    level = np.clip((lum * 3.2).astype(int), 0, 3)
    char = np.where(body, np.where(edge, outline_letter(gx, gy), FILL[level, (hsh + (t * 4 + hsh % 11).astype(int)) % 12]), 0)
    char = np.where(body & (tone == GLINT), AT["*"], char)
    lum = np.where(body, np.where(edge, np.maximum(0.6, lum), np.clip(0.15 + 0.85 * lum, 0.12, 1)), 0)
    dust = ok & (part < 0) & (shade > 0.02)
    hidden = body[iy[dust], ix[dust]]
    fi, fj, fs = iy[dust][~hidden], ix[dust][~hidden], shade[dust][~hidden]
    char[fi, fj] = np.where(fs > 0.7, AT["*"], np.where(fs > 0.35, AT["+"], AT["."]))
    lum[fi, fj], tone[fi, fj] = np.clip(fs, 0, 1), SHINE
    return char, lum, tone


def sparkle(char, lum, tone, t):
    # small four-point stars on the brightest glints
    score = np.where(tone == GLINT, lum + (np.arange(lum.size).reshape(lum.shape) % 7) * 0.01, 0)
    for n, idx in enumerate(np.argsort(score.ravel())[::-1][:3]):
        if score.ravel()[idx] <= 0:
            break
        cy, cx = divmod(int(idx), COLS)
        reach = int(2 + 4 * (0.5 + 0.5 * np.sin(t * 7 + n * 1.7)))
        for d in range(1, reach + 1):
            fade = 1 - d / (reach + 1)
            for dy, dx, ch in ((0, 1, "-"), (0, -1, "-"), (1, 0, "|"), (-1, 0, "|")):
                yy, xx = cy + dy * d, cx + dx * d * 2
                if 0 <= yy < ROWS and 0 <= xx < COLS and lum[yy, xx] < fade:
                    char[yy, xx], lum[yy, xx], tone[yy, xx] = AT[ch], fade, GLINT
        char[cy, cx], lum[cy, cx] = AT["*"], 1.0


def homography(src, dst):
    A = []
    for (x, y), (u, v) in zip(src, dst):
        A += [[x, y, 1, 0, 0, 0, -u * x, -u * y, -u], [0, 0, 0, x, y, 1, -v * x, -v * y, -v]]
    return np.linalg.svd(np.array(A))[2][-1].reshape(3, 3)


def cut_screen(char, lum, screen, icon, name):
    # the handset and the scrolling name stay black on the green screen, cell by cell
    if screen["lit"] < 0.5:
        return
    cx, cy, _ = to_grid(screen["corners"])
    Hm = homography(np.c_[cx, cy], [(0, 0), (TEX_W, 0), (TEX_W, TEX_H), (0, TEX_H)])
    gy, gx = np.mgrid[int(cy.min()):int(cy.max()) + 1, int(cx.min()):int(cx.max()) + 1]
    ink = np.zeros(gx.shape)
    shift = int(screen["t"] * SCROLL)
    for oy in (0.2, 0.5, 0.8):
        for ox in (0.2, 0.5, 0.8):
            q = Hm @ np.stack([gx.ravel() + ox, gy.ravel() + oy, np.ones(gx.size)])
            u, v = q[0] / q[2], q[1] / q[2]
            ok = (u >= 0) & (u < TEX_W) & (v >= 0) & (v < TEX_H)
            ui, vi = u[ok].astype(int), v[ok].astype(int)
            band = (vi >= NAME_Y0) & (vi < NAME_Y0 + NAME_H)
            hit = np.zeros(gx.size, bool)
            hit[ok] = np.where(band, name[np.clip(vi - NAME_Y0, 0, NAME_H - 1), (ui + shift - TEX_W) % name.shape[1]],
                               icon[vi, ui])
            ink += hit.reshape(gx.shape) / 9
    cut = (ink > 0.42) & (gx >= 0) & (gx < COLS) & (gy >= 0) & (gy < ROWS)
    char[gy[cut], gx[cut]], lum[gy[cut], gx[cut]] = 0, 0.0


def glyphs():
    font = pygame.font.SysFont(MONO, FONT_PX)
    atlas = []
    for ch in CHARS:
        s = pygame.Surface((CW, CH))
        g = font.render(ch, True, (255, 255, 255))
        s.blit(g, ((CW - g.get_width()) // 2, (CH - g.get_height()) // 2))
        atlas.append(pygame.surfarray.array3d(s)[:, :, 0].T.astype(np.float32) / 255)
    return np.stack(atlas)


GS = 8                                      # the glow is soft, so it is worked out at 1/8 size
_Y, _X = (np.mgrid[0:H // GS, 0:W // GS].astype(np.float32) + 0.5) * GS


def screen_glow(t, screen):
    # light spilling out of the screen; it swells with every buzz
    if screen["lit"] <= 0.05:
        return None
    cx, cy, _ = to_grid(screen["corners"].mean(0))
    bx, by = cx[0] * CW, cy[0] * CH
    flash = np.exp(-((t - OPEN[1] - 0.1) / 0.25) ** 2)
    r = 220 + 80 * at(t, BUZZ) + 120 * flash
    g = np.exp(-((_X - bx) ** 2 + (_Y - by) ** 2) / (2 * r ** 2))[..., None]
    pulse = 0.85 + 0.15 * at(t, BUZZ)
    return g * GLOW_RGB * screen["lit"] * pulse + g * FLASH_RGB * flash


class Canvas:
    def __init__(self, atlas):
        self.atlas = atlas
        self.icon, self.name = screen_art()
        self.trail = None

    def reset(self):
        self.trail = None

    def draw(self, t):
        P, shade, tag, part, screen = scene(t)
        char, lum, tone = letters(t, P, shade, tag, part)
        sparkle(char, lum, tone, t)
        cut_screen(char, lum, screen, self.icon, self.name)
        tint = COLORS[np.clip(tone, 0, len(COLORS) - 1)] * lum[..., None]
        img = self.atlas[char][..., None] * tint[:, :, None, None, :]
        img = img.transpose(0, 2, 1, 3, 4).reshape(ROWS * CH, COLS * CW, 3)
        img = np.pad(img, ((0, H - ROWS * CH), (0, W - COLS * CW), (0, 0)))
        self.trail = img if self.trail is None else np.maximum(self.trail * TRAIL, img)
        return self.trail, screen_glow(t, screen)


def to_surface(img):
    return pygame.surfarray.make_surface((np.clip(img, 0, 1) * 255).astype(np.uint8).transpose(1, 0, 2))


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
    art, light = canvas.draw(0.0)
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
                pygame.image.save(screen, str(Path(__file__).with_name(f"flip_phone_{int(time.time())}.png")))
        dt = clock.tick(FPS) / 1000
        if not paused:
            t += min(dt, 1 / 15)
            if t >= LOOP:
                t = 0.0
                canvas.reset()
            art, light = canvas.draw(t)
        surf = to_surface(art)
        screen.fill((0, 0, 0))
        if light is not None:
            screen.blit(pygame.transform.smoothscale(to_surface(light), (W, H)), (0, 0))
        screen.blit(surf, (0, 0), special_flags=pygame.BLEND_ADD)
        screen.blit(glow_layer(blur(surf, 4, 5), 0.5), (0, 0), special_flags=pygame.BLEND_ADD)
        screen.blit(glow_layer(blur(surf, 8, 22), 0.3), (0, 0), special_flags=pygame.BLEND_ADD)
        y = H - 70
        state = "open" if at(t, LID) < 0.2 else "shut"
        screen.blit(small.render(SIGN, True, (120, 112, 128)), (64, y - 26))
        screen.blit(small.render(f"{state}   incoming {CALLER if at(t, LIT) > 0.5 else '-'}", True, DIM), (64, y))
        screen.blit(small.render("vibrate" if at(t, BUZZ) > 0.5 else "", True, DIM), (64, y + 26))
        tt = small.render(f"{'●' if int(t * 2) % 2 == 0 else ' '} t {t:05.2f}s", True, PINK)
        screen.blit(tt, (W - 64 - tt.get_width(), 30))
        window.blit(screen if size == (W, H) else pygame.transform.smoothscale(screen, size), (0, 0))
        pygame.display.flip()


if __name__ == "__main__":
    sys.exit(main())

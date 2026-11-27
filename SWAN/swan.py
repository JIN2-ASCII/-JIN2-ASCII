# SWAN
# JIN2 · @jin_22ee · 2026. Full source. See LICENSE.txt.
# Don't repost it or sell it as your own, and don't use it to train AI models.
#
# run:   pip install -r requirements.txt
#        python swan.py
# keys:  Space pause · R restart · S screenshot · Esc quit
# needs: swan.py and swan_shape.npz in the same folder

import multiprocessing
import os
import sys
import time
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from scipy.interpolate import PchipInterpolator

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

TAU = np.pi * 2

# letters by density, dark -> bright; FILL[level, k] cycles through one pool
POOLS = ["1il!;:", "rtfjcvxz=+", "aeoun0{}[]<>", "08B$#&%Q"]
CHARS = " .,:~+*^01|/\\-_#()x" + "".join(POOLS)
AT = {c: i for i, c in enumerate(CHARS)}
FILL = np.array([[AT[p[k % len(p)]] for k in range(12)] for p in POOLS])


def smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def rot_y(p, a):
    c, s = np.cos(a), np.sin(a)
    return np.stack([c * p[:, 0] + s * p[:, 2], p[:, 1], -s * p[:, 0] + c * p[:, 2]], 1)


def camera(eye, target):
    """fixed camera; look(P) -> x, y, z, view vector"""
    eye, target = np.asarray(eye, float), np.asarray(target, float)
    fwd = (target - eye) / np.linalg.norm(target - eye)
    right = np.cross(fwd, [0, 1.0, 0])
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)

    def look(P):
        rel = P - eye
        return rel @ right, rel @ up, rel @ fwd, -fwd
    return look


def outline_letter(gx, gy):
    ax, ay = np.abs(gx), np.abs(gy)
    c = np.where(ax > 2 * ay, AT["|"], np.where(ay > 2 * ax, np.where(gy > 0, AT["_"], AT["-"]),
                 np.where(gx * gy > 0, AT["/"], AT["\\"])))
    return np.where((ax + ay) == 0, AT["+"], c)


def raster(t, cols, rows, aspect, P, shade, T, K, look, inner, particle, *, F=2.9, gap=0.035, edge_min=0.0):
    """project points into a letter grid.
    K >= 0: solid part id (drawn with an outline), K < 0: particle (drawn by `particle`)."""
    x, y, z, _ = look(P)
    zz = np.maximum(z, 0.2)
    sx = (0.5 + x / zz * F * 0.5) * cols
    sy = (0.5 - y / zz * F * 0.5 * aspect) * rows
    order = np.argsort(-z)                              # far to near
    sx, sy, z, shade, T, K = sx[order], sy[order], z[order], shade[order], T[order], K[order]
    ix, iy = sx.astype(int), sy.astype(int)
    ok = (ix >= 0) & (ix < cols) & (iy >= 0) & (iy < rows) & (z > 0.2)

    part = np.full((rows, cols), -1)
    depth = np.full((rows, cols), 99.0)
    lum = np.zeros((rows, cols))
    tag = np.zeros((rows, cols), int)
    b = ok & (K >= 0)
    part[iy[b], ix[b]], depth[iy[b], ix[b]] = K[b], z[b]
    lum[iy[b], ix[b]], tag[iy[b], ix[b]] = shade[b], T[b]
    body = part >= 0

    # outline: cells next to empty space or to another part further back
    pp = np.pad(part, 1, constant_values=-1)
    pd = np.pad(depth, 1, constant_values=99)
    edge = np.zeros_like(body)
    gx = np.zeros((rows, cols))
    gy = np.zeros((rows, cols))
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == dy == 0:
                continue
            nb = pp[1 + dy:rows + 1 + dy, 1 + dx:cols + 1 + dx]
            nz = pd[1 + dy:rows + 1 + dy, 1 + dx:cols + 1 + dx]
            out = body & ((nb < 0) | ((nb != part) & (nz > depth + gap)))
            gx += dx * out
            gy += dy * out
            if dx == 0 or dy == 0:
                edge |= out

    r, c = np.mgrid[0:rows, 0:cols]
    h = (r * 7919 + c * 104729) % 9973
    level = np.clip((lum * 3.2).astype(int), 0, 3)
    fill = FILL[level, (h + (t * 4 + h % 11).astype(int)) % 12]
    char = np.where(body, np.where(edge, outline_letter(gx, gy), fill), 0)
    lum = np.where(body, np.where(edge, np.maximum(edge_min, lum), inner(lum)), 0)

    # particles go only where nothing solid is in front
    fx = ok & (K < 0) & (shade > 0.02)
    hidden = body[iy[fx], ix[fx]] & (depth[iy[fx], ix[fx]] < z[fx])
    fi, fj, fs, ft = (a[fx][~hidden] for a in (iy, ix, shade, T))
    keep = ~body[fi, fj]
    fi, fj, fs, ft = fi[keep], fj[keep], fs[keep], ft[keep]
    char[fi, fj], lum[fi, fj], tag[fi, fj] = particle(ft, fs, fi, fj), np.clip(fs, 0, 1), ft
    return SimpleNamespace(char=char, lum=lum, tag=tag, count=int(body.sum()))


CELL = (9, 14, 15)                                                  # letter cell: width px, height px, font px
LOOP = 26.0                                                         # seconds, then it repeats
GLOW = 1.0
TRAIL = 0.35
TAG_COLOR = [[250, 250, 252], [186, 192, 206], [150, 168, 196], [255, 255, 255]]   # swan, reflection, water, sparkle
SWAN, REFL, WATER, SPARK = range(4)

LIGHT = np.array([-0.3, 0.7, 0.65]) / np.linalg.norm([-0.3, 0.7, 0.65])
PX = 1 / 150                                                        # shape units -> world units

# neck rig: centre line control points (shape units, y down) and bend presets, one angle per bone
CTRL = np.array([(268, 275), (278, 235), (292, 200), (302, 165), (300, 130), (282, 106), (255, 115), (242, 150), (227, 190)], float)
HEAD_FROM = 4.6                                                     # bones past this index move as one rigid head
STRAIGHT = np.array([0, 0, -0.12, -0.28, -0.40, 0.0, 0, 0])          # stretch: unbends the curl and lifts the head
DIP = np.array([0, 0.62, 0.32, 0.14, 0.0, -0.78, 0, 0])              # dip: leans the neck forward from the root


def load_shape():
    """swan point cloud from swan_shape.npz. one side is stored; the far side is mirrored in z.
    per point: x y z, normal n, brightness tex, nearest neck sample j, offset along/across the neck,
    neck weight w (1 = moves with the neck, 0 = body) and wing weight ww.
    also the neck centre line C, its tangents T and the bone index of each sample."""
    f = np.load(Path(__file__).with_name("swan_shape.npz"))
    d = {k: f[k] for k in ("x", "y", "z", "n", "tex", "j", "along", "across", "w", "ww")}
    half = len(d["x"])
    d = {k: np.concatenate([v, v]) for k, v in d.items()}
    d["z"][half:] *= -1
    d["n"][half:, 2] *= -1
    return dict(d, C=f["C"], T=f["T"], bone=f["bone"])


S = load_shape()
TIP = int(np.argmax(S["j"] * (S["w"] > 0.9)))                       # beak tip point


def pose(stretch, down, sway):
    """rotate the neck centre line bone by bone; returns the new line, its tangents and the turn per sample"""
    ang = STRAIGHT * stretch + DIP * down + np.array([0, 0.3, 0.5, 0.3, 0, 0.6, 0, 0]) * sway
    C, T, bone = S["C"], S["T"], S["bone"]
    i = np.minimum(np.floor(bone).astype(int), 4)
    cum = np.r_[0, np.cumsum(ang)]
    turn = cum[i] + np.clip(bone - i, 0, 1) * ang[i]                 # angle accumulates along the bones
    turn = turn + ang[5] * np.clip((bone - HEAD_FROM) / 0.4, 0, 1)   # head tilt, blended in near the crown
    seg = np.diff(C, axis=0, prepend=0)
    c, s = np.cos(turn), np.sin(turn)
    seg = np.stack([seg[:, 0] * c + seg[:, 1] * s, -seg[:, 0] * s + seg[:, 1] * c], 1)   # y points down here
    return np.cumsum(seg, axis=0), np.stack([T[:, 0] * c + T[:, 1] * s, -T[:, 0] * s + T[:, 1] * c], 1), turn


def swan(t, stretch, down, look_at, sway, wing=0.0):
    """one swan in its own frame: head toward -x, waterline y = 0, camera side +z"""
    C, T, turn = pose(stretch, down, sway)
    j, w = S["j"], S["w"]
    nrm = np.stack([-T[j, 1], T[j, 0]], 1)
    moved = C[j] + S["along"][:, None] * T[j] + S["across"][:, None] * nrm
    px = S["x"] * (1 - w) + moved[:, 0] * w
    py = S["y"] * (1 - w) + moved[:, 1] * w
    py = py - S["ww"] * (24 * wing + (2 + 8 * wing) * np.sin(S["x"] * 0.05 + t * 3.5))   # wing lift and feather ripple
    a = turn[j] * w
    n = S["n"].copy()
    n[:, 0], n[:, 1] = n[:, 0] * np.cos(a) + n[:, 1] * np.sin(a), -n[:, 0] * np.sin(a) + n[:, 1] * np.cos(a)
    P = np.stack([(px - 400) * PX, (283 - py) * PX, S["z"] * PX], 1)
    n[:, 1] *= -1                                                   # shape y down -> world y up
    yaw = look_at * np.clip(S["bone"][j] / 4, 0, 1) ** 1.5 * w        # head turn, stronger toward the head
    rx = (CTRL[0, 0] - 400) * PX
    c, s = np.cos(yaw), np.sin(yaw)
    P = np.stack([rx + (P[:, 0] - rx) * c + P[:, 2] * s, P[:, 1], -(P[:, 0] - rx) * s + P[:, 2] * c], 1)
    n = np.stack([n[:, 0] * c + n[:, 2] * s, n[:, 1], -n[:, 0] * s + n[:, 2] * c], 1)
    return P, n, P[TIP]


def shade(n):
    return 0.720222 + 0.28 * np.clip(n @ LIGHT, 0, 1) + 0.15 * (1 - np.abs(n[:, 2])) ** 2


def ease(t, a, b):
    return smooth((t - a) / (b - a))


def pulse(t, a, b, c, d):
    return ease(t, a, b) * (1 - ease(t, c, d))


# two swans. way: (time, x, z) waypoints, x to the right, z toward the camera.
# the other entries are motion curves over time: neck stretch, neck dip, head turn, wing lift,
# paddle (speed variation), sway2 (extra body sway) and yaw (heading limit).
FREE = lambda t: 0.3 + 3.0 * smooth((t - 12.5) / 2.0)                # heading limit of the second swan: small until 12.5 s, then free
SWANS = [
    dict(face=1, scale=0.95, phase=0.0,
         way=[(0, 3.8, 0.5), (7, 1.3, 0.5), (13.5, 1.3, 0.5), (24, -2.6, 0.55), (26, -3.3, 0.55), (27, -3.65, 0.55)],
         stretch=lambda t: 0.22 + 0.18 * np.sin(t * 0.5 + 1.0) + 0.35 * pulse(t, 2.5, 4.0, 5.5, 7.0),
         down=lambda t: 0.1 + 0.08 * np.sin(t * 0.73 + 2.0),
         look=lambda t: 0.3 * pulse(t, 5.0, 6.5, 8.5, 10.0) + 0.15 * pulse(t, 19, 20.5, 23, 24.5),
         wing=lambda t: 0.9 * pulse(t, 6.5, 8.0, 9.0, 10.5) + 0.3 * pulse(t, 9.0, 10.0, 12.0, 13.5) + 0.35 * pulse(t, 17.0, 18.5, 19.5, 21.0),
         paddle=lambda t: 0.07 * np.sin(t * 1.1), sway2=lambda t: 0.0,
         yaw=lambda t, v: float(np.clip(v, -0.3, 0.3))),
    dict(face=-1, scale=0.95, phase=2.4,
         way=[(0, -3.3, -3.2), (2, -3.25, -3.1), (4.5, -2.7, -2.0), (6.5, -1.9, -0.6), (8.5, -1.3, 0.5),
              (12.5, -1.3, 0.5), (15, -0.5, -0.2), (17.5, 0.5, -1.1), (19.5, 1.1, -2.0), (21, 1.1, -2.7),
              (22.5, 0.5, -3.1), (24, -0.5, -3.25), (26, -1.7, -3.35), (27, -2.3, -3.4)],
         stretch=lambda t: 0.28 + 0.1 * np.sin(t * 0.45) + 0.3 * pulse(t, 2.0, 4.0, 7.5, 9.0) + 0.25 * pulse(t, 16.0, 18.0, 21.0, 23.0),
         down=lambda t: 0.08 + 0.06 * np.sin(t * 0.6) + 0.08 * pulse(t, 13.0, 14.5, 15.5, 17.0),
         look=lambda t: 0.25 * pulse(t, 18.0, 19.5, 21.0, 22.5),
         wing=lambda t: 0.3 * pulse(t, 9.0, 10.0, 12.0, 13.5) + 0.5 * pulse(t, 14.0, 15.5, 16.5, 18.0) + 0.6 * pulse(t, 18.5, 20.0, 21.0, 22.5)
         + 0.35 * pulse(t, 23.5, 24.5, 25.3, 26.5),
         paddle=lambda t: 0.07 * np.sin(t * 1.1 + 2.4),
         sway2=lambda t: 0.05 * np.sin(t * 0.7) * smooth((t - 12.5) / 2.0),
         yaw=lambda t, v: float(np.clip(v, -FREE(t), FREE(t)))),
]
HEART = lambda t: 0.2 * pulse(t, 7.5, 8.5, 12.5, 13.5)               # both heads lowered toward each other
NUZZLE = lambda t: pulse(t, 8.3, 8.8, 12.0, 12.8)                    # small head rub while the beaks touch
for _c in SWANS:
    _w = np.array(_c["way"], float)
    _c["spl"] = PchipInterpolator(_w[:, 0], _w[:, 1:], axis=0)


def position(t, c):
    """position on the path and heading; the heading fades in with speed and is clipped by c['yaw']"""
    tt = t + c["paddle"](t)
    end = c["spl"].x[-1]
    x, z = c["spl"](np.clip(tt, 0, end))
    x1, z1 = c["spl"](np.clip(tt + 0.4, 0, end))
    ux, uz = (x1 - x) * c["face"], (z1 - z) * c["face"] - 1e-4
    speed = np.hypot(ux, uz) / 0.4
    yaw = np.arctan2(uz, -ux) * smooth((speed - 0.04) / 0.15)
    return x, z, c["yaw"](t, yaw)


def place(t, c):
    """one swan in world space: points, normals, beak tip and its (x, z) on the water"""
    x, z, yaw = position(t, c)
    sway = 0.12 * np.sin(t * 0.9 + c["phase"]) + 0.1 * np.sin(t * 2.3 + c["phase"]) * NUZZLE(t) + c["sway2"](t)
    P, n, tip = swan(t, c["stretch"](t), c["down"](t) + HEART(t), c["look"](t), sway, c["wing"](t))
    P, n = rot_y(P * [c["face"], 1, 1] * c["scale"], yaw), rot_y(n * [c["face"], 1, 1], yaw)
    bob = 0.012 * np.sin(t * 1.3 + c["phase"])
    off = np.array([x, bob, z])
    return P + off, n, tip * [c["face"], 1, 1] * c["scale"] + off, x, z


def frame(t, cols, rows, aspect):
    r = np.random.default_rng(int(t * 30) % 1000)
    parts, lums, tags, kids = [], [], [], []
    tips = []
    for k, c in enumerate(SWANS):
        P, n, tip, sx, sz = place(t, c)
        tips.append(tip)
        L = (0.8 + 0.2 * S["tex"]) * shade(n)
        keep = P[:, 1] > -0.005                                                 # nothing below the waterline
        P, L = P[keep], L[keep]
        parts.append(P); lums.append(L); tags.append(np.full(len(P), SWAN)); kids.append(np.full(len(P), k))
        R = P * [1, -1, 1]                                                      # reflection, displaced by ripples
        R[:, 0] += 0.04 * np.sin(R[:, 1] * 20 + t * 2.4) + 0.012 * np.sin(R[:, 1] * 66 - t * 4)
        rk = (r.random(len(R)) < 0.45) & (np.sin(R[:, 1] * 40 + t * 1.6) > -0.5)
        parts.append(R[rk]); lums.append(L[rk] * 0.340222 * np.clip(1 + R[rk][:, 1] / 2.0, 0, 1))
        tags.append(np.full(rk.sum(), REFL)); kids.append(np.full(rk.sum(), -1))
        c["at"] = (sx, sz)
    gx, gz = np.meshgrid(np.linspace(-9, 9, 340), np.linspace(-8, 4.5, 200))      # water grid
    X, Z = gx.ravel(), gz.ravel()
    rip = np.sin(X * 1.3 + Z * 4.5 - t * 1.1) + 0.6 * np.sin(X * 2.6 - Z * 7 + t * 1.6) + 0.3 * np.sin(X * 5 + Z * 11 + t * 2.3)
    wl = 0.05 + 0.4 * np.clip(rip / 1.9, 0, 1) ** 2.5
    for c in SWANS:                                                             # brighter water around each swan, V wake behind it
        sx, sz = c["at"]
        wl += 0.12 * np.exp(-(((X - sx) / 1.4) ** 2 + ((Z - sz - 0.5) / 0.5) ** 2))
        back = X - (sx + 0.9)
        wake = np.abs(Z - sz + 0.1) - back * 0.28
        wl += 0.28 * np.exp(-(wake / 0.1) ** 2) * np.exp(-back / 2.5) * (back > 0)
    for c in SWANS:                                                             # rings pushed out by the breast every 2.3 s
        for k in range(12):
            t0 = 1.2 + 2.3 * k
            age = t - t0
            if 0 < age < 4.5:
                px0, pz0, _ = position(t0, c)
                cx = px0 - 1.15 * c["face"] * c["scale"]
                rr = np.hypot(X - cx, (Z - pz0) * 1.6)
                wl += 0.45 * np.exp(-((rr - 0.7 * age) / 0.1) ** 2) * np.exp(-age * 0.75)
    mid = (tips[0] + tips[1]) / 2
    age = t - 8.5                                                               # one ring where the beaks meet
    if 0 < age < 5:
        rr = np.hypot(X - mid[0], (Z - mid[2]) * 1.6)
        wl += 0.6 * np.exp(-((rr - 0.6 * age) / 0.12) ** 2) * np.exp(-age * 0.6)
    wk = (wl > 0.13) & (r.random(len(wl)) < np.clip(1.3 - 0.09 * (4.5 - Z), 0.45, 1))
    parts.append(np.stack([X, np.zeros_like(X), Z], 1)[wk]); lums.append(np.clip(wl[wk] * 1.6, 0, 0.800222))
    tags.append(np.full(wk.sum(), WATER)); kids.append(np.full(wk.sum(), -1))
    sp = np.random.default_rng(8)                                               # sun flecks
    n = 1300
    SX, SZ, ph = sp.uniform(-9, 9, n), sp.uniform(-8, 4.5, n), sp.uniform(0, TAU, n)
    tw = np.clip(np.sin(t * (1.5 + 2 * sp.random(n)) + ph), 0, 1) ** 10
    parts.append(np.stack([SX + 0.03 * np.sin(t + ph), np.zeros(n), SZ], 1)); lums.append(tw)
    tags.append(np.full(n, SPARK)); kids.append(np.full(n, -1))
    P, L, T, K = (np.concatenate(a) for a in (parts, lums, tags, kids))

    def letters(ft, fs, fi, fj):
        water = np.where(fs > 0.32, AT["~"], np.where(fs > 0.16, AT["-"], AT["_"]))
        refl = FILL[np.clip((fs * 6).astype(int), 0, 2), (fi * 31 + fj) % 12]
        return np.where(ft == WATER, water, np.where(ft == REFL, refl, np.where(fs > 0.6, AT["*"], AT["+"])))

    cam = camera(eye=(0, 1.0, 8.2 - 0.4 * smooth(t / LOOP)), target=(0, 0.5, 0))   # drifts slowly closer
    g = raster(t, cols, rows, aspect, P, L, T, K, cam, lambda l: np.clip(0.5 + 0.5 * l, 0, 1), letters)
    return g.char, g.lum, g.tag, {"swans": len(SWANS)}, g.count


def HUD(info):
    return f"swans {info.get('swans', 0)}"


# window

TITLE = "SWAN · JIN2"
SIGN = "@jin_22ee · 2026"
CW, CH, FONT_PX = CELL
W, H = 1080, 960
COLS, ROWS = W // CW, H // CH
ASPECT = (COLS * CW) / (ROWS * CH)
COLOR = np.array(TAG_COLOR, np.float32) / 255
DIM, PINK = (120, 112, 128), (255, 122, 182)


def glyphs():
    font = pygame.font.SysFont("consolas,menlo,dejavusansmono,couriernew,monospace", FONT_PX)
    atlas = []
    for ch in CHARS:
        s = pygame.Surface((CW, CH))
        g = font.render(ch, True, (255, 255, 255))
        s.blit(g, ((CW - g.get_width()) // 2, (CH - g.get_height()) // 2))
        atlas.append(pygame.surfarray.array3d(s)[:, :, 0].T.astype(np.float32) / 255)
    return np.stack(atlas)


class Canvas:
    # glyph mask x colour x brightness, over a fading copy of the previous frame

    def __init__(self, atlas):
        self.atlas = (atlas * 255).astype(np.uint8)
        self.shape = pygame.Surface((COLS * CW, ROWS * CH))
        self.trail = pygame.Surface((W, H))
        self.fade = (int(TRAIL * 255),) * 3

    def reset(self):
        self.trail.fill((0, 0, 0))

    def draw(self, res):
        char, lum, tag, info, count = res
        mask = self.atlas[char.T].transpose(0, 3, 1, 2).reshape(COLS * CW, ROWS * CH)
        pygame.surfarray.blit_array(self.shape, np.repeat(mask[..., None], 3, 2))
        col = (COLOR[np.clip(tag, 0, len(COLOR) - 1)] * np.clip(lum, 0, 1)[..., None] * 255).astype(np.uint8)
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
    # shrink to fit small or scaled screens
    info = pygame.display.Info()
    k = 1.0
    if info.current_w > 0 and info.current_h > 0:
        k = min(1.0, 0.85 * info.current_h / H, 0.95 * info.current_w / W)
    return int(W * k), int(H * k)


FPS = 30


def render(t):
    char, lum, tag, info, count = frame(t, COLS, ROWS, ASPECT)
    return char.astype(np.uint8), lum.astype(np.float32), tag.astype(np.uint8), info, count


class Frames:
    # frames are computed ahead on several CPU cores, then shown in order at FPS

    def __init__(self):
        n = max(1, min(8, (os.cpu_count() or 2) - 1))
        self.pool = multiprocessing.Pool(n) if n > 1 else None
        self.ahead = 3 * n
        self.queue = deque()
        self.restart()

    def restart(self):
        self.queue.clear()
        self.k = 0
        self.fill()

    def fill(self):
        while len(self.queue) < self.ahead:
            t = (self.k % int(LOOP * FPS)) / FPS
            job = self.pool.apply_async(render, (t,)) if self.pool else None
            self.queue.append((t, job))
            self.k += 1

    def next(self):
        # the next frame, or None if it isn't ready yet
        t, job = self.queue[0]
        if job is not None and not job.ready():
            return None
        self.queue.popleft()
        self.fill()
        return t, (job.get() if job is not None else render(t))

    def close(self):
        if self.pool:
            self.pool.terminate()


def main():
    pygame.init()
    size = window_size()
    window = pygame.display.set_mode(size)
    pygame.display.set_caption(TITLE)
    screen = pygame.Surface((W, H))
    small = pygame.font.SysFont("consolas,menlo,dejavusansmono,couriernew,monospace", 17)
    canvas, clock = Canvas(glyphs()), pygame.time.Clock()
    frames = Frames()
    t, paused, art = 0.0, False, None
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                frames.close()
                pygame.quit()
                return
            if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                paused = not paused
            if e.type == pygame.KEYDOWN and e.key == pygame.K_r:
                frames.restart()
                canvas.reset()
            if e.type == pygame.KEYDOWN and e.key == pygame.K_s:
                pygame.image.save(screen, str(Path(__file__).with_name(f"swan_{int(time.time())}.png")))
        clock.tick(FPS)
        if not paused:
            nxt = frames.next()
            if nxt is not None:
                t, res = nxt
                if t == 0.0:
                    canvas.reset()
                art, info, count = canvas.draw(res)
        if art is None:
            screen.fill((0, 0, 0))
            screen.blit(small.render("loading", True, DIM), (64, H // 2))
            window.blit(screen if size == (W, H) else pygame.transform.smoothscale(screen, size), (0, 0))
            pygame.display.flip()
            continue
        screen.fill((0, 0, 0))
        screen.blit(art, (0, 0))
        screen.blit(glow_layer(blur(art, 4, 5), 0.75 * GLOW), (0, 0), special_flags=pygame.BLEND_ADD)
        screen.blit(glow_layer(blur(art, 8, 22), 0.45 * GLOW), (0, 0), special_flags=pygame.BLEND_ADD)
        y = H - 70
        screen.blit(small.render(SIGN, True, DIM), (64, y - 26))
        screen.blit(small.render(HUD(info), True, DIM), (64, y))
        screen.blit(small.render(f"letters {count:05,d}", True, DIM), (64, y + 26))
        tt = small.render(f"{'●' if int(t * 2) % 2 == 0 else ' '} t {t:05.2f}s", True, PINK)
        screen.blit(tt, (W - 64 - tt.get_width(), 30))
        window.blit(screen if size == (W, H) else pygame.transform.smoothscale(screen, size), (0, 0))
        pygame.display.flip()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())

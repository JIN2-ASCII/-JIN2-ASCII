# GOLDFISH
# JIN2 · @jin_22ee · 2026. Full source. See LICENSE.txt.
# Don't repost it or sell it as your own, and don't use it to train AI models.
#
# run:   pip install -r requirements.txt
#        python goldfish.py
# keys:  Space pause · R restart · S screenshot · Esc quit

import multiprocessing
import os
import sys
import time
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import numpy as np

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

# letters, dark to bright
POOLS = ["1il!;:", "rtfjcvxz=+", "aeoun0{}[]<>", "08B$#&%Q"]
CHARS = " .,:~+*^01|/\\-_#()x" + "".join(POOLS)
AT = {c: i for i, c in enumerate(CHARS)}
FILL = np.array([[AT[p[k % len(p)]] for k in range(12)] for p in POOLS])


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


def raster(t, cols, rows, aspect, P, shade, T, K, look, *, F=2.9, gap=0.035, glints=(),
           edge_min=0.85, inner=None, particle=None):
    """project points into a letter grid.
    K >= 0: solid part id, K < 0: particle. glints: tags drawn as '*'."""
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
    sparkle = body & np.isin(tag, list(glints))
    char = np.where(body, np.where(edge, outline_letter(gx, gy), fill), 0)
    char = np.where(sparkle, AT["*"], char)
    inner_lum = inner(lum) if inner else np.clip(0.45 + 0.55 * lum / 0.9, 0.45, 1)
    lum = np.where(body, np.where(edge, np.maximum(edge_min, lum), inner_lum), 0)

    # particles go only where nothing solid is in front
    fx = ok & (K < 0) & (shade > 0.02)
    hidden = body[iy[fx], ix[fx]] & (depth[iy[fx], ix[fx]] < z[fx])
    fi, fj, fs, ft = (a[fx][~hidden] for a in (iy, ix, shade, T))
    keep = ~body[fi, fj]
    fi, fj, fs, ft = fi[keep], fj[keep], fs[keep], ft[keep]
    letter = particle(ft, fs, fi, fj)
    char[fi, fj], lum[fi, fj], tag[fi, fj] = letter, np.clip(fs, 0, 1), ft
    return SimpleNamespace(char=char, lum=lum, tag=tag, sparkle=sparkle, h=h,
                           rows=rows, cols=cols, count=int(body.sum()))


def rays(g, cy, cx, reach, glint_tag, strength=1.0, diag=0.7):
    """four-point star with short diagonals"""
    char, lum, tag, rows, cols = g.char, g.lum, g.tag, g.rows, g.cols
    for dist in range(1, reach + 1):
        fade = (1 - dist / (reach + 1)) * strength
        for (dy, dx, ch) in ((0, 1, "-"), (0, -1, "-"), (1, 0, "|"), (-1, 0, "|")):
            yy, xx = cy + dy * dist, cx + dx * dist * 2
            if 0 <= yy < rows and 0 <= xx < cols and lum[yy, xx] < fade:
                char[yy, xx], lum[yy, xx], tag[yy, xx] = AT[ch], fade, glint_tag
        if dist <= reach // 2:
            for (dy, dx, ch) in ((1, 1, "\\"), (-1, -1, "\\"), (1, -1, "/"), (-1, 1, "/")):
                yy, xx = cy + dy * dist, cx + dx * dist
                if 0 <= yy < rows and 0 <= xx < cols and lum[yy, xx] < fade * diag:
                    char[yy, xx], lum[yy, xx], tag[yy, xx] = AT[ch], fade * diag, glint_tag
    char[cy, cx], lum[cy, cx] = AT["*"], 1.0


def starbursts(g, t, glint_tag, count=4, base=4, swing=6):
    """pulsing stars on the brightest glints"""
    score = np.where(g.sparkle, g.lum + (g.h % 7) * 0.01, 0)
    for n, idx in enumerate(np.argsort(score.ravel())[::-1][:count]):
        if score.ravel()[idx] <= 0:
            break
        cy, cx = divmod(int(idx), g.cols)
        rays(g, cy, cx, int(base + swing * (0.5 + 0.5 * np.sin(t * 7 + n * 1.7))), glint_tag)


LOOP = 18.0
CELL = (6, 10, 11)          # cell width, cell height, font px
GLOW = 0.6
TRAIL = 0.3

(RED, BODY, GOLD, BELLY, FIN1, FIN2, FIN3, RAY, IRIS, PUPIL, SHINE, LIP, BUBBLE, BEAM, GLINT, HILITE) = range(16)
TAG_COLOR = [[236, 64, 14], [255, 112, 20], [255, 196, 64], [255, 206, 128], [255, 124, 32], [255, 182, 100],
             [252, 242, 222], [255, 226, 180], [255, 196, 80], [40, 24, 20], [255, 255, 255], [255, 150, 110],
             [196, 226, 255], [255, 236, 190], [255, 250, 220], [255, 238, 150]]

look = camera(eye=(0, 0.05, 4.2), target=(0, 0.0, 0))
F = 2.9
DENS = 0.0065
LIGHT = np.array([-0.55, 0.7, 0.45]) / np.linalg.norm([-0.55, 0.7, 0.45])     # light from the upper left
LEVEL = 0.35              # overall light on the fish
rng = np.random.default_rng(11)

# side outline in pixel units, facing right
K, OX, OY = 0.8 / 368, 504, 225                     # 368 px = 0.8 units


def pts(a):
    a = np.array(a, float)
    return np.c_[(a[:, 0] - OX) * K, -(a[:, 1] - OY) * K]


TOP = pts([(688, 190), (670, 165), (640, 140), (600, 126), (540, 115), (470, 104), (420, 138), (370, 178), (320, 212)])
BOTTOM = pts([(688, 190), (684, 222), (660, 250), (620, 282), (570, 308), (510, 326), (450, 334), (400, 328),
              (360, 318), (320, 312)])
DORSAL = pts([(468, 104), (430, 60), (390, 30), (350, 10), (338, 40), (322, 90), (308, 140), (305, 168), (320, 195),
              (370, 178), (420, 138)])
TAIL = pts([(326, 210), (260, 212), (180, 215), (110, 225), (40, 245), (100, 265), (170, 285), (230, 300), (255, 318),
            (248, 360), (250, 420), (258, 480), (262, 525), (285, 470), (310, 410), (330, 355), (340, 314)])
PELVIC = pts([(470, 332), (455, 390), (440, 440), (416, 485), (405, 430), (402, 380), (410, 333)])
PECTORAL = pts([(540, 312), (520, 345), (498, 372), (488, 352), (505, 318)])
EYE = pts([(630, 195)])[0]
TAIL_ROOT = pts([(330, 262)])[0]
GILL_X = (560 - OX) * K                              # gill cover edge
X0, X1 = TOP[:, 0].min(), TOP[:, 0].max()           # tail stem, snout


def top_y(x):
    return np.interp(x, TOP[::-1, 0], TOP[::-1, 1])


def bottom_y(x):
    return np.interp(x, BOTTOM[::-1, 0], BOTTOM[::-1, 1])


def inside(poly, x, y):
    res = np.zeros(len(x), bool)
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        res ^= ((yi > y) != (yj > y)) & (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi)
        j = i
    return res


def fill(poly, step=DENS):
    lo, hi = poly.min(0) - 0.02, poly.max(0) + 0.02
    gx, gy = np.meshgrid(np.arange(lo[0], hi[0], step), np.arange(lo[1], hi[1], step))
    gx, gy = gx.ravel(), gy.ravel()
    k = inside(poly, gx, gy)
    return gx[k], gy[k], gx, gy


# body: outline swept in ellipses
_rows = []
for x in np.arange(X0, X1, DENS):
    hh = (top_y(x) - bottom_y(x)) / 2
    n = max(int(2 * np.pi * hh / DENS), 8)
    _rows.append(np.c_[np.full(n, x), np.linspace(0, 2 * np.pi, n, endpoint=False)])
BX, BT = np.concatenate(_rows).T
_mid = (top_y(BX) + bottom_y(BX)) / 2
_hh = (top_y(BX) - bottom_y(BX)) / 2
_hw = 0.8 * _hh * np.clip((X1 - BX) / 0.12, 0, 1) ** 0.5 + 0.004      # width = 0.8 x height
BODY_N = np.c_[np.zeros_like(BX), np.sin(BT) / _hh, np.cos(BT) / _hw]
BODY_N /= np.linalg.norm(BODY_N, axis=1, keepdims=True)
_ylocal = np.sin(BT)
_gill = GILL_X + 0.035 * (1 - _ylocal ** 2)
HEAD = BX > _gill
BODY_P = np.c_[BX, _mid + _hh * np.sin(BT), _hw * np.cos(BT)] + BODY_N * 0.007 * HEAD[:, None]   # gill cover raised
# scales: offset rows, bright at the edge
_sr, _sc = BX / 0.028, (BT / (2 * np.pi)) * 40
_sc = _sc + 0.5 * (np.floor(_sr) % 2)
SCALE_EDGE = np.clip(1 - np.hypot((_sr % 1) - 0.5, (_sc % 1) - 0.5) * 1.8, 0, 1)
SCALE_ID = (np.floor(_sr) * 131 + np.floor(_sc) * 17) % 97                 # scale index

def fin_parts(poly, root, seed):
    # filled outline; r = 0 at the root, 1 at the edge, a = angle around the root
    x, y, gx, gy = fill(poly)
    d = np.hypot(x - root[0], y - root[1])
    mean = np.arctan2((y - root[1]).mean(), (x - root[0]).mean())
    a = np.angle(np.exp(1j * (np.arctan2(y - root[1], x - root[0]) - mean)))
    bins = np.clip(((a - a.min()) / (np.ptp(a) + 1e-9) * 60).astype(int), 0, 59)
    reach = np.array([d[bins == k].max() if (bins == k).any() else d.max() for k in range(60)])
    r = d / reach[bins]
    edge = np.random.default_rng(seed).random(len(x))
    skin = ~((r > 0.86) & (edge < (r - 0.86) * 4.5))                       # ragged edge
    return np.c_[x[skin], y[skin]], r[skin], a[skin]


TAIL_SKIN, TAIL_R, TAIL_A = fin_parts(TAIL, TAIL_ROOT, 1)
DORS_ROOT = pts([(400, 150)])[0]
DORS_SKIN, DORS_R, DORS_A = fin_parts(DORSAL, DORS_ROOT, 2)
PELV_ROOT = pts([(440, 333)])[0]
PELV_SKIN, PELV_R, PELV_A = fin_parts(PELVIC, PELV_ROOT, 3)
PECT_ROOT = pts([(530, 315)])[0]
PECT_SKIN, PECT_R, PECT_A = fin_parts(PECTORAL, PECT_ROOT, 4)


_hh_ = rng.random((30, 2)) * 2 - 1
rng_hole = _hh_ / np.maximum(1, np.hypot(_hh_[:, 0], _hh_[:, 1]))[:, None]


def fin_tag(r):
    return np.where(r < 0.45, FIN1, np.where(r < 0.72, FIN2, FIN3))


def fish(t, tail_phase, push, bend, size, base_id):
    amp = 0.025 + 0.04 * push
    P, N, tags, part, shade, glow = [], [], [], [], [], []

    def add(p, n, tag, pid, sh, gl=0.0):
        P.append(p), N.append(n), part.append(np.full(len(p), -1 if pid is None else base_id + pid))
        tags.append(tag if isinstance(tag, np.ndarray) else np.full(len(p), tag))
        shade.append(np.broadcast_to(sh, len(p)).astype(float))
        glow.append(np.broadcast_to(gl, len(p)).astype(float))

    def wave(x):
        k = np.clip((X1 - x) / (X1 - X0), 0, 1.6)        # 0 at the snout, 1 at the tail stem
        return amp * k ** 2 * np.sin(tail_phase - 3.0 * k) + bend * 0.08 * k ** 2

    def flat(n_, s=1.0):
        return np.tile([0.0, 0.0, s], (n_, 1))

    def fin(skin_xy, r, a, n_rays, zf, pid, side=1.0, splay=None, shine_band=None, dim=1.0):
        # ray pattern from the root; splay() bends side fins out of the body plane
        sp = np.c_[skin_xy, zf(skin_xy[:, 0], skin_xy[:, 1], r)]
        if splay is not None:
            sp = splay(sp)
        u = (a - a.min()) / (np.ptp(a) + 1e-9)
        ray = np.clip(np.cos(u * (n_rays - 1) * 2 * np.pi), 0, 1) ** 10 * np.clip(r * 3, 0, 1) * dim
        tg = np.where(ray > 0.5, np.where(r < 0.55, FIN2, FIN3), fin_tag(r))
        solid = r < 0.62
        gl = shine_band(r, u) if shine_band is not None else np.zeros(len(r))
        add(sp[solid], flat(int(solid.sum()), side), tg[solid], pid, dim * (0.86 - 0.3 * r + 0.18 * ray)[solid], gl[solid])
        fade = np.clip(1 - (r - 0.62) / 0.45, 0, 1)         # outer part thins out
        keep = np.random.default_rng(pid).random(len(r)) < 0.15 + 0.8 * fade ** 1.2 + 0.2 * ray * fade
        tip = ~solid & keep
        add(sp[tip], flat(int(tip.sum()), side), np.where(r > 0.7, FIN2, tg)[tip], None,
            dim * (0.12 + 0.6 * fade ** 1.3 + 0.12 * ray * fade)[tip])

    # body colours: back, flank, belly; gill cover as a separate part
    p = BODY_P.copy()
    p[:, 2] += wave(p[:, 0])
    lit = np.clip(BODY_N @ LIGHT, 0, 1)
    flank = np.abs(np.cos(BT)) * np.clip(1 - np.abs(BX) / 0.42, 0, 1)
    tag = np.where(_ylocal > 0.55, RED, np.where(_ylocal < -0.62, BELLY,
                   np.where((flank > 0.45) & (SCALE_EDGE > 0.35), GOLD, BODY)))
    sh = 0.7 + 0.320222 * lit + 0.12 * SCALE_EDGE
    # shiny patch on the flank
    patch = np.exp(-((BX + 0.03) / 0.13) ** 2) * np.exp(-((_ylocal - 0.25) / 0.38) ** 2) * np.abs(np.cos(BT))
    add(p[~HEAD], BODY_N[~HEAD], tag[~HEAD], 0, sh[~HEAD], (patch * (0.3 + 0.7 * SCALE_EDGE))[~HEAD])
    add(p[HEAD], BODY_N[HEAD], np.where(_ylocal[HEAD] > 0.55, RED, BODY), 9, sh[HEAD] + 0.05)

    # mouth: lip ring that opens and closes
    gulp = 0.5 + 0.5 * np.sin(t * 4.2 + base_id)
    a, b = np.meshgrid(np.linspace(0, 2 * np.pi, 48, endpoint=False), np.linspace(0, 2 * np.pi, 10, endpoint=False))
    a, b = a.ravel(), b.ravel()
    my = (top_y(X1 - 0.02) + bottom_y(X1 - 0.02)) / 2 - 0.01
    ring = 0.012 + 0.012 * gulp
    lp = np.c_[X1 - 0.005 + 0.009 * np.sin(b), my + (ring + 0.009 * np.cos(b)) * np.cos(a), (ring + 0.009 * np.cos(b)) * np.sin(a)]
    add(lp, np.c_[np.sin(b), np.cos(b) * np.cos(a), np.cos(b) * np.sin(a)], LIP, 10, 0.95)
    if gulp > 0.35:
        hole = np.c_[np.full(30, X1 + 0.002), my + ring * 0.6 * rng_hole[:, 0], ring * 0.6 * rng_hole[:, 1]]
        add(hole, np.tile([1.0, 0, 0], (30, 1)), PUPIL, 11, 0.2)

    # eyes: iris, pupil, highlight
    a, b = np.meshgrid(np.linspace(0, 2 * np.pi, 80, endpoint=False), np.linspace(0, 1, 18))
    a, b = a.ravel(), b.ravel()
    ex, ey = EYE
    for side in (1, -1):
        hw = 0.8 * (top_y(ex) - bottom_y(ex)) / 2 * np.clip((X1 - ex) / 0.12, 0, 1) ** 0.5
        ez = hw * 1.0 + float(wave(np.array(ex)))
        rr = 0.05 * b
        th = 0.55                                                         # turned slightly forward
        d = np.array([np.sin(th), 0.0, side * np.cos(th)])
        ux = np.array([np.cos(th), 0.0, -side * np.sin(th)])
        w = 0.06 * np.sqrt(1 - b * b)
        pe = (np.array([ex, ey, side * ez]) + (rr * np.cos(a))[:, None] * ux + np.c_[0 * a, rr * np.sin(a), 0 * a]
              + w[:, None] * d)
        ne = 0.4 * (np.cos(a) * b)[:, None] * ux + np.c_[0 * a, 0.4 * np.sin(a) * b, 0 * a] + d
        ne /= np.linalg.norm(ne, axis=1, keepdims=True)
        glint = np.hypot(rr * np.cos(a) - 0.016, rr * np.sin(a) - 0.016) < 0.009
        tg = np.where(glint, SHINE, np.where(b < 0.55, PUPIL, IRIS))
        add(pe, ne, tg, 1 if side > 0 else 2, np.where(glint, 1.0, np.where(b < 0.55, 0.25, 1.0)))

    # tail: phase lag from root to tip, small flutter, sag when gliding
    z_root = float(wave(np.array(X0)))

    def tail_z(x, y, r):
        a_ = np.arctan2(y - TAIL_ROOT[1], x - TAIL_ROOT[0])
        return (z_root + (amp * 2.2 + bend * 0.22) * np.clip(r, 0, 1.1) ** 1.4 * np.sin(tail_phase - 3.0 - 2.2 * r)
                + 0.018 * r ** 2 * np.sin(t * 3.2 + a_ * 6))
    sag = lambda xy, r: np.c_[xy[:, 0], xy[:, 1] - 0.04 * r ** 2 * (1 - push)]
    fin(sag(TAIL_SKIN, TAIL_R), TAIL_R, TAIL_A, 30, tail_z, 3,
        1.0, None, lambda r, u: 0.45 * np.exp(-((r - 0.28) / 0.2) ** 2) * np.exp(-((u - 0.45) / 0.3) ** 2))

    fin(DORS_SKIN, DORS_R, DORS_A, 14, lambda x, y, r: wave(x) + 0.018 * r * np.sin(t * 2.3 - x * 18), 4)

    # pelvic and pectoral fins, both sides
    def spread(root, side, angle, z0):
        # hinge at the root, open away from the body
        def f(q):
            dy = q[:, 1] - root[1]
            return np.c_[q[:, 0], root[1] + dy * np.cos(angle), q[:, 2] + side * (z0 + np.abs(dy) * np.sin(angle))]
        return f
    for side, pid in ((1, 5), (-1, 6)):
        sw = 0.120222 * np.sin(t * 1.8 + side)
        fin(PELV_SKIN, PELV_R, PELV_A, 8, lambda x, y, r: wave(x), pid, side,
            spread(PELV_ROOT, side, 0.6 + sw, 0.03), dim=0.6)
        pd = (0.35 + 0.3 * push) * np.sin(t * (2.4 + 2.5 * push) + side)
        hw_p = 0.8 * (top_y(PECT_ROOT[0]) - bottom_y(PECT_ROOT[0])) / 2 * 0.7
        fin(PECT_SKIN, PECT_R, PECT_A, 7, lambda x, y, r: wave(x), pid + 2, side,
            spread(PECT_ROOT, side, 1.25 + 0.3 * pd, hw_p), dim=0.6)

    return (np.concatenate(P) * size, np.concatenate(N), np.concatenate(tags), np.concatenate(part),
            np.concatenate(shade), np.concatenate(glow))


# size, keyframes (t, x, y, z), yaw keyframes (t, yaw) or None = follow the velocity
FISH = [
    (1.0, [(-1.5, -2.9, -0.55, 0.3), (2.0, -1.0, -0.5, 0.45), (4.5, -0.45, -0.4, 0.6), (5.6, -0.3, -0.38, 0.75),
           (6.6, -0.2, -0.35, 0.75), (8.5, 0.4, 0.2, 0.5), (10.5, 1.0, 0.25, 0.2), (12.5, 1.8, 0.45, -0.1),
           (14.0, 3.2, 0.55, -0.4), (15.5, 3.4, 0.45, -0.6), (19.5, 0.7, 0.35, -0.6)],
     [(-1.5, 0.05), (4.5, -0.15), (5.4, -1.1), (6.6, -1.05), (7.4, -0.2), (10.5, 0.3), (14.0, 0.3), (15.2, 3.1),
      (19.5, 3.1)]),
    (0.55, [(-1.5, 2.6, 1.0, -1.8), (9.0, 0.3, 1.15, -1.9), (19.5, -2.4, 1.05, -1.8)], None),
    (0.8, [(-1.5, 3.2, -0.9, -0.4), (4.0, 2.4, -0.85, -0.4), (5.0, 1.2, -0.9, -0.3), (7.5, 0.55, -0.75, -0.3),
           (8.3, -0.7, -0.65, 0.0), (11.0, -1.1, -0.75, 0.1), (13.0, -1.0, -0.6, 0.3), (14.5, -0.4, -0.7, 0.6),
           (16.0, 0.6, -0.8, 0.4), (17.0, 1.3, -0.72, 0.2), (19.5, 1.9, -0.55, -0.2)], None),
    (0.5, [(-1.5, -3.2, -0.6, -2.2), (10.0, 0.5, -0.9, -2.4), (13.0, 1.2, -0.7, -2.2), (19.5, 3.3, -0.4, -2.0)], None),
    (0.55, [(-1.5, 2.6, 0.1, -1.6), (4.0, 1.0, 0.3, -1.7), (6.0, 0.7, 0.35, -1.7), (8.5, -0.9, 0.55, -1.8),
            (12.0, -1.5, 0.35, -1.8), (15.0, -2.2, 0.15, -1.9), (19.5, -3.6, 0.2, -1.9)], None),
    (1.05, [(-1.5, -3.0, 0.55, 0.4), (1.5, -1.4, 0.45, 0.5), (3.0, -0.9, 0.4, 0.5), (4.2, 0.6, 0.7, 0.3),
            (6.0, 2.0, 1.4, 0.0), (12.0, 3.6, 1.0, 0.0), (14.0, 2.0, 0.2, 0.6), (16.5, -0.5, 0.0, 0.8),
            (19.5, -2.0, -0.25, 0.7)], None),
]
_T = np.linspace(-1.5, 19.5, 4200)


def _hermite(keys, T):
    # cubic Hermite through the keyframes
    k = np.array(keys, float)
    kt, kv = k[:, 0], k[:, 1:]
    m = np.zeros_like(kv)
    m[1:-1] = (kv[2:] - kv[:-2]) / (kt[2:] - kt[:-2])[:, None]
    m[0], m[-1] = (kv[1] - kv[0]) / (kt[1] - kt[0]), (kv[-1] - kv[-2]) / (kt[-1] - kt[-2])
    for j in range(1, len(kv) - 1):                    # zero tangent at a pause
        if np.allclose(kv[j], kv[j - 1], atol=0.06) or np.allclose(kv[j], kv[j + 1], atol=0.06):
            m[j] = 0
    j = np.clip(np.searchsorted(kt, T) - 1, 0, len(kt) - 2)
    h = kt[j + 1] - kt[j]
    s = np.clip((T - kt[j]) / h, 0, 1)[:, None]
    h = h[:, None]
    return ((2 * s ** 3 - 3 * s ** 2 + 1) * kv[j] + (s ** 3 - 2 * s ** 2 + s) * h * m[j]
            + (-2 * s ** 3 + 3 * s ** 2) * kv[j + 1] + (s ** 3 - s ** 2) * h * m[j + 1])


def _path(i):
    size, keys, yaw_keys = FISH[i]
    pos = _hermite(keys, _T)
    hold = np.zeros_like(_T)
    if i == 0:                                         # small bob while facing the camera
        hold = np.clip((_T - 5.2) / 0.4, 0, 1) * np.clip((6.9 - _T) / 0.4, 0, 1)
        pos = pos + hold[:, None] * np.c_[0.0 * _T, 0.015 * np.sin(_T * 1.7), 0.0 * _T]
    v = np.gradient(pos, _T, axis=0)
    speed = np.linalg.norm(v, axis=1)
    push = np.clip((speed - 0.2) / 0.5, 0, 1)
    tail = np.concatenate([[0], np.cumsum((1.2 + 5.0 * push[1:] + 2.0 * speed[1:]) * np.diff(_T))]) * 2 * np.pi * 0.42 + i
    if yaw_keys is None:
        # heading from the velocity, averaged over 0.8 s
        sm = lambda c: np.convolve(np.pad(c, 80, mode="edge"), np.ones(161) / 161, mode="valid")
        yaw = np.unwrap(np.arctan2(-sm(v[:, 2]), sm(v[:, 0])))
    else:
        yaw = _hermite(yaw_keys, _T)[:, 0]
    pitch = np.clip(np.arctan2(v[:, 1], np.hypot(v[:, 0], v[:, 2]) + 0.15), -0.4, 0.4) * (1 - hold)
    return pos, push, tail, yaw, pitch


PATHS = [_path(i) for i in range(len(FISH))]


def where(i, t):
    pos, push, tail, yaw, pitch = PATHS[i]
    f = lambda a: np.interp(t, _T, a)
    return (np.array([f(pos[:, 0]), f(pos[:, 1]), f(pos[:, 2])]), f(push), f(tail), f(yaw), f(pitch))


def placed(i, t, P, N=None):
    pos, _, _, yaw, pitch = where(i, t)
    cp, sp_ = np.cos(pitch), np.sin(pitch)
    P = rot_y(np.c_[cp * P[:, 0] - sp_ * P[:, 1], sp_ * P[:, 0] + cp * P[:, 1], P[:, 2]], yaw) + pos
    if N is not None:
        N = rot_y(np.c_[cp * N[:, 0] - sp_ * N[:, 1], sp_ * N[:, 0] + cp * N[:, 1], N[:, 2]], yaw)
    return P, N


# bubbles
BUB = rng.random((30, 5))


def bubbles(t):
    out = []
    for j, (bx, by, bz, sp, sz) in enumerate(BUB):
        y = -1.35 + ((by + t * (0.05 + 0.06 * sp)) % 1) * 2.8
        out.append(((bx - 0.5) * 3.0 + 0.05 * np.sin(t * 2.3 + j), y, -1.0 + bz * 1.8))
    for i in range(len(FISH)):
        times = (6.0, 13.0) if i == 0 else [1.5 + i * 1.9 + k * 3.7 for k in range(5)]
        for t0 in times:
            for m in range(4):
                age = t - t0 - m * 0.22
                if 0 <= age < 3.0:
                    mouth, _ = placed(i, t0, np.array([[X1 + 0.02, 0.0, 0.0]]) * FISH[i][0])
                    out.append(tuple(mouth[0] + np.array([0.03 * np.sin(age * 5 + m), 0.3 * age + 0.05 * age ** 2, 0])))
    return np.array(out)


def scene(t):
    Ps, Ss, Ts, Ks = [], [], [], []
    for i in range(len(FISH)):
        pos, push, tail, yaw, pitch = where(i, t)
        bend = np.clip(where(i, t + 0.3)[3] - yaw, -0.4, 0.4) * 3
        P, N, tg, k, sh, gl = fish(t, tail, push, bend, FISH[i][0], 100 * i)
        P, N = placed(i, t, P, N)
        is_body = (k == 100 * i) | (k == 100 * i + 9)
        sh = np.where(is_body, sh * (0.740222 + 0.26 * np.clip(N[:, 2], 0, 1)), sh)     # darker toward the silhouette
        sh = sh * (0.82 + 0.45 * LEVEL)
        scale_id = np.zeros(len(P))
        nb = int(is_body.sum())
        scale_id[is_body] = np.resize(SCALE_ID, nb)
        flash = is_body & (np.sin(t * 5 + scale_id * 2.3) > 0.97) & (N[:, 2] > 0.3)          # scale flashes
        tg = np.where(flash, GLINT, tg)
        # specular highlight on the scale edges
        H = LIGHT + np.array([0, 0, 1.0])
        H /= np.linalg.norm(H)
        sedge = np.zeros(len(P))
        sedge[is_body] = np.resize(SCALE_EDGE, nb)
        spec = np.clip(N @ H, 0, 1) ** 22 * is_body * (0.3 + 0.7 * sedge)
        g = np.clip(gl * (0.75 + 0.5 * LEVEL) + spec, 0, 1)
        sh = sh + 0.7 * g
        tg = np.where(~flash & (g > 0.4), np.where((g > 0.85) & (sedge > 0.8), GLINT, HILITE), tg)
        Ps.append(P), Ss.append(np.where(flash, 1.0, sh)), Ts.append(tg), Ks.append(k)
    b = bubbles(t)
    Ps.append(b), Ss.append(np.full(len(b), 0.8)), Ts.append(np.full(len(b), BUBBLE)), Ks.append(-np.ones(len(b), int))
    info = {"fish": len(FISH), "push": float(where(0, t)[1])}
    return np.concatenate(Ps), np.concatenate(Ss), np.concatenate(Ts), np.concatenate(Ks), info


def particle(ft, fs, fi, fj):
    fin = np.where(fs > 0.45, AT["+"], np.where(fs > 0.3, AT[":"], AT["."]))
    return np.where(ft == BUBBLE, AT["o"], fin)


def frame(t, cols, rows, aspect):
    P, shade, tag, part, info = scene(t)
    g = raster(t, cols, rows, aspect, P, shade, tag, part, look, F=F, gap=0.025, glints=[GLINT],
               edge_min=0.6, inner=lambda l: np.clip(0.2 + 0.85 * l, 0.15, 1), particle=particle)
    starbursts(g, t, GLINT, count=6, base=1, swing=3)
    return g.char, g.lum, g.tag, info, g.count


def HUD(info):
    return f"fish {info['fish']}   push {info['push']:.2f}"


# window

TITLE = "GOLDFISH · JIN2"
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
                pygame.image.save(screen, str(Path(__file__).with_name(f"goldfish_{int(time.time())}.png")))
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
        screen.blit(small.render(SIGN, True, (120, 112, 128)), (64, y - 26))
        screen.blit(small.render(HUD(info), True, DIM), (64, y))
        screen.blit(small.render(f"letters {count:05,d}", True, DIM), (64, y + 26))
        tt = small.render(f"{'●' if int(t * 2) % 2 == 0 else ' '} t {t:05.2f}s", True, PINK)
        screen.blit(tt, (W - 64 - tt.get_width(), 30))
        window.blit(screen if size == (W, H) else pygame.transform.smoothscale(screen, size), (0, 0))
        pygame.display.flip()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())

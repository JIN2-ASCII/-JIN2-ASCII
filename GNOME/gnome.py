# GNOME
# JIN2 · @jin_22ee · 2026. Free for learning and personal projects. See LICENSE.txt.
# Don't repost it or sell it as your own, and don't use it with AI.
#
# run:   pip install -r requirements.txt
#        python gnome.py
# keys:  Space pause · R restart · S screenshot · Esc quit

import sys
import time
from pathlib import Path

import numpy as np
import pygame

# letters, dark to bright
POOLS = ["1il!;:", "rtfjcvxz=+", "aeoun0{}[]<>", "08B$#&%Q"]
CHARS = " .,:~+*^01|/\\-_#()x" + "".join(POOLS)
AT = {c: i for i, c in enumerate(CHARS)}
FILL = np.array([[AT[p[k % len(p)]] for k in range(12)] for p in POOLS])

LOOP = 18.0
TRAIL = 0.3
CELL = (7, 11, 12)         # cell width, cell height, font px

PRINT, RED, REDDARK, BEARD, NOSE, BOOT, POM, FLAKE, LAMP, METAL, KNIT, FLAME = range(12)
TAG_COLOR = [[236, 240, 250], [238, 72, 84], [150, 36, 50], [240, 238, 234], [238, 166, 148], [124, 90, 68],
             [250, 250, 250], [255, 255, 255], [255, 204, 110], [128, 116, 110], [246, 246, 250], [255, 246, 214]]

EYE, TARGET = np.array([0, 0.3, 4.2]), np.array([0, -0.35, 0])
F = 2.9
GROUND = -0.8
SCALE = 1.05
STEP = 0.005
DENS = 0.0065              # spacing of the points on the gnome's surfaces
LIGHT = np.array([-0.5, 0.6, 0.65]) / np.linalg.norm([-0.5, 0.6, 0.65])
rng = np.random.default_rng(7)

# timeline, in seconds
PEEK = 1.0                 # starts sliding out from the right edge
PEEK_HOLD = (2.8, 3.5)     # stops half way and turns its head to look at us
PEEK_DONE = 4.7            # then slides the rest of the way out
PEEK_Z = -1.0              # it peeks from further back, so walking forward makes it bigger
APPROACH = (4.9, 6.7)      # walks to the middle, coming closer
CENTER = (0.0, 0.75)       # (x, z) where it says hello
WAVE = (6.9, 8.9)
SHY = (9.1, 10.5)          # glances left and right
OUT = 10.7                 # turns all the way round, its back to us
WALK = 11.3                # walks away to the back left and leaves the screen
EDGE_X = (4.2 - PEEK_Z) / 2.9   # right edge of the screen at the depth it peeks from
WALK_END = 17.8
STEP_T = 0.2               # time per step


def smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def blend(a, b, u):
    u = smooth(u)
    return a * (1 - u) + b * u


def go(u):
    # starts slowly and slows down again before it stops
    u = np.clip(u, 0, 1)
    return 1 - (1 - u ** 1.3) ** 3


# the way out: a curve to the back left with a little wander, walked at an even pace
_u = np.linspace(0, 1, 800)[:, None]
_B = np.array([[CENTER[0], CENTER[1]], [-0.7, -0.8], [-2.2, -3.5], [-5.4, -7.5]])
_c = (1 - _u) ** 3 * _B[0] + 3 * (1 - _u) ** 2 * _u * _B[1] + 3 * (1 - _u) * _u ** 2 * _B[2] + _u ** 3 * _B[3]
_tg = np.gradient(_c, axis=0)
_tg /= np.linalg.norm(_tg, axis=1, keepdims=True)
_c = _c + np.c_[-_tg[:, 1], _tg[:, 0]] * (0.12 * np.sin(_u * 2 * np.pi * 2.5))
_L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(_c, axis=0), axis=1))]
_L /= _L[-1]
_tg = np.gradient(_c, axis=0)
_tg /= np.linalg.norm(_tg, axis=1, keepdims=True)


def path_at(v):
    # position and direction at fraction v of the way
    return (np.interp(v, _L, _c[:, 0]), np.interp(v, _L, _c[:, 1]),
            np.array([np.interp(v, _L, _tg[:, 0]), np.interp(v, _L, _tg[:, 1])]))


def grid_in(x0, x1, y0, y1, step):
    xs, ys = np.meshgrid(np.arange(x0, x1, step), np.arange(y0, y1, step))
    return xs.ravel(), ys.ravel()


def rect(x0, x1, y0, y1, step=STEP):
    x, y = grid_in(x0, x1, y0, y1, step)
    return x, y, (x - (x0 + x1) / 2) / ((x1 - x0) / 2) * 0.6, (y - (y0 + y1) / 2) / ((y1 - y0) / 2) * 0.6


# one footprint: a small oval lying flat on the ground
px_, pz_ = grid_in(-0.05, 0.05, -0.08, 0.08, 0.006)
k_ = (px_ / 0.05) ** 2 + (pz_ / 0.08) ** 2 <= 1
PRINT_XZ = np.c_[px_[k_], pz_[k_]]
PRINT_RIM = np.sqrt((PRINT_XZ[:, 0] / 0.05) ** 2 + (PRINT_XZ[:, 1] / 0.08) ** 2)


# the gnome: x right, y up (feet at 0), z toward us when it faces us
def ellipsoid(c, r, step=DENS):
    # evenly spaced points over an egg shape, with their surface normals
    out, R = [], max(r)
    for p in np.linspace(0, np.pi, max(int(np.pi * R / step), 4)):
        rho = np.sin(p) * max(r[0], r[2])
        n = max(int(2 * np.pi * rho / step), 6)
        th = np.linspace(0, 2 * np.pi, n, endpoint=False)
        out.append(np.c_[r[0] * np.sin(p) * np.cos(th), np.full(n, r[1] * np.cos(p)), r[2] * np.sin(p) * np.sin(th), th])
    e = np.concatenate(out)
    nrm = e[:, :3] / np.array(r) ** 2
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
    return e[:, :3] + c, nrm, e[:, 3]


COAT_P, COAT_N, COAT_TH = ellipsoid((0, 0.2, 0), (0.2, 0.17, 0.18))
# white knit pattern all the way round the coat: a line, a zigzag, a row of dots, a line
_y = COAT_P[:, 1]
_arc = ((COAT_TH - np.pi / 2 + np.pi) % (2 * np.pi) - np.pi) * np.hypot(COAT_P[:, 0], COAT_P[:, 2])
_zig = 0.105 + 0.04 * np.abs(((_arc * 16) % 2) - 1)
_dots = (((_arc + 0.035) % 0.07) - 0.035) ** 2 + (_y - 0.205) ** 2 <= 0.016 ** 2
COAT_KNIT = (np.abs(_y - 0.07) < 0.011) | (np.abs(_y - _zig) < 0.012) | _dots | (np.abs(_y - 0.245) < 0.009)

HEAD_P, HEAD_N, _ = ellipsoid((0, 0.47, 0), (0.16, 0.16, 0.16))           # white hair shows at the back
NOSE_P, NOSE_N, _ = ellipsoid((0, 0.455, 0.25), (0.066, 0.058, 0.062))   # pokes out under the hat
MITT_P, MITT_N, _ = ellipsoid((0, 0, 0), (0.055, 0.06, 0.055))
BOOT_P, BOOT_N, _ = ellipsoid((0, 0.04, 0.03), (0.075, 0.045, 0.1))
POM_P, POM_N, _ = ellipsoid((0, 0, 0), (0.066, 0.066, 0.066))
_fl = 1 + 0.14 * np.sin(np.arctan2(POM_P[:, 1], POM_P[:, 0]) * 9) * np.cos(np.arctan2(POM_P[:, 2], POM_P[:, 0]) * 7)
POM_P = POM_P * _fl[:, None]                                             # fluffy

# beard: a curved sheet round the front of the face and body, pointed at the bottom
BEARD_TOP = 0.47
_a, _by = np.meshgrid(np.linspace(-1.25, 1.25, 96), np.arange(0.03, BEARD_TOP, 0.0055))
_a, _by = _a.ravel(), _by.ravel()
_q = (_by - 0.03) / (BEARD_TOP - 0.03)
_bw = 0.205 * _q ** 0.55
_dep = 0.2 * _q ** 0.4 + 0.02
BEARD_P = np.c_[_bw * np.sin(_a), _by, 0.02 + 0.1 * (1 - _q) + _dep * np.cos(_a)]
BEARD_N = np.c_[np.sin(_a), np.full(len(_a), -0.15), np.cos(_a)]
BEARD_N /= np.linalg.norm(BEARD_N, axis=1, keepdims=True)
STRAND = 0.13 * np.sin(_a * _bw * 95 + np.sin(_by * 14) * 2)               # combed lines

# hat: a tall cone round a bent spine, made of rings, with a rolled rim over the eyes
HAT_BASE, HAT_LEN, HAT_R = 0.43, 1.0, 0.235
_rings = []
for s in np.arange(0, 1, DENS / HAT_LEN):
    w = HAT_R * (1 - s) ** 1.1
    n = max(int(2 * np.pi * w / DENS), 6)
    _rings.append(np.c_[np.full(n, s), np.linspace(0, 2 * np.pi, n, endpoint=False)])
HAT_S, HAT_TH = np.concatenate(_rings).T
_b, _t = np.meshgrid(np.linspace(0, 2 * np.pi, 24, endpoint=False), np.linspace(0, 2 * np.pi, 240, endpoint=False))
_b, _t = _b.ravel(), _t.ravel()
RIM_P = np.c_[(HAT_R + 0.028 * np.cos(_b)) * np.cos(_t), HAT_BASE + 0.028 * np.sin(_b), (HAT_R + 0.028 * np.cos(_b)) * np.sin(_t)]
RIM_N = np.c_[np.cos(_b) * np.cos(_t), np.sin(_b), np.cos(_b) * np.sin(_t)]

# the lantern hangs from the hand (hand at 0, 0)
LS = 1.35                                                     # lantern size
rx_, ry_ = grid_in(-0.03, 0.03, -0.04, 0.02, 0.004)          # ring handle
k_ = np.abs(np.hypot(rx_, ry_ + 0.01) - 0.022) < 0.006
RING = (rx_[k_], ry_[k_], rx_[k_] * 0, ry_[k_] * 0)
cx_, cy_ = grid_in(-0.08, 0.08, -0.095, -0.03, STEP)         # pointed roof
k_ = np.abs(cx_) <= 0.004 + 0.075 * (-0.035 - cy_) / 0.06
ROOF = (cx_[k_], cy_[k_], cx_[k_] / 0.08 * 0.6, np.full(k_.sum(), 0.3))
fx_, fy_ = grid_in(-0.025, 0.025, -0.215, -0.12, 0.004)      # candle flame
k_ = (fx_ / (0.02 * np.clip((fy_ + 0.215) / 0.035, 0, 1) ** 0.5 * np.clip((-0.12 - fy_) / 0.06, 0, 1) ** 0.7 + 1e-6)) ** 2 <= 1
FLAME_XY = (fx_[k_], fy_[k_], fx_[k_] * 0, fy_[k_] * 0)
LANTERN = [   # (x, y, dx, dy), tag, part id, z in front of the glass
    (RING, METAL, 21, 0.0),
    (ROOF, METAL, 22, 0.0),
    (rect(-0.085, 0.085, -0.108, -0.093), METAL, 25, 0.01),
    (rect(-0.065, 0.065, -0.228, -0.108), LAMP, 23, 0.0),
    (rect(-0.069, -0.057, -0.228, -0.108), METAL, 26, 0.02),   # corner posts
    (rect(0.057, 0.069, -0.228, -0.108), METAL, 27, 0.02),
    (FLAME_XY, FLAME, 28, 0.01),
    (rect(-0.08, 0.08, -0.25, -0.228), METAL, 24, 0.01),
]
LANTERN = [((a * LS, b * LS, c, d), tag, pid, zz) for (a, b, c, d), tag, pid, zz in LANTERN]
LAMP_C = np.array([0.0, -0.17 * LS])

_US = np.linspace(0, 1, 400)
SEGS = [(APPROACH[0], APPROACH[1], STEP_T)]   # (start, end, time per step) where it walks with slowing steps


def seg_steps(t):
    # steps taken so far in the current stretch, following how far it has moved
    for a, b, st in SEGS:
        if a < t < b:
            return go((t - a) / (b - a)) * (b - a) / st
    return None


def facing(t):
    # which way the gnome faces: 0 = at us, negative = turned toward the left of the screen
    walk_dir = path_at(np.clip((t - WALK) / (WALK_END - WALK), 0, 1))[2]
    phw = np.arctan2(walk_dir[0], walk_dir[1])
    phw = phw - 2 * np.pi if phw > 0 else phw
    pa = np.arctan2(CENTER[0] - (EDGE_X - 0.35), CENTER[1] - PEEK_Z)
    ph = -0.35
    ph = blend(ph, pa, (t - APPROACH[0]) / 0.4)
    ph = blend(ph, 0.0, (t - APPROACH[1] + 0.2) / 0.5)
    return blend(ph, phw, (t - OUT) / 0.6)


def state(t):
    # where the gnome is and what it is doing at time t
    hide, mid, peek = EDGE_X + 0.5, EDGE_X + 0.05, EDGE_X - 0.35
    z = PEEK_Z
    if t < PEEK:
        x = hide
    elif t < PEEK_HOLD[0]:
        x = hide + (mid - hide) * go((t - PEEK) / (PEEK_HOLD[0] - PEEK))
    elif t < PEEK_HOLD[1]:
        x = mid
    elif t < APPROACH[0]:
        x = mid + (peek - mid) * go((t - PEEK_HOLD[1]) / (PEEK_DONE - PEEK_HOLD[1]))
    elif t < WALK:
        u = go((t - APPROACH[0]) / (APPROACH[1] - APPROACH[0]))
        x, z = peek + (CENTER[0] - peek) * u, PEEK_Z + (CENTER[1] - PEEK_Z) * u
    else:
        x, z, _ = path_at(np.clip((t - WALK) / (WALK_END - WALK), 0, 1))
    wave = smooth((t - WAVE[0]) / 0.3) * (1 - smooth((t - WAVE[1]) / 0.3))
    keys = SHY[0] + (SHY[1] - SHY[0]) * np.array([0.1, 0.3, 0.5, 0.65, 0.85, 1.0])
    glance = np.interp(t, keys, [0, -1, -1, 1, 1, 0]) if SHY[0] < t < SHY[1] else 0.0
    look_us = smooth((t - PEEK_HOLD[0]) / 0.25) * (1 - smooth((t - PEEK_HOLD[1] + 0.1) / 0.25))
    walking = APPROACH[0] < t < APPROACH[1] or OUT < t < WALK_END
    lean = smooth((t - PEEK) / 0.8) * (1 - smooth((t - APPROACH[0]) / 0.5))
    ss = seg_steps(t)
    ph = ss if ss is not None else (t - OUT) / STEP_T if walking else 0.0
    hold = 1 - smooth((t - APPROACH[1] + 0.3) / 0.4) * (1 - smooth((t - OUT) / 0.5))   # lantern held out in front
    return x, z, wave, glance, look_us, walking, ph, facing(t), hold, lean


def footprints(t):
    # a print where each step lands; they stay
    out = []
    times = []
    for a, b, st in SEGS:
        n = (b - a) / st
        times.append(a + (b - a) * np.interp(np.arange(1, int(n) + 1), go(_US) * n, _US))
    times = np.r_[np.concatenate(times), np.arange(WALK + STEP_T, WALK_END, STEP_T)]
    for k, tk in enumerate(times):
        if tk > t:
            break
        x, z = state(tk)[:2]
        x1, z1 = state(tk + 0.05)[:2]
        h = np.array([x1 - x, z1 - z])
        h = h / np.linalg.norm(h) if np.linalg.norm(h) > 1e-6 else np.array([-1.0, 0.0])
        n = np.array([-h[1], h[0]])
        side = -1 if k % 2 == 0 else 1
        if x < EDGE_X - 0.05:
            out.append((x + side * 0.06 * SCALE * n[0], z + side * 0.06 * SCALE * n[1], h, n))
    return out


def yaw(P, N, a, pivot=(0, 0, 0)):
    # turn points and normals round the vertical axis
    c, s = np.cos(a), np.sin(a)
    Q = P - pivot
    Q = np.c_[c * Q[:, 0] + s * Q[:, 2], Q[:, 1], -s * Q[:, 0] + c * Q[:, 2]] + pivot
    N = np.c_[c * N[:, 0] + s * N[:, 2], N[:, 1], -s * N[:, 0] + c * N[:, 2]]
    return Q, N


def gnome(t):
    x0, z0w, wave, glance, look_us, walking, ph, phi, hold, lean = state(t)
    sd = np.sin(np.pi * ph) if walking else 0.0
    bob = 0.025 * abs(sd)
    sway = 0.05 * sd + 0.2 * lean
    wobble = 0.22 * np.sin(np.pi * ph + 0.9) if walking else 0.0         # the hat swings with every step
    head_turn = 0.45 * glance + 0.35 * look_us
    P, N, tags, part, tex = [], [], [], [], []

    def add(p, n, tag, pid, tx=0.0, head=False):
        if head:
            p, n = yaw(p, n, head_turn, (0, 0.47, 0))
        P.append(p), N.append(n), part.append(np.full(len(p), pid))
        tags.append(tag if isinstance(tag, np.ndarray) else np.full(len(p), tag))
        tex.append(np.broadcast_to(tx, len(p)).astype(float))

    for side, pid in ((-1, 10), (1, 11)):                       # boots take turns
        up = 0.04 * max(sd, 0) if walking and ((int(ph) % 2 == 0) == (side < 0)) else 0.0
        fwd = 0.05 * sd * side if walking else 0.0
        add(BOOT_P + [side * 0.1, up, fwd], BOOT_N, BOOT, pid)
    add(COAT_P, COAT_N, np.where(COAT_KNIT, KNIT, REDDARK), 12, np.where(COAT_KNIT, 0.35, 0.0))
    add(HEAD_P, HEAD_N, BEARD, 29, 0.0, head=True)
    # the left hand swings up from the shoulder to wave; the right one holds the lantern
    wv = np.sin((t - WAVE[0]) * 11)
    SH, ARM = np.array([0.17, 0.32, 0.02]), 0.18
    ang = np.radians(-62 + (112 + 18 * wv) * wave)
    mw = SH + ARM * np.array([np.cos(ang), np.sin(ang), 0]) + [0, 0, 0.06 + 0.06 * wave - 0.05 * sd]
    mr = blend(np.array([-0.3, 0.37, 0.08]), np.array([-0.08, 0.37, 0.24]), hold) + [0, 0, 0.03 * sd]
    add(MITT_P + mw, MITT_N, RED, 13)
    add(MITT_P + mr, MITT_N, RED, 14)
    if wave > 0.05:                                             # sleeve from shoulder to mitten
        a = np.linspace(0, 1, 60)[:, None]
        b = np.linspace(0, 2 * np.pi, 30, endpoint=False)
        ax = (mw - SH) / np.linalg.norm(mw - SH)
        u1 = np.cross(ax, [0, 0, 1.0])
        u1 /= np.linalg.norm(u1)
        u2 = np.cross(ax, u1)
        ring = np.cos(b)[:, None] * u1 + np.sin(b)[:, None] * u2
        sp = (SH + (mw - SH) * a)[:, None, :] + 0.04 * ring[None]
        add(sp.reshape(-1, 3), np.tile(ring, (60, 1)), REDDARK, 19)
    add(BEARD_P, BEARD_N, BEARD, 16, STRAND, head=True)
    add(NOSE_P, NOSE_N, NOSE, 15, 0.0, head=True)
    bend = -0.1 + 0.12 * glance + wobble
    droop = 0.18 + 0.05 * abs(glance) + 0.07 * abs(wobble)
    s, th = HAT_S, HAT_TH
    w = HAT_R * (1 - s) ** 1.1
    spine = np.c_[bend * s ** 2.4, HAT_BASE + HAT_LEN * s - droop * s ** 3, -0.12 * s ** 2]
    hp = spine + np.c_[w * np.cos(th), 0 * s, w * np.sin(th)]
    hn = np.c_[np.cos(th), np.full(len(s), 0.25), np.sin(th)]
    hn /= np.linalg.norm(hn, axis=1, keepdims=True)
    add(hp, hn, RED, 20, 0.12 + 0.04 * np.sin(hp[:, 1] * 40), head=True)
    add(RIM_P, RIM_N, RED, 20, 0.12, head=True)
    tip = np.array([bend, HAT_BASE + HAT_LEN - droop, -0.12])
    add(POM_P + tip, POM_N, POM, 18, 0.0, head=True)

    P, N = np.concatenate(P), np.concatenate(N)
    P, N = yaw(P, N, phi)
    mr_w = yaw(mr[None], np.zeros((1, 3)), phi)[0][0]
    c, sn = np.cos(sway), np.sin(sway)
    P = np.c_[c * P[:, 0] - sn * P[:, 1], sn * P[:, 0] + c * P[:, 1], P[:, 2]]
    mr_w = np.array([c * mr_w[0] - sn * mr_w[1], sn * mr_w[0] + c * mr_w[1], mr_w[2]])
    shade = 0.34 + 0.620222 * np.clip(N @ LIGHT, 0, 1) + np.concatenate(tex)
    tags, part = np.concatenate(tags), np.concatenate(part)

    # the lantern swings a little all the time and more while walking
    swing = 0.12 * np.sin(t * 2.300222) + (0.3 * np.sin(np.pi * ph * 0.5) if walking else 0.0)
    cs, sw = np.cos(swing), np.sin(swing)
    fl = 0.85 + 0.15 * np.sin(t * 13.100222) * np.sin(t * 7.7)          # candle flicker
    LP, LS_, LT, LK = [], [], [], []
    for (lx, ly, dx, dy), tag, pid, zz in LANTERN:
        nz = np.sqrt(np.clip(1 - dx * dx - dy * dy, 0, 1))
        n = np.c_[dx, dy, nz + 0.3]
        n /= np.linalg.norm(n, axis=1, keepdims=True)
        tx = 0.0
        if tag == LAMP:
            d = np.sqrt((lx / 0.088) ** 2 + ((ly - LAMP_C[1]) / 0.09) ** 2)
            tx = (0.35 + 0.45 * np.clip(1 - d, 0, 1)) * fl
        elif tag == FLAME:
            tx = 0.6 * fl
        LP.append(np.c_[cs * lx - sw * ly + mr_w[0], sw * lx + cs * ly + mr_w[1], np.full(len(lx), mr_w[2] + zz)])
        LS_.append(0.34 + 0.62 * np.clip(n @ LIGHT, 0, 1) + tx)
        LT.append(np.full(len(lx), tag)), LK.append(np.full(len(lx), pid))
    lamp = mr_w[:2] + [cs * LAMP_C[0] - sw * LAMP_C[1], sw * LAMP_C[0] + cs * LAMP_C[1]]
    P = np.concatenate([P, np.concatenate(LP)])
    shade = np.concatenate([shade, np.concatenate(LS_)])
    tags, part = np.concatenate([tags, np.concatenate(LT)]), np.concatenate([part, np.concatenate(LK)])

    W_ = np.c_[x0 + P[:, 0] * SCALE, GROUND + (P[:, 1] + bob) * SCALE, z0w + P[:, 2] * SCALE]
    info = {"x": x0, "z": z0w, "steps": len(footprints(t)), "fl": fl,
            "lamp": (x0 + lamp[0] * SCALE, GROUND + (lamp[1] + bob) * SCALE, z0w + mr_w[2] * SCALE),
            "doing": "hiding" if t < PEEK else "peek" if t < APPROACH[0] else "hello" if wave > 0.5 else
                     "shy" if t < OUT else "toddle" if t < WALK_END else "gone"}
    return W_, shade, tags, part, info


FLAKES = rng.random((150, 4))
hr_, th_ = np.sqrt(rng.random(26000)), rng.random(26000) * 2 * np.pi
k_ = rng.random(26000) < (1 - hr_) ** 1.6
GLOW_XY, GLOW_R = np.c_[hr_ * np.cos(th_), hr_ * np.sin(th_)][k_], hr_[k_]


def scene(t):
    P, shade, tag, part, info = gnome(t)
    # lantern light: what is near it gets brighter, a halo behind it, a pool on the snow
    lx, ly, lz = info["lamp"]
    fl = info["fl"]
    d2 = (P[:, 0] - lx) ** 2 + (P[:, 1] - ly) ** 2
    shade = shade + 0.35 * np.exp(-d2 / 0.06) * fl
    halo = np.c_[lx + GLOW_XY[:, 0] * 0.95, ly + GLOW_XY[:, 1] * 0.95, np.full(len(GLOW_R), lz - 0.3)]
    pool = np.c_[lx + GLOW_XY[:, 0] * 0.9, np.full(len(GLOW_R), GROUND), lz + GLOW_XY[:, 1] * 0.45]
    lit = smooth((ly - GROUND) / 0.05)
    P = np.concatenate([P, halo, pool])
    shade = np.concatenate([shade, 1.0 * (1 - GLOW_R) ** 1.2 * fl, 0.7 * lit * (1 - GLOW_R) ** 2 * fl])
    tag = np.concatenate([tag, np.full(2 * len(GLOW_R), LAMP)])
    part = np.concatenate([part, -np.ones(2 * len(GLOW_R), int)])
    # white footprints, each turned the way it was walking
    prints = footprints(t)
    if prints:
        fp = np.concatenate([np.c_[fx + PRINT_XZ[:, 0] * n[0] + PRINT_XZ[:, 1] * h[0], np.full(len(PRINT_XZ), GROUND),
                                   fz + PRINT_XZ[:, 0] * n[1] + PRINT_XZ[:, 1] * h[1]]
                             for fx, fz, h, n in prints])
        P = np.concatenate([fp, P])
        shade = np.concatenate([np.tile(0.85 + 0.15 * (PRINT_RIM > 0.75), len(prints)), shade])
        tag = np.concatenate([np.full(len(fp), PRINT), tag])
        part = np.concatenate([np.repeat(100 + np.arange(len(prints)), len(PRINT_XZ)), part])
    # falling snow
    f = FLAKES
    fy = 1.4 - ((f[:, 1] + t * (0.08 + 0.06 * f[:, 3])) % 1) * 2.4
    fxs = (f[:, 0] - 0.5) * 3.2 + 0.05 * np.sin(t * 1.3 + f[:, 2] * 20)
    fp = np.c_[fxs, fy, -0.4 + f[:, 2] * 1.8]
    on = smooth((t - 0.5) / 1.5) * (0.3 + 0.4 * f[:, 3])
    P = np.concatenate([P, fp])
    shade = np.concatenate([shade, on])
    tag = np.concatenate([tag, np.full(len(fp), FLAKE)])
    part = np.concatenate([part, -np.ones(len(fp), int)])
    return P, shade, tag, part, info


# camera
_fwd = (TARGET - EYE) / np.linalg.norm(TARGET - EYE)
_right = np.cross(_fwd, [0, 1.0, 0])
_right /= np.linalg.norm(_right)
_up = np.cross(_right, _fwd)


def outline_letter(gx, gy):
    ax, ay = np.abs(gx), np.abs(gy)
    c = np.where(ax > 2 * ay, AT["|"], np.where(ay > 2 * ax, np.where(gy > 0, AT["_"], AT["-"]),
                 np.where(gx * gy > 0, AT["/"], AT["\\"])))
    return np.where((ax + ay) == 0, AT["+"], c)


def frame(t, cols, rows, aspect):
    # project the points onto the letter grid
    P, shade, T, K, info = scene(t)
    rel = P - EYE
    x, y, z = rel @ _right, rel @ _up, rel @ _fwd
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
            out = body & ((nb < 0) | ((nb != part) & (nz > depth + 0.01)))
            gx += dx * out
            gy += dy * out
            if dx == 0 or dy == 0:
                edge |= out

    r, c = np.mgrid[0:rows, 0:cols]
    h = (r * 7919 + c * 104729) % 9973
    level = np.clip((lum * 3.2).astype(int), 0, 3)
    fill = FILL[level, (h + (t * 4 + h % 11).astype(int)) % 12]   # inside letters keep changing
    char = np.where(body, np.where(edge, outline_letter(gx, gy), fill), 0)
    lum = np.where(body, np.where(edge, np.maximum(0.6, lum), np.clip(0.18 + 0.85 * lum, 0.15, 1)), 0)

    # light and snow go only where nothing solid is in front
    fx = ok & (K < 0) & (shade > 0.02)
    hidden = body[iy[fx], ix[fx]] & (depth[iy[fx], ix[fx]] < z[fx])
    fi, fj, fs, ft = (a[fx][~hidden] for a in (iy, ix, shade, T))
    keep = ~body[fi, fj]
    fi, fj, fs, ft = fi[keep], fj[keep], fs[keep], ft[keep]
    char[fi, fj] = np.where(fs > 0.7, AT["*"], np.where(fs > 0.35, AT["+"], AT["."]))
    lum[fi, fj], tag[fi, fj] = np.clip(fs, 0, 1), ft
    return char, lum, tag, info, int(body.sum())


def HUD(info):
    return f"gnome x {info['x']:+.2f} z {info['z']:+.2f}   steps {info['steps']:02d}   {info['doing']}"


# window

TITLE = "GNOME · JIN2"
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

    def draw(self, t):
        char, lum, tag, info, count = frame(t, COLS, ROWS, ASPECT)
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


def main():
    pygame.init()
    size = window_size()
    window = pygame.display.set_mode(size)
    pygame.display.set_caption(TITLE)
    screen = pygame.Surface((W, H))
    small = pygame.font.SysFont("consolas,menlo,dejavusansmono,couriernew,monospace", 17)
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
                pygame.image.save(screen, str(Path(__file__).with_name(f"gnome_{int(time.time())}.png")))
        dt = clock.tick(30) / 1000
        if not paused:
            t += min(dt, 1 / 15)
            if t > LOOP:
                t = 0.0
                canvas.reset()
            art, info, count = canvas.draw(t)
        screen.fill((0, 0, 0))
        screen.blit(art, (0, 0))
        screen.blit(glow_layer(blur(art, 4, 5), 0.75), (0, 0), special_flags=pygame.BLEND_ADD)
        screen.blit(glow_layer(blur(art, 8, 22), 0.45), (0, 0), special_flags=pygame.BLEND_ADD)
        y = H - 70
        screen.blit(small.render(SIGN, True, (120, 112, 128)), (64, y - 26))
        screen.blit(small.render(HUD(info), True, DIM), (64, y))
        screen.blit(small.render(f"letters {count:05,d}", True, DIM), (64, y + 26))
        tt = small.render(f"{'●' if int(t * 2) % 2 == 0 else ' '} t {t:05.2f}s", True, PINK)
        screen.blit(tt, (W - 64 - tt.get_width(), 30))
        window.blit(screen if size == (W, H) else pygame.transform.smoothscale(screen, size), (0, 0))
        pygame.display.flip()


if __name__ == "__main__":
    sys.exit(main())

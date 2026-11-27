# BUTTERFLY
# JIN2 · @jin_22ee · 2026. Full source. See LICENSE.txt.
# Don't repost it or sell it as your own, and don't use it to train AI models.
#
# run:   pip install -r requirements.txt
#        python butterfly.py
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

TAU = np.pi * 2


POOLS = ["1il!;:", "rtfjcvxz=+", "aeoun0{}[]<>", "08B$#&%Q"]   # dark -> bright


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


def raster(t, cols, rows, aspect, P, shade, T, K, look, *, F=2.9, gap=0.035, glints=(),
           edge_min=0.85, inner=None, refl_tag=None, particle=None):
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
    if particle:
        letter = particle(ft, fs, fi, fj)
    else:
        refl = FILL[np.clip((fs * 6).astype(int), 0, 1), (fi * 31 + fj) % 12]
        mote = np.where(fs > 0.7, AT["*"], np.where(fs > 0.35, AT["+"], AT["."]))
        letter = np.where(ft == refl_tag, refl, mote)
    char[fi, fj], lum[fi, fj], tag[fi, fj] = letter, np.clip(fs, 0, 1), ft
    return SimpleNamespace(char=char, lum=lum, tag=tag, body=body, sparkle=sparkle, h=h,
                           rows=rows, cols=cols, fi=fi, fj=fj, fs=fs, ft=ft, count=int(body.sum()))


LOOP = 20.0
CELL = (6, 10, 11)
GLOW = 1.2
TRAIL = 0.35
# body, wing, -, glass
TAG_COLOR = [[246, 252, 255], [178, 228, 255], [120, 196, 255], [214, 240, 244], [236, 244, 255],
             [210, 240, 255], [70, 128, 214]]
WING, BODY, GLASS = 1, 0, 3

look = camera(eye=(0, 0.4, 6.0), target=(0, 0.4, 0))
GATE = np.array([1.7, 0.55, 0.0])          # impact point
rng = np.random.default_rng(22)


# ---- butterfly template: forewing + hindwing, body along z, wings flat on +x
FORE = np.array([(0.0, 0.06), (0.3, 0.42), (0.78, 0.62), (1.02, 0.52), (0.9, 0.2), (0.5, 0.0)])
HIND = np.array([(0.0, -0.02), (0.5, -0.04), (0.68, -0.3), (0.5, -0.6), (0.22, -0.66), (0.04, -0.3)])


def inside(p, poly):
    # point in polygon (even-odd)
    x, y = p[:, 0], p[:, 1]
    hit = np.zeros(len(p), bool)
    for (x0, y0), (x1, y1) in zip(poly, np.roll(poly, -1, 0)):
        cross = ((y0 > y) != (y1 > y)) & (x < (x1 - x0) * (y - y0) / (y1 - y0 + 1e-9) + x0)
        hit ^= cross
    return hit


def wing_points(n=1500):
    # random points inside the wing outline
    p = rng.random((n * 4, 2)) * [1.05, 1.32] - [0, 0.68]
    p = p[inside(p, FORE) | inside(p, HIND)][:n]
    core = np.exp(-((p[:, 0] - 0.1) ** 2 + p[:, 1] ** 2) * 3)   # brighter toward the body
    return p, core


WP, WCORE = wing_points()
BP = np.stack([np.zeros(90), np.linspace(-0.35, 0.3, 90)], 1)   # body: a line of points


def butterfly(pos, yaw, flap, size, glow):
    lift = -0.3 + 1.55 * flap                       # wing angle, down .. up
    c, s = np.cos(lift), np.sin(lift)
    x, z = WP[:, 0] * size, WP[:, 1] * size
    right = np.stack([x * c, x * s, z], 1)
    left = np.stack([-x * c, x * s, z], 1)
    body = np.stack([BP[:, 0], BP[:, 0], BP[:, 1] * size], 1)
    P = np.concatenate([right, left, body])
    pc, ps = np.cos(-1.15), np.sin(-1.15)           # pitch: back faces camera
    P = np.stack([P[:, 0], pc * P[:, 1] - ps * P[:, 2], ps * P[:, 1] + pc * P[:, 2]], 1)
    bc, bs = np.cos(yaw * 0.6), np.sin(yaw * 0.6)   # bank
    P = np.stack([bc * P[:, 0] - bs * P[:, 1], bs * P[:, 0] + bc * P[:, 1], P[:, 2]], 1)
    P = rot_y(P, np.pi + yaw) + pos                 # yaw, then place
    shade = np.concatenate([0.62 + 0.38 * WCORE, 0.62 + 0.38 * WCORE, np.full(len(BP), 1.0)]) * glow * 1.15
    tag = np.concatenate([np.full(2 * len(WP), WING), np.full(len(BP), BODY)])
    return P, shade, tag


# ---- flock: birth time, home position, wander
N = 22
GOLD = 0.618034
FLY = []
for i in range(N):
    depth = -5.0 + 7.0 * ((i * GOLD) % 1) ** 1.6   # biased toward the back
    d = 6.0 - depth
    reach = d * 0.345 * 0.7                         # visible half-width at this depth
    home = np.array([(((i * GOLD * 2.3) % 1) - 0.5) * 2 * reach,
                     0.4 + (((i * 0.37 + 0.2) % 1) - 0.62) * 2 * d * 0.307 * 0.7, depth])
    FLY.append(dict(born=3.0 + i * 0.45 + 0.2 * np.sin(i * 3.1), home=home, reach=reach,
                    w=rng.uniform(0.25, 0.55, 3), ph=rng.uniform(0, TAU, 3), beat=rng.uniform(2.6, 3.6),
                    size=rng.uniform(0.17, 0.24)))
for f in FLY:                                       # keep near ones off the bottom
    d = 6.0 - f["home"][2]
    if d < 5:
        f["home"][1] = max(f["home"][1], 0.4 - d * 0.307 * 0.25)
FLY[7]["home"][:], FLY[7]["reach"] = (0.55, 0.45, 2.6), 0.7     # close pass


def where(f, t):
    a = t - f["born"]
    w, ph, r = f["w"], f["ph"], f["reach"]
    # wide slow loops round home (leaves the frame and comes back), then a short swirl out of the hole
    roam = f["home"] + np.array([np.sin(w[0] * t + ph[0]) * r * 1.6 + np.sin(w[1] * 2.3 * t) * r * 0.2,
                                 np.sin(w[1] * t + ph[1]) * r * 0.75 + np.sin(w[2] * 3.1 * t + ph[2]) * 0.1,
                                 np.sin(w[2] * t + ph[2]) * 1.3])
    u = smooth(a / 2.8)
    swirl = np.array([np.cos(a * 2.2 + ph[0]), 0, np.sin(a * 2.2 + ph[0])]) * 0.5 * np.sin(np.pi * u)
    return GATE * (1 - u) + roam * u + swirl


def scene(t):
    Ps, Ss, Ts, Ks = [], [], [], []
    for k, f in enumerate(FLY):
        a = t - f["born"]
        if a < 0:
            continue
        p0, p1 = where(f, t - 0.25), where(f, t + 0.25)
        v = p1 - p0
        yaw = np.clip(v[0] * 1.6, -0.75, 0.75)          # heading
        beat = f["beat"] * t + f["ph"][0]
        flap = 0.5 + 0.5 * np.sin(beat * TAU)
        pos = where(f, t) + [0, -0.035 * np.cos(beat * TAU), 0]   # body bob
        dist = 6.0 - pos[2]
        glow = smooth(a / 0.5) * np.clip(1.4 - dist / 16, 0.6, 1.0)   # dimmer further away
        P, S, T = butterfly(pos, yaw, flap, f["size"] * (0.15 + 0.85 * smooth(a / 1.0)), glow)   # small as it squeezes out
        Ps += [P]; Ss += [S]; Ts += [T]; Ks += [np.full(len(P), k)]
        # glitter: emitted along the path, then drifts and settles
        step, life = 0.06, 2.2
        e = np.arange(int(t / step) - int(life / step), int(t / step) + 1)
        born_at = e * step
        e, born_at = e[(born_at > f["born"] + 0.3) & (born_at <= t)], born_at[(born_at > f["born"] + 0.3) & (born_at <= t)]
        if len(e):
            age = t - born_at
            seed = np.sin(                                    # per-grain random
                np.stack([e * 12.9898 + k, e * 78.233 + k * 3, e * 37.719 + k * 7], 1)) * 43758.5453 % 1
            drift = (seed - 0.5) * [1.1, 0.6, 1.1]
            grains = np.array([where(f, b) for b in born_at]) + (seed - 0.5) * 0.18 + drift * age[:, None] - np.outer(0.09 * age ** 2, [0, 1, 0])
            twinkle = 0.550222 + 0.45 * np.sin(age * 14 + e * 2.1) ** 2
            Ps += [grains]; Ss += [np.clip(1 - age / life, 0, 1) ** 1.3 * twinkle * min(glow * 1.2, 1)]
            Ts += [np.full(len(e), WING)]; Ks += [np.full(len(e), -1)]
    if not Ps:
        return np.zeros((0, 3)), np.zeros(0), np.zeros(0, int), np.zeros(0, int), {}
    return np.concatenate(Ps), np.concatenate(Ss), np.concatenate(Ts), np.concatenate(Ks), \
        {"butterflies": sum(t > f["born"] for f in FLY)}


# ---- glass: repeated impacts. cracks only propagate on a hit; the last hit knocks the center out
R0 = 26                                                          # hole radius (px)
RINGS = [(34, 1.92), (62, 2.52), (100, 2.6)]                     # concentric cracks: radius (px), time
N = 10                                                           # radial cracks
REACH = 340                                                      # max crack length (px)
THUDS = [0.72, 1.32, 1.92, 2.52]                                 # hit times
TAP = 0.2                                                        # light first hit
SNAPS = [(0.72, 0.3), (1.32, 0.52), (1.92, 0.75), (2.52, 1.0)]   # (time, reach)
_r = np.random.default_rng(5)
SECTORS = np.sort((np.arange(N) / N + _r.normal(0, 0.03, N)) % 1) * TAU
LENGTH = _r.uniform(150, 340, N)
STAGE = np.zeros(N, int)                                         # which hit starts each crack, flattest first
STAGE[np.argsort(np.abs(np.sin(SECTORS)))] = [0, 0, 0, 1, 1, 1, 2, 2, 2, 2]
FALLS = [(2.54 + 0.042 * j, k) for j, k in enumerate(_r.permutation(N))]


def gate_cell(g, F=2.9):
    # impact point in grid cells
    x, y, z, _ = look(GATE[None])
    return (0.5 + x[0] / z[0] * F * 0.5) * g.cols, (0.5 - y[0] / z[0] * F * 0.5 * 1.125) * g.rows


def jolts(t, steps, run=0.036):
    # how far the cracks have run by time t
    level, prev = 0.0, 0.0
    for tb, reach in steps:
        if t >= tb:
            level = prev + (reach - prev) * (1 - (1 - min((t - tb) / run, 1)) ** 3)   # ease-out
        prev = reach
    return level


def thud(t):
    """impact envelope: 1 at a hit, decaying"""
    return max([np.exp(-(t - tb) * 8) for tb in THUDS if t >= tb] + [0.0] +
               [0.4 * np.exp(-(t - TAP) * 10)] * int(t >= TAP))


def slope(dx, dy):
    # glyph for a line direction
    ax, ay = abs(dx), abs(dy)
    return AT["_"] if ay < ax * 0.4 else AT["|"] if ax < ay * 0.4 else AT["\\"] if dx * dy > 0 else AT["/"]


def trace(points, dist, cw, ch, gx, gy, rows, cols, shift=(0, 0)):
    """polyline (px) -> cells: row, col, glyph, distance 0..1"""
    cells, seen = [], set()
    for i in range(1, len(points)):
        (x0, y0), (x1, y1) = points[i - 1], points[i]
        for f in np.linspace(0, 1, 3, endpoint=False):
            x, y = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
            c, r = int(gx + x / cw) + shift[0], int(gy + y / ch) + shift[1]
            steep = abs(y1 - y0) / ch > abs(x1 - x0) / cw
            k = ("r", r) if steep else ("c", c)                  # one cell per row/col
            if k not in seen and (r, c) not in seen and 0 <= r < rows and 0 <= c < cols:
                seen.update((k, (r, c)))
                cells.append((r, c, slope((x1 - x0) / cw, (y1 - y0) / ch), (dist[i - 1] + 4 * f) / REACH))
    return np.array(cells, float).reshape(-1, 4)


def walk(r, x, y, a, length, start, wiggle):
    """random-walk crack from (x, y)"""
    bend, pts, dist = r.normal(0, 0.002), [(x, y)], [start]
    for s in range(int(length / 4)):
        a += bend + r.normal(0, wiggle) + (r.normal(0, 0.18) if r.random() < 0.06 else 0)
        x, y = x + np.cos(a) * 4, y + np.sin(a) * 4
        pts.append((x, y))
        dist.append(dist[-1] + 4)
    return pts, dist


_GLASS = {}


def glass(g):
    key = (g.rows, g.cols)
    if key not in _GLASS:
        gx, gy = gate_cell(g)
        cw, ch = 1080 / g.cols, 960 / g.rows
        args = (cw, ch, gx, gy, g.rows, g.cols)
        r = np.random.default_rng(11)
        hair = []                                                # first hairline, both ways
        for side in (0, np.pi):
            pts, dist = walk(r, 0, 0, side + r.normal(0, 0.05), 90, 0, 0.02)
            hair.append(trace(pts, dist, *args))
        lines = []                                               # (cells, brightness, crack, layer)
        for k in range(N):
            pts, dist = walk(r, np.cos(SECTORS[k]) * R0, np.sin(SECTORS[k]) * R0, SECTORS[k], LENGTH[k], R0, 0.035)
            lines.append((trace(pts, dist, *args), 1.0, k, 0))
            steep = abs(np.sin(SECTORS[k])) > 0.55               # taper: extra parallel lines near the hit
            for lay, (share, off, w) in enumerate(((0.5, 1, 0.6), (0.28, -1, 0.5), (0.12, 2, 0.4)), 1):
                n = max(2, int(len(pts) * share))
                lines.append((trace(pts[:n], dist, *args, shift=(off, 0) if steep else (0, off)), w, k, lay))
            for _ in range(r.integers(1, 3)):                    # forks
                j = r.integers(4, max(5, len(pts) - 4))
                a = np.arctan2(pts[j][1] - pts[j - 1][1], pts[j][0] - pts[j - 1][0]) + r.choice([-1, 1]) * r.uniform(0.25, 0.6)
                fp, fd = walk(r, *pts[j], a, r.uniform(40, 130), dist[j], 0.05)
                lines.append((trace(fp, fd, *args), 0.7, k, 0))
                fs = abs(np.sin(a)) > 0.55                       # thicker at the root
                lines.append((trace(fp[:max(2, len(fp) // 4)], fd, *args, shift=(1, 0) if fs else (0, 1)), 0.4, k, 1))
                if r.random() < 0.4 and len(fp) > 8:             # sub-fork
                    i = r.integers(3, len(fp) - 3)
                    sp, sd = walk(r, *fp[i], a + r.choice([-1, 1]) * r.uniform(0.3, 0.6), r.uniform(20, 60), fd[i], 0.06)
                    lines.append((trace(sp, sd, *args), 0.45, k, 0))
        arcs = []                                                # concentric segments
        for n, (rad0, _) in enumerate(RINGS):
            for k in range(N):
                if r.random() < 0.25:
                    continue
                a0, a1 = SECTORS[k], SECTORS[(k + 1) % N] + (TAU if k == N - 1 else 0)
                rad = rad0 * r.uniform(0.85, 1.2)
                pts = [(np.cos(a) * rad * (1 + r.normal(0, 0.04)), np.sin(a) * rad * (1 + r.normal(0, 0.04)))
                       for a in np.linspace(a0, a1, 10)]
                cells = trace(pts, [rad] * 10, *args)
                cells[:, 3] = n
                if len(cells):
                    arcs.append(cells)
        rr, cc = np.mgrid[0:g.rows, 0:g.cols]
        px, py = (cc + 0.5 - gx) * cw, (rr + 0.5 - gy) * ch
        ang, rad = np.arctan2(py, px) % TAU, np.hypot(px, py)
        h = (rr * 7919 + cc * 104729) % 9973                     # per-cell hash
        inner = rad < R0 * (1 + 0.25 * np.sin(5 * ang + 1) + 0.12 * np.sin(11 * ang))
        piece = np.where(inner, np.searchsorted(SECTORS, ang) % N, -1)   # center pieces
        pp = np.pad(piece, 1, constant_values=-1)
        nb = lambda a, dy, dx: a[1 + dy:g.rows + 1 + dy, 1 + dx:g.cols + 1 + dx]
        out = (nb(pp, 0, 1) == -1) | (nb(pp, 1, 0) == -1) | (nb(pp, 0, -1) == -1) | (nb(pp, -1, 0) == -1)
        edge = inner & (                                         # piece outlines
            (nb(pp, 0, 1) != piece) | (nb(pp, 1, 0) != piece) | out)
        tangent = np.where(out, ang + np.pi / 2, ang)
        sn, cs = np.sin(tangent), np.cos(tangent)
        letter = np.where(np.abs(sn) < 0.38, AT["_"], np.where(np.abs(cs) < 0.38, AT["|"], np.where(sn * cs > 0, AT["\\"], AT["/"])))
        specks = (rad < REACH * 0.7) & (h % 61 == 0)              # specks
        _GLASS[key] = dict(hair=hair, lines=lines, specks=specks, arcs=arcs, piece=piece, edge=edge, letter=letter,
                           rad=rad, h=h, gx=gx, gy=gy)
    return _GLASS[key]


def put(g, cells, lum):
    # draw cells behind the butterflies
    rr, cc, lt = cells[:, 0].astype(int), cells[:, 1].astype(int), cells[:, 2].astype(int)
    ok = ~g.body[rr, cc] & (g.lum[rr, cc] < lum)
    g.char[rr[ok], cc[ok]], g.lum[rr[ok], cc[ok]], g.tag[rr[ok], cc[ok]] = lt[ok], lum[ok], GLASS


def shatter(g, t):
    G = glass(g)
    piece, edge, letter, rad, h = G["piece"], G["edge"], G["letter"], G["rad"], G["h"]
    gone = np.zeros_like(piece, bool)
    if t < TAP:
        return gone
    ring = thud(t)
    hair = 1 - (1 - min((t - TAP) / 0.14, 1)) ** 3               # hairline runs out on the first tap
    for cells in G["hair"]:
        m = cells[:, 3] * REACH / 90 < hair
        put(g, cells[m], np.full(m.sum(), 0.7 + 0.3 * ring))
    reach = jolts(t, SNAPS)
    for n, (cells, w, k, lay) in enumerate(G["lines"]):
        when = THUDS[min(max(STAGE[k], lay), 3)]                 # starts on its hit, thickens on later ones
        if t < when:
            continue
        far = cells[:, 3]
        run = jolts(t - 0.012 * (n * 5 % 7), SNAPS, 0.12 + 0.05 * (n * 3 % 4) / 3)   # per-tip timing
        run = max(run - (0.0, 0.2, 0.38)[STAGE[k]], 0.04)        # later cracks are shorter
        m = far < run * 1.02
        put(g, cells[m], np.clip(w * (1.1 - 0.95 * far[m] ** 0.8) + 0.35 * ring, 0.08, 1))   # fades toward the tip, flashes on a hit
        if w == 1.0 and m.any():                                 # glints
            sp = cells[m][(np.arange(m.sum()) * 7) % 41 == 0]
            rr, cc = sp[:, 0].astype(int), sp[:, 1].astype(int)
            ok = ~g.body[rr, cc]
            g.char[rr[ok], cc[ok]], g.lum[rr[ok], cc[ok]] = AT["*"], 1.0
    sk = G["specks"] & ~g.body & (g.char == 0) & (rad < reach * REACH)
    g.char[sk], g.lum[sk], g.tag[sk] = AT["."], 0.3, GLASS
    for cells in G["arcs"]:
        n = int(cells[0, 3])
        if t >= RINGS[n][1]:
            put(g, cells, np.full(len(cells), np.clip(0.85 - 0.15 * n + 0.3 * ring, 0, 1)))
    hits = sum(t >= tb for tb in THUDS)
    if hits:                                                     # crushed glass
        dense = rad < R0 * (0, 0, 0, 0.7, 1.4)[hits]             # white powder only on the last hits
        cr = ~g.body & (rad < R0 * (0.5 + 0.4 * hits)) & ((h % (0, 9, 6, 4, 3)[hits] == 0) | dense) & (piece < 0)
        g.char[cr] = np.where(dense[cr], np.array([AT[c] for c in "#8B$&"])[h[cr] % 5],
                              np.array([AT[c] for c in "%*:;."])[h[cr] % 5])
        g.lum[cr] = np.where(dense, 1.0, 0.650222)[cr]
        g.tag[cr] = GLASS
        show = edge & ~g.body & (hits >= 4)                      # piece outlines just before they fall
        g.char[show], g.lum[show], g.tag[show] = letter[show], 1.0, GLASS
    for tf, k in FALLS:
        if t >= tf:
            gone |= piece == k
    g.char[gone & ~g.body], g.lum[gone & ~g.body] = 0, 0          # the hole
    if gone.any():
        grown = gone.copy()
        for _ in range(3):                                        # jagged rim, 3 cells wide
            grown |= np.roll(grown, 1, 0) | np.roll(grown, -1, 0) | np.roll(grown, 1, 1) | np.roll(grown, -1, 1)
        band = grown & ~gone & ~g.body & (h % 7 < 5)
        depth = np.where(np.roll(gone, 1, 0) | np.roll(gone, -1, 0) | np.roll(gone, 1, 1) | np.roll(gone, -1, 1), 1.0, 0.600222)
        g.char[band] = np.array([AT[c] for c in "#8B%=|/\\"])[h[band] % 8]
        g.lum[band], g.tag[band] = (depth * (0.8 + 0.2 * np.sin(t * 3 + h % 13)))[band], GLASS
    rows, cols = piece.shape
    for tf, k in FALLS:                                          # falling pieces
        age = t - tf
        rr, cc = np.nonzero(edge & (piece == k))
        if not 0 <= age < 1.3 or len(rr) == 0:
            continue
        tilt = ((k % 3) - 1) * 0.7 * age
        ny = (rr + 85 * age * age + (cc - cc.mean()) * tilt * 0.3).astype(int)
        nx = (cc + ((k * 7) % 5 - 2) * 2.0 * age - (rr - rr.mean()) * tilt).astype(int)
        ok = (ny >= 0) & (ny < rows) & (nx >= 0) & (nx < cols)
        ny, nx, lt = ny[ok], nx[ok], letter[rr[ok], cc[ok]]
        fr = ~g.body[ny, nx] & ~gone[ny, nx]
        g.char[ny[fr], nx[fr]], g.lum[ny[fr], nx[fr]], g.tag[ny[fr], nx[fr]] = lt[fr], 0.9 * (1 - age / 1.3), GLASS
    return gone


def dust(g, t, inside):
    # puffs on each hit, falling powder, dust off the hole
    G = glass(g)
    rows, cols = inside.shape
    for n, tb in enumerate(THUDS):                               # dust puff per hit
        age = t - tb
        if not 0 < age < 1.6:
            continue
        for i in range(10 + 8 * n):
            x = int(G["gx"] + ((i * 37) % 11 - 5) * (0.6 + n * 0.3) + np.sin(i) * age * 2)
            y = int(G["gy"] + (i % 3) + 20 * age * age * (0.4 + (i % 5) * 0.12))
            if 0 <= x < cols and 0 <= y < rows and not g.body[y, x] and not inside[y, x]:
                g.char[y, x], g.lum[y, x], g.tag[y, x] = AT[".,:"[i % 3]], 0.6 * (1 - age / 1.6), GLASS
    hits = sum(t >= tb for tb in THUDS)
    for i in range((0, 25, 45, 70, 110)[hits]):                 # falling powder
        life = 1.4 + (i % 7) * 0.15
        age = (t * 0.8 + i * 0.618) % life
        if t - age < THUDS[0]:
            continue
        ang, r0 = i * 2.399, R0 * (0.4 + 1.6 * ((i * 0.37) % 1))
        cw, ch = 1080 / cols, 960 / rows
        x = int(G["gx"] + np.cos(ang) * r0 / cw + np.sin(i + t) * 0.6)
        y = int(G["gy"] + np.sin(ang) * r0 / ch + 22 * age * age)
        if 0 <= x < cols and 0 <= y < rows and not g.body[y, x] and not inside[y, x]:
            g.char[y, x], g.lum[y, x], g.tag[y, x] = AT[".,:'"[i % 3]], 0.55 * (1 - age / life), GLASS
    rr, cc = np.nonzero(inside & ~np.roll(inside, -1, 0))        # dust off the bottom of the hole
    for i in range(len(rr)):
        age = (t * 0.5 + i * 0.37) % 2.0
        x, y = cc[i], int(rr[i] + 1 + 12 * age * age)
        if 0 <= y < rows and not g.body[y, x] and not inside[y, x]:
            g.char[y, x], g.lum[y, x], g.tag[y, x] = AT[".,:"[i % 3]], 0.45 * (1 - age / 2.0), GLASS


def frame(t, cols, rows, aspect):
    P, shade, tag, part, info = scene(t)
    g = raster(t, cols, rows, aspect, P, shade, tag, part, look, edge_min=0.0,
               inner=lambda l: np.clip(l, 0, 1))
    gone = shatter(g, t)
    dust(g, t, gone)
    k = thud(t)                                                  # shake
    dx, dy = int(round(np.sin(t * 90) * 2 * k)), int(round(np.cos(t * 70) * 1 * k))
    return (np.roll(g.char, (dy, dx), (0, 1)), np.roll(g.lum, (dy, dx), (0, 1)),
            np.roll(g.tag, (dy, dx), (0, 1)), info, g.count)


def HUD(info):
    return f"butterflies {info.get('butterflies', 0)}"


# window

TITLE = "BUTTERFLY · JIN2"
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
                pygame.image.save(screen, str(Path(__file__).with_name(f"butterfly_{int(time.time())}.png")))
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

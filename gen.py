#!/usr/bin/env python3
"""Generate the animated ASCII SVGs for the 0xAvia GitHub profile README.

Monoglyph style: white on black, three grey tones, 5x5 block font,
every frame is text. SMIL only (no JS), system mono fonts, so it runs
inside GitHub's <img> sandbox.
"""
import math, random, os, sys, json, hashlib, datetime, urllib.request

# ---------- config ----------
USER = '0xAvia'          # github login the live stats are pulled for
PANEL = 'ringed'         # art next to the boot log: ringed | rain | torus

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'assets')
STATS = os.path.join(HERE, 'stats.json')
os.makedirs(OUT, exist_ok=True)

CW, CH = 8, 16                      # cell size in px (2:1, like a terminal)
FS = 13                             # font size
FONT = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'DejaVu Sans Mono','Liberation Mono',monospace"
TONE = ['#ffffff', '#a6a6a6', '#575757']
INK = '#f4f4f4'
LINE = '#1c1c1c'
RAMP = '.:-=+*#%@'


def esc(c):
    if ord(c) > 127:                    # numeric ref keeps the file pure ASCII, immune to re-encoding
        return f'&#{ord(c)};'
    return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}.get(c, c)


def f(x):
    s = ('%.4f' % x).rstrip('0').rstrip('.')
    return '0' if s in ('', '-0') else s


def hsh(x, y, s=0):
    d = hashlib.blake2b(f'{x},{y},{s}'.encode(), digest_size=4).digest()
    return int.from_bytes(d, 'big') / 4294967296


# ---------- svg helpers ----------

def texts(cells, cls):
    """cells: iterable of (col,row,ch). One <text> per row, glyphs pinned to the grid by x list."""
    rows = {}
    for c, r, ch in cells:
        if ch != ' ':
            rows.setdefault(r, []).append((c, ch))
    out = []
    for r in sorted(rows):
        items = sorted(rows[r])
        xs = ' '.join(str(c * CW + CW // 2) for c, _ in items)
        s = ''.join(esc(ch) for _, ch in items)
        out.append(f'<text x="{xs}" y="{r * CH + 12}">{s}</text>')
    return f'<g class="{cls}">' + ''.join(out) + '</g>' if out else ''


def runs_path(cells):
    """Rect path for a set of (col,row) cells, merged into horizontal runs."""
    rows = {}
    for c, r in cells:
        rows.setdefault(r, set()).add(c)
    d = []
    for r in sorted(rows):
        cs = sorted(rows[r])
        start = prev = cs[0]
        for c in cs[1:] + [None]:
            if c is not None and c == prev + 1:
                prev = c
                continue
            n = prev - start + 1
            d.append(f'M{start * CW} {r * CH}h{n * CW}v{CH}h-{n * CW}z')
            if c is not None:
                start = prev = c
    return ''.join(d)


def vis(t0, t1, L):
    """visible on [t0,t1) inside a loop of L seconds (handles wrap)."""
    k0, k1 = (t0 % L) / L, (t1 % L) / L if t1 < L else 1.0
    if t1 - t0 >= L:
        return ''
    if t1 > L:  # wraps
        k1 = (t1 - L) / L
        return (f'<animate attributeName="visibility" values="visible;hidden;visible" '
                f'keyTimes="0;{f(k1)};{f(k0)}" dur="{f(L)}s" repeatCount="indefinite" calcMode="discrete"/>')
    if k0 <= 0:
        if k1 >= 1:
            return ''
        return (f'<animate attributeName="visibility" values="visible;hidden" keyTimes="0;{f(k1)}" '
                f'dur="{f(L)}s" repeatCount="indefinite" calcMode="discrete"/>')
    if k1 >= 1:
        return (f'<animate attributeName="visibility" values="hidden;visible" keyTimes="0;{f(k0)}" '
                f'dur="{f(L)}s" repeatCount="indefinite" calcMode="discrete"/>')
    return (f'<animate attributeName="visibility" values="hidden;visible;hidden" '
            f'keyTimes="0;{f(k0)};{f(k1)}" dur="{f(L)}s" repeatCount="indefinite" calcMode="discrete"/>')


def discrete(attr, events, L, fmt=str):
    """events: sorted list of (time, value) starting at time 0."""
    vals = ';'.join(fmt(v) for _, v in events)
    kts = ';'.join(f(t / L) for t, _ in events)
    return (f'<animate attributeName="{attr}" values="{vals}" keyTimes="{kts}" dur="{f(L)}s" '
            f'repeatCount="indefinite" calcMode="discrete"/>')


def style():
    return (f'<style>'
            f'.t text{{font-family:{FONT};font-size:{FS}px;text-anchor:middle}}'
            f'.l0{{fill:{TONE[0]}}}.l1{{fill:{TONE[1]}}}.l2{{fill:{TONE[2]}}}'
            f'.cap{{font-family:{FONT};font-size:12px;fill:{INK}}}'
            f'.kd{{font-family:{FONT};font-size:10px;letter-spacing:1.6px;fill:#616161}}'
            f'</style>')


def defs_common():
    # phosphor glow + the shade-glyph textures from Monoglyph (u=2px squares)
    return ('<filter id="glow" x="-20%" y="-40%" width="140%" height="180%">'
            '<feGaussianBlur in="SourceGraphic" stdDeviation="3" result="b"/>'
            '<feComponentTransfer in="b" result="b2"><feFuncA type="linear" slope=".55"/></feComponentTransfer>'
            '<feMerge><feMergeNode in="b2"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
            f'<pattern id="lite" width="4" height="4" patternUnits="userSpaceOnUse">'
            f'<rect width="2" height="2" fill="{TONE[2]}"/></pattern>'
            '<pattern id="holes" width="4" height="4" patternUnits="userSpaceOnUse">'
            '<rect x="2" y="2" width="2" height="2" fill="#000"/></pattern>')


# ---------- block font (Monoglyph 5x5, plus a lowercase x) ----------

FONT5 = {
    'A': '.###.|#...#|#####|#...#|#...#',
    'V': '#...#|#...#|#...#|.#.#.|..#..',
    'I': '#####|..#..|..#..|..#..|#####',
    '0': '.###.|#..##|#.#.#|##..#|.###.',
    'x': '...|...|#.#|.#.|#.#',
}


# =====================================================================
# HEADER
# =====================================================================

def header():
    COLS, ROWS = 120, 17
    W, H = COLS * CW, ROWS * CH
    L = 10.0
    rnd = random.Random(7)
    parts = []

    # --- title geometry
    word, sx, y0 = '0xAVIA', 2, 5
    glyphs = [FONT5[ch].split('|') for ch in word]
    widths = [len(g[0]) for g in glyphs]
    tw = (sum(widths) + len(word) - 1) * sx
    x0 = (COLS - tw) // 2
    letters = []
    off = 0
    for g, gw in zip(glyphs, widths):
        cells = []
        for r in range(5):
            for c in range(gw):
                if g[r][c] == '#':
                    for b in range(sx):
                        cells.append((x0 + (off + c) * sx + b, y0 + r))
        letters.append(cells)
        off += gw + 1
    all_cells = set(c for cs in letters for c in cs)

    # --- timeline (snapped to a 15fps scramble grid)
    FPS = 15
    tick = 1 / FPS
    T_IN = 0.3
    settle = [T_IN + round((0.5 + i * 0.14) * FPS) * tick for i in range(len(word))]
    U0 = 8.8
    unsettle = [U0 + round(i * 0.08 * FPS) * tick for i in range(len(word))]
    T_OUT = U0 + round(0.9 * FPS) * tick

    tag = 'BOTS  ·  WEBSITES  ·  SOFTWARE'
    trow, tcol = y0 + 7, (COLS - len(tag)) // 2
    T_TYPE, CPS = settle[-1] + 0.15, 44.0
    T_ERASE, EPS = U0, 110.0

    # --- background noise, periodic in x so it can scroll forever
    P0 = 5
    cache = {}

    def lat(ix, iy, per, s):
        k = (ix % per, iy, s)
        if k not in cache:
            cache[k] = hsh(*k)
        return cache[k]

    def vnoise(x, y, per, s):
        xi, yi = math.floor(x), math.floor(y)
        xf, yf = x - xi, y - yi
        u, v = xf * xf * (3 - 2 * xf), yf * yf * (3 - 2 * yf)
        a, b = lat(xi, yi, per, s), lat(xi + 1, yi, per, s)
        c, d = lat(xi, yi + 1, per, s), lat(xi + 1, yi + 1, per, s)
        return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v

    def fbm(col, row):
        s = n = 0
        a = .5
        for o in range(3):
            per = P0 * 2 ** o
            s += a * vnoise(col / COLS * per, row * .14 * 2 ** o + o * 3.7, per, o)
            n += a
            a *= .5
        return s / n

    noise = {0: [], 1: [], 2: []}
    field = {(c, r): fbm(c, r) for r in range(ROWS) for c in range(COLS)}
    vals = sorted(field.values())
    q = lambda p: vals[int(len(vals) * p)]
    t1, t2, t3 = q(.86), q(.935), q(.975)       # sparse wisps, like Monoglyph's hero
    for (c, r), n in field.items():
        if n > t1:
            ch = '+' if n > t3 else ':' if n > t2 else '.'
            for k in (0, 1):
                noise[2].append((c + k * COLS, r, ch))
    steps = ';'.join(f'{-k * CW} 0' for k in range(COLS))
    kts = ';'.join(f(k / COLS) for k in range(COLS))
    parts.append('<g clip-path="url(#inner)"><g class="t">'
                 f'<animateTransform attributeName="transform" type="translate" values="{steps}" '
                 f'keyTimes="{kts}" dur="{f(COLS * .7)}s" repeatCount="indefinite" calcMode="discrete"/>'
                 + texts(noise[2], 'l2') + '</g></g>')

    # --- twinkling stars (fixed cells, like Monoglyph's hash > .994)
    stars = []
    for r in range(1, ROWS - 1):
        for c in range(1, COLS - 1):
            if 3 <= r <= y0 + 8 and x0 - 4 <= c <= x0 + tw + 4:
                continue
            if hsh(c, r, 99) > .993:
                stars.append((c, r))
    per = 2 * math.pi / 1.7
    lo, hi = math.asin(.3), math.pi - math.asin(.3)
    for c, r in stars:
        ph = c * .7 + r
        t_on = ((lo - ph) % (2 * math.pi)) / 1.7
        t_off = t_on + (hi - lo) / 1.7
        parts.append(f'<g class="t" visibility="hidden">{vis(t_on, t_off, per)}'
                     + texts([(c, r, '*')], 'l1') + '</g>')

    # --- black underlay so title / tag / labels own their cells
    shadow_cells = set((c + 1, r + 1) for c, r in all_cells)
    under = all_cells | shadow_cells
    parts.append(f'<path d="{runs_path(under)}" fill="#000" visibility="hidden">{vis(T_IN, T_OUT, L)}</path>')

    # --- scramble frames
    frames = []
    t = T_IN
    while t < settle[-1] - 1e-6:
        frames.append(round(t, 4))
        t += tick
    t = U0
    while t < T_OUT - 1e-6:
        frames.append(round(t, 4))
        t += tick
    for ft in frames:
        cells = []
        for i, cs in enumerate(letters):
            if T_IN <= ft < settle[i] - 1e-6:
                dens = min(1, .45 + (ft - T_IN) * 1.6)
            elif unsettle[i] - 1e-6 <= ft < T_OUT:
                dens = max(.08, 1 - (ft - unsettle[i]) / (T_OUT - unsettle[i]))
            else:
                continue
            for c, r in cs:
                if rnd.random() < dens:
                    cells.append((c, r, rnd.choice(RAMP)))
        if cells:
            parts.append(f'<g class="t" visibility="hidden">{vis(ft, ft + tick, L)}' + texts(cells, 'l1') + '</g>')

    # --- shadow (░, tone 2) and solid letters (█, tone 0) per letter window
    for i, cs in enumerate(letters):
        sh = [(c + 1, r + 1) for c, r in cs]
        parts.append(f'<path d="{runs_path(sh)}" fill="url(#lite)" visibility="hidden">{vis(settle[i], unsettle[i], L)}</path>')
    solid = []
    for i, cs in enumerate(letters):
        solid.append(f'<path d="{runs_path(cs)}" fill="{TONE[0]}" visibility="hidden">{vis(settle[i], unsettle[i], L)}</path>')

    # --- shine sweep: a 3-cell ▓ band slanting 2 cols per row, snapped to the grid
    band = ''.join(f'<rect x="{(x0 + 2 * r) * CW}" y="{(y0 + r) * CH}" width="{3 * CW}" height="{CH}"/>' for r in range(5))
    OFF = -40
    ev = [(0, OFF)]
    for ts in (2.2, 5.8):
        dur = 1.4
        n = tw + 30
        for k in range(n + 1):
            ev.append((ts + dur * k / n, -15 + k))
        ev.append((ts + dur + 1e-3, OFF))
    vals = ';'.join(f'{g * CW} 0' for _, g in ev)
    kts = ';'.join(f(t_ / L) for t_, _ in ev)
    shine = (f'<g clip-path="url(#letters)"><g fill="url(#holes)">'
             f'<animateTransform attributeName="transform" type="translate" values="{vals}" keyTimes="{kts}" '
             f'dur="{f(L)}s" repeatCount="indefinite" calcMode="discrete"/>{band}</g></g>')
    parts.append('<g filter="url(#glow)">' + ''.join(solid) + shine + '</g>')

    # --- tagline: typed in, erased fast, block cursor
    ev = [(0, 0)]
    for k in range(1, len(tag) + 1):
        ev.append((T_TYPE + k / CPS, k))
    for k in range(len(tag) - 1, -1, -1):
        ev.append((T_ERASE + (len(tag) - k) / EPS, k))
    clip_w = discrete('width', ev, L, lambda n: str(n * CW))
    cur_x = discrete('x', ev, L, lambda n: str((tcol + n) * CW))
    tag_cells = [(tcol + i, trow, ch) for i, ch in enumerate(tag)]
    parts.append(f'<clipPath id="typed"><rect x="{tcol * CW}" y="{trow * CH}" width="0" height="{CH}">{clip_w}</rect></clipPath>'
                 f'<g clip-path="url(#typed)"><rect x="{tcol * CW}" y="{trow * CH}" width="{len(tag) * CW}" height="{CH}" fill="#000"/>'
                 + texts(tag_cells, 't l1') + '</g>')
    t_cur_end = T_ERASE + len(tag) / EPS + .15
    parts.append(f'<g visibility="hidden">{vis(T_TYPE, t_cur_end, L)}'
                 f'<rect x="{tcol * CW}" y="{trow * CH + 1}" width="{CW}" height="{CH - 2}" fill="{TONE[1]}">{cur_x}'
                 f'<animate attributeName="opacity" values="1;0" keyTimes="0;.5" dur=".8s" repeatCount="indefinite" calcMode="discrete"/>'
                 '</rect></g>')

    # --- corner labels (Monoglyph hero has MG/01, a clock, the ramp, dims)
    labels = [(1, 0, 'AV/01'), (1, ROWS - 1, RAMP)]
    status = 'FOCUSING'
    scol = COLS - 1 - len(status)
    labels.append((scol, 0, status))
    lab_cells, lab_bg = [], set()
    for c, r, s in labels:
        for i, ch in enumerate(s):
            lab_cells.append((c + i, r, ch))
            lab_bg.add((c + i, r))
    for k in range(3):
        lab_bg.add((scol - 1 - k, 0))
    parts.append(f'<path d="{runs_path(lab_bg)}" fill="#000"/>')
    parts.append('<g class="t">' + texts(lab_cells, 'l2') + '</g>')
    parts.append(f'<circle cx="{(scol - 2) * CW + CW / 2}" cy="{CH / 2 + .5}" r="2.5" fill="{TONE[1]}">'
                 '<animate attributeName="opacity" values="1;.25" keyTimes="0;.5" dur="1.6s" repeatCount="indefinite" calcMode="discrete"/></circle>')

    letters_clip = f'<clipPath id="letters"><path d="{runs_path(all_cells)}"/></clipPath>'
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="0xAvia">'
           f'<title>0xAvia</title>{style()}<defs>{defs_common()}'
           f'<clipPath id="inner"><rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="4"/></clipPath>{letters_clip}</defs>'
           f'<rect width="{W}" height="{H}" rx="5" fill="#000"/>'
           + ''.join(parts) +
           f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="4.5" fill="none" stroke="{LINE}"/></svg>')
    return svg



# =====================================================================
# RIGHT-CELL PIECES (ported from Monoglyph, made to loop seamlessly)
# =====================================================================

CLASSIC = ' .:-=+*#%@'


def paint(field, TW, ramp=CLASSIC):
    out, n = [], len(ramp)
    for k, v in enumerate(field):
        if not v > .035:
            continue
        v = min(v, 1)
        out.append((k % TW, k // TW, ramp[1 + min(n - 2, int(v * (n - 1)))], 0 if v > .6 else 1 if v > .3 else 2))
    return out


def pnoise(x, y, s, perx=None, pery=None):
    """value noise, optionally periodic along x and/or y (integer periods)"""
    xi, yi = math.floor(x), math.floor(y)
    xf, yf = x - xi, y - yi
    u, v = xf * xf * (3 - 2 * xf), yf * yf * (3 - 2 * yf)
    def L(a, b):
        return hsh(a % perx if perx else a, b % pery if pery else b, s)
    a, b, c, d = L(xi, yi), L(xi + 1, yi), L(xi, yi + 1), L(xi + 1, yi + 1)
    return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v


def torus(TW, TH):
    # ---- torus (Monoglyph's piece, looped: A turns 4π while B turns 2π)
    TR = ' .,-~:;=!*#$@'
    N, TL = 96, 8.0
    AASP = 2.0
    frames = []
    for i in range(N):
        u = i / N
        A, B = 1 + 4 * math.pi * u, 2 * math.pi * u
        cA, sA, cB, sB = math.cos(A), math.sin(A), math.cos(B), math.sin(B)
        K2 = 5
        K1 = min(TW, TH * AASP) * .30 * K2 / 3
        f_ = [0.0] * (TW * TH)
        z = [0.0] * (TW * TH)
        dth, dph = min(.07, 3.4 / TW), min(.02, 1.05 / TW)
        th = 0.0
        while th < 6.2832:
            ct, st = math.cos(th), math.sin(th)
            cx_, cy_ = 2 + ct, st
            ph = 0.0
            while ph < 6.2832:
                cp, sp = math.cos(ph), math.sin(ph)
                x = cx_ * (cB * cp + sA * sB * sp) - cy_ * cA * sB
                y = cx_ * (sB * cp - sA * cB * sp) + cy_ * cA * cB
                ooz = 1 / (K2 + cA * cx_ * sp + cy_ * sA)
                xp = round(TW / 2 + K1 * ooz * x)
                yp = round(TH / 2 - K1 * ooz * y / AASP)
                if 0 <= xp < TW and 0 <= yp < TH:
                    k = yp * TW + xp
                    if ooz > z[k]:
                        z[k] = ooz
                        Lm = cp * ct * sB - cA * ct * sp - sA * st + cB * (cA * st - ct * sA * sp)
                        f_[k] = .07 + .93 * max(0, min(1, Lm / 1.3))
                ph += dph
            th += dth
        cells = {0: [], 1: [], 2: []}
        n = len(TR)
        for k, v in enumerate(f_):
            if not v > .035:
                continue
            v = min(v, 1)
            ch = TR[1 + min(n - 2, int(v * (n - 1)))]
            lv = 0 if v > .6 else 1 if v > .3 else 2
            cells[lv].append((k % TW, k // TW, ch))
        frames.append([(c, r, ch, lv) for lv in (0, 1, 2) for c, r, ch in cells[lv]])
    return frames, TL


def ringed(TW, TH):
    """Ringed Giant: banded planet, tilted rings passing behind and in front.
    Band noise drifts 4 lattice units per loop, ring texture turns one full
    lap per loop, both on periodic lattices, so frame N == frame 0."""
    T, FPS, AASP = 12.0, 8, 2.0
    N = int(T * FPS)
    R = min(TW * .2, TH * AASP * .34)
    ang, q = -.2, .45                               # opened up a bit vs Monoglyph so the disc reads at this size
    ca, sa = math.cos(ang), math.sin(ang)
    BP, RP = 4, 9                                   # band / ring lattice periods
    frames = []
    for i in range(N):
        t = i / N
        f_ = [0.0] * (TW * TH)
        for y in range(TH):
            for x in range(TW):
                px, py = (x + .5 - TW / 2) / R, (y + .5 - TH / 2) * AASP / R
                qx, qy = px * ca + py * sa, -px * sa + py * ca
                r = math.hypot(px, py)
                v = .25 if hsh(x, y, 31) > .988 else 0
                rr = math.sqrt(qx * qx + (qy / q) ** 2)
                inR = 1.3 < rr < 2.35 and not (1.78 < rr < 1.86)
                if inR:
                    th = (math.atan2(qy / q, qx) / (2 * math.pi)) % 1
                    ringV = .3 + .38 * (.5 + .5 * math.sin(rr * 13)) + .18 * pnoise(rr * 6, th * RP - t * RP, 41, pery=RP)
                    if qy < 0:
                        v = max(v, ringV * .85)
                if r < 1:
                    nz = math.sqrt(1 - r * r)
                    band = .5 + .5 * math.sin(qy * 5.5 + pnoise(qx * 1.5 + 1.5 + t * BP, qy * 2 + 3, 42, perx=BP) * 1.6)
                    sh = max(0, min(1, -px * .55 - py * .25 + nz * .8))
                    v = (.22 + .6 * band) * (.12 + .88 * sh)
                if inR and qy >= 0:
                    v = ringV
                f_[y * TW + x] = v
        frames.append(paint(f_, TW))
    return frames, T


def rain(TW, TH):
    """Digital Rain: each column is a track the drop laps an integer number
    of times per loop, glyphs mutate on per-cell cyclic schedules."""
    T, FPS = 6.0, 15
    N = int(T * FPS)
    G = '0123456789ABCDEFXZ<>[]{}=+*:;/\\|#$%&@?!~^'
    rnd = random.Random(11)
    seq = {}
    for y in range(TH):
        for x in range(TW):
            k = max(0, int(rnd.gauss(.8 * T, 1.5)))
            ts = sorted(rnd.uniform(0, T) for _ in range(k))
            ch = [rnd.choice(G) for _ in range(k + 1)]
            ch[-1] = ch[0]                          # last segment wraps into the first
            seq[x, y] = (ts, ch)

    def glyph(x, y, t):
        ts, ch = seq[x, y]
        j = 0
        while j < len(ts) and ts[j] <= t:
            j += 1
        return ch[j]

    cols = []
    for x in range(TW):
        ln = int(4 + rnd.random() * TH * .9)
        gap = rnd.uniform(2, TH * .6)
        C = TH + ln + gap
        m = max(1, round((6 + rnd.random() * 16) * T / C))
        on = [rnd.random() < .55 for _ in range(m)]
        cols.append(dict(len=ln, gap=gap, C=C, sp=m * C / T, m=m, on=on, o=rnd.uniform(0, C)))
    frames = []
    for i in range(N):
        t = i * T / N
        cells = []
        for x, q in enumerate(cols):
            p = q['sp'] * t + q['o']
            if not q['on'][int(p // q['C']) % q['m']]:
                continue
            hd = math.floor(p % q['C'] - q['gap'])
            for k in range(q['len']):
                y = hd - k
                if 0 <= y < TH:
                    cells.append((x, y, glyph(x, y, t), 0 if k == 0 else 1 if k < q['len'] * .35 else 2))
        frames.append(cells)
    return frames, T


# =====================================================================
# LIVE STATS (GitHub GraphQL, cached in stats.json)
# =====================================================================

QUERY = '''query($login:String!){user(login:$login){
  repositories(ownerAffiliations:OWNER,privacy:PUBLIC,first:100){totalCount nodes{stargazerCount}}
  contributionsCollection{contributionCalendar{totalContributions}}}}'''


def fetch_stats():
    """Pull fresh numbers when a token is set (the Action passes one), otherwise
    reuse stats.json. In CI a failed fetch fails the run so you hear about it."""
    try:
        old = json.load(open(STATS))
    except Exception:
        old = {}
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if not token:
        return old
    try:
        req = urllib.request.Request(
            'https://api.github.com/graphql',
            data=json.dumps({'query': QUERY, 'variables': {'login': USER}}).encode(),
            headers={'Authorization': f'bearer {token}', 'Content-Type': 'application/json',
                     'User-Agent': f'{USER}-readme'})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
        u = (d.get('data') or {}).get('user')
        if not u:
            raise RuntimeError(d.get('errors') or 'user not found')
        st = {
            'repos': u['repositories']['totalCount'],
            'stars': sum(n['stargazerCount'] for n in u['repositories']['nodes']),
            'synced': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d'),
        }
        cc = u.get('contributionsCollection')
        if cc:
            st['contributions'] = cc['contributionCalendar']['totalContributions']
        elif 'contributions' in old:
            st['contributions'] = old['contributions']
        with open(STATS, 'w') as fh:
            json.dump(st, fh, indent=2)
            fh.write('\n')
        print('stats', st)
        return st
    except Exception as e:
        print('stats fetch failed:', e)
        if os.environ.get('GITHUB_ACTIONS'):
            sys.exit(1)
        return old


def stat_lines(st):
    """boot log lines built from the numbers: value in white, words in grey"""
    num = lambda n: (f'{n:,}', 0)
    pl = lambda n, w: f'{w}{"" if n == 1 else "s"}'
    out = []
    if 'repos' in st:
        t = [num(st['repos']), (f' {pl(st["repos"], "repo")} indexed', 1)]
        if st.get('stars'):
            t += [(', ', 1), num(st['stars']), (f' {pl(st["stars"], "star")} collected', 1)]
        out.append(t)
    if 'contributions' in st:
        out.append([num(st['contributions']), (f' {pl(st["contributions"], "contribution")} in the last year', 1)])
    return out


# =====================================================================
# TERMINAL: boot log + a Monoglyph piece, as two contact-sheet cells
# =====================================================================

def terminal(PIECE, cap_name, boot_msg, stats=None):
    stats = stats or {}
    COLS, SROWS = 120, 20
    LC = 56                                # left cell cols, the piece gets the rest
    W, SH = COLS * CW, SROWS * CH
    H = SH + 38
    parts = []

    # ---- boot log
    PROMPT = 'avia@0x:~$ '
    OK = [('[', 2), ('  OK  ', 0), (']', 2)]
    WARN = [('[', 2), (' WARN ', 1), (']', 2)]
    lines = [
        dict(pre=[], gap=0, typed=[('0XAVIA BIOS v1.0', 0)]),
        dict(pre=[], gap=0, typed=[('cpu0: 1 core, 0 colours', 1)]),
        dict(pre=[], gap=0, typed=[('memory test .......... 640K OK', 1)]),
        dict(pre=OK, gap=1, typed=[('mounting /dev/avia', 1)]),
        dict(pre=OK, gap=1, typed=[(boot_msg, 1)]),
        *[dict(pre=OK, gap=1, typed=t) for t in stat_lines(stats)],
        dict(pre=WARN, gap=1, typed=[('github activity low, what do u expect lol', 1)]),
        dict(pre=OK, gap=1, typed=[('link established', 1)]),
        dict(pre=[], gap=0, typed=[]),
        dict(pre=[(PROMPT, 2)], gap=0, typed=[('cat about.txt', 0)]),
        dict(pre=[('discord + telegram bots, websites, panels, tools', 1)], gap=0, typed=[]),
        dict(pre=[(PROMPT, 2)], gap=0, typed=[('ls stack/', 0)]),
        dict(pre=[('html  css  ts  js  react  node  tailwind  c  luau', 1)], gap=0, typed=[]),
        dict(pre=[(PROMPT, 2)], gap=0, typed=[]),
    ]
    CPS = 55.0
    X0, Y0 = 2, 1
    S = 0
    timing = []
    for ln in lines:
        plen = sum(len(s) for s, _ in ln['pre'])
        tlen = sum(len(s) for s, _ in ln['typed'])
        timing.append((S, plen, tlen))
        S += tlen + 6
    HOLD = 7.0                             # seconds the finished log stays up before it reboots
    L = S / CPS + HOLD

    cur_events = [(0, (X0, Y0))]
    for j, ln in enumerate(lines):
        Sj, plen, tlen = timing[j]
        row = Y0 + j
        tstart = plen + ln['gap']
        cells = {0: [], 1: [], 2: []}
        col = X0
        for s, lv in ln['pre']:
            for ch in s:
                cells[lv].append((col, row, ch))
                col += 1
        col = X0 + tstart
        for s, lv in ln['typed']:
            for ch in s:
                cells[lv].append((col, row, ch))
                col += 1
        t_vis = (Sj + (1 if Sj == 0 else 0)) / CPS
        ev = [(0, 0), (t_vis, plen)]
        cur_events.append((t_vis, (X0 + (tstart if tlen else plen), row)))
        for k in range(1, tlen + 1):
            tk = (Sj + 6 + k) / CPS
            ev.append((tk, tstart + k))
            cur_events.append((tk, (X0 + tstart + k, row)))
        body = ''.join(texts(cells[lv], f'l{lv}') for lv in (0, 1, 2))
        clip = discrete('width', ev, L, lambda n: str(n * CW))
        parts.append(f'<clipPath id="ln{j}"><rect x="{X0 * CW}" y="{row * CH}" width="0" height="{CH}">{clip}</rect></clipPath>'
                     f'<g class="t" clip-path="url(#ln{j})">{body}</g>')
    cur_events.sort(key=lambda e: e[0])
    cx = discrete('x', [(t, p) for t, p in cur_events], L, lambda p: str(p[0] * CW))
    cy = discrete('y', [(t, p) for t, p in cur_events], L, lambda p: str(p[1] * CH + 1))
    parts.append(f'<rect width="{CW}" height="{CH - 2}" fill="{TONE[0]}" x="{X0 * CW}" y="{Y0 * CH + 1}">{cx}{cy}'
                 '<animate attributeName="opacity" values="1;0" keyTimes="0;.5" dur=".8s" repeatCount="indefinite" calcMode="discrete"/></rect>')

    frames = []
    pframes, TL = PIECE(COLS - LC, SROWS)
    N = len(pframes)
    for i, pc in enumerate(pframes):
        cells = {0: [], 1: [], 2: []}
        for c, r, ch, lv in pc:
            cells[lv].append((LC + c, r, ch))
        body = ''.join(texts(cells[lv], f'l{lv}') for lv in (0, 1, 2))
        frames.append(f'<g class="t" visibility="hidden">{vis(i * TL / N, (i + 1) * TL / N, TL)}{body}</g>')
    parts.append('<g filter="url(#glow)">' + ''.join(frames) + '</g>')

    # ---- captions, Monoglyph card style
    def cap(x_left, x_right, name, sub=''):
        sub = f'<tspan class="kd" dx="12">{sub}</tspan>' if sub else ''
        return (f'<text class="cap" x="{x_left}" y="{SH + 23}">{name}{sub}</text>'
                f'<text class="kd" x="{x_right}" y="{SH + 23}" text-anchor="end">LIVE</text>')
    synced = ''
    if stats.get('synced'):
        synced = 'SYNCED ' + datetime.date.fromisoformat(stats['synced']).strftime('%d %b %Y').upper()
    parts.append(cap(14, LC * CW - 14, 'boot.log', synced))
    parts.append(cap(LC * CW + 14, W - 14, cap_name))

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
           f'aria-label="Boot log typing out next to an ASCII {cap_name}">'
           f'<title>boot.log + {cap_name}</title>{style()}<defs>{defs_common()}</defs>'
           f'<rect width="{W}" height="{H}" rx="5" fill="#000"/>'
           + ''.join(parts) +
           f'<path d="M{LC * CW + .5} 1V{H - 1}" stroke="{LINE}"/>'
           f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="4.5" fill="none" stroke="{LINE}"/></svg>')
    return svg, L


PANELS = {
    'ringed': (ringed, 'ringed giant', 'pulling a gas giant into orbit'),
    'rain': (rain, 'digital rain', 'starting digital rain'),
    'torus': (torus, 'spinning torus', 'spinning up torus'),
}


def write(name, svg):
    with open(os.path.join(OUT, name), 'w', encoding='ascii') as fh:
        fh.write(svg + '\n')
    print(name, len(svg) // 1024, 'KB')


if __name__ == '__main__':
    # python3 gen.py         -> header + the PANEL you picked above
    # python3 gen.py --all   -> header + every panel variant
    stats = fetch_stats()
    write('header.svg', header())
    for key in (PANELS if '--all' in sys.argv else [PANEL]):
        piece, cap_name, msg = PANELS[key]
        svg, _ = terminal(piece, cap_name, msg, stats)
        write(f'terminal-{key}.svg', svg)

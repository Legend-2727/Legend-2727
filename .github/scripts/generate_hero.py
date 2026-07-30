#!/usr/bin/env python3
"""
Generate the theme-aware animated hero banner (dark.svg / light.svg).

One terminal window, 1180x610:
  * left  VISUAL.MAP  — ASCII-art portrait built from assets/avatar.jpg.
                        It types in row by row, then the tiles scatter and a
                        particle field morphs through qubit / circuit / neural
                        shapes before the portrait reassembles.
  * right SYSTEM.INFO — dotted-leader spec sheet with a typing cursor.

Everything is deterministic: same avatar + same PROFILE => byte-identical SVG.

    python3 .github/scripts/generate_hero.py assets/avatar.jpg .
"""
import html
import math
import os
import random
import sys

from PIL import Image, ImageEnhance, ImageOps

# --------------------------------------------------------------------------
# profile content
# --------------------------------------------------------------------------
NAME = "Farhad Al-Amin Dipto"
EMAIL = "alaminfarhad27@gmail.com"

INFO_BLOCKS = [
    [
        ("Subject", NAME),
        ("Role", "Research Scientist, GenMd (California)"),
        ("Focus", "LLM fine-tuning, model training, evaluation"),
        ("Education", "BSc in CSE, BUET"),
        ("Research", "2 first-author NLP papers under review"),
        ("Status", "Training + Evaluating + Shipping"),
    ],
    [
        ("Core.ML", "PyTorch, Hugging Face, PEFT"),
        ("Core.LLM", "LoRA / QLoRA, instruction tuning, RAG"),
        ("Core.Eval", "calibration, abstention, LLM-as-judge"),
        ("Core.Vision", "vision-language models, ViT + XLM-R"),
        ("Core.Lang", "Python, Java, C++, TypeScript, SQL"),
    ],
    [
        ("Grid.Mail", EMAIL),
        ("Grid.Portfolio", "legend-2727.github.io/Farhad-Al-Amin"),
        ("Grid.LinkedIn", "al-amin-farhad"),
        ("Grid.GitHub", "@Legend-2727"),
        ("Grid.YouTube", "ScholarAI demos"),
    ],
]
SEPARATOR_LABEL = "Contact"
FOOTER = "▸ More about me & projects below in README ↓"

# --------------------------------------------------------------------------
# canvas / layout
# --------------------------------------------------------------------------
W, H = 1180, 610
BAR_H = 46
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

PANEL_X, PANEL_Y, PANEL_W, PANEL_H = 36, 84, 400, 492
PAD = 10
ART_X = PANEL_X + PAD                      # 46
ART_Y = PANEL_Y + PAD                      # 94
ART_W = PANEL_W - 2 * PAD                  # 380
ART_H = PANEL_H - 2 * PAD                  # 472

COLS, ROWS = 94, 58
CELL_W = ART_W / COLS                       # 4.04
CELL_H = ART_H / ROWS                       # 8.14
ASCII_FS = round(CELL_H * 0.98, 2)

TILE_C, TILE_R = 12, 8                      # cells per scatter tile -> 8 x 8 tiles

INFO_X = 470
INFO_LEN = 655
INFO_FS = 14
INFO_COLS = 79                              # characters per dotted-leader row
LINE_STEP = 23
BLOCK_GAP = 8

PARTICLES = 900
LOOP = 20.0                                  # seconds per full cycle
INTRO = 3.4                                  # seconds of type-in before looping

# keyTimes shared by every looping animation
KTS = "0;.3;.36;.47;.53;.64;.7;.81;.88;1"
ASCII_OPACITY = "1;1;0;0;0;0;0;0;1;1"
PART_OPACITY = "0;0;1;1;1;1;1;1;0;0"
LOOP_SPLINE = ";".join([".5 0 .3 1"] * 9)

# Glyphs ordered by measured ink coverage in a monospace face, sampled at even
# steps so luminance maps to density linearly instead of to arbitrary symbols.
RAMP = " .-,;+(t5wO8MQg@"

THEMES = {
    "dark": {
        "OUT": "#070B16", "P1": "#0A101F", "P2": "#0C1426", "BAR": "#0B1222",
        "CYAN": "#22D3EE", "VIOLET": "#A78BFA", "VIOLET2": "#7C3AED",
        "EMERALD": "#10B981", "BLUE": "#60A5FA",
        "TEXT": "#F8FAFC", "MUTED": "#94A3B8", "DIM": "#475569",
        "HAIR": "rgba(255,255,255,0.10)", "GRID": "rgba(34,211,238,0.055)",
        "PANEL_STROKE": "rgba(34,211,238,0.35)", "SCAN": "rgba(34,211,238,0.10)",
        "BADGE_BG": "#4C1D95", "BADGE_TX": "#E9D5FF", "LIVE": "#F87171",
        "ASCII": ("#7DD3FC", "#C4B5FD", "#5EEAD4"), "PARTICLE": "#A78BFA",
    },
    "light": {
        "OUT": "#FFFFFF", "P1": "#F8FAFC", "P2": "#F1F5F9", "BAR": "#F1F5F9",
        "CYAN": "#0891B2", "VIOLET": "#7C3AED", "VIOLET2": "#6D28D9",
        "EMERALD": "#059669", "BLUE": "#2563EB",
        "TEXT": "#0F172A", "MUTED": "#475569", "DIM": "#94A3B8",
        "HAIR": "rgba(15,23,42,0.10)", "GRID": "rgba(8,145,178,0.07)",
        "PANEL_STROKE": "rgba(8,145,178,0.35)", "SCAN": "rgba(8,145,178,0.10)",
        "BADGE_BG": "#EDE9FE", "BADGE_TX": "#5B21B6", "LIVE": "#DC2626",
        "ASCII": ("#1D4ED8", "#6D28D9", "#0E7490"), "PARTICLE": "#7C3AED",
    },
}


def esc(s):
    return html.escape(str(s), quote=False)


# --------------------------------------------------------------------------
# ascii portrait
# --------------------------------------------------------------------------
def build_ascii(path):
    """Return ROWS strings of COLS chars: bright pixels -> dense glyphs."""
    img = Image.open(path).convert("L")
    iw, ih = img.size

    # crop to the panel aspect, biased upward so the face stays centred
    want = ART_W / ART_H
    if iw / ih > want:
        nw = int(round(ih * want))
        left = (iw - nw) // 2
        img = img.crop((left, 0, left + nw, ih))
    else:
        nh = int(round(iw / want))
        top = int((ih - nh) * 0.32)
        img = img.crop((0, top, iw, top + nh))

    # clip hard at the top so blown-out highlights in the background stop
    # eating the range the subject needs
    img = ImageOps.autocontrast(img, cutoff=(2, 12))
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    img = img.resize((COLS, ROWS), Image.LANCZOS)
    img = ImageEnhance.Contrast(img).enhance(1.32)

    px = img.load()
    n = len(RAMP) - 1
    out = []
    for y in range(ROWS):
        row = []
        for x in range(COLS):
            row.append(RAMP[int(round(px[x, y] / 255.0 * n))])
        out.append("".join(row))
    return out


def ascii_layer(rows, rnd):
    """Tiled ASCII art: each tile types in, then scatters away and returns.

    The show/hide half of the loop is identical for every tile, so it lives on
    the wrapper group -- only the scatter vector is per tile.
    """
    out = [f'<g transform="translate({ART_X},{ART_Y})" fill="url(#asciiGrad)" '
           f'font-size="{ASCII_FS}" xml:space="preserve">',
           f'<animate attributeName="opacity" values="{ASCII_OPACITY}" '
           f'keyTimes="{KTS}" dur="{LOOP}s" begin="{INTRO}s" repeatCount="indefinite"/>']
    tiles_x = math.ceil(COLS / TILE_C)
    tiles_y = math.ceil(ROWS / TILE_R)
    for ty in range(tiles_y):
        for tx in range(tiles_x):
            c0, c1 = tx * TILE_C, min(COLS, (tx + 1) * TILE_C)
            r0, r1 = ty * TILE_R, min(ROWS, (ty + 1) * TILE_R)
            frags = []
            for r in range(r0, r1):
                s = rows[r][c0:c1]
                if not s.strip():
                    continue
                # trim blank margins: x and textLength stay exact, bytes drop
                lead = len(s) - len(s.lstrip(" "))
                s = s.strip(" ")
                frags.append(
                    f'<text x="{(c0 + lead) * CELL_W:.1f}" y="{(r + 0.82) * CELL_H:.1f}" '
                    f'textLength="{len(s) * CELL_W:.1f}" '
                    f'lengthAdjust="spacingAndGlyphs">{esc(s)}</text>')
            if not frags:
                continue

            # scatter vector: pushed away from the panel centre with some jitter
            cx = (c0 + c1) / 2 / COLS - 0.5
            cy = (r0 + r1) / 2 / ROWS - 0.5
            mag = 120 + rnd.random() * 90
            dx = cx * mag * 2.4 + rnd.uniform(-26, 26)
            dy = cy * mag * 2.4 + rnd.uniform(-26, 26)
            sc = f"{dx:.0f} {dy:.0f}"
            tvals = ";".join(["0 0", "0 0", sc, sc, sc, sc, sc, sc, "0 0", "0 0"])

            delay = 0.18 + (r0 / ROWS) * 2.1 + rnd.random() * 0.16
            out.append(
                f'<g opacity="0">'
                f'<animate attributeName="opacity" values="0;1" dur="0.55s" '
                f'begin="{delay:.2f}s" fill="freeze" calcMode="spline" '
                f'keyTimes="0;1" keySplines=".4 0 .2 1"/>'
                f'<animateTransform attributeName="transform" type="translate" '
                f'values="{tvals}" keyTimes="{KTS}" dur="{LOOP}s" begin="{INTRO}s" '
                f'repeatCount="indefinite" calcMode="spline" keySplines="{LOOP_SPLINE}"/>'
                + "".join(frags) + "</g>")
    out.append("</g>")
    return "".join(out)


# --------------------------------------------------------------------------
# particle shapes  (local panel space: 0..ART_W x 0..ART_H)
# --------------------------------------------------------------------------
CX, CY = ART_W / 2, ART_H / 2


def _resample(pts, n, rnd):
    """Force a point list to exactly n points, then order it for smooth morphs."""
    if not pts:
        pts = [(CX, CY)]
    pts = list(pts)
    while len(pts) < n:
        x, y = pts[rnd.randrange(len(pts))]
        pts.append((x + rnd.uniform(-1.4, 1.4), y + rnd.uniform(-1.4, 1.4)))
    if len(pts) > n:
        step = len(pts) / n
        pts = [pts[int(i * step)] for i in range(n)]
    pts.sort(key=lambda p: (round(math.atan2(p[1] - CY, p[0] - CX), 2),
                            math.hypot(p[0] - CX, p[1] - CY)))
    return pts


def _line(x1, y1, x2, y2, n):
    return [(x1 + (x2 - x1) * i / (n - 1), y1 + (y2 - y1) * i / (n - 1))
            for i in range(max(n, 2))]


def _ring(cx, cy, rx, ry, n, rot=0.0):
    out = []
    c, s = math.cos(rot), math.sin(rot)
    for i in range(n):
        a = 2 * math.pi * i / n
        x, y = rx * math.cos(a), ry * math.sin(a)
        out.append((cx + x * c - y * s, cy + x * s + y * c))
    return out


def _disc(cx, cy, r, n, rnd):
    out = []
    for _ in range(n):
        a = rnd.random() * 2 * math.pi
        d = r * math.sqrt(rnd.random())
        out.append((cx + d * math.cos(a), cy + d * math.sin(a)))
    return out


def shape_portrait(rows, rnd):
    """Particles sitting on the brightest cells of the portrait."""
    cells = []
    n = len(RAMP) - 1
    for r, line in enumerate(rows):
        for c, ch in enumerate(line):
            w = RAMP.index(ch) if ch in RAMP else 0
            if w > n * 0.45:
                cells.append(((c + 0.5) * CELL_W, (r + 0.5) * CELL_H))
    rnd.shuffle(cells)
    return cells


def shape_qubit(rnd):
    """Bloch sphere / atom: nucleus plus three tilted orbits."""
    pts = _disc(CX, CY, 15, 90, rnd)
    for k, rot in enumerate((0.0, math.pi / 3, 2 * math.pi / 3)):
        pts += _ring(CX, CY, 150, 54, 210, rot)
        a = 0.7 + k * 2.1
        ex = CX + 150 * math.cos(a) * math.cos(rot) - 54 * math.sin(a) * math.sin(rot)
        ey = CY + 150 * math.cos(a) * math.sin(rot) + 54 * math.sin(a) * math.cos(rot)
        pts += _disc(ex, ey, 7, 26, rnd)
    pts += _ring(CX, CY, 176, 176, 120)
    return pts


def shape_circuit(rnd):
    """A little quantum circuit: four wires, gates and a CNOT."""
    x0, x1 = CX - 155, CX + 155
    wires = [CY - 96, CY - 32, CY + 32, CY + 96]
    pts = []
    for wy in wires:
        pts += _line(x0, wy, x1, wy, 130)
    gates = [(0, -78), (1, -14), (2, 50), (3, 114), (0, 114), (2, -78)]
    for wi, gx in gates:
        wy = wires[wi]
        x, s = CX + gx, 21
        pts += _line(x - s, wy - s, x + s, wy - s, 22)
        pts += _line(x + s, wy - s, x + s, wy + s, 22)
        pts += _line(x + s, wy + s, x - s, wy + s, 22)
        pts += _line(x - s, wy + s, x - s, wy - s, 22)
    # CNOT: control dot on wire 1, target ring on wire 3
    pts += _disc(CX + 22, wires[1], 7, 26, rnd)
    pts += _line(CX + 22, wires[1], CX + 22, wires[3], 34)
    pts += _ring(CX + 22, wires[3], 15, 15, 44)
    pts += _line(CX + 7, wires[3], CX + 37, wires[3], 14)
    return pts


def shape_neural(rnd):
    """A 4-6-6-3 network with edges drawn as dotted point runs."""
    layers = [4, 6, 6, 3]
    xs = [CX - 150, CX - 50, CX + 50, CX + 150]
    nodes = []
    for li, count in enumerate(layers):
        span = 78 * (count - 1)
        col = [(xs[li], CY - span / 2 + 78 * i) if count > 1 else (xs[li], CY)
               for i in range(count)]
        if count > 1:
            span = min(360, 78 * (count - 1))
            col = [(xs[li], CY - span / 2 + span * i / (count - 1))
                   for i in range(count)]
        nodes.append(col)
    pts = []
    for col in nodes:
        for (nx, ny) in col:
            pts += _ring(nx, ny, 13, 13, 26)
            pts += _disc(nx, ny, 5, 8, rnd)
    for li in range(len(nodes) - 1):
        for (ax, ay) in nodes[li]:
            for (bx, by) in nodes[li + 1]:
                pts += _line(ax, ay, bx, by, 9)[1:-1]
    return pts


def particle_layer(rows, colour, rnd):
    portrait = _resample(shape_portrait(rows, rnd), PARTICLES, rnd)
    a = _resample(shape_qubit(rnd), PARTICLES, rnd)
    b = _resample(shape_circuit(rnd), PARTICLES, rnd)
    c = _resample(shape_neural(rnd), PARTICLES, rnd)

    # every particle shares the same fade timeline -> hoist it to the wrapper
    out = [f'<defs><rect id="px" width="2.6" height="1.9" rx="0.6" fill="{colour}"/></defs>',
           f'<g transform="translate({ART_X},{ART_Y})" opacity="0">',
           f'<animate attributeName="opacity" values="{PART_OPACITY}" '
           f'keyTimes="{KTS}" dur="{LOOP}s" begin="{INTRO}s" repeatCount="indefinite"/>']
    for i in range(PARTICLES):
        p, q, r, s = portrait[i], a[i], b[i], c[i]
        seq = [p, p, q, q, r, r, s, s, p, p]
        vals = ";".join(f"{x:.0f} {y:.0f}" for x, y in seq)
        out.append(
            f'<use href="#px">'
            f'<animateTransform attributeName="transform" type="translate" '
            f'values="{vals}" keyTimes="{KTS}" dur="{LOOP}s" begin="{INTRO}s" '
            f'repeatCount="indefinite"/></use>')
    out.append("</g>")
    return "".join(out)


# --------------------------------------------------------------------------
# system.info panel
# --------------------------------------------------------------------------
def leader(label, value, width=INFO_COLS):
    """label, dot run, value — kept as three pieces so each can be coloured."""
    n = max(width - len(label) - len(value) - 2, 1)
    return label, "." * n, value


def info_layer(t):
    out = []
    a = out.append
    a(f'<text x="{INFO_X}" y="106" font-size="13" letter-spacing="2" '
      f'fill="{t["CYAN"]}" filter="url(#txtGlow)">SYSTEM.INFO</text>')
    a(f'<line x1="{INFO_X + 96}" y1="102" x2="1061" y2="102" stroke="{t["HAIR"]}"/>')
    a(f'<text x="1125" y="106" text-anchor="end" font-size="12" fill="{t["LIVE"]}" '
      f'font-weight="700">&#9679; LIVE'
      f'<animate attributeName="opacity" values="1;0.25;1" dur="2.2s" '
      f'repeatCount="indefinite"/></text>')

    bw = int(len(EMAIL) * 8.65 + 20)
    a(f'<rect x="{INFO_X}" y="122" width="{bw}" height="20" rx="4" fill="{t["BADGE_BG"]}"/>')
    a(f'<text x="{INFO_X + 9}" y="136" font-size="14" font-weight="700" '
      f'fill="{t["BADGE_TX"]}">{esc(EMAIL)}</text>')
    a(f'<line x1="{INFO_X + bw + 10}" y1="130" x2="1125" y2="130" stroke="{t["HAIR"]}"/>')

    lines = []
    for bi, block in enumerate(INFO_BLOCKS):
        if bi == 2:
            pad = INFO_COLS - len(SEPARATOR_LABEL) - 4
            lines.append(("sep", f"- {SEPARATOR_LABEL} {'-' * max(pad, 1)}"))
        for label, value in block:
            lines.append(("row", leader(label, value)))
        if bi < len(INFO_BLOCKS) - 1:
            lines.append(("gap", None))

    y = 162
    delay = 0.55
    ys = []
    for kind, text in lines:
        if kind == "gap":
            y += BLOCK_GAP
            continue
        if kind == "sep":
            a(f'<text x="{INFO_X}" y="{y}" font-size="{INFO_FS}" textLength="{INFO_LEN}" '
              f'lengthAdjust="spacingAndGlyphs" xml:space="preserve" fill="{t["DIM"]}" '
              f'opacity="0"><animate attributeName="opacity" values="0;1" dur="0.28s" '
              f'begin="{delay:.2f}s" fill="freeze"/>{esc(text)}</text>')
        else:
            label, dots, value = text
            a(f'<text x="{INFO_X}" y="{y}" font-size="{INFO_FS}" textLength="{INFO_LEN}" '
              f'lengthAdjust="spacingAndGlyphs" xml:space="preserve" opacity="0">'
              f'<animate attributeName="opacity" values="0;1" dur="0.28s" '
              f'begin="{delay:.2f}s" fill="freeze"/>'
              f'<tspan fill="{t["CYAN"]}">{esc(label)}</tspan>'
              f'<tspan fill="{t["DIM"]}"> {esc(dots)} </tspan>'
              f'<tspan fill="{t["TEXT"]}">{esc(value)}</tspan></text>')
        ys.append(y)
        y += LINE_STEP
        delay += 0.11

    # block cursor that walks down the panel while the lines type in
    cvals = ";".join(f"0 {yy - ys[0]}" for yy in ys)
    ckt = ";".join(f"{i / (len(ys) - 1):.3f}" for i in range(len(ys)))
    a(f'<g><animateTransform attributeName="transform" type="translate" '
      f'values="{cvals}" keyTimes="{ckt}" dur="{delay - 0.55:.2f}s" begin="0.55s" '
      f'calcMode="discrete" fill="freeze"/>'
      f'<rect x="{INFO_X + INFO_LEN + 6}" y="{ys[0] - 11}" width="8" height="14" '
      f'fill="{t["EMERALD"]}"><animate attributeName="opacity" values="1;0;1" '
      f'dur="0.9s" repeatCount="indefinite"/></rect></g>')

    a(f'<text x="{INFO_X}" y="577" font-size="14" fill="{t["MUTED"]}" opacity="0">'
      f'<animate attributeName="opacity" values="0;1" dur="0.5s" begin="{delay:.2f}s" '
      f'fill="freeze"/>{esc(FOOTER)} '
      f'<tspan fill="{t["EMERALD"]}">&#9608;<animate attributeName="opacity" '
      f'values="1;0;1" dur="1s" repeatCount="indefinite"/></tspan></text>')
    return "".join(out)


# --------------------------------------------------------------------------
# window chrome
# --------------------------------------------------------------------------
def build(rows, theme):
    t = THEMES[theme]
    rnd = random.Random(20727)               # deterministic output
    c1, c2, c3 = t["ASCII"]
    s = []
    a = s.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
      f'viewBox="0 0 {W} {H}" font-family="{FONT}" role="img" '
      f'aria-label="{esc(NAME)} - profile.sh --live">')

    a('<defs>')
    a(f'<linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">'
      f'<stop offset="0" stop-color="{t["VIOLET2"]}"><animate attributeName="stop-color" '
      f'values="{t["VIOLET2"]};{t["CYAN"]};{t["EMERALD"]};{t["VIOLET2"]}" dur="10s" '
      f'repeatCount="indefinite"/></stop>'
      f'<stop offset="0.5" stop-color="{t["CYAN"]}"><animate attributeName="stop-color" '
      f'values="{t["CYAN"]};{t["EMERALD"]};{t["VIOLET2"]};{t["CYAN"]}" dur="10s" '
      f'repeatCount="indefinite"/></stop>'
      f'<stop offset="1" stop-color="{t["EMERALD"]}"><animate attributeName="stop-color" '
      f'values="{t["EMERALD"]};{t["VIOLET2"]};{t["CYAN"]};{t["EMERALD"]}" dur="10s" '
      f'repeatCount="indefinite"/></stop></linearGradient>')
    a(f'<linearGradient id="asciiGrad" x1="0" y1="0" x2="0" y2="{ART_H}" '
      f'gradientUnits="userSpaceOnUse">'
      f'<stop offset="0" stop-color="{c1}"/><stop offset="0.45" stop-color="{c2}"/>'
      f'<stop offset="1" stop-color="{c3}"/>'
      f'<animateTransform attributeName="gradientTransform" type="translate" '
      f'values="0 -120; 0 120; 0 -120" dur="9s" repeatCount="indefinite"/>'
      f'</linearGradient>')
    a(f'<linearGradient id="panelGrad" x1="0" y1="0" x2="0" y2="1">'
      f'<stop offset="0" stop-color="{t["P1"]}"/>'
      f'<stop offset="1" stop-color="{t["P2"]}"/></linearGradient>')
    a('<filter id="glow8" x="-60%" y="-60%" width="220%" height="220%">'
      '<feGaussianBlur stdDeviation="8"/></filter>')
    a('<filter id="glow3" x="-60%" y="-60%" width="220%" height="220%">'
      '<feGaussianBlur stdDeviation="3"/></filter>')
    a('<filter id="txtGlow" x="-30%" y="-30%" width="160%" height="160%">'
      '<feGaussianBlur stdDeviation="0.9" result="b"/><feMerge>'
      '<feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')
    a(f'<clipPath id="winClip"><rect x="2" y="2" width="{W - 4}" height="{H - 4}" rx="18"/></clipPath>')
    a(f'<clipPath id="artClip"><rect x="{PANEL_X}" y="{PANEL_Y}" width="{PANEL_W}" '
      f'height="{PANEL_H}" rx="10"/></clipPath>')
    a('</defs>')

    a(f'<rect x="2" y="2" width="{W - 4}" height="{H - 4}" rx="18" fill="{t["OUT"]}"/>')
    a('<g clip-path="url(#winClip)">')
    a(f'<rect x="2" y="2" width="{W - 4}" height="{H - 4}" fill="url(#panelGrad)"/>')

    # title bar
    a(f'<rect x="2" y="2" width="{W - 4}" height="{BAR_H}" fill="{t["BAR"]}"/>')
    a(f'<line x1="2" y1="{BAR_H + 2}" x2="{W - 2}" y2="{BAR_H + 2}" stroke="{t["HAIR"]}"/>')
    for i, col in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        a(f'<circle cx="{30 + i * 20}" cy="25" r="5.5" fill="{col}"/>')
    a(f'<text x="{W / 2:.0f}" y="29" text-anchor="middle" font-size="12" '
      f'fill="{t["MUTED"]}">{esc(EMAIL)} - % ./profile.sh --live'
      f'<tspan fill="{t["EMERALD"]}">_<animate attributeName="opacity" values="1;0;1" '
      f'dur="1.1s" repeatCount="indefinite"/></tspan></text>')

    # left panel
    a(f'<text x="38" y="74" font-size="10" letter-spacing="3" fill="{t["DIM"]}">VISUAL.MAP</text>')
    a(f'<text x="{PANEL_X + PANEL_W - 2}" y="74" text-anchor="end" font-size="10" '
      f'letter-spacing="1" fill="{t["DIM"]}">render --ascii</text>')
    a(f'<rect x="{PANEL_X}" y="{PANEL_Y}" width="{PANEL_W}" height="{PANEL_H}" rx="10" '
      f'fill="none" stroke="{t["CYAN"]}" stroke-width="2" opacity="0.45" filter="url(#glow3)"/>')
    a(f'<rect x="{PANEL_X}" y="{PANEL_Y}" width="{PANEL_W}" height="{PANEL_H}" rx="10" '
      f'fill="{t["P1"]}" stroke="{t["PANEL_STROKE"]}"/>')

    a('<g clip-path="url(#artClip)">')
    for gx in range(0, PANEL_W, 40):
        a(f'<line x1="{PANEL_X + gx}" y1="{PANEL_Y}" x2="{PANEL_X + gx}" '
          f'y2="{PANEL_Y + PANEL_H}" stroke="{t["GRID"]}"/>')
    for gy in range(0, PANEL_H, 40):
        a(f'<line x1="{PANEL_X}" y1="{PANEL_Y + gy}" x2="{PANEL_X + PANEL_W}" '
          f'y2="{PANEL_Y + gy}" stroke="{t["GRID"]}"/>')
    a(ascii_layer(rows, rnd))
    a(particle_layer(rows, t["PARTICLE"], rnd))
    # scanline sweep
    a(f'<rect x="{PANEL_X}" y="{PANEL_Y}" width="{PANEL_W}" height="26" fill="{t["SCAN"]}">'
      f'<animateTransform attributeName="transform" type="translate" '
      f'values="0 -30; 0 {PANEL_H + 10}" dur="5.5s" repeatCount="indefinite"/></rect>')
    a('</g>')

    # corner brackets
    for (bx, by, sx, sy) in ((PANEL_X, PANEL_Y, 1, 1), (PANEL_X + PANEL_W, PANEL_Y, -1, 1),
                             (PANEL_X, PANEL_Y + PANEL_H, 1, -1),
                             (PANEL_X + PANEL_W, PANEL_Y + PANEL_H, -1, -1)):
        a(f'<path d="M{bx + sx * 2} {by + sy * 22}L{bx + sx * 2} {by + sy * 2}'
          f'L{bx + sx * 22} {by + sy * 2}" fill="none" stroke="{t["CYAN"]}" '
          f'stroke-width="2" opacity="0.75"/>')

    a(info_layer(t))
    a('</g>')

    # animated border
    a(f'<rect x="3" y="3" width="{W - 6}" height="{H - 6}" rx="17" fill="none" '
      f'stroke="url(#accent)" stroke-width="3" opacity="0.55" filter="url(#glow8)"/>')
    a(f'<rect x="3" y="3" width="{W - 6}" height="{H - 6}" rx="17" fill="none" '
      f'stroke="url(#accent)" stroke-width="1.6"/>')
    a('</svg>')
    return "".join(s)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "assets/avatar.jpg"
    outdir = sys.argv[2] if len(sys.argv) > 2 else "."
    for theme, fname in (("dark", "dark.svg"), ("light", "light.svg")):
        rows = build_ascii(src)
        svg = build(rows, theme)
        path = os.path.join(outdir, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"wrote {path}  ({len(svg) // 1024} KB)")


if __name__ == "__main__":
    main()

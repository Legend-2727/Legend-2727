#!/usr/bin/env python3
"""
Render the projects panel (projects.svg / projects-light.svg).

A two-column grid of mini terminal cards styled to match the hero banner.
Content comes from projects.json; stars, languages and last-push are merged in
by fetch_data.py at build time. Add, remove or reorder projects by editing
projects.json alone -- the README never changes.

    python3 .github/scripts/generate_projects.py merged.json out
"""
import base64
import html
import json
import math
import os
import sys
from datetime import datetime, timezone

THEMES = {
    "dark": {
        "BG": "#0A101F", "CARD": "#0C1426", "CARD_BAR": "#0B1222",
        "CYAN": "#22D3EE", "VIOLET": "#A78BFA", "VIOLET2": "#7C3AED",
        "EMERALD": "#10B981", "TEXT": "#F8FAFC", "MUTED": "#94A3B8",
        "DIM": "#475569", "MONO_TX": "#EDE9FE",
        "STROKE": "rgba(34,211,238,0.28)", "STROKE_HI": "rgba(34,211,238,0.50)",
        "STROKE_LO": "rgba(34,211,238,0.18)", "BARLINE": "rgba(255,255,255,0.08)",
        "RING": "rgba(148,163,184,0.15)", "PILL": "rgba(124,58,237,0.28)",
        "PILL_STROKE": "rgba(167,139,250,0.5)",
    },
    "light": {
        "BG": "#F8FAFC", "CARD": "#FFFFFF", "CARD_BAR": "#F1F5F9",
        "CYAN": "#0891B2", "VIOLET": "#7C3AED", "VIOLET2": "#6D28D9",
        "EMERALD": "#059669", "TEXT": "#0F172A", "MUTED": "#475569",
        "DIM": "#94A3B8", "MONO_TX": "#FFFFFF",
        "STROKE": "rgba(8,145,178,0.30)", "STROKE_HI": "rgba(8,145,178,0.55)",
        "STROKE_LO": "rgba(8,145,178,0.18)", "BARLINE": "rgba(15,23,42,0.08)",
        "RING": "rgba(100,116,139,0.20)", "PILL": "rgba(124,58,237,0.12)",
        "PILL_STROKE": "rgba(124,58,237,0.40)",
    },
}

W = 1180
CARD_W, CARD_H = 578, 168
GAP, MARGIN = 14, 5
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"


def esc(s):
    return html.escape(str(s), quote=True)


def donut_colours(t):
    return [t["VIOLET"], t["CYAN"], t["EMERALD"], "#6366F1", "#64748B", "#94A3B8"]


def rel_time(iso):
    if not iso:
        return "n/a"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        d = datetime.now(timezone.utc) - dt
    except Exception:
        return "n/a"
    if d.days > 365:
        return f"{d.days // 365}y ago"
    if d.days > 30:
        return f"{d.days // 30}mo ago"
    if d.days > 0:
        return f"{d.days}d ago"
    h = d.seconds // 3600
    return f"{h}h ago" if h else "just now"


def logo_b64(name):
    if not name:
        return None
    for base in ("logos", "."):
        p = os.path.join(base, name)
        if os.path.exists(p):
            ext = os.path.splitext(p)[1].lower().lstrip(".")
            mime = {"png": "image/png", "svg": "image/svg+xml", "jpg": "image/jpeg",
                    "jpeg": "image/jpeg", "webp": "image/webp"}.get(ext, "image/png")
            with open(p, "rb") as f:
                return f"data:{mime};base64," + base64.b64encode(f.read()).decode()
    return None


def wrap(text, width, max_lines=2):
    lines, cur = [], ""
    for word in text.split():
        if len(cur) + len(word) + 1 <= width:
            cur = f"{cur} {word}".strip()
        else:
            lines.append(cur)
            cur = word
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and len(" ".join(lines)) < len(text):
        lines[-1] = lines[-1][:width - 1].rstrip() + "…"
    return lines


def donut(langs, cx, cy, r, begin, t):
    """Language split as a ring whose segments draw themselves in sequence."""
    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:4]
    other = total - sum(v for _, v in top)
    if other > 0:
        top.append(("Other", other))
    circumference = 2 * math.pi * r
    colours = donut_colours(t)
    parts, legend, offset, at = [], [], 0.0, begin
    for i, (lang, v) in enumerate(top):
        frac = v / total
        seg = frac * circumference
        col = colours[i % len(colours)]
        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{col}" '
            f'stroke-width="9" stroke-dasharray="{seg:.2f} {circumference - seg:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {cx} {cy})" opacity="0">'
            f'<animate attributeName="opacity" from="0" to="1" dur="0.01s" '
            f'begin="{at:.2f}s" fill="freeze"/>'
            f'<animate attributeName="stroke-dasharray" from="0 {circumference:.2f}" '
            f'to="{seg:.2f} {circumference - seg:.2f}" dur="0.6s" begin="{at:.2f}s" '
            f'fill="freeze" calcMode="spline" keyTimes="0;1" keySplines="0.3 0 0.2 1"/>'
            f'</circle>')
        legend.append((lang, frac, col))
        offset += seg
        at += 0.18
    return "".join(parts), legend


def card(p, x, y, idx, t):
    b = 0.25 + idx * 0.15
    e = []
    a = e.append
    repo = (p.get("repo", "").strip()
            .replace("https://github.com/", "").replace("http://github.com/", "")
            .rstrip("/"))
    a(f'<a href="https://github.com/{esc(repo)}" target="_blank">')
    a(f'<g opacity="0" transform="translate({x},{y})">')
    a(f'<animate attributeName="opacity" from="0" to="1" dur="0.5s" '
      f'begin="{b:.2f}s" fill="freeze"/>')

    a(f'<rect width="{CARD_W}" height="{CARD_H}" rx="12" fill="{t["CARD"]}" '
      f'stroke="{t["STROKE"]}"><animate attributeName="stroke" '
      f'values="{t["STROKE_LO"]};{t["STROKE_HI"]};{t["STROKE_LO"]}" dur="4.5s" '
      f'begin="{b + idx * 0.7:.2f}s" repeatCount="indefinite"/></rect>')
    a(f'<rect width="{CARD_W}" height="30" rx="12" fill="{t["CARD_BAR"]}"/>')
    a(f'<rect y="18" width="{CARD_W}" height="12" fill="{t["CARD_BAR"]}"/>')
    a(f'<line x1="0" y1="30" x2="{CARD_W}" y2="30" stroke="{t["BARLINE"]}"/>')
    a(f'<text x="16" y="19" font-size="10" fill="{t["MUTED"]}">'
      f'<tspan fill="{t["CYAN"]}">&#8226;</tspan> {esc(repo)}</text>')

    days = 9999
    try:
        pushed = datetime.fromisoformat(p.get("pushed_at", "").replace("Z", "+00:00"))
        days = (datetime.now(timezone.utc) - pushed).days
    except Exception:
        pass
    if days <= 30:
        a(f'<circle cx="{CARD_W - 16}" cy="15" r="3.5" fill="{t["EMERALD"]}">'
          f'<animate attributeName="opacity" values="1;0.25;1" dur="1.8s" '
          f'repeatCount="indefinite"/></circle>')
    else:
        a(f'<circle cx="{CARD_W - 16}" cy="15" r="3.5" fill="{t["DIM"]}"/>')

    float_anim = (f'<animateTransform attributeName="transform" type="translate" '
                  f'values="0 0; 0 -2.5; 0 0" dur="5s" begin="{b + idx * 0.5:.2f}s" '
                  f'repeatCount="indefinite" calcMode="spline" keyTimes="0;0.5;1" '
                  f'keySplines="0.4 0 0.6 1;0.4 0 0.6 1"/>')
    logo = p.get("_logo")
    if logo:
        a(f'<g>{float_anim}<image x="16" y="44" width="40" height="40" href="{logo}" '
          f'preserveAspectRatio="xMidYMid meet"/></g>')
    else:
        a(f'<g>{float_anim}<rect x="16" y="44" width="40" height="40" rx="9" '
          f'fill="{t["VIOLET2"]}" opacity="0.9"/>'
          f'<text x="36" y="71" text-anchor="middle" font-size="20" font-weight="700" '
          f'fill="{t["MONO_TX"]}">{esc((p.get("name") or "?")[0].upper())}</text></g>')

    a(f'<text x="68" y="61" font-size="17" font-weight="700" fill="{t["TEXT"]}">'
      f'{esc(p.get("name", "unnamed"))}<tspan fill="{t["CYAN"]}">_'
      f'<animate attributeName="opacity" values="1;0;1" dur="1.2s" '
      f'begin="{b + 0.4:.2f}s" repeatCount="indefinite"/></tspan></text>')

    for i, line in enumerate(wrap(p.get("description", ""), 52)):
        a(f'<text x="68" y="{80 + i * 16}" font-size="11" fill="{t["MUTED"]}">{esc(line)}</text>')

    tx = 68
    for tag in (p.get("tags") or [])[:3]:
        tw = len(tag) * 6.6 + 14
        a(f'<rect x="{tx}" y="118" width="{tw:.0f}" height="17" rx="8.5" '
          f'fill="{t["PILL"]}" stroke="{t["PILL_STROKE"]}"/>')
        a(f'<text x="{tx + tw / 2:.0f}" y="130" text-anchor="middle" font-size="9.5" '
          f'fill="{t["VIOLET"]}">{esc(tag)}</text>')
        tx += tw + 7

    a(f'<text x="68" y="155" font-size="11" fill="{t["MUTED"]}">'
      f'<tspan fill="{t["CYAN"]}">&#9733;</tspan> {p.get("stars", 0)}'
      f'<tspan fill="{t["DIM"]}" dx="14">updated {rel_time(p.get("pushed_at"))}</tspan></text>')

    langs = p.get("languages") or {}
    if langs:
        cx, cy, r = CARD_W - 58, CARD_H // 2 + 6, 27
        segs, legend = donut(langs, cx, cy, r, b + 0.3, t)
        a(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{t["RING"]}" '
          f'stroke-width="9"/>')
        a(segs)
        a(f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" font-size="11" '
          f'font-weight="700" fill="{t["TEXT"]}">{legend[0][1] * 100:.0f}%</text>')
        dot_x, ly = cx - r - 92, cy - 22
        for lang, frac, col in legend[:3]:
            a(f'<circle cx="{dot_x}" cy="{ly}" r="3.5" fill="{col}"/>')
            a(f'<text x="{dot_x + 9}" y="{ly + 4}" font-size="10" fill="{t["MUTED"]}">'
              f'{esc(lang)} {frac * 100:.0f}%</text>')
            ly += 18

    a('</g></a>')
    return "".join(e)


def build(projects, theme):
    t = THEMES[theme]
    rows = math.ceil(len(projects) / 2)
    H = 56 + rows * (CARD_H + GAP) + MARGIN
    gid = f"acc_{theme}"
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family="{FONT}" role="img" aria-label="Projects">',
         f'<rect width="{W}" height="{H}" fill="{t["BG"]}"/>',
         f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="0">'
         f'<stop offset="0" stop-color="{t["VIOLET2"]}"><animate attributeName="stop-color" '
         f'values="{t["VIOLET2"]};{t["CYAN"]};{t["EMERALD"]};{t["VIOLET2"]}" dur="10s" '
         f'repeatCount="indefinite"/></stop>'
         f'<stop offset="1" stop-color="{t["EMERALD"]}"><animate attributeName="stop-color" '
         f'values="{t["EMERALD"]};{t["VIOLET2"]};{t["CYAN"]};{t["EMERALD"]}" dur="10s" '
         f'repeatCount="indefinite"/></stop></linearGradient></defs>',
         f'<text x="{MARGIN + 2}" y="18" font-size="11" letter-spacing="2" '
         f'fill="{t["CYAN"]}">PROJECTS.LIST</text>',
         f'<text x="{MARGIN + 130}" y="18" font-size="10" fill="{t["DIM"]}">'
         f'./projects.sh --all</text>',
         f'<line x1="{MARGIN}" y1="28" x2="{W - MARGIN}" y2="28" stroke="url(#{gid})" '
         f'stroke-width="1.5" opacity="0.7"/>']
    for i, p in enumerate(projects):
        s.append(card(p, MARGIN + (i % 2) * (CARD_W + GAP + 4),
                      42 + (i // 2) * (CARD_H + GAP), i, t))
    s.append('</svg>')
    return "".join(s)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "merged.json"
    outdir = sys.argv[2] if len(sys.argv) > 2 else "."
    with open(src, encoding="utf-8") as f:
        projects = json.load(f)
    for p in projects:
        p["_logo"] = logo_b64(p.get("logo"))
    for theme, name in (("dark", "projects.svg"), ("light", "projects-light.svg")):
        svg = build(projects, theme)
        path = os.path.join(outdir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"wrote {path}: {theme}, {len(projects)} projects, {len(svg) // 1024}KB")


if __name__ == "__main__":
    main()

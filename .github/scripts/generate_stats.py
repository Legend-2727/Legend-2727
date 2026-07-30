#!/usr/bin/env python3
"""
Render the profile stat cards: streak, summary and top languages.

Replaces the third-party card services the README used to embed. Everything
comes straight from the GitHub GraphQL API and is drawn in the same terminal
style as the hero banner, so nothing depends on someone else's uptime.

    GITHUB_TOKEN=... python3 .github/scripts/generate_stats.py Legend-2727 out

Writes streak.svg, stats.svg, langs.svg plus -light variants.

Private contributions are included only when the account has "include private
contributions on my profile" enabled. Set METRICS_TOKEN to a personal token
with read:user if the default Actions token comes back short.
"""
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta

API = "https://api.github.com/graphql"
TOKEN = os.environ.get("METRICS_TOKEN") or os.environ.get("GITHUB_TOKEN", "")

# Languages to leave out of the top-languages card (build noise, vendored code).
EXCLUDE_LANGS = {"CMake", "Makefile", "Roff", "Dockerfile", "Shell", "Batchfile"}
# Repos to leave out of the language totals entirely.
EXCLUDE_REPOS = set()

FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

THEMES = {
    "dark": {
        "BG": "#0A101F", "PANEL": "#0C1426", "BAR": "#0B1222",
        "CYAN": "#22D3EE", "VIOLET": "#A78BFA", "VIOLET2": "#7C3AED",
        "EMERALD": "#10B981", "TEXT": "#F8FAFC", "MUTED": "#94A3B8",
        "DIM": "#475569", "HAIR": "rgba(255,255,255,0.10)",
        "STROKE": "rgba(34,211,238,0.30)", "TRACK": "rgba(148,163,184,0.18)",
    },
    "light": {
        "BG": "#FFFFFF", "PANEL": "#F8FAFC", "BAR": "#F1F5F9",
        "CYAN": "#0891B2", "VIOLET": "#7C3AED", "VIOLET2": "#6D28D9",
        "EMERALD": "#059669", "TEXT": "#0F172A", "MUTED": "#475569",
        "DIM": "#94A3B8", "HAIR": "rgba(15,23,42,0.10)",
        "STROKE": "rgba(8,145,178,0.30)", "TRACK": "rgba(100,116,139,0.20)",
    },
}


# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------
def gql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(API, data=body, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "profile-stats",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.load(r)
    if "errors" in out:
        raise RuntimeError(out["errors"])
    return out["data"]


PROFILE_Q = """
query($login:String!) {
  user(login:$login) {
    createdAt
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    contributionsCollection { contributionYears }
    repositories(ownerAffiliations:OWNER, isFork:false, first:100,
                 orderBy:{field:STARGAZERS, direction:DESC}) {
      totalCount
      nodes {
        name
        stargazerCount
        languages(first:12, orderBy:{field:SIZE, direction:DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}"""

YEAR_Q = """
query($login:String!, $from:DateTime!, $to:DateTime!) {
  user(login:$login) {
    contributionsCollection(from:$from, to:$to) {
      totalCommitContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}"""


def collect(login):
    user = gql(PROFILE_Q, {"login": login})["user"]
    repos = user["repositories"]["nodes"]

    langs, colours = {}, {}
    for repo in repos:
        if repo["name"] in EXCLUDE_REPOS:
            continue
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            if name in EXCLUDE_LANGS:
                continue
            langs[name] = langs.get(name, 0) + edge["size"]
            colours[name] = edge["node"]["color"] or "#64748B"

    days, commits, contributions = {}, 0, 0
    for year in user["contributionsCollection"]["contributionYears"]:
        c = gql(YEAR_Q, {"login": login,
                         "from": f"{year}-01-01T00:00:00Z",
                         "to": f"{year}-12-31T23:59:59Z"})["user"]["contributionsCollection"]
        commits += c["totalCommitContributions"]
        contributions += c["contributionCalendar"]["totalContributions"]
        for week in c["contributionCalendar"]["weeks"]:
            for d in week["contributionDays"]:
                days[d["date"]] = d["contributionCount"]

    return {
        "login": login,
        "since": user["createdAt"][:10],
        "followers": user["followers"]["totalCount"],
        "prs": user["pullRequests"]["totalCount"],
        "issues": user["issues"]["totalCount"],
        "repos": user["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "commits": commits,
        "contributions": contributions,
        "langs": langs,
        "colours": colours,
        "days": days,
    }


def streaks(days):
    """Current and longest run of consecutive contributing days.

    Anchored to the last day that actually has activity rather than to the
    runner's clock: the calendar is in the profile's timezone while Actions
    runs in UTC, so a naive "today" drops the newest day and reports a streak
    one short. A day of slack in either direction absorbs that offset, and a
    gap wider than that means the streak really has ended.
    """
    active = sorted(d for d, c in days.items() if c > 0)
    if not active:
        return (0, None, None), (0, None, None)
    dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in active]

    best = run = 1
    best_start = run_start = best_end = dates[0]
    for prev, day in zip(dates, dates[1:]):
        if (day - prev).days == 1:
            run += 1
        else:
            run, run_start = 1, day
        if run > best:
            best, best_start, best_end = run, run_start, day

    i = len(dates) - 1
    cur = 1
    while i > 0 and (dates[i] - dates[i - 1]).days == 1:
        cur += 1
        i -= 1
    stale = (date.today() - dates[-1]).days > 1
    current = (0, None, None) if stale else (cur, dates[i], dates[-1])
    return current, (best, best_start, best_end)


# --------------------------------------------------------------------------
# drawing helpers
# --------------------------------------------------------------------------
def fmt(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n / 1000:.1f}k"
    return f"{n:,}"


def span(a, b):
    if not a or not b:
        return "-"
    fa = a.strftime("%b %d, %Y")
    fb = "Present" if b >= date.today() - timedelta(days=1) else b.strftime("%b %d, %Y")
    return f"{fa} - {fb}"


def accent_defs(t, gid):
    return (f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="0">'
            f'<stop offset="0" stop-color="{t["VIOLET2"]}"><animate attributeName="stop-color" '
            f'values="{t["VIOLET2"]};{t["CYAN"]};{t["EMERALD"]};{t["VIOLET2"]}" dur="10s" '
            f'repeatCount="indefinite"/></stop>'
            f'<stop offset="1" stop-color="{t["EMERALD"]}"><animate attributeName="stop-color" '
            f'values="{t["EMERALD"]};{t["VIOLET2"]};{t["CYAN"]};{t["EMERALD"]}" dur="10s" '
            f'repeatCount="indefinite"/></stop></linearGradient></defs>')


def fade(begin, dur=0.5):
    return (f'<animate attributeName="opacity" from="0" to="1" dur="{dur}s" '
            f'begin="{begin:.2f}s" fill="freeze"/>')


def header(t, gid, w, label, cmd):
    return (f'<text x="14" y="24" font-size="11" letter-spacing="2" fill="{t["CYAN"]}">'
            f'{label}</text>'
            f'<text x="{14 + len(label) * 8 + 18}" y="24" font-size="10" fill="{t["DIM"]}">'
            f'{cmd}</text>'
            f'<line x1="14" y1="34" x2="{w - 14}" y2="34" stroke="url(#{gid})" '
            f'stroke-width="1.5" opacity="0.7"/>')


# --------------------------------------------------------------------------
# cards
# --------------------------------------------------------------------------
def streak_card(d, theme):
    t = THEMES[theme]
    W, H = 1180, 200
    (cur, cur_a, cur_b), (best, best_a, best_b) = streaks(d["days"])
    gid = f"sa_{theme}"
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family="{FONT}" role="img" '
         f'aria-label="Contribution streak">',
         accent_defs(t, gid),
         f'<rect width="{W}" height="{H}" rx="12" fill="{t["BG"]}" stroke="{t["STROKE"]}"/>',
         header(t, gid, W, "STREAK.LOG", "./streak.sh --all-time")]

    since = datetime.strptime(d["since"], "%Y-%m-%d").date()
    cols = [
        (fmt(d["contributions"]), "Total Contributions", span(since, date.today()), t["CYAN"]),
        (fmt(cur), "Current Streak", span(cur_a, cur_b), t["EMERALD"]),
        (fmt(best), "Longest Streak", span(best_a, best_b), t["VIOLET"]),
    ]
    cw = (W - 28) / 3
    for i, (big, label, sub, col) in enumerate(cols):
        cx = 14 + cw * i + cw / 2
        if i:
            s.append(f'<line x1="{14 + cw * i:.0f}" y1="56" x2="{14 + cw * i:.0f}" y2="{H - 22}" '
                     f'stroke="{t["HAIR"]}"/>')
        s.append(f'<g opacity="0">{fade(0.25 + i * 0.18)}')
        if i == 1:
            # ring sits clear of the shared label baseline at H-42
            ry, r = 98, 36
            circ = 2 * 3.14159265 * r
            s.append(f'<circle cx="{cx:.0f}" cy="{ry}" r="{r}" fill="none" '
                     f'stroke="{t["TRACK"]}" stroke-width="6"/>')
            s.append(f'<circle cx="{cx:.0f}" cy="{ry}" r="{r}" fill="none" stroke="{col}" '
                     f'stroke-width="6" stroke-linecap="round" '
                     f'transform="rotate(-90 {cx:.0f} {ry})" '
                     f'stroke-dasharray="{circ:.1f}" stroke-dashoffset="{circ:.1f}">'
                     f'<animate attributeName="stroke-dashoffset" from="{circ:.1f}" to="0" '
                     f'dur="1.1s" begin="0.5s" fill="freeze" calcMode="spline" '
                     f'keyTimes="0;1" keySplines="0.3 0 0.2 1"/></circle>')
            s.append(f'<text x="{cx:.0f}" y="{ry + 11}" text-anchor="middle" font-size="30" '
                     f'font-weight="700" fill="{t["TEXT"]}">{big}</text>')
            s.append(f'<text x="{cx:.0f}" y="{H - 42}" text-anchor="middle" font-size="13" '
                     f'letter-spacing="1" fill="{col}">{label}</text>')
        else:
            s.append(f'<text x="{cx:.0f}" y="118" text-anchor="middle" font-size="44" '
                     f'font-weight="700" fill="{t["TEXT"]}">{big}</text>')
            s.append(f'<text x="{cx:.0f}" y="{H - 42}" text-anchor="middle" font-size="13" '
                     f'letter-spacing="1" fill="{col}">{label}</text>')
        s.append(f'<text x="{cx:.0f}" y="{H - 22}" text-anchor="middle" font-size="10" '
                 f'fill="{t["DIM"]}">{sub}</text>')
        s.append('</g>')
    s.append('</svg>')
    return "".join(s)


def stats_card(d, theme):
    t = THEMES[theme]
    W, H = 583, 232
    gid = f"sb_{theme}"
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family="{FONT}" role="img" '
         f'aria-label="GitHub statistics">',
         accent_defs(t, gid),
         f'<rect width="{W}" height="{H}" rx="12" fill="{t["BG"]}" stroke="{t["STROKE"]}"/>',
         header(t, gid, W, "STATS", f"@{d['login']}")]

    rows = [
        ("Total Stars Earned", fmt(d["stars"]), "&#9733;"),
        ("Total Commits", fmt(d["commits"]), "&#9679;"),
        ("Total PRs", fmt(d["prs"]), "&#8644;"),
        ("Total Issues", fmt(d["issues"]), "&#9888;"),
        ("Public Repositories", fmt(d["repos"]), "&#9635;"),
        ("Followers", fmt(d["followers"]), "&#9787;"),
    ]
    width_chars = 46
    y = 62
    for i, (label, value, icon) in enumerate(rows):
        dots = max(width_chars - len(label) - len(value) - 2, 1)
        s.append(f'<text x="14" y="{y}" font-size="13" textLength="{W - 28}" '
                 f'lengthAdjust="spacingAndGlyphs" xml:space="preserve" opacity="0">'
                 f'{fade(0.3 + i * 0.1, 0.35)}'
                 f'<tspan fill="{t["CYAN"]}">{icon} </tspan>'
                 f'<tspan fill="{t["MUTED"]}">{label}</tspan>'
                 f'<tspan fill="{t["DIM"]}"> {"." * dots} </tspan>'
                 f'<tspan fill="{t["TEXT"]}" font-weight="700">{value}</tspan></text>')
        y += 28
    s.append('</svg>')
    return "".join(s)


def langs_card(d, theme):
    t = THEMES[theme]
    W, H = 583, 232
    gid = f"sc_{theme}"
    top = sorted(d["langs"].items(), key=lambda kv: -kv[1])[:8]
    total = sum(v for _, v in top) or 1

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family="{FONT}" role="img" '
         f'aria-label="Most used languages">',
         accent_defs(t, gid),
         f'<rect width="{W}" height="{H}" rx="12" fill="{t["BG"]}" stroke="{t["STROKE"]}"/>',
         header(t, gid, W, "TOP.LANGUAGES", "by bytes")]

    bar_x, bar_y, bar_w, bar_h = 14, 54, W - 28, 12
    s.append(f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="6" '
             f'fill="{t["TRACK"]}"/>')
    s.append(f'<clipPath id="bc_{theme}"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" '
             f'height="{bar_h}" rx="6"/></clipPath>')
    s.append(f'<g clip-path="url(#bc_{theme})">')
    off = 0.0
    for i, (name, size) in enumerate(top):
        seg = bar_w * size / total
        s.append(f'<rect x="{bar_x + off:.1f}" y="{bar_y}" width="{seg:.1f}" '
                 f'height="{bar_h}" fill="{d["colours"].get(name, "#64748B")}" opacity="0">'
                 f'{fade(0.3 + i * 0.08, 0.4)}</rect>')
        off += seg
    s.append('</g>')

    for i, (name, size) in enumerate(top):
        col_x = 14 + (i % 2) * (bar_w / 2)
        row_y = 100 + (i // 2) * 30
        pct = size / total * 100
        s.append(f'<g opacity="0">{fade(0.5 + i * 0.07, 0.4)}'
                 f'<circle cx="{col_x + 6:.0f}" cy="{row_y - 4}" r="5" '
                 f'fill="{d["colours"].get(name, "#64748B")}"/>'
                 f'<text x="{col_x + 20:.0f}" y="{row_y}" font-size="12.5" '
                 f'fill="{t["TEXT"]}">{name}</text>'
                 f'<text x="{col_x + bar_w / 2 - 14:.0f}" y="{row_y}" text-anchor="end" '
                 f'font-size="12.5" font-weight="700" fill="{t["MUTED"]}">{pct:.1f}%</text>'
                 f'</g>')
    s.append('</svg>')
    return "".join(s)


def main():
    login = sys.argv[1] if len(sys.argv) > 1 else "Legend-2727"
    outdir = sys.argv[2] if len(sys.argv) > 2 else "."
    if not TOKEN:
        raise SystemExit("set GITHUB_TOKEN (or METRICS_TOKEN)")
    os.makedirs(outdir, exist_ok=True)
    d = collect(login)
    for theme, suffix in (("dark", ""), ("light", "-light")):
        for name, fn in (("streak", streak_card), ("stats", stats_card), ("langs", langs_card)):
            path = os.path.join(outdir, f"{name}{suffix}.svg")
            with open(path, "w", encoding="utf-8") as f:
                f.write(fn(d, theme))
            print(f"wrote {path}")
    print(f"{d['contributions']} contributions, {d['commits']} commits, "
          f"{d['stars']} stars, {len(d['langs'])} languages")


if __name__ == "__main__":
    main()

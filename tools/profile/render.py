"""Render data/profile.json into themed, responsive SVG panels and README.md.

Every panel is rendered four times: {desktop, phone} x {dark, light}. The README wraps each
panel in a <picture> element so GitHub serves the variant matching the reader's theme and
screen width.
"""

import base64
import datetime as dt
import hashlib
import json
import math
import os
from html import escape

OUT = "assets/profile"

DARK = {
    "name": "dark", "bg": "#130e1f", "line": "#2b2040", "dim": "#7c6a9c", "txt": "#ddd2f0",
    "p": "#a855f7", "p2": "#c084fc", "p3": "#e9d5ff", "mag": "#f0abfc", "ok": "#86efac", "cmd": "#f3e8ff",
    "bar": ("#3a3a3f", "#2c2c30"), "barline": "#18181b", "border": "#48484e", "title": "#a1a1a6",
    "hl": ".08", "track": "#1c1530", "axis": "#4c3a6e", "band": "#1d1030", "scan": ".02",
    "indigo": "#818cf8", "muted": "#6d5a92", "jwt": ("#f472b6", "#c084fc", "#67e8f9"), "glow": ".55",
}
LIGHT = {
    "name": "light", "bg": "#fcfbff", "line": "#e6dff2", "dim": "#76689a", "txt": "#2a2140",
    "p": "#7c3aed", "p2": "#9333ea", "p3": "#3b0764", "mag": "#c026d3", "ok": "#15803d", "cmd": "#1e1530",
    "bar": ("#ececee", "#dadadd"), "barline": "#c4c4c8", "border": "#c8c8cc", "title": "#4d4d52",
    "hl": ".7", "track": "#ede7f8", "axis": "#cfc2e8", "band": "#f4edfd", "scan": "0",
    "indigo": "#6366f1", "muted": "#a594c8", "jwt": ("#db2777", "#9333ea", "#0e7490"), "glow": ".18",
}

# Variant state, set by variant() before each render pass.
T = DARK
PHONE = False
W = 880
FS = 13.0          # base font size
CW = FS * 0.6      # monospace advance


def variant(theme, phone):
    global T, PHONE, W, FS, CW
    T, PHONE = theme, phone
    W = 440 if phone else 880
    FS = 12.0 if phone else 13.0
    CW = FS * 0.6


def css():
    t = T
    return (
        f"text{{font-family:ui-monospace,'SF Mono',SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace;font-size:{FS:g}px;fill:{t['txt']};white-space:pre}}"
        f".dim{{fill:{t['dim']}}}.p{{fill:{t['p']}}}.p2{{fill:{t['p2']}}}.p3{{fill:{t['p3']}}}.mag{{fill:{t['mag']}}}.ok{{fill:{t['ok']}}}.cmd{{fill:{t['cmd']}}}"
        f".big{{font-size:{24 if PHONE else 30}px;font-weight:700;fill:{t['p3']}}}.lbl{{font-size:{9.5 if PHONE else 10.5}px;letter-spacing:1.3px;fill:{t['dim']}}}"
        f".sm{{font-size:{10.5 if PHONE else 11}px}}.b{{font-weight:700}}"
        f".title{{font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text','Segoe UI',Helvetica,Arial,sans-serif;font-size:12.5px;font-weight:600;fill:{t['title']}}}"
        ".cursor{animation:blink 1.06s step-end infinite}@keyframes blink{50%{opacity:0}}"
        ".pulse{animation:pulse 1.4s ease-in-out infinite}@keyframes pulse{50%{opacity:.15}}"
        "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
    )


def e(s):
    return escape(str(s), quote=True)


def k(n):
    if n >= 1e6:
        return f"{n / 1e6:.1f}M"
    if n >= 1e3:
        return f"{n / 1e3:.1f}".rstrip("0").rstrip(".") + "k"
    return str(n)


def c(n):
    return f"{n:,}"


def parse(ts):
    return dt.datetime.strptime(ts[:10], "%Y-%m-%d").date()


def wrap(text, width, sep=" "):
    lines, cur = [], ""
    for word in text.split(sep):
        word = word.strip()
        if cur and len(cur) + len(sep) + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur}{sep}{word}" if cur else word
    return lines + ([cur] if cur else [])


def maxchars(px, fs=None):
    return int(px / ((fs or FS) * 0.6))


def svg(w, h, body, label, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h:.0f}" viewBox="0 0 {w} {h:.0f}" '
            f'role="img" aria-label="{e(label)}"><title>{e(label)}</title>'
            f'<style>{css()}</style><defs>{defs}</defs>{body}</svg>\n')


def window(name, inner_h, body, label, defs="", scan=False, gap=10):
    t = T
    h = 30 + inner_h
    d = (f'<clipPath id="win"><rect x="1" y="1" width="{W - 2}" height="{h - 2:.0f}" rx="11"/></clipPath>'
         f'<linearGradient id="bar" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="{t["bar"][0]}"/><stop offset="1" stop-color="{t["bar"][1]}"/></linearGradient>'
         f'<pattern id="scan" width="4" height="3" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#fff" fill-opacity="{t["scan"]}"/></pattern>')
    g = f'<g clip-path="url(#win)"><rect width="{W}" height="{h:.0f}" fill="{t["bg"]}"/>'
    g += f'<g transform="translate(0,30)">{body}</g>'
    if scan and t["scan"] != "0":
        g += f'<rect y="30" width="{W}" height="{inner_h:.0f}" fill="url(#scan)"/>'
    g += f'<rect width="{W}" height="30" fill="url(#bar)"/><line x1="0" x2="{W}" y1="30" y2="30" stroke="{t["barline"]}"/>'
    g += f'<line x1="12" x2="{W - 12}" y1="1.5" y2="1.5" stroke="#fff" stroke-opacity="{t["hl"]}"/></g>'
    for i, col in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        g += f'<circle cx="{20 + i * 20}" cy="15" r="6" fill="{col}" stroke="#000" stroke-opacity=".2" stroke-width=".5"/>'
    title = f"james - {name}" if PHONE else f"james - {name} - 120×32"
    g += f'<text x="{W / 2 + (18 if PHONE else 0)}" y="19.5" text-anchor="middle" class="title">{e(title)}</text>'
    g += f'<rect x=".5" y=".5" width="{W - 1}" height="{h - 1:.0f}" rx="11.5" fill="none" stroke="{t["border"]}"/>'
    return svg(W, h + gap, g, label, d + defs)


def tile(w, h, body, label, gap=10, x=0, tw=None):
    tw = tw or w
    g = f'<rect x="{x + .5}" y=".5" width="{tw - 1}" height="{h - 1}" rx="10" fill="{T["bg"]}" stroke="{T["line"]}"/>{body}'
    return svg(w, h + gap, g, label)


def prompt(cfg, x, y, cmd, comment=""):
    user = cfg["login"].split("-")[0]
    if PHONE:
        s = f'<text x="{x}" y="{y}"><tspan class="p2">~</tspan><tspan class="p">$</tspan> <tspan class="cmd">{e(cmd)}</tspan>'
    else:
        s = f'<text x="{x}" y="{y}"><tspan class="p">{e(user)}@{e(cfg["host"])}</tspan>:<tspan class="p2">~</tspan>$ <tspan class="cmd">{e(cmd)}</tspan>'
        if comment:
            s += f'   <tspan class="dim"># {e(comment)}</tspan>'
    return s + "</text>"


def prompt_width(cfg, cmd):
    if PHONE:
        return (3 + len(cmd)) * CW
    return (len(cfg["login"].split("-")[0]) + len(cfg["host"]) + 5 + len(cmd)) * CW


def stat_grid(cells, y0, x0=24):
    cols = 2 if PHONE else 4
    colw = (W - 2 * x0) / cols
    rowh = 84 if PHONE else 92
    g = ""
    for i, (lbl, big, sub) in enumerate(cells):
        x = x0 + (i % cols) * colw
        y = y0 + (i // cols) * rowh
        g += f'<text x="{x:.0f}" y="{y}" class="lbl">{e(lbl.upper())}</text>'
        g += f'<text x="{x:.0f}" y="{y + (30 if PHONE else 34)}" class="big">{e(big)}</text>'
        if sub:
            g += f'<text x="{x:.0f}" y="{y + (48 if PHONE else 54)}" class="dim sm">{e(sub)}</text>'
    return g, math.ceil(len(cells) / cols) * rowh


# ---------------------------------------------------------------- header

BOX = {  # unit-cell segments for the double-line box drawing glyphs used by the name banner
    "═": [(0, .38, 1, .38), (0, .62, 1, .62)],
    "║": [(.38, 0, .38, 1), (.62, 0, .62, 1)],
    "╗": [(0, .38, .62, .38), (.62, .38, .62, 1), (0, .62, .38, .62), (.38, .62, .38, 1)],
    "╔": [(.38, .38, 1, .38), (.38, .38, .38, 1), (.62, .62, 1, .62), (.62, .62, .62, 1)],
    "╝": [(0, .62, .62, .62), (.62, 0, .62, .62), (0, .38, .38, .38), (.38, 0, .38, .38)],
    "╚": [(.38, .62, 1, .62), (.38, 0, .38, .62), (.62, .38, 1, .38), (.62, 0, .62, .38)],
}


def name_art(lines, x0, y0, width):
    cw = min(8.0, width / max(len(l) for l in lines))
    ch = cw * 1.65
    blocks, strokes = [], []
    for r, line in enumerate(lines):
        for i, glyph in enumerate(line):
            x, y = x0 + i * cw, y0 + r * ch
            if glyph == "█":
                blocks.append(f"M{x:.1f} {y:.1f}h{cw + .3:.1f}v{ch + .3:.1f}h{-cw - .3:.1f}Z")
            for (a, b, c_, d) in BOX.get(glyph, []):
                strokes.append(f"M{x + a * cw:.1f} {y + b * ch:.1f}L{x + c_ * cw:.1f} {y + d * ch:.1f}")
    db, ds = "".join(blocks), "".join(strokes)
    g = f'<path d="{db}" fill="{T["p"]}" opacity="{T["glow"]}" filter="url(#glow)"/>'
    g += f'<path d="{ds}" stroke="{T["p"]}" stroke-width="{.7 if PHONE else 1}" fill="none" opacity=".9"/>'
    g += f'<path d="{db}" fill="{T["p2"]}"/>'
    return g, len(lines) * ch


def kv(label, value, width, sep=" · "):
    """label/value rows; value wraps on sep with a hanging indent."""
    pad = len(label)
    parts = wrap(value, width - pad, sep) if len(label) + len(value) > width else [value]
    rows = []
    for i, part in enumerate(parts):
        lead = f'<tspan class="dim">{e(label)}</tspan>' if i == 0 else " " * pad
        rows.append(lead + e(part))
    return rows


def header(cfg):
    who = cfg["whoami"]
    g = prompt(cfg, 24, 30, "whoami --verbose")
    art, art_h = name_art(cfg["name_art"], 24, 46, W - 48)
    g += art
    y = 46 + art_h + (24 if PHONE else 30)
    width = maxchars(W - 48)
    rows = []
    if PHONE:
        rows += kv("uid=", cfg["login"], width)
        rows += kv("gid=", ",".join(who["gid"]), width, ",")
    else:
        rows.append(f'<tspan class="dim">uid=</tspan>{e(cfg["login"])} <tspan class="dim">gid=</tspan>{e(",".join(who["gid"]))}')
    rows += kv("groups=", ",".join(who["groups"]), width, ",")
    rows += kv("role:   ", who["role"], width)
    rows += kv("speaks: ", who["speaks"], width)
    status = f'<tspan class="dim">status: </tspan><tspan class="ok">● online</tspan> - {e(who["status"])}'
    if PHONE:
        rows.append(f'<tspan class="dim">tz:     </tspan>{e(who["tz"])}')
        rows.append(status)
    else:
        rows.append(f'<tspan class="dim">tz:     </tspan>{e(who["tz"]).ljust(28)}{status}')
    lh = 19 if PHONE else 21
    for row in rows:
        g += f'<text x="24" y="{y:.0f}">{row}</text>'
        y += lh
    y += 16
    g += prompt(cfg, 24, y, "")
    g += f'<rect class="cursor" x="{24 + prompt_width(cfg, "") + 2:.0f}" y="{y - FS + 1:.0f}" width="{CW:.1f}" height="{FS + 2:.0f}" fill="{T["p"]}"/>'
    defs = '<filter id="glow" x="-5%" y="-20%" width="110%" height="140%"><feGaussianBlur stdDeviation="3"/></filter>'
    label = f'{cfg["login"]}: {who["role"]}. Speaks {who["speaks"]}.'
    return window(f'{cfg["login"].split("-")[0]}@{cfg["host"]}: ~ - zsh', y + 20, g, label, defs, scan=True)


# ---------------------------------------------------------------- links

def link(l, n):
    w = round(W / n)
    g = f'<text x="{w / 2}" y="{28 if PHONE else 26}" text-anchor="middle" class="p2">[ <tspan class="p3 b">{e(l["label"])}</tspan> ]</text>'
    if not PHONE:
        g += f'<text x="{w / 2}" y="44" text-anchor="middle" class="dim sm">{e(l["sub"])}</text>'
    return tile(w, 46 if PHONE else 58, g, f'{l["label"]}: {l["sub"]}', x=3, tw=w - 6)


# ---------------------------------------------------------------- telemetry

def telemetry(cfg, d):
    u, yrs = d["user"], d["user"]["years"]
    yr = d["fetched_at"][:4]
    this = yrs.get(yr, {})
    total = lambda key: sum(v[key] for v in yrs.values())
    stars = sum(r["stars"] for r in d["repos"].values())
    cells = [
        ("stars · key projects", k(stars), f'{len(d["repos"])} repos'),
        ("contributions", c(total("total")), f'{c(this.get("total", 0))} in {yr}'),
        ("pull requests", c(u["pull_requests"]), f'{c(u["merged"])} merged'),
        ("pr reviews", c(total("totalPullRequestReviewContributions")), f'{c(this.get("totalPullRequestReviewContributions", 0))} in {yr}'),
        ("issue comments", c(u["issue_comments"]), f'{c(u["issues"])} issues opened'),
        ("discussion replies", c(u["discussion_comments"]), f'{c(u["discussions"])} started'),
        ("commits", c(total("totalCommitContributions")), "public repos"),
        ("followers", c(u["followers"]), f'member since {u["created_at"][:4]}'),
    ]
    g = prompt(cfg, 24, 30, "telemetry --all-time", f'refreshed {d["fetched_at"][:10]}')
    grid, gh = stat_grid(cells, 66)
    label = "All-time telemetry: " + ", ".join(f"{a} {b}" for a, b, _ in cells)
    return window("telemetry", 66 + gh - 10, g + grid, label)


# ---------------------------------------------------------------- city

class Rand:
    def __init__(self, seed):
        self.s = seed

    def __call__(self):
        self.s = (self.s * 16807) % 2147483647
        return self.s / 2147483647


def city(cfg, d):
    """Isometric skyline, one tower per day. Night in dark mode, day in light mode."""
    night = T["name"] == "dark"
    u, days = d["user"], d["user"]["calendar"]
    C = [n for _, n in days]
    mx = max(C) or 1
    busiest = C.index(mx)
    bdate = parse(days[busiest][0])
    rnd = Rand(7)
    if PHONE:
        geo = dict(ox=16, step=7, bw=5.5, rx=3.5, ry=3, dx=2.5, dy=2.5, hmax=92, overlay=196)
    else:
        geo = dict(ox=44, step=14, bw=11, rx=7, ry=6, dx=5, dy=5, hmax=150, overlay=0)
    ox, step, bw, rx, ry, dx, dy, hmax = (geo[x] for x in ("ox", "step", "bw", "rx", "ry", "dx", "dy", "hmax"))
    top = 46
    sky_h = geo["overlay"] + (hmax + 70 if PHONE else 380)
    b = top + sky_h - 28
    ink, ink_dim, ink_hi, ink_mag = ("#e9d5ff", "#9d8bbd", "#c084fc", "#f0abfc") if night else ("#3b0764", "#6b5b8a", "#7c3aed", "#a21caf")

    if night:
        stops = ("#07040d", "#1a0d2e", "#2d1452")
    else:
        stops = ("#fbf8ff", "#f1e8ff", "#e4d4fb")
    g = f'<rect y="{top}" width="{W}" height="{sky_h}" fill="url(#sky)"/>'
    if night:
        for _ in range(70 if not PHONE else 40):
            g += f'<circle cx="{rnd() * W:.0f}" cy="{top + rnd() * (sky_h - hmax - 60):.0f}" r="{1.2 if rnd() < .1 else .6}" fill="#e9d5ff" opacity="{.3 + rnd() * .6:.2f}"/>'
        mx_, my_ = (W - 40, top + 36) if PHONE else (470, top + 48)
        g += f'<circle cx="{mx_}" cy="{my_}" r="{14 if PHONE else 18}" fill="#e9d5ff" opacity=".9"/><circle cx="{mx_ + 6}" cy="{my_ - 5}" r="{12 if PHONE else 16}" fill="#0c0617"/>'
    else:
        sx, sy = (W - 40, top + 36) if PHONE else (470, top + 52)
        g += f'<circle cx="{sx}" cy="{sy}" r="{26 if PHONE else 34}" fill="#f9a8d4" opacity=".25"/><circle cx="{sx}" cy="{sy}" r="{14 if PHONE else 18}" fill="#f9a8d4"/>'
        for cx_, cy_, s_ in ((120, 70, 1), (640, 120, .8), (300, 150, .7)) if not PHONE else ((90, 150, .7),):
            g += f'<g opacity=".7" transform="translate({cx_},{top + cy_}) scale({s_})"><ellipse cx="0" cy="0" rx="34" ry="9" fill="#fff"/><ellipse cx="14" cy="-6" rx="18" ry="9" fill="#fff"/></g>'
    g += f'<rect y="{b - 70}" width="{W}" height="80" fill="url(#haze)"/>'

    # overlay: headline + breakdown
    tot = sum(C)
    active = sum(1 for n in C if n)
    st = best = 0
    for n in C:
        st = st + 1 if n else 0
        best = max(best, st)
    cur = 0
    for n in reversed(C):
        if not n:
            break
        cur += 1
    L = u["last12"]
    small = 11 if PHONE else 12
    g += f'<text x="{16 if PHONE else 24}" y="{top + 34}" style="font-size:{19 if PHONE else 22}px;font-weight:700;fill:{ink}">{c(tot)}<tspan style="font-size:{12 if PHONE else 13}px;font-weight:400;fill:{ink_hi}"> contributions · last 365 days</tspan></text>'
    g += f'<text x="{16 if PHONE else 24}" y="{top + 56}" style="font-size:{small}px;fill:{ink_dim}">busiest <tspan style="fill:{ink_mag}">{bdate:%b} {bdate.day}</tspan> · {mx}  ·  <tspan style="fill:{ink}">{active}</tspan> active days</text>'
    g += f'<text x="{16 if PHONE else 24}" y="{top + 74}" style="font-size:{small}px;fill:{ink_dim}">streak <tspan style="fill:{ink}">{cur}d</tspan> now · <tspan style="fill:{ink}">{best}d</tspan> longest</text>'
    rows = [("reviews", L["totalPullRequestReviewContributions"], "#f0abfc" if night else "#c026d3"),
            ("commits", L["totalCommitContributions"], "#c084fc" if night else "#9333ea"),
            ("pull requests", L["totalPullRequestContributions"], "#a855f7" if night else "#7c3aed"),
            ("private", L["restrictedContributionsCount"], "#6d5a92" if night else "#a594c8"),
            ("issues", L["totalIssueContributions"], "#818cf8" if night else "#6366f1")]
    rm = max(r[1] for r in rows) or 1
    if PHONE:
        bx, by, barw = 16 + 14 * 6.3, top + 98, 150
    else:
        bx, by, barw = W - 24 - 200, top + 24, 110
    for i, (name, n, col) in enumerate(rows):
        y = by + i * 17
        bwid = max(2, n / rm * barw)
        g += f'<text x="{bx - 10:.0f}" y="{y + 8}" text-anchor="end" class="sm" style="fill:{ink_dim}">{name}</text>'
        g += f'<rect x="{bx:.0f}" y="{y}" width="{bwid:.1f}" height="9" rx="2" fill="{col}" opacity=".85"/>'
        g += f'<text x="{bx + bwid + 6:.1f}" y="{y + 8}" class="sm" style="fill:{ink}">{c(n)}</text>'
    y = by + 5 * 17
    lbl = "discussions" if PHONE else "discussions · all time"
    g += f'<text x="{bx - 10:.0f}" y="{y + 8}" text-anchor="end" class="sm" style="fill:{ink_dim}">{lbl}</text>'
    g += f'<text x="{bx:.0f}" y="{y + 8}" class="sm" style="fill:{ink}">{c(u["discussion_comments"])} replies · {u["discussions"]} started</text>'

    # ground grid + towers
    for r in range(8):
        g += f'<line x1="{ox + r * rx - 4}" y1="{b - r * ry + 4}" x2="{ox + r * rx + 53 * step}" y2="{b - r * ry + 4}" stroke="{"#3b1f63" if night else "#d6c6f2"}" stroke-width=".6"/>'
    first = parse(days[0][0])
    offset = (first.weekday() + 1) % 7  # GitHub weeks start on Sunday
    cells = []
    for i, n in enumerate(C):
        kk = i + offset
        cells.append((kk // 7, 6 - kk % 7, n, i))
    cells.sort(key=lambda t_: (-t_[1], t_[0]))
    for w, r, n, i in cells:
        x, y = ox + w * step + r * rx, b - r * ry
        h = 3 + (n / mx) ** .55 * hmax if n else 1.2
        t = min(1, math.log(n + 1) / math.log(mx + 1)) if n else 0
        if night:
            hue, sat = 276 + t * 20, 55 + t * 30
            col = lambda a, s: f"hsl({hue:.0f},{sat:.0f}%,{a + t * s:.0f}%)"
            front, side, roof = col(10, 22), col(6, 14), col(18, 45)
        else:
            hue, sat = 270 + t * 18, 40 + t * 40
            col = lambda a, s: f"hsl({hue:.0f},{sat:.0f}%,{a - t * s:.0f}%)"
            front, side, roof = col(84, 34), col(76, 34), col(92, 28)
        g += f'<path d="M{x:.1f} {y:.1f}h{bw}v{-h:.1f}h{-bw}Z" fill="{front}"/>'
        g += f'<path d="M{x + bw:.1f} {y:.1f}l{dx} {-dy}v{-h:.1f}l{-dx} {dy}Z" fill="{side}"/>'
        g += f'<path d="M{x:.1f} {y - h:.1f}h{bw}l{dx} {-dy}h{-bw}Z" fill="{roof}"/>'
        if h > 20 and not PHONE:
            wy = y - 6
            while wy > y - h + 4:
                wx = x + 2
                while wx < x + bw - 2:
                    if rnd() < .18 + t * .4:
                        if night:
                            g += f'<rect x="{wx}" y="{wy:.1f}" width="2" height="2" fill="{"#f0abfc" if t > .75 else "#c084fc"}" opacity="{.5 + rnd() * .5:.2f}"/>'
                        else:
                            g += f'<rect x="{wx}" y="{wy:.1f}" width="2" height="2" fill="#fff" opacity="{.35 + rnd() * .4:.2f}"/>'
                    wx += 4
                wy -= 6
        if i == busiest:
            ax, ay = x + bw / 2 + dx / 2, y - h
            beacon = "#f0abfc" if night else "#db2777"
            g += f'<line x1="{ax:.1f}" y1="{ay - 3:.1f}" x2="{ax:.1f}" y2="{ay - 18:.1f}" stroke="{ink_hi}"/>'
            g += f'<circle cx="{ax:.1f}" cy="{ay - 19:.1f}" r="7" fill="{beacon}" opacity=".35" filter="url(#cg)"/>'
            g += f'<circle class="pulse" cx="{ax:.1f}" cy="{ay - 19:.1f}" r="2.5" fill="{beacon}"/>'
            g += f'<text x="{ax - 9:.1f}" y="{ay - 16:.1f}" text-anchor="end" class="sm" style="fill:{ink_mag}">peak · {bdate:%b} {bdate.day} · {mx}</text>'
    last = parse(days[-1][0])
    g += f'<text x="{ox}" y="{top + sky_h - 8}" class="sm" style="fill:{ink_dim}">{first:%b %Y}</text>'
    g += f'<text x="{W - 16}" y="{top + sky_h - 8}" text-anchor="end" class="sm" style="fill:{ink_dim}">{last:%b %Y}</text>'
    g = prompt(cfg, 24, 30, "city --render --night" if night else "city --render --day", "taller = busier") + g
    defs = (f'<linearGradient id="sky" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="{stops[0]}"/><stop offset=".7" stop-color="{stops[1]}"/><stop offset="1" stop-color="{stops[2]}"/></linearGradient>'
            f'<linearGradient id="haze" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#a855f7" stop-opacity="0"/><stop offset="1" stop-color="#a855f7" stop-opacity="{.25 if night else .12}"/></linearGradient>'
            '<filter id="cg"><feGaussianBlur stdDeviation="2.5"/></filter>')
    label = (f"Contribution city: one tower per day for the last year. {c(tot)} contributions, busiest {bdate:%B} {bdate.day} with {mx}, "
             f"{active} active days, longest streak {best} days. Reviews {L['totalPullRequestReviewContributions']}, commits {L['totalCommitContributions']}, "
             f"pull requests {L['totalPullRequestContributions']}, issues {L['totalIssueContributions']}.")
    return window("city", top + sky_h, g, label, defs)


# ---------------------------------------------------------------- projects

def used_by(r):
    return r.get("dependents", {}).get("repositories", 0)


def projects_head(cfg, d):
    total = sum(used_by(r) for r in d["repos"].values())
    g = prompt(cfg, 24, 30, "ls -l --sort=stars ~/src", f"used by {c(total)} repositories")
    if PHONE:
        g += f'<text x="{W - 24}" y="30" text-anchor="end" class="dim sm">used by {k(total)}</text>'
    return tile(W, 50, g, f"Projects, sorted by stars. Used by {c(total)} repositories.")


def card(repo, r, maxstars, side):
    w = W // 2
    owner, name = repo.split("/")
    x0 = 3 if side else 0
    tw = w - 3
    pad = 12 if PHONE else 18
    fs = 11.5 if PHONE else FS
    g = f'<text x="{x0 + pad}" y="{24 if PHONE else 30}" class="p3 b" style="font-size:{fs}px">{e(name)}</text>'
    g += f'<text x="{x0 + tw - pad}" y="{24 if PHONE else 30}" text-anchor="end" class="mag" style="font-size:{fs}px">★ {k(r["stars"])}</text>'
    ub = used_by(r)
    if PHONE:
        meta = f"used by {k(ub)}" if ub else (r["language"].lower() or owner)
        g += f'<text x="{x0 + pad}" y="42" class="dim" style="font-size:10px">{e(meta)}</text>'
        bar_y, h = 54, 64
    else:
        meta = f'drwxr-xr-x {owner.ljust(11)} {(r["language"].lower() or "-")}  ⑂ {r["forks"]}'
        if ub:
            meta += f"  · used by {c(ub)}"
        g += f'<text x="{x0 + pad}" y="48" class="dim sm">{e(meta)}</text>'
        for i, line in enumerate(wrap(r["description"], 54)[:3]):
            g += f'<text x="{x0 + pad}" y="{72 + i * 16}" style="font-size:12px" opacity=".85">{e(line)}</text>'
        bar_y, h = 118, 134
    full = tw - 2 * pad
    frac = max(.04, math.log(r["stars"] + 1) / math.log(maxstars + 1))
    g += f'<defs><linearGradient id="bg" x1="0" x2="1"><stop offset="0" stop-color="{T["p"]}"/><stop offset="1" stop-color="{T["mag"]}"/></linearGradient></defs>'
    g += f'<rect x="{x0 + pad}" y="{bar_y}" width="{full}" height="3" fill="{T["line"]}"/><rect x="{x0 + pad}" y="{bar_y}" width="{full * frac:.1f}" height="3" fill="url(#bg)"/>'
    label = f'{repo}: {r["description"]} {r["stars"]} stars' + (f", used by {ub} repositories" if ub else "")
    return tile(w, h, g, label, x=x0, tw=tw, gap=8 if PHONE else 10)


# ---------------------------------------------------------------- releases

def releases(cfg, d):
    rel = d["releases"][:6 if PHONE else 8]
    now = parse(d["fetched_at"])
    g = prompt(cfg, 24, 30, "tail ~/.log/releases", "latest tags across projects")
    y = 60
    for r in rel:
        when = parse(r["date"])
        ago = (now - when).days
        ago_s = "today" if ago == 0 else f"{ago}d ago"
        repo = r["repo"].split("/")[1] if PHONE else r["repo"]
        if PHONE:
            line = (f'<tspan class="dim">{when:%Y-%m-%d}</tspan>  <tspan class="mag">{e(r["tag"].ljust(9))}</tspan> {e(repo)}')
        else:
            line = (f'<tspan class="dim">{when:%Y-%m-%d}</tspan>  <tspan class="ok">{r["kind"].ljust(7)}</tspan> '
                    f'<tspan class="mag">{e(r["tag"].ljust(10))}</tspan> <tspan class="p3">{e(repo.ljust(26))}</tspan><tspan class="dim">{ago_s}</tspan>')
        g += f'<text x="24" y="{y}">{line}</text>'
        y += 20
    label = "Latest releases: " + ", ".join(f'{r["repo"]} {r["tag"]} ({r["date"][:10]})' for r in rel)
    return window("releases", y - 4, g, label)


# ---------------------------------------------------------------- star charts

def axis(x0, x1, y1, Y, ymax, ystep, X, t0, t1):
    g = ""
    v = ystep
    while v <= ymax:
        g += f'<line x1="{x0}" x2="{x1}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{T["line"]}" stroke-dasharray="2 4"/>'
        g += f'<text x="{x0 - 8}" y="{Y(v) + 4:.1f}" text-anchor="end" class="dim sm">{k(v)}</text>'
        v += ystep
    every = 2 if PHONE and t1.year - t0.year > 6 else 1
    for yr in range(t0.year + 1, t1.year + 1):
        x = X(dt.date(yr, 1, 1))
        if x > x1:
            break
        if (yr - t0.year) % every:
            continue
        g += f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{y1}" y2="{y1 + 5}" stroke="{T["axis"]}"/>'
        g += f'<text x="{x:.1f}" y="{y1 + 19}" text-anchor="middle" class="dim sm">\'{str(yr)[2:]}</text>'
    return g + f'<line x1="{x0}" x2="{x1}" y1="{y1}" y2="{y1}" stroke="{T["axis"]}"/>'


def flagship(cfg, d):
    repo = cfg["flagship"]
    r = d["repos"][repo]
    now = parse(d["fetched_at"])
    pts = [(parse(ts), n) for n, ts in r["history"]]
    pts.append((now, r["stars"]))
    t0, horizon = pts[0][0], now + dt.timedelta(days=300)
    top = 46
    H = 230 if PHONE else 300
    x0, x1 = (40, W - 24) if PHONE else (56, W - 60)
    y0, y1 = top + 24, top + H - 40
    span = (horizon - t0).days
    ymax = math.ceil(r["stars"] * 1.08 / 5000) * 5000
    X = lambda t: x0 + (t - t0).days / span * (x1 - x0)
    Y = lambda v: y1 - v / ymax * (y1 - y0)

    def at(n):
        for a, b in zip(pts, pts[1:]):
            if b[1] >= n:
                f = (n - a[1]) / max(1, b[1] - a[1])
                return a[0] + dt.timedelta(days=f * (b[0] - a[0]).days)

    year_ago = now - dt.timedelta(days=365)
    base = pts[0][1]
    for a, b in zip(pts, pts[1:]):
        if b[0] >= year_ago:
            f = (year_ago - a[0]).days / max(1, (b[0] - a[0]).days)
            base = a[1] + f * (b[1] - a[1])
            break
    gained = r["stars"] - base
    rate = gained / 365
    step = 5000 if r["stars"] >= 10000 else 1000
    target = (r["stars"] // step + 1) * step
    eta = now + dt.timedelta(days=(target - r["stars"]) / rate) if rate > 0 else None

    line = " ".join(("M" if i == 0 else "L") + f"{X(t):.1f} {Y(n):.1f}" for i, (t, n) in enumerate(pts))
    g = axis(x0, x1, y1, Y, ymax, 10000 if ymax > 20000 else step, X, t0, horizon)
    g += f'<path d="{line} L{X(now):.1f} {y1} L{X(t0):.1f} {y1} Z" fill="url(#fa)"/>'
    g += f'<path d="{line}" fill="none" stroke="{T["p"]}" stroke-width="5" opacity="{T["glow"]}" filter="url(#gw)"/>'
    g += f'<path d="{line}" fill="none" stroke="{T["p2"]}" stroke-width="2"/>'
    if eta and X(eta) <= x1 + 20:
        g += f'<line x1="{X(now):.1f}" y1="{Y(r["stars"]):.1f}" x2="{X(eta):.1f}" y2="{Y(target):.1f}" stroke="{T["mag"]}" stroke-dasharray="3 4"/>'
        g += f'<circle cx="{X(eta):.1f}" cy="{Y(target):.1f}" r="4" fill="none" stroke="{T["mag"]}"/>'
        g += f'<text x="{X(eta):.1f}" y="{Y(target) - 10:.1f}" text-anchor="middle" class="mag sm">{k(target).upper()}</text>'
    m = step
    while m < r["stars"]:
        t = at(m)
        if t:
            g += f'<circle cx="{X(t):.1f}" cy="{Y(m):.1f}" r="{3.5 if PHONE else 4.5}" fill="{T["bg"]}" stroke="{T["mag"]}" stroke-width="2"/>'
            lbl = k(m).upper() if PHONE else f"{k(m).upper()} · {t:%b} '{t:%y}"
            g += f'<text x="{X(t) + 8:.1f}" y="{Y(m) + 15:.1f}" class="mag sm">{lbl}</text>'
        m += step
    g += f'<circle cx="{X(now):.1f}" cy="{Y(r["stars"]):.1f}" r="5" fill="{T["p3"]}"><animate attributeName="r" values="4;7;4" dur="2s" repeatCount="indefinite"/></circle>'
    eta_s = (f"{eta:%b} {eta.day}, {eta:%Y}" if not PHONE else f"{eta:%b} {eta.day} '{eta:%y}") if eta else "n/a"
    grid, gh = stat_grid([("stars", c(r["stars"]), ""), ("last 12 months", f"+{c(round(gained))}", ""),
                          ("per day", f"{rate:.1f}", ""), (f"pace to {k(target).upper()}", eta_s, "")], top + H + 14)
    g = prompt(cfg, 24, 30, f"stars {repo}" if PHONE else f"stars {repo} --since={t0.year}") + g + grid
    defs = (f'<linearGradient id="fa" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="{T["p"]}" stop-opacity=".35"/><stop offset="1" stop-color="{T["p"]}" stop-opacity="0"/></linearGradient>'
            '<filter id="gw"><feGaussianBlur stdDeviation="3"/></filter>')
    label = f"Line chart of {repo} stars since {t0:%b %Y}: {c(r['stars'])} stars, +{c(round(gained))} in the last 12 months, {rate:.1f} a day."
    if eta:
        label += f" On pace for {k(target).upper()} around {eta:%B} {eta.day}, {eta:%Y}."
    return window("stars", top + H + gh - 20, g, label, defs)


def beyond(cfg, d):
    flag = cfg["flagship"]
    repos = [p["repo"] for p in cfg["projects"] if p["repo"] != flag]
    cols = [T["p2"], T["mag"], T["indigo"], "#e879f9", "#a78bfa", "#f472b6", T["muted"], "#c4b5fd"]
    now = parse(d["fetched_at"])
    t0 = min(parse(d["repos"][r]["created_at"]) for r in repos)
    t0 = dt.date(t0.year, t0.month, 1)
    top = 46
    H = 220 if PHONE else 280
    x0, x1 = (40, W - 20) if PHONE else (56, W - 30)
    y0, y1 = top + 20, top + H - (40 if PHONE else 60)
    N = 80 if PHONE else 120
    span = (now - t0).days
    X = lambda t: x0 + (t - t0).days / span * (x1 - x0)
    steps = [t0 + dt.timedelta(days=i * span / N) for i in range(N + 1)]
    cum = []
    for r in repos:
        ts = sorted(parse(s) for _, s in d["repos"][r]["history"])
        row, j = [], 0
        for t in steps:
            while j < len(ts) and ts[j] <= t:
                j += 1
            row.append(j)
        cum.append(row)
    total = sum(row[-1] for row in cum)
    ystep = 500 if total > 1000 else 100
    ymax = max(ystep, math.ceil(total / ystep) * ystep)
    Y = lambda v: y1 - v / ymax * (y1 - y0)
    g = axis(x0, x1, y1, Y, ymax, ystep, X, t0, now)
    base = [0] * (N + 1)
    for idx, row in enumerate(cum):
        topv = [b + v for b, v in zip(base, row)]
        pts_t = " L".join(f"{X(t):.1f} {Y(v):.1f}" for t, v in zip(steps, topv))
        pts_b = " L".join(f"{X(t):.1f} {Y(v):.1f}" for t, v in reversed(list(zip(steps, base))))
        col = cols[idx % len(cols)]
        g += f'<path d="M{pts_t} L{pts_b}Z" fill="{col}" fill-opacity="{.35 if idx == 0 else .55}" stroke="{col}" stroke-width="1"/>'
        base = topv
    ya_i = max(0, round(N - 365 / (span / N)))
    ya = sum(row[ya_i] for row in cum)
    xa = X(now - dt.timedelta(days=365))
    g += f'<line x1="{xa:.1f}" x2="{xa:.1f}" y1="{y0}" y2="{y1}" stroke="{T["dim"]}" stroke-dasharray="3 3"/>'
    g += f'<text x="{xa - 6:.1f}" y="{y0 + 12}" text-anchor="end" class="dim sm">~{k(ya)} a year ago</text>'
    if PHONE:
        ly = top + H + 4
        for idx, r in enumerate(repos):
            col = cols[idx % len(cols)]
            lx = 24 + (idx % 2) * (W - 48) / 2
            yy = ly + (idx // 2) * 16
            g += f'<rect x="{lx:.0f}" y="{yy - 8}" width="8" height="8" fill="{col}"/><text x="{lx + 13:.0f}" y="{yy}" class="sm">{e(r.split("/")[1])} <tspan class="dim">{k(d["repos"][r]["stars"])}</tspan></text>'
        foot = ly + math.ceil(len(repos) / 2) * 16 + 8
    else:
        for idx, r in enumerate(repos):
            x = X(parse(d["repos"][r]["created_at"]))
            col = cols[idx % len(cols)]
            g += f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{y1 - 6}" y2="{y1}" stroke="{col}" stroke-width="2"/>'
            g += f'<text x="{min(x, x1 - 40):.1f}" y="{y1 + 34 + (idx % 2) * 14}" text-anchor="middle" class="sm" style="fill:{col}">{e(r.split("/")[1])}</text>'
        foot = top + H + 2
    note = f"{c(total)} stars, stacked by repo" if PHONE else f"cumulative stars since {t0:%b %Y}, stacked by repo · {c(total)} total · ticks mark each repo's creation"
    g += f'<text x="24" y="{foot}" class="dim sm">{e(note)}</text>'
    cmd = "stars --stack --exclude=authelia" if PHONE else f"stars --owner=@me --exclude={flag} --stack"
    g = prompt(cfg, 24, 30, cmd, f"beyond {flag.split('/')[1]}") + g
    label = f"Beyond {flag}: cumulative stars of every other project, {c(total)} total."
    return window("stars", foot + 16, g, label)


# ---------------------------------------------------------------- downloads

def ghcr_name(url):
    parts = url.rstrip("/").split("/")  # https://github.com/<owner>/<repo>/pkgs/container/<package>
    return f"ghcr.io/{parts[3]}/{parts[-1]}"


def downloads(cfg, d):
    dl = d["downloads"]
    flag = cfg["flagship"]
    rows = [(f'docker.io/{cfg["downloads"]["docker_hub"]}', dl["docker_hub"], T["p"]),
            (ghcr_name(cfg["downloads"]["ghcr"]), dl["ghcr"], T["mag"]),
            ("github releases", dl["github_releases"], T["indigo"])]
    tot = sum(r[1] for r in rows) or 1
    top = 46
    g = f'<text x="24" y="{top + 10}" class="lbl">{e(flag.split("/")[1].upper())} · ALL-TIME PULLS + DOWNLOADS</text>'
    g += f'<text x="24" y="{top + 54}" class="big" style="font-size:{36 if PHONE else 44}px">{k(tot)}</text>'
    if not PHONE:
        g += f'<text x="{W - 24}" y="{top + 50}" text-anchor="end" class="dim">container pulls + release downloads</text>'
    x, bw = 24, W - 48
    g += f'<rect x="24" y="{top + 72}" width="{bw}" height="14" rx="4" fill="{T["track"]}"/>'
    for name, n, col in rows:
        wd = max(4, n / tot * bw)
        g += f'<rect x="{x:.1f}" y="{top + 72}" width="{wd:.1f}" height="14" fill="{col}"/>'
        x += wd
    fs = 11.5 if PHONE else 12.5
    for i, (name, n, col) in enumerate(rows):
        y = top + 112 + i * 18
        g += f'<rect x="24" y="{y - 9}" width="9" height="9" fill="{col}"/><text x="40" y="{y}" style="font-size:{fs}px">{e(name)}</text>'
        g += f'<text x="{W - (66 if PHONE else 74)}" y="{y}" text-anchor="end" class="p3 b" style="font-size:{fs}px">{k(n)}</text><text x="{W - 24}" y="{y}" text-anchor="end" class="dim" style="font-size:{fs}px">{n / tot * 100:.1f}%</text>'
    note = "docker hub pull_count + ghcr package total + release asset downloads. pulls ≠ unique installs. CI included."
    y = top + 172
    for ln in wrap(note, maxchars(W - 48, 10.5 if PHONE else 11)):
        g += f'<text x="24" y="{y}" class="dim sm">{e(ln)}</text>'
        y += 15
    cmd = f'pulls {flag.split("/")[1]}' if PHONE else f'pulls {flag.split("/")[1]} --registries=docker.io,ghcr.io,github-releases'
    g = prompt(cfg, 24, 30, cmd) + g
    label = f"{flag} pulls and downloads: {k(tot)} total. " + ", ".join(f"{n_} {k(v)}" for n_, v, _ in rows) + "."
    return window("pulls", y + 3, g, label)


# ---------------------------------------------------------------- upstream

def upstream(cfg, d):
    up = d["upstream"]
    repos = up["repos"][:6 if PHONE else 8]
    g = prompt(cfg, 24, 30, "gh pr list --merged --upstream" if PHONE else "gh pr list --author @me --merged --upstream",
               "outside my orgs")
    g += f'<text x="24" y="60"><tspan class="p3 b">{c(up["merged"])}</tspan> merged pull requests across <tspan class="p3 b">{len(up["repos"])}</tspan> {"repos" if PHONE else "repositories I do not maintain"}</text>'
    y = 90
    for r in repos:
        years = f'{r["first"][:4]}' if r["first"][:4] == r["last"][:4] else f'{r["first"][:4]}-{r["last"][2:4]}'
        prs = f'{r["prs"]} PR' + ("s" if r["prs"] != 1 else "")
        if PHONE:
            line = f'<tspan class="mag">★ {k(r["stars"]).ljust(6)}</tspan> <tspan class="p3">{e(r["repo"])}</tspan>'
        else:
            line = (f'<tspan class="mag">★ {k(r["stars"]).ljust(6)}</tspan> <tspan class="p3">{e(r["repo"].ljust(34))}</tspan>'
                    f'<tspan class="ok">{prs.ljust(7)}</tspan> <tspan class="dim">{years}</tspan>')
        g += f'<text x="24" y="{y}">{line}</text>'
        y += 20
    label = f'{up["merged"]} merged pull requests to {len(up["repos"])} external repositories, including ' + ", ".join(r["repo"] for r in repos) + "."
    return window("upstream", y - 4, g, label)


# ---------------------------------------------------------------- standards

def standards(cfg, d):
    s = cfg["standards"]
    g = prompt(cfg, 24, 30, "cat ~/.well-known/credentials")
    y = 62
    g += f'<text x="24" y="{y}" class="lbl">CERTIFIED</text>'
    y += 22
    for cert in s["certifications"]:
        g += f'<text x="24" y="{y}"><tspan class="ok">✓</tspan> <tspan class="p3 b">{e(cert["name"])}</tspan></text>'
        sub = f'{cert["subject"]} · {cert["detail"]}'
        if PHONE:
            y += 17
            g += f'<text x="40" y="{y}" class="dim sm">{e(sub)}</text>'
        else:
            g += f'<text x="{24 + 22 * CW:.0f}" y="{y}" class="dim">{e(sub)}</text>'
        y += 22
    y += 8
    g += f'<text x="24" y="{y}" class="lbl">MEMBER OF</text>'
    y += 22
    for m in s["memberships"]:
        g += f'<text x="24" y="{y}"><tspan class="p2">◆</tspan> {e(m)}</text>'
        y += 20
    y += 10
    g += f'<text x="24" y="{y}" class="lbl">IMPLEMENTS</text>'
    y += 12
    cols = 2 if PHONE else 4
    cw = (W - 48 - (cols - 1) * 8) / cols
    fs = 10.5 if PHONE else 11.5
    for i, spec in enumerate(s["implements"]):
        cx = 24 + (i % cols) * (cw + 8)
        cy = y + (i // cols) * 30
        rfc = spec.startswith("RFC ")
        head = " ".join(spec.split(" ")[:2]) if rfc else spec
        g += f'<rect x="{cx:.1f}" y="{cy}" width="{cw:.1f}" height="22" rx="6" fill="{T["band"]}" stroke="{T["line"]}"/>'
        g += f'<text x="{cx + 10:.1f}" y="{cy + 15}" style="font-size:{fs}px"><tspan class="p2">{e(head)}</tspan>'
        if rfc and not PHONE:
            g += f' <tspan class="dim">{e(" ".join(spec.split(" ")[2:]))}</tspan>'
        g += "</text>"
    y += math.ceil(len(s["implements"]) / cols) * 30
    label = ("Credentials: " + "; ".join(f'{x["name"]} ({x["subject"]})' for x in s["certifications"]) +
             ". Member of " + ", ".join(s["memberships"]) + ". Implements " + ", ".join(s["implements"]) + ".")
    return window("credentials", y + 8, g, label)


# ---------------------------------------------------------------- jwt

def b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def identity_token(cfg):
    hdr = {"alg": "EdDSA", "kid": "jde", "typ": "profile+jwt"}
    payload = {"sub": cfg["login"], "name": "James Elliott", "roles": cfg["jwt"]["roles"], "amr": cfg["jwt"]["amr"],
               "zoneinfo": cfg["whoami"]["tz"], "iss": "https://github.com", "aud": "you", "exp": None}
    signing = b64(json.dumps(hdr, separators=(",", ":")).encode()) + "." + b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = b64(hashlib.sha512(signing.encode()).digest())
    return hdr, payload, signing.split(".") + [sig]


def json_block(obj, x, y0, width, fs):
    keyw = max(len(kk) for kk in obj) + 4
    out, y = f'<text x="{x}" y="{y0}" style="font-size:{fs}px">{{</text>', y0
    items = list(obj.items())
    for i, (kk, v) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        key = f'<tspan class="p2">{e((json.dumps(kk) + ":").ljust(keyw))}</tspan>'
        val = "null" if v is None else json.dumps(v, ensure_ascii=False, separators=(", ", ": "))
        vcls = "mag" if v is None else "p3"
        note = '  <tspan class="dim">// never expires</tspan>' if kk == "exp" else ""
        if isinstance(v, list) and 2 + keyw + len(val) > width:
            y += fs * 1.5
            out += f'<text x="{x + 16}" y="{y:.0f}" style="font-size:{fs}px">{key}<tspan class="p3">[</tspan></text>'
            for j, item in enumerate(v):
                y += fs * 1.5
                ic = "," if j < len(v) - 1 else ""
                out += f'<text x="{x + 32}" y="{y:.0f}" style="font-size:{fs}px"><tspan class="p3">{e(json.dumps(item))}</tspan>{ic}</text>'
            y += fs * 1.5
            out += f'<text x="{x + 16}" y="{y:.0f}" style="font-size:{fs}px"><tspan class="p3">]</tspan>{comma}</text>'
        else:
            y += fs * 1.5
            out += f'<text x="{x + 16}" y="{y:.0f}" style="font-size:{fs}px">{key}<tspan class="{vcls}">{e(val)}</tspan>{comma}{note}</text>'
    y += fs * 1.5
    out += f'<text x="{x}" y="{y:.0f}" style="font-size:{fs}px">}}</text>'
    return out, y - y0


def jwt(cfg, d):
    hdr, payload, parts = identity_token(cfg)
    top = 46
    fs = 11 if PHONE else 12
    g = f'<text x="24" y="{top + 6}" class="lbl">AUTHORIZATION: BEARER</text>'
    per = maxchars(W - 48, fs)
    segs = []
    for i, p in enumerate(parts):
        segs.append((p, T["jwt"][i]))
        if i < 2:
            segs.append((".", T["txt"]))
    lines, cur, n = [], "", 0
    for text, col in segs:
        while text:
            take = text[:per - n]
            cur += f'<tspan style="fill:{col}">{e(take)}</tspan>'
            n += len(take)
            text = text[len(take):]
            if n >= per:
                lines.append(cur)
                cur, n = "", 0
    if cur:
        lines.append(cur)
    y = top + 26
    for ln in lines:
        g += f'<text x="24" y="{y}" style="font-size:{fs}px">{ln}</text>'
        y += fs * 1.5
    y += 8
    g += f'<line x1="0" x2="{W}" y1="{y:.0f}" y2="{y:.0f}" stroke="{T["line"]}"/>'
    if PHONE:
        g += f'<text x="24" y="{y + 24:.0f}" class="lbl" style="fill:{T["jwt"][0]}">HEADER</text>'
        hb, hh = json_block(hdr, 24, y + 46, maxchars(W - 48, fs), fs)
        y2 = y + 46 + hh + 30
        g += hb + f'<text x="24" y="{y2:.0f}" class="lbl" style="fill:{T["jwt"][1]}">PAYLOAD</text>'
        pb, ph = json_block(payload, 24, y2 + 22, maxchars(W - 48, fs), fs)
        g += pb
        y = y2 + 22 + ph + 20
    else:
        hb, hh = json_block(hdr, 24, y + 50, 30, fs)
        pb, ph = json_block(payload, 276, y + 50, maxchars(W - 300, fs), fs)
        box = 50 + max(hh, ph) + 22
        g += f'<line x1="256" x2="256" y1="{y:.0f}" y2="{y + box:.0f}" stroke="{T["line"]}"/>'
        g += f'<text x="24" y="{y + 24:.0f}" class="lbl" style="fill:{T["jwt"][0]}">HEADER</text><text x="276" y="{y + 24:.0f}" class="lbl" style="fill:{T["jwt"][1]}">PAYLOAD</text>'
        g += hb + pb
        y += box
    g += f'<rect x="0" y="{y:.0f}" width="{W}" height="34" fill="{T["band"]}"/><line x1="0" x2="{W}" y1="{y:.0f}" y2="{y:.0f}" stroke="{T["line"]}"/>'
    g += f'<text x="24" y="{y + 22:.0f}" class="ok" style="font-size:12px">✓ signature verified</text>'
    g += f'<text x="{W - 24}" y="{y + 22:.0f}" text-anchor="end" class="dim" style="font-size:12px">{"aud=you" if PHONE else "iss=https://github.com · aud=you"}</text>'
    g = prompt(cfg, 24, 30, "jwt decode ~/.config/identity.jwt" if PHONE else "jwt decode --verify ~/.config/identity.jwt") + g
    label = "Decoded identity token: " + json.dumps(payload)
    return window("jwt decode", y + 34, g, label, scan=True)


def revoke(cfg, d):
    _, _, parts = identity_token(cfg)
    g = prompt(cfg, 24, 30, "jwt revoke ~/.config/identity.jwt")
    if PHONE:
        lines = ['<tspan class="dim">POST /oauth2/revoke</tspan>',
                 f'token={e(parts[0][:14])}...',
                 '<tspan class="ok">200 OK</tspan> <tspan class="dim">·</tspan> token revoked <tspan class="dim">· RFC 7009</tspan>',
                 None,
                 f'connection to <tspan class="p2">{e(cfg["login"])}</tspan> closed.',
                 '<tspan class="dim">[Process completed]</tspan>']
    else:
        lines = [f'<tspan class="dim">POST /oauth2/revoke</tspan>  token={e(parts[0][:20])}...  token_type_hint=access_token',
                 '<tspan class="ok">200 OK</tspan> <tspan class="dim">·</tspan> token revoked <tspan class="dim">·</tspan> session terminated <tspan class="dim">· RFC 7009</tspan>',
                 None,
                 f'connection to <tspan class="p2">{e(cfg["login"])}</tspan> closed. <tspan class="dim">// EOF</tspan>',
                 '<tspan class="dim">[Process completed]</tspan>']
    y = 52
    for ln in lines:
        if ln is None:
            y += 14
            continue
        g += f'<text x="24" y="{y}">{ln}</text>'
        y += 21
    credit = "// console after @jdx · city after @georgekobaidze"
    if PHONE:
        g += f'<text x="24" y="{y + 4}" class="dim sm">{credit}</text>'
        y += 22
    else:
        g += f'<text x="{W - 24}" y="{y - 21}" text-anchor="end" class="dim sm">{credit}</text>'
    return window("jwt revoke", y - 4, g, "Token revoked. Connection closed.", scan=True, gap=0)


# ---------------------------------------------------------------- readme

def panels(cfg, d):
    """[(name, svg, href, width_percent)] in page order for the current variant."""
    out = [("header", header(cfg), None, 100)]
    n = len(cfg["links"])
    for i, l in enumerate(cfg["links"], 1):
        out.append((f"link-{i}", link(l, n), l["url"], round(100 / n, 2)))
    out += [("telemetry", telemetry(cfg, d), None, 100),
            ("city", city(cfg, d), None, 100),
            ("projects", projects_head(cfg, d), None, 100)]
    ranked = sorted(cfg["projects"], key=lambda p: -d["repos"][p["repo"]]["stars"])
    maxstars = max(d["repos"][p["repo"]]["stars"] for p in ranked)
    for i, p in enumerate(ranked):
        r = d["repos"][p["repo"]]
        out.append((f"project-{i + 1}", card(p["repo"], r, maxstars, i % 2), r["url"], 50))
    out += [("releases", releases(cfg, d), None, 100),
            ("stars", flagship(cfg, d), d["repos"][cfg["flagship"]]["url"] + "/stargazers", 100),
            ("beyond", beyond(cfg, d), None, 100),
            ("pulls", downloads(cfg, d), "https://hub.docker.com/r/" + cfg["downloads"]["docker_hub"], 100),
            ("upstream", upstream(cfg, d), "https://github.com/pulls?q=" + d["upstream"]["query"].replace(" ", "+"), 100),
            ("credentials", standards(cfg, d), None, 100),
            ("jwt", jwt(cfg, d), None, 100),
            ("revoke", revoke(cfg, d), None, 100)]
    return out


def label_of(svgtext):
    i = svgtext.index('aria-label="') + 12
    return svgtext[i:svgtext.index('"', i)]


def picture(name, alt, width, href):
    base = f"./{OUT}"
    tag = (f'<picture>'
           f'<source media="(max-width: 600px) and (prefers-color-scheme: light)" srcset="{base}/phone/light/{name}.svg">'
           f'<source media="(max-width: 600px)" srcset="{base}/phone/dark/{name}.svg">'
           f'<source media="(prefers-color-scheme: light)" srcset="{base}/light/{name}.svg">'
           f'<img src="{base}/dark/{name}.svg" width="{width:g}%" align="top" alt="{alt}"></picture>')
    return f'<a href="{e(href)}">{tag}</a>' if href else tag


def run(root):
    cfg = json.load(open(os.path.join(root, "tools/profile/config.json")))
    d = json.load(open(os.path.join(root, "data/profile.json")))
    layout = None
    count = 0
    for phone in (False, True):
        for theme in (DARK, LIGHT):
            variant(theme, phone)
            out = os.path.join(root, OUT, *(["phone"] if phone else []), theme["name"])
            os.makedirs(out, exist_ok=True)
            for f in os.listdir(out):
                if f.endswith(".svg"):
                    os.remove(os.path.join(out, f))
            ps = panels(cfg, d)
            for name, text, _, _ in ps:
                with open(os.path.join(out, f"{name}.svg"), "w") as f:
                    f.write(text)
                count += 1
            if not phone and theme is DARK:
                layout = [(name, label_of(text), href, width) for name, text, href, width in ps]

    lines, row, roww = [], [], 0.0
    for name, alt, href, width in layout:
        tag = picture(name, alt, width, href)
        if width == 100:
            if row:
                lines.append("".join(row))
                row, roww = [], 0.0
            lines.append(tag)
            continue
        row.append(tag)
        roww += width
        if roww >= 99:
            lines.append("".join(row))
            row, roww = [], 0.0
    if row:
        lines.append("".join(row))
    readme = ("<!-- Generated by tools/profile (python3 tools/profile/profile.py). Edit config.json or the generator, not this file. -->\n"
              '<p align="center">\n' + "\n".join(lines) + "\n</p>\n")
    with open(os.path.join(root, "README.md"), "w") as f:
        f.write(readme)
    print(f"wrote {count} SVGs ({len(layout)} panels x 4 variants) and README.md")

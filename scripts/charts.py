"""Render README charts (light + dark SVG) from published results/.
usage: python3 scripts/charts.py -> assets/*.svg

Reads:
  - results/real/             (Claude Opus 5.5, Claude Code, pre-registered)
  - results/real_gemini_neon/ (Gemini 4 Neon XHigh, Antigravity CLI, generalisation)
Palette: validated categorical slots (blue, orange, aqua, yellow), light and dark steps.
"""
import csv, json, math, os, statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES, OUT = os.path.join(ROOT, "results"), os.path.join(ROOT, "assets")
os.makedirs(OUT, exist_ok=True)

THEME = {
    "light": dict(
        t1="#0b0b0b", t2="#52514e", t3="#7a7973", grid="#e4e3df", gap="#ffffff",
        s=["#2a78d6", "#eb6834", "#1baf7a", "#eda100"], tile="#f6f6f4", border="#e4e3df",
    ),
    "dark": dict(
        t1="#f0efec", t2="#c3c2b7", t3="#9a9990", grid="#30302d", gap="#0d1117",
        s=["#3987e5", "#d95926", "#199e70", "#c98500"], tile="#161b22", border="#2a2d33",
    ),
}
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
ARMS = ["baseline", "ponytail", "nonhuman"]
NAME = {"baseline": "No skill", "ponytail": "Ponytail", "nonhuman": "nonhuman"}
TASKS = [f"h{i:02d}" for i in range(1, 17)]
REPO_GROUPS = [
    ("ansible/ansible", [f"h{i:02d}" for i in range(1, 7)]),
    ("internetarchive/openlibrary", [f"h{i:02d}" for i in range(7, 13)]),
    ("qutebrowser/qutebrowser", [f"h{i:02d}" for i in range(13, 17)]),
]
CR = 0.05  # Both Opus 5.5 and Gemini 4 Neon ($3/$0.15/$15) have cache-read 0.05, output 5.0


def load_dataset(subdir, grades_file, has_cw):
    d = os.path.join(RES, subdir)
    runs = {(r["task"], r["arm"]): r for r in csv.DictReader(open(os.path.join(d, "billed_runs.csv"))) if r["task"] in TASKS}
    grades = {}
    for l in open(os.path.join(d, grades_file)):
        g = json.loads(l)
        if "excluded" not in g:
            grades[(g["task"], g["arm"])] = g
    valid = [t for t in TASKS if grades.get((t, "gold"), {}).get("resolved")]
    cost = lambda r: float(r["in"]) + 1.25 * float(r["cw"]) + CR * float(r["cr"]) + 5.0 * float(r["out"])
    tot = {a: sum(cost(runs[(t, a)]) for t in valid) for a in ARMS}
    rel = {a: tot[a] / tot["baseline"] for a in ARMS}
    calls = {a: st.mean(float(runs[(t, a)]["calls"]) for t in valid) for a in ARMS}
    resolved = {a: sum(bool(grades[(t, a)]["resolved"]) for t in valid) for a in ARMS}
    cheaper = {a: sum(cost(runs[(t, a)]) < cost(runs[(t, "baseline")]) for t in valid) for a in ARMS}
    per_task = {t: {a: cost(runs[(t, a)]) / cost(runs[(t, "baseline")]) for a in ARMS} for t in valid}

    by = {}
    for c in csv.DictReader(open(os.path.join(d, "billed_calls.csv"))):
        if c["task"] in valid:
            by.setdefault((c["task"], c["arm"]), []).append(
                {k: (float(v) if k not in ("agent", "task", "arm") else v) for k, v in c.items()}
            )
    parts = {a: {"prefix": [], "growth": [], "output": [], "thinking": []} for a in ARMS}
    for (t, a), L in by.items():
        L.sort(key=lambda x: x["call"])
        N, P = len(L), L[0]["ctx"]
        th = 5.0 * sum(x["think"] for x in L)
        out_vis = 5.0 * sum(x["out"] for x in L) - th
        if has_cw:
            pref = CR * N * P + (1.25 - CR) * L[0]["cw"]
            grow = sum(x["in"] for x in L) + 1.25 * sum(x["cw"] for x in L[1:]) + CR * (sum(x["cr"] for x in L) - N * P + L[0]["cw"])
        else:
            pref = L[0]["in"] + CR * L[0]["cr"] + CR * sum(min(P, x["cr"]) for x in L[1:])
            grow = sum(x["in"] for x in L[1:]) + CR * sum(max(0.0, x["cr"] - P) for x in L[1:])
        parts[a]["prefix"].append(pref)
        parts[a]["growth"].append(grow)
        parts[a]["output"].append(out_vis)
        parts[a]["thinking"].append(th)
    anat = {a: {k: st.mean(v) for k, v in parts[a].items()} for a in ARMS}
    return dict(valid=valid, tot=tot, rel=rel, calls=calls, resolved=resolved, cheaper=cheaper, per_task=per_task, anat=anat)


OPUS = load_dataset("real", "grades_heldout.jsonl", has_cw=True)
NEON = load_dataset("real_gemini_neon", "grades_neon.jsonl", has_cw=False)


def bar(x0, y, w, h, color, r=4):
    """Horizontal bar, square at x0, rounded at right end."""
    if w <= 0:
        return ""
    if w <= r or r <= 0:
        return f'<rect x="{x0:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h}" fill="{color}"/>'
    x1 = x0 + w
    return (
        f'<path d="M{x0:.1f},{y:.1f} H{x1-r:.1f} Q{x1:.1f},{y:.1f} {x1:.1f},{y+r:.1f} '
        f'V{y+h-r:.1f} Q{x1:.1f},{y+h:.1f} {x1-r:.1f},{y+h:.1f} H{x0:.1f} Z" fill="{color}"/>'
    )


def text(x, y, s, fill, size=13, weight=400, anchor="start", halo=None):
    h = f' stroke="{halo}" stroke-width="4" paint-order="stroke" stroke-linejoin="round"' if halo else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}"{h}>{s}</text>'


def svg(w, h, body, title):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'font-family="{FONT}" role="img" aria-label="{title}"><title>{title}</title>{body}</svg>\n'
    )


def hero(T):
    cards = [
        ("Claude Opus 5.5", "Claude Code · pre-registered", OPUS, T["s"][0], "0.76–0.88"),
        ("Gemini 4 Neon XHigh", "Antigravity CLI · generalisation", NEON, T["s"][2], "0.72–0.81"),
    ]
    w, h, gap = 820, 150, 16
    cw = (w - gap) / 2
    b = ""
    for i, (title, sub, D, accent, ci) in enumerate(cards):
        x = i * (cw + gap)
        b += f'<rect x="{x+0.5:.1f}" y="0.5" width="{cw-1:.1f}" height="{h-1}" rx="11" fill="{T["tile"]}" stroke="{T["border"]}" stroke-width="1"/>'
        b += f'<rect x="{x+18:.1f}" y="18" width="4" height="16" rx="2" fill="{accent}"/>'
        b += text(x + 29, 31, title, T["t1"], 13.5, 650)
        b += text(x + cw - 18, 30, sub, T["t3"], 11, 400, "end")
        pct = f"−{(1 - D['rel']['nonhuman']) * 100:.0f}%"
        b += text(x + 18, 76, pct, T["t1"], 34, 700)
        b += text(x + 134, 61, "billed cost vs no skill", T["t2"], 13, 500)
        b += text(x + 134, 77, f"{D['rel']['nonhuman']:.2f}× (95% CI {ci}) · Ponytail {D['rel']['ponytail']:.2f}×", T["t3"], 11.5)
        b += f'<line x1="{x+18:.1f}" y1="95" x2="{x+cw-18:.1f}" y2="95" stroke="{T["grid"]}" stroke-width="1"/>'
        cols = [
            (f"{D['resolved']['nonhuman']}/{len(D['valid'])}", "tasks resolved"),
            (f"{D['calls']['baseline']:.1f} → {D['calls']['nonhuman']:.1f}", "calls / run"),
            (f"{D['cheaper']['nonhuman']}/{len(D['valid'])}", "tasks cheaper"),
        ]
        xs = [x + 18, x + 144, x + 280]
        for cx, (val, lab) in zip(xs, cols):
            b += text(cx, 118, val, T["t1"], 14, 650)
            b += text(cx, 134, lab, T["t3"], 11)
    return svg(w, h, b, "nonhuman headline results on Claude Opus 5.5 and Gemini 4 Neon XHigh")


def anatomy(T):
    keys = [("prefix", "Prefix re-read"), ("growth", "Context growth"), ("output", "Visible output"), ("thinking", "Thinking")]
    w, left, right, bh, band = 820, 96, 198, 20, 32
    bar_w = w - left - right
    h = 338
    b = text(0, 18, "Where the bill goes (per run, normalised to each model's No skill = 100%)", T["t1"], 15, 600)
    b += text(0, 37, "exact 4-term accounting on 16 held-out SWE-Bench Pro tasks · fewer calls shrink context growth and thinking", T["t3"], 12)
    lx = 0
    for i, (_, lab) in enumerate(keys):
        b += f'<rect x="{lx:.1f}" y="52" width="10" height="10" rx="2" fill="{T["s"][i]}"/>'
        b += text(lx + 15, 61, lab, T["t2"], 12)
        lx += 15 + len(lab) * 7.4 + 26

    panels = [
        (88, "Claude Opus 5.5", "Claude Code · 1 / 1.25 cw / 0.05 cr / 5 out", OPUS, T["s"][0]),
        (218, "Gemini 4 Neon XHigh", "Antigravity CLI · $3 / $0.15 / $15 per 1M (1 / 0.05 cr / 5 out)", NEON, T["s"][2]),
    ]
    for y0, title, sub, D, accent in panels:
        b += f'<rect x="0" y="{y0-10}" width="4" height="13" rx="2" fill="{accent}"/>'
        b += text(11, y0 + 1, title, T["t1"], 13, 650)
        b += text(w - 2, y0 + 1, sub, T["t3"], 11.5, 400, "end")
        totals = {a: sum(D["anat"][a].values()) for a in ARMS}
        sx = bar_w / totals["baseline"]
        for r, a in enumerate(ARMS):
            y = y0 + 14 + r * band
            x = left
            is_nh = a == "nonhuman"
            b += text(left - 12, y + 14.5, NAME[a], T["t1"] if is_nh else T["t2"], 12.5, 600 if is_nh else 400, "end")
            for i, (k, _) in enumerate(keys):
                ww = D["anat"][a][k] * sx
                last = i == len(keys) - 1
                b += bar(x, y, max(0.0, ww - (0 if last else 1.5)), bh, T["s"][i], 4 if last else 0)
                x += ww
            delta = f" (−{(1 - D['rel'][a])*100:.0f}%)" if a != "baseline" else ""
            b += text(x + 10, y + 14.5, f"{totals[a]/1e3:,.0f}k · {D['calls'][a]:.1f} calls{delta}", T["t1"] if is_nh else T["t2"], 11.5, 600 if is_nh else 400)
    return svg(w, h, b, "Billed cost decomposition per run on Claude Opus 5.5 and Gemini 4 Neon XHigh")


def by_task(T):
    w = 820
    bh, band, group_hdr = 7.5, 22, 22
    top = 74
    all_vals = [
        D["per_task"][t][a]
        for D in (OPUS, NEON)
        for t in TASKS
        for a in ("nonhuman", "ponytail")
    ]
    xmax = max(1.4, math.ceil(max(all_vals) * 10) / 10 + 0.05)
    p1_x0, p2_x0, pw = 48, 456, 304
    sx = pw / xmax

    # Pre-compute row Y positions with repo group headers
    y_cursor = top
    layout = []
    for gname, gtasks in REPO_GROUPS:
        layout.append(("group", gname, y_cursor))
        y_cursor += group_hdr
        for t in gtasks:
            layout.append(("task", t, y_cursor))
            y_cursor += band
        y_cursor += 6
    bottom = y_cursor - 6
    h = bottom + 28

    b = text(0, 18, "Billed cost per held-out task relative to no skill", T["t1"], 15, 600)
    b += text(0, 36, "16 SWE-Bench Pro Python tasks (h01–h16) · 16/16 resolved per arm on both models", T["t3"], 12)
    # Legend top-right
    lx = w - 186
    for i, (a, c) in enumerate([("nonhuman", T["s"][0]), ("ponytail", T["s"][1])]):
        b += f'<rect x="{lx + i*96}" y="9" width="10" height="10" rx="2" fill="{c}"/>'
        b += text(lx + 15 + i * 96, 18, NAME[a], T["t2"], 12)

    panels = [
        (p1_x0, "Claude Opus 5.5", f"nh {OPUS['rel']['nonhuman']:.2f}× · pt {OPUS['rel']['ponytail']:.2f}×", OPUS, T["s"][0]),
        (p2_x0, "Gemini 4 Neon XHigh", f"nh {NEON['rel']['nonhuman']:.2f}× · pt {NEON['rel']['ponytail']:.2f}×", NEON, T["s"][2]),
    ]
    for px0, ptitle, psub, D, accent in panels:
        b += f'<rect x="{px0}" y="50" width="4" height="13" rx="2" fill="{accent}"/>'
        b += text(px0 + 10, 61, ptitle, T["t1"], 12.5, 650)
        b += text(px0 + pw, 61, psub, T["t3"], 11, 400, "end")
        ticks = [0, 0.5, 1.0, 1.4] if xmax <= 1.45 else [0, 0.5, 1.0, 1.5]
        for tick in ticks:
            if tick > xmax + 1e-6:
                continue
            gx = px0 + tick * sx
            b += f'<line x1="{gx:.1f}" y1="{top-4}" x2="{gx:.1f}" y2="{bottom}" stroke="{T["grid"]}" stroke-width="1"/>'
            b += text(gx, bottom + 15, f"{tick:.2g}×" if tick else "0", T["t3"], 10.5, anchor="middle")
        x1 = px0 + 1.0 * sx
        b += f'<line x1="{x1:.1f}" y1="{top-6}" x2="{x1:.1f}" y2="{bottom+2}" stroke="{T["t3"]}" stroke-width="1.4" stroke-dasharray="3,2"/>'

    for kind, item, y in layout:
        if kind == "group":
            b += f'<line x1="{p1_x0}" y1="{y+18}" x2="{p1_x0+pw}" y2="{y+18}" stroke="{T["grid"]}" stroke-width="0.7"/>'
            b += f'<line x1="{p2_x0}" y1="{y+18}" x2="{p2_x0+pw}" y2="{y+18}" stroke="{T["grid"]}" stroke-width="0.7"/>'
            b += text(2, y + 14, item, T["t3"], 11, 600, halo=T["gap"])
        else:
            t = item
            b += text(p1_x0 - 10, y + bh + 4, t, T["t2"], 11, 500, "end")
            for px0, _, _, D, _ in panels:
                v = D["per_task"][t]["nonhuman"]
                vp = D["per_task"][t]["ponytail"]
                b += bar(px0, y, v * sx, bh, T["s"][0], 2.5)
                b += text(px0 + v * sx + 5, y + bh - 0.5, f"{v:.2f}×", T["t1"], 10, 600, halo=T["gap"])
                b += bar(px0, y + bh + 1.5, vp * sx, bh, T["s"][1], 2.5)
                b += text(px0 + vp * sx + 5, y + 2 * bh + 1, f"{vp:.2f}×", T["t3"], 9.5, 400, halo=T["gap"])
    return svg(w, h, b, "Billed cost per held-out task on Claude Opus 5.5 and Gemini 4 Neon XHigh")


for mode, T in THEME.items():
    for name, fn in (("hero", hero), ("cost-anatomy", anatomy), ("cost-per-task", by_task)):
        open(os.path.join(OUT, f"{name}-{mode}.svg"), "w").write(fn(T))
print("Rendered:", sorted(os.listdir(OUT)))

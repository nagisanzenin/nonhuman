"""Render README charts (light + dark SVG) from results/. usage: python3 scripts/charts.py -> assets/*.svg
Numbers come from results/billed_runs.csv, results/billed_calls.csv and results/quality_*_opus.json (Opus = run >= 11).
Palette: validated categorical slots (blue, orange, aqua, yellow), light and dark steps."""
import csv, json, os, statistics as st
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES, OUT = os.path.join(ROOT, "results"), os.path.join(ROOT, "assets")
os.makedirs(OUT, exist_ok=True)
THEME = {
    "light": dict(t1="#0b0b0b", t2="#52514e", t3="#7a7973", grid="#e4e3df", gap="#ffffff",
                  s=["#2a78d6", "#eb6834", "#1baf7a", "#eda100"], tile="#f6f6f4"),
    "dark": dict(t1="#f0efec", t2="#c3c2b7", t3="#9a9990", grid="#30302d", gap="#0d1117",
                 s=["#3987e5", "#d95926", "#199e70", "#c98500"], tile="#161b22"),
}
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
ARMS = ["baseline", "ponytail", "nonhuman"]
NAME = {"baseline": "No skill", "ponytail": "Ponytail", "nonhuman": "nonhuman"}

runs = [r for r in csv.DictReader(open(os.path.join(RES, "billed_runs.csv"))) if int(r["run"]) >= 11]
mean = lambda X, k: st.mean(float(r[k]) for r in X)
rel = {}
for lang in ["all", "py", "rs", "c", "ts"]:
    sel = lambda a: [r for r in runs if r["arm"] == a and lang in (r["lang"], "all")]
    b = mean(sel("baseline"), "cost")
    rel[lang] = {a: mean(sel(a), "cost") / b for a in ARMS}
calls = {a: mean([r for r in runs if r["arm"] == a], "calls") for a in ARMS}

# per-run decomposition: prefix re-reads, context growth, visible output, thinking
calls_rows = [c for c in csv.DictReader(open(os.path.join(RES, "billed_calls.csv"))) if int(c["run"]) >= 11]
by = {}
for c in calls_rows:
    by.setdefault(c["agent"], []).append({k: (float(v) if k not in ("agent", "lang", "arm") else v) for k, v in c.items()})
parts = {a: {"prefix": [], "growth": [], "output": [], "thinking": []} for a in ARMS}
for L in by.values():
    L.sort(key=lambda x: x["call"]); N, P = len(L), L[0]["ctx"]
    th = 5 * sum(x["think"] for x in L)
    d = {"prefix": 0.1 * N * P + 1.15 * L[0]["cw"],
         "growth": 1.25 * sum(x["cw"] for x in L[1:]) + 0.1 * (sum(x["cr"] for x in L) - N * P + L[0]["cw"]),
         "output": 5 * sum(x["out"] for x in L) - th, "thinking": th}
    for k, v in d.items():
        parts[L[0]["arm"]][k].append(v)
anat = {a: {k: st.mean(v) for k, v in parts[a].items()} for a in ARMS}

sec = {a: [0, 0] for a in ARMS}
for lang in ["py", "ts", "rs", "c"]:
    for x in json.load(open(os.path.join(RES, f"quality_{lang}_opus.json"))):
        sec[x["arm"]][0] += x["sec"][0]; sec[x["arm"]][1] += x["sec"][1]


def bar(x0, y, w, h, color, r=4):
    """Horizontal bar, square at the baseline (x0), 4px rounded data end."""
    if w <= r:
        return f'<rect x="{x0:.1f}" y="{y:.1f}" width="{max(w,0):.1f}" height="{h}" fill="{color}"/>'
    x1 = x0 + w
    return (f'<path d="M{x0:.1f},{y:.1f} H{x1-r:.1f} Q{x1:.1f},{y:.1f} {x1:.1f},{y+r:.1f} V{y+h-r:.1f} '
            f'Q{x1:.1f},{y+h:.1f} {x1-r:.1f},{y+h:.1f} H{x0:.1f} Z" fill="{color}"/>')


def text(x, y, s, fill, size=13, weight=400, anchor="start", halo=None):
    h = f' stroke="{halo}" stroke-width="4" paint-order="stroke" stroke-linejoin="round"' if halo else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}"{h}>{s}</text>'


def svg(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'font-family="{FONT}" role="img" aria-label="{title}"><title>{title}</title>{body}</svg>\n')


def hero(T):
    tiles = [(f"−{(1-rel['all']['nonhuman'])*100:.0f}%", "billed cost vs no skill", "Opus · Python, TS, Rust, C"),
             (f"{calls['baseline']:.1f} → {calls['nonhuman']:.1f}", "model calls per run", "the main lever"),
             (f"{sec['nonhuman'][0]}/{sec['nonhuman'][1]}", "security tests passed", "same as no skill")]
    w, h, gap = 720, 112, 12; tw = (w - 2 * gap) / 3; b = ""
    for i, (v, lab, sub) in enumerate(tiles):
        x = i * (tw + gap)
        b += f'<rect x="{x:.1f}" y="0" width="{tw:.1f}" height="{h}" rx="10" fill="{T["tile"]}"/>'
        b += text(x + 20, 46, v, T["t1"], 32, 650) + text(x + 20, 72, lab, T["t2"], 14, 500) + text(x + 20, 93, sub, T["t3"], 12)
    return svg(w, h, b, "nonhuman headline results")


def by_language(T):
    rows = [("All", "all"), ("Python", "py"), ("Rust", "rs"), ("C", "c"), ("TypeScript", "ts")]
    w, left, right, top = 720, 96, 64, 64; bh, inner, band = 14, 4, 44
    h = top + band * len(rows) + 36; xmax = 1.15; sx = (w - left - right) / xmax
    b = text(0, 18, "Billed cost relative to no skill", T["t1"], 15, 600)
    b += text(0, 38, "lower is better · mean of 3 runs per cell · 1.0× = no skill", T["t3"], 12)
    lx = w - right - 190
    for i, (a, c) in enumerate([("nonhuman", T["s"][0]), ("ponytail", T["s"][1])]):
        b += f'<rect x="{lx + i*104}" y="10" width="10" height="10" rx="2" fill="{c}"/>' + text(lx + 16 + i*104, 19, NAME[a], T["t2"], 12)
    for tick in [0, 0.25, 0.5, 0.75, 1.0]:
        x = left + tick * sx
        b += f'<line x1="{x:.1f}" y1="{top-6}" x2="{x:.1f}" y2="{top + band*len(rows) - 8}" stroke="{T["grid"]}" stroke-width="1"/>'
        b += text(x, top + band * len(rows) + 10, f"{tick:.2g}×" if tick else "0", T["t3"], 11, anchor="middle")
    x1 = left + 1.0 * sx
    b += f'<line x1="{x1:.1f}" y1="{top-10}" x2="{x1:.1f}" y2="{top + band*len(rows) - 4}" stroke="{T["t3"]}" stroke-width="1.5"/>'
    b += text(x1 + 4, top + band * len(rows) + 26, "no skill", T["t3"], 11)
    for i, (lab, k) in enumerate(rows):
        y = top + i * band
        b += text(left - 12, y + bh + 6, lab, T["t1"] if k == "all" else T["t2"], 13, 600 if k == "all" else 400, "end")
        for j, (a, c) in enumerate([("nonhuman", T["s"][0]), ("ponytail", T["s"][1])]):
            yy = y + j * (bh + inner); v = rel[k][a]
            b += bar(left, yy, v * sx, bh, c)
            b += text(left + v * sx + 6, yy + bh - 3, f"{v:.2f}×", T["t1"] if a == "nonhuman" else T["t3"], 12, 600 if a == "nonhuman" else 400, halo=T["gap"])
    return svg(w, h, b, "Billed cost relative to no skill, by language")


def anatomy(T):
    keys = [("prefix", "Prefix re-read every call"), ("growth", "Context growth"), ("output", "Visible output"), ("thinking", "Thinking")]
    w, left, right, top, bh, band = 720, 96, 120, 84, 24, 44
    h = top + band * 3 + 16; tot = {a: sum(anat[a].values()) for a in ARMS}; sx = (w - left - right) / max(tot.values())
    b = text(0, 18, "Where the bill goes (per run, base-input-token units)", T["t1"], 15, 600)
    b += text(0, 38, "every call re-reads the whole context: fewer calls shrink the first two terms", T["t3"], 12)
    lx = 0
    for i, (k, lab) in enumerate(keys):
        b += f'<rect x="{lx}" y="54" width="10" height="10" rx="2" fill="{T["s"][i]}"/>' + text(lx + 16, 63, lab, T["t2"], 12)
        lx += 16 + len(lab) * 6.6 + 22
    for r, a in enumerate(ARMS):
        y = top + r * band; x = left
        b += text(left - 12, y + 17, NAME[a], T["t1"] if a == "nonhuman" else T["t2"], 13, 600 if a == "nonhuman" else 400, "end")
        for i, (k, _) in enumerate(keys):
            ww = anat[a][k] * sx
            last = i == len(keys) - 1
            b += bar(x, y, ww - (0 if last else 2), bh, T["s"][i], 4 if last else 0)
            x += ww
        b += text(x + 8, y + 12, f"{tot[a]/1e3:,.0f}k", T["t1"], 13, 600)
        b += text(x + 8, y + 26, f"{calls[a]:.1f} calls", T["t3"], 11)
    return svg(w, h, b, "Billed cost decomposition per run by arm")


for mode, T in THEME.items():
    for name, fn in (("hero", hero), ("cost-by-language", by_language), ("cost-anatomy", anatomy)):
        open(os.path.join(OUT, f"{name}-{mode}.svg"), "w").write(fn(T))
print(sorted(os.listdir(OUT)))

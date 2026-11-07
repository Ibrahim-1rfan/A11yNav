"""The study report: one HTML page with every graph, grouped by the HCI idea each one measures.

Made by analyze.py from its task table (no extra libraries: the charts are SVG drawn here). Each student's tasks
are averaged per condition, as in summary.md; graphs show every student as a thin grey line and the median in colour.
"""
import html
import statistics

WITHOUT, WITH, KLICKY_TIME = "#7a8290", "#1d9e75", "#9fd9c5"   # with Klicky in Klicky's own teal
INK, QUIET, GRID = "#1b1f2a", "#5a6170", "#e3e6ea"

SECTIONS = [  # (heading, what it shows, [(column, label, unit, lower is better)])
    ("Cognitive load: how much thinking it took",
     "Hesitation and stopping are signs of mental effort: the longer a student waits before acting, the more often "
     "the pointer stops and the longer it rests before a click, the harder they are working out what to do "
     "(Grimes & Valacich 2015). Klicky's own turns are left out.",
     [("first_click_s", "Time to first click", "s", True), ("pauses", "Pauses over 1 s", "", True),
      ("pause_s", "Time paused", "s", True), ("decide_s", "Time still before each click", "s", True),
      ("idle_share", "Share of own time the pointer was still", "", True)]),
    ("Cognitive offloading: searching handed over to Klicky",
     "When Klicky shows the way, the student no longer searches the screen: the pointer travels less and more "
     "directly, changes direction less, moves in fewer stop-and-go bursts and faster (load slows movement and adds "
     "corrections: Grimes & Valacich 2015; Thorpe et al. 2022; MacKenzie et al. 2001).",
     [("path_px", "Pointer distance", "px", True), ("straightness", "Path straightness (1 = straight)", "", False),
      ("turns", "Direction changes", "", True), ("bursts", "Stop-and-go movements", "", True),
      ("speed", "Pointer speed while moving", "px/s", False)]),
    ("Navigation and disorientation: finding the way through the LMS",
     "How directly the student reached the goal. Lostness (Smith 1996) combines pages visited, different pages and "
     "the fewest pages needed: 0 is a direct route, near 1 is lost. Navigation efficiency is the clicks needed "
     "divided by the clicks made.",
     [("clicks", "Clicks on the page", "", True), ("pages", "Page changes", "", True),
      ("revisits", "Pages visited again", "", True), ("lostness", "Lostness (0 = direct, 1 = lost)", "", True),
      ("nav_efficiency", "Navigation efficiency (1 = shortest)", "", False)]),
    ("Against an expert, and frustration",
     "The Keystroke-Level Model (Card, Moran & Newell) predicts an expert needs about 2.65 s per click (think 1.35 s, "
     "point 1.1 s, click 0.2 s); the chart shows how many times slower the student's own work was. Rage clicks "
     "(3+ quick clicks on one spot) show frustration.",
     [("klm_ratio", "Times slower than an expert (KLM)", "x", True), ("rage_clicks", "Rage clicks", "", True)]),
]


def time_budget(table):
    """Where the time went, as shares: moving the pointer, the pointer still (thinking, reading), Klicky's turns."""
    rows = []
    for klicky, name in (("without", "Without Klicky"), ("with", "With Klicky")):
        tasks = [r for r in table if r["klicky"] == klicky]
        total = sum(r["seconds"] for r in tasks)
        if not total:
            continue
        klicky_s = sum(r["klicky_s"] for r in tasks)
        still = sum((r["idle_share"] or 0) * r["own_s"] for r in tasks)
        moving = max(0.0, total - klicky_s - still)
        rows.append((name, [(moving / total, "#5e2770", "moving the pointer"), (still / total, "#c9a227", "pointer still (thinking)"),
                            (klicky_s / total, KLICKY_TIME, "Klicky's turn")]))
    parts = ['<svg viewBox="0 0 600 132" role="img" aria-label="Where the time went">']
    for i, (name, segments) in enumerate(rows):
        y, x = 18 + i * 46, 130
        parts.append(f'<text x="0" y="{y + 19}" font-size="13" fill="{INK}">{name}</text>')
        for share, colour, _ in segments:
            parts.append(f'<rect x="{x:.1f}" y="{y}" width="{420 * share:.1f}" height="28" fill="{colour}"/>')
            if share > .09:
                parts.append(f'<text x="{x + 6:.1f}" y="{y + 19}" font-size="12" fill="#fff">{share:.0%}</text>')
            x += 420 * share
    for j, (_, colour, what) in enumerate(rows[0][1] if rows else []):
        parts += [f'<rect x="{130 + j * 150}" y="112" width="12" height="12" fill="{colour}"/>',
                  f'<text x="{148 + j * 150}" y="122" font-size="12" fill="{QUIET}">{what}</text>']
    return "".join(parts) + "</svg>"


def per_student(table, column):
    """[(without, with)] per student: the mean of their tasks in each condition, students with both only."""
    pairs = []
    for code in sorted({r["code"] for r in table}):
        means = []
        for klicky in ("without", "with"):
            values = [r[column] for r in table if r["code"] == code and r["klicky"] == klicky and r[column] is not None]
            means.append(statistics.mean(values) if values else None)
        if None not in means:
            pairs.append(tuple(means))
    return pairs


def number(value, unit=""):
    text = f"{value:.2f}" if abs(value) < 1 else f"{value:.1f}" if abs(value) < 100 else f"{value:,.0f}"
    return f"{text} {unit}".strip()


def slope(label, unit, pairs, lower_better, p=None):
    """One small chart: each student a grey line from without to with Klicky, the median in colour."""
    w, h, left, right, top, bottom = 250, 210, 62, 188, 46, 176
    top_value = max([1.0] + [v for pair in pairs for v in pair]) * 1.12
    y = lambda v: bottom - (bottom - top) * v / top_value
    parts = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{html.escape(label)}">',
             f'<text x="12" y="20" font-size="13" font-weight="700" fill="{INK}">{html.escape(label)}</text>',
             f'<text x="12" y="36" font-size="11" fill="{QUIET}">{"lower" if lower_better else "higher"} is better'
             + (f" · p = {p:.3f}" if p is not None else "") + "</text>",
             f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="{GRID}"/>']
    for a, b in pairs:
        parts.append(f'<line x1="{left}" y1="{y(a):.1f}" x2="{right}" y2="{y(b):.1f}" stroke="#c4c9d0" stroke-width="1.2"/>')
    if pairs:
        ma, mb = statistics.median(a for a, _ in pairs), statistics.median(b for _, b in pairs)
        better = mb < ma if lower_better else mb > ma
        colour = QUIET if mb == ma else WITH if better else "#b42318"
        parts += [f'<line x1="{left}" y1="{y(ma):.1f}" x2="{right}" y2="{y(mb):.1f}" stroke="{colour}" stroke-width="3"/>',
                  f'<circle cx="{left}" cy="{y(ma):.1f}" r="5" fill="{WITHOUT}"/>',
                  f'<circle cx="{right}" cy="{y(mb):.1f}" r="5" fill="{WITH}"/>',
                  f'<text x="{left - 8}" y="{y(ma) + 4:.1f}" font-size="11" text-anchor="end" fill="{INK}">{number(ma, unit)}</text>',
                  f'<text x="{right + 8}" y="{y(mb) + 4:.1f}" font-size="11" fill="{INK}">{number(mb, unit)}</text>']
    parts += [f'<text x="{left}" y="{bottom + 18}" font-size="11" text-anchor="middle" fill="{QUIET}">without</text>',
              f'<text x="{right}" y="{bottom + 18}" font-size="11" text-anchor="middle" fill="{QUIET}">with Klicky</text>',
              "</svg>"]
    return "".join(parts)


def success_bars(table):
    rows = []
    for klicky, colour, name in (("without", WITHOUT, "Without Klicky"), ("with", WITH, "With Klicky")):
        done = [r["success"] for r in table if r["klicky"] == klicky and r["success"] is not None]
        share = sum(done) / len(done) if done else 0
        rows.append((name, colour, share, sum(done), len(done)))
    w, bar = 600, 300
    parts = [f'<svg viewBox="0 0 {w} 110" role="img" aria-label="Tasks done">']
    for i, (name, colour, share, n, total) in enumerate(rows):
        y = 18 + i * 44
        parts += [f'<text x="0" y="{y + 19}" font-size="13" fill="{INK}">{name}</text>',
                  f'<rect x="130" y="{y}" width="{bar}" height="28" fill="{GRID}" rx="4"/>',
                  f'<rect x="130" y="{y}" width="{bar * share:.1f}" height="28" fill="{colour}" rx="4"/>',
                  f'<text x="{130 + bar + 10}" y="{y + 19}" font-size="13" font-weight="700" fill="{INK}">'
                  f'{share:.0%} ({n} of {total})</text>']
    return "".join(parts) + "</svg>"


def time_bars(table):
    """Time on task split into the student's own work and the time spent with Klicky (asking, waiting, listening)."""
    own = per_student(table, "own_s")
    klicky = per_student(table, "klicky_s")
    if not own:
        return "<p>Not enough data yet.</p>"
    own_without, own_with = statistics.median(a for a, _ in own), statistics.median(b for _, b in own)
    with_klicky = statistics.median(b for _, b in klicky) if klicky else 0
    top = max(own_without, own_with + with_klicky) * 1.1 or 1
    scale = 360 / top
    parts = ['<svg viewBox="0 0 600 132" role="img" aria-label="Time on task">']
    for i, (name, segments) in enumerate((("Without Klicky", [(own_without, WITHOUT, "own work")]),
                                          ("With Klicky", [(own_with, WITH, "own work"), (with_klicky, KLICKY_TIME, "with Klicky")]))):
        y, x = 18 + i * 46, 130
        parts.append(f'<text x="0" y="{y + 19}" font-size="13" fill="{INK}">{name}</text>')
        for value, colour, what in segments:
            parts.append(f'<rect x="{x:.1f}" y="{y}" width="{value * scale:.1f}" height="28" fill="{colour}"/>')
            if value * scale > 60:
                parts.append(f'<text x="{x + 8:.1f}" y="{y + 19}" font-size="12" fill="{INK}">{number(value, "s")} {what}</text>')
            x += value * scale
        parts.append(f'<text x="{x + 8:.1f}" y="{y + 19}" font-size="13" font-weight="700" fill="{INK}">'
                     f'{number(sum(v for v, _, _ in segments), "s")}</text>')
    parts += [f'<rect x="130" y="112" width="12" height="12" fill="{WITH}"/>',
              f'<text x="148" y="122" font-size="12" fill="{QUIET}">the student’s own work</text>',
              f'<rect x="300" y="112" width="12" height="12" fill="{KLICKY_TIME}"/>',
              f'<text x="318" y="122" font-size="12" fill="{QUIET}">asking Klicky, waiting, listening</text>']
    return "".join(parts) + "</svg>"


def write(table, out, pictures, wilcoxon):
    codes = sorted({r["code"] for r in table})
    sections = []
    for heading, text, measures in SECTIONS:
        charts = []
        for column, label, unit, lower in measures:
            pairs = per_student(table, column)
            p = wilcoxon([b - a for a, b in pairs]) if len(pairs) > 1 else None
            charts.append(f'<figure>{slope(label, unit, pairs, lower, p)}</figure>')
        sections.append(f'<section><h2>{html.escape(heading)}</h2><p>{html.escape(text)}</p>'
                        f'<div class="grid">{"".join(charts)}</div></section>')
    paths = "".join(f'<figure class="wide"><img src="{p.name}" alt="Pointer paths of {p.stem[6:]}"><figcaption>'
                    f'{p.stem[6:]}: pointer path, without Klicky (left) and with Klicky (right). Green: start, red: clicks.'
                    f'</figcaption></figure>' for p in pictures if p)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Klicky study report</title>
<meta name="viewport" content="width=device-width, initial-scale=1"><style>
body {{ font-family: "Segoe UI", system-ui, sans-serif; color: {INK}; margin: 0 auto; max-width: 900px; padding: 28px 20px 60px; line-height: 1.5; }}
h1 {{ margin: 0 0 4px; }} h2 {{ margin: 36px 0 4px; }} p {{ color: {QUIET}; max-width: 70ch; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 12px; }}
figure {{ margin: 0; border: 1px solid {GRID}; border-radius: 10px; padding: 8px; background: #fff; }}
figure.wide img {{ width: 100%; }} figcaption {{ color: {QUIET}; font-size: 13px; padding: 4px; }}
</style></head><body>
<h1>Klicky study report</h1>
<p>{len(codes)} student(s), {len(table)} tasks. Every student did the same tasks without and with Klicky. Grey lines are
single students, the coloured line is the median (teal when Klicky did better, red when it did worse). p is the exact
Wilcoxon signed-rank test; it needs at least 6 students to be able to reach 0.05.</p>
<section><h2>Effectiveness: did they get it done?</h2><p>Share of tasks finished correctly without help.</p>
<figure>{success_bars(table)}</figure></section>
<section><h2>Efficiency: how long it took, and what Klicky cost</h2>
<p>Time on task, split into the student's own work and the time spent with Klicky (asking, waiting for it, listening).
Medians across students.</p><figure>{time_bars(table)}</figure></section>
<section><h2>Where the time went</h2><p>All tasks together: how much of the time the pointer was moving, how much it
was still (thinking, reading, looking for the next step), and how much was Klicky's turn.</p>
<figure>{time_budget(table)}</figure></section>
{"".join(sections)}
<section><h2>What the pointer did</h2><p>The path of the mouse in each task: searching shows as long, crossing lines.</p>
{paths}</section>
</body></html>"""
    path = out / "report.html"
    path.write_text(page, encoding="utf-8")
    return path

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


def fmt_p(p):
    return "< 0.001" if p < 0.001 else f"= {p:.3f}"


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
             + (f" · p {fmt_p(p)}" if p is not None else "") + "</text>",
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
            label = f"{number(value, 's')} {what}"
            if value * scale > len(label) * 7 + 16:   # only when the words fit inside the bar
                parts.append(f'<text x="{x + 8:.1f}" y="{y + 19}" font-size="12" fill="{INK}">{label}</text>')
            x += value * scale
        parts.append(f'<text x="{x + 8:.1f}" y="{y + 19}" font-size="13" font-weight="700" fill="{INK}">'
                     f'{number(sum(v for v, _, _ in segments), "s")}</text>')
    parts += [f'<rect x="130" y="112" width="12" height="12" fill="{WITH}"/>',
              f'<text x="148" y="122" font-size="12" fill="{QUIET}">the student’s own work</text>',
              f'<rect x="300" y="112" width="12" height="12" fill="{KLICKY_TIME}"/>',
              f'<text x="318" y="122" font-size="12" fill="{QUIET}">asking Klicky, waiting, listening</text>']
    return "".join(parts) + "</svg>"


TASK_NAMES = {"outline": "Course Outline (Computer Security)", "assignment": "Next assignment (HCI)"}


def med(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def by_task_chart(table):
    """For each task, without and with Klicky: median own work, plus the time spent with Klicky."""
    groups = []
    for task in ("outline", "assignment"):
        for klicky in ("without", "with"):
            rows = [r for r in table if r["task"] == task and r["klicky"] == klicky]
            groups.append((TASK_NAMES[task], klicky, med(r["own_s"] for r in rows), med(r["klicky_s"] for r in rows) or 0, len(rows)))
    top = max([(o or 0) + k for _, _, o, k, _ in groups] + [1]) * 1.1
    scale = 300 / top
    parts = ['<svg viewBox="0 0 640 250" role="img" aria-label="Time per task">']
    for i, (name, klicky, own, kl, n) in enumerate(groups):
        y = 16 + i * 50
        if i % 2 == 0:
            parts.append(f'<text x="0" y="{y + 12}" font-size="12" font-weight="700" fill="{INK}">{html.escape(name)}</text>')
        parts.append(f'<text x="0" y="{y + 32}" font-size="12" fill="{QUIET}">{klicky} Klicky</text>')
        x = 140
        for value, colour in ((own or 0, WITH if klicky == "with" else WITHOUT), (kl, KLICKY_TIME)):
            parts.append(f'<rect x="{x:.1f}" y="{y + 18}" width="{value * scale:.1f}" height="22" fill="{colour}"/>')
            x += value * scale
        parts.append(f'<text x="{x + 8:.1f}" y="{y + 34}" font-size="12" fill="{INK}">{number(own or 0, "s")} own'
                     + (f' + {number(kl, "s")} with Klicky' if kl else "") + f' (n = {n})</text>')
    return "".join(parts) + "</svg>"


def order_chart(table):
    """Own work by task position (1-4), one line per group: Klicky first, Klicky second."""
    w, h, left, right, top, bottom = 640, 300, 60, 600, 30, 240
    series = {}
    for order in ("Klicky second", "Klicky first"):
        rows = [r for r in table if r.get("order") == order]
        if rows:
            series[order] = [(step, med(r["own_s"] for r in rows if r["step"] == step),
                              next((r["klicky"] for r in rows if r["step"] == step), "")) for step in (1, 2, 3, 4)]
    top_value = max([v for s in series.values() for _, v, _ in s if v is not None] + [1]) * 1.15
    x = lambda step: left + (right - left) * (step - 1) / 3
    y = lambda v: bottom - (bottom - top) * v / top_value
    parts = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Own work by task position">',
             f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="{GRID}"/>']
    for step in (1, 2, 3, 4):
        parts.append(f'<text x="{x(step)}" y="{bottom + 20}" font-size="12" text-anchor="middle" fill="{QUIET}">task {step}</text>')
    styles = {"Klicky second": ("#5e2770", ""), "Klicky first": ("#c9a227", ' stroke-dasharray="6 4"')}
    for order, points in series.items():
        colour, dash = styles[order]
        pts = [(x(s), y(v)) for s, v, _ in points if v is not None]
        parts.append(f'<polyline points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in pts)}" fill="none" stroke="{colour}" stroke-width="2.5"{dash}/>')
        for s, v, klicky in points:
            if v is None:
                continue
            fill = WITH if klicky == "with" else WITHOUT
            parts += [f'<circle cx="{x(s):.1f}" cy="{y(v):.1f}" r="7" fill="{fill}" stroke="{colour}" stroke-width="2"/>',
                      f'<text x="{x(s) + 10:.1f}" y="{y(v) - 8:.1f}" font-size="11" fill="{INK}">{number(v, "s")}</text>']
    legend_y = h - 24
    parts += [f'<line x1="{left}" y1="{legend_y}" x2="{left + 30}" y2="{legend_y}" stroke="#5e2770" stroke-width="2.5"/>',
              f'<text x="{left + 36}" y="{legend_y + 4}" font-size="12" fill="{QUIET}">Klicky second (n = {len({r["code"] for r in table if r.get("order") == "Klicky second"})})</text>',
              f'<line x1="{left + 220}" y1="{legend_y}" x2="{left + 250}" y2="{legend_y}" stroke="#c9a227" stroke-width="2.5" stroke-dasharray="6 4"/>',
              f'<text x="{left + 256}" y="{legend_y + 4}" font-size="12" fill="{QUIET}">Klicky first (n = {len({r["code"] for r in table if r.get("order") == "Klicky first"})})</text>',
              f'<circle cx="{left + 440}" cy="{legend_y}" r="6" fill="{WITHOUT}"/><text x="{left + 450}" y="{legend_y + 4}" font-size="12" fill="{QUIET}">without</text>',
              f'<circle cx="{left + 510}" cy="{legend_y}" r="6" fill="{WITH}"/><text x="{left + 520}" y="{legend_y + 4}" font-size="12" fill="{QUIET}">with</text>']
    return "".join(parts) + "</svg>"


def practice_findings(table):
    """Plain sentences that separate practice from Klicky, from the numbers."""
    lines = []
    second = [r for r in table if r.get("order") == "Klicky second"]
    first = [r for r in table if r.get("order") == "Klicky first"]
    if second:
        t1, t2 = med(r["own_s"] for r in second if r["step"] == 1), med(r["own_s"] for r in second if r["step"] == 2)
        if t1 and t2:
            lines.append(f"Students who met Klicky second got faster from task 1 to task 2 on their own ({number(t1, 's')} to "
                         f"{number(t2, 's')}): that is practice, learning the LMS layout (course tabs at the top, the left menu).")
    if first:
        w = med(r["own_s"] for r in first if r["klicky"] == "with")
        wo = med(r["own_s"] for r in first if r["klicky"] == "without")
        n_first = len({r["code"] for r in first})
        if w is not None and wo is not None and n_first < 3:
            lines.append(f"Only {n_first} student(s) met Klicky first ({', '.join(sorted({r['code'] for r in first}))}): "
                         f"own work with Klicky {number(w, 's')}, later without it {number(wo, 's')}. Too few to separate "
                         "practice from Klicky; with every student meeting Klicky second, part of the improvement is practice.")
        elif w is not None and wo is not None:
            lines.append(f"Students who met Klicky first had no practice when they used it, yet their own work with Klicky "
                         f"({number(w, 's')}) was {'shorter' if w < wo else 'longer'} than their later tasks without it "
                         f"({number(wo, 's')}), which they did after practising. "
                         + ("So Klicky's effect is not only practice." if w < wo else "Here practice outweighs Klicky."))
    return "".join(f"<li>{html.escape(s)}</li>" for s in lines)


def students_table(table):
    cols = [("outline", "without"), ("outline", "with"), ("assignment", "without"), ("assignment", "with")]
    head = "".join(f"<th>{'Outline' if t == 'outline' else 'Assignment'}<br>{k}</th>" for t, k in cols)
    rows = []
    for code in sorted({r["code"] for r in table}):
        mine = [r for r in table if r["code"] == code]
        cells = []
        for task, klicky in cols:
            r = next((r for r in mine if r["task"] == task and r["klicky"] == klicky), None)
            if r is None:
                cells.append("<td>-</td>")
                continue
            done = "" if r["success"] is None else (" ✓" if r["success"] else " ✗")
            cells.append(f"<td>{r['own_s']:.0f} s{done}<br><small>{r['clicks']} clicks</small></td>")
        rows.append(f"<tr><th>{code}</th><td>{html.escape(mine[0].get('order', ''))}</td><td>{html.escape(mine[0].get('source', ''))}</td>{''.join(cells)}</tr>")
    return (f"<table><thead><tr><th>Student</th><th>Order</th><th>Data source</th>{head}</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>")


def source_check(table, wilcoxon):
    """The headline numbers again, with recorder sessions only and with every session."""
    groups = [("Recorder sessions only", [r for r in table if r.get("source") == "recorder"]), ("All sessions", table)]
    measures = [("own_s", "Own work (s)"), ("first_click_s", "Time to first click (s)"), ("path_px", "Pointer distance (px)"),
                ("clicks", "Clicks"), ("lostness", "Lostness")]
    body = []
    for name, rows in groups:
        n = len({r["code"] for r in rows})
        for column, label in measures:
            pairs = per_student(rows, column)
            if not pairs:
                continue
            p = wilcoxon([b - a for a, b in pairs]) if len(pairs) > 1 else None
            body.append(f"<tr><td>{name} (n = {n})</td><td>{label}</td><td>{number(med(a for a, _ in pairs))}</td>"
                        f"<td>{number(med(b for _, b in pairs))}</td><td>{'n/a' if p is None else fmt_p(p)}</td></tr>")
    return ("<table><thead><tr><th>Sessions</th><th>Measure</th><th>Without</th><th>With Klicky</th><th>p</th></tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table>")


def write(table, out, pictures, wilcoxon, left_out=()):
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
table {{ border-collapse: collapse; width: 100%; font-size: 13px; margin: 8px 0; }}
th, td {{ border-bottom: 1px solid {GRID}; padding: 6px 8px; text-align: left; vertical-align: top; }}
thead th {{ color: {QUIET}; font-weight: 600; }} small {{ color: {QUIET}; }} li {{ color: {INK}; margin: 6px 0; }}
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
<section><h2>Task by task</h2><p>Each task without and with Klicky: the student's own work (solid) and the time
spent with Klicky (light). Medians.</p><figure>{by_task_chart(table)}</figure></section>
<section><h2>Practice or Klicky?</h2><p>Students learn the LMS as they go, so later tasks are easier anyway (a practice
or learning effect). Comparing students who met Klicky first with those who met it second shows how much is practice
and how much is Klicky. Each line is the median own work at each task position; the dot colour shows whether that task
was with or without Klicky.</p><figure>{order_chart(table)}</figure><ul>{practice_findings(table)}</ul></section>
{"".join(sections)}
<section><h2>Every student</h2><p>Own work per task (Klicky's turns left out), clicks, and whether it was done
(✓ / ✗; blank when the file has no answer).</p>{students_table(table)}</section>
<section><h2>Data sources</h2><p>The headline results with recorder sessions only and with every session. Sessions
whose files say they were generated ("synthetic") are marked in the table above.</p>{source_check(table, wilcoxon)}
{f"<p>Not in this report: {', '.join(f'{c} (left out on purpose)' for c in left_out)}.</p>" if left_out else ""}</section>
<section><h2>What the pointer did</h2><p>The path of the mouse in each task: searching shows as long, crossing lines.</p>
{paths}</section>
</body></html>"""
    path = out / "report.html"
    path.write_text(page, encoding="utf-8")
    return path

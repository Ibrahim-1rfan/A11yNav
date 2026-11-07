"""Turns the recorder's files into the study's numbers and pictures.

Reads every study/recordings/P*.csv (+ .json), works out per task how long it took, how long before the first
click, how often the pointer stopped, how straight it moved, how many clicks and page changes, then compares each
student's tasks with Klicky against without (Wilcoxon signed-rank, exact, for small groups). Clicks on the
recorder window or the taskbar don't count, and the time Klicky was busy (asking, thinking, speaking: from Klicky's
log, or when that's missing, while a Klicky window was in front) is reported on its own and left out of pauses.

Writes study/results/tasks.csv (one row per task), study/results/summary.md (the comparison table) and
study/results/paths_<code>.png (the pointer's path, without Klicky beside with Klicky).
Usage: python study/analyze.py [folder with the recordings]
"""
import csv
import itertools
import json
import math
from pathlib import Path
import statistics
import sys

HERE = Path(__file__).resolve().parent
PAUSE_S = 1.0        # the pointer still for this long counts as a pause ("where do I go now?")
TURN_DEGREES = 90    # a change of direction sharper than this counts as a turn
MIN_STEP_PX = 3      # ignore hand tremor smaller than this
MOVING_GAP_S = 0.15  # pointer samples closer than this belong to one movement; a longer gap is a stop
RAGE = (3, 1.0, 40)  # 3 or more clicks within 1 s and 40 px: a frustrated "rage click"
# Shortest route for each task, for lostness and the expert benchmark: pages on the way (Home, the course, the tool)
# and clicks needed (course tab, then Assignments; or course tab, Syllabus, Course Outline).
ROUTE = {"assignment": {"pages": 3, "clicks": 2}, "outline": {"pages": 3, "clicks": 3}}
KLM_CLICK_S = 1.35 + 1.1 + 0.2   # Keystroke-Level Model: think (M) + point (P) + click (B, down and up)
METRICS = [  # column, label, lower is better. Klicky's own turns (asking, thinking, speaking) are left out of all
    ("own_s", "Time on task, Klicky's turns left out (s)", True),         # but "Time on task"
    ("seconds", "Time on task (s)", True),
    ("first_click_s", "Time to first click (s)", True),
    ("pauses", "Pauses over 1 s", True),
    ("pause_s", "Time paused (s)", True),
    ("decide_s", "Time still before each click (s)", True),
    ("idle_share", "Share of own time the pointer was still", True),
    ("path_px", "Pointer distance (px)", True),
    ("straightness", "Path straightness (0-1)", False),
    ("turns", "Direction changes", True),
    ("bursts", "Stop-and-go movements", True),
    ("speed", "Pointer speed while moving (px/s)", False),
    ("clicks", "Clicks on the page", True),
    ("pages", "Page changes", True),
    ("revisits", "Pages visited again", True),
    ("lostness", "Lostness (0 = direct, 1 = lost)", True),
    ("nav_efficiency", "Navigation efficiency (needed / made clicks)", False),
    ("klm_ratio", "Times slower than an expert (KLM)", True),
    ("rage_clicks", "Rage clicks", True),
]
RECORDER = "Klicky study recorder"


def window(title):
    """Which window a title belongs to: the recorder, Klicky, nothing (desktop or taskbar), or the browser page."""
    title = (title or "").strip()
    if not title:
        return "other"
    if title == RECORDER:
        return "recorder"
    if title == "Klicky" or (title.startswith("Klicky ") and not title.startswith("Klicky Mart")):
        return "klicky"
    return "page"


def load(folder):
    tasks = {}
    for path in sorted(folder.glob("P*.csv")):
        with path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                key = (row["code"], int(row["step"]))
                tasks.setdefault(key, []).append(row)
    results = {}
    for path in sorted(folder.glob("P*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for task in data["tasks"]:
            results[(data["code"], task["step"])] = task
    return tasks, results


def klicky_spans(rows, end):
    """Without Klicky's log (older recordings): the stretches when a Klicky window was in front."""
    spans, since = [], None
    for r in rows:
        if r["type"] in ("start", "page"):
            kind = window(r["title"])
            if kind == "klicky" and since is None:
                since = float(r["t"])
            elif kind != "klicky" and since is not None:
                spans.append([since, float(r["t"])])
                since = None
    if since is not None:
        spans.append([since, end])
    return spans


def overlap(a, b, spans):
    return sum(max(0.0, min(b, y) - max(a, x)) for x, y in spans)


def rage_clicks(clicks):
    """Bursts of 3+ clicks within 1 s and 40 px of each other: a sign of frustration."""
    count, need, within_s, within_px = 0, *RAGE
    i = 0
    while i < len(clicks):
        j = i
        while (j + 1 < len(clicks) and float(clicks[j + 1]["t"]) - float(clicks[i]["t"]) <= within_s
               and math.hypot(float(clicks[j + 1]["x"]) - float(clicks[i]["x"]), float(clicks[j + 1]["y"]) - float(clicks[i]["y"])) <= within_px):
            j += 1
        if j - i + 1 >= need:
            count += 1
            i = j + 1
        else:
            i += 1
    return count


def lostness(titles, required):
    """Smith (1996): sqrt((N/S - 1)^2 + (R/N - 1)^2). S pages visited, N different pages, R the fewest needed."""
    s, n = len(titles), len(set(titles))
    if not s:
        return None
    r = min(required, n)
    return math.sqrt((n / s - 1) ** 2 + (r / n - 1) ** 2)


def measure(rows, busy=None, task=None):
    """The numbers for one task, from its events in time order. busy: when Klicky was asking, thinking or speaking
    ([[from, to], ...] seconds into the task); those stretches are the student's wait, not their own pauses."""
    rows = sorted(rows, key=lambda r: float(r["t"]))
    track = [r for r in rows if r["type"] in ("start", "move", "click", "end")]
    points = [(float(r["t"]), float(r["x"]), float(r["y"])) for r in track]
    clicks = [r for r in rows if r["type"] == "click" and window(r["title"]) == "page"]   # not the recorder or taskbar
    end = next((float(r["t"]) for r in rows if r["type"] == "end"), points[-1][0] if points else 0.0)
    spans = [[max(0.0, a), min(end, b)] for a, b in (busy if busy is not None else klicky_spans(rows, end)) if b > a]
    klicky_s = overlap(0.0, end, spans)
    # pauses: gaps between pointer movements (a still pointer writes no move rows), minus Klicky's turns
    times = [float(r["t"]) for r in track if r["type"] in ("start", "move")] + [end]
    gaps = [(b - a) - overlap(a, b, spans) for a, b in zip(times, times[1:])]
    gaps = [g for g in gaps if g >= PAUSE_S]
    # path length and turns
    path, turns, heading = 0.0, 0, None
    for (_, x1, y1), (_, x2, y2) in zip(points, points[1:]):
        step = math.hypot(x2 - x1, y2 - y1)
        path += step
        if step >= MIN_STEP_PX:
            angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
            if heading is not None and abs((angle - heading + 180) % 360 - 180) > TURN_DEGREES:
                turns += 1
            heading = angle
    # straightness: straight line between the targets clicked (start -> each click) over the distance travelled
    anchors = [points[0][1:]] + [(float(c["x"]), float(c["y"])) for c in clicks] if points else []
    straight = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(anchors, anchors[1:]))
    travelled = 0.0
    if clicks:
        last_click = float(clicks[-1]["t"])
        travelled = sum(math.hypot(x2 - x1, y2 - y1) for (t1, x1, y1), (t2, x2, y2) in zip(points, points[1:]) if t2 <= last_click)
    titles = []
    for r in rows:   # pages of the site only, each change once
        if r["type"] in ("start", "page") and window(r["title"]) == "page" and (not titles or titles[-1] != r["title"]):
            titles.append(r["title"])
    seen, revisits = set(), 0
    for title in titles:
        revisits += title in seen
        seen.add(title)
    first = float(clicks[0]["t"]) if clicks else None
    # movement: samples close in time are one movement; a longer gap means the pointer stopped
    moves = [(float(r["t"]), float(r["x"]), float(r["y"])) for r in track if r["type"] in ("start", "move")]
    moving_s, moving_px, bursts, last_t = 0.0, 0.0, 0, None
    for (t1, x1, y1), (t2, x2, y2) in zip(moves, moves[1:]):
        if t2 - t1 <= MOVING_GAP_S:
            if last_t is None or t1 - last_t > MOVING_GAP_S:
                bursts += 1
            moving_s += (t2 - t1) - overlap(t1, t2, spans)
            moving_px += math.hypot(x2 - x1, y2 - y1)
            last_t = t2
    own = end - klicky_s
    move_times = [m[0] for m in moves]
    waits = []   # how long the pointer rested on the spot before each click: deciding
    for c in clicks:
        before = [mt for mt in move_times if mt <= float(c["t"])]
        if before:
            a, b = before[-1], float(c["t"])
            waits.append((b - a) - overlap(a, b, spans))
    route = ROUTE.get(task or "", {})
    lost = lostness(titles, route["pages"]) if route else None
    return {"seconds": round(end, 2), "own_s": round(own, 2), "klicky_s": round(klicky_s, 2),
            "klicky_uses": len(spans),
            "decide_s": round(statistics.mean(waits), 2) if waits else None,
            "idle_share": round(max(0.0, own - moving_s) / own, 3) if own > 0 else None,
            "bursts": bursts, "speed": round(moving_px / moving_s) if moving_s > 0 else None,
            "lostness": round(lost, 3) if lost is not None else None,
            "nav_efficiency": round(min(1.0, route["clicks"] / len(clicks)), 3) if route and clicks else None,
            "klm_ratio": round(own / (route["clicks"] * KLM_CLICK_S), 2) if route else None,
            "rage_clicks": rage_clicks(clicks),
            "first_click_s": round(first - overlap(0.0, first, spans), 2) if first is not None else None,
            "pauses": len(gaps), "pause_s": round(sum(gaps), 2), "path_px": round(path),
            "straightness": round(min(1.0, straight / travelled), 3) if travelled else None,
            "turns": turns, "clicks": len(clicks), "pages": max(0, len(titles) - 1), "revisits": revisits}


def wilcoxon(differences):
    """Two-sided exact Wilcoxon signed-rank p-value (zeros dropped, ties share ranks). None below 2 pairs."""
    d = [x for x in differences if x != 0]
    n = len(d)
    if n < 2:
        return None
    order = sorted(range(n), key=lambda i: abs(d[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(d[order[j + 1]]) == abs(d[order[i]]):
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    observed = sum(r for r, x in zip(ranks, d) if x > 0)
    mean = sum(ranks) / 2
    extreme = sum(1 for signs in itertools.product((0, 1), repeat=n)
                  if abs(sum(r for r, s in zip(ranks, signs) if s) - mean) >= abs(observed - mean) - 1e-9)
    return extreme / 2 ** n


def draw_paths(code, tasks, out):
    """The pointer's path for each task: without Klicky on the left, with Klicky on the right."""
    from PIL import Image, ImageDraw
    rows_by = {(r[0]["klicky"], r[0]["task"]): r for r in tasks}
    names = [t for t in ("assignment", "outline") if ("without", t) in rows_by or ("with", t) in rows_by]
    if not names:
        return None
    all_points = [(float(r["x"]), float(r["y"])) for rows in rows_by.values() for r in rows]
    left, top = min(p[0] for p in all_points), min(p[1] for p in all_points)
    width = max(1.0, max(p[0] for p in all_points) - left)
    height = max(1.0, max(p[1] for p in all_points) - top)
    cell = 480                                   # each panel is shaped like the screen area the pointer used
    scale = (cell - 40) / max(width, height * 1.2)
    tall = int(height * scale) + 60
    image = Image.new("RGB", (cell * 2, tall * len(names) + 30), "white")
    pen = ImageDraw.Draw(image)
    pen.text((cell // 2 - 50, 8), "Without Klicky", fill="black")
    pen.text((cell + cell // 2 - 40, 8), "With Klicky (green: start, red: clicks)", fill="black")
    for row_i, name in enumerate(names):
        for col, klicky in enumerate(("without", "with")):
            rows = sorted(rows_by.get((klicky, name), []), key=lambda r: float(r["t"]))
            ox, oy = col * cell + 20, 30 + row_i * tall + 30
            pen.rectangle((col * cell + 4, 30 + row_i * tall + 4, col * cell + cell - 4, 30 + row_i * tall + tall - 4), outline="#cccccc")
            pts = [(ox + (float(r["x"]) - left) * scale, oy + (float(r["y"]) - top) * scale) for r in rows if r["type"] != "page"]
            if len(pts) > 1:
                pen.line(pts, fill="#5e2770", width=2)
            if pts:
                pen.ellipse((pts[0][0] - 5, pts[0][1] - 5, pts[0][0] + 5, pts[0][1] + 5), fill="#3f7a2e")
            for r in rows:
                if r["type"] == "click":
                    x, y = ox + (float(r["x"]) - left) * scale, oy + (float(r["y"]) - top) * scale
                    pen.ellipse((x - 5, y - 5, x + 5, y + 5), outline="#b42318", width=2)
            pen.text((col * cell + 10, 30 + row_i * tall + 8), name, fill="#555555")
    path = out / f"paths_{code}.png"
    image.save(path)
    return path


def main(folder=None, out=None):
    folder = Path(folder) if folder else HERE / "recordings"
    out = Path(out) if out else HERE / "results"
    out.mkdir(parents=True, exist_ok=True)
    tasks, results = load(folder)
    if not tasks:
        print(f"No recordings found in {folder}.")
        return 1
    table = []
    for (code, step), rows in sorted(tasks.items()):
        result = results.get((code, step), {})
        table.append({"code": code, "step": step, "round": rows[0]["round"], "klicky": rows[0]["klicky"],
                      "task": rows[0]["task"], "success": result.get("success"),
                      **measure(rows, result.get("klicky_busy"), rows[0]["task"])})
    with (out / "tasks.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)

    codes = sorted({row["code"] for row in table})
    lines = ["# Klicky study results", "", f"{len(codes)} students, {len(table)} tasks.", ""]
    for klicky in ("without", "with"):
        done = [r["success"] for r in table if r["klicky"] == klicky and r["success"] is not None]
        if done:
            lines.append(f"- Tasks done {klicky} Klicky: {sum(done)} of {len(done)} ({100 * sum(done) / len(done):.0f}%)")
    used = [r for r in table if r["klicky"] == "with"]
    if used:
        lines += ["", "Time spent with Klicky in the with-Klicky tasks (asking, waiting for it, listening), median per task: "
                  f"{statistics.median(r['klicky_s'] for r in used):.1f} s, Klicky used "
                  f"{statistics.median(r['klicky_uses'] for r in used):.0f} time(s). It is left out of pauses and of the "
                  "first-click time below; 'Time on task' includes it."]
    lines += ["", "Each student's tasks are averaged per condition; the median across students is shown.",
              "p is the exact two-sided Wilcoxon signed-rank test (with vs without, paired by student).", "",
              "| Measure | Without Klicky | With Klicky | Better with Klicky? | p |", "| --- | --- | --- | --- | --- |"]
    for column, label, lower_better in METRICS:
        pairs = []
        for code in codes:
            means = []
            for klicky in ("without", "with"):
                values = [r[column] for r in table if r["code"] == code and r["klicky"] == klicky and r[column] is not None]
                means.append(statistics.mean(values) if values else None)
            if None not in means:
                pairs.append(means)
        if not pairs:
            continue
        without, with_ = statistics.median(p[0] for p in pairs), statistics.median(p[1] for p in pairs)
        p = wilcoxon([w - wo for wo, w in pairs])
        better = "yes" if (with_ < without if lower_better else with_ > without) else "no" if with_ != without else "same"
        lines.append(f"| {label} | {without:.2f} | {with_:.2f} | {better} | {'n/a' if p is None else f'{p:.3f}'} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    pictures = [draw_paths(code, [rows for (c, _), rows in tasks.items() if c == code], out) for code in codes]
    import importlib.util
    spec = importlib.util.spec_from_file_location("study_report", HERE / "report.py")
    report = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(report)
    page = report.write(table, out, pictures, wilcoxon)
    print("\n".join(lines))
    print(f"\nSaved {out / 'tasks.csv'}, {out / 'summary.md'}, {len([p for p in pictures if p])} path pictures "
          f"and the report with all the graphs: {page}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else None))

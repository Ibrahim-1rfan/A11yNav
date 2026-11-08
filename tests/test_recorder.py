"""The study recorder and analysis: task order, what one session writes, and the numbers drawn from it."""
import csv
import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(f"study_{name}", ROOT / "study" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


recorder, analyze = load("recorder"), load("analyze")


@pytest.fixture(autouse=True)
def no_real_klicky_log(monkeypatch):
    """Tests never read the person's real Klicky log."""
    monkeypatch.setattr(recorder, "read_log_lines", lambda paths=None: [])


def test_every_student_gets_the_same_four_tasks_in_the_same_order():
    first, other = recorder.plan("P11"), recorder.plan("P12")
    assert first == other
    assert [(s["klicky"], s["task"]) for s in first] == [("without", "outline"), ("without", "assignment"),
                                                          ("with", "outline"), ("with", "assignment")]
    assert "Computer Security" in first[0]["text"] and first[0]["text"] == first[2]["text"]
    assert "Human Computer Interaction" in first[1]["text"] and first[1]["text"] == first[3]["text"]
    with pytest.raises(ValueError):
        recorder.Session("student one")


def run_task(session, start, moves, clicks, pages=()):
    """F8, pointer moves at 20 ms steps, clicks at given sample numbers, F8, done."""
    t = start
    session.start(t, *moves[0], "Sakai : Home")
    for i, (x, y) in enumerate(moves):
        t = start + 0.02 * (i + 1)
        title = dict(pages).get(i, session.title)
        session.sample(t, x, y, i in clicks, False, title)
        if i in clicks:
            session.sample(t + 0.01, x, y, False, False, title)
    session.end(t + 0.1, *moves[-1], session.title)
    return t + 0.1


def test_a_session_writes_only_between_the_f8_presses_and_saves_after_each_answer(tmp_path):
    s = recorder.Session("P11", folder=tmp_path)
    s.sample(0.0, 5, 5, True, False, "Sakai : Home")            # before F8: not recorded
    assert s.rows == []
    end = run_task(s, 1.0, [(0, 0), (10, 0), (20, 0), (20, 0), (30, 0)], clicks={2}, pages={3: "Sakai : HCI : Overview"})
    assert s.waiting and s.start(end + 1, 0, 0, "x") is None   # waiting for done / not done: Ctrl+S ignored
    assert s.end(end + 1, 0, 0, "x") is None and s.f8(end + 1, 0, 0, "x") is None
    s.mark(True)
    kinds = [r["type"] for r in s.rows]
    assert kinds[0] == "start" and kinds[-1] == "end" and kinds.count("click") == 1 and kinds.count("page") == 1
    assert kinds.count("move") == 3                              # a still pointer writes nothing
    saved = json.loads((tmp_path / "P11.json").read_text(encoding="utf-8"))
    assert saved["tasks"][0]["success"] is True and saved["tasks"][0]["klicky"] == "without"
    assert len(list(csv.DictReader((tmp_path / "P11.csv").open(encoding="utf-8")))) == len(s.rows)
    for _ in range(3):
        run_task(s, 10.0, [(0, 0), (5, 5)], clicks={1})
        s.mark(False)
    assert s.done and s.current is None and len(s.results) == 4


def test_ctrl_s_only_starts_ctrl_e_only_ends_and_f8_toggles(tmp_path):
    s = recorder.Session("P12", folder=tmp_path)
    assert s.end(0, 0, 0, "Home") is None                     # nothing running: Ctrl+E does nothing
    assert s.start(1, 0, 0, "Home") == "started" and s.start(2, 0, 0, "Home") is None   # a second Ctrl+S is ignored
    assert s.end(3, 0, 0, "Home") == "ended" and s.waiting["seconds"] == 2
    s.mark(True)
    assert s.f8(4, 0, 0, "Home") == "started" and s.f8(5, 0, 0, "Home") == "ended"


def test_klickys_busy_time_is_read_from_its_log_for_the_task_window():
    from datetime import datetime
    start = datetime(2026, 11, 8, 10, 0, 0).timestamp()
    lines = ["2026-11-08 09:59:58,000 dock closed -> idle",          # opened just before the task
             "2026-11-08 10:00:01,000 dock idle -> listening",
             "2026-11-08 10:00:04,500 dock listening -> thinking",
             "2026-11-08 10:00:06,000 dock thinking -> speaking",
             "2026-11-08 10:00:09,000 dock speaking -> waiting",       # the student's turn: not busy
             "2026-11-08 10:00:15,000 dock waiting -> speaking",
             "2026-11-08 10:00:17,250 dock speaking -> done",
             "2026-11-08 10:00:16,000 step 2 (link: Syllabus), dock speaking",   # other lines are ignored
             "2026-11-08 10:01:00,000 dock done -> closed"]
    spans = recorder.busy_spans(lines, start, start + 20)
    assert spans == [[0.0, 1.0], [1.0, 4.5], [4.5, 6.0], [6.0, 9.0], [15.0, 17.25]]
    assert recorder.busy_spans(lines, start + 30, start + 40) == []


def test_recorder_and_taskbar_clicks_dont_count_and_klickys_turns_are_not_pauses():
    rows = [{"t": t, "type": k, "x": x, "y": y, "title": title} for t, k, x, y, title in [
        (0.0, "start", 0, 0, "Sakai : Home"), (0.5, "click", 0, 0, "Klicky study recorder"),
        (0.6, "page", 0, 0, "Klicky study recorder"), (0.7, "click", 5, 5, ""), (0.8, "page", 5, 5, "Klicky"),
        (6.0, "page", 5, 5, "Sakai : Home"), (6.1, "move", 50, 5, ""), (6.2, "click", 50, 5, "Sakai : Home"),
        (6.4, "page", 50, 5, "Sakai : HCI : Syllabus"), (7.0, "end", 50, 5, "Sakai : HCI : Syllabus")]]
    m = analyze.measure(rows)                                  # no log: Klicky's window in front counts as its turn
    assert m["clicks"] == 1 and m["pages"] == 1               # only the page click and the page change
    assert m["klicky_s"] == pytest.approx(5.2) and m["klicky_uses"] == 1
    assert m["pauses"] == 0                                    # the 6 s still pointer was Klicky's turn
    assert m["own_s"] == pytest.approx(1.8) and m["first_click_s"] == pytest.approx(1.0)
    logged = analyze.measure(rows, busy=[[0.8, 3.0]])          # from Klicky's log: only 2.2 s busy
    assert logged["klicky_s"] == pytest.approx(2.2) and logged["pauses"] == 1


def test_measures_from_one_task():
    rows = [{"t": t, "type": k, "x": x, "y": y, "title": title} for t, k, x, y, title in [
        (0.0, "start", 0, 0, "Home"), (0.1, "move", 100, 0, ""), (0.2, "move", 0, 0, ""),        # out and back: a turn
        (1.8, "move", 100, 0, ""), (1.9, "click", 100, 0, "Home"), (2.0, "page", 100, 0, "Course"),
        (2.1, "move", 100, 100, ""), (2.2, "click", 100, 100, "Course"), (2.3, "page", 100, 100, "Home"),
        (2.5, "end", 100, 100, "Home")]]
    m = analyze.measure(rows)
    assert m["seconds"] == 2.5 and m["first_click_s"] == 1.9 and m["clicks"] == 2
    assert m["pauses"] == 1 and 1.5 < m["pause_s"] < 1.7                 # still from 0.2 s to 1.8 s
    assert m["path_px"] == 400 and m["turns"] >= 1
    assert m["straightness"] == 0.5                                       # 200 px needed, 400 px travelled
    assert m["pages"] == 2 and m["revisits"] == 1                         # Home -> Course -> Home again


def test_wilcoxon_exact_p_values():
    assert analyze.wilcoxon([1, 2, 3, 4, 5]) == pytest.approx(2 / 32)   # all one way, 5 pairs: the smallest p
    assert analyze.wilcoxon([1, -1]) == 1.0
    assert analyze.wilcoxon([0, 0, 3]) is None


def test_analysis_end_to_end_writes_the_table_and_pictures(tmp_path):
    rec, out = tmp_path / "recordings", tmp_path / "results"
    for code, slow in (("P11", 3), ("P12", 2)):
        s = recorder.Session(code, folder=rec)
        while not s.done:
            step = s.current
            wander = step["klicky"] == "without"
            moves = [(i * 10, (i % 2) * 40 if wander else 0) for i in range(30 * (slow if wander else 1))]
            run_task(s, 0.0, moves, clicks={len(moves) - 1})
            s.mark(True)
    assert analyze.main(rec, out) == 0
    summary = (out / "summary.md").read_text(encoding="utf-8")
    assert "| Time on task (s) |" in summary and "Tasks done with Klicky: 4 of 4" in summary
    assert len(list(csv.DictReader((out / "tasks.csv").open(encoding="utf-8")))) == 8
    assert (out / "paths_P11.png").exists() and (out / "paths_P12.png").exists()
    page = (out / "report.html").read_text(encoding="utf-8")
    assert "Cognitive offloading" in page and page.count("<svg") == 22 and "paths_P11.png" in page


def test_lostness_rage_clicks_and_the_expert_benchmark():
    assert analyze.lostness(["Home", "Course", "Assignments"], 3) == 0.0                     # the direct route
    lost = analyze.lostness(["Home", "Course", "Home", "Other", "Home", "Course", "Assignments"], 3)
    assert 0.4 < lost < 0.6                                                                  # wandering about
    click = lambda t, x: {"t": t, "x": x, "y": 0}
    assert analyze.rage_clicks([click(0, 0), click(.2, 5), click(.4, 10), click(3, 0)]) == 1
    assert analyze.rage_clicks([click(0, 0), click(.5, 300), click(.9, 600)]) == 0          # far apart: not rage
    rows = [{"t": t, "type": k, "x": x, "y": 0, "title": title} for t, k, x, title in [
        (0.0, "start", 0, "Sakai : Home"), (0.02, "move", 10, ""), (0.04, "move", 20, ""), (2.0, "move", 30, ""),
        (2.02, "move", 40, ""), (3.0, "click", 40, "Sakai : Home"), (3.1, "page", 40, "Sakai : HCI : Overview"),
        (4.0, "click", 40, "Sakai : HCI : Overview"), (4.1, "page", 40, "Sakai : HCI : Assignments"), (5.3, "end", 40, "")]]
    m = analyze.measure(rows, busy=[], task="assignment")
    assert m["bursts"] == 2 and m["nav_efficiency"] == 1.0 and m["lostness"] == 0.0
    assert m["klm_ratio"] == pytest.approx(5.3 / (2 * analyze.KLM_CLICK_S), abs=.01)
    assert m["decide_s"] == pytest.approx((0.98 + 1.98) / 2, abs=.01)                       # still before each click
    assert 0.9 < m["idle_share"] < 1.0


def test_exported_and_synthetic_files_are_included_but_labelled_and_codes_can_be_left_out(tmp_path):
    rec, out = tmp_path / "recordings", tmp_path / "results"
    for code in ("P11", "P12", "P13"):
        s = recorder.Session(code, folder=rec)
        while not s.done:
            run_task(s, 0.0, [(i * 10, 0) for i in range(20)], clicks={19})
            s.mark(True)
    events = [{"t": 0, "type": "start", "x": 0, "y": 0, "title": "Sakai : Home"}, {"t": .5, "type": "move", "x": 50, "y": 0},
              {"t": 1, "type": "click", "x": 50, "y": 0, "button": "left", "title": "Sakai : Home"},
              {"t": 2, "type": "end", "x": 50, "y": 0, "title": "Sakai : Home"}]
    trials = [{"step": s["step"], "round": s["round"], "klicky": s["klicky"], "task": s["task"], "duration_s": 2,
               "events": events} for s in recorder.plan("P29")]
    (rec / "P29.json").write_text(json.dumps({"code": "P29", "synthetic": True, "trials": trials}), encoding="utf-8")
    assert analyze.main(rec, out, leave_out=["P13"]) == 0
    rows = list(csv.DictReader((out / "tasks.csv").open(encoding="utf-8")))
    assert sorted({r["code"] for r in rows}) == ["P11", "P12", "P29"]
    assert {r["source"] for r in rows if r["code"] == "P29"} == {"marked synthetic in file"}
    page = (out / "report.html").read_text(encoding="utf-8")
    assert "marked synthetic in file" in page and "P29" in page and "P13 (left out on purpose)" in page

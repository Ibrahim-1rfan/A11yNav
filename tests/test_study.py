"""The Klicky Mart usability study: the shop's guides, its platform, and the local results server."""
import csv
import importlib.util
import json
import threading
from pathlib import Path
import pytest
from cua.assistant import Assistant
from cua.config import Settings
from cua.rag import Index, detect_platform, load_corpus

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("study_server", ROOT / "study" / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


@pytest.fixture(scope="module")
def corpus():
    return load_corpus()


def test_the_shop_is_recognised_from_its_tab_title():
    assert detect_platform(title="Klicky Mart - Google Chrome") == "mart"
    assert detect_platform(title="Klicky Mart - Personal - Microsoft​ Edge") == "mart"
    assert detect_platform(title="Sakai : Home : Overview - Google Chrome") == "lms"


@pytest.mark.parametrize("question,title", [
    ("how do I add 2 apples to my cart?", "Add apples to your cart in Klicky Mart"),
    ("how do I add three bananas", "Add bananas to your cart in Klicky Mart"),
    ("show me how to add milk", "Add milk to your cart in Klicky Mart"),
    ("how do I add yogurt?", "Add yoghurt to your cart in Klicky Mart"),
    ("how do I remove the bread and check out?", "Remove the bread and check out in Klicky Mart"),
    ("how do I remove the eggs and check out?", "Remove the eggs and check out in Klicky Mart"),
    ("how do I check out?", "Check out in Klicky Mart"),
])
def test_each_task_gets_its_own_guided_steps_on_the_shop(corpus, question, title):
    answer = Assistant(Settings(), Index(corpus), talk=lambda q, small: pytest.fail("chatted")).answer(
        question, threading.Event(), platform="mart")
    assert answer.grounded and answer.title == title and answer.apps == ("mart",)
    assert len(answer.points) == len(answer.steps) and 2 <= len(answer.steps) <= 3   # one control per step


def test_shop_guides_point_only_at_controls_the_shop_names(corpus):
    app = (ROOT / "study" / "klicky-mart" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "study" / "klicky-mart" / "index.html").read_text(encoding="utf-8")
    for chunk in (c for c in corpus if c.platform == "mart"):
        assert chunk.evidence
        for point in chunk.points:
            kind, _, name = point.partition(": ")
            assert kind in {"link", "button"}
            prefix = name.split(": ")[0]   # "Add to cart: Apples" -> the label the shop builds with ${it.name}
            assert prefix in app or f">{name}<" in html or f'aria-label="{name}' in html, point


def round_data(**changes):
    data = {"participant": "P01", "group": "deaf", "version": "A", "klicky": "with", "task": 1,
            "text": "Add 2 apples to your cart", "success": True, "skipped": False, "seconds": 12.5,
            "first_click_seconds": 2.1, "clicks": 3, "wrong_actions": 0, "paas": 3, "events": [{"t": 10}]}
    data.update(changes)
    return data


def test_task_rows_go_to_one_summary_csv_without_the_click_log(tmp_path):
    server.save_task(round_data(), tmp_path)
    server.save_task(round_data(task=2, paas=5), tmp_path)
    rows = list(csv.DictReader((tmp_path / "summary.csv").open(encoding="utf-8")))
    assert [r["task"] for r in rows] == ["1", "2"] and rows[1]["paas"] == "5" and "events" not in rows[0]


def test_a_round_is_saved_whole_under_its_participant_code(tmp_path):
    path = server.save_round(round_data(tasks=[], tlx={"raw_tlx": 40}, sus={"score": 75}), tmp_path)
    assert path.parent == tmp_path and path.name.startswith("P01_A_with_")
    assert json.loads(path.read_text(encoding="utf-8"))["sus"]["score"] == 75


@pytest.mark.parametrize("bad", [{"participant": "../../evil"}, {"participant": ""}, {"group": "admin"},
                                 {"version": "C"}, {"klicky": "maybe"}])
def test_nothing_unexpected_reaches_a_file_name(tmp_path, bad):
    with pytest.raises(ValueError):
        server.save_round(round_data(**bad), tmp_path)
    assert list(tmp_path.iterdir()) == []

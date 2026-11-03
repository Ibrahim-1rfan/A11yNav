"""Reading the LMS page: course names, picking the course the person said, finding a step's link or button.

The page is a fake UI Automation tree shaped like the IBA LMS (Sakai) course tabs and left menu.
"""
from types import SimpleNamespace
import pytest
from cua import page
from cua.page import courses, find, is_course, pick, short_name

COURSES = ["FYP Group 2026-2027", "Computer Security (Class No 101765) - Fall 2026",
           "Introduction to Cloud Computing ( Class : 102201 ) Fall 2026", "ARABIC LANGUAGE-I ( Class : 102155 ) Fall 2026",
           "HUMAN COMPUTER INTERACTION (Class No 101624) - Fall 2026", "BUSINESS COMMUNICATION (Class No.: 99509) - FALL 2025",
           "CALCULUS - II (UMS Class:95900 / CMS Class:40286) - Spring 2024"]
SHORT = [short_name(c) for c in COURSES]


def test_short_names_drop_class_numbers_and_terms():
    assert SHORT == ["FYP Group 2026-2027", "Computer Security", "Introduction to Cloud Computing", "Arabic Language-I",
                     "Human Computer Interaction", "Business Communication", "Calculus - II"]


@pytest.mark.parametrize("said,expected", [
    ("Computer Security", "Computer Security"), ("computer security please", "Computer Security"),
    ("HCI", "Human Computer Interaction"), ("cloud", "Introduction to Cloud Computing"), ("the cloud computing one", "Introduction to Cloud Computing"),
    ("Arabic", "Arabic Language-I"), ("calculus", "Calculus - II"), ("FYP", "FYP Group 2026-2027"),
    ("business comm", "Business Communication"), ("the second one", "Computer Security"),
    ("computer", None),   # Computer Security or Human Computer Interaction: ask again
    ("biology", None), ("", None),
])
def test_pick_understands_short_and_spoken_answers(said, expected):
    assert pick(said, SHORT) == expected


def test_numbers_in_the_question_are_not_a_choice():
    assert pick("how do I submit assignment 2", SHORT, numbers=False) is None
    assert pick("how do I submit my HCI assignment", SHORT, numbers=False) == "Human Computer Interaction"


def test_course_links_are_recognised_by_address_or_name():
    assert is_course("Computer Security", "https://lms.iba.edu.pk/portal/site/56d208ec-81e0-4878")
    assert not is_course("Home", "https://lms.iba.edu.pk/portal/site/~29227")
    assert not is_course("Assignments", "https://lms.iba.edu.pk/portal/site/56d208ec/tool/3a1d5089")
    assert is_course("HUMAN COMPUTER INTERACTION (Class No 101624) - Fall 2026")


# ---- a fake page --------------------------------------------------------------------------------------------
class Rect(SimpleNamespace):
    def width(self): return self.right - self.left
    def height(self): return self.bottom - self.top


def node(name, kind, box, url="", visible=True):
    return SimpleNamespace(name=name, control_type=kind, rectangle=Rect(left=box[0], top=box[1], right=box[2], bottom=box[3]),
                           visible=visible, element=SimpleNamespace(GetCurrentPropertyValue=lambda prop: url))


@pytest.fixture
def lms(monkeypatch):
    site = "https://lms.iba.edu.pk/portal/site/"
    nodes = [node("Home", "Hyperlink", (20, 260, 150, 300), site + "~29227")]
    nodes += [node(name, "Hyperlink", (180 + 10 * i, 260, 400 + 10 * i, 300), site + f"id{i}") for i, name in enumerate(COURSES)]
    nodes += [node(COURSES[1], "Hyperlink", (300, 600, 700, 630), site + "id1"),  # the same course again, in the page body
              node("Assignments", "Hyperlink", (20, 480, 240, 520), site + "id1/tool/abc"),
              node("Old course (Class No 1)", "Hyperlink", (0, 0, 10, 10), site + "old", visible=False),  # hidden Sites drawer
              node("Submit", "Button", (280, 1500, 380, 1540)),   # below the fold
              node("Save Draft", "Button", (400, 1500, 520, 1540))]
    document = SimpleNamespace(rectangle=Rect(left=0, top=240, right=1900, bottom=1000),
                               descendants=lambda control_type: [n for n in nodes if n.control_type == control_type])
    monkeypatch.setattr(page, "document", lambda hwnd: document)
    return nodes


def test_courses_are_read_in_order_once_each(lms):
    assert courses(1) == COURSES


def test_find_points_at_the_top_bar_course_and_the_menu_link(lms):
    assert find(1, "course", COURSES[1]) == ((190, 260, 410, 300), False)
    assert find(1, "link: Assignments") == ((20, 480, 240, 520), False)
    assert find(1, "button: Submit") == ((280, 1500, 380, 1540), "below")   # there, but scrolled out of view
    assert find(1, "link: Drop Box") == (None, False)
    assert find(1, "nonsense") == (None, False)


def test_course_tabs_are_the_links_between_home_and_the_left_menu():
    site = "https://lms.iba.edu.pk/portal/site/"
    links = [("Overview", site + "%7E29227/page-reset/36aa", False),          # hidden skip link before the tabs
             ("Home", site + "%7E29227", True), ("Open attached menu for Home to access its tools", "https://lms.iba.edu.pk/portal#", True),
             ("FYP Group 2026-2027", site + "c55b", True), ("", "https://lms.iba.edu.pk/portal#", True),
             (COURSES[1], site + "56d2", False),                                # scrolled out of view: still a tab
             ("Overview", site + "%7E29227/page-reset/36aa", True), ("Profile", site + "%7E29227/tool/2ee4", True),
             ("SOFTWARE ENGINEERING (Class No.: 99412) - FALL 2025", site + "28ad", True)]  # in the page body
    assert page.course_tabs(links) == ["FYP Group 2026-2027", COURSES[1]]
    assert page.course_tabs(links[5:6] + links[-1:]) == ["SOFTWARE ENGINEERING (Class No.: 99412) - FALL 2025"]  # no Home: visible ones
    assert page.label("  Assignments ") == "Assignments" and not is_course("Home", site + "%7E29227")


def test_left_menu_links_with_icons_are_found_and_an_empty_page_is_retried(monkeypatch):
    calls = []
    doc = SimpleNamespace(rectangle=Rect(left=0, top=180, right=1900, bottom=1000),
                          descendants=lambda control_type: [node(" Assignments", "Hyperlink", (20, 480, 240, 520))]
                          if control_type == "Hyperlink" else [])
    monkeypatch.setattr(page, "document", lambda hwnd: calls.append(1) or (None if len(calls) < 3 else doc))
    monkeypatch.setattr(page.time, "sleep", lambda s: None)
    assert find(1, "link: Assignments") == (None, False)
    assert find(1, "link: Assignments") == (None, False)
    assert find(1, "link: Assignments") == ((20, 480, 240, 520), False)
    calls.clear()
    assert courses(1) == [] and len(calls) == 6          # looked six times, then gave up


def test_a_control_can_be_a_link_a_button_or_a_menu_item(monkeypatch):
    nodes = [node("Actions", "Hyperlink", (960, 610, 1048, 640)), node("Upload Files", "MenuItem", (850, 570, 950, 590)),
             node("Continue", "Button", (278, 715, 393, 755)), node("Cancel", "Button", (397, 715, 490, 755))]
    doc = SimpleNamespace(rectangle=Rect(left=0, top=100, right=1900, bottom=1000),
                          descendants=lambda control_type: [n for n in nodes if n.control_type == control_type])
    monkeypatch.setattr(page, "document", lambda hwnd: doc)
    assert find(1, "control: Actions")[0] == (960, 610, 1048, 640)
    assert find(1, "control: Upload Files")[0] == (850, 570, 950, 590)
    assert find(1, "control: Continue")[0] == (278, 715, 393, 755)
    assert find(1, "button: Upload Files") == (None, False)
    assert find(1, "control: Proceed|Continue")[0] == (278, 715, 393, 755)   # either name

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


# ---- the Assignments list and an opened assignment (shapes as read on the live IBA LMS, made-up content) ----------
def cell(name, left, right, top):
    return ("DataItem", name, left, top, right, top + 45)


TITLE_COL, STATUS_COL, OPEN_COL, DUE_COL = (278, 723), (722, 1235), (1234, 1553), (1552, 1878)
LIST_PAGE = [("Text", "Assignments", 278, 439, 1878, 467), ("Table", "List of assignments.", 278, 605, 1878, 1534),
             cell("Assignment Title", *TITLE_COL, 605), cell("Status", *STATUS_COL, 605), cell("Open Date", *OPEN_COL, 605),
             cell("Due Date", *DUE_COL, 605), ("Hyperlink", "Assignment Title", 288, 615, 430, 639)]
for top, title, status, due in [(649, "Week 08 Reading This assignment has attachments", "In progress", "Nov 4, 2026, 2:15 PM"),
                                (694, "Week 07 Reading", "Submitted Oct 28, 2026, 2:04 PM", "Oct 28, 2026, 2:15 PM"),
                                (738, "Part IV (Part A)", "Submitted Sep 21, 2026, 3:02 PM - late", "Sep 21, 2026, 3:00 PM"),
                                (782, "Project Draft", "Not Started", "Sep 30, 2026, 11:55 PM")]:
    LIST_PAGE += [cell("", 278, 1878, top), cell(title, *TITLE_COL, top), ("Hyperlink", title.split(" This")[0], 288, top + 10, 430, top + 34),
                  cell(status, *STATUS_COL, top), cell("Oct 1, 2026, 9:00 AM", *OPEN_COL, top), cell(due, *DUE_COL, top)]


def text(name, left, top, right=1878):
    return ("Text", name, left, top, right, top + 24)


OPEN_PAGE = [text("Assignment - In progress", 278, 520), ("StatusBar", "In progress", 278, 588, 1878, 613),
             text("In progress", 506, 590, 584), text("Submitted", 1041, 590, 1115), text("Returned", 1578, 590, 1644),
             text("Title", 283, 641, 321), text("Week 08 Reading", 828, 641, 968), text("This assignment has attachments", 983, 640, 1082),
             text("Due", 283, 675, 317), text("Nov 4, 2026, 2:15 PM", 828, 675, 993), text("Status", 283, 743, 337),
             text("In progress", 828, 743, 917), text("Instructions", 278, 863), text("Read the paper provided.", 278, 901),
             text("In no more than 400 words, answer the questions below:", 278, 997), text("1- What is the problem?", 278, 1021),
             text("Additional resources for assignment", 278, 1107), ("Hyperlink", "paper.pdf", 318, 1151, 579, 1175),
             text("Assignment Text", 278, 1271)]
SUBMITTED_PAGE = [text("Week 07 Reading - Submitted Oct 28, 2026, 2:04 PM", 278, 478), ("StatusBar", "Submitted", 278, 520, 1878, 545),
                  ("Table", "The grading detail of assignment submission", 278, 568, 940, 763),
                  ("DataItem", "Title", 278, 568, 433, 603), ("DataItem", "Week 07 Reading This assignment has attachments", 432, 568, 940, 603),
                  ("DataItem", "Submitted Date", 278, 636, 433, 671), ("DataItem", "Oct 28, 2026, 2:04 PM", 432, 636, 940, 671),
                  text("Instructions", 278, 777), text("Answer three questions.", 289, 825),
                  text("Original submission text", 278, 1173), text("My answer, which is not instructions.", 289, 1222)]


def test_the_assignments_list_is_read_row_by_row_with_status_and_due_date():
    rows = page.assignment_rows(LIST_PAGE)
    assert [(r.title, r.status, r.due) for r in rows] == [
        ("Week 08 Reading", "In progress", "Nov 4, 2026, 2:15 PM"), ("Week 07 Reading", "Submitted Oct 28, 2026, 2:04 PM", "Oct 28, 2026, 2:15 PM"),
        ("Part IV (Part A)", "Submitted Sep 21, 2026, 3:02 PM - late", "Sep 21, 2026, 3:00 PM"), ("Project Draft", "Not Started", "Sep 30, 2026, 11:55 PM")]
    assert [r.submitted for r in rows] == [False, True, True, False]
    assert page.assignment_rows(OPEN_PAGE) == []                     # an opened assignment isn't the list


def test_an_opened_assignment_gives_its_due_date_and_only_its_instructions():
    found = page.assignment_page(OPEN_PAGE)
    assert found == page.AssignmentPage("Week 08 Reading", False, "", "Nov 4, 2026, 2:15 PM",
                                        "Read the paper provided. In no more than 400 words, answer the questions below: "
                                        "1- What is the problem?")
    assert page.assignment_page(LIST_PAGE) is None


def test_a_submitted_assignment_is_recognised_and_its_submission_is_not_read_as_instructions():
    found = page.assignment_page(SUBMITTED_PAGE)
    assert found.submitted and found.submitted_on == "Oct 28, 2026, 2:04 PM" and found.title == "Week 07 Reading"
    assert found.instructions == "Answer three questions."


def test_due_dates_are_spoken_naturally():
    assert page.spoken_time("Nov 4, 2026, 2:15 PM") == "November 4 at 2:15 PM"
    assert page.spoken_time("Sep 19, 2026, 12:05 AM") == "September 19 at 12:05 AM"
    assert page.spoken_time("tomorrow") == "tomorrow" and page.due_time("tomorrow") is None


@pytest.mark.parametrize("said,expected", [("week 8", "Week 08 Reading"), ("week eight reading", "Week 08 Reading"),
                                           ("the seventh week one", "Week 07 Reading"), ("project draft", "Project Draft"),
                                           ("the second one", "Week 07 Reading"), ("reading", None)])
def test_an_assignment_is_picked_by_number_or_words(said, expected):
    options = ["Week 08 Reading", "Week 07 Reading", "Project Draft", "Assignment 6"]
    assert pick(said, options) == expected


def test_a_link_name_ending_in_a_bracket_is_found(monkeypatch):
    link = node("Part IV (Part A)", "Hyperlink", (288, 748, 443, 772))
    doc = SimpleNamespace(rectangle=Rect(left=0, top=0, right=1900, bottom=1000),
                          descendants=lambda control_type=None: [link] if control_type == "Hyperlink" else [])
    monkeypatch.setattr(page, "document", lambda hwnd: doc)
    assert find(1, "link: Part IV (Part A)")[0] == (288, 748, 443, 772)


def test_the_tool_a_tab_shows_and_whether_a_step_opens_it():
    assert not hasattr(page, "press")                                 # Klicky never opens pages itself
    assert page.tool_of("Sakai : Computer Security (Class No 101765) - Fall 2026 : Assignments - Google Chrome") == "Assignments"
    assert page.opens("link: Assignments", "Assignments") and not page.opens("control: Submit", "Submit")

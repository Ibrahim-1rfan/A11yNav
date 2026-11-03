"""Reading and pointing inside a web page (the LMS), through the browser's UI Automation tree.

Only link and button names, positions and link addresses are read, on this machine, to list the person's courses
and to find the control a guided step points at. Nothing is clicked or typed: the person does every step.
"""
import re
import time
from dataclasses import dataclass
from datetime import datetime
from PySide6.QtCore import QThread, Signal

# A course site's home link, e.g. https://lms.iba.edu.pk/portal/site/56d208ec-... (not a tool page, not ~Home).
SITE_URL = re.compile(r"/portal/site/(?!~|%7E)[^/?#]+/?$", re.I)
HOME_URL = re.compile(r"/portal/site/(?:~|%7E)[^/?#]*/?$", re.I)   # your own Home tab, e.g. /portal/site/%7E29227
TOOL_URL = re.compile(r"/(?:tool|page-reset|page)/", re.I)          # left-menu links: the course tabs have ended
ICONS = re.compile(r"[-]")  # icon-font glyphs in link names, e.g. " Overview"
COURSE_NAME = re.compile(r"\(\s*(?:UMS\s+)?Class\b|\bClass\s*(?:No\.?|:)", re.I)
TERM = re.compile(r"\s*-?\s*\b(?:Fall|Spring|Summer|Winter)\s*\d{4}\s*$", re.I)
NUMBERS = {"first": 1, "one": 1, "1": 1, "second": 2, "two": 2, "2": 2, "third": 3, "three": 3, "3": 3, "fourth": 4,
           "four": 4, "4": 4, "fifth": 5, "five": 5, "5": 5, "sixth": 6, "six": 6, "6": 6, "seventh": 7, "seven": 7,
           "7": 7, "eighth": 8, "eight": 8, "8": 8}
FILLER = set("the a an my course class subject for of in on to and please one it its that this i want need assignment "
             "assignments submit upload how do can see show me where what which have find open read check view get tell "
             "is are".split())
THIS_ONE = re.compile(r"\b(?:this|current|same|here)\b", re.I)  # "this one": the course the person is in
MAX_OPTIONS = 8
ATTACHED = re.compile(r"\s*This assignment has attachments\s*$", re.I)
# Where an assignment's Instructions end (checked on the live IBA LMS): its attachments, the submission, the buttons.
INSTRUCTIONS_END = {"additional resources for assignment", "submission", "original submission text", "assignment text",
                    "no attachments submitted", "back to list", "proceed", "save draft", "preview", "cancel"}
DONE_STATES = ("submitted", "returned", "graded", "resubmitted")
MAX_INSTRUCTIONS = 4000


@dataclass(frozen=True)
class Assignment:
    """One row of a course's Assignments list."""
    title: str
    status: str     # as the LMS shows it: "Not Started", "In progress", "Submitted Oct 28, 2026, 2:04 PM", "Returned"
    due: str        # "Nov 4, 2026, 2:15 PM"

    @property
    def submitted(self):
        return self.status.lower().startswith(DONE_STATES)


@dataclass(frozen=True)
class AssignmentPage:
    """What an opened assignment says about itself."""
    title: str
    submitted: bool
    submitted_on: str   # "Oct 28, 2026, 2:04 PM", when submitted
    due: str
    instructions: str


def short_name(full):
    """'Computer Security (Class No 101765) - Fall 2026' -> 'Computer Security'; all capitals become Title Case."""
    name = re.sub(r"\s*\([^)]*\)\s*", " ", full)
    name = TERM.sub("", name)
    name = re.sub(r"\s+", " ", name).strip(" -") or full.strip()
    if name.isupper():  # "HUMAN COMPUTER INTERACTION" -> "Human Computer Interaction", keeping Roman numerals like "II"
        name = re.sub(r"[A-Z]+", lambda m: m.group() if re.fullmatch(r"[IVX]+", m.group()) else m.group().capitalize(), name)
    return name


def is_course(name, url=""):
    return bool(name) and (bool(url and SITE_URL.search(url)) or bool(COURSE_NAME.search(name)))


def label(name):
    """A link's readable name: icon glyphs and extra spaces removed."""
    return " ".join(ICONS.sub(" ", name or "").split())


def course_tabs(links):
    """links: (name, address, visible) in page order. The course tabs follow the Home tab and end at the left menu,
    whether or not the top bar is scrolled out of view. Without a Home tab, visible course-like links are used."""
    names, started = [], False
    for name, url, _visible in links:
        if HOME_URL.search(url):
            started = True
        elif started and TOOL_URL.search(url):
            break
        elif started and is_course(name, url) and name not in names:
            names.append(name)
    if not names:
        names = list(dict.fromkeys(name for name, url, visible in links if visible and is_course(name, url)))
    return names


def _words(text):
    """Meaningful words; numbers as plain digits, so "week eight", "week 8" and "Week 08" match."""
    words = [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in FILLER]
    return [str(NUMBERS[w]) if w in NUMBERS else w.lstrip("0") or "0" if w.isdigit() else w for w in words]


def _initials(name):
    return "".join(w[0] for w in re.findall(r"[A-Za-z]+", name) if len(w) > 2 or w.isupper()).lower()


def pick(text, options, numbers=True):
    """The option the person meant, or None when it's unclear. options: short names in the order they were offered.
    numbers: accept "the second one"; off when reading the original question ("assignment 2" isn't a choice)."""
    words = _words(text)
    if not words or not options:
        return None
    for word in words if numbers else ():  # "the second one"
        if word in NUMBERS and NUMBERS[word] <= len(options) and len(words) == 1:
            return options[NUMBERS[word] - 1]
    scores = []
    for option in options:
        own = set(_words(option))
        score = sum(1 for w in words if w in own or any(o.startswith(w) and len(w) >= 4 for o in own))
        if any(w == _initials(option) and len(w) >= 2 for w in words):  # "HCI"
            score += 2
        scores.append(score)
    best = max(scores)
    if best == 0 or scores.count(best) > 1:
        return None
    return options[scores.index(best)]


def tool_of(title):
    """The LMS tool the tab shows: 'Sakai : Computer Security (...) - Fall 2026 : Assignments - Google Chrome' ->
    'Assignments'. Empty when the title isn't an LMS page."""
    parts = title.split(" : ")
    if len(parts) < 3:
        return ""
    tool = re.sub(r"\s+-\s+.*(?:Chrome|Edge|Firefox).*$", "", parts[-1])
    return re.sub(r"\s+and \d+ more pages?$", "", tool).strip()


def opens(spec, tool):
    """Whether a "link: Assignments" step opens the tool the tab already shows."""
    kind, _, names = spec.partition(":")
    return kind.strip() == "link" and bool(tool) and any(
        n.strip().lower() == tool.lower() for n in names.split("|"))


def due_time(text):
    """'Nov 4, 2026, 2:15 PM' -> datetime, or None."""
    try:
        return datetime.strptime(text.strip(), "%b %d, %Y, %I:%M %p")
    except (ValueError, AttributeError):
        return None


def spoken_time(text):
    """'Nov 4, 2026, 2:15 PM' -> 'November 4 at 2:15 PM', for reading aloud; other text is kept as it is."""
    when = due_time(text)
    if when is None:
        return text.strip()
    return f"{when:%B} {when.day} at {when:%I:%M %p}".replace(" at 0", " at ")


def assignment_rows(items):
    """[Assignment] from the Assignments list table, top to bottom. items: (kind, name, left, top, right, bottom).
    Each cell sits under its column's header, so cells are matched to the header by their left and right edges."""
    cells = [item for item in items if item[0] == "DataItem"]
    header = {item[1]: item for item in cells if item[1] in ("Assignment Title", "Status", "Due Date")}
    if "Assignment Title" not in header:
        return []
    rows = {}
    for kind, name, left, top, right, bottom in cells:
        if top <= header["Assignment Title"][3]:
            continue
        for column, head in header.items():
            if abs(left - head[2]) <= 3 and abs(right - head[4]) <= 3:
                rows.setdefault(top, {})[column] = name
    found = []
    for top in sorted(rows):
        title = ATTACHED.sub("", rows[top].get("Assignment Title", "")).strip()
        if title and title not in (a.title for a in found):
            found.append(Assignment(title, rows[top].get("Status", ""), rows[top].get("Due Date", "")))
    return found


def value_beside(items, name):
    """The value to the right of a label on the same row, e.g. 'Due' -> 'Nov 4, 2026, 2:15 PM'."""
    for i, (kind, text, left, top, right, bottom) in enumerate(items):
        if text != name or kind not in ("Text", "DataItem"):
            continue
        for other in items[i + 1:i + 6]:
            if other[0] in ("Text", "DataItem") and abs(other[3] - top) <= 6 and other[2] >= right - 4 and other[1] != name:
                return other[1]
    return ""


def assignment_page(items):
    """AssignmentPage from an opened assignment, or None when this isn't one (the list, or still loading)."""
    status = next((text for kind, text, *_ in items if kind == "StatusBar"), "")
    start = next((i for i, (kind, text, *_) in enumerate(items) if kind == "Text" and text == "Instructions"), None)
    if start is None and not status:
        return None
    parts = []
    for kind, text, *_ in items[start + 1:] if start is not None else ():
        if text.lower() in INSTRUCTIONS_END or kind in ("Button", "Table", "Pane", "Edit", "Group"):
            break
        if kind in ("Text", "ListItem") and text not in parts:
            parts.append(text)
    submitted_on = value_beside(items, "Submitted Date")
    return AssignmentPage(title=ATTACHED.sub("", value_beside(items, "Title")).strip(),
                          submitted=status.lower().startswith(DONE_STATES) or bool(submitted_on),
                          submitted_on=submitted_on, due=value_beside(items, "Due"),
                          instructions=" ".join(parts)[:MAX_INSTRUCTIONS])


def named_items(page):
    """(kind, name, left, top, right, bottom) of every named element in the page, in reading order."""
    found = []
    for info in page.descendants():
        try:
            name, r, kind = label(info.name), info.rectangle, info.control_type
        except Exception:
            continue
        if name:
            found.append((kind, name, r.left, r.top, r.right, r.bottom))
    return found


def assignments(hwnd, tries=6, wait=.5):
    """The Assignments list on the page, read again while it loads; [] when this isn't the list."""
    for attempt in range(tries):
        page = document(hwnd)
        rows = assignment_rows(named_items(page)) if page is not None else []
        if rows:
            return rows
        if attempt < tries - 1:
            time.sleep(wait)
    return []


def opened_assignment(hwnd, tries=8, wait=.5):
    """The assignment just opened (AssignmentPage), read again while it loads; None when none appears."""
    for attempt in range(tries):
        page = document(hwnd)
        found = assignment_page(named_items(page)) if page is not None else None
        if found and (found.instructions or found.submitted):
            return found
        if attempt < tries - 1:
            time.sleep(wait)
    return None


def document(hwnd):
    """The visible web page's UI Automation element in a browser window."""
    from pywinauto import Desktop
    window = Desktop(backend="uia").window(handle=hwnd).wrapper_object()
    for info in window.element_info.descendants(control_type="Document"):
        r = info.rectangle
        if r.width() > 0 and r.height() > 0 and info.visible:
            return info
    return None


def link_url(info):
    try:
        return str(info.element.GetCurrentPropertyValue(30045) or "")  # UIA_ValueValuePropertyId: a link's address
    except Exception:
        return ""


def courses(hwnd, tries=6, wait=.4):
    """Full course names from the page's course tabs, in order. Chrome builds a page's accessibility tree only once
    something asks for it, so the first look can come back empty: look again for a couple of seconds."""
    for attempt in range(tries):
        page = document(hwnd)
        if page is not None:
            found = course_tabs([(label(i.name), link_url(i), i.visible) for i in page.descendants(control_type="Hyperlink")])
            if found:
                return found
        if attempt < tries - 1:
            time.sleep(wait)
    return []


PRESSABLE = ("course", "link")  # what Klicky may open by itself: the course tab and menu links, never a button


def find(hwnd, spec, chosen=""):
    """Rect (physical pixels) of the control a step points at, and False, or "above"/"below" when scrolled out of view.

    spec: "course" (the chosen course's tab), "link: <name>", "button: <name>" or "control: <name>" (a link, button
    or menu item; pages draw the same control differently). The control's name starts with <name>; "A|B" allows
    either, e.g. "control: Proceed|Submit"."""
    _info, rect, hidden = locate(hwnd, spec, chosen)
    return rect, hidden


def press(hwnd, spec, chosen=""):
    """Open a course tab or menu link through UI Automation, as a screen reader would; the mouse never moves.
    Only "course" and "link:" steps, and only a real link, are ever pressed. True when it was pressed."""
    if spec.partition(":")[0].strip().lower() not in PRESSABLE:
        return False
    info, rect, _hidden = locate(hwnd, spec, chosen)
    if info is None or info.control_type != "Hyperlink":
        return False
    from pywinauto.controls.uiawrapper import UIAWrapper
    control = UIAWrapper(info)
    try:
        control.invoke()
        return True
    except Exception:
        pass
    try:
        control.iface_legacy_iaccessible.DoDefaultAction()  # links that don't offer Invoke
        return True
    except Exception:
        return False


def locate(hwnd, spec, chosen=""):
    """(element info, rect, hidden) of the control a step points at; (None, None, False) when it isn't there."""
    page = document(hwnd)
    if page is None:
        return None, None, False
    kind, _, name = spec.partition(":")
    kind, name = kind.strip().lower(), name.strip()
    if kind == "course":
        types, wanted = ("Hyperlink",), lambda text: text == chosen or text.startswith(chosen)
    else:
        types = {"link": ("Hyperlink",), "button": ("Button",), "control": ("Hyperlink", "Button", "MenuItem")}.get(kind)
        if not types or not name:
            return None, None, False
        pattern = re.compile(rf"^\s*(?:{'|'.join(re.escape(n.strip()) for n in name.split('|'))})(?!\w)", re.I)
        wanted = lambda text: bool(pattern.match(text))
    view = page.rectangle
    best = None
    for info in (info for control_type in types for info in page.descendants(control_type=control_type)):
        text = label(info.name)
        r = info.rectangle
        if not text or not wanted(text) or r.width() <= 0:
            continue
        rect = (r.left, r.top, r.right, r.bottom)
        if info.visible and view.top <= r.top and r.bottom <= view.bottom:
            return info, rect, False  # first on screen, in reading order: the top bar before the page body
        best = best or (info, rect, "above" if r.bottom <= view.top else "below")
    return best or (None, None, False)


class PageWorker(QThread):
    """Runs one page lookup off the UI thread. result(value) gets the function's return, or None on failure."""
    result = Signal(object)

    def __init__(self, fn, *args):
        super().__init__()
        self.fn, self.args = fn, args

    def run(self):
        import sys
        import pythoncom
        sys.coinit_flags = 2
        pythoncom.CoInitialize()
        try:
            self.result.emit(self.fn(*self.args))
        except Exception:
            self.result.emit(None)
        finally:
            pythoncom.CoUninitialize()

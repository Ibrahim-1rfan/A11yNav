"""Reading and pointing inside a web page (the LMS), through the browser's UI Automation tree.

Only link and button names, positions and link addresses are read, on this machine, to list the person's courses
and to find the control a guided step points at. Nothing is clicked or typed: the person does every step.
"""
import re
import time
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
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in FILLER]


def _initials(name):
    return "".join(w[0] for w in re.findall(r"[A-Za-z]+", name) if len(w) > 2 or w.isupper()).lower()


def pick(text, options, numbers=True):
    """The option the person meant, or None when it's unclear. options: short names in the order they were offered.
    numbers: accept "the second one"; off when reading the original question ("assignment 2" isn't a choice)."""
    words = _words(text)
    if not words or not options:
        return None
    for word in words if numbers else ():  # "the second one"
        if word in NUMBERS and NUMBERS[word] <= len(options) and len(words) <= 2:
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


def find(hwnd, spec, chosen=""):
    """Rect (physical pixels) of the control a step points at, and False, or "above"/"below" when scrolled out of view.

    spec: "course" (the chosen course's tab), "link: <name>", "button: <name>" or "control: <name>" (a link, button
    or menu item; pages draw the same control differently). The control's name starts with <name>; "A|B" allows
    either, e.g. "control: Proceed|Submit"."""
    page = document(hwnd)
    if page is None:
        return None, False
    kind, _, name = spec.partition(":")
    kind, name = kind.strip().lower(), name.strip()
    if kind == "course":
        types, wanted = ("Hyperlink",), lambda text: text == chosen or text.startswith(chosen)
    else:
        types = {"link": ("Hyperlink",), "button": ("Button",), "control": ("Hyperlink", "Button", "MenuItem")}.get(kind)
        if not types or not name:
            return None, False
        pattern = re.compile(rf"^\s*(?:{'|'.join(re.escape(n.strip()) for n in name.split('|'))})\b", re.I)
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
            return rect, False  # first on screen, in reading order: the top bar before the page body
        best = best or (rect, "above" if r.bottom <= view.top else "below")
    return best or (None, False)


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

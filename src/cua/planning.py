"""Small search-only state machine. Model output cannot expand this capability."""
from dataclasses import dataclass
import re
from urllib.parse import urlencode
from .config import UserError


@dataclass(frozen=True)
class SearchTask:
    query: str
    engine: str

    @property
    def home(self):
        return {"bing": "https://www.bing.com/", "google": "https://www.google.com/", "duckduckgo": "https://duckduckgo.com/"}[self.engine]

    @property
    def url(self):
        return self.home + ("search?" if self.engine != "duckduckgo" else "?") + urlencode({"q": self.query})


def parse_task(text: str, engine: str) -> SearchTask:
    # Explicit grammar makes requests outside search fail closed. The query itself
    # remains inert data; it is URL encoded and is never interpreted as instructions.
    match = re.fullmatch(r"\s*(?:please\s+)?(?:(?:open|launch)\s+(?:my |the |a )?browser\s+and\s+)?(?:search(?:\s+(?:the web|online))?\s+for|look\s+up|google)\s+(.+?)\s*", text, re.I)
    if not match:
        raise UserError('I can search the web. Try "Search for accessible computer interfaces".')
    query = match.group(1).strip().strip('"')
    if not 1 <= len(query) <= 300 or any(ord(c) < 32 for c in query):
        raise UserError("Use a search topic between 1 and 300 characters, on one line.")
    if re.search(r"\b(?:and then|then)\s+(?:send|buy|delete|purchase|log|change|open|click)\b", query, re.I):
        raise UserError("I can only display search results. Please request one search topic.")
    return SearchTask(query, engine)


@dataclass(frozen=True)
class HelpQuestion:
    question: str


HELP_START = re.compile(r"\s*(?:please\s+)?(?:how\s+(?:do|can|to|would|should)\b|how\b|where\s+(?:is|are|do|can)\b|what\s+(?:is|are|does)\b|help\s+me\b|can\s+(?:you|u)\s+(?:show|tell|explain)\s+(?:me\s+)?(?:how|where|what|why)\b|can\s+(?:you|u)\s+help\b|show\s+me\s+how\b|i\s+(?:can't|cannot|can not|want\s+to|need\s+to)\b|is\s+there\s+a\s+way\b)", re.I)


@dataclass(frozen=True)
class BrowserAction:
    """One of a fixed set of simple browser actions Klicky may do for the person."""
    action: str


# Spoken or typed requests, e.g. "open a new tab for me", "refresh it", "zoom in please". The whole request must be
# one short command: anything compound ("... and then ...") or unknown is never acted on.
SIZE_THING = r"(?:it|this|everything|things|the\s+(?:page|text|screen|words|font|letters|website|site)|text|words)"
ACTION_PATTERNS = [
    ("newtab", r"(?:open|make|start|add|give\s+me|create)\s+(?:a\s+new|another\s+new|a|another|new|one\s+more)\s+(?:tab|page)|new\s+tab"),
    ("reopen", r"re-?open\s+(?:the\s+|that\s+|my\s+|a\s+)?(?:closed\s+|last\s+)?(?:tab|page)(?:\s+(?:i|you)\s+(?:just\s+)?closed)?"
               r"|bring\s+(?:back\s+)?(?:it|the\s+tab|that\s+tab|the\s+closed\s+tab|my\s+tab)(?:\s+back)?|undo\s+close"),
    ("closetab", r"(?:close|cancel|shut)\s+(?:this|the|that|my|current)?\s*(?:tab|page)"),
    ("refresh", r"refresh|reload"),
    ("zoomreset", r"reset\s+(?:the\s+)?zoom|(?:make\s+it\s+|put\s+it\s+|back\s+to\s+|go\s+back\s+to\s+)?(?:normal|actual|original|regular)\s+size"
                  r"|zoom\s+(?:back\s+)?to\s+(?:normal|100(?:\s*%|\s+percent)?)"),
    ("back", r"go\s+back(?:\s+(?:a|one)\s+page)?(?:\s+to\s+the\s+(?:last|previous)\s+page)?|take\s+me\s+back"
             r"|go\s+to\s+the\s+(?:previous|last)\s+page|back\s+(?:a\s+|one\s+)?page|previous\s+page"),
    ("forward", r"go\s+forward(?:\s+(?:a|one)\s+page)?|go\s+to\s+the\s+next\s+page|forward\s+(?:a\s+|one\s+)?page|next\s+page"),
    ("zoomin", rf"zoom\s+in|(?:make|making)\s+(?:{SIZE_THING}\s+)?(?:bigger|larger)|(?:increase|raise)\s+(?:the\s+)?(?:zoom|text\s+size|font\s+size|size)"
               r"|bigger|larger|enlarge"),
    ("zoomout", rf"zoom\s+out|(?:make|making)\s+(?:{SIZE_THING}\s+)?smaller|(?:decrease|reduce|lower)\s+(?:the\s+)?(?:zoom|text\s+size|font\s+size|size)"
                r"|smaller"),
    ("bookmark", r"(?:bookmark|favou?rite|save)\s+(?:this|the|that|it)(?:\s+(?:page|site|tab|website))?"
                 r"|add\s+(?:this|it|the|that)(?:\s+(?:page|site|tab|website))?\s+to\s+(?:my\s+)?(?:favou?rites|bookmarks)"),
    ("history", r"(?:open|show)\s+(?:me\s+)?(?:my\s+|the\s+)?(?:browsing\s+)?history"),
    ("settings", r"(?:open|show)\s+(?:me\s+)?(?:the\s+|my\s+)?(?:browser\s+)?settings"),
    ("extensions", r"(?:open|show)\s+(?:me\s+)?(?:my\s+|the\s+)?(?:extensions|add-?ons)"),
]
COURTESY = (r"(?:(?:hey\s+)?klicky[,\s]+)?"
            r"(?:(?:please|kindly|just|can\s+(?:you|u)|could\s+(?:you|u)|would\s+you|will\s+you|i\s+want\s+you\s+to|i'?d\s+like\s+you\s+to)\s+)*")
TAIL = (r"(?:\s+(?:the|this|that|my|current|whole))?(?:\s+(?:page|screen|it|this|browser|tab|website|site|one))?"
        r"(?:\s+(?:a\s+bit|a\s+little|a\s+bit\s+more|a\s+little\s+more|more|again|now|quickly))?"
        r"(?:\s+for\s+me)?(?:\s+please)?[\s.!?]*")


def parse_action(text: str):
    """A short command naming exactly one allowed action, or None."""
    words = " ".join(text.lower().split())
    if not words or len(words) > 80 or re.search(r"\b(?:and|then|also|after)\b", words):
        return None
    for name, pattern in ACTION_PATTERNS:
        if re.fullmatch(rf"\s*{COURTESY}(?:{pattern}){TAIL}", words):
            return BrowserAction(name)
    return None


def route(text: str, engine: str):
    """Deterministic routing; no model decides which capability runs."""
    try:
        return parse_task(text, engine)
    except UserError:
        pass
    question = " ".join(text.split())
    if not HELP_START.match(question):
        action = parse_action(question)
        if action:
            return action
    if HELP_START.match(question) or question.endswith("?"):
        if not 3 <= len(question) <= 500:
            raise UserError("Ask one question of up to 500 characters.")
        return HelpQuestion(question)
    raise UserError('Try "Search for accessible computer interfaces" or ask "How do I make text bigger in Edge?"')


@dataclass(frozen=True)
class Action:
    kind: str
    text: str = ""
    keys: tuple[str, ...] = ()
    x: float | None = None
    y: float | None = None
    amount: int = 0
    seconds: float = 1


def expected_action(stage: int, task: SearchTask) -> Action:
    return (Action("hotkey", keys=("ctrl", "l")), Action("type_text", text=task.url),
            Action("press_key", keys=("enter",)), Action("finish_task"))[stage]


def enforce_policy(action: Action, stage: int, task: SearchTask):
    if action.kind in {"wait", "capture_screen", "request_user_help"}:
        return
    if action != expected_action(stage, task):
        raise UserError("The suggested action is outside this search step. No action was performed.")

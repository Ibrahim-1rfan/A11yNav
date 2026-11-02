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


HELP_START = re.compile(r"\s*(?:please\s+)?(?:how\s+(?:do|can|to|would|should)\b|how\b|where\s+(?:is|are|do|can)\b|what\s+(?:is|are|does)\b|help\s+me\b|can\s+you\s+(?:show|tell|explain)\b|show\s+me\s+how\b|i\s+(?:can't|cannot|can not|want\s+to|need\s+to)\b|is\s+there\s+a\s+way\b)", re.I)


def route(text: str, engine: str):
    """Deterministic routing; no model decides which capability runs."""
    try:
        return parse_task(text, engine)
    except UserError:
        pass
    question = " ".join(text.split())
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

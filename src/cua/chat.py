"""Talking with Klicky when a question isn't a how-to: "hey Klicky, how are you?", "thanks", "what can you do?".

Small talk is caught before the guides are searched (otherwise "what's up" matched the profile guide). Questions no
guide answers are also sent here. The reply comes from the first service with a key in keys.env (OpenRouter, then
Anthropic, then a local LM Studio answer model), with the last few turns so a follow-up makes sense. Only what the
person said and Klicky's replies are sent, never the page. Klicky is told never to make up browser or LMS steps:
those come only from the checked guides. Without a service, or with chat off in Settings, short built-in replies are used.
"""
import os
import re
import threading
import time

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "anthropic/claude-haiku-5.5"
CLAUDE_MODEL = "claude-haiku-5-5"
TIMEOUT_S = 15
MAX_WORDS = 60        # replies are read aloud; longer ones are cut at a sentence
TURNS = 6             # messages remembered (3 back-and-forths)
FORGET_AFTER_S = 600  # a new conversation after 10 quiet minutes
SYSTEM = ("You are Klicky, a friendly voice companion on a Windows PC that helps students, many with disabilities, use "
          "their web browser and the IBA LMS (Sakai). Talk like a warm, relaxed friend: short and natural, one to three "
          "sentences, under 50 words, because your reply is read aloud. No lists, no markdown, no emoji. "
          "You can chat about anything and answer general questions briefly. "
          "Never give step-by-step instructions for the browser or the LMS and never make up menus, buttons or "
          "shortcuts: those come only from Klicky's checked guides. If someone asks how to do something you have no "
          "guide for, say so kindly and mention what you can help with: zoom, reading mode, read aloud, dark mode, "
          "captions, tabs, bookmarks and history in Edge, Chrome and Firefox, and course outlines, resources, "
          "assignments, quizzes, announcements and the Drop Box on the LMS. Never ask for passwords or personal details.")

# A name at the start ("hey Klicky,") doesn't change what was asked.
_CALL = r"^(?:(?:hey|hi|hello|ok|okay|yo|oi)\s+)?(?:klicky|clicky|clickey|klickey)\b[\s,.!?]*"
_SMALL_TALK = re.compile(r"""^(?:
    (?:hey|hi|hello|hiya|howdy|yo|sup|hey\ there|hi\ there|good\ (?:morning|afternoon|evening|night)|salam|assalam\w*|aoa)
  | how\s+(?:are|r)\s+(?:you|u|ya)(?:\s+doing)?(?:\s+today)?
  | how(?:'?s|\s+is)\s+(?:it\s+going|everything|life|your\s+day|things)
  | how\s+(?:have\s+you\s+been|you\s+doing|do\s+you\s+do)
  | what(?:'?s|\s+is)\s+up | wh?a?(?:ss|z)up | wassup | what'?s\s+new | how'?s\s+up
  | (?:thanks|thank\s+you|thank\s+u|thx|ty|cheers|great|nice|cool|awesome|perfect|ok|okay|got\s+it)(?:\s+(?:so\s+much|a\s+lot|klicky|man|dude|bro))*
  | (?:bye|goodbye|see\s+you|see\s+ya|good\s+night|later)
  | who\s+are\s+you | what\s+are\s+you | what(?:'?s|\s+is)\s+your\s+name | who\s+made\s+you | who\s+built\s+you
  | what\s+can\s+you\s+do | what\s+do\s+you\s+do | how\s+can\s+you\s+help(?:\s+me)? | can\s+you\s+help(?:\s+me)?
  | are\s+you\s+(?:there|listening|awake|real|a\s+robot|an?\s+ai)
  | tell\s+me\s+(?:a\s+joke|something|about\s+yourself) | i'?m\s+(?:bored|tired|sad|happy|good|fine|great|ok|okay|stressed)
)(?:[\s,.!?]+(?:klicky|clicky|man|dude|bro|buddy|there|today|then))*[\s,.!?]*$""", re.I | re.X)

CANNED = {
    "greet": "Hey! I'm doing well, thanks for asking. What would you like to do in your browser or on the LMS?",
    "thanks": "You're welcome! Ask me anytime.",
    "bye": "See you later! Press the shortcut whenever you need me.",
    "who": ("I'm Klicky, your browser and LMS helper. Ask me how to do something, like submitting an assignment or "
            "making text bigger, and I'll point you to it step by step."),
}


def strip_call(question):
    return re.sub(_CALL, "", question.strip(), flags=re.I).strip()


def is_small_talk(question):
    """Greetings, how-are-yous, thanks, goodbyes and "who are you": not a question for the guides."""
    rest = strip_call(question)
    return not rest or bool(_SMALL_TALK.match(rest))


def canned(question):
    rest = strip_call(question).lower()
    if re.match(r"(thanks|thank|thx|ty\b|cheers)", rest):
        return CANNED["thanks"]
    if re.match(r"(bye|goodbye|see\s+y|later|good\s+night)", rest):
        return CANNED["bye"]
    if re.match(r"(who|what\s+are|what'?s\s+your|what\s+(can|do)\s+you|how\s+can\s+you|can\s+you\s+help|tell\s+me\s+about)", rest):
        return CANNED["who"]
    return CANNED["greet"]


def shorten(text, words=MAX_WORDS):
    text = " ".join(re.sub(r"[*_#`]+", "", text or "").split())
    parts = text.split()
    if len(parts) <= words:
        return text
    cut = " ".join(parts[:words])
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    return cut[:end + 1] if end > len(cut) // 3 else cut.rstrip(",;:") + "..."


class History:
    """The last few turns, forgotten after a quiet spell."""
    def __init__(self, clock=time.monotonic):
        self.clock, self.messages, self.last, self.lock = clock, [], 0.0, threading.Lock()

    def recent(self):
        with self.lock:
            if self.clock() - self.last > FORGET_AFTER_S:
                self.messages = []
            return list(self.messages)

    def add(self, question, reply):
        with self.lock:
            self.messages = (self.messages + [{"role": "user", "content": question}, {"role": "assistant", "content": reply}])[-TURNS:]
            self.last = self.clock()


HISTORY = History()


def ask_openrouter(messages, post=None):
    import requests
    body = {"model": OPENROUTER_MODEL, "temperature": 0.7, "max_tokens": 160, "stream": False,
            "messages": [{"role": "system", "content": SYSTEM}] + messages}
    headers = {"Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY', '')}"}
    response = (post or requests.post)(OPENROUTER_URL, json=body, headers=headers, timeout=TIMEOUT_S, allow_redirects=False)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def ask_claude(messages, client=None):
    import anthropic
    client = client or anthropic.Anthropic(timeout=TIMEOUT_S, max_retries=1)
    response = client.messages.create(model=CLAUDE_MODEL, max_tokens=250, system=SYSTEM, output_config={"effort": "low"},
                                      messages=messages)
    if response.stop_reason == "refusal":
        return ""
    return next((b.text for b in response.content if b.type == "text"), "")


def ask_local(messages, settings):
    from .models import local_request
    body = {"model": settings.text_model, "temperature": 0.7, "max_tokens": 160, "stream": False,
            "messages": [{"role": "system", "content": SYSTEM}] + messages}
    return local_request(settings, "/chat/completions", body)["choices"][0]["message"]["content"]


def reply(question, settings, small_talk=True, history=None, post=None, client=None):
    """What Klicky says back. Never raises. "" when it has nothing better than the no-guide message."""
    history = history or HISTORY
    question = " ".join(question.split())
    said = ""
    if getattr(settings, "chat", True):
        messages = history.recent() + [{"role": "user", "content": question}]
        try:
            if os.environ.get("OPENROUTER_API_KEY"):
                said = ask_openrouter(messages, post)
            elif os.environ.get("ANTHROPIC_API_KEY"):
                said = ask_claude(messages, client)
            elif getattr(settings, "text_model", ""):
                said = ask_local(messages, settings)
        except Exception:
            said = ""
    said = shorten(said) or (canned(question) if small_talk else "")
    if said:
        history.add(question, said)
    return said

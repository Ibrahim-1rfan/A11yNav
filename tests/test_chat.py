"""Talking with Klicky: what counts as small talk, which service is asked, what is sent and remembered."""
from cua import chat
from cua.config import Settings


class Reply:
    def __init__(self, content, status=200):
        self.content, self.status = content, status
    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(self.status)
    def json(self):
        return {"choices": [{"message": {"content": self.content}}]}


def test_small_talk_is_told_apart_from_how_to_questions():
    for said in ["hey klicky how are you", "Hi Clicky!", "what's up", "wassup dude", "how is everything", "how's it going?",
                 "thank you so much", "bye", "who are you?", "what can you do", "I'm bored", "tell me a joke", "klicky"]:
        assert chat.is_small_talk(said), said
    for said in ["how do I zoom in", "hey klicky how do I submit my assignment", "show me the syllabus", "open a new tab",
                 "what is up with my quiz", "thanks, now how do I print"]:
        assert not chat.is_small_talk(said), said


def test_without_a_service_or_with_chat_off_built_in_replies_are_used_and_nothing_is_sent(monkeypatch):
    sent = []
    post = lambda url, **kw: sent.append(url)
    assert "doing well" in chat.reply("hey klicky how are you", Settings(), post=post, history=chat.History())
    assert chat.reply("thanks!", Settings(), post=post, history=chat.History()) == chat.CANNED["thanks"]
    assert chat.reply("what is the capital of France", Settings(), small_talk=False, post=post, history=chat.History()) == ""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    assert chat.reply("who are you", Settings(chat=False), post=post, history=chat.History()) == chat.CANNED["who"]
    assert sent == []


def test_openrouter_gets_the_conversation_and_never_invented_steps_are_asked_for(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    sent, history = [], chat.History()
    post = lambda url, **kw: (sent.append((url, kw)), Reply("**All good** here! How can I help?"))[1]
    assert chat.reply("hey klicky  how are you", Settings(), post=post, history=history) == "All good here! How can I help?"
    chat.reply("nice, and you?", Settings(), post=post, history=history)
    url, kw = sent[-1]
    assert url == chat.OPENROUTER_URL and kw["json"]["model"] == "anthropic/claude-haiku-5.5" and kw["allow_redirects"] is False
    system, *messages = kw["json"]["messages"]
    assert "Never give step-by-step instructions" in system["content"]
    assert [m["content"] for m in messages] == ["hey klicky how are you", "All good here! How can I help?", "nice, and you?"]


def test_a_failed_call_falls_back_and_never_raises(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    def boom(url, **kw):
        raise TimeoutError()
    assert chat.reply("hi", Settings(), post=boom, history=chat.History()) == chat.CANNED["greet"]
    assert chat.reply("why is the sky blue", Settings(), small_talk=False, post=lambda u, **k: Reply("", 500), history=chat.History()) == ""


def test_history_keeps_the_last_turns_and_forgets_after_a_quiet_spell():
    now = [0.0]
    history = chat.History(clock=lambda: now[0])
    for n in range(5):
        history.add(f"q{n}", f"a{n}")
    assert len(history.recent()) == chat.TURNS and history.recent()[-1]["content"] == "a4"
    now[0] += chat.FORGET_AFTER_S + 1
    assert history.recent() == []


def test_long_replies_are_cut_for_reading_aloud():
    long = "This is a sentence. " * 40
    assert len(chat.shorten(long).split()) <= chat.MAX_WORDS

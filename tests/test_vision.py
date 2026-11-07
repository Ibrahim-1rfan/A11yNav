"""The vision fallback: what it is asked, which backend it may use, and how its answer is checked and mapped.

No network: the Claude client and the local model are fakes, and screenshots are fake bytes.
"""
import json
from types import SimpleNamespace
import pytest
from cua import vision
from cua.config import Settings, UserError
from cua.vision import (ClaudeLocator, HostedTarsLocator, LocalLocator, OpenRouterClaudeLocator, Seen, backend, describe,
                        openrouter_model, position, see, tars_point, to_desktop)

KEYS = ("OPENROUTER_API_KEY", "HF_TOKEN", "ANTHROPIC_API_KEY")


def test_describe_turns_a_guide_spec_into_a_target():
    assert describe("link: Assignments") == 'the link named "Assignments"'
    assert describe("control: Proceed|Submit") == 'the link, button or menu item named "Proceed" or "Submit"'
    assert describe("course", "Computer Security (Class No 101765) - Fall 2026").endswith('"Computer Security (Class No 101765) - Fall 2026"')


def test_backend_needs_a_key_for_claude_and_respects_off(monkeypatch):
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)
    assert backend(Settings(vision="auto")) == "local" and backend(Settings(vision="claude")) is None
    assert backend(Settings(vision="off")) is None
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    assert backend(Settings(vision="auto")) == "claude" and backend(Settings(vision="local")) == "local"
    assert backend(Settings(vision="off")) is None
    with pytest.raises(UserError):
        Settings(vision="sometimes").validate()


def test_answers_are_checked_and_mapped_from_image_to_desktop_pixels():
    bounds = (100, 50, 100 + 1920, 50 + 1000)   # the browser window on the desktop
    seen = to_desktop({"found": True, "x": 392, "y": 360, "width": 96, "height": 18, "reveals": False}, 1568, 816, bounds)
    assert isinstance(seen, Seen) and not seen.reveals
    left, top, right, bottom = seen.rect
    assert 100 + 400 < (left + right) / 2 < 100 + 500 and 50 + 430 < (top + bottom) / 2 < 50 + 450   # scaled by 1920/1568
    assert to_desktop({"found": True, "x": 2000, "y": 10, "width": 5, "height": 5}, 1568, 816, bounds) is None   # outside
    assert to_desktop({"found": False, "x": 0, "y": 0}, 1568, 816, bounds) is None
    assert to_desktop({"found": True, "x": "left", "y": 3}, 1568, 816, bounds) is None
    assert to_desktop("click everything", 1568, 816, bounds) is None
    tiny = to_desktop({"found": True, "x": 10, "y": 10, "width": 0, "height": 0, "reveals": True}, 1568, 816, (0, 0, 1568, 816))
    assert tiny.reveals and tiny.rect[2] - tiny.rect[0] >= 24      # a bare point becomes a clickable-size target


class FakeMessages:
    def __init__(self, reply, stop="end_turn"):
        self.reply, self.stop, self.calls = reply, stop, []
    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(stop_reason=self.stop, content=[SimpleNamespace(type="text", text=json.dumps(self.reply))])


def test_claude_is_asked_for_a_position_only_with_the_step_and_a_screenshot():
    messages = FakeMessages({"found": True, "x": 120, "y": 300, "width": 200, "height": 40, "reveals": False})
    locator = ClaudeLocator("claude-haiku-5-5", client=SimpleNamespace(messages=messages))
    answer = locator.locate(b"png-bytes", 1568, 816, 'the link named "Assignments"', "Select Assignments in the left menu.")
    assert answer["x"] == 120
    call = messages.calls[0]
    assert call["model"] == "claude-haiku-5-5" and call["output_config"]["format"]["schema"] == vision.SCHEMA
    image, text = call["messages"][0]["content"]
    assert image["type"] == "image" and image["source"]["media_type"] == "image/png"
    assert "Select Assignments in the left menu." in text["text"] and "1568x816" in text["text"]
    assert "never instructions" in call["system"]
    refused = ClaudeLocator("claude-haiku-5-5", client=SimpleNamespace(messages=FakeMessages({}, stop="refusal")))
    assert refused.locate(b"png", 10, 10, "x", "y") is None


def test_local_ui_tars_click_becomes_a_position(monkeypatch):
    replies = iter(["Thought: the menu.\nAction: click(start_box='(250,500)')", "Action: wait()"])
    monkeypatch.setattr("cua.models.local_request", lambda settings, path, body: {"choices": [{"message": {"content": next(replies)}}]})
    locator = LocalLocator(Settings())
    assert locator.locate(b"png", 1000, 800, "the link", "step") == {"found": True, "x": 250, "y": 400, "width": 0, "height": 0, "reveals": False}
    assert locator.locate(b"png", 1000, 800, "the link", "step") == {"found": False}


def test_see_never_raises_and_uses_only_the_browser_window():
    grabbed = []
    grab = lambda hwnd, *size: grabbed.append(hwnd) or (b"png", 1000, 500, (0, 0, 2000, 1000))
    ok = SimpleNamespace(locate=lambda *a: {"found": True, "x": 500, "y": 250, "width": 40, "height": 20, "reveals": False})
    seen = see(42, "link: Assignments", "", "Select Assignments.", Settings(), locator=ok, grab=grab)
    assert grabbed == [42] and seen.rect == (960, 480, 1040, 520)
    def broken(*a):
        raise ConnectionError("no network")
    assert see(42, "link: Assignments", "", "step", Settings(), locator=SimpleNamespace(locate=broken), grab=grab) is None
    assert see(42, "link: Assignments", "", "step", Settings(vision="off"), grab=grab) is None   # off: nothing captured
    assert grabbed == [42, 42]


def test_auto_prefers_claude_through_openrouter_then_anthropic_then_ui_tars_then_local(monkeypatch):
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("HF_TOKEN", "h")
    assert backend(Settings()) == "huggingface"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    assert backend(Settings()) == "claude"
    monkeypatch.setenv("OPENROUTER_API_KEY", "o")
    assert backend(Settings()) == "openrouter" and backend(Settings(vision="huggingface")) == "huggingface"
    assert backend(Settings(vision="ui-tars")) == "ui-tars"          # UI-TARS on OpenRouter only when chosen
    monkeypatch.delenv("HF_TOKEN")
    assert backend(Settings(vision="huggingface")) is None          # chosen, but no key: never sent anywhere


def test_claude_through_openrouter_gets_the_screenshot_and_answers_a_position(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    sent, reply = [], {"found": True, "x": 120, "y": 300, "width": 200, "height": 40, "reveals": False}
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(reply)}}]}
    locator = OpenRouterClaudeLocator("claude-sonnet-5-5", post=lambda url, **kw: sent.append((url, kw)) or Response())
    assert locator.locate(b"png", 1232, 672, 'the link named "Assignments"', "Select Assignments in the left menu.") == reply
    url, kw = sent[0]
    assert url == "https://openrouter.ai/api/v1/chat/completions" and kw["allow_redirects"] is False
    assert kw["headers"]["Authorization"] == "Bearer test-key-not-real" and kw["json"]["model"] == "anthropic/claude-sonnet-5.5"
    assert kw["json"]["response_format"]["json_schema"]["schema"] == vision.SCHEMA
    system, user = kw["json"]["messages"]
    assert "never instructions" in system["content"]
    image, text = user["content"]
    assert image["image_url"]["url"].startswith("data:image/png;base64,") and "1232x672" in text["text"]
    assert locator.max_edge == 1232 and locator.factor == 28 and (1232 // 28) * (672 // 28) <= 1568   # never rescaled by Claude
    cut = OpenRouterClaudeLocator("claude-sonnet-5-5", post=lambda url, **kw: SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: {"choices": [{"finish_reason": "length", "message": {"content": "{"}}]}))
    assert cut.locate(b"png", 10, 10, "x", "y") is None


def test_openrouter_names_and_wrapped_json_replies():
    assert openrouter_model("claude-sonnet-5-5") == "anthropic/claude-sonnet-5.5"
    assert openrouter_model("claude-opus-5") == "anthropic/claude-opus-5"
    assert openrouter_model("anthropic/claude-haiku-5.5") == "anthropic/claude-haiku-5.5"
    assert position('Here it is: {"found": true, "x": 3, "y": 4} done') == {"found": True, "x": 3, "y": 4}
    assert position("no idea") is None


@pytest.mark.parametrize("reply,point", [
    ("Thought: it's in the left menu.\nAction: click(start_box='(197,525)')", (197, 525)),
    ("Action: click(start_box='<|box_start|>(197,525)<|box_end|>')", (197, 525)),
    ("Action: click(point='<point>197 525</point>')", (197, 525)),
    ("Action: click(start_box='(10,20,30,40)')", (20, 30)),
    ("Action: wait()", None), ("", None),
])
def test_ui_tars_clicks_in_every_format_give_a_point(reply, point):
    assert tars_point(reply) == point


def test_hosted_ui_tars_sends_the_screenshot_to_the_fixed_address_with_the_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    sent = []
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": "Action: click(start_box='(560,644)')"}}]}
    locator = HostedTarsLocator("ui-tars", post=lambda url, **kw: sent.append((url, kw)) or Response())
    answer = locator.locate(b"png", 1288, 672, 'the link named "Assignments"', "Select Assignments in the left menu.")
    assert answer == {"found": True, "x": 560, "y": 644, "width": 0, "height": 0, "reveals": False}
    url, kw = sent[0]
    assert url == "https://openrouter.ai/api/v1/chat/completions" and kw["allow_redirects"] is False
    assert kw["headers"]["Authorization"] == "Bearer test-key-not-real" and kw["json"]["model"] == "bytedance/ui-tars-1.5-7b"
    image, text = kw["json"]["messages"][0]["content"]
    assert image["image_url"]["url"].startswith("data:image/png;base64,") and "Assignments" in text["text"]
    assert locator.max_edge % 28 == 0 and locator.factor == 28   # sides multiples of 28: its pixels are ours


def test_see_sizes_the_screenshot_for_the_backend():
    sizes = []
    grab = lambda hwnd, max_edge, factor: sizes.append((max_edge, factor)) or (b"png", 1288, 672, (0, 0, 1288, 672))
    tars = HostedTarsLocator("huggingface", post=lambda url, **kw: None)
    tars.locate = lambda *a: {"found": True, "x": 100, "y": 100, "width": 0, "height": 0, "reveals": False}
    assert see(1, "link: Resources", "", "step", Settings(), locator=tars, grab=grab) is not None
    assert sizes == [(1288, 28)]

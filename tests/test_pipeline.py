"""Mocked integration tests; these do not establish real desktop/model success."""
from dataclasses import replace
import threading
from PIL import Image
import pytest
from cua.controller import Controller
from cua.config import Settings, UserError
from cua.planning import SearchTask, expected_action, Action
from cua.perception import preprocess


class Browser:
    def __init__(self): self.value=""; self.focus=False; self.calls=[]
    def open(self,home,stop): self.value=home; self.calls.append("open")
    def guard(self): pass
    def bounds(self): return (0,0,800,600)
    def focus_address(self,stop): self.focus=True; self.calls.append("focus")
    def set_address(self,text,stop): self.value=text; self.calls.append("type")
    def submit(self,expected,stop): self.calls.append("submit")
    def address_focused(self): return self.focus
    def address_value(self): return self.value


class Capture:
    def __init__(self): self.count=0
    def capture(self,bounds,edge):
        self.count+=1
        return preprocess(Image.new("RGB",(800,600)),bounds,edge)


class Model:
    def __init__(self,actions): self.actions=iter(actions); self.calls=0
    def health(self,stop): pass
    def propose(self,*args):
        self.calls+=1
        action=next(self.actions)
        if isinstance(action,Exception): raise action
        return action


def run(actions, **changes):
    browser, capture, events = Browser(),Capture(),[]
    model=Model(actions)
    settings=replace(Settings(),settle_seconds=.1,**changes)
    result=Controller(settings,model,capture,browser,lambda *e: events.append(e)).run("Search for cats",threading.Event())
    return result,browser,capture,events,model


def test_success_observes_after_each_action():
    task=SearchTask("cats","bing")
    result,browser,capture,events,model=run([expected_action(i,task) for i in range(4)])
    assert result == "success"
    assert browser.calls == ["open","focus","type","submit"]
    assert capture.count == 7
    assert events[-1][0] == "success"


def test_model_cannot_finish_early():
    result,browser,_,events,model=run([Action("finish_task")]*4)
    assert result == "error" and browser.calls == ["open"] and model.calls == 3
    assert all(e[0] != "success" for e in events)


def test_invalid_reply_retry_is_bounded():
    result,browser,_,_,model=run([UserError("Invalid")]*4,max_retries=1)
    assert result == "error" and model.calls == 2 and browser.calls == ["open"]


def test_transport_failure_is_not_retried():
    from cua.models import ModelTransportError
    result,browser,_,events,model=run([ModelTransportError("Model timed out")]*4)
    assert result == "error" and model.calls == 1 and browser.calls == ["open"]
    assert events[-1] == ("error", "Model timed out")


def test_expired_response_never_executes_or_retries(monkeypatch):
    import cua.controller as module
    clock=[0]
    monkeypatch.setattr(module.time,"monotonic",lambda:clock[0])
    model=Model([]); browser=Browser(); events=[]
    def propose(*args):
        clock[0]=1000
        return Action("hotkey",keys=("ctrl","l"))
    model.propose=propose
    result=Controller(replace(Settings(),settle_seconds=.1),model,Capture(),browser,lambda *e:events.append(e)).run("Search for cats",threading.Event())
    assert result == "error" and browser.calls == ["open"]
    assert "step 1/4" in events[-1][1]


def test_action_limit_counts_waits():
    result,_,_,events,model=run([Action("capture_screen")]*4,max_actions=3)
    assert result == "error" and model.calls == 3
    assert "action limit" in events[-1][1]


def test_health_failure_opens_nothing():
    browser=Browser(); events=[]
    model=Model([])
    model.health=lambda stop: (_ for _ in ()).throw(UserError("Server unavailable"))
    result=Controller(Settings(),model,Capture(),browser,lambda *e:events.append(e)).run("Search for cats",threading.Event())
    assert result == "error" and not browser.calls


def test_cancel_inflight_ignores_late_action():
    stop=threading.Event(); browser=Browser(); model=Model([])
    def propose(*args):
        stop.set()
        return Action("hotkey",keys=("ctrl","l"))
    model.propose=propose
    result=Controller(replace(Settings(),settle_seconds=.1),model,Capture(),browser,lambda *e:None).run("Search for cats",stop)
    assert result == "stopped" and browser.calls == ["open"]


def test_visual_finish_alone_is_not_success():
    task=SearchTask("cats","bing"); browser=Browser(); model=Model([expected_action(i,task) for i in range(4)])
    original=model.propose
    def propose(*args):
        action=original(*args)
        if action.kind == "finish_task": browser.value="https://evil.test"
        return action
    model.propose=propose
    result=Controller(replace(Settings(),settle_seconds=.1),model,Capture(),browser,lambda *e:None).run("Search for cats",threading.Event())
    assert result == "error"


def test_browser_missing():
    browser=Browser()
    browser.open=lambda *args: (_ for _ in ()).throw(UserError("No browser found"))
    model=Model([])
    assert Controller(Settings(),model,Capture(),browser,lambda *e:None).run("Search for cats",threading.Event()) == "error"


def test_task_deadline(monkeypatch):
    import cua.controller as module
    ticks=iter([0,1000])
    monkeypatch.setattr(module.time,"monotonic",lambda: next(ticks))
    browser=Browser()
    assert Controller(Settings(),Model([]),Capture(),browser,lambda *e:None).run("Search for cats",threading.Event()) == "error"
    assert not browser.calls

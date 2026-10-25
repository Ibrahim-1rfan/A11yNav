from dataclasses import replace
import json
import threading
import time
import pytest
from PIL import Image
from cua.config import Settings, UserError, load, save
from cua.planning import Action, SearchTask, parse_task, enforce_policy, expected_action
from cua.actions import validate_action, Executor
from cua.models import parse_response, bounded_call, Cancelled
from cua.perception import preprocess
from cua.verification import search_url_matches


def test_config_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    save(Settings(model="test"),path)
    assert load(path).model == "test"
    path.write_text('{"unknown":1}')
    with pytest.raises(UserError): load(path)


@pytest.mark.parametrize("patch", [{"endpoint":"https://example.com/v1"},{"endpoint":"http://localhost.evil/v1"},{"endpoint":"http://user@localhost/v1"},{"endpoint":"http://localhost/v1?x=1"},{"endpoint":"http://localhost:99999/v1"},{"max_actions":True},{"max_retries":4},{"request_timeout":float('nan')},{"font_px":10},{"adapter":"python"},{"speech":"yes"}])
def test_bad_config(patch):
    with pytest.raises(UserError): replace(Settings(),**patch).validate()


@pytest.mark.parametrize("text",["Search for accessible computer interfaces","Open my browser and search for accessible computer interfaces","Please look up accessible computer interfaces"])
def test_task(text):
    assert parse_task(text,"bing").query == "accessible computer interfaces"


@pytest.mark.parametrize("text",["delete my files","","search for " + "x"*301,"search for cats then buy food","search for cats\npassword"])
def test_task_rejected(text):
    with pytest.raises(UserError): parse_task(text,"bing")


def test_query_is_inert_encoded_data():
    task = parse_task("Search for cats & dogs اردو", "google")
    assert "&dogs" not in task.url and "%26" in task.url
    assert search_url_matches(task.url,task)
    assert not search_url_matches(task.url.replace("www.google.com","www.google.com.evil"),task)
    assert not search_url_matches(task.url.replace("https:","http:"),task)
    assert not search_url_matches("https://www.google.com/search?q=other",task)


def test_screenshot_mapping():
    frame = preprocess(Image.new("RGBA",(2000,1000)),(-2000,50,0,1050),1000)
    assert (frame.width,frame.height) == (1000,500)
    assert frame.desktop_point(0,0) == (-2000,50)
    assert frame.desktop_point(1,1) == (-1,1049)
    assert frame.data_url.startswith("data:image/png;base64,")
    with pytest.raises(UserError): frame.desktop_point(1.1,0)
    with pytest.raises(UserError): preprocess(Image.new("RGB",(1,1)),(0,0,2,2),640)


@pytest.mark.parametrize("reply,expected",[("Thought: Focus browser\nAction: hotkey(key='ctrl l')",Action("hotkey",keys=("ctrl","l"))), ("Action: hotkey(key='enter')",Action("press_key",keys=("enter",))), ("Action: type(content='abc')",Action("type_text",text="abc")),("Action: finished()",Action("finish_task")),("Action: click(start_box='(100, 200)')",Action("click",x=.1,y=.2))])
def test_tars_parser(reply,expected):
    assert parse_response(reply,"ui_tars") == expected


@pytest.mark.parametrize("reply",["__import__('os').system('whoami')","Action: click(start_box=run())","Action: finished(); print(1)","Action: hotkey(**evil)","Action: click(start_box='(1001,0)')","Action: finished(x=1)","Action: type(content='a',content='b')"])
def test_no_code_execution(reply):
    with pytest.raises(UserError): parse_response(reply,"ui_tars")


def test_json_parser():
    assert parse_response('{"kind":"hotkey","keys":["ctrl","l"]}',"json") == Action("hotkey",keys=("ctrl","l"))
    with pytest.raises(UserError): parse_response('{"kind":"wait","code":"evil"}',"json")


@pytest.mark.parametrize("action",[Action("shell"),Action("click",x=-.1,y=.2),Action("click",x=float('nan'),y=0),Action("click"),Action("hotkey",keys=("win","r")),Action("type_text",text="bad\n"),Action("wait",seconds=99),Action("scroll",amount=500)])
def test_invalid_actions(action):
    with pytest.raises(UserError): validate_action(action)


def test_policy_cannot_be_elevated():
    task = SearchTask("cats","bing")
    for stage in range(4): enforce_policy(expected_action(stage,task),stage,task)
    for action in [Action("click",x=.5,y=.5),Action("type_text",text="https://evil.test"),Action("finish_task")]:
        with pytest.raises(UserError): enforce_policy(action,0,task)


def test_bounded_timeout_and_cancellation():
    with pytest.raises(UserError): bounded_call(lambda: time.sleep(.3),threading.Event(),.05)
    stop=threading.Event()
    stop.set()
    with pytest.raises(Cancelled): bounded_call(lambda: "late",stop,1)


def test_expired_or_cancelled_request_does_not_start():
    from cua.models import ModelTransportError
    called=threading.Event()
    stop=threading.Event(); stop.set()
    with pytest.raises(Cancelled): bounded_call(called.set,stop,1)
    with pytest.raises(ModelTransportError): bounded_call(called.set,threading.Event(),0)
    assert not called.is_set()


def test_executor_checks_stop_before_input():
    class Browser:
        def guard(self): raise AssertionError("Must not interact after stop")
    stop=threading.Event(); stop.set()
    with pytest.raises(Cancelled): Executor(Browser()).execute(Action("hotkey",keys=("ctrl","l")),0,SearchTask("cats","bing"),stop)

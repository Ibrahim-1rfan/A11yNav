"""Real loopback HTTP contract with a fake inference server, not a real VLM."""
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import pytest
from PIL import Image
from cua.models import LocalModel
from cua.config import Settings,UserError
from cua.perception import preprocess


@pytest.fixture
def server():
    received=[]
    class Handler(BaseHTTPRequestHandler):
        status=200
        answer="Action: wait()"
        def log_message(self,*args): pass
        def do_GET(self): self.reply({"data":[{"id":"test"},{"id":"text"},{"id":"embed"}]})
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            received.append(body)
            if self.path.endswith("/embeddings"):
                self.reply({"data":[{"index":i,"embedding":[float(len(t)),1.0]} for i,t in reversed(list(enumerate(body["input"])))]})
            else:
                self.reply({"choices":[{"message":{"content":self.answer}}]})
        def reply(self,data):
            body=json.dumps(data).encode()
            self.send_response(self.status)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(body)))
            self.end_headers(); self.wfile.write(body)
    server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    yield LocalModel(replace(Settings(),endpoint=f"http://127.0.0.1:{server.server_port}/v1",model="test")),received,Handler
    server.shutdown(); server.server_close(); thread.join()


def test_real_http_image_contract(server):
    model,received,_=server
    assert model.health(threading.Event()) == ["test","text","embed"]
    frame=preprocess(Image.new("RGB",(800,600)),(0,0,800,600),640)
    assert model.propose(frame,"Wait",threading.Event(),5).kind == "wait"
    assert received[0]["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert received[0]["model"] == "test"


@pytest.mark.parametrize("status",[302,400,401,422,500,503])
def test_http_failure_never_succeeds(server,status):
    model,_,handler=server; handler.status=status
    with pytest.raises(UserError): model.health(threading.Event())


def test_wrong_model(server):
    model,_,_=server; model.settings=replace(model.settings,model="missing")
    with pytest.raises(UserError): model.health(threading.Event())


def text_client(model):
    from cua.models import LocalText
    return LocalText(replace(model.settings,text_model="text",embed_model="embed"))


def test_text_and_embedding_contract(server):
    model,received,handler=server
    client=text_client(model)
    assert "text" in client.health(threading.Event())
    handler.answer="1. Press Ctrl and F. [1]"
    assert client.complete("system","question",threading.Event()) == "1. Press Ctrl and F. [1]"
    assert received[-1]["model"] == "text" and received[-1]["messages"][0]["role"] == "system"
    vectors=client.embed(["a","bbb","cc"],threading.Event(),batch=2)
    assert vectors == [[1.0,1.0],[3.0,1.0],[2.0,1.0]]
    assert received[-1] == {"model":"embed","input":["cc"]}


def test_missing_text_model_is_reported(server):
    model,_,_=server
    client=text_client(model)
    client.settings=replace(client.settings,text_model="absent")
    with pytest.raises(UserError): client.health(threading.Event())

"""Explicit manual component test. Opens one search tab; no model is simulated.

Run only on an unlocked desktop prepared for browser control. Does NOT certify AI E2E.
"""
import sys
from pathlib import Path
import threading
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from cua.browser import WindowsBrowser,enable_dpi_awareness
from cua.actions import Executor
from cua.planning import SearchTask,expected_action
from cua.perception import ScreenCapture
from cua.verification import verify_step

enable_dpi_awareness()
stop=threading.Event()
browser=WindowsBrowser("edge")
task=SearchTask("accessible computer interfaces","bing")
browser.open(task.home,stop)
print("Browser foreground verified",flush=True)
time.sleep(2)
capture=ScreenCapture()
executor=Executor(browser)
for stage in range(3):
    frame=capture.capture(browser.bounds(),1280)
    print("Captured",frame.width,frame.height,flush=True)
    executor.execute(expected_action(stage,task),stage,task,stop)
    time.sleep(1)
    print("Step",stage,"verified",verify_step(stage,browser,task),flush=True)
time.sleep(2)
print("Search URL matches",verify_step(3,browser,task),flush=True)
print("Component smoke complete. No model inference or visual AI verification occurred.",flush=True)

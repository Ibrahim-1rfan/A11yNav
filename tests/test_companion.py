"""Companion cursor: follow feel, visibility rules, morph into the orb and placement. Desktop reads are faked."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import time
from types import SimpleNamespace
import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QApplication
from cua.companion import (IDLE_OPACITY, OFFSET, SETTLED_MS, SPEEDS, Companion, companion_opacity, follow_step)
from cua.config import Settings, UserError
from cua.morph import ORB_EDGE, PANEL_EDGE, orb_center, panel_rect

SCREEN = QRect(0, 0, 1920, 1040)


def run(frames, dt, speed=.18):
    x = 0.0
    for _ in range(frames):
        x = follow_step(x, 100.0, speed, dt)
    return x


def test_follow_feels_the_same_at_60_120_and_144_hz():
    at60, at120, at144 = run(30, 1 / 60), run(60, 1 / 120), run(72, 1 / 144)  # half a second each
    assert at60 == pytest.approx(at120, abs=1e-6) == pytest.approx(at144, abs=1e-6)
    assert follow_step(0, 100, .18, 1 / 60) == pytest.approx(18)  # 18% of the gap per 60 fps frame
    assert run(30, 1 / 60, SPEEDS["gentle"]) < at60 < run(30, 1 / 60, SPEEDS["snappy"])


@pytest.mark.parametrize("args,expected", [
    ((True, False, False, True, False, 0), 1.0),
    ((True, False, False, True, False, 5), IDLE_OPACITY),   # dims after 4 s without movement
    ((False, False, False, True, False, 0), 0.0),           # setting off
    ((True, True, False, True, False, 0), 0.0),             # orb open
    ((True, False, True, True, False, 0), 0.0),             # typing
    ((True, False, False, False, False, 0), 0.0),           # pointer left the browser / browser not in front
    ((True, False, False, True, True, 0), 0.0),             # fullscreen
])
def test_visibility_rules(args, expected):
    assert companion_opacity(*args) == expected


@pytest.mark.parametrize("anchor,side", [(QPoint(400, 500), "right"), (QPoint(1800, 500), "left")])
def test_card_sits_beside_the_orb_and_flips_near_the_right_edge(anchor, side):
    center = orb_center(anchor, SCREEN, 28)
    card = panel_rect(center, 320, 300, SCREEN)
    if side == "right":
        assert card.left() == center.x() + 40
    else:
        assert card.right() < center.x() - 39
    assert card.top() == center.y() - 30


@pytest.mark.parametrize("anchor", [QPoint(-50, -50), QPoint(5000, 5000), QPoint(0, 900), QPoint(1919, 3)])
def test_orb_and_card_stay_inside_all_four_edges(anchor):
    center = orb_center(anchor, SCREEN, 28)
    assert SCREEN.left() + ORB_EDGE + 28 <= center.x() <= SCREEN.right() - ORB_EDGE - 28
    assert SCREEN.top() + ORB_EDGE + 28 <= center.y() <= SCREEN.bottom() - ORB_EDGE - 28
    card = panel_rect(center, 320, 600, SCREEN)
    assert card.top() >= SCREEN.top() + PANEL_EDGE and card.bottom() <= SCREEN.bottom() - PANEL_EDGE + 1
    assert card.left() >= SCREEN.left() + PANEL_EDGE and card.right() <= SCREEN.right() - PANEL_EDGE + 1


def test_new_settings_validate():
    assert Settings().companion and Settings().click_ripple and Settings().companion_speed == "normal"
    from dataclasses import replace
    with pytest.raises(UserError):
        replace(Settings(), companion_speed="warp").validate()
    with pytest.raises(UserError):
        replace(Settings(), click_ripple="yes").validate()


class FakeDesktop:
    """Pointer inside a maximised Chrome window unless a test changes it."""
    def __init__(self):
        self.window, self.fullscreen, self.down, self.typing, self.input = (0, 0, 1920, 1040), False, False, False, 1
    def cursor(self): return (500, 400)
    def buttons(self): return self.down
    def key_down(self): return self.typing
    def last_input(self): return self.input
    def browser_window(self): return (self.window, self.fullscreen) if self.window else None


def make(monkeypatch, **settings):
    app = QApplication.instance() or QApplication([])
    position = {"p": QPoint(500, 400)}
    monkeypatch.setattr("cua.companion.QCursor.pos", lambda: position["p"])
    desk = FakeDesktop()
    s = Settings(**settings)
    companion = Companion(lambda: s, desktop=desk)
    companion.reduced = False
    return app, companion, desk, position


def advance(companion, frames=1, dt=1 / 60):
    for _ in range(frames):
        companion.last_tick -= dt
        companion.tick()


def test_first_appearance_snaps_then_fades_in_and_follows_lazily(monkeypatch):
    app, c, desk, pos = make(monkeypatch)
    advance(c)
    assert (c.x, c.y) == (500 + OFFSET[0], 400 + OFFSET[1])   # snapped, not flying in from 0,0
    assert 0 < c.opacity < .2                                  # fading in over 200 ms
    advance(c, 15)
    assert c.opacity == 1.0 and c.isVisible()
    pos["p"] = QPoint(700, 400)
    advance(c)
    assert 516 < c.x < 716 and c.x == pytest.approx(516 + 200 * .18, abs=.5)  # lags behind, catches up
    advance(c, 120)
    assert c.x == pytest.approx(716, abs=.1)


def test_settles_into_light_polling_when_idle_and_dims_after_4_seconds(monkeypatch):
    app, c, desk, pos = make(monkeypatch)
    advance(c, 40)
    assert c.timer.interval() == SETTLED_MS          # no full-rate loop on an idle page
    c.last_move -= 5
    advance(c, 20)
    assert c.opacity == pytest.approx(IDLE_OPACITY)
    pos["p"] = QPoint(510, 400)
    advance(c, 15)
    assert c.opacity == 1.0 and c.timer.interval() < SETTLED_MS


def test_hides_while_typing_in_fullscreen_and_outside_the_browser(monkeypatch):
    app, c, desk, pos = make(monkeypatch)
    advance(c, 20)
    desk.typing, desk.input = True, 2                # a key press without mouse movement
    advance(c, 20)
    assert c.opacity == 0 and not c.isVisible()
    desk.typing = False
    c.typing_until = 0
    advance(c, 20)
    assert c.opacity == 1.0
    desk.fullscreen = True
    c.context_at = 0
    advance(c, 20)
    assert c.opacity == 0
    desk.fullscreen, desk.window = False, None       # another app in front
    c.context_at = 0
    advance(c, 20)
    assert c.opacity == 0


def test_click_squishes_and_ripples_without_touching_the_click(monkeypatch):
    from cua.ripple import Ripple
    app, c, desk, pos = make(monkeypatch)
    advance(c, 20)
    desk.down, desk.input = True, 3
    advance(c)
    assert c.squish_started is not None and len(Ripple.live) >= 1
    advance(c, 6)
    assert c.scale < .9                               # squished toward the tip
    desk.down = False
    advance(c, 30)
    assert c.scale == 1.0 and c.squish_started is None
    deadline = time.monotonic() + 2
    while Ripple.live and time.monotonic() < deadline:
        app.processEvents(); time.sleep(.01)
    assert not Ripple.live                            # removed after 500 ms


def test_reduced_motion_has_no_lag_squish_or_ripple(monkeypatch):
    from cua.ripple import Ripple
    app, c, desk, pos = make(monkeypatch)
    c.reduced = True
    advance(c, 20)
    pos["p"] = QPoint(900, 300)
    advance(c)
    assert (c.x, c.y) == (916, 314)                   # moves exactly with the pointer
    before = len(Ripple.live)
    desk.down, desk.input = True, 4
    advance(c)
    assert c.squish_started is None and len(Ripple.live) == before


def test_morph_out_shrinks_away_and_reappears_at_the_pointer(monkeypatch):
    app, c, desk, pos = make(monkeypatch)
    advance(c, 20)
    c.morph_out()
    advance(c, 6)
    assert 0 < c.scale < 1 and 0 < c.opacity < 1      # shrinking and fading over 200 ms
    advance(c, 10)
    assert c.opacity == 0 and c.suppressed
    pos["p"] = QPoint(1200, 600)                      # the user moved while the orb was open
    c.reappear()
    advance(c)
    assert (c.x, c.y) == (1216, 614)                  # snaps to the pointer, never flies back
    advance(c, 15)
    assert c.opacity == 1.0


def test_hotkey_opens_the_orb_where_the_companion_is(monkeypatch):
    from cua.ui import MainWindow
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr("cua.dock.screen_reader_running", lambda: False)
    monkeypatch.setattr("cua.ui.foreground_app", lambda: (None, "chrome"))
    window = MainWindow(Settings(hotkey="", voice=False))
    companion = window.companion
    companion.timer.stop()
    companion.x, companion.y, companion.opacity = 600.0, 300.0, 1.0
    monkeypatch.setattr(companion, "isVisible", lambda: True)
    window.summon()
    dock = window.dock
    assert dock.anchor == QPoint(618, 318) and companion.suppressed       # centred at companion + 18 px
    assert dock.geometry().center().x() == pytest.approx(618, abs=1)
    dock.start_typing("x")
    area = dock.screen_area(dock.anchor)                                  # the 800 px offscreen test screen
    assert dock.panel.geometry() == panel_rect(dock.anchor, 320, dock.panel.height(), area)
    assert dock.panel.geometry().right() < 618 - 39                       # no room on the right: flipped left
    dock.escape()
    deadline = time.monotonic() + 2
    while dock.isVisible() and time.monotonic() < deadline:
        app.processEvents(); time.sleep(.01)
    assert not dock.isVisible() and not companion.suppressed              # companion comes back
    window.settings = Settings(hotkey="", voice=False, companion=False)
    monkeypatch.setattr(companion, "isVisible", lambda: False)
    monkeypatch.setattr("cua.ui.QCursor.pos", lambda: QPoint(400, 500))
    window.summon()
    assert dock.anchor == QPoint(400, 500)                                # companion off: opens at the pointer
    dock.close_dock()
    window.close()


def test_new_tab_steps_point_at_the_plus_button():
    from cua.highlighter import target_for
    assert target_for("Select New tab, the plus sign next to the last tab at the top of the window.") == "newtab"
    # Firefox's step also mentions the address bar; the plus sign is what the step is about.
    assert target_for("Select the plus sign on the right side of the last tab. The cursor appears in the address bar.") == "newtab"
    assert target_for("Or press Ctrl and T to open a new tab from the keyboard.") is None


def test_companion_flies_from_the_orb_to_the_control_and_points_at_it(monkeypatch):
    from cua.companion_asset import TIP
    app, c, desk, pos = make(monkeypatch)
    c.suppressed = True                               # the orb is open, so the companion is hidden
    advance(c, 20)
    assert c.opacity == 0
    orb, button = QPoint(600, 500), QPoint(860, 50)
    c.guide(orb, button)
    advance(c)
    assert c.opacity > 0 and abs(c.x + TIP[0] - 600) < 60 and abs(c.y + TIP[1] - 500) < 60  # starts at the orb
    advance(c, 10)
    assert 600 < c.x + TIP[0] < 860                  # visibly gliding, not teleporting
    advance(c, 120)
    assert (c.x + TIP[0], c.y + TIP[1]) == pytest.approx((860, 50), abs=.2)  # tip rests on the control
    pos["p"] = QPoint(100, 900)                       # the user's own mouse moving does not pull it away
    advance(c, 30)
    assert (c.x + TIP[0], c.y + TIP[1]) == pytest.approx((860, 50), abs=.2)
    c.stop_guide()
    advance(c, 20)
    assert c.opacity == 0                             # orb still open: back to hidden


def test_located_control_rings_it_and_sends_the_companion(monkeypatch):
    from cua.highlighter import Highlighter
    app = QApplication.instance() or QApplication([])
    located = []
    highlighter = Highlighter(located.append)
    highlighter.label_rings = False
    highlighter.show("newtab", (839, 0, 887, 62), None)
    assert located[-1] is not None and highlighter.overlay.isVisible() and highlighter.overlay.text == ""
    highlighter.clear()
    assert located[-1] is None and not highlighter.overlay.isVisible()


def test_dock_sends_the_companion_while_reading_and_recalls_it_on_close(monkeypatch):
    from cua.ui import MainWindow
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr("cua.dock.screen_reader_running", lambda: False)
    window = MainWindow(Settings(hotkey="", voice=False))
    window.companion.timer.stop()
    dock = window.dock
    dock.open_for("chrome", None, listen=False, anchor=QPoint(400, 400))
    dock.guide_companion(QRect(500, 10, 40, 40))
    assert window.companion.guiding == QPoint(519, 45)  # lower middle of the control (Qt rects are inclusive)
    dock.close_dock()
    assert window.companion.guiding is None
    window.settings = Settings(hotkey="", voice=False, companion=False)
    dock.open_for("chrome", None, listen=False, anchor=QPoint(400, 400))
    dock.guide_companion(QRect(500, 10, 40, 40))
    assert window.companion.guiding is None              # companion turned off: ring only
    dock.close_dock()
    window.close()


def test_prefetch_makes_pointing_instant_when_the_step_is_read(monkeypatch):
    from PySide6.QtCore import QThread, Signal
    import cua.highlighter as hl
    lookups = []

    class FakeLocator(QThread):
        found = Signal(str, object)
        def __init__(self, hwnd, target):
            super().__init__()
            self.target = target
            lookups.append(target)
        def run(self):
            self.found.emit(self.target, (839, 0, 887, 62))

    monkeypatch.setattr(hl, "ControlLocator", FakeLocator)
    monkeypatch.setattr(hl.ctypes.windll.user32, "IsIconic", lambda hwnd: False)
    app = QApplication.instance() or QApplication([])
    located = []
    highlighter = hl.Highlighter(located.append)
    step = "Select New tab, the plus sign next to the last tab at the top of the window."
    highlighter.prefetch([step, "Or press Ctrl and T."], 4242)
    deadline = time.monotonic() + 2
    while (4242, "newtab") not in highlighter.cache and time.monotonic() < deadline:
        app.processEvents(); time.sleep(.01)
    assert lookups == ["newtab"] and not located        # looked up early, nothing shown yet
    highlighter.point(step, 4242)
    assert located and located[-1] is not None           # shown at once from the cache, no second lookup
    assert lookups == ["newtab"]
    highlighter.clear()


def test_lookup_never_walks_into_the_web_page():
    from types import SimpleNamespace as N
    from cua.highlighter import browser_chrome
    visited = []
    def node(kind, name, kids=()):
        n = N(control_type=kind, name=name)
        n.children = lambda: (visited.append(name), list(kids))[1]
        return n
    page = node("Document", "page", [node("Button", "Back")])        # a page button that looks like the toolbar's
    root = node("Window", "root", [node("ToolBar", "bar", [node("Button", "Back"), node("Button", "Reload")]), page])
    names = [n.name for n in browser_chrome(root)]
    assert names == ["bar", "Back", "Reload"] and "page" not in visited


@pytest.mark.parametrize("selected,expected", [(1, True), (0, False)])
def test_only_the_current_tabs_close_button_counts(selected, expected):
    from types import SimpleNamespace as N
    from cua.highlighter import ControlLocator
    locator = ControlLocator(1, "closetab")
    control = N(parent=lambda: N(iface_selection_item=N(CurrentIsSelected=selected)))
    assert locator.on_current_tab(control) is expected
    assert ControlLocator(1, "back").on_current_tab(control) is True

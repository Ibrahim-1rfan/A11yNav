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

"""Companion <-> orb placement and easing. Pure geometry, so edge cases are easy to test."""
from PySide6.QtCore import QEasingCurve, QPoint, QPointF, QRect

ORB_EDGE = 16       # the orb stays at least this far inside the screen
PANEL_EDGE = 10     # the card stays at least this far inside the screen
PANEL_GAP = 40      # card starts this far to the side of the orb's centre
PANEL_RISE = 30     # card starts this far above the orb's centre


def overshoot():
    """cubic-bezier(0.34, 1.56, 0.64, 1): a small overshoot for the orb popping in."""
    curve = QEasingCurve(QEasingCurve.Type.BezierSpline)
    curve.addCubicBezierSegment(QPointF(.34, 1.56), QPointF(.64, 1), QPointF(1, 1))
    return curve


def orb_center(anchor, area, radius):
    """Keep the whole orb at least ORB_EDGE px inside the screen's available area."""
    margin = ORB_EDGE + radius
    x = min(max(anchor.x(), area.left() + margin), area.right() - margin)
    y = min(max(anchor.y(), area.top() + margin), area.bottom() - margin)
    return QPoint(x, y)


def panel_rect(center, width, height, area, gap=PANEL_GAP):
    """Card beside the orb: to the right by default, flipped left near the right edge, clamped top and bottom.
    gap: from the orb's centre to the card's edge (past the toggle under the orb)."""
    left = center.x() + gap
    if left + width > area.right() - PANEL_EDGE:
        left = center.x() - gap - width
    left = min(max(left, area.left() + PANEL_EDGE), area.right() - PANEL_EDGE - width)
    top = center.y() - PANEL_RISE
    top = min(max(top, area.top() + PANEL_EDGE), area.bottom() - PANEL_EDGE - height)
    return QRect(left, top, width, height)

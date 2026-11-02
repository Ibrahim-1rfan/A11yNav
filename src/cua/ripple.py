"""Click ripple: a 40 px teal ring that grows and fades at the click point, then removes itself."""
from PySide6.QtCore import QEasingCurve, QPointF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

TEAL = "#1D9E75"
DIAMETER, DURATION_MS = 40, 500


class Ripple(QWidget):
    live = set()  # keeps running ripples alive until they finish

    def __init__(self, point):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.WindowTransparentForInput | Qt.WindowType.WindowDoesNotAcceptFocus
                         | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        side = int(DIAMETER * 1.2) + 6
        self.setFixedSize(side, side)
        self.move(point.x() - side // 2, point.y() - side // 2)  # centred on the click
        self.progress = 0.0
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(DURATION_MS)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self.step)
        self.animation.finished.connect(self.done)
        Ripple.live.add(self)
        self.show()
        self.animation.start()

    def step(self, value):
        self.progress = value
        self.update()

    def done(self):
        Ripple.live.discard(self)
        self.hide()
        self.deleteLater()

    def paintEvent(self, event):
        scale = .2 + self.progress * 1.0          # 0.2 -> 1.2
        opacity = .9 * (1 - self.progress)        # 0.9 -> 0
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(TEAL)
        color.setAlphaF(opacity)
        painter.setPen(QPen(color, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        radius = DIAMETER / 2 * scale
        painter.drawEllipse(QPointF(self.width() / 2, self.height() / 2), radius, radius)

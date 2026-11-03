"""Speak / Type: one segmented control under the orb, so people who can't speak or hear can type instead.

One container, 190 x 46 px, 2 px border in the text colour, fully rounded, with a straight 2 px divider between its
two halves (each half draws its own border, so there's no notch where they meet). The chosen half is filled with the
text colour and its icon and label turn the surface colour. Screen readers get a group called "Input mode" with two
toggle buttons, "Voice" and "Typing", whose pressed state is the mode. Focus shows as a 3 px accent ring inside the
button. Both halves are 46 px tall, more than the 44 px minimum touch target.
"""
from PySide6.QtCore import QByteArray, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QButtonGroup, QGroupBox, QHBoxLayout, QPushButton

WIDTH, HEIGHT, BORDER, RADIUS = 190, 46, 2, 23
ICON_PX, LABEL_PX, ICON_GAP = 17, 14, 6
FOCUS_PX = 3
FOCUS = "#1D9E75"  # the theme's teal: at least 3:1 against both the chosen and the plain half, light and dark
ICONS = {  # 24-unit outline icons, drawn in the current colour
    "speak": ('<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v1a7 7 0 0 0 14 0v-1"/>'
              '<line x1="12" y1="18" x2="12" y2="22"/>'),
    "type": ('<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M6 9h.01M10 9h.01M14 9h.01M18 9h.01M6 13h.01'
             'M18 13h.01M10 13h4"/><line x1="7" y1="16" x2="17" y2="16"/>'),
}


def icon(name, color, px=ICON_PX):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2.2" '
           f'stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>')
    pixmap = QPixmap(px * 2, px * 2)  # drawn at twice the size, so it stays sharp on high-DPI screens
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode("utf-8"))).render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


class Half(QPushButton):
    """One half of the toggle; paints the inset focus ring itself (style sheets have no outline)."""
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.hasFocus():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor(FOCUS), FOCUS_PX))
            inset = BORDER + FOCUS_PX / 2
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(inset, inset, -inset, -inset), RADIUS - inset, RADIUS - inset)


class InputToggle(QGroupBox):
    changed = Signal(str)  # "speak" or "type", when the person picks a half

    def __init__(self, mode="speak"):
        super().__init__()
        self.setFlat(True)
        self.setAccessibleName("Input mode")
        self.setFixedSize(WIDTH, HEIGHT)
        self.colors = {"text": "#14231E", "surface": "#FFFFFF"}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = {}
        for key, label, name in (("speak", "Speak", "Voice"), ("type", "Type", "Typing")):
            button = Half(label)
            button.setObjectName(key)
            button.setCheckable(True)
            button.setAccessibleName(name)
            button.setAccessibleDescription("Ask by speaking" if key == "speak" else "Ask by typing")
            button.setFixedSize(WIDTH // 2, HEIGHT)
            button.setIconSize(QSize(ICON_PX, ICON_PX))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, key=key: self.pick(key))
            self.group.addButton(button)
            layout.addWidget(button)
            self.buttons[key] = button
        self.mode = mode
        self.buttons[mode].setChecked(True)
        self.restyle(self.colors)

    def pick(self, key):
        if key != self.mode:
            self.set_mode(key)
            self.changed.emit(key)
        else:
            self.buttons[key].setChecked(True)

    def set_mode(self, key):
        """Show this mode as chosen (without telling anyone: the dock calls this when it switches by itself)."""
        self.mode = key
        self.buttons[key].setChecked(True)
        self.paint_icons()

    def restyle(self, colors):
        self.colors = colors
        text, surface = colors["text"], colors["surface"]
        half = (f"font-family:'Segoe UI'; font-size:{LABEL_PX}px; font-weight:500; padding:0 {ICON_GAP}px; "
                f"border:{BORDER}px solid {text}; background:{surface}; color:{text};")
        self.setStyleSheet(
            f"QGroupBox {{ background:transparent; border:none; margin:0; padding:0; }}"  # the halves draw it all
            f" QPushButton {{ {half} min-height:{HEIGHT - 2 * BORDER}px; max-height:{HEIGHT - 2 * BORDER}px; }}"  # inside the border
            # Each half has the outer border on three sides and 1 px of the 2 px divider, so they meet in a straight line.
            f" QPushButton#speak {{ border-right-width:1px; border-top-left-radius:{RADIUS}px; border-bottom-left-radius:{RADIUS}px; }}"
            f" QPushButton#type {{ border-left-width:1px; border-top-right-radius:{RADIUS}px; border-bottom-right-radius:{RADIUS}px; }}"
            f" QPushButton:checked {{ background:{text}; color:{surface}; }}")
        self.paint_icons()

    def paint_icons(self):
        for key, button in self.buttons.items():
            chosen = key == self.mode
            button.setIcon(icon(key, self.colors["surface"] if chosen else self.colors["text"]))

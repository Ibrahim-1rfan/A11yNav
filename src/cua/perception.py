"""On-demand browser capture and explicit model-to-desktop coordinate mapping."""
from dataclasses import dataclass
import base64
from io import BytesIO
from PIL import Image, ImageGrab
from .config import UserError


@dataclass(frozen=True)
class Frame:
    data_url: str
    width: int
    height: int
    bounds: tuple[int, int, int, int]

    def desktop_point(self, x: float, y: float):
        if not 0 <= x <= 1 or not 0 <= y <= 1:
            raise UserError("The suggested target is outside the screen.")
        l, t, r, b = self.bounds
        return l + round(x * (r-l-1)), t + round(y * (b-t-1))


def preprocess(image: Image.Image, bounds: tuple[int, int, int, int], max_edge: int) -> Frame:
    l, t, r, b = bounds
    if r <= l or b <= t or image.size != (r-l, b-t):
        raise UserError("The browser window changed size. Please try again.")
    image = image.convert("RGB")
    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return Frame("data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"), *image.size, bounds)


class ScreenCapture:
    def capture(self, bounds, max_edge):
        try:
            return preprocess(ImageGrab.grab(bbox=bounds, all_screens=True), bounds, max_edge)
        except OSError as exc:
            raise UserError("I could not capture the browser. Unlock the desktop and try again.") from exc

"""Shared answer worker and answer renderer used by the main window and the voice dock."""
import html
import threading
from urllib.parse import urlsplit
from PySide6.QtCore import QThread, Signal
from .config import UserError
from .models import Cancelled
from .rag import display_name


class AnswerWorker(QThread):
    """Finds a guide and optionally rewrites it with the local text model. Never touches the desktop."""
    status = Signal(str, str)
    answered = Signal(object)

    def __init__(self, settings, question, factory=None, platform=None):
        super().__init__()
        self.settings, self.question, self.platform = settings, question, platform
        self.stop_event = threading.Event()
        self.factory = factory

    def run(self):
        try:
            from .assistant import build_assistant
            helper = self.factory() if self.factory else build_assistant(self.settings)
            self.status.emit("processing", "Finding the guide and writing your answer" if self.settings.text_model else "Finding the guide")
            answer = helper.answer(self.question, self.stop_event, platform=self.platform)
            if self.stop_event.is_set():
                raise Cancelled()
            self.answered.emit(answer)
            if answer.chat:
                self.status.emit("success", "Klicky replied.")
            else:
                self.status.emit("success" if answer.grounded else "error",
                                 "Here is how to do it." if answer.grounded else "I don't have a guide for that yet.")
        except Cancelled:
            self.status.emit("inactive", "Question stopped")
        except UserError as exc:
            self.status.emit("error", str(exc))
        except Exception:
            self.status.emit("error", "I could not look up that guide. Please try again.")


def answer_html(answer, profile, step=0, show_title=True):
    """Answer as rich text. One step at a time for profiles that ask for it."""
    c, line = profile.colors, f"line-height:{profile.line_height}%;"
    parts = []
    if show_title:
        parts.append(f'<p style="font-size:large; font-weight:bold; margin-bottom:2px;">{html.escape(answer.title)}</p>')
    if answer.apps:
        parts.append(f'<p style="color:{c["muted"]}; margin-top:0;">For {html.escape(", ".join(display_name(a) for a in answer.apps))}</p>')
    one_step = profile.one_step and answer.grounded and len(answer.steps) > 1
    if one_step:
        parts.append(f'<p style="{line} color:{c["accent"]}; font-weight:bold;">Step {step + 1} of {len(answer.steps)}</p>'
                     f'<p style="{line}">{html.escape(answer.steps[step])}</p>')
    elif answer.steps:
        rows = "".join(f'<tr><td valign="top" style="color:{c["accent"]}; font-weight:bold; padding-right:10px;">{i}</td>'
                       f'<td style="{line} padding-bottom:8px;">{html.escape(s)}</td></tr>' for i, s in enumerate(answer.steps, 1))
        parts.append(f'<table cellspacing="0" cellpadding="2">{rows}</table>')
    if answer.note:
        parts.append(f'<p style="{line} color:{c["muted"]};"><i>{html.escape(answer.note)}</i></p>')
    links = " · ".join(f'<a style="color:{c["accent"]};" href="{html.escape(s)}">{html.escape(urlsplit(s).hostname or s)}</a>'
                       for s in answer.sources if s.startswith("https://"))
    if answer.grounded:
        origin = "Written by your local answer model from the guide" if answer.generated else "From Klicky's checked guide"
        parts.append(f'<p style="color:{c["muted"]};">{origin}{" · " + links if links else ""}</p>')
    return "".join(parts), one_step

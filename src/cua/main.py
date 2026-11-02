"""Application entry point. --smoke exercises the real UI without desktop input."""
import argparse
import logging
from pathlib import Path
import sys
from .browser import enable_dpi_awareness
from .config import load, Settings, UserError, settings_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="Show and close the UI without starting automation")
    parser.add_argument("--smoke-image", help="Optional screenshot of the app itself during smoke testing")
    parser.add_argument("--smoke-popup", help="Open the Ask popup, answer a sample question, save a screenshot and exit")
    args = parser.parse_args()
    enable_dpi_awareness()
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from .ui import MainWindow
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Klicky")
    app.setOrganizationName("Klicky HCI")
    # Klicky lives in the corner widget and popup; only closing the main window quits it.
    app.setQuitOnLastWindowClosed(False)
    try:
        settings, error = load(), ""
    except UserError as exc:
        settings, error = Settings(), str(exc)
    logging.basicConfig(level=logging.WARNING)
    window = MainWindow(settings,error)
    first_run = not settings_path().exists()
    if (args.smoke or first_run or error) and not args.smoke_popup:
        window.show()
    # Otherwise start quietly: the corner widget and the global shortcut are the way in.
    if args.smoke_popup:
        def popup_finish():
            window.popup.open_for("chrome", None)
            window.popup.input.setText("How do I make text bigger?")
            window.popup.submit()
            QTimer.singleShot(1500, lambda: (window.popup.grab().save(args.smoke_popup), window.popup.hide(), window.close()))
        QTimer.singleShot(300, popup_finish)
    elif args.smoke:
        def finish():
            if args.smoke_image:
                window.grab().save(args.smoke_image)
            window.close()
        QTimer.singleShot(1500,finish)
    elif first_run:
        QTimer.singleShot(300,window.open_settings)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

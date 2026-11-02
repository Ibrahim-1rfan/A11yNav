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
    parser.add_argument("--smoke-popup", help="Open the voice dock, answer a typed sample question, save a screenshot and exit")
    args = parser.parse_args()
    enable_dpi_awareness()
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from .ui import MainWindow
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Klicky")
    app.setOrganizationName("Klicky HCI")
    # Klicky waits in the tray for its shortcut; only Quit in the tray menu ends it.
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
    elif window.tray and window.active_hotkey and not args.smoke_popup:
        # Start quietly: one short notice, then nothing on screen until the shortcut is pressed.
        window.tray.showMessage("Klicky is ready", f"Press {window.active_hotkey} in Chrome or Edge to ask a question.", window.tray.icon(), 5000)
    if args.smoke_popup:
        def popup_finish():
            window.dock.tts.volume = 0  # the smoke run reads silently
            window.dock.open_for("chrome", None, listen=False)
            window.dock.start_typing("How do I make text bigger?")
            window.dock.submit_typed()
            QTimer.singleShot(2500, lambda: (window.dock.grab().save(args.smoke_popup), window.quit_app()))
        QTimer.singleShot(300, popup_finish)
    elif args.smoke:
        def finish():
            if args.smoke_image:
                window.grab().save(args.smoke_image)
            window.quit_app()
        QTimer.singleShot(1500,finish)
    elif first_run:
        QTimer.singleShot(300,window.open_settings)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

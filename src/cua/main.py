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
    args = parser.parse_args()
    enable_dpi_awareness()
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from .ui import MainWindow
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Klicky")
    app.setOrganizationName("Klicky HCI")
    try:
        settings, error = load(), ""
    except UserError as exc:
        settings, error = Settings(), str(exc)
    logging.basicConfig(level=logging.WARNING)
    window = MainWindow(settings,error)
    window.show()
    if args.smoke:
        def finish():
            if args.smoke_image:
                window.grab().save(args.smoke_image)
            window.close()
        QTimer.singleShot(1500,finish)
    elif not settings_path().exists():
        QTimer.singleShot(300,window.open_settings)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

"""Double-click entry point, also used by PyInstaller."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from cua.main import main
raise SystemExit(main())

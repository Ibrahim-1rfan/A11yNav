# Windows folder build. Use Windows' own unversioned ICU API required by Qt;
# a third-party ICU found on PATH exports version-suffixed symbols and breaks Qt.
from pathlib import Path
root = Path(SPECPATH)
a = Analysis([str(root / 'launch.pyw')], pathex=[str(root / 'src')],
             binaries=[], datas=[], hiddenimports=[
                 'pyttsx3.drivers.sapi5', 'comtypes.gen.UIAutomationClient',
                 'pywinauto.controls.uia_controls', 'pywinauto.controls.win32_controls'],
             hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
a.binaries = [entry for entry in a.binaries
              if Path(entry[0]).name.lower() != 'icuuc.dll'
              and not Path(entry[0]).name.lower().startswith('icudt')]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Klicky',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Klicky')

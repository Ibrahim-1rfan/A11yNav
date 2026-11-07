# Setting up Klicky on your PC

This guide takes you from nothing to a working Klicky in about 20 minutes. Follow the steps in order. When you
finish, `scripts\check_setup.bat` should say **All good**.

**The one rule:** API keys go only in `keys.env` on your own PC. Never put a key in code, a commit, a chat, a
WhatsApp group or a screenshot. `keys.env` is ignored by git, so it can't be pushed by accident as long as you
don't rename it.

---

## 1. What you need

| Need | Details |
| --- | --- |
| Windows | Windows 10 or 11, 64-bit |
| Python | **3.13** (3.10 to 3.13 work; 3.14 is not tested). From [python.org](https://www.python.org/downloads/) |
| Git | From [git-scm.com](https://git-scm.com/download/win), or use GitHub Desktop / VS Code |
| Browser | **Google Chrome** or **Microsoft Edge** (Klicky reads these two). Firefox gets guides but no pointing |
| Microphone | For voice questions. Without one, use Type mode |
| Internet | For the LMS, the AI service and the voice |
| Disk | About 1.5 GB (Python packages 1.2 GB, speech model 145 MB) |

When installing Python, tick **"Add python.exe to PATH"** on the first screen.

---

## 2. Get the code

In a terminal (PowerShell, or the terminal in VS Code):

```powershell
git clone https://github.com/Ibrahim-1rfan/A11yNav.git
cd A11yNav
git checkout azhab-dev
```

`main` has the same code; `azhab-dev` is where new work lands first. Ask the project lead for access to the
repository if the clone is refused.

---

## 3. Install the packages

Double-click **`scripts\setup.bat`**. It creates a private Python environment in `.venv` and installs everything
Klicky needs from `requirements-dev.txt`. It takes 5 to 10 minutes and downloads about 1.2 GB.

Or in the terminal:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

What gets installed and why:

| Package | Used for |
| --- | --- |
| `PySide6` | Klicky's window: the orb, answer card, pointer, settings |
| `pywinauto`, `pywin32` | Reading the browser page (finding LMS links and buttons by name) |
| `faster-whisper`, `numpy`, `sounddevice` | Microphone input and the speech model on your PC |
| `edge-tts`, `av` | The natural voice that reads answers aloud |
| `requests` | Talking to the AI services (OpenRouter, Groq) |
| `Pillow`, `PyAutoGUI`, `pyttsx3`, `anthropic` | Screenshots, keyboard input, the Windows voice, optional Claude direct |
| `pytest`, `pyinstaller` | Running the tests and building `Klicky.exe` (not needed to use Klicky) |

---

## 4. Download the speech model

Double-click **`scripts\get_speech_model.bat`** once (145 MB). Klicky uses it to show your words live while you
speak, and as a backup when the online speech service can't be reached.

---

## 5. Add your API keys

Klicky uses two online services. You need one key for each.

| Line in `keys.env` | What it's for | Where you get it |
| --- | --- | --- |
| `OPENROUTER_API_KEY=` | Claude Haiku 5.5: finding a button on screen when the page doesn't name it, chat replies, assignment summaries | **From the project lead.** Each member gets their own key with a spending limit. Don't make your own |
| `GROQ_API_KEY=` | Turning your voice into text (Whisper) | **Make your own, free:** sign in at [console.groq.com/keys](https://console.groq.com/keys) → Create API Key |
| `HF_TOKEN=` | Not used. Leave empty | |
| `ANTHROPIC_API_KEY=` | Not used. Leave empty | |

**How to add them:**

1. Start Klicky once (`scripts\run.bat`), then quit it from the tray icon. This creates `keys.env` in the
   `A11yNav` folder, next to `launch.pyw`. (Or create a file named exactly `keys.env` there yourself.)
2. Open `keys.env` in VS Code or Notepad. It looks like this:

   ```ini
   OPENROUTER_API_KEY=
   HF_TOKEN=
   ANTHROPIC_API_KEY=
   GROQ_API_KEY=
   ```

3. Paste each key right after its `=` sign: no spaces, no quotes. Save.
4. Check that git can't see it: `git status` must **not** list `keys.env`.

**Keeping keys safe:**

- Don't share your keys with anyone, including other group members. Each person uses their own.
- Don't copy keys into code, `README`, issues, commits or screenshots.
- If a key leaks, tell the project lead at once so it can be deleted. A new one is free to make.
- The project lead can see how much each OpenRouter key has spent, and the limit stops it from spending more.

---

## 6. Check everything

Double-click **`scripts\check_setup.bat`**. Every line should say `OK`. It checks Windows, Python, the packages,
the speech model, both keys (without showing them; it also says how much of your OpenRouter limit is left) and
that `keys.env` is not tracked by git. Fix any `FIX` line, then run it again.

---

## 7. Start Klicky and try it

1. Double-click **`scripts\run.bat`**. A **"K"** icon appears in the system tray (bottom right).
2. Open the LMS (`lms.iba.edu.pk`) in Chrome or Edge and log in with **your own** account.
3. Press **Win+Shift+K**. The teal orb appears with a **Speak | Type** switch under it.
4. Ask, by voice or by typing:
   - *"How do I open the course outline?"*
   - *"Which assignment is due next?"*
   - *"Hey Klicky, how are you?"*
5. Klicky points at each link or button in turn and waits for your click.

If Win+Shift+K does nothing, another app owns that shortcut: right-click the tray icon → Settings, and choose
**Ctrl+Alt+F9**.

**Settings to check** (right-click the tray icon → Settings):

| Setting | Should be |
| --- | --- |
| Finding buttons by looking | Auto (uses Claude through OpenRouter) |
| Speech to text | Groq Whisper |
| Conversation | On |
| Klicky opens in | Speak (or Type if you have no microphone) |

---

## 8. If voice is mishearing you

Double-click **`scripts\mic_test.bat`**, press Enter and say the sentence it shows. It tells you if your voice is too
quiet, the room too noisy, or Klicky stops listening too early, and shows what each speech model heard. Send the
result to the project lead. Until it's fixed, use **Type** mode.

---

## 9. Getting updates

```powershell
git pull
```

If `requirements.txt` changed, double-click `scripts\setup.bat` again. Your `keys.env` and settings are kept.

---

## 10. Running study sessions

Once `check_setup` says All good and you've tried Klicky yourself, follow
**[study/STUDY_DAY.md](study/STUDY_DAY.md)**. It covers OBS (screen recording), the recorder
(`study\run_recorder.bat`: **Ctrl+S** starts a task, **Ctrl+E** ends it), what to read to each student, and how to
send your recordings back.

---

## 11. Troubleshooting

| Problem | Fix |
| --- | --- |
| `py` is not recognised | Reinstall Python and tick "Add python.exe to PATH" |
| `setup.bat` fails | Check the internet, then run it again. Python must be 3.10 to 3.13 |
| No "K" icon | Run `scripts\run.bat` again; check the tray's hidden icons (the ^ arrow) |
| The shortcut does nothing | Settings → shortcut **Ctrl+Alt+F9** |
| "Couldn't hear that" | Allow microphone access: Windows Settings → Privacy → Microphone → Let desktop apps access |
| Klicky answers but doesn't point | Use Chrome or Edge; keep the browser window on the main screen |
| Pointing is wrong or missing on some buttons | Run `check_setup.bat`: the OpenRouter key may be empty or out of its limit |
| `check_setup` says a key was refused | Paste it again with nothing before or after it; ask for a new OpenRouter key if it still fails |

Klicky writes a small log of guided steps and voice questions (lengths and loudness only, never what you said) to
`%LOCALAPPDATA%\Klicky\klicky.log`. Send it to the project lead when reporting a problem.

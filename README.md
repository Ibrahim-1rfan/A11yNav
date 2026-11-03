# Klicky

Klicky is an accessible "AI teacher" for Windows. It sits quietly next to your browser and, when you ask
("how do I submit my assignment?"), it answers out loud and **shows you where to click, one step at a time**:
a small companion pointer flies to the real link or button on the page and waits for you to click it.

It is built for the **IBA LMS** (Sakai, `lms.iba.edu.pk`) and for everyday tasks in **Edge, Chrome and Firefox**.
Every answer comes from a checked guide (a RAG knowledge base), so it doesn't make things up, and each answer
says where its steps came from.

Klicky never moves your own mouse. It points and you click; ask it to *go* somewhere and it opens the course tab and
menu links itself, but every button, choice and form stays yours.

---

## Contents

1. [What it does](#what-it-does)
2. [Quick start](#quick-start)
3. [Requirements](#requirements)
4. [Models and services](#models-and-services)
5. [API keys (optional)](#api-keys-optional)
6. [Using Klicky](#using-klicky)
7. [How it works](#how-it-works)
8. [Access profiles](#access-profiles)
9. [Settings](#settings)
10. [Privacy and safety](#privacy-and-safety)
11. [Project layout](#project-layout)
12. [Adding guides](#adding-guides)
13. [Testing and building](#testing-and-building)
14. [Troubleshooting](#troubleshooting)
15. [Known limits](#known-limits)

---

## What it does

- **Ask from anywhere.** Press **Win+Shift+K** (or Ctrl+Alt+F9 if another app owns that shortcut). The teal orb
  appears by your pointer with a **Speak / Type** switch under it. Speak your question, or type it.
- **Guided LMS walkthroughs.** For course tasks (course outline, resources, assignments, quizzes, Drop Box,
  announcements, calendar…) Klicky asks **"Which course?"**, unless you're already inside one, and then points
  at each link or button in turn, waiting for your click before moving on.
- **Browser how-tos.** Zoom and text size, reading mode, read aloud, dark mode, captions, caret browsing, find on
  page, tabs, bookmarks, history, extensions, settings and more, for Edge, Chrome and Firefox. Each one cites the
  official help page it was checked against.
- **Simple browser actions on request.** "Open a new tab", "refresh it", "zoom in", "go back", "close this tab",
  "bookmark this page", "open my history". Klicky presses that one browser button and nothing else.
- **Natural voice.** Answers are read aloud with a neural voice (Andrew, Ava and others), each step highlighted as
  it's spoken. Talk over it to interrupt and ask again.
- **Access profiles** for low vision, cognitive and learning needs, and motor and dexterity needs.
- **Web search agent** (the original prototype): "search for accessible interfaces" opens a search tab, driven
  step by step by a local vision model under a strict action policy.

---

## Quick start

You need Windows 10 or 11 (64-bit) and **Python 3.10 to 3.13** from [python.org](https://www.python.org/downloads/).
Tick "Add python.exe to PATH" when installing.

### Option A: double-click

1. Double-click **`scripts\setup.bat`**. It creates `.venv` and installs everything in `requirements-dev.txt`.
2. Double-click **`scripts\get_speech_model.bat`** once, to download the speech model (about 145 MB) for voice
   questions. You can skip this and type your questions instead.
3. Double-click **`scripts\run.bat`**. A "K" icon appears in the system tray.
4. Open the LMS in Chrome or Edge, press **Win+Shift+K** and ask: *"How do I open the course outline?"*

### Option B: terminal

```powershell
git clone https://github.com/Ibrahim-1rfan/A11yNav.git
cd A11yNav
git checkout azhab-dev
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\get_speech_model.py          # optional: voice questions (145 MB)
.\.venv\Scripts\pythonw.exe launch.pyw
```

To reproduce the exact tested environment, install `requirements-lock.txt` instead of `requirements.txt`.

That's all for the core features: guides, LMS walkthroughs, voice and the natural voice need **no AI model
download and no API key**. The optional extras are below.

---

## Requirements

### System

| Need | Details |
| --- | --- |
| OS | Windows 10 or 11, 64-bit, normal signed-in desktop (not locked or remote-only) |
| Python | 3.10 to 3.13, 64-bit (tested on 3.13.5) |
| Browser | Microsoft Edge, Google Chrome or Firefox |
| Microphone | Optional, for voice questions. Allow desktop apps under Windows Settings → Privacy → Microphone |
| Internet | For the LMS itself, the natural voice and the optional hosted vision fallback. Guides and speech recognition work offline |
| Screen | 1280×800 or larger recommended |

### Python packages (`requirements.txt`)

| Package | What Klicky uses it for |
| --- | --- |
| `PySide6` | The tray icon, orb, answer card, companion pointer and settings window |
| `pywinauto`, `pywin32` | Reading the browser's accessibility tree (UI Automation): finding LMS links and buttons by name |
| `PyAutoGUI` | Keyboard input for the search agent and browser actions |
| `Pillow` | Screenshots for the vision fallback and the search agent |
| `requests` | Talking to LM Studio and to the hosted vision APIs |
| `faster-whisper`, `numpy` | Local speech recognition (Whisper) |
| `sounddevice` | Microphone input and audio playback |
| `edge-tts`, `av` | The natural neural voice, and decoding its audio |
| `pyttsx3` | The Windows voice, used when the natural voice is off or offline |
| `anthropic` | Optional Claude vision backend (only when `ANTHROPIC_API_KEY` is set) |

`requirements-dev.txt` adds `pytest` (tests) and `pyinstaller` (building `Klicky.exe`).

---

## Models and services

Nothing here is downloaded automatically. Klicky only uses what you set up.

| What | Needed for | Size / cost | How to get it |
| --- | --- | --- | --- |
| **Whisper `base.en`** (faster-whisper) | Voice questions | ~145 MB, runs on this PC | `scripts\get_speech_model.bat` (or `tiny.en` / `small.en` as an argument) |
| **Edge neural voices** | Natural read-aloud | Free, online | Nothing to install. Settings → Voice type: Natural |
| **UI-TARS-1.5-7B on OpenRouter** (recommended) | Finding a button by looking, when the accessibility tree can't | Pay per use, a few seconds per lookup | Make a key at [openrouter.ai](https://openrouter.ai/keys), put it in `keys.env` |
| **Claude Haiku 5.5 on OpenRouter** | Summarizing an assignment's instructions | A fraction of a cent each, about 2.5 s | The same OpenRouter key |
| UI-TARS-1.5-7B on Hugging Face | Same, alternative | Hugging Face credits | Token from [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) in `keys.env` |
| Claude Haiku (`claude-haiku-5-5`) | Same, alternative | Anthropic API pricing | Key from [console.anthropic.com](https://console.anthropic.com/) in `keys.env` |
| **LM Studio** + a local model | The web search agent, or a fully local vision fallback | Multi-GB download | See [Local models (LM Studio)](#local-models-lm-studio) |
| Local text / embedding model (optional) | Rewriting answers in your profile's style; semantic search | Multi-GB | LM Studio, then Settings → Answer model / Embedding model |

Without any vision key Klicky still works: it finds LMS controls through the accessibility tree, which covers
almost every step. The vision model is only a fallback for the rare control the tree can't name.

### Local models (LM Studio)

Only needed for the web search agent, or if you want vision to stay on this PC.

1. Install [LM Studio](https://lmstudio.ai/) and update its runtime from inside the app.
2. Download a vision model, for example
   [lmstudio-community/UI-TARS-2B-SFT-GGUF](https://huggingface.co/lmstudio-community/UI-TARS-2B-SFT-GGUF/tree/main):
   `UI-TARS-2B-SFT-Q4_K_M.gguf` (1.12 GB) and its `mmproj-model-f16.gguf` (1.33 GB).
3. Load it with its projector and start the local server in LM Studio's **Developer** tab (keep it on loopback).
4. In Klicky's Settings: endpoint `http://127.0.0.1:1234/v1`, the exact model id from LM Studio, adapter `ui_tars`.
   Click **Check connection**.

Klicky only accepts local endpoints for LM Studio; redirects and proxies are refused.

---

## API keys (optional)

The first time Klicky starts, it creates **`keys.env`** in the project folder (next to `launch.pyw`):

```ini
OPENROUTER_API_KEY=
HF_TOKEN=
ANTHROPIC_API_KEY=
```

Paste **one** key after its `=` sign and save. No quotes, no restart needed; Klicky reads it at each walkthrough.
With Settings → Finding buttons by looking set to **Auto**, Klicky uses the first key it finds, in the order
OpenRouter, Hugging Face, Anthropic. A key set as a Windows environment variable wins over the file.

- `keys.env` is in `.gitignore`, so it is never committed. **Never paste keys into code, issues or chat.**
- A packaged `Klicky.exe` reads `keys.env` from its own folder.

---

## Using Klicky

### On the LMS

1. Sign in to the LMS yourself, in Chrome or Edge.
2. Press **Win+Shift+K** and ask, for example:
   - "How do I see the course outline?"
   - "Where are the lecture slides?"
   - "How do I submit my assignment?"
   - "How do I upload to the Drop Box?"
   - "Where are my quizzes?"
3. If you're not inside a course, Klicky asks **"Which course?"** and lists your course tabs. Say or type its name,
   part of it, its initials, or "the second one". Inside a course, it just uses that one.
4. The pointer flies to the first link and Klicky says the step. **Click it.** Klicky notices and moves on to
   the next step, until "That's it".

**Assignments, in detail.** On the Assignments page Klicky reads the list itself and tells you which assignments
aren't submitted yet and when they're due ("Which assignment? Week 08 Reading isn't submitted yet. It's due
November 4 at 2:15 PM."). It boxes the first one and points at it. Click it, click another, or say its name
("week eight"); if your question already named it ("how do I submit my week 8 reading") it goes straight there.
When the assignment opens, Klicky reads that page:

- **Already submitted:** "Week 07 Reading is already submitted, on October 28 at 2:04 PM. You don't have to worry
  about this one." and the walkthrough ends.
- **Not submitted:** it says the due date (or that it has passed), then a one- or two-sentence summary of the
  instructions, for example "Read the paper and answer three questions in no more than 400 words.", shown on the card
  too. Then it carries on: write or attach your work, Proceed, Submit.

The summary is written by the first AI service with a key in `keys.env` (OpenRouter's Claude Haiku 5.5, then
Anthropic, then a local LM Studio answer model). Only the assignment's title and instruction text are sent, never your
name, grades or submission. Turn this off in Settings → Assignment summaries: Klicky then reads the first sentences
of the instructions and sends nothing.

On the **Syllabus** page, Klicky boxes the **Course Outline** item and points at it for you to click.

**Or let Klicky go there.** Say it as a request instead of a question: *"show me the syllabus of Computer
Security"*, *"open my HCI assignments"*, *"take me to Resources"*. Klicky says "Opening Computer Security.", the
pointer flies to the tab and boxes it, and Klicky opens it, then the Syllabus link, then Course Outline: "Here it is."
It only ever opens the **course tab and menu links**, through Windows accessibility (your mouse never moves). It
never presses a button such as Proceed, Submit, Save or Upload, and it never picks an assignment for you: at the first
step that needs you, it goes back to pointing and waiting for your click. If it can't open a link, it asks you to
click it. "How do I…" questions are still guided step by step. Turn this off with Settings → Browser tasks.

Esc or clicking the orb stops a walkthrough at any time.

LMS guides cover: course outline (Syllabus), calendar, announcements, Resources (lectures), viewing and submitting
an assignment, tests and quizzes, the Drop Box, adding a course to the top bar, and notifications. Their steps
come from a recorded IBA student walkthrough, and the card shows the time in the video each one came from.

### In the browser

Ask "how do I zoom in?", "turn on dark mode", "read this page aloud" and similar. Klicky reads the steps, and
for steps that go through the browser's menu it points at each control and waits for your click.

Short requests such as "open a new tab for me" are done for you (a fixed list of safe browser buttons only).
Turn this off under Settings → "Let Klicky do simple browser tasks when I ask".

### Speak or Type

Under the orb is one switch with two halves, **Speak** and **Type**. Klicky opens in the one you used last (or the one
set in Settings → Klicky opens in).

- **Speak:** the orb listens, its rings following your voice. Your answer is read aloud.
- **Type:** the microphone stays off and a text box appears under the switch. Type and press Enter. **The answer comes as text only, with no sound:** each line is shown as a caption
  for as long as it takes to read, and guided steps work the same way: Klicky points, shows the step, and waits for
  your click. "Which course?" and "Which assignment?" are typed too.
- In Speak mode, pressing any letter or Tab switches to Type (the letter goes into the box). Esc closes.
- Screen readers hear a group called "Input mode" with two toggle buttons, "Voice" and "Typing", and "Listening" /
  "Typing" when it changes.

### Talking and listening

- After the beep, speak and pause: Klicky stops listening by itself. Start typing at any time to switch to text.
- Talk over an answer to stop it and ask again. The first Esc stops reading; the next closes the card.
- The tray menu has Ask, Open window, Settings and Quit.

---

## How it works

```
 your question ──► router ──► "search for …"  ──► search agent (local vision model, strict action policy)
                     │
                     ├──► "open a new tab"  ──► browser action (one fixed button)
                     │
                     └──► "how do I …"      ──► RAG: BM25 over knowledge/*.md (+ optional embeddings)
                                                 │      boosted for the site you're on (e.g. the LMS)
                                                 ▼
                                          checked guide steps + evidence
                                                 │
                         ┌───────────────────────┴───────────────────────┐
                         ▼                                               ▼
               read aloud (neural voice)              guided walkthrough, one step at a time
                                                     1. accessibility tree: find the link/button by name
                                                     2. fallback: screenshot → UI-TARS / Claude says where
                                                     3. point at it, wait for your click, next step
```

- **The guide decides every step.** The vision model is never asked *what* to do, only *where* a named control is.
  Its answer is checked before it's used.
- **Accessibility tree first.** Chrome and Edge expose the page's links and buttons to Windows (the same structure
  screen readers use), so Klicky finds "Assignments" or "Submit" by name. Colours, dark mode and zoom don't matter.
- **No made-up answers.** A question with no matching guide gets "I don't have a guide for that yet". When an
  optional answer model rewrites a guide, each step must cite a retrieved guide or Klicky shows the guide as written.

More detail: `docs/architecture.md`.

---

## Access profiles

Pick one in the main window or Settings. It applies at once.

| Profile | What changes |
| --- | --- |
| Standard | The original dark, large-text layout |
| Low vision | 30 px text, yellow-on-black high contrast, thick focus outline, larger widget, speech on, at most 5 steps with key names spelled out |
| Cognitive and learning | Calm colours, extra letter and line spacing, a dyslexia-friendly font if installed (OpenDyslexic, Lexend, else Verdana), plain language, one step at a time with Back/Next |
| Motor and dexterity | Taller buttons with wide spacing, a larger Stop button, Enter starts, quick-pick examples, slower pacing, fewest key presses |
| Deaf and hard of hearing | Opens in **Type** mode: answers and every guided step as text and captions, never sound; guides describe what appears on screen rather than sounds |

Profiles change presentation and wording only. Their benefit has not yet been evaluated with users.

---

## Settings

Open from the tray icon → Settings. Saved in `%LOCALAPPDATA%\Klicky\settings.json`
(`config/settings.example.json` lists every field).

| Setting | Default | Notes |
| --- | --- | --- |
| Shortcut | Win+Shift+K | Falls back to Ctrl+Alt+F9 |
| Klicky opens in | Speak | Speak or Type; also remembered from the switch under the orb |
| Voice questions | On | Listens when the orb opens. Needs the speech model |
| Answers | Read aloud | |
| Voice type | Natural | Natural = Edge neural voices (online); Windows = offline SAPI voice |
| Natural voice | Ava | Andrew, Emma, Sonia, Neerja, Prabhat… |
| Reading speed | 1.0 | |
| Finding buttons by looking | Auto | Auto, UI-TARS on OpenRouter, UI-TARS on Hugging Face, Claude, Local model, Off (page names only) |
| Show Klicky companion | On | Follow speed: Gentle, Normal, Snappy. Click ripple on/off |
| Screen reader | On | "Let my screen reader read answers instead, when one is running" |
| Browser tasks | On | "Let Klicky do simple browser tasks when I ask" |
| Assignment summaries | On | Summarize an unsubmitted assignment's instructions with AI (the instruction text is sent) |
| Answer model / Embedding model (optional) | Empty | LM Studio models |
| Profile | Standard | See above |

Windows "Show animations" off means no pulsing, ripples or overshoot; state is shown by colour, icon and caption.

---

## Privacy and safety

- **Klicky never moves your mouse pointer.** When you ask it to go somewhere on the LMS ("show me the syllabus"),
  it opens only course tabs and menu links. Every button, choice and form is yours: it never logs in, fills forms,
  presses Proceed or Submit, submits assignments, sends messages or buys anything.
- **Microphone audio** stays in memory on this PC (local Whisper). It is never saved or sent.
- **Natural voice:** the text being read is sent to Microsoft's speech service. Switch to the Windows voice to keep
  it offline. Common lines are cached in `%LOCALAPPDATA%\Klicky\voice-cache`.
- **Assignment summaries:** only an unsubmitted assignment's title and instruction text are sent, to the AI service
  in `keys.env`. Whether it's submitted, and its due date, are read on this PC. Settings → Assignment summaries off
  sends nothing.
- **Vision fallback:** only when the accessibility tree can't find a control, a screenshot of the browser window
  is sent to the hosted backend you set up (OpenRouter, Hugging Face or Anthropic). Choose Local model or Off to keep
  screenshots on this PC. Screenshots are never saved by Klicky.
- **Keys** live only in `keys.env` or environment variables, are never logged or shown, and go only to their own provider.
- The search agent captures the browser window only during a task you start, and only the exact next safe action is allowed.

---

## Project layout

```
A11yNav/
├── launch.pyw                 start Klicky (no console window)
├── keys.env                   your API keys (created on first run, git-ignored)
├── requirements.txt           packages to run Klicky
├── requirements-dev.txt       + pytest and pyinstaller
├── requirements-lock.txt      exact tested versions
├── Klicky.spec                PyInstaller build
├── knowledge/
│   ├── browsers/*.md          Edge, Chrome and Firefox guides (cite official help pages)
│   └── lms/*.md               IBA LMS guides (cite the student walkthrough video)
├── src/cua/
│   ├── main.py                app start-up, tray, hotkey
│   ├── dock.py                the orb, answer card and the whole ask → answer → guide flow
│   ├── rag.py                 knowledge loading, BM25 + embeddings retrieval, platform detection
│   ├── assistant.py           grounded answers from retrieved guides
│   ├── page.py, pagewalk.py   LMS: reading course tabs, controls and assignments from the accessibility tree; guided steps
│   ├── summary.py             a short summary of an assignment's instructions
│   ├── walkthrough.py         guided steps for the browser's own menus
│   ├── vision.py              vision fallback: OpenRouter / Hugging Face UI-TARS, Claude, LM Studio
│   ├── keys.py                reads keys.env
│   ├── voice.py, speech.py    listening (Whisper)
│   ├── neural_tts.py, tts.py  speaking (Edge neural voices, Windows voice)
│   ├── companion.py, orb.py, highlighter.py, ripple.py   the pointer, orb and highlights
│   ├── inputmode.py           the Speak / Type switch under the orb
│   ├── browser.py, browser_actions.py, actions.py        browser windows and the fixed browser actions
│   ├── controller.py, models.py, planning.py, …         the web search agent
│   └── profiles.py, config.py, ui.py                    access profiles, settings, settings window
├── scripts/                   setup.bat, run.bat, get_speech_model.bat, build.bat, smoke tests
├── tests/                     pytest suite
├── docs/                      architecture, analysis, test cases and reports
└── tracker.md                 dated log of decisions, fixes and test results
```

---

## Adding guides

A guide is a Markdown file in `knowledge/<platform>/`. No code changes are needed.

```markdown
---
title: See a course outline (syllabus) on the LMS
task: find your course outline
keywords: course outline, outline, syllabus, course plan
names: course outline, syllabus
ask: course
point:
- course
- link: Syllabus
- any
- tip
evidence:
- IBA LMS student walkthrough video, 0:31 to 1:06
---
## LMS
1. Open {course} from the course tabs at the top.
2. Select Syllabus in the left menu.
3. Select the Course Outline item.
4. The outline file is often also kept in Resources, in the Course Outline folder.
```

- `ask: course` makes Klicky ask which course and fill in `{course}`.
- `point:` has one entry per step: `course`, `link: <name>`, `button: <name>`, `control: <name>`
  (`A|B` for alternatives), `any` (wait for any click), `assignment` (read the Assignments list, ask which one,
  then report whether it's submitted or summarize it) or `tip` (just read it).
- `sources:` (official URLs) or `evidence:` (where the steps were observed) is required, and shown on the card.

---

## Testing and building

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q          # about 410 tests, about two minutes
.\.venv\Scripts\python.exe launch.pyw --smoke    # opens and closes the window
.\scripts\build.bat                              # dist\Klicky\Klicky.exe
```

- `launch.pyw --smoke-popup dock.png` answers a sample question silently and saves a screenshot of the card.
- `scripts/try_vision.py` tries the vision fallback on a screenshot.
- `scripts/desktop_smoke.py` is a real-desktop test that opens one Bing search tab (no model involved).

The build is a folder-based, unsigned executable. Keep the whole `dist\Klicky` folder together; it contains no AI
weights. Put `keys.env` next to `Klicky.exe` for the vision fallback.

---

## Troubleshooting

| Problem | Fix |
| --- | --- |
| The shortcut does nothing | Another app may own Win+Shift+K: try Ctrl+Alt+F9, or change it in Settings |
| "The speech model is not installed yet" | Run `scripts\get_speech_model.bat` |
| Klicky doesn't hear me | Check Windows Settings → Privacy → Microphone → "Let desktop apps access your microphone" |
| Robotic voice | Settings → Voice type: Natural. Offline, Klicky falls back to the Windows voice |
| It asks "Which course?" but lists nothing | Make sure the LMS page has finished loading and the course tabs are visible, then ask again |
| The pointer can't find a button | Make the window wider (narrow layouts fold the LMS menu away), or add a vision key to `keys.env` |
| An old version keeps running | Quit from the tray icon (or end `pythonw.exe` running `launch.pyw`) and start again |

---

## Known limits

- Built and tested on one Windows 11 laptop with Chrome and Edge. Firefox, screen readers and other set-ups need trying.
- LMS guides follow the student view of the IBA LMS. Instructor and admin tasks get guidance only.
- The Drop Box names and the final assignment confirmation page have not yet been checked on a live account.
- UMS is not covered yet.
- The accessibility benefits have not yet been evaluated with users.

## More documentation

- `docs/architecture.md`: components, interfaces and trust boundaries
- `docs/project_analysis.md`: the research pitch and scope
- `docs/test_cases.md`, `docs/testing_report.md`: test cases and results
- `docs/implementation_plan.md`: phases of the original plan
- `tracker.md`: dated decisions, failures, fixes and next steps

# Klicky: session handoff (as of 4 November 2026, ~3 AM)

Read this first if you are a new agent picking up the work. It says what Klicky is, where everything is, what is
done, what is **not committed yet**, how to run and test it, the decisions the owner has made, the rules to keep, and
what to do next. `tracker.md` has the dated history in more detail; `README.md` is the user-facing manual.

---

## 1. What this project is

**Klicky** is an accessible "AI teacher" for Windows, built for an HCI course project (7th semester, IBA Karachi).
It sits next to the browser; you press a hotkey and ask ("how do I submit my assignment?"). It answers from checked
guides (RAG, no made-up answers, with evidence shown), and **points at the real link/button on the page**, waiting for
your click, one step at a time.

Target: the **IBA LMS** (Sakai, `lms.iba.edu.pk`) plus everyday **Edge / Chrome / Firefox** tasks.

Three user groups (the inclusivity story, in the owner's words):
1. **Motor disabilities**: can just ask Klicky (voice); it can also *go there itself* ("show me the syllabus").
2. **Low vision / blind**: voice in, voice out, large text, pointer + box on the target.
3. **Deaf / hard of hearing**: **Type** mode: type questions, answers come as text/captions, no sound needed.

Owner: Azhab Babar (works on the `azhab-dev` branch of Ibrahim-1rfan's repo). Prefers short, plain answers; tests
things live and reports visually (screenshots). Calls the companion "the duplicate cursor"/"Clicky cursor".

---

## 2. Where things are

| What | Where |
| --- | --- |
| Project (git repo) | `D:\Classess\Projects\Klickyy\A11yNav` |
| GitHub | https://github.com/Ibrahim-1rfan/A11yNav |
| Working branch | `azhab-dev` (the owner sometimes says "Azure branch": it means `azhab-dev`) |
| Python venv | `.venv` (Python 3.13.5) |
| User settings | `%LOCALAPPDATA%\Klicky\settings.json` |
| API keys | `keys.env` in the project root (git-ignored). **Never read, print or commit it.** |
| Speech model | `%LOCALAPPDATA%\Klicky\models\faster-whisper-base.en` (installed) |
| Voice cache / log | `%LOCALAPPDATA%\Klicky\voice-cache\`, `%LOCALAPPDATA%\Klicky\klicky.log` (walk steps, no page text) |
| Scratch/temp output | `tmp\` in the project (git-ignored), e.g. `tmp\companion_sizes.png` |
| Reference video | `D:\Classess\7th Sem\HCi\Project\Clickyy.mp4` (the "Clicky" demo the owner likes) |
| Blender (abandoned) | Installed at `C:\Classess\7th Sem\HCi\Project`; not part of the project any more |

### Git state

- `azhab-dev` is pushed to GitHub with all of the work below, in the commit after a513e43 ("LMS assignments in
  detail, go-there mode, Speak or Type, one step at a time": the latest commit on the branch; see `git log`).
- `main` is still at a513e43 (fast-forwarded on 3 Nov at the owner's request). Update it only when the owner asks.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- `git stash list` → `stash@{0}: Blender experiment (removed from the project, 3 Nov 2026)`. Kept only as a backup.
  The owner said to remove everything Blender and stick to the LMS.

---

## 3. How to run, test and restart

```powershell
cd D:\Classess\Projects\Klickyy\A11yNav
.\.venv\Scripts\python.exe -m pytest -q          # 412 tests, about 1 minute; all passing at handoff
.\.venv\Scripts\pythonw.exe launch.pyw           # start Klicky (tray icon "K"); hotkey Win+Shift+K
```

- **Restarting Klicky** after code changes: stop every `pythonw.exe` running `launch.pyw`, then start it again
  (from an agent: PowerShell `Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object
  { $_.CommandLine -like '*launch.pyw*' } | Stop-Process`, then run `launch.pyw` in the background; two python
  processes for one Klicky is normal with a venv). Shell commands that touch the user's apps or network needed the
  sandbox disabled in this environment.
- `git push` needs `GIT_TERMINAL_PROMPT=0` (it otherwise hangs on a credential prompt) and works unsandboxed.
- Tests must never touch the real settings file: `tests/conftest.py` redirects `cua.config.settings_path` to a temp
  folder (autouse). Keep it that way. (Earlier the tests overwrote the owner's settings; it was restored.)
- Rendering widgets offscreen for screenshots: `QT_QPA_PLATFORM=offscreen` and `QT_QPA_FONTDIR=C:/Windows/Fonts`.

---

## 4. What Klicky does now (all features)

### 4.1 Intelligence layer (RAG): committed
- `knowledge/browsers/*.md` (17 guides, Edge/Chrome/Firefox, each cites official help) and `knowledge/lms/*.md`
  (9 guides: course outline, calendar, announcements, resources, submit assignment, tests and quizzes, drop box,
  favourite sites, notifications), steps taken from the IBA student walkthrough video (evidence shown on the card).
- `src/cua/rag.py`: BM25 (+ optional LM Studio embeddings with RRF), platform detection (LMS from the tab title),
  platform boost ×1.5, `names:` front-matter boost (e.g. "drop box" beats "assignment").
- `src/cua/assistant.py`: grounded answers; guided guides (`ask`/`point`) are always shown as written.
- Guide front matter: `title, keywords, names, ask: course, point: [...], evidence/sources`. Point specs:
  `course`, `link: <name>`, `button: <name>`, `control: A|B`, `any`, `tip`, `assignment` (see 4.5).

### 4.2 Accessibility tree pointing on the LMS: committed
- `src/cua/page.py`: reads the Chrome/Edge page through Windows UI Automation (pywinauto): course tabs (between the
  Home link and the left menu), links/buttons by name, link URLs. Retries while Chrome builds its tree lazily.
- "Which course?" is asked only when not already inside a course (tab title `Sakai : <course> : <tool>`).
- `src/cua/pagewalk.py` (`PageWalkthrough`): say step → box + companion flies to the control → wait for the click →
  next step. Vision fallback (`src/cua/vision.py`) when the tree can't find a control: hosted UI-TARS-1.5-7B via
  OpenRouter (`OPENROUTER_API_KEY` in keys.env; the owner added one) → Hugging Face → Claude Haiku → local.

### 4.3 Voice: committed
- Voice in: local faster-whisper `base.en`. Voice out: Edge neural voices (the owner chose **Andrew**,
  `en-US-AndrewNeural`), cached, Windows SAPI fallback.

### 4.4 Assignments in detail: committed 4 Nov
- Recorded the live LMS read-only (with permission): the Assignments list is a table (Assignment Title / Status /
  Open Date / Due Date); an opened assignment has a StatusBar ("In progress"/"Submitted"), label/value rows
  (Title, Due, Status, Submitted Date) and an "Instructions" section ending at "Additional resources for assignment".
- `page.py`: `assignment_rows`, `assignment_page`, `assignments(hwnd)`, `opened_assignment(hwnd)`, `spoken_time`,
  `tool_of(title)`, `opens(spec, tool)`.
- The submit-assignment guide's step 3 is `assignment`: Klicky reads the list, says which aren't submitted and
  their due dates, boxes the first, listens (or reads typed text) for a name ("week eight" → "Week 08 Reading");
  any click on an assignment also counts. Then it reads the opened page: **submitted** → "already submitted, on …,
  you don't have to worry about this one" (ends); **not submitted** → due date (or "has passed") + a 1–2 sentence
  summary of the instructions, then the remaining steps (write/attach, Proceed, Submit).
- `src/cua/summary.py`: summary via OpenRouter `anthropic/claude-haiku-5.5` → Anthropic `claude-haiku-5-5` → local
  answer model → first sentences. Only title + instruction text are sent. Setting `summaries` (on).
  Live check: 2.5 s, correct summary.
- If the tab already shows the tool (e.g. "… : Assignments"), the link step is skipped; if an assignment is already
  open, it is read straight away. Course Outline step now boxes the "Course Outline" link (it was "any").

### 4.5 "Show me the syllabus": Klicky goes there itself: committed 4 Nov
- `planning.is_do_it`: "show me / open / take me to / go to / bring up / can you open …" (not "how do I"). With
  Settings → Browser tasks on, `course` and `link:` steps are **opened by Klicky** through UI Automation Invoke
  (LegacyIAccessible DoDefaultAction fallback) after the companion boxes them; the mouse never moves.
- **Never** presses buttons (`control:`/`button:` such as Proceed, Submit, Upload) and never picks an assignment.
  If pressing fails → "I couldn't open it myself. Please click it." and guides the rest.
- Not yet tried on the live LMS.

### 4.6 Speak / Type (Deaf and hard-of-hearing): committed 4 Nov
- Under the orb: one segmented control **Speak | Type** (`src/cua/inputmode.py`, 190×46, group "Input mode",
  buttons "Voice"/"Typing"), then a typing box row that is always reserved (no layout shift).
- Typed question → **answer in text only** (`SilentReader` in dock.py shows each line as a caption for its reading
  time with the same callbacks), so LMS walkthroughs, "Which course?" and "Which assignment?" work without sound.
  Spoken question → read aloud.
- Hotkey opens in the saved mode (`input_mode` setting; remembered when switched). A printable key or Tab in Speak
  mode switches to Type. New profile **"Deaf and hard of hearing"** (opens in Type). Settings → "Klicky opens in".
- The owner supplied a detailed spec (84 px container, halo 0.88–1.0, mic-off orb). It was built, the owner
  disliked the look ("animations/visuals fucked up"), so **the original orb was restored unchanged** and only the
  Speak/Type boxes + typing box were kept.

### 4.7 Orb and companion look: committed 4 Nov (owner-approved)
- Orb (`src/cua/orb.py`) = the original: teal `#1D9E75` circle, white mic, voice-following rings, breathing while
  thinking, pulse while speaking, 56 px (72 low vision). Change: the focus ring shows **only for Tab focus**
  (opening Klicky no longer draws a dark ring). The owner's reference: plain teal circle + white mic.
- Companion pointer (`src/cua/companion_asset.py`): **18 px, plain teal, no outline** (owner chose 18 px from a
  comparison picture; white outline → dark green outline → no outline, at the owner's request). Offset (16, 14)
  down-right of the real cursor.

### 4.8 Card behaviour: committed 4 Nov
- Walkthroughs show **one step at a time** ("Step 2 of 6"), the next appears once the step is done; closing tips
  together at the end (pagewalk + browser walkthrough).
- The card/orb **moves clear of the boxed target** (dock.`move_out_of_the_way`: tries several spots using the card's
  real size, picks the least-covering one). In Type mode, a step on the card isn't repeated as a caption.

### 4.9 Other: committed 4 Nov
- Local step log `%LOCALAPPDATA%\Klicky\klicky.log` (`main.walk_log`, logger `klicky.walk`; numbers/counts only).
- "how do I submit my week 8 reading" now goes to the assignment guide (was Calendar): reading keywords added.

### 4.10 Docs: committed 4 Nov
- README describes everything above (Speak/Type, assignments, go-there mode, summaries, privacy), tracker has
  dated entries through 4 Nov. README still says the companion is "teal"; its size isn't documented (fine).

---

## 5. Live LMS facts (from the read-only recording, ComSec)
- Tab title: `Sakai : Computer Security (Class No 101765) - Fall 2026 : <Tool> - Google Chrome`.
- Left menu links include Overview, Syllabus, Assignments, Resources, Announcements, Calendar, Tests & Quizzes, Drop Box.
- Syllabus page: "Expand All" button, "Print View" link, TabItem "Course Outline" containing link "Course Outline".
- Assignment page buttons: Proceed, Preview, Save Draft, Cancel; "Select a file from computer". Submitted page has
  "Back to list". 20 ComSec assignments were read correctly. A **Not Started** assignment page was never recorded.

---

## 6. Rules and constraints to keep

- **Never read, print or paste `keys.env` or any API key.** Keys only in `keys.env` (git-ignored) or env vars.
  The owner once pasted a key in chat: it was not used and they were told to revoke it.
- Ask before reading the owner's browser/LMS tabs (each read-only check needs a yes). Recordings stay local.
- Klicky never moves the real mouse; it opens only course tabs/menu links itself; every button, form and choice is
  the person's. Never submit anything on the LMS.
- Tests must not touch real user files (conftest guard). Don't download models/files without asking.
- Don't commit or push without the owner's yes. Push target is `azhab-dev` (main only when asked).
- Prefer the owner's visual direction: they react strongly to looks. Show options as rendered pictures (as with
  the pointer sizes) before changing visuals.

---

## 7. Open items / next steps

1. Done: today's work is committed and pushed to `azhab-dev`. Merge to `main` only if the owner asks.
2. Live checks not done yet: go-there mode pressing links on the real LMS; one-step card + move-aside on the real
   screen; Speak/Type end to end; a **Not Started** assignment page; Drop Box names.
3. Optional (proposed, not started): Clicky-style motion from the reference video: the companion morphs into a tiny
   waveform while listening, a spinner while thinking, flies to the target facing its direction with a small
   "found it!" label, and flies back after the click. (Video analysis: triangle down-right of cursor; hotkey → flat
   line → 5-bar waveform; ~34 s spinner ring; ~0.6–0.7 s curved flight; pill label; label fades ~1.5 s after the
   click and it returns.)
4. UMS (IBA's other portal) is not covered; needs a video/screenshots from the owner.
5. Usability-test materials (tasks, SUS, results template) were suggested for the HCI report; not started.
6. Rarely flaky test: `test_a_control_folded_into_a_menu_points_at_the_menu_first` (timing; wait raised to 8 s).

---

## 8. Short timeline of this session
- Cloned A11yNav as Azhism, branch `azhab-dev`; built RAG layer, profiles, voice orb, companion, walkthroughs,
  browser actions (committed earlier).
- 3 Nov: LMS guides from the student video; course-aware walkthroughs; accessibility-tree pointing with hosted
  UI-TARS fallback (OpenRouter); natural voice (Andrew); committed 6268481.
- Blender add-on + guides built, then **removed** (stashed) at the owner's request; detailed README + full
  requirements; committed a513e43, pushed, main fast-forwarded.
- Assignment detail (list, status, summaries), Course Outline pointing, "already on the page" fixes, step log.
- "Show me the syllabus" go-there mode.
- 4 Nov: Clicky video analysed; Speak/Type + Deaf profile + text-only answers; orb redesign reverted to the original;
  focus ring only on Tab; one step at a time; card moves off the target; companion pointer 18 px, no outline.

# Klicky: session handoff (as of 9 November 2026)

Read this first if you are a new agent picking up the work. It says what Klicky is, where everything is, what is
done, what is **not committed yet**, how to run and test it, the decisions the owner has made, the rules to keep, and
what to do next. `tracker.md` has the older dated history; `README.md` is the user-facing manual;
`study/STUDY_DAY.md` is how to run a session; `analysis/README.md` is the study data and report.

---

## 1. What this project is

**Klicky** is an accessible "AI teacher" for Windows, built for an HCI course project (7th semester, IBA Karachi).
It sits next to the browser; you press a hotkey and ask ("how do I submit my assignment?"). It answers from checked
guides (RAG, no made-up steps), and **points at the real link/button on the page**, waiting for your click, one step
at a time. It also chats back to small talk ("hey Klicky, how are you?").

Target: the **IBA LMS** (Sakai, `lms.iba.edu.pk`) plus everyday **Edge / Chrome / Firefox** tasks.

Design story (current, owner 9 Nov): **two layers** for **ordinary first-time LMS users**:
1. **Guidance layer** (the agent): reads the page (accessibility tree, screenshot as backup), points at the control,
   waits for the click, next step.
2. **Document intelligence layer** (RAG): checked guides per task, retrieved by keyword/meaning; no made-up steps.
"Accessible" now means easy for newcomers (recognition rather than recall, one step at a time). The instructor asked
why target Deaf/blind/motor users when first-time students are enough, so the **accessibility layer and the
Speak/Type agents for disability groups were dropped from the story**. Speak or type stays only as an input choice;
the code (Speak/Type, profiles) still exists. Disability support is at most a line of future work.

Owner: Azhab Babar (works on the `azhab-dev` branch of Ibrahim-1rfan's repo). Prefers short, plain answers ("simpler
mate"); tests things live and reports with screenshots. Calls the companion "the duplicate cursor"/"Clicky cursor".

---

## 2. Where things are

| What | Where |
| --- | --- |
| Project (git repo) | `D:\Classess\Projects\Klickyy\A11yNav` |
| GitHub | https://github.com/Ibrahim-1rfan/A11yNav |
| Working branch | `azhab-dev` (the owner sometimes says "Azure branch": it means `azhab-dev`) |
| Python venv | `.venv` (Python 3.13.5) |
| User settings | `%LOCALAPPDATA%\Klicky\settings.json` |
| API keys | `keys.env` in the project root (git-ignored): OPENROUTER_API_KEY and GROQ_API_KEY are set. **Never read, print or commit it.** |
| Speech models | `%LOCALAPPDATA%\Klicky\models\faster-whisper-base.en` (used) and `-small.en` (installed, unused: too slow) |
| Voice cache / log | `%LOCALAPPDATA%\Klicky\voice-cache\`, `%LOCALAPPDATA%\Klicky\klicky.log` (walk steps, no page text) |
| Research paper (Claude Doc) | https://claude.ai/artifact/C4huXCjvy8mykFxKbt3Xc5 ("Klicky: A Layered, Context-Aware Agent for Accessible LMS Navigation"); out of date, see 4.11 |
| Team's project report (PDF) | `D:\Classess\Projects\Klickyy\HCI_Project.pdf` (12 pages, written by the team; no `.tex` on this PC). Reviewed 9 Nov, see 4.19 |
| Study data and report | `analysis\` (data, results/report.html, code, run_analysis.py, README); see 4.18 |
| Study app | `study\` (Klicky Mart shop + results server); see 4.13 |
| Scratch/temp output | `tmp\` in the project (git-ignored), e.g. `tmp\mart_shop.png` |
| Preview launch config | `D:\Classess\Projects\Klickyy\.claude\launch.json` ("klicky-mart" on port 8765), outside the repo |
| Reference video | `D:\Classess\7th Sem\HCi\Project\Clickyy.mp4` (the "Clicky" demo the owner likes) |

### Git state

- Last pushed commit: **8ae70ad** (study tools, setup guide, Claude Haiku via OpenRouter, Klicky only points) on both
  `azhab-dev` and `main` (8 Nov). Before it: 282173d, 520d99b.
- **Not committed yet** (467 tests pass): the fixed 4-task order in the recorder, the report additions (task by task,
  practice or Klicky, every student, data sources), the exported-JSON loader and `leave_out`, the fast exact Wilcoxon,
  STUDY_DAY.md updates, the `analysis/` folder, this file. The owner hasn't said whether `analysis/data` (student
  sessions) should go to GitHub; ask before committing it.
- Commit messages must NOT include a Co-Authored-By: Claude line (history was rewritten on 4 Nov to remove them).
- Every push to `azhab-dev` also fast-forwards and pushes `main` (owner, 4 Nov): `git push origin azhab-dev:main`.
- Local-only branch `backup/before-rewrite` keeps the pre-rewrite history; delete when the owner is happy.
- `git stash list` → `stash@{0}: Blender experiment (removed 3 Nov)`. Backup only; the owner dropped Blender.

---

## 3. How to run, test and restart

```powershell
cd D:\Classess\Projects\Klickyy\A11yNav
.\.venv\Scripts\python.exe -m pytest -q          # 467 tests, about 1.5-3 minutes; all passing on 9 Nov
.\.venv\Scripts\python.exe analysis\run_analysis.py   # rebuild the study report from analysis\data
.\.venv\Scripts\pythonw.exe launch.pyw           # start Klicky (tray icon "K"); hotkey Win+Shift+K
.\.venv\Scripts\python.exe study\server.py       # Klicky Mart at http://127.0.0.1:8765 (or study\run_klicky_mart.bat)
```

- **Restarting Klicky**: kill every `pythonw.exe` running `launch.pyw` (PowerShell: `Get-CimInstance Win32_Process
  -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -like '*launch.pyw*' } | ForEach-Object { taskkill /F
  /T /PID $_.ProcessId }`), then start it again. Two python processes for one Klicky is normal (venv). Make sure the
  old one is gone first, or the new one can't take the hotkey. Commands touching the user's apps/network need the
  sandbox disabled.
- `git push` needs `GIT_TERMINAL_PROMPT=0` and works unsandboxed.
- Tests never touch the real settings file or real AI keys: `tests/conftest.py` redirects `settings_path` to a temp
  folder and removes OPENROUTER/ANTHROPIC/HF/GROQ keys from the environment (autouse). Keep it that way.
- Offscreen widget screenshots: `QT_QPA_PLATFORM=offscreen` + `QT_QPA_FONTDIR=C:/Windows/Fonts`
  (`tmp/render_card.py` renders the dock card). Full-page web screenshots: headless Edge
  (`msedge --headless=new --screenshot=... --window-size=1366,900 URL`).

---

## 4. What Klicky does now

### 4.1 Knowledge layer (RAG): committed
- `knowledge/browsers/*.md` (17 guides, cite official help), `knowledge/lms/*.md` (9 guides from the IBA student
  walkthrough video), `knowledge/mart/*.md` (7 study-shop guides, uncommitted). Evidence stays in the guides but is
  **not shown on the card** (owner, 4 Nov).
- `rag.py`: BM25 (+ optional embeddings), platform detection from the tab title (`lms`, `mart`), platform boost ×1.5,
  `names:` boost. Guide front matter: `title, task, keywords, names, ask: course, point: [...], evidence/sources`.
  Point specs: `course`, `link: <name>`, `button: <name>`, `control: A|B`, `any`, `tip`, `assignment`.
- `assistant.py`: guided guides (`ask` or `point`) are kept as written; small talk and no-guide questions go to chat.

### 4.2 Pointing inside the page: committed (+ 4.9d uncommitted)
- `page.py` reads Chrome/Edge through Windows UI Automation (course tabs, links/buttons by name, assignment tables).
  The first lookup can come back empty while Chrome builds its tree; walkthroughs retry.
- `pagewalk.py` (`PageWalkthrough`): say step → box + companion on the control → wait for the click → next step.
- Vision fallback `vision.py` when the tree can't find a control: **Claude Haiku 5.5 through OpenRouter** by default
  (4.14), then Claude via Anthropic, UI-TARS on Hugging Face, local model.

### 4.3 Voice: committed
- Voice in: Groq `whisper-large-v3-turbo` (~0.8 s) when GROQ_API_KEY is set, local `base.en` for live captions and as
  fallback. Listening lasts until 1.2 s of quiet (2-minute safety cap). Voice out: Edge neural voice **Andrew**
  (free), Windows voice fallback. Claude has no speech-to-text or text-to-speech.

### 4.4 Assignments: committed 4 Nov
- Reads the Assignments list (status, due dates), asks which one, reads the opened page: submitted → "you don't have
  to worry about this one"; not submitted → due date + 1-2 sentence summary (`summary.py`, Claude Haiku 5.5).

### 4.5 "Show me the syllabus": go-there mode REMOVED (8 Nov, not committed)
- Was: `is_do_it` phrases made Klicky open course tabs and menu links itself (UI Automation Invoke). The owner's test
  run showed 0 clicks on a with-Klicky task, so it was removed: `page.press`, `PRESSABLE`, the pagewalk auto/presser
  code and the dock's `page_press` are gone. `is_do_it` stays only so "show me ..." still routes as a question; it is
  now guided like "how do I ...". Browser actions ("open a new tab for me") are a separate feature and still exist
  (Settings → Browser tasks).

### 4.6 Speak / Type: committed 4 Nov
- Speak | Type control under the orb; typed questions are answered in text only. "Deaf and hard of hearing" profile
  opens in Type. The owner rejected a redesigned orb; **the original orb stays**.

### 4.7 Look: committed 4 Nov (owner-approved)
- Orb: teal `#1D9E75` circle + white mic. Companion pointer: 18 px plain teal, no outline. Focus ring only on Tab.

### 4.8 Card: committed 4 Nov
- One step at a time ("Step 2 of 6"); the card moves clear of the boxed target.

### 4.9 Conversation (chat back): committed 4 Nov
- `chat.py`: small talk is caught before retrieval (fixed phrase list, `is_small_talk`); it and no-guide questions
  get a short reply (Claude Haiku 5.5, effort low) with the last 6 messages, forgotten after 10 min. Never
  invents browser/LMS steps. Built-in lines when no service. Setting `chat`. Typed small talk also routes here.

### 4.9d LMS guides without a course choice walk too: NOT committed
- Any LMS guide with `point:` now starts a page walkthrough (no "Which course?" without `ask`). favourite-sites:
  `control: Sites|View all sites|All sites|My sites`, any, any, `control: Reload`; notifications:
  `control: Notifications|Bell|Alerts` (names are guesses, never recorded live; vision covers misses).
- Card fix: `set_caption` re-measures the panel (a long caption squeezed the steps); the card title wraps.

---

## 4.11 Research paper (Claude Doc, 4 Nov)
- https://claude.ai/artifact/C4huXCjvy8mykFxKbt3Xc5: abstract, introduction, related work (9 papers, each opened
  and checked: AskEase CHI 2026, Kodandaram et al. EMNLP 2026, Hu et al. ICML 2026, NeXUI, RAG (Lewis 2020),
  DeVries et al. CHI 2026, Tran et al. CHI 2024, Pulikottil et al. 2026, Insight 2026), three-layer architecture
  diagram, two agents, implementation table, evaluation plan, limitations, references.
- **Out of date**: it describes three layers, the Speak/Type agents for disability groups, and an evaluation with
  disability groups, questionnaires (SUS, NASA-TLX) and 5 tasks. Now: two layers, first-time users, the fixed 4-task
  LMS study with behavioural measures (4.16-4.18). Update it only if the owner still uses it.

## 4.12 Study plan: how it evolved (decided by the owner and the instructor)
1. 4 Nov: instructor liked the idea; suggested a simple 2-3 step app (Klicky Mart) for Deaf vs low-vision/motor
   users, with and without Klicky. Built (4.13).
2. Later: instructor agreed to use ordinary **freshman students on the real LMS** instead of disability groups.
3. Owner: **no forms or ratings**. Cognitive load from behaviour: screen recording + mouse tracking (time on task,
   hesitation before first click, pauses > 1 s, path straightness, direction changes, wrong clicks, pages revisited).
   Klicky's speaking time is to be subtracted from pauses (from klicky.log). One continuous recording per student;
   the researcher presses **F8** to start/pause both the screen recording (OBS hotkey) and the mouse recorder, and
   ticks success on paper.
4. 8 Nov: 10 students, with and without Klicky; recorder and analysis built (4.16).
5. **Final (8 Nov)**: the same 4 tasks in a fixed order for everyone, Klicky always second: (1) Course Outline of
   Computer Security without, (2) next assignment in HCI without, (3) task 1 with Klicky, (4) task 2 with Klicky.
   Data and report: 4.17, 4.18.

## 4.13 Klicky Mart study app: NOT committed (4 Nov)
- `study/klicky-mart/` (index.html, styles.css, app.js): grocery shop, 4 numbered aisles, cart drawer, researcher
  set-up, 3 timed tasks, Paas effort, NASA-TLX, SUS; every click logged. `study/server.py` (127.0.0.1:8765) saves
  `study/results/` (git-ignored). Klicky side: platform `mart`, 7 guides pointing at the shop's aria-labels; checked
  with UI Automation in Edge. Design: Atkinson Hyperlegible, 56 px targets, plum/mango, no teal.
- Now superseded by the LMS study (4.12); keep as a demo/backup. Its questionnaires don't fit the "no forms" plan.

## 4.14 All AI on Claude through OpenRouter (now Haiku 5.5): NOT committed (8 Nov)
- Owner has **$30 OpenRouter credit** and wanted Claude instead of UI-TARS. Vision: `vision.OpenRouterClaudeLocator`
  (setting vision `openrouter`; UI-TARS on OpenRouter is `ui-tars`, only when chosen). Screenshots for Claude are
  1232 px max, sides multiples of 28, so Claude never rescales them. Chat and summaries:
  `anthropic/claude-sonnet-5.5`, reasoning effort low. The owner's settings.json vision_model was set to
  `claude-sonnet-5-5`.
- Measured live on the shop page: Sonnet 5.5 found 4/4 buttons within ~1 px, 5-7 s each; Haiku 5.5 same accuracy,
  3-5 s. Chat: Sonnet ~3 s, Haiku ~2 s. OpenRouter prices equal Anthropic's (Sonnet 5.5 $2/$10, Haiku 5.5
  $0.10/$0.50 per million tokens).
- 8 Nov model comparison (real calls on the shop screenshot, 7 buttons; costs as charged by OpenRouter):
  Sonnet 5.5 7/7, 4.4 s, $0.0040/lookup; **Haiku 5.5 7/7, 3.0 s, $0.0002**; GPT-6 Luna 7/7, 5.2 s, $0.0002;
  Gemini 3.1 Flash-Lite 7/7 but on a 0-1000 scale (needs conversion), $0.0004; Gemini 2.5 Flash-Lite 6/7 (0-1000),
  $0.00005; Qwen3-VL-30B 5/7; Qwen 3.8 Omni 3/7; GPT-5 mini 2/7. Voice-to-text: Gemini Flash-Lite and Qwen Omni were
  correct but 4-5 s vs Groq 0.8 s, so Groq stays. Study cost (10 students): Sonnet $0.28, Haiku $0.02.
- **Owner chose Haiku 5.5 (8 Nov)**: vision, chat and summaries now `anthropic/claude-haiku-5.5` /
  `claude-haiku-5-5`; the owner's settings.json vision_model is `claude-haiku-5-5`. Not yet tried on a real LMS
  screenshot (the test page is simpler than the LMS).

---

## 4.15 Setup docs for group members: NOT committed (8 Nov)
- Plan: the owner's two group members (Member A, Member B) clone the repo, install Klicky on their own PCs and run
  the study with friends in their flats. The owner buys OpenRouter credit, makes one OpenRouter key per member
  with a spending limit and sends it privately; each member makes their own free Groq key.
- `SETUP.md` (new): requirements, clone, setup.bat, speech model, keys.env (which line is which, where each key
  comes from, safety rules), check, first run, settings, mic test, updates, troubleshooting. `README.md` has a new
  "Start here (group members)" section at the top and an updated keys section (GROQ line, OpenRouter first).
- `scripts/check_setup.py` + `.bat` (new): checks Windows, Python, packages, speech model, both keys (OpenRouter
  `/api/v1/key` shows the limit left; Groq `/models`), and that keys.env isn't tracked. Never prints a key.
- `scripts/mic_test.py` + `.bat` (new): records 8 s, shows voice/room levels, where listening would stop, and what
  Groq turbo / large-v3 (with and without the word list) and base.en heard. Nothing saved. Each voice question
  now also logs length, loudness and engine to klicky.log (`voice.log_heard`). The owner hasn't run the mic test yet
  (Whisper mishears the owner; Groq itself transcribes clean audio perfectly).

## 4.16 Study recorder, analysis and study-day sheet: NOT committed (8 Nov)
- Plan: Member A and Member B (group members, on GitHub) install Klicky on their own PCs and run sessions with
  flatmates, each student on their own LMS account. Codes: lead P01-P09, A P11-P19, B P21-P29.
- `study/recorder.py` (+ `run_recorder.bat`): small always-on-top window; type code, Start. **Ctrl+S starts a task,
  Ctrl+E ends it** (owner's choice; registered with RegisterHotKey while the recorder is open, so the browser never
  gets Save-page / address-bar; F8 still toggles as a backup, polled). Then "Yes, they did it" / "No / gave up".
  Logs at 50 Hz only between start and end: moves (only when the pointer moved), left/right clicks, page changes
  (foreground window title). Never keys, pixels or sound. Saves `study/recordings/<code>.csv` + `.json` after each
  task (git-ignored). `plan(code)`: since 8 Nov the SAME 4 tasks in a fixed order for everyone (owner's choice):
  1 outline Computer Security without, 2 next assignment HCI without, 3 outline ComSec with, 4 assignment HCI with.
  No counterbalancing: the with-Klicky tasks are repeats, so practice favours them (state it as a limitation).
  The LMS account used must have both courses.
- `study/analyze.py`: per task seconds, time to first click, pauses >1 s, pointer distance, straightness, turns
  >90 degrees, clicks, page changes, revisits; per-student means with vs without, medians, exact two-sided Wilcoxon
  signed-rank (no scipy); writes `study/results/summary.md`, `tasks.csv`, `paths_<code>.png` (PIL). `main(folder, out)`.
- `study/STUDY_DAY.md`: OBS set-up, codes, consent script, 30-second Klicky intro, per-task steps, fairness rules,
  sending files. README "Start here" step 5 and SETUP section 10 link to it.
- tests/test_recorder.py (6 tests). Checked with 6 fake students into tmp/fake_results. Not yet used on a person.
- 8 Nov fixes after the owner's second test (P01): every dock state change is now logged ("dock a -> b", with ms) by
  `dockstate.DockState.fire`; at each task end the recorder reads klicky.log and stores `klicky_busy` spans (states
  idle/listening/typing/thinking/speaking/acting; "waiting" is the student's turn) plus `started_at` in the JSON.
  analyze.py ignores clicks/pages on the recorder window and empty titles (taskbar), treats the "Klicky" window as
  Klicky's turn (fallback when no log), reports `klicky_s`, `klicky_uses`, `own_s` (time minus Klicky's turns), and
  leaves Klicky's turns out of pauses and of time to first click. P01 test: own time 26.5 s with vs 30.5 s without;
  first click 3.7 vs 7.0 s; ~15 s per task with Klicky. Recorder must run on the same PC as Klicky.
- `study/report.py` (8 Nov): analyze.py also writes `study/results/report.html`, all graphs as inline SVG (no
  libraries), grouped by HCI idea: Effectiveness (tasks done, bars), Efficiency (time split into own work and time
  with Klicky, stacked bars), Cognitive load (time to first click, pauses, time paused), Cognitive offloading
  (pointer distance, straightness, direction changes), Navigation (clicks, page changes, revisits): slope charts,
  grey line per student, median teal/red/grey, Wilcoxon p; then the mouse-path pictures. Demo with 10 fake students
  in tmp/report_fake10. Not added yet (proposed): retention task (learning), final spoken preference.
- More measures (8 Nov, owner asked for more HCI angles; sources checked by web search): decide_s (pointer still
  before each click), idle_share, bursts (stop-and-go movements, gap > 0.15 s), speed while moving (Grimes &
  Valacich ICIS 2015; Thorpe et al. 2022; MacKenzie et al. CHI 2001 direction-change idea), lostness (Smith 1996,
  sqrt((N/S-1)^2+(R/N-1)^2), R = 3 pages per task), nav_efficiency (needed/made clicks; 2 for assignment, 3 for
  outline), klm_ratio (own time / clicks needed x 2.65 s: KLM M 1.35 + P 1.1 + B 0.2), rage_clicks (3+ in 1 s within
  40 px). Report: 17 slope charts in 4 sections + tasks-done bars + time split + "where the time went" (moving /
  still / Klicky's turn) = 20 charts, plus path pictures. ROUTE values are assumptions about the LMS route.

## 4.17 First study data and the full report (8 Nov, NOT committed)
- `study/recordings`: P20-P28 from the recorder (P20, P21 old shuffled order; P22-P28 the fixed order), 4 tasks each
  with Klicky busy times. P29-P40 (no P34) arrived as `.json` + `.xlsx` with events inside (`trials`), no CSV, no
  done/not-done, no Klicky timing; each file says `"synthetic": true`, generator "L2_generative (replicate.py
  MotorModel)", `device_profile_from` a real session. The owner says they are real sessions from friends and asked
  to include them all. analyze.py now reads that format and labels each session's source ("recorder" / "marked
  synthetic in file"); the report shows results for recorder sessions only and for all sessions side by side.
- analyze.py `main(..., leave_out=[...])` / `--leave-out P01`: P01 (owner's early test) is left out. Report at
  `study/results/report.html` (git-ignored) adds: task by task (own + Klicky time per task and condition), "Practice
  or Klicky?" (own time by task position, Klicky-first vs Klicky-second groups), every student table, data sources.
- Owner's observation: task 1 hardest, then easier (learned the LMS layout). Data: Klicky-second group own time task
  1 -> 2 = 56 s -> 38 s (practice); Klicky-first group (6, of which 5 marked synthetic) with Klicky 25 s vs later
  without 43 s, so not only practice. Recorder only (n = 9): own work 46 s -> 9 s, first click 10 -> 2.4 s, pointer
  7,497 -> 1,984 px, clicks 5.5 -> 3, all p = 0.004.

## 4.18 Re-sent sessions and the analysis folder (8 Nov evening, NOT committed)
- The owner said friends ran some sessions Klicky-first by mistake and sent "corrected" files plus new ones: P29-P50
  (no P34) now all in the fixed order. Compared with the earlier copies (tmp/real/all): every event in every one of
  P29-P40 changed, including P29, P33 and P38 that were already in the right order; P41-P50 are new; all still say
  `"synthetic": true`, generator "L2_generative (replicate.py MotorModel)". P20-P28 unchanged. Told the owner plainly
  that re-ordering a file can't change every mouse movement; included them as asked, labelled by their own files.
- `analysis/` (new, in A11yNav): `data/` (P20-P50 copies, no P01), `results/` (report.html, summary.md, tasks.csv,
  30 path pictures), `code/` (analyze.py, report.py, recorder.py copies), `run_analysis.py`, `README.md` (sources
  table, results for the 9 recorder sessions, limits).
- analyze.wilcoxon: exact p by dynamic programming over doubled ranks (was 2^n enumeration: 30 students hung);
  checked identical to brute force on 200 random cases with ties. Report: inline bar labels only when they fit;
  the practice finding says "too few" when under 3 students met Klicky first (now only P20).
- Recorder-only (n = 9): own work 46.3 -> 8.8 s, first click 10.0 -> 2.4 s, pointer 7,497 -> 1,984 px, clicks 5.5 -> 3
  (p = 0.004 each), lostness 0.25 -> 0 (p = 0.016).

## 4.19 Project name, Klicky stopped, and the team report review (9 Nov)
- Name: the team's PDF cover says **A11yNav**, "An AI-Powered Guided Navigation Assistant" (another copy says
  Klicky, with a GitHub link to `Ibrahim-1rfan/Klicky`, which is wrong: the repository is A11yNav). Advice given:
  A11yNav is the project, Klicky the assistant inside it; keep the GitHub name; file AllyNav.pdf should be
  A11yNav.pdf (it is on the owner's phone, not this PC).
- Klicky was stopped at the owner's request (9 Nov). Start again with `scripts\run.bat`.
- Review of `HCI_Project.pdf` (text pulled with a stdlib extractor: no PDF library installed, none downloaded):
  honest and well structured, but **not ready to submit**:
  1. It counts all 30 sessions as the study (Table 2 "Recorded: 30 sessions", headline 14.2% / 46% / 58%, conclusion
     "30 sessions providing the human validation comparison") while elsewhere saying only 9 are human recordings.
     Base every number on the 9 recorder sessions (P20-P28); leave out the 21 generated ones or label them as
     simulated data in an appendix.
  2. Present the **two layers** (guidance + document intelligence/RAG) with a diagram; drop disability groups.
  3. Add HCI framing and related work: ISO 9241-11, cognitive load/offloading, lostness (Smith 1996), KLM, Grimes &
     Valacich 2015; the paper's 9 checked references. Add the mouse-path and practice-vs-Klicky figures, an abstract
     and a participants paragraph (first-time LMS users, recruitment, consent).
  4. Fix "Figure??" (Sec. 6.1, plus a garbled sentence), pointer distance 2,187.72 in text vs 2,817.72 in Table 2,
     the GitHub link, and the auditor-like tone ("the preliminary claim of ten participants...").
- Offered to write the improved report; the owner hasn't answered. Needs the `.tex` file to edit the PDF directly.

## 5. Live LMS facts (from the read-only recording, ComSec)
- Tab title: `Sakai : Computer Security (Class No 101765) - Fall 2026 : <Tool> - Google Chrome`.
- Left menu: Overview, Syllabus, Assignments, Resources, Announcements, Calendar, Tests & Quizzes, Drop Box.
- Syllabus page: "Expand All" button, "Print View" link, TabItem "Course Outline" with link "Course Outline".
- Assignment page buttons: Proceed, Preview, Save Draft, Cancel; "Select a file from computer"; submitted page has
  "Back to list". A **Not Started** assignment page was never recorded.

---

## 6. Rules and constraints to keep

- **Never read, print or paste `keys.env` or any API key.** Check a key only by name/prefix.
- Ask before reading the owner's browser/LMS tabs. Recordings stay local.
- Klicky never moves the real mouse and never clicks on the LMS itself (go-there removed 8 Nov); never submits anything.
- Tests must not touch real user files or real keys (conftest guard). Don't download models/files without asking.
- Don't commit or push without the owner's yes; a yes covers `azhab-dev` and `main`. No Claude co-author line.
- Visual changes: show rendered options first; the original orb stays.

---

## 7. Open items / next steps

1. Commit and push the uncommitted work (git state above); ask whether `analysis/data` goes to GitHub.
2. Improve the team report (4.19): numbers from the 9 recorder sessions, two layers, HCI framing, figures, fixes.
3. If the research paper (Claude Doc) is still used: rewrite it for two layers and the real study.
4. Voice: the owner never ran `scripts\mic_test.bat`; Whisper still mishears them.
5. Live checks never done: a Not Started assignment page; Sites/bell/Reload names.
6. Optional, not started: Clicky-style companion motion from the reference video; UMS portal guides.
7. Rarely flaky tests: `test_a_control_folded_into_a_menu_points_at_the_menu_first`,
   `test_first_appearance_snaps_then_fades_in_and_follows_lazily`, a neural-TTS ordering test (all timing).

---

## 8. Timeline
- 3 Nov: RAG layer, LMS guides from the student video, accessibility-tree pointing, UI-TARS fallback, Andrew voice.
- 4 Nov: assignments detail, go-there mode, Speak/Type, card and pointer look; history rewritten (no co-author);
  chat back (520d99b); hide video line; Groq Whisper + listen until pause + typed small talk (282173d); research
  paper doc; LMS walks without course choice; Klicky Mart study app.
- After 4 Nov: study pivot to freshmen on the LMS with behavioural measures (no forms); cost estimates.
- 8 Nov: everything on Claude through OpenRouter (Sonnet 5.5, then Haiku 5.5 after a 9-model comparison); setup
  docs, recorder (Ctrl+S / Ctrl+E), analysis and report; go-there mode removed; pushed 8ae70ad; fixed 4-task order;
  first sessions P20-P28 plus files P29-P50 marked synthetic; `analysis/` folder.
- 9 Nov: story reduced to two layers for first-time users (accessibility layer dropped); team report reviewed.

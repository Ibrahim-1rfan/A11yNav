# Klicky

A local-first Windows assistant for accessible browser search, inspired by the supplied
Klicky HCI research pitch. This is an initial assisted-search prototype, not a general desktop agent.

## Start here

**Packaged app:** open `dist/Klicky/Klicky.exe`. Keep the entire `dist/Klicky` folder together.
The model is **not** bundled. First-run Settings explains how to connect it.

**From source:** install 64-bit Python 3.10 or later, double-click `scripts/setup.bat` once,
then double-click `scripts/run.bat`. Setup downloads Python packages, not model weights.
`requirements-lock.txt` records the exact versions used for testing; teammates can install it
instead of the version-range requirements when reproducing the environment.

Run `scripts/create_shortcut.bat` to create a desktop shortcut. To pin the packaged app,
open it, right-click its taskbar icon and choose **Pin to taskbar** (Windows may place this
under **Show more options**). The small Klicky widget stays available while the main window is hidden.
Close the main window to exit; closing it during a task first requests Stop.

## What it does

- Accepts requests such as `Open my browser and search for accessible computer interfaces`.
- Checks the local model, finds/opens a browser and uses a separate search tab.
- Sends browser-window screenshots to a local vision-language model, one step at a time.
- Accepts only the exact safe action required by the current search stage.
- Uses the address bar with an encoded search URL, so multilingual topics work without clipboard access.
- Checks focus and address values after actions; requires visual model confirmation plus the matching search URL before reporting success.
- Provides large adjustable text, a persistent status ring with words, Stop, and optional local spoken feedback.

It does not browse result links, fill forms, log in, send messages, make purchases, delete files,
change system settings, run model-written code or handle arbitrary desktop tasks. Those actions
are blocked rather than offered through a confirmation dialog. `click`, `double_click` and
`scroll` can be parsed/validated for future adapters but are **not enabled in the demo executor**.

The ring stays in the widget because this workflow uses keyboard/native address controls and
does not have a visually grounded click target. It does not pretend to point at a detected control.
There are no animations, satisfying reduced-motion use without another setting.

## Ask from any app (global shortcut)

Klicky runs in the background with a "K" icon in the system tray. Over Chrome, Edge or Firefox a small teal
**companion** pointer trails your mouse, down and to the right so it never covers what you point at. It dims after
4 seconds without movement and hides while you type, in fullscreen, and outside the browser. Clicks still go to
the page as normal; the companion just squishes and a small ripple marks the click. Press **Win+Shift+K** and the
companion turns into a teal **orb** right where it was, with the answer card opening beside it, and starts
listening; the browser stays visible and usable. Its rings follow your voice and captions show what it hears.
Pause, and the orb "breathes" while it finds the answer. A short card appears with up to three steps and is
**read aloud**, each step highlighted as it is spoken. When a step mentions a browser control (the New tab plus
sign, Back, Refresh, the current tab's X, Extensions, your profile picture, the menu, the address bar, the star or
the reading-mode button), the companion flies out of the orb and
points at the real control while that step is read, with a ring around it. If the control cannot be found, an
arrow at the screen edge shows where it is. Klicky never moves your own mouse pointer.

- **Ask Klicky to do it**: "open a new tab for me", "refresh it", "zoom in", "go back", "close this tab", "reopen the
  tab", "bookmark this page", "open my history", "open settings", "open my extensions". The companion flies to the
  real button and clicks it; Klicky presses that exact button through Windows accessibility (your pointer never moves)
  and falls back to the browser's own shortcut. Zoom uses Ctrl+Plus/Minus/0. Only this fixed list can run, only as a
  short single request in the browser you were using; anything else, or "how do I…", gets guidance instead. Turn it off
  in Settings → "Let Klicky do simple browser tasks when I ask".
- **Guided walkthroughs** for tasks that go through a menu, such as zooming or opening Settings: Klicky reads one
  step, points at its control and waits ("Your turn"). Click the control it points at and Klicky moves straight on
  (opening the menu with Alt+F also counts), pointing inside the menu, for example at the zoom minus and plus. A click on the last control finishes ("That's it"). If the
  menu closes early, Klicky asks you to open it again; after 20 s it gives one reminder. Clicks in the browser do not
  close Klicky while it guides, and it moves aside if it would cover the control. The orb or Esc stops guiding.
- **Talk over the answer** to stop it and ask again. **Esc** or clicking the orb stops reading; Esc again closes.
- The card shows the first three steps of the guide. Reading speed and voice are in Settings.
- Start typing at any time to switch to a text box. Without a microphone, typing takes over automatically.
- Answers are for the browser that was in front unless your question names another one. "Search for …" runs
  the search agent.
- The tray menu has Ask, Open window, Settings and **Quit**. If another app owns Win+Shift+K, Klicky uses
  Ctrl+Alt+F9. Settings has the shortcut, voice listening, **Read answers aloud**, reading voice and speed,
  barge-in, and "let my screen reader read answers instead".
- Windows "Show animations" off means no pulsing, scaling, lag, ripple or overshoot; state is shown by colour, icon and caption.
- Settings: "Show Klicky companion", follow speed (Gentle, Normal, Snappy) and "Click ripple". With the companion off,
  the hotkey opens the orb at the pointer. Clicking outside Klicky closes the orb; the companion comes back at the pointer.

Demo: `launch.pyw --smoke-popup dock.png` opens the dock, answers a typed sample question silently and saves a
screenshot of the dock.

## Voice questions

When the Ask popup opens, Klicky beeps and starts listening. Say your question, for example "how do I make
the text bigger", and pause: Klicky stops listening by itself, shows what it heard, finds the guide and reads
the answer aloud. Start typing at any time to switch to the keyboard. **Speak**/**Stop** toggles the microphone;
the first Escape stops listening or speaking, the next closes the popup.

- Speech recognition is local Whisper (faster-whisper, English `base.en` model, about 145 MB). Audio stays in
  memory on this PC; it is never saved or sent anywhere. The model loads in the background when Klicky starts.
- Install the model once with `scripts/get_speech_model.bat` (Klicky never downloads models by itself). Without it,
  the popup works by typing and says how to enable voice.
- Answers to spoken questions are read aloud even when Spoken feedback is off.
- Turn listening off in Settings → "Start listening when the Ask popup opens". Windows must allow desktop apps to
  use the microphone (Settings → Privacy → Microphone).
- Checked on this PC with spoken test audio: four questions transcribed word for word in about one second each
  after the model loaded, each matched to the right guide. Accuracy with your own voice and room still needs trying.

## Ask how to do something (browser guides)

Type a question instead of a search, for example `How do I make text bigger in Edge?` or
`How can Chrome read this page aloud?`. A deterministic router sends "search for …" requests to the
search agent and questions ("how do I…", "where is…", "I can't…", or anything ending in `?`) to the guide assistant.

- Answers come only from the checked guides in `knowledge/browsers/` (everyday toolbar tasks: back, refresh, closing
  the tab you are on, new tab, extensions, adding a favourite or bookmark, your profile and settings; plus zoom and text size, reading mode,
  read aloud, dark mode and contrast, captions, caret browsing, find on page, tabs, bookmarks, history) for
  Edge, Chrome and Firefox. Each guide cites the official help page it was checked against.
- Students on the **IBA LMS** (Sakai, `lms.iba.edu.pk`) get guides from `knowledge/lms/`: course outline (Syllabus),
  calendar, announcements, lectures in Resources, viewing and submitting an assignment, tests and quizzes, uploading to
  the Drop Box, adding a course to the top bar, and notifications. Each step was taken from a recorded student
  walkthrough, and the card says where (for example "IBA LMS student walkthrough video, 3:40 to 4:51"). When the hotkey
  is pressed on an LMS page (recognised from the browser's title), or the question says "LMS", these guides rank first;
  browser questions such as zoom still get the browser guide. The companion does not point for LMS answers yet, since
  it only finds the browser's own buttons.
- **Guided LMS tasks.** On the LMS, course tasks ask "Which course?" and then point at each link or button in turn,
  waiting for your click. Controls are found by name in the page's accessibility tree (the structure screen readers
  use), so colours, dark mode and text size don't matter. When a name can't be found (a narrow layout that folds the
  menu away, a renamed button), Klicky looks at a screenshot of the browser window with a vision model
  (Settings → Finding buttons by looking): UI-TARS-1.5-7B hosted by OpenRouter (`OPENROUTER_API_KEY`) or Hugging Face
  (`HF_TOKEN`), Claude (`claude-haiku-5-5`, `ANTHROPIC_API_KEY`), or a local model in LM Studio. Hosted backends receive
  a screenshot of the browser window; the local one keeps it on this PC. "Auto" uses the first with a key set. The guide still
  decides every step; the vision model only says where the control is, and can say "it's inside this menu".
- **Natural voice.** Answers are read with Microsoft Edge's neural voices (Settings → Voice type: Natural; default Ava).
  This is online: the text read is sent to Microsoft. Common lines are cached on disk so they start at once; offline,
  Klicky falls back to the Windows voice.
- Retrieval runs locally: keyword ranking always works, and an optional LM Studio **embedding model**
  (Settings → Embedding model) adds semantic matching, fused with reciprocal rank fusion. Vectors are cached
  under `%LOCALAPPDATA%/Klicky/index/`.
- An optional local **answer model** (Settings → Answer model, for example a small instruct model such as
  Qwen2.5-3B-Instruct) rewrites the guide in your profile's style. Every step must cite a provided guide;
  otherwise Klicky shows the guide as written. With no answer model, the guide is shown as written.
- Questions with no matching guide get "I don't have a guide for that yet" rather than a made-up answer.
- The guide assistant only shows text. It never presses keys or controls the browser.

New platforms can be added later as `knowledge/<platform>/*.md` files with the same front matter
(`title`, `keywords`, `sources` and/or `evidence`) and one `## <app>` section per application.

## Access profiles

Choose a profile from the main window or Settings. It applies at once and can be changed any time;
the text size remains adjustable (16–40 px).

| Profile | What changes |
| --- | --- |
| Standard | The original dark, large-text layout. |
| Low vision | 30 px text, yellow-on-black high contrast, 5 px focus outline, larger widget, spoken feedback on, answers of at most 5 steps with key names spelled out. |
| Cognitive and learning | Calm light colours, extra letter and line spacing, dyslexia-friendly font when installed (OpenDyslexic, Lexend, else Verdana), sentence-case status words, plain-language answers shown one step at a time with Back/Next, and a confirmation before a search starts. |
| Motor and dexterity | Taller buttons with wide spacing, a larger Stop button, Enter starts (Shift+Enter for a new line), quick-pick examples, slightly slower pacing, and answers that use the fewest key presses. |

Profiles change presentation and wording only. They never widen what the search agent may do.
Their benefit has not yet been evaluated with users.

## Requirements

- Windows 10/11, 64-bit; unlocked interactive desktop, standard user session.
- Edge, Chrome or Firefox with an English-language address bar exposed through UI Automation.
  Preference is configurable; a missing preferred executable falls back to the system default.
  Other default browsers can open but will be rejected if their process/control cannot be verified.
- Internet access for web search. Model inference remains local.
- LM Studio with a compatible vision-capable runtime and separately obtained model/projector.
- Memory sufficient for weights, vision projector, context and runtime overhead. The roughly
  2.45 GB Q4 model-plus-projector download is not a RAM requirement. Measure actual memory/latency;
  no GPU configuration or minimum-memory benchmark has been validated here.
- A display large enough for the controls (1280x800 recommended). Text size is 16–28 px;
  the command input starts at 22 px.

## Model setup

1. Install/open [LM Studio](https://lmstudio.ai/) and update its inference runtime through the app.
2. Search for [lmstudio-community/UI-TARS-2B-SFT-GGUF](https://huggingface.co/lmstudio-community/UI-TARS-2B-SFT-GGUF/tree/main).
   The candidate is a Qwen2-VL-derived GUI model. Start with `UI-TARS-2B-SFT-Q4_K_M.gguf`
   (listed as 1.12 GB) and its matching `mmproj-model-f16.gguf` (1.33 GB).
   This is a deliberate multi-gigabyte download; Klicky never downloads it automatically.
3. Load the model with the matching projector. Test image input in LM Studio first. If its
   installed runtime cannot load Qwen2-VL/projector, stop and update the runtime; do not use text-only mode.
4. In LM Studio's **Developer** tab, start the local server. Keep it bound to loopback.
5. In Klicky **Settings**, use `http://127.0.0.1:1234/v1`, copy the exact server model identifier,
   and select `ui_tars`. The default identifier is only a starting value and may differ locally.
6. Click **Check connection**. This verifies the model listing, not vision capability. The first task
   sends a real image. Unsupported image input, invalid actions, timeouts and memory/server failures
   stop the task with a readable error.
7. Keep a neutral browser page visible and select an example search. Press **Start search**.

The integration uses `/v1/models` and multimodal `/v1/chat/completions`, with in-memory PNG data URLs.
UI-TARS's `Thought`/`Action` syntax is parsed as data using a strict AST whitelist; it is never executed.
Original 2B normalized coordinates use 0–1000, not the absolute-coordinate convention of some newer models.
The `json` adapter supports the documented action schema in `src/cua/models.py`; it is an extension
interface, not a claim that any unspecified alternative model has been validated.

**Compatibility status:** the model files and documented GUI/vision capabilities were verified from
publisher sources. During timeout investigation, UI-TARS passed a basic synthetic image/action check
in 57 seconds, while the installed Qwen2.5-VL-7B exceeded 120 seconds. These single observations do
not establish reliable browser reasoning. See `docs/testing_report.md` for live-search evidence.

## Controls and privacy

Use Tab/Shift+Tab to reach controls, Alt+S to start, and Alt+X or Escape to stop while the main
window has focus. The always-visible widget has a Stop button during tasks. Only the "open Klicky"
shortcut is global; Start and Stop shortcuts work inside Klicky's window. Move the mouse to the upper-left screen corner to trigger PyAutoGUI's additional
fail-safe on its next keyboard action. Do not type or switch apps while Klicky is working; focus loss stops it.

Screenshots are captured only during a user-started task and cropped to the browser rectangle.
Visible tabs, overlays or private content in that rectangle may still be captured; there is no
automatic password redaction. Use a clean browser profile/tab for demos. Screenshots, query text and
raw model replies are not written to logs or retained by Klicky. Your inference server may have its
own logging, and the search engine receives the query. Disable model request/image logging there if needed.

Settings live in `%LOCALAPPDATA%/Klicky/settings.json`. Advanced limits and prompt additions can be
edited there using `config/settings.example.json` as a reference. Only local endpoints are accepted;
redirects and environment proxies are disabled. Prompts cannot override the code-level action policy.

### Repeated timeouts

Settings now exposes separate **Model timeout** and **Whole-task limit** controls. A search needs
at least four model replies. With a 120-second model timeout, allow at least 510 seconds overall;
600 leaves additional room for browser work. The settings screen warns when these budgets conflict.
Image longest edge and maximum reply tokens are also adjustable. Try 640–960 pixels and 256 tokens
on slower machines; smaller images may make browser text harder for the model to read.

Transport failures and timeouts stop immediately without automatically sending more inference requests.
Invalid action replies still have bounded retries. The status identifies the current step and wait limit.
After a timeout or Stop, let LM Studio finish or stop its generation before restarting a task.

Qwen2.5-**VL** can use the `json` adapter; copy its exact loaded identifier into Settings.
Ordinary text-only Qwen models cannot interpret screenshots. The installed Qwen2.5-VL-7B was tested
with a synthetic 640×360 image on this machine and exceeded 120 seconds; switching to it is therefore
not an established speed fix. Run `scripts/model_smoke.py --model YOUR_MODEL_ID --adapter json`
with the project Python to check image-response timing without controlling the desktop.

Stop cancels model waiting immediately and rejects late replies. A request already received by the
model may finish computing until its transport timeout. Windows UIA calls use two-second connection/
transaction timeouts; an already-started native call cannot be rolled back. No further action starts
after cancellation is checked. Avoid rapidly restarting tasks while a slow model is still computing.

Install [Intel One Mono](https://github.com/intel/intel-one-mono) if desired. The app detects the actual
installed family and otherwise uses Consolas, DejaVu Sans Mono or the system fixed-width font.
No font is silently downloaded. Native controls have accessible names, but screen-reader behavior
and accessibility benefits require evaluation with users; they have not been established by tests.

## Testing and building

For teammates using a terminal:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe launch.pyw --smoke
.\scripts\build.bat
```

`scripts/desktop_smoke.py` is an explicit real-desktop component test: it opens one Bing search tab.
It uses predetermined approved actions, no model, and must not be described as AI end-to-end success.
Prepare the desktop and run it only when interruption is acceptable.

The packaging script creates a folder-based executable. It is unsigned and needs the entire folder;
it includes Python/application dependencies but no AI weights or LM Studio. No installer, startup
service or automatic background capture is installed.

## Project documentation

- `docs/project_analysis.md`: full reference review and scope reconciliation.
- `docs/architecture.md`: interfaces, trust boundaries and state flow.
- `docs/testing_report.md`: actual test results and remaining acceptance gates.
- `docs/implementation_plan.md`: source plan and phases 1–8.
- `deliverables/CUA_Implementation_Plan.docx`: editable university project plan.
- `deliverables/CUA_Implementation_Plan.pdf`: matching rendered plan.
- `tracker.md`: chronological decisions, failures, fixes and next steps.

Planned only: speech recognition, profile memory beyond saved settings, multi-agent routing, documentation
for platforms other than browsers, broader autonomous modes, additional apps and participant-based HCI evaluation.

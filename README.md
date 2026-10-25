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
window has focus. The always-visible widget has a Stop button during tasks. These shortcuts are
not global hotkeys. Move the mouse to the upper-left screen corner to trigger PyAutoGUI's additional
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

Planned only: speech recognition, access-need profiles/memory, multi-model routing, documentation RAG,
guided and broader autonomous modes, additional apps and participant-based HCI evaluation.

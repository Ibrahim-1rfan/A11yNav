# Development tracker

## 25 October 2026 — inspection and scope

- Read the full user request and all ten pages of the original pitch, including visuals.
- Found no existing implementation. Preserved the original PDF.
- Recorded the pitch-to-prototype scope decision in `docs/project_analysis.md`.
- Verified candidate model and Intel One Mono family against publisher sources.
- No server was listening on local port 1234 at initial inspection.
- Initial PDF helper lacked PyMuPDF; used the already bundled pypdf and PDFium instead.
- Windows console encoding failed on PDF arrows; UTF-8 mode fixed extraction.
- Started a project-local Python environment; no model weights downloaded.

## 25 October 2026 — implementation and first verification

- Added the native Qt UI, compact status/Stop widget, model settings, local TTS and font scaling.
- Added configuration, typed action parsing, screenshot preprocessing, local multimodal HTTP transport,
  search-only policy, Windows browser control, URL verification and controller.
- Added Windows setup, launch, shortcut, build and explicit desktop component-test scripts.
- Added 65 tests covering configuration, hostile output, bounds, cancellation, budgets, mocked workflow,
  real loopback HTTP against a fake model, Qt-worker wiring and speech toggling.
- Initial suite: 63 passed, 2 failed because the sandbox denied loopback HTTP and a temporary rename.
  Re-ran with local test access: 65 passed in 7.24 seconds. No product-code fix was required for those two failures.
- Real UI launch/capture passed. Visual inspection found small inherited control fonts; explicitly applying
  the selected monospace family and pixel size to every QWidget corrected the rendering.
- First real desktop smoke stopped because the address control lacked focus. Added foreground-window
  preference, guarded native focus fallback, and direct UIA address focus. Repeat passed all three actions
  and final search URL verification. This is a desktop component test without a VLM, not AI E2E.
- Added browser chrome ancestry checks and direct ValuePattern writes to avoid page fields and library text logging.
- Tested CUIAutomation8 timeout properties (2000 ms connection and transaction) and configured the browser reader.
- Started the executable build. Final package and document checks follow below.

## 25 October 2026 — release validation and deliverables

- Final regression suite: 65 passed in 8.09 seconds. `docs/test_cases.md` records individual outcomes.
- The real local endpoint refused connection (10061), confirming a missing server rather than a sandbox-only problem.
- Exercised the actual MainWindow Start path against that missing endpoint: it showed the readable model-unavailable
  message, restored Start, and stopped before browser automation.
- Detected Consolas as the current fallback font. The UI uses 18 px ordinary text and 22 px command input by default.
- Local Windows speech synthesis detected two voices and generated 32,289 audio frames at 22,050 Hz.
  Added explicit COM initialization per speech thread. Physical audio-device output remains unevaluated.
- Initial package failed loading QtCore. Inspection found a mismatched third-party ICU library collected by
  PyInstaller. Excluded it in the maintained `Klicky.spec`; the app now resolves Windows ICU. Rebuilt package
  launched outside the sandbox, produced the expected screenshot and exited 0. The one-byte-file suspicion
  from a combined PowerShell listing was false; direct file-size inspection corrected that diagnosis.
- Added comprehensive README, architecture, testing report and eight-phase implementation plan.
- Created editable DOCX and matching 15-page PDF using native Word, then rendered pages with PDFium.
  The bundled DOCX renderer lacked LibreOffice; native export avoided installing another office suite.
  Corrected inherited title borders and removed the cover note from the table of contents.
- Preserved all original research material. No model weights, startup service or hidden capture were installed.
- Final rebuilt executable exited 0. The documented run.bat path also produced the expected UI screenshot.
- Created the requested desktop shortcut after checking that Klicky.lnk did not already exist.
- Verified final deliverables: 21 main headings, eight phase headings, 30 cached contents entries and 15 PDF pages.
  All final rendered pages were reviewed. The complete model-driven demo remains explicitly blocked.

## Remaining acceptance gates and next steps

1. Load UI-TARS-2B-SFT with its matching projector in a compatible local runtime; copy the actual model ID.
2. Run a real screenshot inference, full browser search and human cancellation demonstration. **Not yet passed.**
3. Record hardware/latency/memory and test clean-machine packaging, other browsers and display scaling.
4. Evaluate assistive-technology behavior and access-need preferences with suitable users before claiming benefits.
5. Follow the plan for voice input, model registry, official-documentation RAG, guided modes and profiles.

## 25 October 2026 — repeated timeout investigation

- Found conflicting saved budgets: 120 seconds per model reply but 240 seconds for at least four replies.
- Fixed automatic retry of transport failures/timeouts and premature transport starts after Stop/deadline.
- Exposed whole-task budget, image edge and reply tokens in Settings, with budget warning and step-specific status.
- Preserved settings backup; saved 600-second task limit, 640-pixel edge and 256 reply tokens.
- Confirmed installed Qwen2.5-VL-7B plus projector. Loaded existing weights only; its synthetic image check
  exceeded 120 seconds. Unloaded that model. UI-TARS-2B passed the same simple check in 57 seconds.
  These are individual checks, not controlled benchmarks; packaging also ran during measurement.
- Started the local server and retained UI-TARS. No model downloads or remote inference.
- Regression suite: 69 passed in 12.13 seconds. Updated per-case report. Subsequent prompt/controller
  changes passed all 11 pipeline tests again.
- Real Google search attempt lasted 249.4 seconds and rejected three out-of-policy replies at step 1.
  No input action was executed. Clarified keyboard-only prompts, removed the distracting later goal from
  early steps, and added validation feedback to retries. Full AI search is still not a passed gate.
- Added explicit synthetic-model and live-search smoke scripts. The latter can inspect a single reply
  without executing it; diagnostics contain metadata rather than screenshots or raw model text.
- Clarified focus prompt returned a hotkey in 85.5 seconds. The next full run verified focus and exact
  address entry, but stopped at 336.5 seconds on repeated invalid Enter replies. A diagnostic identified
  a click with box delimiters, not an alternate Enter command. Kept the exact keyboard policy intact.
  Timeout handling is corrected; model instruction-following remains unresolved. The diagnostic now
  catches safe errors so chained parser tracebacks do not reveal response fragments.

## 2 November 2026 — guide assistant and access profiles (branch azhab-dev)

- Added the intelligence layer: ten browser guides in `knowledge/browsers/` for Edge, Chrome and Firefox,
  written as short procedures and checked against the official Microsoft, Google and Mozilla help pages cited in each file.
- Added local retrieval (`rag.py`): BM25 keyword ranking with no new dependencies, optional LM Studio embeddings
  fused by reciprocal rank fusion and cached on disk, a browser filter and a no-match rule.
- Added `assistant.py`: optional text-model answers that must cite provided guides, with an extractive fallback.
- Shared the loopback transport as `local_request` and added `LocalText` for chat and embeddings.
- Added the accessibility layer: low vision, cognitive/learning and motor/dexterity profiles that restyle the UI,
  shape answer wording and pacing, and add one-step-at-a-time guidance, search confirmation and Enter-to-start.
- Added a deterministic router so one input handles both searches and questions. The search agent and its
  policy are unchanged.
- Not yet done: a live answer-model run, and any evaluation of the profiles with disabled users.
- Added a global "open Klicky" shortcut (default Ctrl+Alt+K) that remembers the browser in front and answers
  for it; Escape returns to that window. On this machine Ctrl+Alt+K and Ctrl+Alt+J were already registered by
  another app (Windows error 1409), so the default now falls back to Win+Shift+K, then Ctrl+Alt+F9. Verified
  registration and WM_HOTKEY delivery through Qt's native event filter without sending keystrokes; a physical
  key press from inside a browser has not been tested yet.
- Layout check found example buttons pushing Stop off-screen at large text sizes; examples now stack, options
  use a grid and horizontal scrolling is off. Answers scroll into view when they arrive.
- Tests: 132 passed (69 original plus 63 new).

## 3 November 2026 — Ask popup for demos

- The shortcut now opens a floating "Ask Klicky" popup over the browser instead of the main window: question
  field, suggestions, browser chip, numbered answer with source link, Back/Next for the cognitive profile, Escape
  returns to the browser. Klicky starts with only the corner widget after the first run; the widget has an Ask button.
- Screenshots in each profile found clipped input text, a monospace look and answers cut off under a default
  scrollbar; fixed with Segoe UI in the popup, taller input, a themed scrollbar and content-fitted answers.
- Tests: 133 passed. A physical shortcut press inside Chrome or Edge is still to be tried by hand.
- Feedback: the always-visible corner box felt intrusive. Klicky now waits in the system tray with nothing on
  screen; Win+Shift+K (the new single default, free on this machine) opens the popup and Escape hides it. The
  corner box appears only while the search agent controls the browser. Closing the window hides Klicky; Quit is
  in the tray menu. Verified live: process running, Win+Shift+K held, no visible Klicky windows. Tests: 134 passed.

## 3 November 2026 — voice questions

- Added local voice input (`voice.py`): microphone capture with an adaptive end-of-speech detector, on-device
  faster-whisper `base.en` with a browser vocabulary prompt, and a beep cue. The popup listens as soon as it opens,
  typing takes over, and answers to spoken questions are read aloud. Model download is an explicit script.
- Verified with Windows text-to-speech audio: without the vocabulary prompt "Chrome" was heard as "crow"; with it,
  all four test questions were transcribed exactly in about 1 s each and matched the right guide. The model now
  preloads at startup. Tests: 147 passed; the suite never opens the real microphone. A live spoken test by a person
  is still to be done.
- Bug from live use: Escape closed the popup but the answer kept being read. pyttsx3 reports "not busy" while
  Windows SAPI is still speaking, so Stop was never applied. Speech now drives SAPI directly, waits on a stop
  event instead of polling, and mutes, pauses and purges on Stop. Measured: muted 0 ms after Stop, SAPI finished
  within 115-180 ms (was 700+ ms or never). Guide text is spoken as plain text only (no SAPI markup). Tests: 148 passed.

## 3 November 2026 — voice-first orb redesign

- Replaced the Ask popup with a docked orb (dock, dockstate, orb, answer_card, tts, highlighter). The brief was
  written for a browser extension; Klicky is a desktop app, so Shadow DOM became a separate frameless window,
  chrome.storage became settings.json, and on-page pointing became UI Automation on the browser's own toolbar.
- Live captions come from re-transcribing the audio so far about once a second; microphone levels are now 50 ms.
- Barge-in learns the echo of Klicky's own voice for 0.6 s and needs sound 2.5x louder for 300 ms (no echo
  cancellation on desktops). Checked with synthetic levels only; needs a person talking over real speakers.
- Bugs found by inspecting renders: the app-wide button min-height squashed the orb to 44 px and clipped its rings;
  word-wrapped captions were under-measured. Minimized browsers reported controls near -32000; pointing now skips them.
- Live checks: per-step SAPI callbacks in order, stop silent in 156 ms with no late end event; real Whisper captions
  then exact final text; Chrome's menu button found by UI Automation in 1.0 s. Tests: 161 passed.

## 3 November 2026 — companion cursor and morph

- Added a teal companion pointer (exact supplied SVG, 22 px) that trails the mouse over Chrome, Edge and Firefox
  with frame-rate independent easing (k = 1 - (1 - 0.18)^(dt*60)), offset (16, 14), idle dim, typing/fullscreen/
  outside-browser hiding, click squish and ripple. It is a click-through window that never takes focus.
- The hotkey morphs it into the orb at its position (+18 px) with an overshoot pop; the card opens beside the orb,
  flips left at the right edge and clamps to the screen. Closing fades both and the companion reappears at the pointer.
- Desktop adaptations of the extension brief: pointer polling instead of mousemove (no system-wide hook, so no
  click can ever be delayed), "page" means the foreground browser window, settings live in settings.json.
- Findings: Qt's precise timer forced 1 ms system timer resolution, costing 3.4% of a core while idle; coarse timers
  and 4 Hz polling with no browser in front brought the whole app to 0.94% of one core. Renders caught duplicated
  steps on a second answer (deleteLater left old labels in the layout) and steps vanishing when a visible card
  re-rendered. Tests: 184 passed. The feel of the follow and squish needs a person's eye.

## 3 November 2026 — companion points at the control being explained

- New guide "Open a new tab or window", checked against Google's and Mozilla's help pages; Microsoft documents only
  the shortcuts, so Edge's plus-sign button was confirmed by finding it through UI Automation in the real Edge window.
- While a step is read, the companion flies out of the orb and its tip rests on the real control (New tab, menu,
  address bar, star, reading mode), with an unlabelled ring; it ignores the user's mouse until the step or card ends.
  The user's real pointer is never moved. With the companion off, the labelled ring alone is shown.
- Live on Edge: the answer was read, Edge's + button was found and ringed, and the companion glided from the orb to
  rest exactly on it. Pointing began 6.1 s after asking, so controls are now looked up as soon as the answer arrives.
  Also keeps every running lookup thread referenced (an earlier one could be collected mid-run). Tests: 189 passed.

## 3 November 2026 — everyday toolbar tasks in Edge and Chrome

- New guides, each leading with the button so the companion can point from step 1: go back, refresh, close the tab
  you are on, extensions, profile, settings; the bookmarks guide now starts with the star. Wording checked against
  Google's and Microsoft's help pages (shortcuts, extensions, profiles, "Add this page to favorites").
- Pointer targets were taken from the real Chrome and Edge windows on this PC: the profile button is named after the
  profile, so it is matched by class (AvatarToolbarButton / EdgeAvatarToolbarButton); every tab has a close button,
  so the selected tab's one is used. Targets that only mention the address bar as a location no longer point at it.
- Lookups searched the web page too (about 3 s each on a WhatsApp tab); they now skip the page's Document subtree and
  take 0.1-0.2 s. Live: Chrome found all eight buttons; Edge found all but the star, which its New tab page does not
  show. Firefox sections for these guides are still to do. Tests: 208 passed.

## 3 November 2026 — guided walkthroughs

- Zoom and Settings are now walkthroughs (guides declare "walkthrough: 2"): open the three-dot menu, then use the zoom
  buttons or the Settings item inside it. Klicky waits in a new "waiting" state and advances when the next control
  appears (menu opened by click or Alt+F), finishes on a click on the last control, steps back if the menu closes,
  and reminds once after 20 s. Menu controls are searched in the browser's popup windows and never cached.
- Walkthroughs were first inferred from "leading steps that point at controls", but the extensions guide lists
  alternatives that fit that pattern, so sequences are now declared explicitly in the guide.
- Klicky moves its orb and card aside when they would cover the control it points at.
- Not verified live: the zoom button and Settings item names inside a real open menu (both browsers were minimized);
  names match both Chromium spellings ("Zoom in"/"Make text larger"). Tests: 216 passed.
- Live feedback: clicking the three dots in Edge left Klicky waiting, because steps only advanced when the menu's
  buttons were recognised. Now a click on the pointed control completes any step (350 ms later the next step is read);
  recognising the open menu remains a backup for keyboard users. "The menu closed" only counts after the menu was seen,
  so unrecognised menus no longer cause false step-backs; with no control found, any click outside Klicky completes
  the step. If the zoom buttons are unnamed, the whole Zoom row is ringed. Tests: 217 passed.

## 3 November 2026 — Klicky does simple browser tasks on request

- "Open a new tab for me", "refresh it", "zoom in", "go back", "close this tab", "reopen the tab", "bookmark this page",
  "open my history/settings/extensions": a deterministic grammar maps one short request to one fixed action; questions
  ("how do I...") and anything compound or unknown get guidance instead. A new "acting" state shows "Opening a new tab...".
- Toolbar actions locate the real button, the companion flies to it and shows a click, and Klicky presses that
  button through UI Automation's Invoke (the pointer is never moved); if it cannot, the browser shortcut is sent to
  the browser window after bringing it forward. Zoom uses Ctrl+=/-/0; settings and extensions open the browser's own
  page in a new tab through the verified address-bar path. Setting "actions" turns this off.
- Not run live in the person's browser by the developer; tests use fake buttons and keys. Tests: 251 passed.
- People will usually ask "can you ...?". Of 44 such phrasings, 19 were missed (e.g. "take me back", "increase the zoom",
  "bring back the tab", "refresh this page?", "can u"), and "can you show my history" was taken for a question. Widened
  the action grammar and narrowed questions to "can you show/tell me how/where/what/why" and "can you help": 44/44.
  Tests: 283 passed.

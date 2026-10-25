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

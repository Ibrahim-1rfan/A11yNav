# Testing report

Test date: 25 October 2026. Windows x64, Python 3.10.11, PySide6 6.12.0.
The exact environment is recorded in `requirements-lock.txt`.

## Outcome and boundaries

**69 automated tests passed (12.13 seconds after the timeout fix).** These cover real application logic, real Qt widgets and a real local
HTTP connection to a **fake** inference server. Browser/model pipeline tests use fakes and do not
prove live model performance. Actual Windows browser controls, capture, speech synthesis and the
packaged UI were tested separately as described below.

**Initial release full AI end-to-end search: BLOCKED, not passed.** No server was listening at
`http://127.0.0.1:1234/v1`. An unsandboxed check returned Windows connection-refused error 10061.
Klicky converted that failure to: “The local model is unavailable. Start the server in LM Studio
and check Settings.” No weights were downloaded and no model reasoning was simulated in the app.
The candidate's file availability and documented capabilities are verified; actual local inference,
model latency, memory use and visual-result recognition were not tested in that initial release.

## Timeout investigation follow-up

The user's saved model timeout was 120 seconds, but the whole task allowed only 240 seconds for
at least four image calls plus browser work. Transport errors were also incorrectly retried as
invalid actions. Fixed that distinction, moved the post-response deadline check out of the retry
path, and prevented requests from starting after cancellation or an already-expired budget.
Settings now exposes task time, image size and reply length, with a warning for conflicting budgets.
Four additional regression tests cover these behaviors; all 69 cases passed.

Real local synthetic-image checks used a 640×360 red rectangle and the actual configured image
transport/action parser. Qwen2.5-VL-7B loaded with its projector but exceeded the 120-second wait
limit. It was unloaded after the check. UI-TARS-2B returned the expected `wait` action in 57.0 seconds.
These are single observations under normal machine load (packaging work also ran), not controlled
comparative benchmarks or proof of reliable image comprehension. Windows reports Intel UHD graphics.
No model weights were downloaded. The local server was started for these checks.

Saved a timestamped backup of user settings, then changed the task limit to 600 seconds, maximum
image edge to 640 and reply tokens to 256. Kept the user's UI-TARS choice, Google engine, speech
preference, 120-second request limit and other settings. Reduced image detail can hurt small-text
recognition. The updated executable was rebuilt after closing the idle copy that locked it.

The first real Google browser run under the larger budget ended after 249.4 seconds: three model
responses at step 1 were rejected by the exact-action policy. No browser input action was executed
after opening the search home page. This is a model action-selection failure, not a task timeout.
Clarified the prompt to prohibit all clicks (including the search field/address bar), limit it to
the current step, and feed safe rejection messages into bounded retries. Retry status now displays
the actual validation reason instead of a generic message. Pipeline tests passed again (11 cases).
The full model-driven search remains unverified.

The clarified focus-step check returned a parsed `hotkey` action in 85.5 seconds. A second full
run verified both address-bar focus and exact URL entry, then stopped at 336.5 seconds after three
invalid Enter-step replies. A metadata diagnostic identified the reply as `click(start_box=...)`,
using UI-TARS box delimiter tokens, rather than an Enter command. Clicks are outside this demo's
approved policy, so broadening the parser alone would not make that action acceptable. No search
submission or final visual verification passed. The larger time budget is working; remaining
model instruction-following is a distinct unresolved acceptance gate. Do not claim end-to-end success.

## Automated suite

Command: `.venv\Scripts\python.exe -m pytest -q --junitxml=tmp/test-results.xml`

| Test group | Expected result | Actual result | Components |
| --- | --- | --- | --- |
| Configuration | Round-trip valid settings; reject unknown keys, remote/credential endpoints, invalid ranges/types | Passed | Real file and validation logic |
| Task interpretation | Extract supported search requests; reject other tasks and unsafe multiline/oversized input | Passed | Real parser |
| Query encoding and URLs | Preserve Unicode as encoded inert data; reject wrong query, host and scheme | Passed | Real URL logic |
| Image processing | Aspect-preserving resize, PNG payload and physical coordinate mapping including negative origins | Passed | Real Pillow, synthetic image |
| Model parsing | Decode permitted UI-TARS/JSON records; reject executable syntax, duplicate/unknown arguments and malformed coordinates | Passed | Real parser, fixture responses |
| Action validation | Reject unknown operations, forbidden keys, invalid bounds, oversized text, excessive scroll/wait | Passed | Real policy |
| Execution policy | Allow only the exact current search step; reject early finish and arbitrary clicks/URLs | Passed | Real policy, fake browser |
| Cancellation and deadlines | Reject late replies and stop before further input; bound transport waiting and task duration | Passed | Real control logic, timed/fake operations |
| Pipeline success | Four model stages, exactly three desktop actions, fresh screenshots, verified final state | Passed | Real controller; fake model/browser/capture source |
| Pipeline failure | Missing browser/model, wrong final URL, invalid output, repeated waits and retry limit never report success | Passed | Real controller; injected failure components |
| Local HTTP contract | Model listing and multimodal PNG body transmitted through actual HTTP | Passed | Real Requests/socket; fake model server |
| HTTP failures | Reject 302, 400, 401, 422, 500 and 503; reject missing model ID | Passed | Real transport; fake server |
| Qt worker and Stop | Stop button sets cancellation; worker reports stopped; Start becomes available | Passed | Real Qt, fake controller |
| Voice toggle | Disabled speech queues nothing; mute clears pending speech | Passed | Real Speaker queue, no speech output |

The per-case names, durations and pass/fail results are recorded in `docs/test_cases.md`.
No live-model behavior is inferred from these tests. Resource-exhaustion errors are covered through
server-error handling, not by deliberately exhausting the machine's memory.

## Actual component checks

| Test | Expected result | Actual result and status | Limitation |
| --- | --- | --- | --- |
| Source application launch | Show readable native window, then exit cleanly | PASS; source smoke exited 0 and produced an app-only screenshot | Does not start model automation |
| Font selection | Intel family if installed; readable monospace fallback otherwise | PASS; detected Consolas on this machine; rendered controls inspected | Intel font itself was not installed |
| Desktop capture | Capture an interactive desktop image | PASS; 2560x1440 capture returned; browser-cropped captures also succeeded | No mixed-DPI hardware matrix |
| Browser detection | Find installed supported browsers | PASS; Edge, Chrome and Firefox executables detected | Real action test used Edge only |
| Browser action sequence | Open/focus browser, focus address, enter URL, submit, verify matching URL | PASS on repeat; three stages verified true and final search URL matched | Predetermined component test, no VLM; final result content was not certified |
| Browser initial failure | Stop when address focus cannot be verified | PASS as a safe failure; first smoke stopped before query input | Prompted focus-handling improvement |
| Native UIA final lookup | Locate visible browser chrome with bounded UIA client | PASS; address control found and CUIAutomation8 configured | Read-only check after final backend change |
| Actual model availability | Find model or show explicit setup error | PASS failure handling; connection refused at port 1234 | Live AI task remains BLOCKED |
| Real UI missing-server task | Start example request, show setup error, restore Start | PASS; actual MainWindow/worker/model transport showed the expected message and restored Start | No browser opening or model inference occurred |
| Packaged executable | Launch independently from source environment | PASS after packaging fix; exit code 0 and app-only screenshot inspected | Same host, not a clean-machine install test |
| Documented launch script | Open packaged app through scripts/run.bat | PASS; generated the expected final-launch screenshot | Startup took longer than the first five-second file check |
| Desktop shortcut | Create shortcut pointing to packaged app | PASS; Klicky.lnk created after confirming no existing shortcut | Taskbar pinning remains a user action |
| Speech engine | Synthesize local status audio | PASS; two voices detected; WAV contained 32,289 frames at 22,050 Hz | Audio-device audibility and participant preferences not evaluated |
| Manual human Stop during a live AI task | Stop automation before further input | BLOCKED with live model unavailable; Qt Stop and in-flight cancellation passed automated tests | Must repeat with real inference |
| Plan export | Editable Word and matching clean PDF with contents and numbered headings | PASS; 15-page native Word PDF export, pages inspected | Bundled LibreOffice renderer unavailable; native Word used |

## Failures encountered and fixes

1. Initial test run: 63 passed and two failed. The sandbox denied a temporary-file rename and local
   socket access. Running the suite with the needed local access resolved both; no product behavior
   was changed to hide them.
2. Initial UI screenshot: several controls inherited small system text. Applying an explicit family
   and pixel size across Qt widgets fixed the visible inconsistency. Source and packaged screenshots
   were reviewed after the fix.
3. Initial browser component test: address focus was not established. Added foreground preference,
   guarded native window focusing and a verified UIA focus fallback. The repeated real test passed
   focus, entry, submission and URL verification.
4. Initial executable: QtCore failed with “The specified procedure could not be found.” Binary inspection
   traced this to a bundled third-party `icuuc.dll` whose version-suffixed exports did not match Qt's
   Windows ICU imports. The maintained PyInstaller spec excludes that library and its data DLL,
   allowing the Windows ICU API to resolve. A rebuilt executable then passed the normal-desktop smoke.
   An earlier suspicion that one-byte DLLs had been copied was disproved by inspecting actual file sizes.
5. Standard document rendering failed because LibreOffice is not bundled on this Windows host. Native
   Microsoft Word updated the table of contents and exported the PDF; PDFium rendered it for review.
   A background Word save stalled in the first export sequence; exporting before saving and completing
   the operation through the verified plan document produced both final files.
6. Added explicit COM initialization to the speech thread so enabling voice after browser automation
   does not depend on which thread first imported the Windows COM libraries.

## Remaining live acceptance procedure

1. Load the chosen UI-TARS GGUF and matching projector in a compatible local runtime; record versions,
   hardware, image settings and memory use. Start the local server and copy the exact model ID.
2. Test an image in the runtime UI, then use Klicky's Check connection. Confirm the actual image request
   works rather than treating a successful model listing as vision validation.
3. Open Klicky through the packaged executable/shortcut. Enter the example task and press Start.
4. Observe actual model-guided stages. Check that search results for the correct query are visible,
   not a CAPTCHA, empty page or consent screen. Record the final state without unrelated private content.
5. Start another task and press Stop during inference and after a desktop action. Confirm that no late
   reply causes input. Test a switched foreground application and an unavailable server.
6. Record success/failure, elapsed time, action count, interventions and any error. Only then mark the
   AI end-to-end gate passed. Do not use the component script as a replacement for this test.

Further checks: other browsers, localized controls, mixed display scaling, assistive technology,
an unsigned package on a clean Windows account, speech output-device behavior and participant evaluation.

## Deliverable verification

- Final executable smoke exit: 0, after the last source change and rebuild.
- Word document contains 21 numbered primary sections, eight detailed phase subsections and 30 cached contents entries.
- Matching PDF: 15 pages; every rendered page inspected. No clipped text or overlapping content observed.
- Original reference PDF preserved; no screenshot of unrelated browser content retained.
- Full AI end-to-end success remains unclaimed and blocked by the absent model server/weights.

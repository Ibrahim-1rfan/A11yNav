# Architecture

## Data flow and trust boundaries

User command -> deterministic search parser -> local model health check -> trusted browser bootstrap
-> browser-window screenshot -> resized PNG -> local multimodal inference -> strict action parser
-> independent search policy -> guarded native action -> fresh screenshot and native state check
-> next observation. Visual finish plus matching engine/query URL is the only success path.

The browser bootstrap is trusted deterministic application code. It opens a new search tab at the
selected engine before the model-controlled loop. The model then chooses the next permitted action
from focus address, enter the encoded search URL, submit, and verify. This is a deliberately constrained
hybrid CUA rather than an open-ended general desktop planner. It enters the query through an encoded
search URL rather than typing into a page-specific search field.

## Components

| File | Responsibility |
| --- | --- |
| main.py | DPI awareness, app entry, first-run settings, UI-only smoke option |
| ui.py | Qt controls, worker signals, compact ring/status, Stop, settings and accessible font sizing |
| config.py | Typed settings, strict local endpoint/range validation, atomic settings persistence |
| planning.py | Explicit natural-language search grammar, inert query, encoded engine URLs, stage policy |
| perception.py | On-demand cropped capture, RGB/PNG preprocessing, coordinate mapping |
| models.py | Local HTTP, bounded/cancellable waiting, UI-TARS and JSON data adapters |
| actions.py | Action shape/range validation and a second policy check at execution boundary |
| browser.py | Browser discovery, known executables, foreground/process guards, UIA address control |
| verification.py | Focus, entered-value and exact engine/query URL checks |
| controller.py | Observe/act/verify loop, status transitions, finite attempts, deadline and retry policy |
| speech.py | Optional local speech worker, mute and pending-speech cancellation |

No empty subsystem scaffolds or orchestration frameworks are included. Future perception/retrieval/profile
interfaces should consume typed observations and proposed steps without bypassing the action policy.

## Interfaces

`Frame` carries a PNG data URL, resized image dimensions and original physical desktop bounds.
Normalized coordinates map back to those bounds, including negative multi-monitor origins. The current
search policy does not execute coordinate actions. DPI awareness is established before Qt is created.

`LocalModel.health(stop)` checks endpoint availability and configured model ID. `propose(frame,
instruction, stop, remaining)` sends the current image and one stage-specific request. It returns an
`Action` dataclass. HTTP failures never produce a synthetic action. No alternate model fallback exists.

`Executor.execute(action, stage, task, stop)` revalidates action shape and exact permitted action.
The only text permitted is the code-generated HTTPS search URL. Query input is inert URL-encoded data.
Unknown operations, arbitrary URLs, page clicks and dangerous shortcuts cannot be executed.

## States and progress

The controller emits `processing`, `action`, `success`, `error` and `inactive` with readable messages.
Search stages advance only after postconditions hold: address focused -> exact value entered ->
matching navigated URL -> model visually recognizes results. Every meaningful action is followed by
a screenshot. Repeated invalid replies, loading waits and capture requests all consume `max_actions`.
Invalid inference retries are limited per stage by `max_retries`; a failed native action stops immediately.

The compact widget uses both a colored outline and words. No target is shown when none is visually
grounded. No motion is used. It remains operable while model inference runs on a worker thread.
Qt UI changes are delivered by queued signals; native Windows COM use is initialized in the task thread.

## Safety and privacy

Only browser search is authorized. Out-of-scope actions are rejected, including sensitive actions that
would require confirmation in a future broader agent. There is no hidden confirmation bypass.
Browser windows are identified by process executable, not title. Address candidates must be visible
browser chrome outside a page Document ancestor. Before text/Enter, the expected address control and
foreground window are rechecked. UIA ValuePattern writes avoid clipboard access and typing into a
different application's field. The final Enter key still has a small OS focus race; users must keep
the desktop undisturbed, and this prototype is not a security isolation boundary.

Screenshots stay in memory and are browser-cropped; no automatic field redaction is claimed. The local
server may independently log requests. Klicky only logs exception class names on unexpected failure.
Loopback-only endpoints, disabled redirects and ignored proxy variables prevent accidental remote image upload.

Stop is an Event checked before/after operations, during waits and while awaiting inference.
Late model results are ignored. Native COM calls use CUIAutomation8 connection/transaction timeouts
of two seconds; finite browser-launch and retry waits bound normal desktop work. A native call already
in progress cannot be undone. HTTP workers are daemon threads with finite socket timeouts; cancellation
does not guarantee cancellation of computation inside the model server.

## Extension boundaries

- Voice recognition should produce the same `SearchTask`, with microphone permission/status and voice Stop.
- A model registry can implement the existing health/propose contract with explicit coordinate conventions.
- Documentation retrieval should return cited procedures, never executable scripts or screen coordinates.
- Access-need profiles should choose instruction format, text size and speech preferences with user consent.
- New application capabilities require independent policies, postconditions, sensitive-action confirmations
  and a regression suite before they are exposed to a model.

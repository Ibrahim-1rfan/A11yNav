# Klicky implementation and research plan

University HCI project

25 October 2026

## 1 Project overview and motivation

Klicky is a screen-aware assistant intended to help people who find conventional computer interfaces difficult to use. The immediate engineering deliverable is a Windows application that accepts a natural-language search request, opens a browser, observes its screen through a local vision-language model, performs a small approved sequence and reports whether results are visible. The research direction is personalized interface guidance shaped by a user's access needs.

The prototype establishes the observation, action and verification infrastructure needed for that research. It does not establish that automation improves accessibility, and it does not replace user studies. A successful engineering demonstration must be distinguished from evidence of usability, trust or benefit for particular users.

The current application, tests and launch scripts are implemented. A real browser component test exercised address entry and submission. The full AI demonstration remains an acceptance gate because no local vision model was available during development. The team should complete that gate before presenting autonomous search as validated.

## 2 Interpretation of the Klicky reference

The supplied ten-page research pitch is titled Profile-Conditioned Multi-Agent Assistance for Accessible Interface Navigation. Its central proposition is that the same procedure can be delivered through spatial cues, keyboard paths or one step at a time depending on an individual's access needs. Page 8 proposes vision, retrieval and profile components. The first component understands the current interface; the second retrieves official documentation; the third changes how guidance is delivered.

Pages 2 and 3 position MATE as precedent for local accessibility assistance and modality conversion. Pages 4 and 5 describe failures in grounding, hidden paths, constraint tracking and termination, and emphasize users' desire for explanation and confirmation. Pages 6 and 7 describe PersonaAgent's memory-to-persona-to-action loop. Page 9 compares these foundations with Klicky's intended contribution. The numerical claims in these slides remain claims from the supplied pitch; they are neither Klicky results nor independently verified findings in this implementation.

The immediate build request narrows the implementation to assisted browser search and explicitly postpones RAG and multi-model orchestration. This plan preserves the pitch's direction while sequencing that scope. A visible status widget, plain-language explanations and Stop are included now. Personalized delivery, documentation grounding and distinct interaction modes are future phases. The navy and teal interface follows the reference's visual direction while using large monospace controls.

## 3 Accessibility objectives and target users

The intended audience includes people who experience visual, motor, reading or navigation barriers. These groups have different needs and cannot be treated as one persona. The team should recruit participants based on tasks and access needs, ask about preferred assistance, and avoid inferring disability from behavior.

Current objectives are readable text, visible focus, a short command path, an always-available Stop control, optional speech and explicit progress. Intel One Mono is selected when installed; the app checks actual font families and falls back to Consolas or another system monospace font. Ordinary text starts at 18 px, command text at 22 px, with settings up to 28 px. State labels accompany color. The indicator is static to avoid unnecessary motion.

Keyboard traversal and accessible names are implemented with native Qt controls. These implementation choices do not establish screen-reader compatibility. The team must test with the actual assistive technologies participants use, including focus restoration after automation, status announcements, magnification and scaling. Users must be able to choose silence, written guidance or speech without losing access to task status.

## 4 Initial prototype scope

Supported requests include Search for a topic, Look up a topic, and Open my browser and search for a topic. A deterministic parser extracts one query and rejects unsupported task grammar. The query is treated as inert data and encoded into a search URL. Bing, Google and DuckDuckGo are configurable engines. Edge, Chrome and Firefox are recognized by executable identity and accessible browser chrome.

The demonstration uses the address bar to enter the search URL rather than locating a search box inside the webpage. This reduces dependence on page layout and prevents arbitrary result-link clicks. The model participates in choosing the next approved action and visually deciding whether results are shown. Native focus and URL checks supplement that visual judgment.

The application cannot send messages, make purchases, delete files, enter passwords or change settings in other applications. These operations are outside its capability boundary, even if a user asks for them. A future sensitive-action confirmation flow must be designed before broader capabilities are enabled. Voice input, RAG, personal memory, multi-agent orchestration and free-form desktop planning are not implemented.

## 5 Current system architecture

The system is a modular Python application. PySide6 provides the UI and worker signals. Pillow captures and preprocesses the browser rectangle. Requests sends image-bearing messages to the local inference API. Pywinauto and Windows APIs identify browser windows and address controls; PyAutoGUI supplies a small number of fixed keyboard gestures. Pyttsx3 provides optional local speech. PyInstaller packages the application into a Windows executable folder.

The data path is command interpretation, model health check, trusted browser opening, screen capture, model proposal, action parsing, policy validation, execution and verification. Configuration is independent of these components. The UI receives state and status signals, rather than manipulating model internals. Future adapters can replace model transport without changing the browser policy.

An Action record describes a supported operation. The model parser never executes Python. It accepts a strict UI-TARS call-shaped syntax or a JSON object. The executor repeats policy validation, so a direct caller cannot bypass the approved sequence. Coordinate actions have parsing and bounds checks but remain disabled by the current search policy.

## 6 Detailed end to end workflow

1. The user opens the application or compact widget, reviews the screenshot/privacy notice and enters one search request.
2. Start validates the request and settings. The main window collapses, leaving a persistent status and Stop widget.
3. The application checks the local server and exact model identifier. Failure stops before browser automation.
4. Trusted application code finds a supported browser or launches the preferred/default browser and opens the search engine in a new tab.
5. The application captures the browser rectangle, resizes it to the configured image limit and keeps the PNG in memory.
6. The local VLM receives the image and current approved step. The response must parse as one supported action.
7. The policy permits only address focus, the exact encoded search URL, Enter at the correct stage, bounded waiting, capture or help.
8. Before input, the application checks foreground ownership and the address control. After input it captures again and checks the native postcondition.
9. After submission, the next visual observation asks the VLM to distinguish actual results from loading, consent, CAPTCHA, sign-in or error pages.
10. Success requires visual completion and an independently matching engine and query URL. Otherwise the task waits within its budget, asks for help, stops or reports an error.

The user can cancel while inference is pending. Late replies are ignored. A Windows call already in progress cannot be undone, but Stop prevents subsequent actions once control returns. If focus changes unexpectedly, the application stops instead of refocusing and continuing to type.

## 7 Model selection and integration strategy

The selected candidate adapter targets UI-TARS-2B-SFT through a local LM Studio-compatible server. The publisher's repository identifies a Qwen2-VL-based GUI model and supplies GGUF files. The file listing includes a Q4_K_M model of approximately 1.12 GB and a separate f16 multimodal projector of approximately 1.33 GB. Both are needed for the intended image workflow. Download size does not determine runtime memory consumption: vision encoding, context, cache and runtime overhead add memory requirements.

LM Studio documents local serving and a Chat Completions compatibility endpoint. Klicky uses GET /v1/models and POST /v1/chat/completions with an image data URL. The configured model identifier must match the server. The default settings are a starting point, not a promise that every runtime exposes the same identifier. A connection check verifies listing availability only; the team must separately validate a real image response.

The original UI-TARS-2B action convention is handled separately from newer absolute-coordinate models. No alternative model has been selected or claimed as tested. If the current runtime cannot load this GGUF/projector combination, the team should record the runtime version and error, test an updated compatible runtime, and evaluate a replacement against the same image/action acceptance cases before changing defaults.

Model requests have configurable token, temperature, image-size and timeout limits. Unsupported image input, malformed output and server failures produce visible errors. No prerecorded or deterministic response is silently substituted for failed inference. Model weights are never downloaded automatically.

## 8 Desktop interaction and visual guidance

Browser preference can be default, Edge, Chrome or Firefox. Discovery checks installed paths and registered application paths. Existing suitable browser windows are preferred; otherwise the app launches a detected executable or the operating system's default browser. A launched process alone does not count as a verified browser: the foreground window must belong to a recognized browser process.

Address controls are located through UI Automation and must be visible browser chrome outside a webpage Document ancestor. Direct ValuePattern writes avoid modifying the clipboard or sending query characters to whichever application happens to have focus. Fixed Ctrl+L and Enter gestures are guarded. There remains a small operating-system focus race around a keyboard event; the prototype requires an undisturbed interactive desktop and is not a sandbox for hostile applications.

Screenshots use physical browser bounds with DPI awareness enabled before UI creation. Image resizing preserves aspect ratio and retains the original rectangle for coordinate conversion. Negative display origins are represented. Multi-monitor, mixed-DPI and alternate-language browser behavior require further hardware testing.

The compact widget displays a static colored ring and a word indicating readiness, observation, action, completion or help. This workflow has no reliable visually grounded click target, so the ring stays in the widget. Future grounded actions can use normalized target coordinates, but must not animate toward guessed locations.

## 9 Privacy safety and user control

Every task begins with an explicit Start. No background capture, startup service, microphone recording or unattended task scheduling is installed. The UI explains that visible browser content is sent to the local model, while the search query goes to the selected search engine. A clean browser profile is recommended for demonstrations because cropping cannot remove sensitive content already visible within the browser rectangle.

Klicky accepts only loopback model endpoints, ignores proxy environment variables and rejects redirects. Screenshots, query text and raw model replies are not persisted by the application. Its local inference server may retain its own logs; the team should review those settings before participant sessions. Settings contain preferences, not credentials or participant profiles.

The action budget counts invalid model replies and waits as well as executed steps. Invalid inference has bounded retries. Browser launch has a finite wait; Windows UIA connection and transaction timeouts are configured to two seconds. Model waiting is cancellable and has a task deadline. These controls do not roll back actions or stop computation already running inside the model server.

Sensitive operations are blocked completely in this prototype. Future approval must identify the exact action, recipient or destination, data being submitted and consequences. Approval should authorize only that concrete operation and should expire when the target changes. Screen instructions and retrieved documents must never be treated as user authorization.

## 10 Technology stack and dependencies

| Layer | Current choice | Reason and qualification |
| --- | --- | --- |
| Interface | Python and PySide6 | Native controls, keyboard access and background workers |
| Capture | Pillow ImageGrab | On-demand browser crop and portable image processing |
| Model transport | Requests and local HTTP | Explicit timeout/error handling and no cloud requirement |
| Windows access | Pywinauto and ctypes | Process identity, native focus and address-control values |
| Keyboard input | PyAutoGUI | Limited fixed gestures with fail-safe enabled |
| Speech | Pyttsx3 and Windows voices | Optional local status speech |
| Tests | Pytest and fake components | Repeatable policy, transport and UI integration cases |
| Distribution | PyInstaller folder build | Double-click executable without a developer environment |

The tested dependency snapshot is recorded in requirements-lock.txt. The build includes application dependencies, not LM Studio, model weights or fonts. Dependency upgrades should rerun the transport, native-control and packaged-launch checks. The source architecture can support other platforms later, but the current action backend is Windows-specific.

## 11 Implementation phases

### 11.1 Phase 1 Initial working CUA

Purpose and problem: establish a controllable browser-search loop and expose failures before expanding the project. Users need a short, understandable path from a request to visible results.

Features and integration: native UI, persistent widget, optional speech, browser discovery, image-bearing inference, validated actions, independent verification and cancellation are implemented. Configuration, capture, model, policy and executor are separate interfaces. No advanced RAG or orchestration dependencies are required.

Implementation steps: inspect the reference, define the search policy, implement adapters and UI, test failure paths, package the executable and run the live model acceptance demonstration. Earlier-phase dependencies: none, but a local vision runtime and model are external prerequisites for the final demonstration.

Testing and completion: unit and mocked integration tests must pass; the executable must launch; real browser controls must work; then a real model must process screenshots and the final result page must be independently reviewed. Cancellation must be exercised during inference and after at least one desktop action. Completion requires recording model/runtime versions, hardware, latency and the actual result. The last live-model gate remains open.

Risks: model format support, insufficient memory, focus loss, consent pages and hallucinated completion. Mitigations are small images, explicit setup, strict action policy, finite budgets and both native and visual checks. These reduce risk without guaranteeing correct visual reasoning.

### 11.2 Phase 2 Voice based interaction

Purpose and problem: enable users who cannot comfortably type to initiate and cancel the same supported tasks. Speech recognition must not silently expand task permissions.

Features: an opt-in microphone button, active-recording indicator, local speech recognition, spoken clarifications, voice cancellation, and rate/volume controls. A wake word is optional and should be considered only after an explicit privacy and resource evaluation.

Integration and components: a SpeechInput adapter produces text for the existing task parser. Likely dependencies include a local recognizer such as Whisper through an evaluated runtime, an audio-input library and a device-selection UI. The current Speaker remains the output interface. Recognition results must pass the same search grammar and safety policy.

Steps and dependencies: first stabilize phase 1; add push-to-talk capture; expose device permission and recording state; implement recognition and review; then test interruption and ambiguous commands. Do not store raw audio by default. Microphone failure must leave text input usable.

Testing and completion: test recognition under noise, different accents and speech patterns, including participants with relevant access needs. Measure task success and correction burden rather than transcription accuracy alone. Completion requires reliable opt-in recording, working voice Stop, no capture after mute/exit and a usable text fallback.

Risks: false activation, missed cancellation, recognition bias, local-model latency and audio leakage. Limit recording duration, retain explicit visual controls and evaluate whether wake-word behavior is appropriate at all.

### 11.3 Phase 3 Multiple model support

Purpose and problem: compare specialized perception, planning, OCR and verification models without tying the entire application to one output format or multiplying every request unnecessarily.

Features: a model registry, capability metadata, runtime adapters, explicit coordinate conventions, per-role selection and compatibility probes. Separate roles should be introduced only when measured accuracy or latency benefits justify them.

Integration and components: extend the existing health/propose contract with capabilities and typed observations. Add adapter-specific preprocessing and parsers. Keep the executor and application policy independent. Optional OCR must return text and evidence, never executable instructions.

Steps and dependencies: use the completed phase 1 test fixtures as a common contract, implement a second verified adapter, compare a fixed task set, record memory and inference latency, and then consider explicit role routing. Voice input from phase 2 is useful but not required for this phase.

Testing and completion: identical screenshot fixtures must produce valid bounded outputs; wrong coordinate conventions must be rejected. Run real-image and real-desktop trials per supported model/runtime version. Completion requires two tested adapters, a documented selection rationale and no silent fallback to an incompatible model.

Risks: compounded latency, inconsistent action semantics, hardware pressure and misleading benchmark comparisons. Use matched tasks, explicit capability checks and transparent fallback messages. Keep a single-model baseline for comparison.

### 11.4 Phase 4 Software documentation RAG

Purpose and problem: address the pitch's hidden-procedure problem by grounding guidance in official help material while retaining current-screen checks. Documentation explains procedures but does not establish where controls are located on a particular screen.

Features: application/task identification, approved-source retrieval, versioned citations, concise explanations, procedure steps, error recovery and refresh/re-index policies. Users should be able to see the source supporting a recommendation.

Integration and components: add a RetrievalService that returns passages with source URL, version and retrieval date, and a ProcedurePlanner that converts evidence into proposed steps. Likely dependencies include document parsers, an embedding model and a small vector or hybrid search index. Retrieved content is untrusted data and cannot grant tool permissions.

Steps and dependencies: stabilize phase 1 policy and preferably phase 3 adapter contracts; choose one application and a bounded official corpus; implement ingestion and provenance; evaluate retrieval; connect cited steps to visual grounding; then add refresh and stale-source detection.

Testing and completion: maintain a held-out task set with relevant documentation and cases with no answer. Test stale versions, malicious text, conflicting sources and screen/document mismatch. Completion requires useful retrieval, visible citations, justified abstention and no coordinate execution derived from documentation alone.

Risks: outdated help, inaccessible licensing terms, missing procedures, hallucinated citations and retrieval prompt injection. Restrict sources, preserve provenance, track versions and keep code-level permissions independent of retrieved text.

### 11.5 Phase 5 Guided and autonomous modes

Purpose and problem: let users choose how much help to delegate. The reference warns that silent autopilot can conflict with a user's desire to understand and control a task.

Features: guided mode explains and highlights while the user acts; assisted mode performs approved low-risk steps and verifies them; autonomous mode completes a bounded approved task and pauses for sensitive operations. Mode and current authority must remain visible throughout.

Integration and components: add a mode policy above the existing executor, a user-action observation path, and a concrete approval record bound to action, target and expiry. Guided mode can reuse perception and verification without dispatching input. RAG procedures from phase 4 should improve explanations but remain optional for basic search.

Steps and dependencies: require stable phase 1 verification; define authority per mode; implement guided steps first; add assisted transitions; then add sensitive-action approval and only a small audited autonomous capability. Do not infer consent from continuing a conversation.

Testing and completion: verify that guided mode never performs input, mode switches cancel stale proposals, and changed targets invalidate approval. Test confusion, accidental clicks and interruption with users. Completion requires comprehensible mode boundaries, working Stop in every mode and measured adherence to authority limits.

Risks: automation surprise, approval fatigue, mode confusion and recovery after partially completed tasks. Keep default authority narrow and show what happened before asking the user to continue.

### 11.6 Phase 6 Expanded accessibility

Purpose and problem: realize the pitch's access-need profiles while avoiding one-size-fits-all assumptions. Personalization should adapt instruction delivery and interaction pathways, not merely change wording.

Features: adjustable layout, high contrast, screen-reader announcements, keyboard-first guidance, configurable speech, one-step presentation, reduced motion, speed control and optional profiles. Let users inspect, change and delete preferences. Personal memory is optional and requires a separate consent design.

Integration and components: a ProfileStore holds explicit preferences; a GuidancePresenter selects spatial, keyboard or sequential explanations. The planner still describes the same task and the executor applies unchanged safety policy. Use native accessibility APIs and participants' actual assistive technology rather than adding a model for every preference.

Steps and dependencies: build on phase 1 controls and phase 5 guided mode; conduct formative sessions; implement the most important barriers; test focus order and announcements; add opt-in profiles; then compare alternative delivery patterns.

Testing and completion: evaluate with users with different access needs, including conflicting preferences. Combine keyboard/screen-reader checks with task performance, comprehension and perceived control. Completion requires resolved critical barriers in the agreed target workflows and documented remaining limitations, not a universal accessibility claim.

Risks: stereotyping, sensitive profile data, cognitive overload and false confidence from automated audits. Prefer explicit preferences, minimize stored data and invite participants to correct the system.

### 11.7 Phase 7 Broader application support

Purpose and problem: extend from browser search to useful desktop work without weakening the capability boundary or replacing screen verification with fixed scripts.

Features: a small registry of application capabilities, application-specific launch/focus handlers when necessary, documented safe actions, recovery behavior and task postconditions. Add one bounded task family at a time, starting with non-destructive work in disposable documents.

Integration and components: introduce an application adapter with observation, action policy and verification methods. Shared model, speech, guidance and configuration components remain reusable. UI Automation should be preferred where reliable, with visually grounded coordinates only when tested. RAG can explain hidden workflows, but every action must match the actual interface.

Steps and dependencies: require stable modes and approval boundaries from phase 5; select a useful task with participants; specify its hazards and postconditions; implement its adapter; build fixtures and recovery tests; then pilot it before enabling it by default.

Testing and completion: run success and failure cases across supported application versions, window sizes and interrupted states. Completion requires an explicit supported-task matrix and reproducible evidence for every enabled capability. Unknown versions should abstain when verification is unreliable.

Risks: destructive side effects, application updates, inaccessible controls and combinatorial testing cost. Limit supported scope and use clean test data. Never claim broad desktop support from a single successful demonstration.

### 11.8 Phase 8 Evaluation and research

Purpose and problem: determine whether Klicky is useful, understandable and trustworthy for the intended users, and whether profile-conditioned guidance adds value beyond a generic assistant.

Features: repeatable task sets, consented minimal telemetry, baseline conditions, participant feedback and an analysis protocol. Compare conventional interaction, generic guidance and personalized guidance where feasible. Include failure and recovery tasks rather than only favorable examples.

Integration and components: add an opt-in EvaluationRecorder separate from normal application logging. Store event types, durations and outcomes without screenshot, query or audio content unless specifically consented. Use a reproducible analysis script and a protocol describing exclusion, missing-data and stopping rules.

Steps and dependencies: define measures early; pilot engineering tasks after phase 1; seek applicable university ethics approval before recruiting; evaluate modes/profiles after phases 5 and 6; counterbalance conditions; analyze results with uncertainty and publish limitations. Do not delay basic formative accessibility feedback until the final phase.

Testing and completion: validate metric calculations on known traces, record human adjudication rules and disagreements, and preserve anonymized analysis provenance. Completion requires a repeatable protocol, approved participation process and an honest report, including failed tasks and adverse experiences.

Risks: small samples, learning effects, unrepresentative tasks, privacy leakage and overclaiming. Use within-participant comparisons only where appropriate, allow breaks/withdrawal and report descriptive results with uncertainty rather than implying population-wide benefit.

## 12 Future voice command support

Voice recognition will be an optional input route into the same task interpreter. The microphone must have an explicit active state, a maximum recording interval and an immediate stop control. Recognition should present a review or clarification when the query is uncertain. Voice cancellation must receive priority over task generation and remain available while the model is processing.

Rate, volume and speech verbosity should be independent of microphone permission. Local recognition is preferred, but its latency and recognition quality must be evaluated on the target hardware and with the intended users. Continuous listening and wake words are not part of the current application.

## 13 Future multiple model architecture

A registry should record model identifier, runtime, image support, action schema, coordinate system, maximum image size and observed resource requirements. Roles may include perception, interpretation, OCR and verification. Route a step to the minimum necessary models and record why any additional verification model is used.

Model disagreement should lead to abstention or a visible recovery decision, not arbitrary voting over incompatible actions. Keep one canonical Action type and one independent capability policy. A second model is not a substitute for a native postcondition or user confirmation.

## 14 Future software documentation retrieval

Each indexed passage should retain its official source, application version, retrieval timestamp and content hash. Refresh schedules should be based on source volatility. Help for a different application release must be marked as potentially stale. Missing evidence should produce an explanation of uncertainty rather than an invented instruction.

Retrieval should help explain hidden procedures and recover from errors. Current screenshots or accessibility state still determine whether a control exists and where it is. The retrieval store must not contain private participant documents by default. The team should test both retrieval relevance and whether the resulting guidance helps users perform the intended task.

## 15 Future guided and autonomous modes

The default mode should be chosen through user research rather than assuming maximum automation is preferable. Guided mode needs an explicit way to mark a step complete, ask for repetition and request a different explanation. Assisted mode should narrate concise actions. Autonomous mode needs a clearly stated task boundary and concrete sensitive-action approval.

Switching modes must invalidate queued actions and require a new observation. Recovery should explain which actions already occurred and which did not. A persistent Stop must remain operable even when speech or the model fails.

## 16 Accessibility improvements

Prioritize barriers observed in formative sessions: small targets, focus loss, unreadable contrast, excessive text, ambiguous progress and inaccessible error recovery. Add layout scale separately from font size where needed. Expose status through assistive-technology announcements without overwhelming users with every internal observation.

Profiles should be explicit, editable and task-sensitive. A person may prefer spoken navigation in one context and concise keyboard instructions in another. Avoid inferring medical information or treating a diagnosis as a complete interaction preference. Personalization must never remove safety information or reduce the user's ability to stop.

## 17 Testing and evaluation methodology

Engineering tests cover configuration, task grammar, image resizing, coordinate bounds, parser rejection, allowed actions, verification, retries, time limits and cancellation. Integration tests connect the real controller to fake browser/model components, exercise actual loopback HTTP against a fake inference service, and connect Qt controls to a worker. These tests are labeled as simulated where appropriate.

Real component tests cover application launch, screen capture, browser detection and address entry/submission. A model-enabled end-to-end run must record the exact model and runtime versions, hardware, request, observations, final page and manual cancellation. A result is not passed merely because a browser process launched or a URL was entered.

Research measures include task completion, action success, incorrect actions, total task time, interventions, recovery, inference latency and resource use. Collect comprehension, usability, trust and perceived-control feedback with consent. Compare with conventional interaction on matched tasks, account for learning order and report failure cases. No participant results are currently available.

## 18 Risks constraints and mitigations

| Risk | Consequence | Mitigation and residual limitation |
| --- | --- | --- |
| Unsupported vision runtime | No usable image reasoning | Check projector and real image inference; live compatibility remains a gate |
| Model hallucination | Wrong action or false completion | Fixed policy plus native postconditions; visual verification remains fallible |
| Focus changes | Input to wrong target | Process/focus/control checks and stop; tiny OS keyboard race remains |
| Private browser content | Unwanted disclosure to local server | Clean demo profile, cropped capture, no app retention; no automatic redaction |
| Slow or out-of-memory inference | Delays or failure | Smaller images/model, timeouts, visible errors; hardware benchmark still needed |
| Browser updates or language | Address-control discovery fails | Known controls and fail-closed errors; broaden only after testing |
| Packaging differences | App fails on another PC | Keep full distribution folder and test on a clean Windows account |
| Accessibility assumptions | Unusable assistance | Formative sessions and assistive-technology testing before benefit claims |

## 19 Milestones and deliverables

| Milestone | Deliverable | Exit evidence |
| --- | --- | --- |
| M1 Reference and scope | Project analysis and preserved pitch | All ten pages reviewed and scope reconciled |
| M2 Initial application | Modular code, native UI, settings and controls | Unit/integration tests and real UI launch |
| M3 Demonstrable search | Model/runtime setup and desktop workflow | Real VLM screenshots, correct results and cancellation recorded |
| M4 Team handoff | Executable folder, scripts and documentation | Packaged launch and teammate walkthrough |
| M5 Voice and adapters | Optional speech input and model registry | Opt-in recording and adapter contract tests |
| M6 Grounded guidance | RAG, modes and explicit profiles | Cited procedures, authority tests and formative usability sessions |
| M7 Broader research | Audited task adapters and evaluation report | Repeatable tasks, consent and measured outcomes |

These are dependency-based milestones, not fabricated calendar commitments. The team should estimate effort after measuring model latency and resolving the live demonstration gate. Documentation deliverables include README, tracker, architecture, project analysis, testing report and this plan in editable Word and PDF formats.

## 20 Acceptance criteria

The reference is preserved and its full contents are reflected in the project analysis. The app launches without a development environment when packaged, exposes readable controls and a persistent Stop widget, and provides clear model setup. Screenshot capture, model transport, parsing and execution are separate modules. No model-generated code is executed.

Every enabled action is bounded and checked against the current search step. Model/server failures do not produce success. The user can stop an active task, and late inference output cannot trigger later input. Browser search is demonstrated with a real model and results are visually verified before the team marks the AI acceptance gate passed.

Tests must record expected and actual outcomes and identify real versus fake components. Documentation must describe limitations and distinguish future features from current implementation. The plan must be editable, numbered, navigable and available as a matching PDF. A teammate should be able to install, configure, launch and explain the prototype using repository instructions alone.

## 21 Known limitations and research directions

The application is a bounded hybrid assistant, not a general-purpose autonomous agent. The real local-model demonstration remains unverified. Native browser support is limited to tested control conventions; screen-reader behavior, mixed-DPI displays, clean-machine packaging and participant accessibility outcomes require additional evaluation. The status indicator does not claim visual click grounding, and the prototype has no microphone input or personal memory.

The most important next steps are to load the candidate with its projector, record a successful and failed image request, run the full search and Stop demonstration, test an English-language browser at common display scales, and conduct a teammate walkthrough. Subsequent research should examine when users prefer guidance over execution and whether access-need-conditioned delivery improves comprehension and control.

### References and setup sources

Primary project reference: klicky_research_pitch(1)(1).pdf, ten-page supplied university HCI pitch. Research descriptions and statistics attributed to the pitch are not independent validation.

Model files and format: https://huggingface.co/lmstudio-community/UI-TARS-2B-SFT-GGUF/tree/main

Original model capabilities: https://huggingface.co/ByteDance-Seed/UI-TARS-2B-SFT

Action conventions and deployment: https://github.com/bytedance/UI-TARS

Local serving: https://lmstudio.ai/docs/developer/core/server

Chat Completions interface: https://lmstudio.ai/docs/developer/openai-compat/chat-completions

Font family and licensing: https://github.com/intel/intel-one-mono

Publisher sources checked 25 October 2026. Runtime availability and local hardware compatibility must be rechecked on the demonstration machine.

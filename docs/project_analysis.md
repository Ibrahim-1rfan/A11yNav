# Klicky project analysis

Inspected 25 October 2026 before implementation. The original folder contained only
`klicky_research_pitch(1)(1).pdf` (183,854 bytes). No source, configuration,
notebooks, repository metadata or inherited AGENTS.md was found. The PDF is preserved.
All ten pages were extracted and visually reviewed, including the workflow,
comparison cards and bar chart.

## Reference interpretation

1. Title: profile-conditioned multi-agent assistance for accessible interface navigation.
2. MATE: interpreter routes modality conversions to specialist agents; example image-to-speech flow.
3. MATE classifier comparison: the slide reports 0.917 versus 0.750 accuracy over 600 prompts.
4. A diary-study slide reports eight blind users, 1,258 commands and model success rates from 37.9% to 52.5%.
5. Grounding, hidden procedures, constraint loss and termination are failure modes. Users want explanations and control.
6. PersonaAgent connects personal memory and personalized action through a per-user prompt.
7. The proposed distinction is conditioning delivery on access needs.
8. Klicky's proposed architecture has vision, documentation retrieval and profile components.
9. The comparison table distinguishes modality conversion from personalized guidance and connects RAG to hidden procedures.
10. Closing principle: one procedure, many paths.

These are claims in the supplied pitch, not new experimental findings or independently
validated research results. In particular, do not reuse its benchmark numbers as Klicky results.
Its visual language uses navy, teal, generous whitespace and simple cards.

## Scope reconciliation

The pitch prioritizes point-and-explain guidance, RAG and profiles; the implementation
request prioritizes a working assisted browser search and explicitly defers multiple
agents and RAG. Phase one therefore implements a bounded assisted workflow with visible
status, Stop and optional speech. Profile-conditioned delivery remains central to the
roadmap. No retrieval, persona memory or multi-agent system is claimed in this prototype.

## Requirements and decisions

| Requirement | Implementation decision |
| --- | --- |
| Accessible Windows entry point | Native PySide6 window, persistent compact widget, shortcut and packaged executable |
| Readable controls | Intel One Mono when installed; Consolas/system monospace fallback; adjustable font size |
| Local inference | LM Studio-compatible loopback HTTP endpoint and configurable model ID |
| Candidate verification | UI-TARS-2B-SFT GGUF exists; Qwen2-VL architecture and separate projector; runtime execution still requires a local image test |
| Observe and verify | Capture browser window in memory; model proposes one action; independent policy validates it; capture after action |
| Reliable safe search | Detect browser by process, inspect native address control, use encoded HTTPS search URL through address bar |
| Bounded actions | Fixed search sequence, exact payload matching, foreground checks, time and attempt budgets |
| Honest completion | Require actual browser URL plus model visual completion; no fallback fabricated model output |
| Sensitive operations | Entirely out of scope and blocked; no confirmation can elevate the demo to arbitrary desktop control |
| Privacy | No screenshot/query/model-output logging; loopback only; consent reminder before Start |
| Verification | Unit, mocked pipeline, HTTP contract and real component smoke tests; live model test reported separately |
| Deliverables | README, tracker, architecture, testing report and matching editable Word/PDF roadmap |

## Initial implementation sequence

1. Record analysis and confirm model protocol from official sources.
2. Implement typed configuration, safe parsing, screen preprocessing and model transport.
3. Implement constrained planning, browser discovery and desktop action guards.
4. Connect native UI, compact status widget, target ring, speech and cancellation.
5. Exercise unit/integration failure paths, launch and packaging.
6. Produce the detailed plan, render it and inspect all pages.
7. Record exact test evidence and outstanding live-model acceptance gate.

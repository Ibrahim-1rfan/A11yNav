# Evidence map and review

- Motivation: user's supplied task description; anecdotes are explicitly attributed to the team.
- Retrieval: src/cua/rag.py and assistant.py; BM25, optional semantic fusion, preserved guided steps, generated-answer validation.
- Guidance and recovery: pagewalk.py, walkthrough.py, page.py, vision.py; distinguish localization from final-state verification.
- Search-demo safety: controller.py, planning.py, verification.py; not conflated with user-operated LMS guidance.
- Speech: voice.py, speech.py, neural_tts.py; accent challenge from user, mitigations from code, no measured efficacy claim.
- Protocol: study/STUDY_DAY.md compared with analysis/analysis/README.md and all session metadata; discrepancies disclosed.
- Outcomes: analysis/analysis/data; recomputed in support/all_tasks.csv and verified_tasks.csv. Nine recorder sessions and 21 marked generated sessions; duplicate XLSX exports not counted again.
- Qualitative evidence: no retained questionnaires or interview transcripts found; no invented quotes.
- Historical tests: docs/testing_report.md; historical failures and fake-model boundaries preserved.

Blueprint: motivation -> scoped objectives -> actual implementation -> observed protocol -> measurement definitions -> pooled and recorded results -> order/overhead interpretation -> limitations -> conclusion.

Review: contribution is prototype feasibility, not novelty claim; all numerical comparisons trace to recomputation; causal claims restricted by order; no accessibility population claims; no invented user feedback. Expanded sample does not increase independent human evidence. External references receive a separate verification pass. Compilation and visual verification status are recorded in build notes.

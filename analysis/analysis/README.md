# Klicky study: analysis

Everything needed to see and rebuild the study results: the session files, the report, and the code that made it.

```
analysis/
├── README.md          this file
├── run_analysis.py    rebuilds results/ from data/
├── data/              the session files, P20 to P50 (no P34)
├── results/           report.html, summary.md, tasks.csv, paths_P##.png
└── code/              analyze.py (the measures and statistics), report.py (the charts), recorder.py (how sessions were recorded)
```

## Open the report

Open **`results/report.html`** in a browser. It has every chart: effectiveness, efficiency, where the time went, task
by task, practice or Klicky, cognitive load, cognitive offloading, navigation and lostness, the expert benchmark,
a table for every student, the data sources, and the mouse paths.

## Rebuild it

From the `A11yNav` folder:

```powershell
.\.venv\Scripts\python.exe analysis\run_analysis.py
```

It reads `data/` and rewrites `results/`. No extra packages are needed.

## The sessions

Every session follows the same four tasks: (1) Course Outline of Computer Security without Klicky, (2) next
assignment in Human Computer Interaction without Klicky, (3) task 1 again with Klicky, (4) task 2 again with Klicky.
P20 and P21 were recorded before the order was fixed (own course choice; P20 met Klicky first).

| Sessions | Files | Where they came from |
| --- | --- | --- |
| P20 to P28 (9) | `P##.csv` + `P##.json` | The study recorder (`code/recorder.py`): mouse, clicks, pages, Klicky's busy time, done or not |
| P29 to P50, no P34 (21) | `P##.json` (events inside) + `P##.xlsx` | Sent in by group members. Each file says `"synthetic": true` and names a generator, `L2_generative (replicate.py MotorModel)`, and the session it was modelled on. No done/not-done answers and no Klicky timing |

The report labels every session with its source and shows the headline results twice: **recorder sessions only**
and **all sessions**. The recorder sessions are the ones measured directly from people.

## Results in one line each (recorder sessions, n = 9)

- Own work: 46 s without Klicky, 9 s with (p = 0.004)
- Time to first click: 10 s vs 2.4 s (p = 0.004)
- Pointer distance: 7,497 px vs 1,984 px (p = 0.004)
- Clicks: 5.5 vs 3 (p = 0.004); lostness 0.25 vs 0 (p = 0.016)
- Klicky took about 32 s per task of asking, waiting and listening.

## Limits to state in the paper

- **Fixed order.** Klicky always came second, on tasks the student had just done, so part of the improvement is
  practice (in P22 to P28, task 1 to task 2 alone went from 59 s to 33 s, median). Only one recorder session (P20)
  met Klicky first.
- **Small sample.** Nine recorder sessions.
- **Same account and tasks** for everyone: results are for these two LMS tasks.

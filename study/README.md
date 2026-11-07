# Klicky Mart usability study

> **The current study runs on the real LMS:** see [STUDY_DAY.md](STUDY_DAY.md). Klicky Mart below is the earlier
> plan, kept as a demo.

Klicky Mart is a small grocery shop built only for this study. Participants do three short tasks in it
(2 or 3 steps each), once **with Klicky** and once **without**, so we can compare effort, time and errors for
two groups: Deaf and hard-of-hearing students (Type agent) and students with low vision or a motor impairment
(Speak agent). Everything runs on the study PC; nothing is bought and no personal data is collected.

## Running it

```powershell
cd D:\Classess\Projects\Klickyy\A11yNav
.\.venv\Scripts\python.exe study\server.py        # opens http://127.0.0.1:8765 in the default browser
```

Or double-click `study\run_klicky_mart.bat`. Use Chrome or Edge (Klicky reads those).
For the "with Klicky" round, start Klicky first (`launch.pyw`); for the
"without" round, quit it from the tray. Results are saved in `study\results\` (git-ignored): one JSON file per
round and one row per task in `summary.csv`.

## Goals and measures

Written as OKRs so each goal has a number we can score honestly afterwards. The targets are stretch targets:
if every one is met, they were set too low.

**Objective 1. Students in both groups finish everyday tasks with less mental effort when Klicky helps.**

| Key result | Measure | Target |
| --- | --- | --- |
| KR1.1 | NASA-TLX overall workload (0–100), with vs without Klicky, per group | 15 points lower with Klicky |
| KR1.2 | Paas mental effort per task (1–9) | Median 2 points lower with Klicky |
| KR1.3 | Hesitation: seconds from "Start task" to the first click | Halved with Klicky |

**Objective 2. Klicky helps people succeed, not just feel better.**

| Key result | Measure | Target |
| --- | --- | --- |
| KR2.1 | Task success (finished correctly, no researcher help) | 90% or more with Klicky in both groups |
| KR2.2 | Wrong actions per task (wrong item added, wrong item removed) | Under 0.5 with Klicky |
| KR2.3 | Time on task | No slower with Klicky than without |

**Objective 3. Each agent works for its own group.**

| Key result | Measure | Target |
| --- | --- | --- |
| KR3.1 | Type agent: tasks where a Deaf participant needed sound | 0 |
| KR3.2 | Speak agent: questions Klicky misheard (from Klicky's caption) | Under 1 in 10 |
| KR3.3 | System Usability Scale with Klicky | 68 or more (the usual "above average" line) |

## Tasks

Each round starts with an empty cart on the Vegetables aisle. Version A and B are matched in steps and difficulty;
half the participants do A with Klicky first, the other half B with Klicky first.

| Task | Version A | Version B | Steps |
| --- | --- | --- | --- |
| 1 | Add 2 apples to your cart | Add 3 bananas to your cart | Fruit aisle, raise the amount, Add to cart |
| 2 | Add a carton of milk to your cart | Add a cup of yoghurt to your cart | Dairy aisle, Add to cart |
| 3 | Remove the bread from your cart, then check out | Remove the eggs from your cart, then check out | Open the cart, Remove, Check out |

For task 3 the cart already holds two items.

## What is recorded

Per task: success (checked from the cart when the participant presses "I'm done"), time on task, time to the
first click, number of clicks, wrong actions, skipped or not, and the Paas effort rating. Per round: NASA-TLX
(6 scales) and SUS (10 items). Every click is also logged with its time, for later analysis.

Analysis: per-group medians, with vs without Klicky, compared with a Wilcoxon signed-rank test (small groups).

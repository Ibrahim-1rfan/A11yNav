# Study day: running a session

Each student does **2 tasks without Klicky and 2 tasks with Klicky** on the LMS, about 10–15 minutes. We measure
effort from what they do (time, pauses, wrong clicks, how the pointer moves), not from forms. You, the member
running the session, only read the tasks, press **Ctrl+S** (start) and **Ctrl+E** (end), and click whether they
did it.

While the recorder is open, Ctrl+S and Ctrl+E belong to it: the browser won't open "Save page" or jump to the
address bar. Close the recorder when you're done with sessions to get them back. If the recorder warns that another
app owns them, use **F8** instead: press it once to start and again to end.

---

## Once, before your first student

1. Klicky is installed and `scripts\check_setup.bat` says **All good** (see [SETUP.md](../SETUP.md)).
2. Install **OBS Studio** (free, [obsproject.com](https://obsproject.com/)). In OBS: Sources → **+** → **Display
   Capture** → your main screen. Settings → Output → note where recordings are saved.
3. Do one practice session yourself as **P00** and run `study\analyze.py` on it, to see that everything works.

## Your student codes

So that codes never clash between members:

| Member | Codes |
| --- | --- |
| Project lead | P01 to P09 |
| Member A | P11 to P19 |
| Member B | P21 to P29 |

**Even** numbers do the round **with Klicky first**, **odd** numbers **without Klicky first**. The recorder handles
this for you and tells you which round is which.

---

## Each student, step by step

### Before they sit down

1. Klicky is running (the "K" in the tray). The browser is open on the LMS **login page**.
2. Double-click **`study\run_recorder.bat`**. The recorder window appears bottom left. Type the student's code
   (e.g. `P11`) and click **Start this student**. It shows the first task.

### When they sit down (read this to them)

> "Thanks for helping with our HCI project. We're testing Klicky, a helper for the LMS. We'll ask you to do four
> short things on the LMS: twice on your own, twice with Klicky. We're testing Klicky, not you, so there's no wrong
> way to do it. The screen and mouse are recorded for our project only; we don't record your password, your
> keyboard or your voice, and only our group sees the recording. You can stop at any time. Is that okay?"

If they say yes:

1. They **log in to the LMS with their own account**. (If Chrome offers to save the password, click **Never**.)
2. Click **Start Recording** in OBS. It records the whole session; leave it running.

### Before the WITH-Klicky round (the same words for everyone, about 30 seconds)

> "In this round you can use Klicky. Press **Windows + Shift + K**, then ask your question out loud, or type it.
> Klicky will point at what to click."

Show them once where the keys are. Don't do a full demo.

### For each of the 4 tasks

| Step | You | The student |
| --- | --- | --- |
| 1 | Go back to the LMS **Home** page | |
| 2 | Read the task aloud, exactly as the recorder shows it | Listens |
| 3 | Press **Ctrl+S** (task starts) | Does the task |
| 4 | Watch quietly. **Don't help or hint.** If asked, say "Do what you'd do normally" | |
| 5 | When they say they're done, or give up, press **Ctrl+E** (task ends) | |
| 6 | Click **Yes, they did it** or **No / gave up** in the recorder | |

The tasks (the recorder shows them in the right order for each student):

1. *"In one of your courses, find which assignment is due next, and its due date."* (Ask them to say which course
   before you press Ctrl+S.)
2. *"Open the Course Outline of that course."*

In the second round, the same two tasks in **a different course**.

A task counts as done only if they found the right thing: the actual next assignment and its date, or the Course
Outline page is open.

### After the 4th task

1. Click **Stop Recording** in OBS. Rename the video to the student's code, e.g. `P11.mp4`.
2. The student **logs out** of the LMS. Close the browser.
3. Thank them.

---

## Rules that keep the results fair

- Read the tasks word for word. Don't explain the LMS.
- Never help during a task, and never press anything for them.
- Without Klicky means they don't press Windows + Shift + K. You can leave Klicky running.
- Start every task from the LMS Home page.
- If something breaks (Klicky crashes, the internet drops), click **No / gave up** for that task and write a note.

---

## Sending your results

After all your students, send the project lead:

- the files in **`study\recordings\`**: `P11.csv`, `P11.json` and so on (small, a few hundred KB each);
- your notes, if any.

Keep the videos on your PC unless the project lead asks for one. They show the students' courses, so don't upload
them anywhere public.

The project lead puts everyone's files in one `study\recordings` folder and runs:

```powershell
.\.venv\Scripts\python.exe study\analyze.py
```

which writes `study\results\summary.md` (the comparison table), `tasks.csv` (every task) and a mouse-path picture
per student.

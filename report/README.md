# A11yNav report

Compile from this folder:

    pdflatex -jobname=report main.tex
    pdflatex -jobname=report main.tex

Or use Tectonic:

    support\texbin\tectonic.exe main.tex --keep-logs

Tectonic produces main.pdf; copy it to report.pdf for delivery. Figures and table fragments are included; no Python is needed to compile. The bibliography is embedded in main.tex.

Recompute from the repository root:

    python report/support/analyze_report.py
    python report/support/expand_analysis.py

Recomputation needs matplotlib and openpyxl, plus the original analysis/analysis data and analysis code. Included CSV and JSON outputs preserve the calculated values for inspection. Expanded data comprises all 30 sessions; source labels remain in all_tasks.csv. No generated records are counted as independently observed people. Figures are vector PDF with PNG previews.

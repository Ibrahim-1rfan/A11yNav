from pathlib import Path
p=Path('report/main.tex');t=p.read_text()
for f in ['results_rows','task_rows']:
 t=t.replace('\\input{support/'+f+'.tex}',(p.parent/'support'/f'{f}.tex').read_text()+'\n')
t=t.replace('\\setlength{\\parskip}{5pt}','\\setlength{\\emergencystretch}{2em}\n\\setlength{\\parskip}{5pt}')
p.write_text(t)

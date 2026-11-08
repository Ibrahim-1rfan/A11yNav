import re,pathlib,csv
p=pathlib.Path('report');t=(p/'main.tex').read_text()
print('Missing refs:',set(re.findall(r'\\ref\{([^}]+)',t))-set(re.findall(r'\\label\{([^}]+)',t)))
rows=list(csv.DictReader((p/'support/all_tasks.csv').open()));old={(r['code'],r['step']):r for r in csv.DictReader(open('analysis/analysis/results/tasks.csv'))}
diffs=[]
for r in rows:
 for m in ['seconds','own_s','clicks','path_px','pauses','first_click_s']:
  if float(r[m])!=float(old[(r['code'],r['step'])][m]):diffs.append((r['code'],r['step'],m))
print('Rows verified:',len(rows),'differences:',diffs)
print('Recorded second unassisted faster:',sum(float(z[1]['seconds'])<float(z[0]['seconds']) for pcode in sorted({r['code'] for r in rows if r['source']=='recorder'}) for z in [[r for r in rows if r['code']==pcode and r['condition']=='without']]))

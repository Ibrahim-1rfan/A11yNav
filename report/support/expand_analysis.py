import csv,json,pathlib,statistics as s,importlib.util
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=pathlib.Path.cwd();out=root/'report';spec=importlib.util.spec_from_file_location('a',root/'analysis/analysis/code/analyze.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
events,meta=a.load(root/'analysis/analysis/data');rows=[]
for key,ev in sorted(events.items()):
 r=meta[key];rows.append(dict(code=key[0],step=key[1],condition=r['klicky'],task=r['task'],source=r['source'],success=r.get('success'),moves=sum(e['type']=='move' for e in ev),**a.measure(ev,r.get('klicky_busy'),r['task'])))
with (out/'support/all_tasks.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
metrics=['seconds','own_s','klicky_s','clicks','moves','path_px','pauses','first_click_s','revisits']
subsets={'Expanded dataset':rows,'Recorded sessions':[r for r in rows if r['source']=='recorder']}
stats={n:{c:{m:s.mean(r[m] for r in rr if r['condition']==c) for m in metrics} for c in ['without','with']} for n,rr in subsets.items()};(out/'support/expanded_statistics.json').write_text(json.dumps(stats,indent=2))
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,axs=plt.subplots(1,3,figsize=(10,3.3))
for ax,m,label in zip(axs,['seconds','clicks','moves'],['Elapsed time (s)','Page clicks','Movement samples']):
 vals=[stats['Expanded dataset'][c][m] for c in ['without','with']];ax.bar(['Without','With'],vals,color=['#64748b','#087e8b']);ax.set_ylabel(label);ax.bar_label(ax.containers[0],fmt='%.1f');ax.set_ylim(0,max(vals)*1.25)
fig.tight_layout();fig.savefig(out/'figures/expanded.pdf');fig.savefig(out/'figures/expanded.png',dpi=160);plt.close(fig)
fig,axs=plt.subplots(1,2,figsize=(9,3.5))
for ax,(n,rr) in zip(axs,subsets.items()):
 vals=[s.mean(r['seconds'] for r in rr if r['condition']==c and r['task']==t) for t in ['outline','assignment'] for c in ['without','with']]
 ax.bar([0,1],[vals[0],vals[2]],width=.35,label='Without',color='#64748b');ax.bar([.35,1.35],[vals[1],vals[3]],width=.35,label='With',color='#087e8b');ax.set_xticks([.175,1.175],['Outline','Assignment']);ax.set_ylabel('Mean elapsed time (s)');ax.set_title(n);ax.set_ylim(0,70);ax.legend(fontsize=8)
fig.tight_layout();fig.savefig(out/'figures/task_time.pdf');fig.savefig(out/'figures/task_time.png',dpi=160)
labels={'seconds':'Elapsed time (s)','own_s':'Time excluding assistant turns (s)','klicky_s':'Assistant turns (s)','clicks':'Page clicks','moves':'Movement samples','path_px':'Pointer distance (px)','pauses':'Pauses of at least 1 s','first_click_s':'Adjusted first-click time (s)','revisits':'Page revisits'}
lines=[]
for m in metrics:
 vals=[stats[n][c][m] for n in subsets for c in ['without','with']];lines.append(labels[m]+' & '+' & '.join(f'{v:.2f}' for v in vals)+r' \\')
(out/'support/results_rows.tex').write_text('\n'.join(lines))
lines=[]
for n,rr in subsets.items():
 for t in ['outline','assignment']:
  vals=[s.mean(r['seconds'] for r in rr if r['condition']==c and r['task']==t) for c in ['without','with']];lines.append(n+' / '+t+' & '+' & '.join(f'{v:.2f}' for v in vals)+f' & {vals[1]-vals[0]:+.2f}'+r' \\')
(out/'support/task_rows.tex').write_text('\n'.join(lines))
print(json.dumps(stats,indent=2));print('\n'.join(lines))
# File-level inventory records the inspected project scope without copying secrets or dependencies.
files=[p for p in root.rglob('*') if p.is_file() and not any(x in p.parts for x in ['.git','.venv','node_modules','report','__pycache__'])]
(out/'support/project_inventory.txt').write_text('\n'.join(str(p.relative_to(root)) for p in files),encoding='utf-8')


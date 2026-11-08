import pathlib,importlib.util,csv,json,statistics as s
root=pathlib.Path.cwd(); out=root/'report'; spec=importlib.util.spec_from_file_location('a',root/'analysis/analysis/code/analyze.py'); a=importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
tasks,res=a.load(root/'analysis/analysis/data'); rows=[]
for key,events in sorted(tasks.items()):
 r=res[key]
 if r['source']=='recorder': rows.append(dict(code=key[0],step=key[1],condition=r['klicky'],task=r['task'],success=r['success'],moves=sum(e['type']=='move' for e in events),**a.measure(events,r.get('klicky_busy'),r['task'])))
with (out/'support/verified_tasks.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
metrics=['seconds','own_s','klicky_s','clicks','moves','path_px','pauses','first_click_s','revisits']
summary={c:{m:{'mean':s.mean(r[m] for r in rows if r['condition']==c),'median_participant':s.median(s.mean(r[m] for r in rows if r['condition']==c and r['code']==p) for p in sorted({r['code'] for r in rows}))} for m in metrics} for c in ['without','with']}
(out/'support/statistics.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
for task in ['outline','assignment']:
 for c in ['without','with']:
  rr=[r for r in rows if r['task']==task and r['condition']==c]; print(task,c,s.mean(r['seconds'] for r in rr),sum(r['success'] for r in rr))
print('endpoints')
for (p,st),ev in tasks.items():
 if p in [f'P{i}' for i in range(22,29)] and st==1: print(p,[(e['type'],e['title']) for e in ev if e['type'] in ('page','end')][-4:])
import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,axs=plt.subplots(1,3,figsize=(10,3.3))
for ax,m,label in zip(axs,['seconds','clicks','path_px'],['Elapsed time (s)','Page clicks','Pointer distance (px)']):
 vals=[summary[c][m]['mean'] for c in ['without','with']]; ax.bar(['Without','With'],vals,color=['#64748b','#087e8b']);ax.set_ylabel(label);ax.bar_label(ax.containers[0],fmt='%.1f');ax.set_ylim(0,max(vals)*1.25)
fig.tight_layout();fig.savefig(out/'figures/comparison.pdf');fig.savefig(out/'figures/comparison.png',dpi=170);plt.close(fig)
fig,ax=plt.subplots(figsize=(7,3.5))
for p in sorted({r['code'] for r in rows}):
 vals=[s.mean(r['seconds'] for r in rows if r['code']==p and r['condition']==c) for c in ['without','with']];ax.plot([0,1],vals,'o-',alpha=.7,label=p)
ax.set_xticks([0,1],['Without A11yNav','With A11yNav']);ax.set_ylabel('Participant mean elapsed time (s)');ax.legend(ncol=3,fontsize=8);fig.tight_layout();fig.savefig(out/'figures/paired.pdf');fig.savefig(out/'figures/paired.png',dpi=170)
# Inspect every supplied workbook without counting its duplicate export as a new participant.
import openpyxl
inventory=[]
for f in (root/'analysis/analysis/data').glob('*.xlsx'):
 w=openpyxl.load_workbook(f,read_only=True,data_only=True); inventory.append({'file':f.name,'sheets':{sh.title: {'rows':sh.max_row,'cols':sh.max_column,'header':list(next(sh.values))} for sh in w}});w.close()
(out/'support/workbook_inventory.json').write_text(json.dumps(inventory,default=str,indent=2))

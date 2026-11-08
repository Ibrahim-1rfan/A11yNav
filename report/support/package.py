import pathlib,zipfile
root=pathlib.Path('report')
with zipfile.ZipFile(root/'A11yNav_report.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in root.rglob('*'):
  if not p.is_file() or any(x in p.parts for x in ['renderlib','texbin','preview','__pycache__']):continue
  if p.suffix in ['.zip','.log'] or p.name=='main.pdf':continue
  z.write(p,p.relative_to(root))
print('Created reproducible report archive')

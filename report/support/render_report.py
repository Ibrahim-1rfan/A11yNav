import pathlib,sys
sys.path.insert(0,str(pathlib.Path('report/support/renderlib').resolve()))
import pymupdf
from PIL import Image,ImageOps,ImageDraw
p=pathlib.Path('report');doc=pymupdf.open(p/'main.pdf');qa=p/'support/preview';qa.mkdir(exist_ok=True)
thumbs=[]
for i,page in enumerate(doc):
 pix=page.get_pixmap(matrix=pymupdf.Matrix(1,1));pix.save(qa/f'page-{i+1:02}.png')
 im=Image.open(qa/f'page-{i+1:02}.png').convert('RGB');im.thumbnail((300,425));tile=Image.new('RGB',(320,455),'#dddddd');tile.paste(im,((320-im.width)//2,20));ImageDraw.Draw(tile).text((10,438),f'Page {i+1}',fill='black');thumbs.append(tile)
cols=3;sheet=Image.new('RGB',(cols*320,((len(thumbs)+cols-1)//cols)*455),'white')
for i,im in enumerate(thumbs):sheet.paste(im,((i%cols)*320,(i//cols)*455))
sheet.save(qa/'contact.png');print('Pages:',len(doc));print('Page 2:',doc[1].get_text()[:120]);print('Text extracted:',sum(len(pg.get_text()) for pg in doc))

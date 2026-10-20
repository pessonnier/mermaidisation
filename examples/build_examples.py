"""Recréer les images de référence (Pillow requis pour ce script seulement)."""
from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont
from bpmn_mermaid.core import render
from bpmn_mermaid.html_export import export_html
ROOT=Path(__file__).resolve().parent
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
font=ImageFont.truetype(FONT,17)
small=ImageFont.truetype(FONT,15)
bold=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',22)

def draw_case(folder,title,lanes,nodes,edges):
    height=100+180*len(lanes)
    image=Image.new('RGB',(1220,height),'white');d=ImageDraw.Draw(image)
    d.text((25,20),title,font=bold,fill='#173d50')
    for i,(ident,label) in enumerate(lanes):
        y=75+i*180
        d.rectangle((20,y,1200,y+180),fill=('#eef5fa' if i%2==0 else '#f4f7ec'),outline='#70899a',width=2)
        d.line((165,y,165,y+180),fill='#70899a',width=2)
        for j,line in enumerate(label.split('\n')):d.text((35,y+65+j*24),line,font=font,fill='#173d50')
    for source,target,points,label in edges:
        d.line(points,fill='#263b49',width=3)
        x,y=points[-1];px,py=points[-2]
        import math
        angle=math.atan2(y-py,x-px)
        d.polygon([(x,y),(x-13*math.cos(angle-.45),y-13*math.sin(angle-.45)),(x-13*math.cos(angle+.45),y-13*math.sin(angle+.45))],fill='#263b49')
        if label:
            lx,ly = (665,205) if label=='Non' else (680,310) if label=='Oui' else points[0];d.text((lx+10,ly+9),label,font=small,fill='#173d50')
    for ident,lane,kind,label,x,y in nodes:
        if kind in ('start','end'):
            d.ellipse((x-21,y-21,x+21,y+21),fill='white',outline='#173d50',width=5 if kind=='end' else 2)
            d.text((x,y+36),label,font=small,fill='#173d50',anchor='mm')
        elif kind in ('exclusive','parallel'):
            d.polygon([(x,y-30),(x+30,y),(x,y+30),(x-30,y)],fill='white',outline='#173d50',width=2)
            d.text((x,y), 'X' if kind=='exclusive' else '+',font=bold,fill='#173d50',anchor='mm')
            if kind=='exclusive':d.text((x,y-50),label,font=small,fill='#173d50',anchor='mm')
        else:
            d.rounded_rectangle((x-80,y-32,x+80,y+32),radius=9,fill='white',outline='#173d50',width=2)
            d.multiline_text((x,y),label,font=font,fill='#173d50',anchor='mm',align='center',spacing=4)
    model={'pools':[{'id':'pool','label':title}],'lanes':[{'id':i,'label':l.replace('\n',' '),'pool':'pool'} for i,l in lanes],
           'nodes':[{'id':i,'lane':lane,'kind':kind,'label':label.replace('\n',' ')} for i,lane,kind,label,x,y in nodes],
           'edges':[dict(source=s,target=t,kind='sequence',label=label) for s,t,points,label in edges],
           'warnings':['Exemple pédagogique : transcription de référence préparée manuellement, pas une sortie de modèle vision.']}
    dest=ROOT/folder;dest.mkdir(exist_ok=True)
    image.save(dest/'source.png')
    (dest/'reference.json').write_text(json.dumps(model,ensure_ascii=False,indent=2)+'\n')
    (dest/'expected.mmd').write_text(render(model))
    # Les HTML sont générables mais ne sont pas tous versionnés (moteur de 2,7 Mo chacun).
    (dest/'preview.html').write_text(export_html(model))

draw_case('demande','Traitement d’une demande',[('demandeur','Demandeur'),('gestion','Gestionnaire')],[
 ('debut','demandeur','start','Début',220,165),('deposer','demandeur','task','Déposer\nla demande',380,165),
 ('complet','gestion','exclusive','Dossier complet ?',620,345),('completer','demandeur','task','Compléter\nle dossier',820,165),
 ('valider','gestion','task','Valider\nla demande',850,345),('fin','gestion','end','Fin',1100,345)],
 [('debut','deposer',[(241,165),(300,165)],''),('deposer','complet',[(460,165),(500,165),(500,345),(590,345)],''),
 ('complet','completer',[(620,315),(620,235),(820,235),(820,197)],'Non'),
 ('completer','complet',[(900,165),(1160,165),(1160,410),(620,410),(620,375)],''),
 ('complet','valider',[(650,345),(770,345)],'Oui'),('valider','fin',[(930,345),(1079,345)],'')])

draw_case('validation-parallele','Validation technique et financière',[('coord','Coordination'),('tech','Équipe\ntechnique'),('finance','Service\nfinancier')],[
 ('debut','coord','start','Début',220,165),('recevoir','coord','task','Recevoir\nle dossier',380,165),
 ('split','coord','parallel','',570,165),('technique','tech','task','Étudier\nla faisabilité',770,345),
 ('budget','finance','task','Vérifier\nle budget',770,525),('join','coord','parallel','',970,165),
 ('fin','coord','end','Fin',1130,165)],
 [('debut','recevoir',[(241,165),(300,165)],''),('recevoir','split',[(460,165),(540,165)],''),
 ('split','technique',[(600,165),(660,165),(660,345),(690,345)],''),('split','budget',[(570,195),(570,525),(690,525)],''),
 ('technique','join',[(850,345),(940,345),(940,165)],''),('budget','join',[(850,525),(970,525),(970,195)],''),
 ('join','fin',[(1000,165),(1109,165)],'')])
print('Deux images PNG et leurs modèles de référence recréés.')

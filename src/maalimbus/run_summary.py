"""Independent completed Hard run summary, never a payment receipt."""
from .vision import Text,find

def completed_hard_summary(record):
    texts=[Text(t['text'],tuple(t['box']),t['score']) for t in record.get('ocr',[])]
    size=record.get('size') or (1920,1080)
    required=[(r'^Exploration$',(.10,.10,.27,.18)),
              (r'^Complete$',(.10,.16,.27,.24)),
              (r'^Dungeon Progress$',(.10,.22,.29,.29)),
              (r'^Total Progress$',(.10,.63,.29,.71)),
              (r'^100%$',(.12,.69,.25,.81)),
              (r'^Floor\s*5\s*\[HARD\]$',(.12,.55,.29,.62))]
    if any(len(find(texts,pattern,band,size,.9))!=1 for pattern,band in required):return None
    for floor in range(1,6):
        left=(150+(floor-1)*80)/1920;right=(232+(floor-1)*80)/1920
        if len(find(texts,rf'^Floor\s*{floor}$',(left,.325,right,.365),size,.9))!=1:return None
        if len(find(texts,r'^\[HARD\]$',(left,.35,right,.38),size,.9))!=1:return None
    if len(find(texts,r'^7/7$',(.25,.38,.285,.425),size,.9))!=1:return None
    return dict(floors=[1,2,3,4,5],difficulty='hard',progress=100,
                floor_five_encounters='7/7',reward_received=False)

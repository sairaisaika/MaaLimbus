"""Account ownership reconciles with a revisioned catalogue, never public ownership."""
import re
import unicodedata
from .storage import SINNERS
from .vision import Text, find


def normalized(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', value)).casefold()


def build_index(names, catalog, provenance):
    facts = {item['id']: item for item in catalog['identities']}
    entries = {}
    for item in names:
        identity = item.get('id')
        if type(identity) is not int or not 10101 <= identity <= 11299:
            continue  # NPCs and non-playable entities are not account identities.
        sinner = identity // 100 - 100
        if not 1 <= sinner <= 12 or identity % 100 == 0:
            raise ValueError('Invalid playable identity ID')
        if identity in entries:
            raise ValueError('Duplicate identity ID')
        title = item.get('title')
        if not isinstance(title, str) or not title.strip():
            raise ValueError('Identity title missing')
        fact = facts.get(identity)
        entries[identity] = dict(id=identity, sinner_index=sinner,
            sinner=SINNERS[sinner-1], titles={'zh-CN': title},
            keywords=fact['keywords'] if fact else None,
            facts_available=fact is not None)
    return dict(schema_version=1, identities=sorted(entries.values(), key=lambda x:x['id']),
        provenance=provenance, coverage=dict(known_count=len(entries),
            live_complete=False, reason='Source revision coverage requires live catalogue reconciliation'))


def reconcile_titles(index, sinner, observations, locale):
    """Exact normalized aliases only; unresolved rows are retained, never unowned."""
    if type(sinner) is not int or not 1 <= sinner <= 12:
        raise ValueError('Invalid sinner index')
    aliases = {}
    for entry in index['identities']:
        if entry['sinner_index'] != sinner:
            continue
        title = entry['titles'].get(locale)
        if title:
            aliases.setdefault(normalized(title), []).append(entry['id'])
    owned, unresolved = [], []
    for row in observations:
        title = row.get('title')
        if not isinstance(title, str) or not title.strip() or row.get('score', 0) < .9:
            unresolved.append(dict(observation=row, reason='missing_or_low_confidence_title'))
            continue
        matches = aliases.get(normalized(title), [])
        if len(matches) != 1:
            unresolved.append(dict(observation=row, reason='unknown_or_ambiguous_title'))
            continue
        if matches[0] in {x['id'] for x in owned}:
            raise ValueError('Duplicate observed identity requires reconciliation')
        owned.append(dict(id=matches[0], owned=True, level=row.get('level'),
                          uptie=row.get('uptie'), evidence=row.get('evidence')))
    return dict(sinner_index=sinner, owned=owned, unresolved=unresolved,
                inventory_complete=False, unobserved_ownership='unknown')


def owned_page(record):
    if record.get('size') != [1920,1080]:
        raise ValueError('Unsupported inventory image size')
    texts = [Text(x['text'], tuple(x['box']), x['score']) for x in record['ocr']]
    header = find(texts, r'^IDENTITIES\s*:\s*[^\d:]+$', (.07,.03,.5,.13),record['size'],.9)
    if len(header) != 1:
        raise ValueError('Independent identity inventory header absent')
    name = normalized(''.join(c for c in unicodedata.normalize('NFKD',
        header[0].text.split(':',1)[1]) if not unicodedata.combining(c)))
    matches = [i+1 for i,s in enumerate(SINNERS) if normalized(s)==name]
    if len(matches)!=1:
        raise ValueError('Unrecognized sinner header')
    proof = record.get('owned_filter') or {}
    if proof.get('owned_checked') is not True or proof.get('all_unchecked') is not True:
        raise ValueError('Native owned-only filter proof required')
    return matches[0]


def sidebar_target(record,sinner):
    owned_page(record)
    if type(sinner) is not int or not 1<=sinner<=12:
        raise ValueError('Invalid sinner index')
    # Inventory sidebar filters, not the identity cards which equip a unit.
    row,column=divmod(sinner-1,2)
    return [65+column*101,258+row*92,78,64]


def recognize_filter(native, image):
    from maa.pipeline import JRecognitionType, JTemplateMatch
    result = {}
    for key,template,roi in (
        ('owned_checked','navigation/owned-filter-checked.png',(1687,68,49,49)),
        ('all_unchecked','navigation/all-filter-unchecked.png',(1767,68,49,49))):
        detail = native(JRecognitionType.TemplateMatch,
            JTemplateMatch(template=[template],roi=roi,threshold=[.92]),image)
        result[key] = bool(detail and detail.hit and len(detail.filtered_results)==1
                           and detail.filtered_results[0].score>=.92)
    return result


def observe_titles(native,image,record,evidence):
    """Native OCR of visible cards; no title completion or guessing from images."""
    owned_page(record)
    from maa.pipeline import JRecognitionType,JOCR
    observations=[]
    for row in range(3):
        for column in range(6):
            x=280+column*207;y=150+row*289
            roi=(x+5,y+180,185,87)
            detail=native(JRecognitionType.OCR,JOCR(roi=roi,threshold=.2),image)
            tokens=list(detail.filtered_results) if detail else []
            if not tokens:continue
            raw=[dict(text=t.text,box=list(t.box),score=t.score) for t in tokens]
            title_tokens=[t for t in raw if not re.match(r'^lv',t['text'],re.I)]
            if not title_tokens:continue
            lines=[]
            for token in sorted(title_tokens,key=lambda t:t['box'][1]+t['box'][3]/2):
                center=token['box'][1]+token['box'][3]/2
                if not lines or abs(center-lines[-1][0])>12:lines.append((center,[token]))
                else:lines[-1][1].append(token)
            ordered=[t for _,line in lines for t in sorted(line,key=lambda t:t['box'][0])]
            level_tokens=[t for t in raw if re.fullmatch(r'lv\s*[0-9]{1,2}',t['text'],re.I)
                          and t['score']>=.9]
            level=int(re.search(r'[0-9]+',level_tokens[0]['text'])[0]) if len(level_tokens)==1 else None
            observations.append(dict(title=' '.join(t['text'] for t in ordered),
                score=min(t['score'] for t in ordered),title_roi=list(roi),
                level=level,uptie=None,evidence=evidence,tokens=raw))
    return observations

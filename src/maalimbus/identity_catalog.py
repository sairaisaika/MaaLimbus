"""Offline identity catalog: community static data merged into facts we can decide on.

The catalog carries derived facts only - identity ids, Chinese names, rank, HP
numbers, resistance values and keyword tags. Raw community downloads stay under
build/upstream and are never committed. Nothing here talks to a device.

The game's own buff keywords are not our team keyword vocabulary: 破裂 is the
internal `Burst`, 呼吸法 is `Breath`, and 流血 is split across `Bleeding` and
`Laceration`. `keyword_for_buff` maps them onto `storage.KEYWORDS` so policies
can keep using the canonical names.
"""
from .storage import KEYWORDS, SINNERS

# Exact game buff keyword -> canonical team keyword.
BUFF_KEYWORDS = {
    'Bleeding': 'Bleed', 'Laceration': 'Bleed',
    'Burn': 'Burn', 'Combustion': 'Burn',
    'Sinking': 'Sinking',
    'Charge': 'Charge', 'SpecialCharge': 'Charge',
    'Breath': 'Poise', 'Poise': 'Poise',
}
# Longest-prefix-wins for the family keywords (VibrationBleeding is still Tremor).
BUFF_PREFIXES = (
    ('Vibration', 'Tremor'), ('Burst', 'Rupture'), ('Sinking', 'Sinking'),
    ('Charge', 'Charge'), ('Combustion', 'Burn'), ('Burn', 'Burn'),
    ('Breath', 'Poise'), ('Poise', 'Poise'),
    ('Bleeding', 'Bleed'), ('Laceration', 'Bleed'),
)
RESISTANCE_TYPES = ('SLASH', 'PENETRATE', 'HIT')


def keyword_for_buff(name):
    """Canonical team keyword for one game buff keyword, or None."""
    if not isinstance(name, str) or not name:
        return None
    exact = BUFF_KEYWORDS.get(name)
    if exact:
        return exact
    for prefix, keyword in BUFF_PREFIXES:
        if name.startswith(prefix):
            return keyword
    return None


def collect_buff_keywords(value, found=None):
    """Collect every `buffKeyword` inside nested skill data."""
    if found is None:
        found = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == 'buffKeyword' and isinstance(item, str):
                found.add(item)
            else:
                collect_buff_keywords(item, found)
    elif isinstance(value, list):
        for item in value:
            collect_buff_keywords(item, found)
    return found


def archetypes(buff_keywords):
    """Sorted canonical keywords for a set of game buff keywords."""
    return sorted({k for k in (keyword_for_buff(b) for b in buff_keywords) if k})


def _entry_skill_ids(entry):
    ids = []
    for skill in entry.get('attributeList') or ():
        if isinstance(skill, dict) and isinstance(skill.get('skillId'), int):
            ids.append(skill['skillId'])
    for skill_id in entry.get('defenseSkillIDList') or ():
        if isinstance(skill_id, int):
            ids.append(skill_id)
    return ids


def _unit_names(raw_values, units):
    names = []
    for raw in raw_values or ():
        if not isinstance(raw, str):
            continue
        name = units.get(raw) or units.get('UnitKeyword_' + raw) or ''
        if name and name not in names:
            names.append(name)
    return names


def merge(personalities, skills, names, units, *, source=None, commit=None):
    """Merge downloaded payloads into the committed catalog.

    `personalities` is a flat list of personality entries, `skills` a flat list
    of `{id, skillData}` entries, `names` maps identity id to the localized
    name/title and `units` maps unit/association keyword ids to their text.
    """
    skill_by_id = {}
    for skill in skills:
        if isinstance(skill, dict) and isinstance(skill.get('id'), int):
            skill_by_id[skill['id']] = skill
    identities = []
    seen = set()
    for entry in personalities:
        if not isinstance(entry, dict) or not isinstance(entry.get('id'), int):
            raise ValueError('Personality entry needs an integer id')
        identity_id = entry['id']
        if identity_id in seen:
            raise ValueError('Duplicate identity id %d' % identity_id)
        seen.add(identity_id)
        sinner = entry.get('characterId')
        if not isinstance(sinner, int) or not 1 <= sinner <= len(SINNERS):
            sinner = identity_id // 10000
        if not 1 <= sinner <= len(SINNERS):
            raise ValueError('Identity %d has no sinner' % identity_id)
        hp = entry.get('hp') or {}
        resistances = {}
        for item in (entry.get('resistInfo') or {}).get('atkResistList') or ():
            if isinstance(item, dict) and item.get('type') in RESISTANCE_TYPES:
                resistances[item['type']] = item.get('value')
        buffs = set()
        for skill_id in _entry_skill_ids(entry):
            skill = skill_by_id.get(skill_id)
            if skill:
                collect_buff_keywords(skill.get('skillData'), buffs)
        localized = names.get(identity_id) or {}
        identities.append({
            'id': identity_id,
            'sinner': sinner,
            'sinner_name': SINNERS[sinner - 1],
            'name': localized.get('name', ''),
            'title': (localized.get('title', '') or '').replace('\n', ' '),
            'rank': entry.get('rank'),
            'hp_default': hp.get('defaultStat'),
            'hp_increment': hp.get('incrementByLevel'),
            'keywords': archetypes(buffs),
            'buff_keywords': sorted(buffs),
            'unit_keywords': _unit_names(entry.get('unitKeywordList'), units),
            'association': _unit_names(entry.get('associationList'), units),
            'resistances': resistances,
            'skills': sorted(set(_entry_skill_ids(entry))),
        })
    identities.sort(key=lambda i: (i['sinner'], i['id']))
    for identity in identities:
        unknown = set(identity['keywords']) - set(KEYWORDS)
        if unknown:
            raise ValueError('Keyword outside the team vocabulary: %r' % sorted(unknown))
    catalog = {'version': 1, 'sinners': list(SINNERS),
               'keyword_map': dict(BUFF_KEYWORDS),
               'keyword_prefixes': {p: k for p, k in BUFF_PREFIXES},
               'identities': identities}
    if source:
        catalog['source'] = list(source)
    if commit:
        catalog['commit'] = dict(commit)
    return catalog


def by_id(catalog):
    """Identity id -> identity, for lookups."""
    return {i['id']: i for i in catalog.get('identities') or ()}


def with_keyword(catalog, sinner, keyword, *, owned=None):
    """Identities of one sinner carrying a keyword, strongest first.

    Mirrors `auto_formation.choose_identity` ordering (rank, then hp) so a
    caller can fall back to the offline catalog when the game UI cannot be
    filtered.
    """
    found = [i for i in catalog.get('identities') or ()
             if i['sinner'] == sinner and keyword in (i.get('keywords') or ())]
    if owned is not None:
        found = [i for i in found if i['id'] in owned]
    return sorted(found, key=lambda i: (-(i.get('rank') or 0), -(i.get('hp_default') or 0), i['id']))

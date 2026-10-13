"""Fail public exports on local user paths and literal player identifiers.

Reports contain file/line/category only. Images and Git history still need review.
"""
import re
TEXT={'.md','.py','.json','.jsonl','.toml','.txt','.ps1','.yml','.yaml','.js','.ts','.tsx','.rs','.html'}
PATTERNS={
    'local_user_path':re.compile(r'(?i)[A-Z]:[\\/]+Users[\\/]+(?!Public\b|Default\b|<|%|\$)[^\\/\s"\x27]+'),
    'player_id_literal':re.compile(r'(?i)(?:\buser[_ -]?id|\buid|玩家(?:编号|ID)|好友(?:代码|ID))\s*[:=]\s*["\x27]?[A-Z]?\d{7,}')}

def public_file(path):
    return (path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc'
            and not path.name.endswith('.local.json') and path.suffix not in {'.log','.jsonl'})

def findings(paths):
    result=[]
    for path in paths:
        if path.suffix.lower() not in TEXT:continue
        try:content=path.read_text(encoding='utf-8')
        except UnicodeError:continue
        for number,line in enumerate(content.splitlines(),1):
            for category,pattern in PATTERNS.items():
                if pattern.search(line):result.append(dict(file=path.as_posix(),line=number,category=category))
    return result

def require_public(paths):
    paths=list(paths);issues=findings(paths)
    if issues:
        # Never embed the matched identifier or an absolute home path in errors.
        first=issues[0]
        raise ValueError('Public privacy gate: %s in %s line %d (%d findings)'%
                         (first['category'],first['file'].split('/')[-1],first['line'],len(issues)))
    return paths

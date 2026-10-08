"""Preferred-language helpers shared by profile editing and opportunity ranking."""
from __future__ import annotations

LANGUAGES = {
    'english': ('en', 'GB'),
    'mandarin chinese': ('zh', 'CN'),
    'chinese': ('zh', 'CN'),
    'german': ('de', 'DE'),
    'french': ('fr', 'FR'),
    'spanish': ('es', 'ES'),
    'portuguese': ('pt', 'PT'),
    'italian': ('it', 'IT'),
    'dutch': ('nl', 'NL'),
    'japanese': ('ja', 'JP'),
    'korean': ('ko', 'KR'),
    'indonesian': ('id', 'ID'),
    'malay': ('ms', 'MY'),
    'thai': ('th', 'TH'),
    'vietnamese': ('vi', 'VN'),
    'filipino': ('tl', 'PH'),
    'tagalog': ('tl', 'PH'),
    'hindi': ('hi', 'IN'),
    'polish': ('pl', 'PL'),
    'swedish': ('sv', 'SE'),
    'norwegian': ('no', 'NO'),
    'danish': ('da', 'DK'),
    'finnish': ('fi', 'FI'),
}
CODE_TO_NAME = {}
for _name, (_code, _country) in LANGUAGES.items():
    CODE_TO_NAME.setdefault(_code, _name)


def normalise_language(value: str) -> str:
    raw=' '.join(str(value or '').strip().split())
    if not raw:
        return ''
    low=raw.lower().replace('_','-')
    base=low.split('-',1)[0]
    if low in LANGUAGES:
        return low
    if base in CODE_TO_NAME:
        return CODE_TO_NAME[base]
    return low


def language_code(value: str) -> str:
    low=normalise_language(value)
    if low in LANGUAGES:
        return LANGUAGES[low][0]
    if len(low)==2 and low.isalpha():
        return low
    return ''


def preferred_language_codes(profile) -> set[str]:
    values=(getattr(profile,'scope_json',{}) or {}).get('preferred_languages')
    if not isinstance(values,list) or not values:
        values=['english']
    out={language_code(v) for v in values}
    return {x for x in out if x}


def preferred_language_delta(profile, detected_code: str) -> int:
    code=(detected_code or '').strip().lower().replace('_','-').split('-',1)[0]
    if not code:
        return 0
    preferred=preferred_language_codes(profile)
    return 6 if code in preferred else -8


def _flag(country: str) -> str:
    if not country or len(country)!=2:
        return ''
    return ''.join(chr(127397+ord(ch)) for ch in country.upper())


def language_options() -> list[dict]:
    seen=set(); out=[]
    for name,(code,country) in LANGUAGES.items():
        if code in seen:
            continue
        seen.add(code)
        out.append({'value':name,'label':name.title(),'code':code,'flag':_flag(country)})
    return out

"""Search query normalization helpers.

These helpers run immediately before provider dispatch.  They keep quoted phrases,
operators and site: scopes intact, but remove duplicated generated tokens so ScoutBox
search activity stays readable and providers do not receive redundant query terms.
"""
from __future__ import annotations

import re
from typing import Iterable

_TOKEN_RE = re.compile(r'"[^"\n]*"|\'[^\'\n]*\'|site:[^\s]+|\b(?:AND|OR|NOT)\b|[()]+|[^\s]+', re.I)
_ROLE_GENERIC = {
    'engineer', 'engineering', 'developer', 'development', 'dev', 'software',
    'role', 'roles', 'job', 'jobs', 'career', 'careers', 'hiring', 'hire',
    'company', 'companies', 'opportunity', 'opportunities', 'work', 'remote',
}
_EQUIV = {
    'engineering': 'engineer',
    'engineers': 'engineer',
    'developer': 'developer',
    'developers': 'developer',
    'development': 'developer',
    'careers': 'career',
    'jobs': 'job',
    'roles': 'role',
    'opportunities': 'opportunity',
    'companies': 'company',
    'hiring': 'hire',
    'hires': 'hire',
}
_PUNCT_STRIP = '.,;:!?|/\\[]{}'


def _token_key(token: str) -> str:
    raw = str(token or '').strip().strip(_PUNCT_STRIP).casefold()
    if not raw:
        return ''
    if raw.startswith('site:'):
        host = re.sub(r'^site:https?://', 'site:', raw)
        return host.rstrip('/')
    raw = re.sub(r"^[\"']|[\"']$", '', raw)
    raw = re.sub(r'[^a-z0-9+#.]+', '', raw)
    return _EQUIV.get(raw, raw)



_SITE_TOKEN_RE = re.compile(r'^site:', re.I)
_BARE_DOMAIN_RE = re.compile(r'^(?:https?://)?(?:www\.)?([a-z0-9](?:[a-z0-9-]{0,62}\.)+[a-z]{2,63})(?:[/?#][^\s]*)?$', re.I)

def _repair_generated_quotes(text: str) -> str:
    """Never dispatch a generated query with a dangling double quote."""
    value=re.sub(r'\s+',' ',str(text or '')).strip()
    if value.count(chr(34)) % 2:
        value=value.replace(chr(34),' ')
    return re.sub(r'\s+',' ',value).strip()


def _normalize_site_scope(token: str) -> str:
    """Return a host-only site: operator or an empty string."""
    raw = str(token or '').strip().strip('()[]{}')
    if not _SITE_TOKEN_RE.match(raw):
        return ''
    value = raw[5:].strip().strip('"\'')
    value = re.sub(r'^https?://', '', value, flags=re.I)
    host = value.split('/', 1)[0].split('?', 1)[0].split('#', 1)[0].split(':', 1)[0]
    host = host.lower().removeprefix('www.').strip()
    return ('site:' + host) if host else ''


def split_multi_site_search_queries(query: str) -> list[str]:
    """Split an outgoing provider query into one query per site: scope.

    This is intentionally a dispatch-time guard. Query builders may combine source
    domains while composing a campaign/search variant, but public providers should
    never receive `site:a site:b terms` because recall and provider semantics become
    unpredictable. Quoted phrases are preserved and duplicate site scopes collapse.
    """
    text = _repair_generated_quotes(query)
    if not text:
        return []
    tokens = _TOKEN_RE.findall(text)
    if not tokens:
        return [text]
    sites: list[str] = []
    seen_sites: set[str] = set()
    rest: list[str] = []
    for tok in tokens:
        tok = str(tok or '').strip()
        if not tok:
            continue
        if tok.lower().startswith('site:'):
            site = _normalize_site_scope(tok)
            key = site.casefold()
            if site and key not in seen_sites:
                seen_sites.add(key)
                sites.append(site)
        else:
            rest.append(tok)
    if len(sites) <= 1:
        return [text]
    rest_text = re.sub(r'\s+', ' ', ' '.join(rest)).strip()
    return [re.sub(r'\s+', ' ', (site + (' ' + rest_text if rest_text else ''))).strip() for site in sites]


def normalize_generated_search_query(query: str) -> str:
    """Remove duplicated generated terms while preserving provider query syntax.

    Quoted phrases, site: operators and boolean punctuation are preserved exactly.  For
    generic role words that occur repeatedly after multiple role fragments are joined,
    the final occurrence is retained so `emulation engineer virtualization engineer`
    becomes `emulation virtualization engineer`.
    """
    text = _repair_generated_quotes(query)
    if not text:
        return ''
    tokens = _TOKEN_RE.findall(text)
    if not tokens:
        return text

    # Keep one site: scope, exactly as first normalized by the existing sanitizer.
    first_site_seen = False
    prelim: list[str] = []
    for tok in tokens:
        if not tok or not tok.strip():
            continue
        if tok.lower().startswith('site:'):
            if first_site_seen:
                continue
            first_site_seen = True
            tok=_normalize_site_scope(tok) or tok
        elif not tok.startswith(('"', "'")):
            match=_BARE_DOMAIN_RE.match(tok.strip('.,;:!?'))
            if match:
                site=_normalize_site_scope('site:'+match.group(1))
                if first_site_seen or not site:
                    continue
                first_site_seen=True; tok=site
        prelim.append(tok.strip())

    # Generic role/common terms should usually appear once, preferably at the end of the
    # generated role phrase.  Distinctive terms keep first occurrence.
    last_generic_idx: dict[str, int] = {}
    for idx, tok in enumerate(prelim):
        if tok.startswith(('"', "'")) or tok.lower().startswith('site:') or tok.upper() in {'AND','OR','NOT'} or tok in {'(',')'}:
            continue
        key = _token_key(tok)
        if key in _ROLE_GENERIC:
            last_generic_idx[key] = idx

    seen: set[str] = set()
    out: list[str] = []
    for idx, tok in enumerate(prelim):
        upper = tok.upper()
        if tok.startswith(('"', "'")) or tok.lower().startswith('site:') or upper in {'AND','OR','NOT'} or tok in {'(',')'}:
            out.append(tok)
            continue
        key = _token_key(tok)
        if not key:
            continue
        if key in _ROLE_GENERIC:
            if last_generic_idx.get(key) != idx:
                continue
            if key in seen:
                continue
            seen.add(key)
            # Use the canonical readable form for common morphology, but leave `dev`
            # unchanged because it is a distinct user/search idiom.
            display = {'career': 'careers', 'job': 'jobs', 'hire': 'hiring', 'role': 'roles', 'opportunity': 'opportunities'}.get(key, key)
            out.append(display)
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(tok)

    normalized = re.sub(r'\s+', ' ', ' '.join(out)).strip()
    # Cosmetic cleanup around parentheses introduced by boolean/grouped queries.
    normalized = normalized.replace('( ', '(').replace(' )', ')')
    return normalized or text

"""Shared multi-location parsing and display helpers for ScoutBox.

Locations are user-facing recruitment eligibility labels, not always ISO countries.
A posting can legitimately be open to multiple countries or broad recruiter regions
such as Europe, APAC or Worldwide.
"""
from __future__ import annotations

import re
from typing import Any

from portal.ui import COUNTRIES

REGION_DEFS = {
    'Europe': {
        'code': 'EUROPE', 'icon': 'eu',
        'aliases': ('europe','european region','europe countries'),
    },
    'EU': {'code': 'EU', 'icon': 'eu', 'aliases': ('eu','e.u.','european union','european union only','eu only','eu countries','eu member states')},
    'EEA': {'code': 'EEA', 'icon': 'eu', 'aliases': ('eea','european economic area')},
    'EU/EEA': {'code': 'EU_EEA', 'icon': 'eu', 'aliases': ('eu/eea','eu & eea','eu and eea','european union / eea')},
    'UK & Europe': {'code': 'UK_EUROPE', 'icon': 'eu', 'aliases': ('uk & europe','uk and europe','uk/europe','europe and uk','europe/uk','eu/uk','uk/eu')},
    'UK & Ireland': {'code': 'UK_IRELAND', 'icon': 'eu', 'aliases': ('uk & ireland','uk and ireland','uk/ireland','ireland and uk')},
    'DACH': {'code': 'DACH', 'icon': 'eu', 'aliases': ('dach','dach region')},
    'CEE': {'code': 'CEE', 'icon': 'eu', 'aliases': ('cee','central and eastern europe','central/eastern europe','central eastern europe')},
    'Benelux': {'code': 'BENELUX', 'icon': 'eu', 'aliases': ('benelux','benelux region')},
    'Nordics': {'code': 'NORDICS', 'icon': 'eu', 'aliases': ('nordics','nordic region','nordic countries','scandinavia','scandinavian region')},
    'APAC': {'code': 'APAC', 'icon': 'apac', 'aliases': ('apac','asia pacific','asia-pacific','asia/pacific')},
    'ASEAN': {'code': 'ASEAN', 'icon': 'apac', 'aliases': ('asean','asean region','southeast asia','south-east asia','south east asia')},
    'ANZ': {'code': 'ANZ', 'icon': 'apac', 'aliases': ('anz','australia and new zealand','australia/new zealand','australia & new zealand')},
    'Asia': {'code': 'ASIA', 'icon': 'asia', 'aliases': ('asia','asian region')},
    'EMEA': {'code': 'EMEA', 'icon': 'emea', 'aliases': ('emea','europe middle east africa','europe, middle east and africa','europe/middle east/africa')},
    'MENA': {'code': 'MENA', 'icon': 'middle_east', 'aliases': ('mena','middle east and north africa','middle east & north africa','middle east/north africa')},
    'GCC': {'code': 'GCC', 'icon': 'middle_east', 'aliases': ('gcc','gulf cooperation council','gulf countries','gulf region')},
    'Middle East': {'code': 'MIDDLE_EAST', 'icon': 'middle_east', 'aliases': ('middle east','middle eastern region')},
    'Africa': {'code': 'AFRICA', 'icon': 'africa', 'aliases': ('africa','african region')},
    'LATAM': {'code': 'LATAM', 'icon': 'latam', 'aliases': ('latam','latin america','latin america region','latin-america')},
    'South America': {'code': 'SOUTH_AMERICA', 'icon': 'latam', 'aliases': ('south america','south american region')},
    'Central America': {'code': 'CENTRAL_AMERICA', 'icon': 'latam', 'aliases': ('central america','central american region')},
    'Caribbean': {'code': 'CARIBBEAN', 'icon': 'latam', 'aliases': ('caribbean','caribbean region')},
    'North America': {'code': 'NORTH_AMERICA', 'icon': 'north_america', 'aliases': ('north america','na region','us/canada','usa/canada','canada/us','canada/usa')},
    'Americas': {'code': 'AMERICAS', 'icon': 'north_america', 'aliases': ('americas','the americas','amer region','amer')},
    'Worldwide': {'code': 'WORLDWIDE', 'icon': 'global', 'aliases': ('worldwide','global','anywhere','remote anywhere','remote worldwide','work from anywhere')},
}

REGION_LABELS = list(REGION_DEFS.keys())
_LOCATION_PLACEHOLDERS = {'', 'remote', 'fully remote', 'hybrid', 'on-site', 'onsite', 'not specified', 'unspecified', 'unknown', 'n/a', 'na', 'none', 'null', 'tbd'}
_FORBIDDEN_LOCATION_LABELS = {'worldwide', 'global', 'anywhere', 'remote worldwide', 'remote anywhere', 'work from anywhere'}
LOCATION_CHOICES = [x for x in REGION_LABELS if x.casefold() not in _FORBIDDEN_LOCATION_LABELS and REGION_DEFS.get(x, {}).get('code') != 'WORLDWIDE'] + [c for c in COUNTRIES if c not in REGION_LABELS]
_COUNTRY_ALIASES = {
    'usa': 'United States', 'us': 'United States', 'u.s.': 'United States', 'u.s.a.': 'United States', 'united states of america': 'United States',
    'uk': 'United Kingdom', 'u.k.': 'United Kingdom', 'gb': 'United Kingdom', 'gbr': 'United Kingdom', 'great britain': 'United Kingdom', 'britain': 'United Kingdom',
    'uae': 'United Arab Emirates', 'republic of korea': 'South Korea', 'korea, republic of': 'South Korea', 'czech republic': 'Czechia',
}


def clean_location_text(value: Any, limit: int = 1200) -> str:
    return ' '.join(str(value or '').replace('\xa0', ' ').replace('\n', ' ').split()).strip()[:limit]


def _word_pattern(term: str) -> str:
    escaped = re.escape(term).replace('\\ ', r'[-\s]+')
    return r'(?<![A-Za-z0-9])' + escaped + r'(?![A-Za-z0-9])'


def canonical_location_label(value: Any) -> str:
    raw = clean_location_text(value, 160).strip(' .,:;|/\\')
    if not raw:
        return ''
    folded = raw.casefold()
    if folded in _FORBIDDEN_LOCATION_LABELS:
        return ''
    for label, spec in REGION_DEFS.items():
        if folded == label.casefold() or folded in {a.casefold() for a in spec.get('aliases', ())}:
            return label
    aliased = _COUNTRY_ALIASES.get(folded, raw)
    for country in COUNTRIES:
        if country.casefold() == aliased.casefold():
            return country
    return ''


def location_icon(label: Any) -> str:
    canonical = canonical_location_label(label) or clean_location_text(label, 80)
    spec = REGION_DEFS.get(canonical)
    if not spec:
        return ''
    icon = spec.get('icon')
    return {
        'eu': '🇪🇺', 'apac': '🌏', 'asia': '🌏', 'emea': '🌍', 'middle_east': '🌍',
        'africa': '🌍', 'latam': '🌎', 'north_america': '🌎', 'global': '🌐',
    }.get(icon, '🌐')


def _gcc_is_geographic(raw_label: Any, evidence: Any = '') -> bool:
    """Disambiguate Gulf-region GCC from GNU Compiler Collection references."""
    label=clean_location_text(raw_label,120)
    context=clean_location_text(evidence,800)
    blob=f'{label} {context}'.casefold()
    if re.search(r'\b(?:gnu compiler|compiler|toolchain|cross[- ]compil|buildroot|gcc version|g\+\+)\b',blob):
        return False
    return bool(re.search(r'\b(?:gulf cooperation council|gulf countries|gulf region|gcc (?:region|countries|states|market)|(?:based|located|remote|hiring|roles?|candidates?|across|within|in)\s+(?:the\s+)?gcc)\b',blob))


def _make_item(label: str, *, source: str, evidence: str, kind: str | None = None) -> dict:
    raw_label = clean_location_text(label, 120)
    if raw_label.casefold() in _FORBIDDEN_LOCATION_LABELS:
        return {}
    label = canonical_location_label(raw_label)
    if not label:
        return {}
    if label == 'GCC' and not _gcc_is_geographic(raw_label,evidence):
        return {}
    if label.casefold() in _FORBIDDEN_LOCATION_LABELS or REGION_DEFS.get(label, {}).get('code') == 'WORLDWIDE':
        return {}
    if kind is None:
        kind = 'region' if label in REGION_DEFS else 'country'
    code = REGION_DEFS.get(label, {}).get('code') if kind == 'region' else label
    return {
        'kind': kind,
        'label': label,
        'code': str(code or label)[:40],
        'icon': REGION_DEFS.get(label, {}).get('icon', ''),
        'source': str(source or '')[:80],
        'evidence': clean_location_text(evidence, 400),
    }


def parse_location_items(value: Any, *, source: str = 'page_location', evidence: str = '') -> list[dict]:
    raw = clean_location_text(value, 2200)
    if not raw or raw.casefold() in _LOCATION_PLACEHOLDERS:
        return []
    evidence = evidence or raw
    out = []
    seen = set()

    def add(label, kind=None):
        item = _make_item(label, source=source, evidence=evidence, kind=kind)
        if not item:
            return
        key = item['label'].casefold()
        if key in seen:
            return
        # Prefer the most specific explicit recruiter region over components that can
        # also appear inside its long-form alias (for example APAC -> Asia Pacific).
        suppressions={
            'UK & Europe': {'Europe'},
            'EU/EEA': {'EU','EEA'},
            'APAC': {'Asia'},
            'EMEA': {'Europe','Middle East','Africa'},
            'MENA': {'Middle East','Africa'},
        }
        for specific,components in suppressions.items():
            if item['label'] in components and specific.casefold() in seen:
                return
            if item['label'] == specific:
                component_keys={x.casefold() for x in components}
                out[:] = [x for x in out if str(x.get('label') or '').casefold() not in component_keys]
                seen.difference_update(component_keys)
        seen.add(key); out.append(item)

    # Normalize separators while preserving country names with spaces.
    lowered = raw.casefold()
    for label, spec in REGION_DEFS.items():
        if label.casefold() in _FORBIDDEN_LOCATION_LABELS or spec.get('code') == 'WORLDWIDE':
            continue
        aliases = [label] + list(spec.get('aliases', ()))
        for alias in sorted(aliases, key=len, reverse=True):
            if re.search(_word_pattern(alias.casefold()), lowered, flags=re.I):
                add(label, 'region'); break

    aliases = dict(_COUNTRY_ALIASES)
    for alias, country in aliases.items():
        if re.search(_word_pattern(alias), lowered, flags=re.I):
            add(country, 'country')
    # Scan canonical country labels. Longest first prevents partial shorter matches.
    for country in sorted(COUNTRIES, key=len, reverse=True):
        if country in REGION_DEFS or country == 'Remote worldwide':
            continue
        if re.search(_word_pattern(country.casefold()), lowered, flags=re.I):
            add(country, 'country')

    # Conservative city/state hints for common cases retained from job boards.
    if not out:
        city_map = {
            'vancouver': 'Canada', 'toronto': 'Canada', 'montreal': 'Canada', 'calgary': 'Canada', 'ottawa': 'Canada',
            'singapore': 'Singapore', 'london': 'United Kingdom', 'cairo': 'Egypt', 'dubai': 'United Arab Emirates',
            'dallas': 'United States', 'houston': 'United States', 'austin': 'United States', 'boston': 'United States',
            'chicago': 'United States', 'new york': 'United States', 'san francisco': 'United States', 'mountain view': 'United States',
        }
        for city, country in city_map.items():
            if re.search(_word_pattern(city), lowered, flags=re.I):
                add(country, 'country'); break
    return out[:12]


def normalize_location_items(value: Any, *, source: str = 'stored', evidence: str = '') -> list[dict]:
    if isinstance(value, list):
        out = []
        seen = set()
        for item in value:
            if isinstance(item, dict):
                label = canonical_location_label(item.get('label') or item.get('country') or item.get('name') or item.get('code'))
                src = item.get('source') or source
                ev = item.get('evidence') or evidence or item.get('reason') or ''
            else:
                label = canonical_location_label(item)
                src = source; ev = evidence
            if not label:
                continue
            made = _make_item(label, source=src, evidence=ev, kind=('region' if label in REGION_DEFS else 'country'))
            key = made['label'].casefold()
            if key not in seen:
                seen.add(key); out.append(made)
        return out[:12]
    return parse_location_items(value, source=source, evidence=evidence)



def strip_non_company_location_items(items_or_text: Any) -> list[dict]:
    """Company/lead/contact locations must be concrete; Worldwide is only job eligibility."""
    return [x for x in normalize_location_items(items_or_text) if str(x.get('label') or '').casefold() not in _FORBIDDEN_LOCATION_LABELS and str(x.get('code') or '').casefold() not in _FORBIDDEN_LOCATION_LABELS and str(x.get('code') or '') != 'WORLDWIDE']

def location_labels(items_or_text: Any) -> list[str]:
    return [x['label'] for x in normalize_location_items(items_or_text) if x.get('label')]


def location_display_text(items_or_text: Any, *, limit: int = 4) -> str:
    """Display one or more canonical countries/regions compactly."""
    labels = location_labels(items_or_text)
    if not labels:
        return ''
    visible = labels[:max(1, int(limit or 4))]
    suffix = f' +{len(labels)-len(visible)}' if len(labels) > len(visible) else ''
    return ', '.join(visible) + suffix


def legacy_location_text(items_or_text: Any, *, limit: int = 120) -> str:
    """Compatibility string stored in legacy country/company_country fields."""
    text = ', '.join(location_labels(items_or_text))
    return text[:max(20, int(limit or 120))]


def location_title(items_or_text: Any) -> str:
    """Safe user-facing location tooltip.

    Older tooltips exposed extraction provenance and raw structured JSON-LD evidence.
    Dense list rows should only show the cleaned locations the user can act on.
    Internal provenance remains available in diagnostics/export.
    """
    labels = location_labels(items_or_text)
    if not labels:
        return ''
    return 'Location: ' + ', '.join(labels[:8])


def primary_legacy_location(items_or_text: Any) -> str:
    items = normalize_location_items(items_or_text)
    for item in items:
        if item.get('kind') == 'country':
            return item.get('label') or ''
    return (items[0].get('label') if items else '') or ''


def _looks_like_expanded_structured_country_array(items: Any) -> bool:
    """Detect provider-expanded eligibility regions stored as country arrays.

    Recruiter/job-board schemas sometimes expand a human-facing region such as LATAM,
    APAC or Europe into many ``Country`` objects. ScoutBox must not turn that provider
    implementation detail into a long list of apparent job locations. Small explicit
    multi-country lists remain valid; only larger structured JobPosting arrays are
    treated as expansion artifacts.
    """
    normalized = normalize_location_items(items)
    if len(normalized) < 5:
        return False
    sources = {str(x.get('source') or '').casefold() for x in normalized}
    return 'structured_jobposting' in sources


def _record_explicit_region_items(record: Any) -> list[dict]:
    """Return recruiter/source region labels retained on an Opportunity.

    This is intentionally conservative: only fields whose key describes location,
    eligibility or remote scope are searched. It lets old rows recover a source-native
    ``LATAM``/``APAC``/``EMEA`` label without inferring a region from a country list.
    """
    values = []
    role_value = getattr(record, 'role_location', '') if hasattr(record, 'role_location') else ''
    if role_value:
        values.append(('role_location', role_value))
    facts = getattr(record, 'extracted_facts', None)
    key_re = re.compile(r'(?i)(?:location|region|eligib|remote|workplace|country)')
    def walk(node, path='', depth=0):
        if depth > 5:
            return
        if isinstance(node, dict):
            for key, value in node.items():
                next_path = f'{path}.{key}' if path else str(key)
                path_fold=next_path.casefold()
                company_only=any(token in path_fold for token in ('company_location','company.country','headquarter','hq_location','company_hq'))
                if key_re.search(str(key)) and not company_only and isinstance(value, (str, int, float)):
                    values.append((next_path, str(value)))
                elif isinstance(value, (dict, list, tuple)):
                    walk(value, next_path, depth+1)
        elif isinstance(node, (list, tuple)):
            for idx, value in enumerate(node[:30]):
                walk(value, f'{path}[{idx}]', depth+1)
    if isinstance(facts, (dict, list, tuple)):
        walk(facts)
    out=[]; seen=set()
    for source, value in values:
        for item in parse_location_items(value, source=source, evidence=str(value or '')):
            if item.get('kind') != 'region':
                continue
            key=str(item.get('label') or '').casefold()
            if key and key not in seen:
                seen.add(key); out.append(item)
    return normalize_location_items(out)


def _looks_like_raw_structured_location(value: Any) -> bool:
    text = clean_location_text(value, 800)
    return bool(text.startswith(('[', '{')) or '"@type"' in text or "'@type'" in text or _looks_like_expanded_structured_country_array(parse_location_items(text)))


def record_location_items(record: Any) -> list[dict]:
    # Opportunities display/filter from the recruiter/source role_location when present.
    # The JSON locations field may contain old expanded region-country arrays; do not let
    # those override a concise source label such as Europe, Ukraine or USA, Europe.
    if hasattr(record, 'locations'):
        role_value = getattr(record, 'role_location', '') if hasattr(record, 'role_location') else ''
        explicit_regions = _record_explicit_region_items(record)
        if role_value and _looks_like_raw_structured_location(role_value):
            return explicit_regions
        role_items = parse_location_items(role_value, source='role_location', evidence=str(role_value or ''))
        if role_items:
            return normalize_location_items(role_items)
        stored_locations = getattr(record, 'locations', None)
        if _looks_like_expanded_structured_country_array(stored_locations):
            return explicit_regions
        items = normalize_location_items(stored_locations)
        if items:
            return items
        parts = []
        for field, src in (('country', 'country'), ('remote_text', 'remote_text')):
            value = getattr(record, field, '') if hasattr(record, field) else ''
            if value and _looks_like_raw_structured_location(value):
                continue
            parts.extend(parse_location_items(value, source=src, evidence=str(value or '')))
        return normalize_location_items(parts)
    if hasattr(record, 'company_locations'):
        items = strip_non_company_location_items(getattr(record, 'company_locations', None))
        if items:
            return items
        return strip_non_company_location_items(parse_location_items(getattr(record, 'company_country', ''), source='company_country'))
    # Leads and company/contact rows do not have role_location; Worldwide/Global is not a company location.
    return strip_non_company_location_items(parse_location_items(getattr(record, 'country', '') or getattr(record, 'company_country', ''), source='country'))


def record_location_display(record: Any, *, limit: int = 3) -> str:
    return location_display_text(record_location_items(record), limit=limit)

def record_location_filter_text(record: Any) -> str:
    labels = [x.get('label') for x in record_location_items(record) if x.get('label')]
    return ' '.join(labels)


def record_location_title(record: Any) -> str:
    return location_title(record_location_items(record))

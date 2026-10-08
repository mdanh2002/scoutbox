"""Market-aware discovery configuration.

Discovery Markets decide where acquisition looks. Candidate operating locations remain
soft suitability/ranking preferences and are deliberately not used to suppress market
passes.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from collections import defaultdict


@dataclass(frozen=True)
class Market:
    code: str
    name: str
    country_code: str
    locale: str
    ddg_region: str
    query_label: str
    languages: tuple[str, ...] = ('English',)

    @property
    def flag(self) -> str:
        if not self.country_code:
            return '🌐'
        code=self.country_code.upper()
        if len(code)!=2 or not code.isalpha():
            return '🌐'
        return ''.join(chr(0x1F1E6+ord(ch)-ord('A')) for ch in code)


MARKETS = (
    Market('worldwide','Worldwide','','en-US','wt-wt','remote worldwide',('English',)),
    Market('us','United States','US','en-US','us-en','United States',('English',)),
    Market('ca','Canada','CA','en-CA','ca-en','Canada',('English','French')),
    Market('gb','United Kingdom','GB','en-GB','uk-en','United Kingdom',('English',)),
    Market('ie','Ireland','IE','en-IE','ie-en','Ireland',('English',)),
    Market('au','Australia','AU','en-AU','au-en','Australia',('English',)),
    Market('nz','New Zealand','NZ','en-NZ','nz-en','New Zealand',('English',)),
    Market('sg','Singapore','SG','en-SG','sg-en','Singapore',('English',)),
    Market('my','Malaysia','MY','en-MY','my-en','Malaysia',('English','Malay')),
    Market('hk','Hong Kong','HK','en-HK','hk-en','Hong Kong',('English','Chinese')),
    Market('in','India','IN','en-IN','in-en','India',('English',)),
    Market('ph','Philippines','PH','en-PH','ph-en','Philippines',('English',)),
    Market('ae','United Arab Emirates','AE','en-AE','ae-en','United Arab Emirates',('English','Arabic')),
    Market('za','South Africa','ZA','en-ZA','za-en','South Africa',('English',)),
    Market('mt','Malta','MT','en-MT','wt-wt','Malta',('English',)),
    Market('de','Germany','DE','de-DE','de-de','Germany',('German',)),
    Market('fr','France','FR','fr-FR','fr-fr','France',('French',)),
    Market('es','Spain','ES','es-ES','es-es','Spain',('Spanish',)),
    Market('pt','Portugal','PT','pt-PT','pt-pt','Portugal',('Portuguese',)),
    Market('nl','Netherlands','NL','nl-NL','nl-nl','Netherlands',('Dutch',)),
    Market('it','Italy','IT','it-IT','it-it','Italy',('Italian',)),
    Market('pl','Poland','PL','pl-PL','pl-pl','Poland',('Polish',)),
    Market('cz','Czech Republic','CZ','cs-CZ','cz-cs','Czech Republic',('Czech',)),
    Market('dk','Denmark','DK','da-DK','dk-da','Denmark',('Danish',)),
    Market('se','Sweden','SE','sv-SE','se-sv','Sweden',('Swedish',)),
    Market('no','Norway','NO','nb-NO','no-no','Norway',('Norwegian',)),
    Market('fi','Finland','FI','fi-FI','fi-fi','Finland',('Finnish',)),
    Market('jp','Japan','JP','ja-JP','jp-jp','Japan',('Japanese',)),
    Market('kr','South Korea','KR','ko-KR','kr-kr','South Korea',('Korean',)),
    Market('br','Brazil','BR','pt-BR','br-pt','Brazil',('Portuguese',)),
    Market('mx','Mexico','MX','es-MX','mx-es','Mexico',('Spanish',)),
)

# Country-wide fallback catalogue. The original curated markets above keep their city
# rotations, native-source presets and provider-specific locale details. Every remaining
# sovereign country is still a first-class Discovery Market so Global Coverage can make
# auditable acquisition attempts worldwide rather than treating "Worldwide" as a query
# suffix. These rows deliberately default to country-wide targeting; city/source depth can
# be added without another schema change.
_GLOBAL_COUNTRY_CODES = {
    'Afghanistan':'AF', 'Albania':'AL', 'Algeria':'DZ', 'Andorra':'AD',
    'Angola':'AO', 'Antigua and Barbuda':'AG', 'Argentina':'AR', 'Armenia':'AM',
    'Australia':'AU', 'Austria':'AT', 'Azerbaijan':'AZ', 'Bahamas':'BS',
    'Bahrain':'BH', 'Bangladesh':'BD', 'Barbados':'BB', 'Belarus':'BY',
    'Belgium':'BE', 'Belize':'BZ', 'Benin':'BJ', 'Bhutan':'BT',
    'Bolivia':'BO', 'Bosnia and Herzegovina':'BA', 'Botswana':'BW', 'Brazil':'BR',
    'Brunei':'BN', 'Bulgaria':'BG', 'Burkina Faso':'BF', 'Burundi':'BI',
    'Cambodia':'KH', 'Cameroon':'CM', 'Canada':'CA', 'Cape Verde':'CV',
    'Central African Republic':'CF', 'Chad':'TD', 'Chile':'CL', 'China':'CN',
    'Colombia':'CO', 'Comoros':'KM', 'Costa Rica':'CR', 'Croatia':'HR',
    'Cuba':'CU', 'Cyprus':'CY', 'Czechia':'CZ', 'Democratic Republic of the Congo':'CD',
    'Denmark':'DK', 'Djibouti':'DJ', 'Dominica':'DM', 'Dominican Republic':'DO',
    'Ecuador':'EC', 'Egypt':'EG', 'El Salvador':'SV', 'Equatorial Guinea':'GQ',
    'Eritrea':'ER', 'Estonia':'EE', 'Eswatini':'SZ', 'Ethiopia':'ET',
    'Fiji':'FJ', 'Finland':'FI', 'France':'FR', 'Gabon':'GA',
    'Gambia':'GM', 'Georgia':'GE', 'Germany':'DE', 'Ghana':'GH',
    'Greece':'GR', 'Grenada':'GD', 'Guatemala':'GT', 'Guinea':'GN',
    'Guinea-Bissau':'GW', 'Guyana':'GY', 'Haiti':'HT', 'Honduras':'HN',
    'Hungary':'HU', 'Iceland':'IS', 'India':'IN', 'Indonesia':'ID',
    'Iran':'IR', 'Iraq':'IQ', 'Ireland':'IE', 'Israel':'IL',
    'Italy':'IT', 'Ivory Coast':'CI', 'Jamaica':'JM', 'Japan':'JP',
    'Jordan':'JO', 'Kazakhstan':'KZ', 'Kenya':'KE', 'Kiribati':'KI',
    'Kuwait':'KW', 'Kyrgyzstan':'KG', 'Laos':'LA', 'Latvia':'LV',
    'Lebanon':'LB', 'Lesotho':'LS', 'Liberia':'LR', 'Libya':'LY',
    'Liechtenstein':'LI', 'Lithuania':'LT', 'Luxembourg':'LU', 'Madagascar':'MG',
    'Malawi':'MW', 'Malaysia':'MY', 'Maldives':'MV', 'Mali':'ML',
    'Malta':'MT', 'Marshall Islands':'MH', 'Mauritania':'MR', 'Mauritius':'MU',
    'Mexico':'MX', 'Micronesia':'FM', 'Moldova':'MD', 'Monaco':'MC',
    'Mongolia':'MN', 'Montenegro':'ME', 'Morocco':'MA', 'Mozambique':'MZ',
    'Myanmar':'MM', 'Namibia':'NA', 'Nauru':'NR', 'Nepal':'NP',
    'Netherlands':'NL', 'New Zealand':'NZ', 'Nicaragua':'NI', 'Niger':'NE',
    'Nigeria':'NG', 'North Korea':'KP', 'North Macedonia':'MK', 'Norway':'NO',
    'Oman':'OM', 'Pakistan':'PK', 'Palau':'PW', 'Palestine':'PS',
    'Panama':'PA', 'Papua New Guinea':'PG', 'Paraguay':'PY', 'Peru':'PE',
    'Philippines':'PH', 'Poland':'PL', 'Portugal':'PT', 'Qatar':'QA',
    'Republic of the Congo':'CG', 'Romania':'RO', 'Russia':'RU', 'Rwanda':'RW',
    'Saint Kitts and Nevis':'KN', 'Saint Lucia':'LC', 'Saint Vincent and the Grenadines':'VC', 'Samoa':'WS',
    'San Marino':'SM', 'Sao Tome and Principe':'ST', 'Saudi Arabia':'SA', 'Senegal':'SN',
    'Serbia':'RS', 'Seychelles':'SC', 'Sierra Leone':'SL', 'Singapore':'SG',
    'Slovakia':'SK', 'Slovenia':'SI', 'Solomon Islands':'SB', 'Somalia':'SO',
    'South Africa':'ZA', 'South Korea':'KR', 'South Sudan':'SS', 'Spain':'ES',
    'Sri Lanka':'LK', 'Sudan':'SD', 'Suriname':'SR', 'Sweden':'SE',
    'Switzerland':'CH', 'Syria':'SY', 'Taiwan':'TW', 'Tajikistan':'TJ',
    'Tanzania':'TZ', 'Thailand':'TH', 'Timor-Leste':'TL', 'Togo':'TG',
    'Tonga':'TO', 'Trinidad and Tobago':'TT', 'Tunisia':'TN', 'Turkey':'TR',
    'Turkmenistan':'TM', 'Tuvalu':'TV', 'Uganda':'UG', 'Ukraine':'UA',
    'United Arab Emirates':'AE', 'United Kingdom':'GB', 'United States':'US', 'Uruguay':'UY',
    'Uzbekistan':'UZ', 'Vanuatu':'VU', 'Vatican City':'VA', 'Venezuela':'VE',
    'Vietnam':'VN', 'Yemen':'YE', 'Zambia':'ZM', 'Zimbabwe':'ZW',
}

_GLOBAL_LANGUAGE_OVERRIDES = {
    'AR':('Spanish',), 'AT':('German',), 'BE':('Dutch','French','German'), 'BG':('Bulgarian',),
    'CH':('German','French','Italian'), 'CL':('Spanish',), 'CN':('Chinese',), 'CO':('Spanish',),
    'CR':('Spanish',), 'HR':('Croatian',), 'CY':('Greek','Turkish','English'), 'EE':('Estonian',),
    'EG':('Arabic',), 'GR':('Greek',), 'HU':('Hungarian',), 'ID':('Indonesian',), 'IL':('Hebrew',),
    'KZ':('Kazakh','Russian'), 'LK':('Sinhala','Tamil','English'), 'LT':('Lithuanian',),
    'LV':('Latvian',), 'MA':('Arabic','French'), 'PK':('English','Urdu'), 'RO':('Romanian',),
    'RU':('Russian',), 'SA':('Arabic',), 'SK':('Slovak',), 'SI':('Slovenian',), 'TH':('Thai',),
    'TR':('Turkish',), 'TW':('Chinese',), 'UA':('Ukrainian',), 'UY':('Spanish',), 'VN':('Vietnamese',),
    'DZ':('Arabic','French'), 'TN':('Arabic','French'), 'LB':('Arabic','French','English'),
    'RS':('Serbian',), 'BA':('Bosnian','Croatian','Serbian'),
    'GE':('Georgian',), 'AM':('Armenian',), 'AZ':('Azerbaijani',), 'UZ':('Uzbek','Russian'),
    'BD':('Bengali','English'), 'NP':('Nepali','English'), 'KH':('Khmer',), 'LA':('Lao',),
    'MM':('Burmese',), 'MN':('Mongolian',), 'IR':('Persian',), 'IQ':('Arabic',),
}

_GLOBAL_LOCALE_OVERRIDES = {
    'AR':'es-AR','AT':'de-AT','BE':'nl-BE','BG':'bg-BG','CH':'de-CH','CL':'es-CL','CN':'zh-CN',
    'CO':'es-CO','CR':'es-CR','HR':'hr-HR','CY':'el-CY','EE':'et-EE','EG':'ar-EG','GR':'el-GR',
    'HU':'hu-HU','ID':'id-ID','IL':'he-IL','KZ':'kk-KZ','LK':'en-LK','LT':'lt-LT','LV':'lv-LV',
    'MA':'ar-MA','PK':'en-PK','RO':'ro-RO','RU':'ru-RU','SA':'ar-SA','SK':'sk-SK','SI':'sl-SI',
    'TH':'th-TH','TR':'tr-TR','TW':'zh-TW','UA':'uk-UA','UY':'es-UY','VN':'vi-VN','DZ':'ar-DZ',
    'TN':'ar-TN','LB':'ar-LB','RS':'sr-RS','BA':'bs-BA','GE':'ka-GE','AM':'hy-AM','AZ':'az-AZ',
    'UZ':'uz-UZ','BD':'bn-BD','NP':'ne-NP','KH':'km-KH','LA':'lo-LA','MM':'my-MM','MN':'mn-MN',
    'IR':'fa-IR','IQ':'ar-IQ',
}

# Fill common official/search languages for the rest of the world catalogue. These are
# discovery defaults rather than claims about every resident's preferred language. They
# prevent newly added countries from silently behaving as English-only markets merely
# because they were not part of ScoutBox's original curated 31-market set.
_GLOBAL_LANGUAGE_FAMILIES = {
    'Spanish': {'BO','CU','DO','EC','SV','GT','HN','NI','PA','PY','PE','VE'},
    'Portuguese': {'AO','CV','GW','MZ','ST','TL'},
    'French': {'BJ','BF','BI','CM','CF','TD','KM','CD','CG','DJ','GA','GN','CI','MG','ML','MC','NE','SN','TG','HT'},
    'Arabic': {'BH','JO','KW','LY','OM','PS','QA','SD','SY','YE'},
    'Russian': {'BY','KG','TJ','TM'},
    'English': {'AG','BS','BB','BZ','BW','DM','FJ','GM','GH','GD','GY','JM','KE','KI','LS','LR','MW','MH','MU','FM','NA','NR','NG','PW','PG','KN','LC','VC','WS','SC','SL','SB','SS','SZ','TO','TT','TV','UG','VU','ZM','ZW'},
}
for _language,_codes in _GLOBAL_LANGUAGE_FAMILIES.items():
    for _country_code in _codes:
        _GLOBAL_LANGUAGE_OVERRIDES.setdefault(_country_code,(_language,))

# Locale defaults mirror the principal discovery language where Google/SearchAPI accepts
# a normal BCP-47 style interface locale. The country part stays market-specific.
_LANGUAGE_LOCALE_PREFIX = {
    'Spanish':'es','Portuguese':'pt','French':'fr','Arabic':'ar','Russian':'ru','English':'en',
}
for _country_code,_languages in list(_GLOBAL_LANGUAGE_OVERRIDES.items()):
    if _country_code in _GLOBAL_LOCALE_OVERRIDES or not _languages:
        continue
    _prefix=_LANGUAGE_LOCALE_PREFIX.get(_languages[0])
    if _prefix:
        _GLOBAL_LOCALE_OVERRIDES[_country_code]=f'{_prefix}-{_country_code}'

_existing_market_codes={m.code for m in MARKETS}
_extra_markets=[]
for _country_name,_country_code in _GLOBAL_COUNTRY_CODES.items():
    _code=_country_code.lower()
    if _code in _existing_market_codes:
        continue
    _extra_markets.append(Market(
        _code,_country_name,_country_code,
        _GLOBAL_LOCALE_OVERRIDES.get(_country_code,f'en-{_country_code}'),
        'wt-wt',_country_name,_GLOBAL_LANGUAGE_OVERRIDES.get(_country_code,('English',)),
    ))
MARKETS = MARKETS + tuple(_extra_markets)

MARKET_BY_CODE={m.code:m for m in MARKETS}
DEFAULT_MARKET_CODES=[m.code for m in MARKETS]
# Mature/high-volume markets retain a reserved lane inside Global Coverage so the one-time
# expansion from 31 to ~200 countries cannot starve established markets for an entire world
# sweep. This is a scheduling lane only; it does not change qualification or ranking.
CORE_MARKET_CODES=('us','ca','gb','ie','au','nz','sg','my','hk','in','ph','ae','za','mt','de','fr','es','pt','nl','it','pl','cz','dk','se','no','fi','jp','kr','br','mx')

# Country markets use a deterministic city rotation so discovery is locally specific
# without abandoning occasional country-wide searches. Small city-state markets remain
# naturally market-wide. The final item in each tuple is the country-wide fallback.
MARKET_QUERY_LOCATIONS = {
    'us': ('New York','San Francisco','Austin','Seattle','Boston','United States'),
    'ca': ('Toronto','Vancouver','Montreal','Calgary','Ottawa','Canada'),
    'gb': ('London','Manchester','Cambridge','Edinburgh','Bristol','United Kingdom'),
    'ie': ('Dublin','Cork','Galway','Limerick','Ireland'),
    'au': ('Melbourne','Sydney','Brisbane','Perth','Adelaide','Australia'),
    'nz': ('Auckland','Wellington','Christchurch','New Zealand'),
    'sg': ('Singapore',),
    'my': ('Kuala Lumpur','Penang','Johor Bahru','Malaysia'),
    'hk': ('Hong Kong',),
    'in': ('Bengaluru','Hyderabad','Pune','Chennai','Mumbai','Delhi','India'),
    'ph': ('Manila','Cebu','Davao','Philippines'),
    'ae': ('Dubai','Abu Dhabi','Sharjah','United Arab Emirates'),
    'za': ('Johannesburg','Cape Town','Durban','Pretoria','South Africa'),
    'mt': ('Malta',),
    'de': ('Berlin','Munich','Hamburg','Frankfurt','Cologne','Germany'),
    'fr': ('Paris','Lyon','Toulouse','Grenoble','Lille','France'),
    'es': ('Madrid','Barcelona','Valencia','Malaga','Bilbao','Spain'),
    'pt': ('Lisbon','Porto','Braga','Portugal'),
    'nl': ('Amsterdam','Eindhoven','Rotterdam','Utrecht','Netherlands'),
    'it': ('Milan','Rome','Turin','Bologna','Florence','Italy'),
    'pl': ('Warsaw','Krakow','Wroclaw','Gdansk','Poznan','Poland'),
    'cz': ('Prague','Brno','Ostrava','Czech Republic'),
    'dk': ('Copenhagen','Aarhus','Odense','Denmark'),
    'se': ('Stockholm','Gothenburg','Malmo','Sweden'),
    'no': ('Oslo','Bergen','Trondheim','Norway'),
    'fi': ('Helsinki','Espoo','Tampere','Turku','Oulu','Finland'),
    'jp': ('Tokyo','Osaka','Yokohama','Nagoya','Fukuoka','Japan'),
    'kr': ('Seoul','Busan','Incheon','Daejeon','South Korea'),
    'br': ('Sao Paulo','Rio de Janeiro','Belo Horizonte','Curitiba','Porto Alegre','Brazil'),
    'mx': ('Mexico City','Monterrey','Guadalajara','Queretaro','Mexico'),
}


# Optional extra languages for multilingual exploration. Market-native languages are
# always inferred from enabled Discovery Markets; these values supplement that set.
MULTILINGUAL_LANGUAGE_OPTIONS = (
    ('French','🇫🇷'),('German','🇩🇪'),('Spanish','🇪🇸'),('Portuguese','🇵🇹'),
    ('Italian','🇮🇹'),('Dutch','🇳🇱'),('Japanese','🇯🇵'),('Korean','🇰🇷'),
    ('Arabic','🇦🇪'),('Chinese','🇭🇰'),('Malay','🇲🇾'),('Polish','🇵🇱'),
    ('Czech','🇨🇿'),('Danish','🇩🇰'),('Swedish','🇸🇪'),('Norwegian','🇳🇴'),
    ('Finnish','🇫🇮'),('Greek','🇬🇷'),('Turkish','🇹🇷'),('Hebrew','🇮🇱'),
    ('Russian','🇷🇺'),('Ukrainian','🇺🇦'),('Indonesian','🇮🇩'),('Thai','🇹🇭'),
    ('Vietnamese','🇻🇳'),('Romanian','🇷🇴'),('Hungarian','🇭🇺'),('Bulgarian','🇧🇬'),
    ('Croatian','🇭🇷'),('Serbian','🇷🇸'),('Slovak','🇸🇰'),('Slovenian','🇸🇮'),
    ('Bengali','🇧🇩'),('Urdu','🇵🇰'),('Persian','🇮🇷'),('Estonian','🇪🇪'),
    ('Latvian','🇱🇻'),('Lithuanian','🇱🇹'),('Georgian','🇬🇪'),('Armenian','🇦🇲'),
)
DEFAULT_ADDITIONAL_LANGUAGES = ['French','German','Spanish']

# Query language is independent of provider locale and target market. Search Activity
# persists these stable language codes on each newly-issued provider request so filters
# never mistake Naver's ko-KR UI locale (or SearchAPI hl/gl) for the query language.
QUERY_LANGUAGE_CODE_BY_NAME = {
    'English':'en','French':'fr','German':'de','Spanish':'es','Portuguese':'pt',
    'Italian':'it','Dutch':'nl','Japanese':'ja','Korean':'ko','Arabic':'ar',
    'Chinese':'zh','Malay':'ms','Polish':'pl','Czech':'cs','Danish':'da',
    'Swedish':'sv','Norwegian':'no','Finnish':'fi','Greek':'el','Turkish':'tr',
    'Hebrew':'he','Russian':'ru','Ukrainian':'uk','Indonesian':'id','Thai':'th',
    'Vietnamese':'vi','Romanian':'ro','Hungarian':'hu','Bulgarian':'bg',
    'Croatian':'hr','Serbian':'sr','Slovak':'sk','Slovenian':'sl','Bengali':'bn',
    'Urdu':'ur','Persian':'fa','Estonian':'et','Latvian':'lv','Lithuanian':'lt',
    'Georgian':'ka','Armenian':'hy',
    # Market-native languages that are part of the global discovery catalogue must
    # also have stable ISO 639-1 codes. Without these mappings, the pre-0.11.151
    # fallback treated full language names (for example ``Azerbaijani`` or ``Khmer``)
    # as if they were codes, which leaked those names into Search Activity's code
    # column and made historical filtering inconsistent.
    'Kazakh':'kk','Sinhala':'si','Tamil':'ta','Bosnian':'bs','Azerbaijani':'az',
    'Uzbek':'uz','Nepali':'ne','Khmer':'km','Lao':'lo','Burmese':'my','Mongolian':'mn',
}
QUERY_LANGUAGE_NAME_BY_CODE = {code:name for name,code in QUERY_LANGUAGE_CODE_BY_NAME.items()}

def query_language_code(language):
    value=' '.join(str(language or '').split()).strip()
    if not value:
        return ''
    low=value.casefold()
    for name,code in QUERY_LANGUAGE_CODE_BY_NAME.items():
        if low in {name.casefold(),code.casefold()}:
            return code
    # Preserve an already-normalized short language code for forward compatibility,
    # but never mistake an arbitrary full language name for a code. Unknown names
    # are intentionally classified as Unknown until ScoutBox has an explicit mapping.
    return low if re.fullmatch(r'[a-zA-Z]{2,3}',value) else ''

def query_language_label(language_or_code):
    value=' '.join(str(language_or_code or '').split()).strip()
    code=query_language_code(value)
    return QUERY_LANGUAGE_NAME_BY_CODE.get(code,value.title() if value else '')

def query_language_metadata(language='English'):
    code=query_language_code(language) or 'en'
    return {'query_language':code,'query_language_label':QUERY_LANGUAGE_NAME_BY_CODE.get(code,query_language_label(language) or code)}


def query_language_identity(query_language='', query_language_label_value='', multilingual_language=''):
    """Normalize stored Search Activity language metadata without inventing legacy data.

    Returns ``(state, code, label)`` where state is ``known``, ``unknown`` or
    ``unrecorded``. Rows created before semantic query-language telemetry existed
    usually have all three values empty; they are *unrecorded*, not evidence that
    the language itself was unknown. ``unknown`` is reserved for an explicit stored
    language value that ScoutBox cannot normalize.
    """
    raw=' '.join(str(query_language or '').split()).strip()
    label=' '.join(str(query_language_label_value or '').split()).strip()
    historical=' '.join(str(multilingual_language or '').split()).strip()
    code=(query_language_code(raw) or query_language_code(label) or
          (query_language_code(historical) if historical else ''))
    if code:
        resolved_label=(label or QUERY_LANGUAGE_NAME_BY_CODE.get(code) or query_language_label(code) or code.upper())
        return 'known',code,resolved_label
    if raw or label or historical:
        return 'unknown','', 'Unknown'
    return 'unrecorded','',''

# Local-market sources are ordinary Search Sources. This metadata only decides when a
# dedicated domain receives a market-targeted pass; disabling the source always wins.
MARKET_SOURCE_DEFAULTS = {
    'au': [('SEEK Australia','https://www.seek.com.au')],
    'nz': [('SEEK New Zealand','https://www.seek.co.nz')],
    'sg': [('MyCareersFuture','https://www.mycareersfuture.gov.sg'),('JobStreet Singapore','https://sg.jobstreet.com')],
    'my': [('JobStreet Malaysia','https://my.jobstreet.com')],
    'hk': [('JobsDB Hong Kong','https://hk.jobsdb.com')],
    'ph': [('JobStreet Philippines','https://ph.jobstreet.com')],
    'gb': [('Reed UK','https://www.reed.co.uk')],
    'ie': [('IrishJobs','https://www.irishjobs.ie')],
    'ca': [('Job Bank Canada','https://www.jobbank.gc.ca')],
    'ae': [('GulfTalent','https://www.gulftalent.com')],
    'za': [('Careers24','https://www.careers24.com')],
    'de': [('StepStone Germany','https://www.stepstone.de')],
    'fr': [('France Travail','https://www.francetravail.fr')],
    'es': [('InfoJobs Spain','https://www.infojobs.net')],
    'pt': [('Net-Empregos Portugal','https://www.net-empregos.com')],
    'nl': [('Nationale Vacaturebank','https://www.nationalevacaturebank.nl')],
    'it': [('Cliclavoro Italy','https://www.cliclavoro.gov.it')],
    'pl': [('Pracuj.pl','https://www.pracuj.pl')],
    'cz': [('Jobs.cz','https://www.jobs.cz')],
    'dk': [('Jobindex Denmark','https://www.jobindex.dk')],
    'se': [('Arbetsförmedlingen Platsbanken','https://arbetsformedlingen.se/platsbanken')],
    'no': [('FINN Jobs','https://www.finn.no/job/search')],
    'fi': [('Jobly Finland','https://www.jobly.fi')],
    'jp': [('Daijob','https://www.daijob.com')],
    'kr': [('JobKorea','https://www.jobkorea.co.kr')],
    'br': [('Vagas.com.br','https://www.vagas.com.br')],
    'mx': [('OCCMundial','https://www.occ.com.mx')],
}


def enabled_markets(settings_obj):
    raw=list(getattr(settings_obj,'discovery_markets',None) or DEFAULT_MARKET_CODES)
    out=[]; seen=set()
    for code in raw:
        code=str(code or '').strip().lower()
        if code in MARKET_BY_CODE and code not in seen:
            seen.add(code); out.append(MARKET_BY_CODE[code])
    return out or list(MARKETS)


def _market_evidence(days=7):
    """Return bounded, auditable market outcomes from recent discovery telemetry."""
    evidence=defaultdict(lambda:{'attempts':0,'pages':0,'errors':0,'retained':0})
    try:
        from django.utils import timezone
        from portal.models import UsageMetric
        cutoff=timezone.now()-timezone.timedelta(days=max(1,min(30,int(days or 7))))
        rows=UsageMetric.objects.filter(category='discovery_market',at__gte=cutoff).order_by('-at')[:5000]
        for row in rows:
            meta=row.metadata if isinstance(row.metadata,dict) else {}
            code=str(meta.get('market_code') or '').strip().lower()
            if code not in MARKET_BY_CODE: continue
            bucket=evidence[code]
            bucket['attempts']+=int(row.requests or 0)
            bucket['pages']+=int(row.pages or 0)
            bucket['errors']+=int(row.errors or 0)
            if row.stage=='retained': bucket['retained']+=max(1,int(row.pages or 0))
    except Exception:
        return {}
    return dict(evidence)


def _evidence_score(row, *, adaptive=False):
    row=row if isinstance(row,dict) else {}
    attempts=max(0,int(row.get('attempts') or 0)); pages=max(0,int(row.get('pages') or 0))
    errors=max(0,int(row.get('errors') or 0)); retained=max(0,int(row.get('retained') or 0))
    if not attempts and not pages and not retained and not errors: return 0.0
    reliability=max(0.0,1.0-(errors/max(1,attempts)))
    page_yield=min(4.0,pages/max(1,attempts))
    retained_yield=min(1.0,retained/max(1,pages or attempts))
    if adaptive:
        return round((retained_yield*8.0)+(page_yield*0.7)+(reliability*1.5),6)
    return round((retained_yield*3.0)+(page_yield*0.45)+reliability,6)


def market_plan(settings_obj, *, campaign_id=0, rotation_offset=0, evidence=None):
    """Build a fair market order and report the strategy that actually took effect.

    Global Coverage prioritizes markets with the least recent acquisition work. Balanced
    and Adaptive retain evidence-weighted ordering, while missing evidence falls back
    explicitly instead of making several UI values aliases.
    """
    values=enabled_markets(settings_obj)
    requested=str(getattr(settings_obj,'discovery_market_strategy','balanced') or 'balanced').strip().lower()
    if requested not in {'global','even','balanced','adaptive'}: requested='global'
    evidence=_market_evidence() if evidence is None else (evidence or {})
    has_general=any(sum(max(0,int((row or {}).get(k) or 0)) for k in ('attempts','pages','errors','retained')) for row in evidence.values())
    has_retained=any(max(0,int((row or {}).get('retained') or 0)) for row in evidence.values())
    effective=requested
    fallback=''
    if effective=='adaptive' and not has_retained:
        effective='balanced'; fallback='Adaptive has no retained-result evidence; using Balanced.'
    if effective=='balanced' and not has_general:
        effective='even'; fallback=(fallback+' ' if fallback else '')+'Balanced has no recent market evidence; using Even.'
    if not values:
        return {'markets':[],'requested_strategy':requested,'effective_strategy':effective,'fallback':fallback,'evidence':{},'ordered_codes':[]}
    # A rotating anchor guarantees that every enabled market receives the first available
    # query/pass once per bounded cycle, even when evidence ranks other markets highly.
    base=sorted(values,key=lambda m:(m.name.casefold(),m.code))
    seed=int(hashlib.sha256(f'{campaign_id}'.encode()).hexdigest()[:8],16)
    shift=(seed+int(rotation_offset or 0))%len(base)
    even_order=base[shift:]+base[:shift]
    if effective=='global':
        # Global Coverage is acquisition-fair rather than yield-fair. Markets with the
        # fewest recent query attempts are moved to the front, with the rotating even
        # order as a deterministic tie-breaker. Retained-result yield never steals a
        # market's minimum acquisition turn.
        position={m.code:i for i,m in enumerate(even_order)}
        ordered=sorted(even_order,key=lambda m:(max(0,int((evidence.get(m.code) or {}).get('attempts') or 0)),position[m.code]))
    elif effective=='even':
        ordered=even_order
    else:
        anchor=even_order[0]
        position={m.code:i for i,m in enumerate(even_order)}
        adaptive=effective=='adaptive'
        ranked=sorted(even_order[1:],key=lambda m:(-_evidence_score(evidence.get(m.code),adaptive=adaptive),position[m.code]))
        if adaptive:
            tail=ranked
        else:
            # Balanced alternates a bounded evidence choice with the fair rotation order;
            # Adaptive is deliberately more aggressive and uses the full evidence ranking.
            tail=[]; remaining=list(ranked)
            while remaining:
                tail.append(remaining.pop(0))
                fair=next((m for m in even_order[1:] if m in remaining),None)
                if fair is not None:
                    remaining.remove(fair); tail.append(fair)
        ordered=[anchor]+tail
    snapshot={m.code:{
        'attempts':max(0,int((evidence.get(m.code) or {}).get('attempts') or 0)),
        'pages':max(0,int((evidence.get(m.code) or {}).get('pages') or 0)),
        'errors':max(0,int((evidence.get(m.code) or {}).get('errors') or 0)),
        'retained':max(0,int((evidence.get(m.code) or {}).get('retained') or 0)),
        'score':_evidence_score(evidence.get(m.code),adaptive=effective=='adaptive'),
    } for m in ordered}
    return {'markets':ordered,'requested_strategy':requested,'effective_strategy':effective,'fallback':fallback,'evidence':snapshot,'ordered_codes':[m.code for m in ordered]}


def market_rotation(settings_obj, *, campaign_id=0, rotation_offset=0):
    return market_plan(settings_obj,campaign_id=campaign_id,rotation_offset=rotation_offset)['markets']


def market_workload_schedule(plan, count, *, rotation_offset=0):
    """Allocate query slots according to the effective market strategy.

    Global Coverage gives every under-covered market a turn before any market repeats.
    Balanced/Adaptive retain the historical productive-market behavior for users who
    prefer yield over geographic coverage.
    """
    count=max(0,int(count or 0))
    markets=list((plan or {}).get('markets') or [])
    if not count or not markets:
        return []
    if str((plan or {}).get('effective_strategy') or '').lower()=='global':
        # Most slots advance the least-covered worldwide queue, while every third slot is
        # reserved for the mature/core market lane. This prevents the expanded ~200-country
        # catalogue from making UK/Australia/Singapore/Hong Kong wait through a full initial
        # world sweep, without returning to the old US/yield-dominated scheduler. Within a
        # single pass we avoid duplicates whenever enough distinct markets are enabled.
        # market_plan() already uses rotation_offset as the tie-breaker among markets
        # with equal coverage. Do not rotate the resulting list again here: doing so could
        # move heavily searched markets ahead of the least-covered markets and undo the
        # Global Coverage guarantee.
        worldwide=list(markets)
        core_by_code={m.code:m for m in markets if m.code in CORE_MARKET_CODES}
        core=[core_by_code[code] for code in CORE_MARKET_CODES if code in core_by_code]
        if core:
            core_shift=int(rotation_offset or 0)%len(core)
            core=core[core_shift:]+core[:core_shift]
        out=[]; used=set(); widx=0; cidx=0
        for idx in range(count):
            prefer_core=bool(core) and idx%3==2
            pools=(core,worldwide) if prefer_core else (worldwide,core)
            chosen=None
            for pool in pools:
                if not pool: continue
                start=cidx if pool is core else widx
                for step in range(len(pool)):
                    candidate=pool[(start+step)%len(pool)]
                    if candidate.code not in used or len(used)>=len(markets):
                        chosen=candidate
                        if pool is core: cidx=(start+step+1)%len(pool)
                        else: widx=(start+step+1)%len(pool)
                        break
                if chosen is not None: break
            if chosen is None:
                chosen=worldwide[idx%len(worldwide)]
            out.append(chosen); used.add(chosen.code)
        return out
    evidence=(plan or {}).get('evidence') or {}
    productive=[]; exploration=[]
    for market in markets:
        row=evidence.get(market.code) or {}
        attempts=max(0,int(row.get('attempts') or 0)); pages=max(0,int(row.get('pages') or 0)); retained=max(0,int(row.get('retained') or 0))
        # Treat Worldwide like every other market. It becomes productive only after
        # returning pages or retained records; the label alone must never cause wt-wt
        # searches to dominate a campaign configured for concrete locations.
        if pages>0 or retained>0:
            productive.append(market)
        else:
            exploration.append(market)
    if not productive:
        productive=[markets[0]]
        exploration=[m for m in markets if m.code!=markets[0].code]
    productive=sorted(productive,key=lambda m:(-_evidence_score(evidence.get(m.code),adaptive=True),m.name.casefold()))
    if exploration:
        shift=int(rotation_offset or 0)%len(exploration)
        exploration=exploration[shift:]+exploration[:shift]
    out=[]; pidx=0; eidx=0
    for idx in range(count):
        use_probe=bool(exploration) and idx%4==3
        if use_probe:
            out.append(exploration[eidx%len(exploration)]); eidx+=1
        else:
            out.append(productive[pidx%len(productive)]); pidx+=1
    return out


def multilingual_strength_cap(settings_obj, market_count=None):
    """Return a bounded multilingual workload sized to the enabled world footprint.

    The old 1/2/4 absolute cap meant 31 enabled markets could receive only two translated
    searches in Balanced mode. Scale the budget with the market set while keeping a hard
    ceiling so translation cannot dominate a campaign.
    """
    strength=str(getattr(settings_obj,'multilingual_exploration_strength','balanced') or 'balanced').strip().lower()
    try:
        count=max(1,int(market_count if market_count is not None else len(enabled_markets(settings_obj))))
    except Exception:
        count=1
    ratio={'low':0.10,'balanced':0.25,'high':0.50}.get(strength,0.25)
    floor={'low':2,'balanced':4,'high':8}.get(strength,4)
    import math
    return min(16,max(floor,int(math.ceil(count*ratio))))


def multilingual_assignments(settings_obj, markets, *, rotation_offset=0):
    """Pair native languages with markets and rotate those pairs across campaigns.

    A single global language queue made every Spanish-speaking country compete for one
    "Spanish" assignment and every French-speaking country compete for one "French"
    assignment. Keep market+language pairs distinct so repeated global sweeps eventually
    issue native-language work in each country rather than only in the first country that
    declares that language.
    """
    unique_markets=[]; seen_markets=set()
    for market in markets or enabled_markets(settings_obj):
        if market.code not in seen_markets:
            seen_markets.add(market.code); unique_markets.append(market)
    if not unique_markets: return []

    native=[]; seen_native=set()
    for market in unique_markets:
        if market.code=='worldwide':
            continue
        for raw in market.languages:
            language=' '.join(str(raw or '').split())
            key=(market.code,language.casefold())
            if language and language.casefold()!='english' and key not in seen_native:
                seen_native.add(key); native.append({'language':language,'market':market,'source':'market'})

    explicit=[]; seen_explicit=set()
    worldwide=next((m for m in unique_markets if m.code=='worldwide'),None)
    for raw in (getattr(settings_obj,'multilingual_languages',[]) or []):
        language=' '.join(str(raw or '').split())
        key=language.casefold()
        if not language or key=='english' or key in seen_explicit:
            continue
        seen_explicit.add(key)
        # Prefer a native market for an explicit language; Worldwide is acceptable for
        # user-requested extra-language exploration when no enabled market declares it.
        market=next((m for m in unique_markets if key in {x.casefold() for x in m.languages}),None) or worldwide or unique_markets[0]
        explicit.append({'language':language,'market':market,'source':'additional'})

    def rotate(values,offset):
        if not values: return []
        shift=int(offset or 0)%len(values)
        return values[shift:]+values[:shift]

    # Rotate native market-language pairs independently of the small additional-language
    # list. The campaign rotation offset therefore advances Spanish/French/etc. across
    # countries instead of repeatedly selecting the same first market.
    native=rotate(native,rotation_offset)
    explicit=rotate(explicit,rotation_offset)
    cap=multilingual_strength_cap(settings_obj,len(unique_markets))
    assignments=[]
    while (native or explicit) and len(assignments)<cap:
        for queue in (native,explicit):
            if queue and len(assignments)<cap:
                row=queue.pop(0)
                assignments.append({
                    'id':f"{row['source']}:{row['language'].casefold()}:{row['market'].code}",
                    **row,
                })
    return assignments


def market_query_location(market: Market, rotation_offset=0):
    choices=MARKET_QUERY_LOCATIONS.get(market.code) or (market.query_label,)
    return choices[int(rotation_offset or 0) % len(choices)]


def market_query(query, market: Market, rotation_offset=0):
    q=' '.join(str(query or '').split())
    if not q: return q
    if market.code=='worldwide':
        if 'remote' not in q.casefold(): q += ' remote'
        return q
    choices=MARKET_QUERY_LOCATIONS.get(market.code) or (market.query_label,)
    folded=q.casefold()
    country_labels={str(market.name or '').casefold(),str(market.query_label or '').casefold()}
    city_choices=[str(label) for label in choices if str(label).casefold() not in country_labels]
    # Respect an explicit city already supplied by the planner/user. A bare country label is
    # different: for a city rotation replace it with the selected metro instead of leaving the
    # search country-only. Provider locale/country settings continue to constrain the market.
    if any(city.casefold() in folded for city in city_choices):
        return q
    location=market_query_location(market,rotation_offset)
    if not location:
        return q
    if location.casefold() in country_labels:
        if any(label and label in folded for label in country_labels):
            return q
        return q+f' {location}'
    for country in (market.query_label,market.name):
        country=str(country or '').strip()
        if country and country.casefold() in q.casefold():
            return re.sub(re.escape(country),location,q,count=1,flags=re.IGNORECASE)
    return q+f' in {location}'


def market_search_meta(market: Market|None):
    if not market:
        return {'market':'','country_code':'','locale':'en-US','ddg_region':'wt-wt'}
    return {'market':market.name,'market_code':market.code,'country_code':market.country_code,
            'locale':market.locale,'ddg_region':market.ddg_region}


def market_from_location(value):
    """Resolve a campaign location to a configured discovery market when unambiguous."""
    text=' '.join(str(value or '').strip().casefold().replace('_',' ').replace('-',' ').split())
    if not text:
        return None
    if text in {'worldwide','worldwide remote','remote worldwide','global','global remote','remote'}:
        return MARKET_BY_CODE.get('worldwide')
    for market in MARKETS:
        aliases={
            ' '.join(str(market.code or '').casefold().replace('-',' ').split()),
            ' '.join(str(market.name or '').casefold().replace('-',' ').split()),
            ' '.join(str(market.query_label or '').casefold().replace('-',' ').split()),
            str(market.country_code or '').casefold(),
        }
        aliases.discard('')
        if text in aliases:
            return market
    return None


def auto_multilingual_languages(settings_obj):
    """Return market-native languages plus user-selected additional languages.

    English remains the primary discovery language. Non-English languages associated
    with enabled markets are always inferred; ``multilingual_languages`` supplements
    that set. Exploration strength keeps the resulting work bounded.
    """
    out=[]; seen=set()
    def add(language):
        value=' '.join(str(language or '').split())
        key=value.casefold()
        if not value or key=='english' or key in seen:
            return
        seen.add(key); out.append(value)
    for market in enabled_markets(settings_obj):
        for language in market.languages:
            add(language)
    for language in (getattr(settings_obj,'multilingual_languages',[]) or []):
        add(language)
    return out[:20]

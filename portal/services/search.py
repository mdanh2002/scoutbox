import base64
import os
import random
import re
import time
import threading
import urllib.parse
from datetime import timedelta, datetime
from html import unescape
import requests
try:
    from curl_cffi import requests as curl_requests
except Exception:  # pragma: no cover - ordinary requests remains a compatibility fallback
    curl_requests=None
from bs4 import BeautifulSoup
from django.utils import timezone
from django.conf import settings
from django.db.models import Count
from portal.models import SearchSource, SearchProviderStat, PortalSettings, UsageMetric, FacebookConfig, FacebookPage, CustomSearchDomain, Opportunity, CompanyLead, AIRequestLog, AIProviderConfig
from .discovery_markets import market_search_meta, market_query_location, enabled_markets, MARKET_BY_CODE, query_language_metadata
from .crypto import decrypt
from .queryplanner import build_query_plan, build_source_guided_query_plan
from .cloud_budget import metadata as usage_metadata

UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36 ScoutBox/0.11.152'
GOOGLE_PUBLIC_UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
GOOGLE_PUBLIC_MOBILE_UA='Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36'
_GOOGLE_PUBLIC_LOCK=threading.Lock()
_GOOGLE_PUBLIC_LAST_REQUEST=0.0
_GOOGLE_PUBLIC_CACHE={}
_GOOGLE_PUBLIC_MIN_INTERVAL=2.25
_GOOGLE_PUBLIC_CACHE_SECONDS=600
SEARCHAPI_SERVICE_SOURCES={
    'jobs':'SearchAPI · Google Jobs',
    'web':'SearchAPI · Google Web',
    'forums':'SearchAPI · Google Forums',
    'news':'SearchAPI · Google News',
    'chatgpt':'SearchAPI · ChatGPT Research',
    'ai_mode':'SearchAPI · Google AI Mode',
    'local':'SearchAPI · Google Local',
}
SEARCHAPI_SERVICE_LABELS={'jobs':'Google Jobs','web':'Google Web','forums':'Google Forums','news':'Google News','chatgpt':'ChatGPT Research','ai_mode':'Google AI Mode Research','local':'Google Local / Employer Discovery'}
SEARCHAPI_SHORT_LABELS={'jobs':'Jobs','web':'Web','forums':'Forums','news':'News','chatgpt':'ChatGPT','ai_mode':'AI Mode','local':'Local'}
SEARCHAPI_DEFAULT_AUTO={'jobs':True,'web':True,'forums':True,'news':True,'chatgpt':False,'ai_mode':False,'local':False}
SEARCHAPI_SOURCE_TO_SERVICE={v:k for k,v in SEARCHAPI_SERVICE_SOURCES.items()}
ALL_SEARCH_ENGINE_NAMES={'Google','Bing','DuckDuckGo','Brave Search','Yahoo Search','Startpage','Ecosia','Mojeek','Yandex','Baidu','Naver',*SEARCHAPI_SERVICE_SOURCES.values()}
ACTIVE_PROVIDER_NAMES={'Google','Bing','DuckDuckGo','Brave Search','Yahoo Search','Mojeek','Startpage','Ecosia','Yandex','Baidu','Naver',*SEARCHAPI_SERVICE_SOURCES.values()}
PROVIDER_NAMES=ALL_SEARCH_ENGINE_NAMES


def searchapi_service_code(source_or_name):
    name=source_or_name.name if hasattr(source_or_name,'name') else str(source_or_name or '')
    return SEARCHAPI_SOURCE_TO_SERVICE.get(name,'')


def searchapi_source(service):
    return SearchSource.objects.filter(name=SEARCHAPI_SERVICE_SOURCES.get(str(service or '').strip(),'')).first()


def searchapi_service_auto_enabled(source_or_service):
    service=searchapi_service_code(source_or_service) if hasattr(source_or_service,'name') else str(source_or_service or '').strip()
    source=source_or_service if hasattr(source_or_service,'name') else searchapi_source(service)
    if not source:
        return False
    cfg=dict(getattr(source,'config_json',{}) or {})
    if 'auto_enabled' in cfg:
        return bool(cfg.get('auto_enabled')) and bool(getattr(source,'enabled',False))
    return bool(SEARCHAPI_DEFAULT_AUTO.get(service,False) and getattr(source,'enabled',False))


def searchapi_master_source():
    return searchapi_source('jobs') or SearchSource.objects.filter(name__startswith='SearchAPI ·').order_by('pk').first()


def _provider_pacing_seconds(source):
    """Small provider-local gap so parallel campaign workers do not stampede one engine."""
    try:
        if provider_budget_kind(source) == 'api':
            default = 1.0
        else:
            default = float(os.environ.get('SCOUTBOX_PUBLIC_PROVIDER_MIN_INTERVAL_SECONDS', '6') or 6)
        value = float((getattr(source, 'config_json', {}) or {}).get('min_interval_seconds') or default)
    except Exception:
        value = 6.0
    return max(0.0, min(60.0, value))


def _search_lock_client():
    try:
        import redis
        return redis.Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=1.5, socket_timeout=1.5)
    except Exception:
        return None


def _wait_for_provider_pacing(source):
    """Process-safe provider pacing; fail-open if Redis is unavailable.

    This keeps automatic discovery concurrency at the campaign level while avoiding
    simultaneous public-search hits to the same provider. It is not a budget gate: it is
    a short spacing mechanism to reduce 403/429 cascades when two campaign workers run.
    """
    gap = _provider_pacing_seconds(source)
    if gap <= 0:
        return 0.0
    client = _search_lock_client()
    if client is None:
        return 0.0
    safe = re.sub(r'[^a-z0-9]+', '-', str(getattr(source, 'name', 'provider') or 'provider').lower()).strip('-') or 'provider'
    key = f'scoutbox:search-provider:last:{safe}'
    deadline = time.monotonic() + min(45.0, max(2.0, gap * 3.0))
    waited = 0.0
    while True:
        now = time.time()
        try:
            raw = client.get(key)
            last = float(raw.decode('utf-8') if isinstance(raw, bytes) else raw or 0)
        except Exception:
            return waited
        remaining = (last + gap) - now
        if remaining <= 0:
            try:
                client.set(key, str(now), ex=max(30, int(gap * 8)))
            except Exception:
                pass
            return waited
        if time.monotonic() + remaining > deadline:
            return waited
        sleep_for = min(max(0.25, remaining), 2.0)
        time.sleep(sleep_for)
        waited += sleep_for

def _setting_attr(obj, name, default=None):
    """Read a PortalSettings value from either a model instance or a dict snapshot."""
    try:
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)
    except Exception:
        return default


def _setting_int(obj, name, default, minimum=None, maximum=None):
    try:
        value = int(_setting_attr(obj, name, default) or default)
    except Exception:
        value = int(default)
    if minimum is not None:
        value = max(int(minimum), value)
    if maximum is not None:
        value = min(int(maximum), value)
    return value

_NAVER_UI_PHRASES=('새 창 열림','Keep에 저장','Keep에 바로가기')
_ROLE_TITLE_HINT=re.compile(r'(?i)\b(engineer|developer|consultant|architect|writer|technical|firmware|software|linux|embedded|systems?|principal|specialist|manager|director|lead|scientist|researcher|designer|devops|security|platform|kernel|administrator|analyst|programmer)\b')


def search_title_contaminated(value, provider=''):
    """Return True when a search-engine result title is mostly SERP chrome/breadcrumbs."""
    text=' '.join(str(value or '').split())
    if not text:
        return False
    low=text.casefold()
    if str(provider or '').casefold()=='naver' and any(x.casefold() in low for x in _NAVER_UI_PHRASES):
        return True
    if ' › ' in text and re.search(r'(?i)(?:https?://)?(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}(?:\s|›)',text):
        return True
    return False


def _clean_naver_result_title(anchor_text, container_text=''):
    """Extract the human result title from Naver public-search result chrome."""
    def clean(text):
        text=' '.join(str(text or '').replace('\xa0',' ').split())
        for phrase in _NAVER_UI_PHRASES:
            text=text.replace(phrase,' ')
        return ' '.join(text.split()).strip(' -–—|·:;')

    anchor=clean(anchor_text)
    if anchor and not search_title_contaminated(anchor,'Naver') and ' › ' not in anchor:
        return anchor[:300]

    raw=str(container_text or anchor_text or '')
    # Accessibility labels and Keep controls are excellent structural separators in
    # Naver's public page. Prefer a role-looking segment after those separators.
    segments=[]
    for part in re.split(r'(?:새 창 열림|Keep에 저장|Keep에 바로가기)',raw,flags=re.I):
        part=clean(part)
        if not part or len(part)<3 or len(part)>300:
            continue
        if ' › ' in part or re.search(r'(?i)^(?:www\.)?[a-z0-9.-]+\.[a-z]{2,}(?:\s|/|$)',part):
            continue
        segments.append(part)
    role_segments=[x for x in segments if _ROLE_TITLE_HINT.search(x) and not (x[:1] in {'•','·','▪'} or (len(x)>115 and (x.endswith('.') or x.count(',')>=2)))]
    if role_segments:
        # The actual result heading normally precedes the snippet and is therefore the
        # shortest early role-looking segment, rather than a long sentence of JD prose.
        return sorted(role_segments,key=lambda x:(len(x)>180,len(x)))[0][:300]
    if segments:
        return segments[0][:300]
    return anchor[:300]



PUBLIC_URL_TEMPLATES={
    'Google':'https://www.google.com/search?q={query}&num={limit}&hl=en&gl=us',
    'Bing':'https://www.bing.com/search?q={query}&count={limit}&setlang=en-US&cc=US',
    'DuckDuckGo':'https://html.duckduckgo.com/html/?q={query}&kl=us-en',
    'Brave Search':'https://search.brave.com/search?q={query}&source=web',
    'Yahoo Search':'https://search.yahoo.com/search?p={query}&vl=lang_en',
    'Mojeek':'https://www.mojeek.com/search?q={query}',
    'Startpage':'https://www.startpage.com/sp/search?query={query}&language=english',
    'Ecosia':'https://www.ecosia.org/search?q={query}&locale=en',
    'Yandex':'https://yandex.com/search/?text={query}&lang=en',
    'Baidu':'https://www.baidu.com/s?wd={query}',
    'Naver':'https://search.naver.com/search.naver?where=webkr&query={query}',
}

def public_query_template(source_or_name):
    name=source_or_name.name if hasattr(source_or_name,'name') else str(source_or_name)
    source=source_or_name if hasattr(source_or_name,'config_json') else SearchSource.objects.filter(name=name).first()
    custom=str(((getattr(source,'config_json',{}) or {}).get('public_query_template') or '')).strip() if source else ''
    return custom or PUBLIC_URL_TEMPLATES.get(name,'')

def public_query_url(source_or_name, query, limit=10, market=None):
    template=public_query_template(source_or_name)
    if not template: return ''
    if '{query}' not in template:
        raise ValueError('Public query template must contain {query}.')
    url=template.replace('{query}',urllib.parse.quote_plus(query)).replace('{limit}',str(int(limit)))
    meta=market_search_meta(market)
    name=source_or_name.name if hasattr(source_or_name,'name') else str(source_or_name)
    # Apply per-market locale to built-in provider templates. Operator-custom templates
    # remain authoritative except for replacing the old built-in US defaults.
    try:
        parts=urllib.parse.urlsplit(url); params=urllib.parse.parse_qs(parts.query,keep_blank_values=True)
        if name=='Google':
            params['hl']=[meta.get('locale') or 'en-US'];
            if meta.get('country_code'): params['gl']=[meta['country_code'].lower()]
            else: params.pop('gl',None)
        elif name=='Bing':
            params['setlang']=[meta.get('locale') or 'en-US']
            if meta.get('country_code'): params['cc']=[meta['country_code']]
            else: params.pop('cc',None)
        elif name=='DuckDuckGo': params['kl']=[meta.get('ddg_region') or 'wt-wt']
        elif name in ('Yahoo Search','Startpage','Ecosia','Yandex','Mojeek'):
            # Providers differ in locale controls; keep their stable public endpoint and
            # rely on the market-qualified query when no exact locale flag is available.
            pass
        query_string=urllib.parse.urlencode([(k,v) for k,vals in params.items() for v in vals])
        url=urllib.parse.urlunsplit((parts.scheme,parts.netloc,parts.path,query_string,parts.fragment))
    except Exception:
        pass
    if not url.startswith(('http://','https://')):
        raise ValueError('Public query template must be a complete http:// or https:// URL.')
    return url

def public_raw_preview(source, query, limit=5):
    """Capture the provider's public response even when it is an HTTP error page.

    Diagnostics need the actual 403/429/CAPTCHA/interstitial body; the normal search
    adapter deliberately raises on those statuses and therefore cannot be used here.
    """
    if not provider_capability(source).get('public_fallback'):
        return {'raw_html':'','request_url':'','http_status':None,'warning':'No public-search page is available for this provider.'}
    url=''
    try:
        url=public_query_url(source,query,limit)
        headers={'User-Agent':UA,'Accept-Language':'en-US,en;q=0.8'}
        r=requests.get(url,headers=headers,timeout=15,allow_redirects=True)
        warning='' if r.ok else f'HTTP {r.status_code} returned by provider; raw response captured for diagnostics.'
        return {'raw_html':(r.text or '')[:50000],'request_url':r.url or url,'http_status':r.status_code,'warning':warning}
    except Exception as exc:
        return {'raw_html':'','request_url':url,'http_status':None,'warning':str(exc)}

PROVIDER_CAPABILITIES={
    'Google': {
        'api_name':'Google Programmable Search JSON API', 'env_key':'GOOGLE_SEARCH_API_KEY',
        'extra_key':'cx', 'extra_label':'Programmable Search Engine ID (cx)', 'env_extra':'GOOGLE_SEARCH_CX',
        'public_fallback':True,
    },
    'Brave Search': {
        'api_name':'Brave Search API', 'env_key':'BRAVE_SEARCH_API_KEY',
        'extra_key':'', 'extra_label':'', 'env_extra':'', 'public_fallback':True,
    },
    # Bing Search APIs were retired in 2025; ScoutBox deliberately uses the public result page.
    'Bing': {'api_name':'', 'env_key':'', 'extra_key':'', 'extra_label':'', 'env_extra':'', 'public_fallback':True},
    'DuckDuckGo': {'api_name':'', 'env_key':'', 'extra_key':'', 'extra_label':'', 'env_extra':'', 'public_fallback':True},
    'Yahoo Search': {'api_name':'', 'env_key':'', 'extra_key':'', 'extra_label':'', 'env_extra':'', 'public_fallback':True},
    'Mojeek': {'api_name':'Mojeek Web Search API', 'env_key':'MOJEEK_SEARCH_API_KEY', 'extra_key':'', 'extra_label':'', 'env_extra':'', 'public_fallback':True},
    'Startpage': {'api_name':'', 'env_key':'', 'extra_key':'', 'extra_label':'', 'env_extra':'', 'public_fallback':True},
    'Ecosia': {'api_name':'', 'env_key':'', 'extra_key':'', 'extra_label':'', 'env_extra':'', 'public_fallback':True},
    'Yandex': {
        'api_name':'Yandex Search API', 'env_key':'YANDEX_SEARCH_API_KEY',
        'extra_key':'folder_id', 'extra_label':'Yandex Cloud folder ID', 'env_extra':'YANDEX_SEARCH_FOLDER_ID', 'public_fallback':True,
        'access_options':[
            {'value':'public','label':'Public Access','api_name':'','secret_label':'','extra_label':''},
            {'value':'yandex_api_key','label':'Yandex Search API — API key','api_name':'Yandex Search API','secret_label':'API key','extra_label':'Yandex Cloud folder ID'},
            {'value':'yandex_iam','label':'Yandex Cloud / AI Studio — IAM token','api_name':'Yandex Search API','secret_label':'IAM token','extra_label':'Yandex Cloud folder ID'},
        ],
    },
    'Baidu': {
        'api_name':'Baidu Qianfan Web Search API', 'env_key':'BAIDU_SEARCH_API_KEY',
        'extra_key':'', 'extra_label':'', 'env_extra':'', 'public_fallback':True,
        'access_options':[
            {'value':'public','label':'Public Access','api_name':'','secret_label':'','extra_label':''},
            {'value':'baidu_qianfan','label':'Baidu Qianfan Web Search API','api_name':'Baidu Qianfan Web Search API','secret_label':'API key','extra_label':''},
        ],
    },
    'SearchAPI · Google Jobs': {
        'api_name':'SearchAPI Google Jobs API', 'env_key':'SEARCHAPI_API_KEY',
        'extra_key':'', 'extra_label':'', 'env_extra':'', 'public_fallback':False,
        'secret_label':'SearchAPI API key', 'shared_credential_group':'searchapi', 'shared_budget_group':'searchapi',
    },
    'SearchAPI · Google Web': {
        'api_name':'SearchAPI Google Search API', 'env_key':'SEARCHAPI_API_KEY',
        'extra_key':'', 'extra_label':'', 'env_extra':'', 'public_fallback':False,
        'secret_label':'SearchAPI API key', 'shared_credential_group':'searchapi', 'shared_budget_group':'searchapi',
    },
    'SearchAPI · Google Forums': {
        'api_name':'SearchAPI Google Forums API', 'env_key':'SEARCHAPI_API_KEY',
        'extra_key':'', 'extra_label':'', 'env_extra':'', 'public_fallback':False,
        'secret_label':'SearchAPI API key', 'shared_credential_group':'searchapi', 'shared_budget_group':'searchapi',
    },
    'SearchAPI · Google News': {
        'api_name':'SearchAPI Google News API', 'env_key':'SEARCHAPI_API_KEY',
        'extra_key':'', 'extra_label':'', 'env_extra':'', 'public_fallback':False,
        'secret_label':'SearchAPI API key', 'shared_credential_group':'searchapi', 'shared_budget_group':'searchapi',
    },
    'SearchAPI · ChatGPT Research': {
        'api_name':'SearchAPI ChatGPT API', 'env_key':'SEARCHAPI_API_KEY',
        'extra_key':'', 'extra_label':'', 'env_extra':'', 'public_fallback':False,
        'secret_label':'SearchAPI API key', 'shared_credential_group':'searchapi', 'shared_budget_group':'searchapi',
    },
    'SearchAPI · Google AI Mode': {
        'api_name':'SearchAPI Google AI Mode API', 'env_key':'SEARCHAPI_API_KEY',
        'extra_key':'', 'extra_label':'', 'env_extra':'', 'public_fallback':False,
        'secret_label':'SearchAPI API key', 'shared_credential_group':'searchapi', 'shared_budget_group':'searchapi',
    },
    'SearchAPI · Google Local': {
        'api_name':'SearchAPI Google Local API', 'env_key':'SEARCHAPI_API_KEY',
        'extra_key':'', 'extra_label':'', 'env_extra':'', 'public_fallback':False,
        'secret_label':'SearchAPI API key', 'shared_credential_group':'searchapi', 'shared_budget_group':'searchapi',
    },
    'Naver': {
        'api_name':'Naver Search API', 'env_key':'NAVER_SEARCH_CLIENT_SECRET',
        'extra_key':'client_id', 'extra_label':'Naver Client ID', 'env_extra':'NAVER_SEARCH_CLIENT_ID', 'public_fallback':True,
        'access_options':[
            {'value':'public','label':'Public Access','api_name':'','secret_label':'','extra_label':''},
            {'value':'naver_legacy','label':'NAVER Developers Center (legacy)','api_name':'Naver Search API (legacy)','secret_label':'Client Secret','extra_label':'Client ID'},
            {'value':'naver_hub','label':'NAVER API HUB','api_name':'NAVER API HUB Search','secret_label':'Client Secret','extra_label':'Client ID'},
        ],
    },
}


def provider_capability(source_or_name):
    name=source_or_name.name if hasattr(source_or_name,'name') else str(source_or_name)
    return PROVIDER_CAPABILITIES.get(name,{'api_name':'','env_key':'','extra_key':'','extra_label':'','env_extra':'','public_fallback':False})


def _access_option(cap, value):
    options=cap.get('access_options') or []
    return next((x for x in options if x.get('value')==value),None)


def provider_access_type(source, cap=None):
    cap=cap or provider_capability(source)
    options=cap.get('access_options') or []
    if not options:
        return ''
    cfg=getattr(source,'config_json',{}) or {}
    selected=str(cfg.get('access_type') or '').strip()
    if _access_option(cap,selected):
        return selected
    # Access Type is explicit in v0.8.21.  Missing/legacy configuration defaults to
    # Public Access for every multi-access provider; saved credentials remain available
    # in their slots until the user selects that API mode.
    return 'public'


def _access_credentials(source, access_type, cap=None):
    cap=cap or provider_capability(source)
    cfg=getattr(source,'config_json',{}) or {}
    slots=cfg.get('access_credentials') or {}
    slot=slots.get(access_type) or {}
    secret=''
    if slot.get('secret_enc'):
        try: secret=decrypt(slot.get('secret_enc')).strip()
        except Exception: secret=''
    extra=str(slot.get('extra') or slot.get('folder_id') or '').strip()

    # Legacy/env compatibility.  Existing Naver credentials continue to work without
    # forcing the user to re-enter them after upgrade.
    if access_type=='naver_legacy':
        if not secret and getattr(source,'api_key_enc',''):
            try: secret=decrypt(source.api_key_enc).strip()
            except Exception: secret=''
        if not extra: extra=str(cfg.get('api_extra') or '').strip()
        secret=secret or (os.getenv('NAVER_SEARCH_CLIENT_SECRET','') or '').strip()
        extra=extra or (os.getenv('NAVER_SEARCH_CLIENT_ID','') or '').strip()
    elif access_type=='naver_hub':
        secret=secret or (os.getenv('NAVER_API_HUB_CLIENT_SECRET','') or '').strip()
        extra=extra or (os.getenv('NAVER_API_HUB_CLIENT_ID','') or '').strip()
    elif access_type=='yandex_api_key':
        secret=secret or (os.getenv('YANDEX_SEARCH_API_KEY','') or '').strip()
        extra=extra or (os.getenv('YANDEX_SEARCH_FOLDER_ID','') or '').strip()
    elif access_type=='yandex_iam':
        secret=secret or (os.getenv('YANDEX_SEARCH_IAM_TOKEN','') or '').strip()
        extra=extra or (os.getenv('YANDEX_SEARCH_FOLDER_ID','') or '').strip()
    elif access_type=='baidu_qianfan':
        secret=secret or (os.getenv('BAIDU_SEARCH_API_KEY','') or '').strip()
    return secret,extra


def _provider_secret(source, cap=None):
    cap=cap or provider_capability(source)
    env=(os.getenv(cap.get('env_key',''),'') or '').strip() if cap.get('env_key') else ''
    # SearchAPI is one account in ScoutBox. 0.11.135 unified the UI, but older child
    # rows can still contain legacy per-service secrets. Those stale secrets must never
    # override the key saved on the unified Google Jobs hub (the exact failure that can
    # make Jobs tests pass while Forums reports "Invalid API key").
    if cap.get('shared_credential_group')=='searchapi':
        try:
            hub=searchapi_master_source()
            if hub is not None and getattr(hub,'api_key_enc',''):
                try:
                    master=decrypt(hub.api_key_enc).strip()
                except Exception:
                    master=''
                if master:
                    return master
        except Exception:
            pass
        if env:
            return env
        # Compatibility fallback for installations upgrading from the pre-unified
        # SearchAPI layout. Migration 0210 promotes one legacy secret to the hub and
        # clears child copies, so this path should disappear after migrations run.
        try:
            candidates=[]
            if getattr(source,'api_key_enc',''):
                candidates.append(source)
            candidates.extend(SearchSource.objects.filter(name__startswith='SearchAPI ·').exclude(pk=getattr(source,'pk',None)))
            for sibling in candidates:
                if getattr(sibling,'api_key_enc',''):
                    try:
                        legacy=decrypt(sibling.api_key_enc).strip()
                    except Exception:
                        legacy=''
                    if legacy:
                        return legacy
        except Exception:
            pass
        return ''
    stored=''
    if getattr(source,'api_key_enc',''):
        try: stored=decrypt(source.api_key_enc).strip()
        except Exception: stored=''
    return stored or env

def _provider_extra(source, cap=None):
    cap=cap or provider_capability(source)
    cfg=getattr(source,'config_json',{}) or {}
    stored=str(cfg.get('api_extra') or '').strip()
    env=(os.getenv(cap.get('env_extra',''),'') or '').strip() if cap.get('env_extra') else ''
    return stored or env

def provider_credential_state(source):
    cap=provider_capability(source)
    options=cap.get('access_options') or []
    if options:
        access_type=provider_access_type(source,cap)
        option=_access_option(cap,access_type) or options[0]
        secret,extra=_access_credentials(source,access_type,cap)
        needs_extra=bool(option.get('extra_label'))
        api_configured=bool(option.get('api_name') and secret and (extra if needs_extra else True))
        cfg=getattr(source,'config_json',{}) or {}; slot=(cfg.get('access_credentials') or {}).get(access_type) or {}
        return {
            **cap,
            'access_type':access_type,'access_type_label':option.get('label') or 'Public Access','access_options':options,
            'api_access_options':[x for x in options if x.get('value')!='public'],
            'api_name':option.get('api_name',''),'secret_label':option.get('secret_label','API key / secret'),
            'extra_label':option.get('extra_label',''),'extra_key':'access_extra' if needs_extra else '',
            'stored_key':bool(slot.get('secret_enc')) or (access_type=='naver_legacy' and bool(getattr(source,'api_key_enc',''))),
            'env_key_present':bool(secret) and not bool(slot.get('secret_enc')),
            'extra_stored':bool(slot.get('extra') or slot.get('folder_id')) or (access_type=='naver_legacy' and bool(cfg.get('api_extra'))),
            'extra_env_present':bool(extra) and not bool(slot.get('extra') or slot.get('folder_id')),
            'extra_configured':bool(extra) if needs_extra else True,
            'api_configured':api_configured,
            'public_query_template':public_query_template(source),
            'mode':option.get('label') if api_configured else ('Public search' if access_type=='public' or cap.get('public_fallback') else 'Not configured'),
        }
    stored=bool(getattr(source,'api_key_enc',''))
    env=bool(os.getenv(cap.get('env_key',''),'')) if cap.get('env_key') else False
    shared=False
    if cap.get('shared_credential_group')=='searchapi' and not stored and not env:
        try:
            shared=bool(_provider_secret(source,cap))
        except Exception:
            shared=False
    extra_key=cap.get('extra_key') or ''
    extra_stored=bool((getattr(source,'config_json',{}) or {}).get('api_extra')) if extra_key else False
    extra_env=bool(os.getenv(cap.get('env_extra',''),'')) if cap.get('env_extra') else False
    extra_ok=(extra_stored or extra_env) if extra_key else True
    api_configured=bool(_provider_secret(source,cap)) and extra_ok if cap.get('api_name') else False
    return {
        **cap,
        'stored_key':stored or shared,'shared_key_present':shared,'env_key_present':env,'extra_stored':extra_stored,'extra_env_present':extra_env,'extra_configured':extra_ok,
        'api_configured':api_configured,
        'public_query_template':public_query_template(source),
        'mode':'API' if api_configured else ('Public search' if cap.get('public_fallback',getattr(source,'public_fallback',False)) else 'Not configured'),
    }


def _stat(source):
    st,_=SearchProviderStat.objects.get_or_create(source=source,day=timezone.localdate())
    return st


def provider_budget_kind(source):
    """Return the default-budget class used by the provider's active access path."""
    try:
        return 'api' if provider_credential_state(source).get('api_configured') else 'public'
    except Exception:
        return 'public'


def _provider_budget_group(source):
    cap=provider_capability(source)
    return str(cap.get('shared_budget_group') or (getattr(source,'config_json',{}) or {}).get('shared_budget_group') or '').strip().lower()


def _provider_budget_group_sources(source):
    group=_provider_budget_group(source)
    if not group:
        return SearchSource.objects.filter(pk=getattr(source,'pk',None))
    if group=='searchapi':
        return SearchSource.objects.filter(name__startswith='SearchAPI ·')
    return SearchSource.objects.filter(pk=getattr(source,'pk',None))


def provider_budget(source):
    cfg=PortalSettings.objects.get_or_create(pk=1)[0]
    group=_provider_budget_group(source)
    if group=='searchapi':
        # 0.11.135: SearchAPI is one account and one shared user-visible daily limit,
        # regardless of how many SearchAPI services are enabled in the unified dialog.
        try:
            return max(0,min(10000,int(getattr(cfg,'searchapi_daily_limit',500))))
        except Exception:
            return 500
    if group:
        overrides=[int(x) for x in _provider_budget_group_sources(source).values_list('daily_budget_override',flat=True) if x is not None]
        if overrides:
            return max(1,max(overrides))
    elif source.daily_budget_override is not None:
        return max(1,int(source.daily_budget_override))
    if provider_budget_kind(source)=='api':
        return max(1,int(getattr(cfg,'provider_api_daily_request_budget',500) or 500))
    return max(1,int(getattr(cfg,'provider_public_daily_request_budget',5000) or 5000))


def provider_budget_used(source):
    group=_provider_budget_group(source)
    if not group:
        return max(0,int(_stat(source).requests or 0))
    source_ids=list(_provider_budget_group_sources(source).values_list('pk',flat=True))
    if not source_ids:
        return 0
    # Sum in Python to stay compatible with the
    # lightweight ORM/test doubles used by ScoutBox release checks.
    return sum(int(x or 0) for x in SearchProviderStat.objects.filter(source_id__in=source_ids,day=timezone.localdate()).values_list('requests',flat=True))


def provider_budget_remaining(source):
    return max(0,provider_budget(source)-provider_budget_used(source))


def provider_is_usable(source):
    try:
        state=provider_credential_state(source)
        if state.get('api_configured'):
            return True
        access=str(state.get('access_type') or 'public')
        public_allowed=(access=='public' or bool(getattr(source,'public_fallback',True)))
        return bool(public_allowed and state.get('public_query_template'))
    except Exception:
        return False


def _recent_provider_health_map(sources, days=7):
    """Aggregate recent search-engine yield, retention and errors for routing.

    Raw result volume is not treated as success. ``unique_results`` records newly created
    opportunities; current Opportunity/Hidden Lead state then adds a retention signal so
    sources whose finds are repeatedly recycled do not keep winning on raw creation alone.
    """
    source_ids=[getattr(source,'pk',None) for source in sources if getattr(source,'pk',None)]
    if not source_ids:
        return {}
    window_days=max(1,int(days or 7))
    cutoff=timezone.localdate()-timedelta(days=window_days-1)
    cutoff_dt=timezone.now()-timedelta(days=window_days)
    totals={}
    for row in SearchProviderStat.objects.filter(source_id__in=source_ids,day__gte=cutoff).values(
        'source_id','requests','results','unique_results','duplicates','errors','avg_latency_ms'
    ):
        bucket=totals.setdefault(row['source_id'],{
            'requests':0,'results':0,'unique_results':0,'duplicates':0,'errors':0,'latency_weighted':0,
            'active_opportunities':0,'discarded_opportunities':0,'active_leads':0,'discarded_leads':0,
        })
        req=int(row.get('requests') or 0)
        bucket['requests']+=req; bucket['results']+=int(row.get('results') or 0)
        bucket['unique_results']+=int(row.get('unique_results') or 0); bucket['duplicates']+=int(row.get('duplicates') or 0)
        bucket['errors']+=int(row.get('errors') or 0); bucket['latency_weighted']+=req*int(row.get('avg_latency_ms') or 0)
    for row in Opportunity.objects.filter(source_id__in=source_ids,first_seen_by_portal__gte=cutoff_dt).values(
        'source_id','user_deleted','suppressed'
    ).annotate(total=Count('id')):
        bucket=totals.setdefault(row['source_id'],{
            'requests':0,'results':0,'unique_results':0,'duplicates':0,'errors':0,'latency_weighted':0,
            'active_opportunities':0,'discarded_opportunities':0,'active_leads':0,'discarded_leads':0,
        })
        key='discarded_opportunities' if bool(row.get('user_deleted') or row.get('suppressed')) else 'active_opportunities'
        bucket[key]+=int(row.get('total') or 0)
    for row in CompanyLead.objects.filter(source_id__in=source_ids,created_at__gte=cutoff_dt).values(
        'source_id','user_deleted'
    ).annotate(total=Count('id')):
        bucket=totals.setdefault(row['source_id'],{
            'requests':0,'results':0,'unique_results':0,'duplicates':0,'errors':0,'latency_weighted':0,
            'active_opportunities':0,'discarded_opportunities':0,'active_leads':0,'discarded_leads':0,
        })
        key='discarded_leads' if bool(row.get('user_deleted')) else 'active_leads'
        bucket[key]+=int(row.get('total') or 0)
    for bucket in totals.values():
        req=max(0,int(bucket['requests']))
        active=int(bucket['active_opportunities'])+int(bucket['active_leads'])
        discarded=int(bucket['discarded_opportunities'])+int(bucket['discarded_leads'])
        kept_total=active+discarded
        bucket['active_records']=active; bucket['discarded_records']=discarded
        bucket['retention_rate']=(float(active)/kept_total) if kept_total else 0.0
        bucket['error_rate']=(float(bucket['errors'])/req) if req else 0.0
        bucket['unique_per_100']=(100.0*float(bucket['unique_results'])/req) if req else 0.0
        bucket['active_per_100']=(100.0*float(active)/req) if req else 0.0
        bucket['results_per_request']=(float(bucket['results'])/req) if req else 0.0
        bucket['avg_latency_ms']=(int(bucket['latency_weighted']/req) if req else 0)
    return totals


def _provider_health_key(source, recent, today_requests=None):
    stats=recent.get(getattr(source,'pk',None),{})
    req=int(stats.get('requests') or 0); unique=int(stats.get('unique_results') or 0)
    active=int(stats.get('active_records') or 0); discarded=int(stats.get('discarded_records') or 0)
    error_rate=float(stats.get('error_rate') or 0.0); unique_rate=float(stats.get('unique_per_100') or 0.0)
    active_rate=float(stats.get('active_per_100') or 0.0); retention=float(stats.get('retention_rate') or 0.0)
    # Tier 0: strong demonstrated yield. Tier 1: low-volume retained yield or a new
    # provider worth exploring. Tier 2: substantial traffic with negligible/poor retained
    # value. Tier 3: repeatedly failing. This keeps a healthy but low-yield provider in
    # rotation without letting it consume the same query volume as a proven provider.
    if req >= 20 and error_rate >= 0.65:
        tier=3
    elif req >= 40 and active <= 1 and discarded >= 5 and retention < 0.15:
        tier=2
    elif active == 0 and discarded >= 3:
        tier=2
    elif req >= 100 and active == 0 and discarded >= 1 and unique_rate < 0.05:
        tier=2
    elif req >= 40 and active == 0 and unique == 0:
        tier=2
    elif error_rate < 0.50 and (active_rate >= 0.05 or unique_rate >= 0.25):
        tier=0
    elif active > 0 or unique > 0:
        tier=1
    else:
        tier=1
    quality=(active_rate*12.0)+(unique_rate*4.0)+(min(active,30)*2.0)+(retention*10.0)-min(45.0,error_rate*45.0)-min(20,discarded)*0.25
    if isinstance(today_requests,dict):
        today_count=int(today_requests.get(getattr(source,'pk',None)) or 0)
    else:
        today_count=int(_stat(source).requests or 0)
    utilization=today_count/max(1,provider_budget(source))
    return (tier,-quality,utilization,error_rate,-int(source.provider_weight or 0),-int(source.priority or 0),source.name.casefold())


def _sort_provider_candidates(candidates):
    candidates=list(candidates)
    recent=_recent_provider_health_map(candidates,days=7)
    ids=[source.pk for source in candidates if getattr(source,'pk',None)]
    today_requests={row['source_id']:int(row.get('requests') or 0) for row in SearchProviderStat.objects.filter(source_id__in=ids,day=timezone.localdate()).values('source_id','requests')} if ids else {}
    candidates.sort(key=lambda source:_provider_health_key(source,recent,today_requests))
    return candidates


def _degraded_provider_probe_due(source, minutes=None):
    """Return whether a low-yield engine is due for one recovery probe.

    The previous adaptive selector allowed one degraded provider *per campaign run*. With
    several campaigns that still produced bursts of Yahoo/Startpage/etc. activity even
    though those engines had near-zero retained yield. Recovery exploration is now global
    and time-bounded: once a degraded provider has been probed recently, other campaigns
    spend their slots on healthy engines instead.
    """
    try:
        if minutes is None:
            minutes=max(30,min(1440,int(os.environ.get('SCOUTBOX_DEGRADED_SEARCH_PROBE_INTERVAL_MINUTES','360') or 360)))
        cutoff=timezone.now()-timedelta(minutes=max(1,int(minutes)))
        return not UsageMetric.objects.filter(
            category='search',provider=source.name,stage='query',at__gte=cutoff
        ).exists()
    except Exception:
        return True


def provider_recent_health(source, days=7):
    """Return one provider's rolling health for diagnostics and per-run query sizing."""
    return _recent_provider_health_map([source],days=days).get(getattr(source,'pk',None),{
        'requests':0,'results':0,'unique_results':0,'duplicates':0,'errors':0,
        'active_opportunities':0,'discarded_opportunities':0,'active_leads':0,'discarded_leads':0,
        'active_records':0,'discarded_records':0,'retention_rate':0.0,
        'error_rate':0.0,'unique_per_100':0.0,'active_per_100':0.0,'results_per_request':0.0,'avg_latency_ms':0,
    })


def _provider_query_allowance_from_stats(stats, requested):
    requested=max(1,int(requested or 1))
    stats=stats or {}
    req=int(stats.get('requests') or 0); unique=int(stats.get('unique_results') or 0); active=int(stats.get('active_records') or 0); discarded=int(stats.get('discarded_records') or 0)
    error_rate=float(stats.get('error_rate') or 0.0); unique_rate=float(stats.get('unique_per_100') or 0.0)
    active_rate=float(stats.get('active_per_100') or 0.0); retention=float(stats.get('retention_rate') or 0.0)
    # Known-bad providers get one cheap recovery probe, not a full campaign slice.
    if req >= 20 and error_rate >= 0.65:
        return 1
    if req >= 40 and active <= 1 and discarded >= 5 and retention < 0.15:
        return 1
    if active == 0 and discarded >= 3:
        return 1
    if req >= 100 and active == 0 and discarded >= 1 and unique_rate < 0.05:
        return 1
    if req >= 40 and unique == 0 and active == 0:
        return 1
    # Strong yield keeps the configured slice. This is source-agnostic and adapts as
    # provider quality changes instead of hard-coding a preferred engine name.
    if error_rate < 0.50 and (active_rate >= 0.05 or unique_rate >= 0.25):
        return requested
    # A provider that has retained something but at very low yield stays useful as
    # diversification, at one fifth of the configured query volume.
    if active > 0 and error_rate < 0.50:
        return min(requested,max(2,(requested+4)//5))
    # Unique-but-not-yet-retained output gets a smaller exploration slice.
    if unique > 0 and error_rate < 0.50:
        return min(requested,max(1,(requested+9)//10))
    # New/unsampled providers get two probes; established no-yield providers get one.
    if req < 20:
        return min(requested,2)
    return 1


def provider_query_allowance(source, requested):
    """Right-size per-run work from both recent saturation and seven-day retained yield.

    The short window catches a provider that was productive last week but is returning only
    duplicates/errors now. That provider gets one recovery probe instead of inheriting a
    large allowance from stale historical success.
    """
    requested=max(1,int(requested or 1))
    # SearchAPI Google Jobs is the market-localized coverage anchor. Do not shrink a newly
    # configured account to two probes before it has had enough market turns to establish
    # country-specific yield. Normal daily budgets still cap total usage.
    if getattr(source,'name','')=='SearchAPI · Google Jobs' and provider_credential_state(source).get('api_configured'):
        return requested
    recent=provider_recent_health(source,days=2)
    recent_requests=int(recent.get('requests') or 0)
    recent_unique=int(recent.get('unique_results') or 0)
    recent_active=int(recent.get('active_records') or 0)
    recent_error=float(recent.get('error_rate') or 0.0)
    if recent_requests>=24 and recent_unique==0 and recent_active==0:
        return 1
    if recent_requests>=12 and recent_error>=0.60:
        return 1
    return _provider_query_allowance_from_stats(provider_recent_health(source,days=7),requested)


def provider_selection_details(limit=3, preferred_only=True, ignore_budget=False):
    """Choose providers with preferred-first failover and return diagnostic reasons."""
    # Supplemental SearchAPI engines (Forums/News) are configured and tested like search
    # providers, but they run in bounded signal lanes rather than competing with ordinary
    # Opportunity SERP providers for the main query budget.
    base=[source for source in SearchSource.objects.filter(enabled=True,name__in=ACTIVE_PROVIDER_NAMES) if not bool((source.config_json or {}).get('supplemental_only'))]
    usable=[source for source in base if provider_is_usable(source)]
    unusable=[source for source in base if source not in usable]
    # 0.11.74: Preferred Search Engines is retired. Every enabled, usable search engine
    # participates in the same adaptive pool; disabling an engine is the only opt-out.
    available=[source for source in usable if ignore_budget or provider_budget_remaining(source)>0]
    exhausted=[source for source in usable if not ignore_budget and provider_budget_remaining(source)<=0]
    ordered=_sort_provider_candidates(available)
    preferred_available=list(available); fallback_available=[]
    preferred_exhausted=list(exhausted); fallback_exhausted=[]
    selection_limit=max(0,int(limit or 0))
    if selection_limit:
        recent_for_selection=_recent_provider_health_map(ordered,days=7)
        healthy=[source for source in ordered if _provider_health_key(source,recent_for_selection)[0] < 2]
        reserved=[]
        for reserved_name in ('SearchAPI · Google Jobs','SearchAPI · Google Web'):
            source=next((x for x in ordered if x.name==reserved_name and provider_credential_state(x).get('api_configured')),None)
            if source is not None and len(reserved)<selection_limit:
                reserved.append(source)
        reserved_ids={source.pk for source in reserved}
        leaders=reserved+[source for source in healthy if source.pk not in reserved_ids][:max(0,selection_limit-len(reserved))]
        leader_ids={source.pk for source in leaders}
        remainder=[source for source in ordered if source.pk not in leader_ids]
        # Never fill spare slots with a whole set of known-bad engines. At most one
        # degraded source receives a one-query recovery probe, and that probe is globally
        # rate-limited across campaigns so failing/zero-yield engines cannot dominate the
        # Search Activity stream merely because many campaigns run concurrently.
        due_recovery=[source for source in remainder if _degraded_provider_probe_due(source)]
        if due_recovery and len(leaders)<selection_limit:
            bucket=int(timezone.now().timestamp()//14400)
            leaders.append(due_recovery[bucket % len(due_recovery)])
        selected=leaders
    else:
        selected=[]
    selected_ids={source.pk for source in selected}
    recent=_recent_provider_health_map(usable,days=7)
    query_default=PortalSettings.objects.get_or_create(pk=1)[0].queries_per_provider
    health={}
    for source in usable:
        row=recent.get(source.pk,{})
        health[source.name]={
            'requests_7d':int(row.get('requests') or 0),'unique_7d':int(row.get('unique_results') or 0),
            'active_records_7d':int(row.get('active_records') or 0),'discarded_records_7d':int(row.get('discarded_records') or 0),
            'retention_rate_7d':round(float(row.get('retention_rate') or 0.0),4),
            'errors_7d':int(row.get('errors') or 0),'error_rate_7d':round(float(row.get('error_rate') or 0.0),4),
            'unique_per_100_requests_7d':round(float(row.get('unique_per_100') or 0.0),3),
            'query_allowance':_provider_query_allowance_from_stats(row,query_default),
            'selected':source.pk in selected_ids,
        }
    details={
        'preferred_eligible':[source.name for source in preferred_available],
        'preferred_exhausted':[source.name for source in preferred_exhausted],
        'fallback_selected':[],
        'budget_exhausted':[source.name for source in preferred_exhausted+fallback_exhausted],
        'selected':[source.name for source in selected],
        'unusable':[source.name for source in unusable],
        'usable_count':len(usable),
        'enabled_count':len(base),
        'fallback_eligible':[source.name for source in fallback_available if source.pk not in selected_ids],
        'adaptive_health_7d':health,
    }
    return selected,details


def choose_providers(limit=3, preferred_only=True, ignore_budget=False):
    return provider_selection_details(limit=limit,preferred_only=preferred_only,ignore_budget=ignore_budget)[0]


def provider_region_context(source_or_name,market=None):
    """Describe the regional setting actually applied by a search adapter."""
    name=source_or_name.name if hasattr(source_or_name,'name') else str(source_or_name or '')
    meta=market_search_meta(market)
    setting=''; market_name=str(meta.get('market') or '')
    if name=='DuckDuckGo':
        setting=str(meta.get('ddg_region') or 'wt-wt')
    elif name in {'Google','Bing'}:
        setting=str(meta.get('locale') or 'en-US')
    elif name.startswith('SearchAPI · Google'):
        setting=f"gl={str(meta.get('country_code') or '').lower() or '-'} · hl={str(meta.get('locale') or 'en').split('-',1)[0].lower()}"
    elif name=='Naver':
        setting='ko-KR'; market_name=market_name or 'South Korea'
    elif name=='Baidu':
        setting='zh-CN'; market_name=market_name or 'China'
    if not setting:
        return {}
    return {
        'region_setting':setting[:24],
        'locale':str(meta.get('locale') or '')[:24],
        'market':market_name[:80],
        'market_code':str(meta.get('market_code') or '')[:24],
        'country_code':str(meta.get('country_code') or '')[:8],
        'provider_locale':(setting if name in {'Google','Bing','Naver','Baidu'} else str(meta.get('locale') or setting))[:32],
    }


def provider_market_compatible(source_or_name, market=None):
    """Keep strictly regional engines out of unrelated market passes.

    Naver deliberately remains global here: although its interface locale is Korean,
    its web index regularly returns useful international employer records.
    """
    name=source_or_name.name if hasattr(source_or_name,'name') else str(source_or_name or '')
    code=str(market_search_meta(market).get('market_code') or '').strip().lower()
    if not code:
        return not name.startswith('SearchAPI ·')
    # SearchAPI is deliberately market-bound. Skip the synthetic Worldwide market rather
    # than consuming a paid request that the adapter would reject for lacking country
    # context (and, more importantly, never allow Google to supply its implicit US default).
    if name.startswith('SearchAPI ·') and code=='worldwide':
        return False
    allowed={'Baidu':{'hk'}}.get(name)
    return True if allowed is None else code in allowed


def _record(source,started,result_count=0,error='',quota_units=1,bytes_downloaded=0,usage_category='search',query='',market=None,metadata_extra=None,query_language='English'):
    st=_stat(source); old=st.requests
    st.requests+=1; st.results+=result_count; st.quota_units+=quota_units; st.bytes_downloaded+=max(0,int(bytes_downloaded or 0))
    latency=int((time.time()-started)*1000)
    st.avg_latency_ms=int(((st.avg_latency_ms*old)+latency)/max(1,st.requests))
    if error: st.errors+=1; st.last_error=error[:1000]
    st.save()
    # Schedule / Limits threshold notifications also cover Local GPU provider budgets.
    # Keep this lazy to avoid coupling the search adapter module to Cloud routing.
    try:
        from .cloud_budget import _record_threshold
        group=_provider_budget_group(source)
        _record_threshold(
            f'day:{timezone.localdate().isoformat()}',
            ('provider-group:searchapi:requests' if group=='searchapi' else f'provider:{source.pk}:requests'),
            ('SearchAPI requests / day' if group=='searchapi' else f'{source.name} provider requests / day'),
            (provider_budget_used(source) if group=='searchapi' else st.requests), provider_budget(source),
        )
    except Exception:
        pass
    metadata={'results':result_count,'query':(query or '')[:500],'error':(error or '')[:1000]}
    metadata.update(provider_region_context(source,market))
    metadata.update(query_language_metadata(query_language))
    if metadata_extra: metadata.update(dict(metadata_extra))
    UsageMetric.objects.create(category=usage_category,provider=source.name,stage='query',requests=1,pages=1,errors=1 if error else 0,latency_ms=latency,bytes_downloaded=max(0,int(bytes_downloaded or 0)),metadata=usage_metadata(metadata))


SEARCH_ENGINE_HOSTS={
    'google.com','www.google.com','bing.com','www.bing.com','duckduckgo.com','html.duckduckgo.com',
    'search.brave.com','search.yahoo.com','r.search.yahoo.com','startpage.com','www.startpage.com',
    'ecosia.org','www.ecosia.org','yandex.com','www.yandex.com','yandex.ru','www.yandex.ru',
    'baidu.com','www.baidu.com','search.naver.com','www.naver.com',
}


def is_search_engine_url(url):
    try:
        host=urllib.parse.urlsplit(str(url or '')).netloc.lower().split('@')[-1].split(':')[0]
    except Exception:
        return False
    return host in SEARCH_ENGINE_HOSTS


def unwrap_search_result_url(url):
    """Return the external destination hidden inside common search-engine redirect URLs."""
    raw=unescape(str(url or '')).strip()
    if raw.startswith('//'): raw='https:'+raw
    if not raw.startswith(('http://','https://')): return raw
    try:
        p=urllib.parse.urlsplit(raw); host=p.netloc.lower().split('@')[-1].split(':')[0]; qs=urllib.parse.parse_qs(p.query)
        # Google/DDG and several generic wrappers.
        for key in ('uddg','url','target','q','r'):
            candidate=(qs.get(key) or [''])[0]
            candidate=urllib.parse.unquote(candidate or '').strip()
            if candidate.startswith(('http://','https://')) and not is_search_engine_url(candidate):
                return candidate
        # Bing click URLs commonly carry URL-safe base64 in u=a1<encoded target>.
        if host.endswith('bing.com'):
            token=(qs.get('u') or [''])[0]
            if token:
                token=urllib.parse.unquote(token)
                if token.startswith('a1'): token=token[2:]
                try:
                    decoded=base64.urlsafe_b64decode(token+'='*((4-len(token)%4)%4)).decode('utf-8','ignore').strip()
                    if decoded.startswith(('http://','https://')) and not is_search_engine_url(decoded): return decoded
                except Exception: pass
        # Yahoo redirect path: /RU=<destination>/RK=.../RS=...
        if host.endswith('yahoo.com'):
            m=re.search(r'/RU=([^/]+)',p.path)
            if m:
                candidate=urllib.parse.unquote(m.group(1)).strip()
                if candidate.startswith(('http://','https://')) and not is_search_engine_url(candidate): return candidate
    except Exception:
        pass
    return raw


def _normalise_result(title,url,snippet=''):
    return {'title':re.sub(r'\s+',' ',unescape(title or '')).strip(),'url':unwrap_search_result_url(url),'snippet':re.sub(r'\s+',' ',unescape(snippet or '')).strip()}


def _get(url,market=None,**kwargs):
    locale=market_search_meta(market).get('locale') or 'en-US'
    headers={'User-Agent':UA,'Accept-Language':f'{locale},en;q=0.8'}; headers.update(kwargs.pop('headers',{}))
    r=requests.get(url,headers=headers,timeout=15,**kwargs); r.raise_for_status(); return r


SEARCHAPI_ENDPOINT='https://www.searchapi.io/api/v1/search'
SEARCHAPI_ACCOUNT_ENDPOINT='https://www.searchapi.io/api/v1/me'
SEARCHAPI_LOCATIONS_ENDPOINT='https://www.searchapi.io/api/v1/locations'
_SEARCHAPI_LOCATION_CACHE={}
_SEARCHAPI_LOCATION_LOCK=threading.Lock()


def _searchapi_canonical_location(source, market):
    """Resolve/cache SearchAPI's canonical Google location for a Discovery Market.

    The Locations endpoint is infrastructure rather than a user-visible discovery service.
    SearchAPI documents it as a free helper, so it does not consume ScoutBox's shared
    SearchAPI request allowance. Any lookup failure falls back to the explicit market name.
    """
    raw=str(getattr(market,'name','') or '').strip()
    if not raw:
        return ''
    meta=market_search_meta(market)
    country=str(meta.get('country_code') or '').strip().upper()
    cache_key=(raw.casefold(),country)
    with _SEARCHAPI_LOCATION_LOCK:
        cached=_SEARCHAPI_LOCATION_CACHE.get(cache_key)
    if cached is not None:
        return cached or raw
    resolved=raw
    try:
        key=_provider_secret(source,provider_capability(source)) if source is not None else ''
        if key:
            r=requests.get(
                SEARCHAPI_LOCATIONS_ENDPOINT,params={'q':raw},
                headers={'Authorization':f'Bearer {key}','Accept':'application/json','User-Agent':UA},timeout=8,
            )
            data=r.json() if r.ok and r.content else []
            candidates=data if isinstance(data,list) else (data.get('locations') or data.get('results') or []) if isinstance(data,dict) else []
            ranked=[]
            for item in candidates:
                if not isinstance(item,dict):
                    continue
                canonical_name=str(item.get('canonical_name') or item.get('name') or '').strip()
                if not canonical_name:
                    continue
                item_country=str(item.get('country_code') or '').strip().upper()
                target_type=str(item.get('target_type') or item.get('type') or '').strip().casefold()
                score=0
                if country and item_country==country: score+=100
                if canonical_name.casefold()==raw.casefold(): score+=60
                if target_type in {'country','country/region','region'}: score+=20
                ranked.append((score,canonical_name))
            if ranked:
                ranked.sort(reverse=True)
                resolved=ranked[0][1]
    except Exception:
        resolved=raw
    with _SEARCHAPI_LOCATION_LOCK:
        _SEARCHAPI_LOCATION_CACHE[cache_key]=resolved
    return resolved


def _searchapi_locale(market, source=None):
    meta=market_search_meta(market)
    if not market or not meta.get('market_code') or meta.get('market_code')=='worldwide':
        raise RuntimeError('SearchAPI requires an explicit Discovery Market so Google cannot silently default to the United States.')
    locale=str(meta.get('locale') or 'en').strip().lower().replace('_','-')
    base=(locale.split('-',1)[0] or 'en')
    # Google/SearchAPI uses a few legacy or region-specific interface-language values.
    # Preserve Chinese script locales and normalize Hebrew/Norwegian instead of sending
    # an invalid generic code that could weaken localization.
    if locale.startswith('zh-cn'):
        language='zh-cn'
    elif locale.startswith('zh-tw') or locale.startswith('zh-hk'):
        language='zh-tw'
    elif base=='he':
        language='iw'
    elif base=='nb':
        language='no'
    elif locale in {'pt-br','pt-pt'}:
        language=locale
    elif locale=='es-419':
        language=locale
    else:
        language=base
    params={'gl':str(meta.get('country_code') or '').strip().lower(),'hl':language}
    # Use the canonical market/country as the provider location. The query itself may
    # rotate through cities; binding the provider to a different fixed city would create
    # contradictory geography (for example a Manchester query localized to London).
    location=_searchapi_canonical_location(source,market) if source is not None else str(getattr(market,'name','') or '').strip()
    if location:
        params['location']=location
    return params


def _searchapi_error_message(data):
    error=(data or {}).get('error') if isinstance(data,dict) else None
    if isinstance(error,dict):
        return str(error.get('message') or error.get('detail') or error.get('error') or '').strip()
    return str(error or '').strip()


def _searchapi_auth_rejected(response, data=None):
    message=_searchapi_error_message(data or {})
    combined=' '.join(filter(None,[message,str(getattr(response,'text','') or '')[:1200]])).casefold()
    auth_markers=('api key','apikey','api_key','authentication','authorization','credential','token')
    invalid_words=('invalid','unauthor','forbidden','not valid','rejected','incorrect','missing')
    auth_message=any(marker in combined for marker in auth_markers) and any(word in combined for word in invalid_words)
    status=int(getattr(response,'status_code',0) or 0)
    # 401 is an authentication failure. A generic 403 can also mean an engine/plan
    # restriction, so only treat 403 as a bad credential when SearchAPI's response
    # actually identifies an auth/key problem.
    return bool(status==401 or (status in (400,403,422) and auth_message))


def _set_searchapi_validation_state(status, message, http_status=0, source=None):
    """Persist one shared SearchAPI credential state on the unified hub.

    Successful authenticated service traffic is conclusive credential evidence, so it
    heals a prior save-time timeout/warning without requiring the user to re-save.
    """
    try:
        hub=searchapi_master_source() or source
        if hub is None:
            return
        cfg=dict(getattr(hub,'config_json',{}) or {})
        normalized=str(status or '').strip().lower()
        # Do not write on every normal SearchAPI request once the key is known-good.
        if normalized=='valid' and str(cfg.get('searchapi_validation_status') or '').strip().lower()=='valid':
            return
        cfg['searchapi_validation_status']=normalized
        cfg['searchapi_validation_message']=str(message or '')[:1000]
        cfg['searchapi_validation_http_status']=int(http_status or 0)
        cfg['searchapi_validated_at']=timezone.now().isoformat()
        hub.config_json=cfg
        hub.save(update_fields=['config_json'])
    except Exception:
        pass


def _mark_searchapi_authenticated_success(source=None, http_status=200):
    _set_searchapi_validation_state('valid','SearchAPI accepted the configured API key.',http_status or 200,source=source)


def validate_searchapi_credential(source, api_key=None, timeout=10):
    """Validate the shared SearchAPI credential without creating search telemetry.

    Use SearchAPI's account endpoint rather than launching a Google search. The account
    endpoint directly tests authentication and avoids a false warning when a live SERP
    request happens to be slow even though the credential is valid.
    """
    key=str(api_key or _provider_secret(source,provider_capability(source)) or '').strip()
    if not key:
        return {'status':'unconfigured','ok':False,'message':'No SearchAPI API key is configured.','http_status':0}
    headers={'Authorization':f'Bearer {key}','Accept':'application/json','User-Agent':UA}
    try:
        response=requests.get(SEARCHAPI_ACCOUNT_ENDPOINT,headers=headers,timeout=max(4,min(20,int(timeout or 10))))
    except requests.RequestException as exc:
        return {'status':'unavailable','ok':False,'message':f'Validation request could not reach SearchAPI: {exc}','http_status':0}
    except Exception as exc:
        return {'status':'unavailable','ok':False,'message':f'Validation request failed: {exc}','http_status':0}
    try:
        data=response.json() if response.content else {}
    except Exception:
        data={}
    message=_searchapi_error_message(data)
    # /api/v1/me is an authenticated account call. A normal successful account payload
    # proves the same shared key used by Jobs/Web/Forums/etc. is accepted.
    if response.ok and isinstance(data,dict) and any(k in data for k in ('account','api_usage','subscription')):
        return {'status':'valid','ok':True,'message':'SearchAPI accepted the API key.','http_status':int(response.status_code or 200)}
    if _searchapi_auth_rejected(response,data):
        detail=message or f'HTTP {response.status_code}'
        return {'status':'invalid','ok':False,'message':f'SearchAPI rejected the API key ({detail}).','http_status':int(response.status_code or 0)}
    detail=message or f'HTTP {response.status_code}'
    return {'status':'unavailable','ok':False,'message':f'SearchAPI validation did not return a usable account response ({detail}).','http_status':int(response.status_code or 0)}


def _searchapi_request(source, engine, query, limit=10, market=None, extra_params=None):
    key=_provider_secret(source,provider_capability(source))
    if not key:
        raise RuntimeError('SearchAPI API key is not configured. Save it on any SearchAPI provider or set SEARCHAPI_API_KEY.')
    params={'engine':engine,'q':query,**_searchapi_locale(market,source)}
    # Never reuse the credential variable while copying engine parameters. 0.11.137
    # accidentally replaced ``key`` with the final extra-parameter name (for example
    # ``safe``/``link``), causing Forums/News/Local to authenticate as "Bearer safe"
    # while Jobs/Web still worked because they passed no extra parameters.
    for param_name,param_value in dict(extra_params or {}).items():
        if param_value not in (None,''):
            params[str(param_name)]=param_value
    # Do not force Google's document-language restriction here. A Japanese, German, or
    # Brazilian market can legitimately contain English-language employer/job pages. The
    # market's gl/location/hl localize discovery, while ScoutBox's multilingual query plan
    # and page translator handle native-language exploration without suppressing English.
    headers={'Authorization':f'Bearer {key}','Accept':'application/json','User-Agent':UA}
    total_bytes=0
    attempts=[params]
    while attempts:
        active_params=attempts.pop(0)
        r=requests.get(SEARCHAPI_ENDPOINT,params=active_params,headers=headers,timeout=25)
        total_bytes+=len(r.content or b'')
        data={}
        try:
            data=r.json() if r.content else {}
        except Exception:
            data={}
        if r.ok:
            if str((data.get('search_metadata') or {}).get('status') or '').lower() in {'error','failed'}:
                message=_searchapi_error_message(data) or 'SearchAPI request failed'
                raise RuntimeError(message)
            _mark_searchapi_authenticated_success(source,int(getattr(r,'status_code',200) or 200))
            return data,total_bytes

        if _searchapi_auth_rejected(r,data):
            detail=_searchapi_error_message(data) or f'HTTP {getattr(r,"status_code",0) or 0}'
            _set_searchapi_validation_state('invalid',f'SearchAPI rejected the configured API key ({detail}).',int(getattr(r,'status_code',0) or 0),source=source)

        # SearchAPI's Google Jobs country-code surface is narrower than ordinary Google
        # Search in some regions. If (and only if) the API explicitly rejects the country
        # parameter, retry once without gl while retaining the concrete market location
        # and language. We never retry without location, so Google's US default cannot
        # silently enter a market-specific ScoutBox pass.
        message=' '.join(filter(None,[
            _searchapi_error_message(data),
            str(getattr(r,'text','') or '')[:1200],
        ])).lower()
        bad_country=(r.status_code in (400,422) and 'gl' in active_params and (
            ('gl' in message and any(token in message for token in ('invalid','unsupported','not supported','country','parameter','value')))
            or ('country' in message and any(token in message for token in ('invalid','unsupported','not supported')))
        ))
        if engine=='google_jobs' and bad_country and active_params.get('location'):
            retry=dict(active_params); retry.pop('gl',None)
            attempts.append(retry)
            continue
        try:
            r.raise_for_status()
        except requests.RequestException as exc:
            detail=_searchapi_error_message(data)
            raise RuntimeError(f'SearchAPI request failed: {detail or exc}') from exc
        raise RuntimeError('SearchAPI request failed')
    raise RuntimeError('SearchAPI request failed')


def _searchapi_apply_link(item):
    """Prefer employer/ATS application targets over aggregator mirrors."""
    candidates=[]
    for candidate in (item.get('apply_links') or []):
        if not isinstance(candidate,dict):
            continue
        link=str(candidate.get('link') or '').strip()
        if link.startswith(('http://','https://')):
            candidates.append((link,str(candidate.get('source') or '').strip()))
    primary=str(item.get('apply_link') or '').strip()
    if primary.startswith(('http://','https://')) and all(link!=primary for link,_ in candidates):
        candidates.append((primary,''))
    if not candidates:
        return '',''

    ats_hosts=(
        'greenhouse.io','lever.co','ashbyhq.com','workdayjobs.com','myworkdayjobs.com',
        'smartrecruiters.com','workable.com','jobvite.com','icims.com','bamboohr.com',
        'successfactors.com','oraclecloud.com','taleo.net','recruitee.com',
    )
    aggregator_hosts=(
        'linkedin.com','indeed.com','indeed.co.','glassdoor.com','ziprecruiter.com',
        'adzuna.','talent.com','jooble.','jobgether.com','lazyapply.com','monster.',
        'simplyhired.com','careerbuilder.com',
    )
    def score(entry):
        link,source=entry
        try:
            host=(urllib.parse.urlparse(link).hostname or '').lower()
        except Exception:
            host=''
        value=0
        if any(marker in host for marker in ats_hosts): value+=60
        if host.startswith(('jobs.','careers.')) or '.jobs.' in host or '.careers.' in host: value+=40
        source_text=source.casefold()
        if any(word in source_text for word in ('company','career','employer','official')): value+=20
        if any(marker in host for marker in aggregator_hosts): value-=80
        if primary and link==primary: value+=5
        return value
    link,source=max(candidates,key=score)
    return link,source


def _searchapi_job_rows(data,limit):
    out=[]; seen=set()
    for item in (data.get('jobs') or []):
        if not isinstance(item,dict): continue
        apply_link,apply_source=_searchapi_apply_link(item)
        url=unwrap_search_result_url(apply_link)
        if not url.startswith(('http://','https://')) or is_search_engine_url(url) or url in seen: continue
        seen.add(url)
        title=' '.join(str(item.get('title') or '').split())
        company=' '.join(str(item.get('company_name') or '').split())
        location=' '.join(str(item.get('location') or '').split())
        description=' '.join(str(item.get('description') or '').split())
        via=' '.join(str(item.get('via') or apply_source or '').split())
        extensions=' · '.join(str(x) for x in (item.get('extensions') or []) if str(x).strip())
        snippet=' · '.join(x for x in (company,location,extensions,description) if x)[:45000]
        row=_normalise_result(title,url,snippet)
        row.update({
            'company':company[:220], '_direct_source':True, '_direct_adapter':'searchapi_google_jobs',
            '_acquisition_path':'SearchAPI Google Jobs structured result', '_role_location_hint':location[:800],
            '_apply_via':(apply_source or via)[:220], '_searchapi_via':via[:220],
        })
        out.append(row)
        if len(out)>=limit: break
    return out


def search_searchapi_google_jobs(query,limit=10,source=None,market=None):
    data,size=_searchapi_request(source,'google_jobs',query,limit=limit,market=market)
    return _searchapi_job_rows(data,limit),size


def search_searchapi_google_web(query,limit=10,source=None,market=None):
    data,size=_searchapi_request(source,'google',query,limit=limit,market=market)
    out=[]; seen=set()
    for item in (data.get('organic_results') or []):
        if not isinstance(item,dict): continue
        url=unwrap_search_result_url(str(item.get('link') or '').strip())
        if not url.startswith(('http://','https://')) or is_search_engine_url(url) or url in seen: continue
        seen.add(url)
        out.append(_normalise_result(item.get('title',''),url,item.get('snippet','')))
        if len(out)>=limit: break
    if len(out)<limit:
        for row in _searchapi_job_rows(data,limit-len(out)):
            if row.get('url') not in seen:
                out.append(row); seen.add(row.get('url'))
    return out[:limit],size


def _searchapi_signal_rows(data,limit,*,adapter,acquisition_path,forum=False,news=False):
    """Normalize SearchAPI discussion/news results for ScoutBox signal lanes."""
    out=[]; seen=set(); items=list(data.get('organic_results') or [])
    if news:
        items.extend(data.get('top_stories') or [])
    for item in items:
        if not isinstance(item,dict):
            continue
        url=unwrap_search_result_url(str(item.get('link') or '').strip())
        if not url.startswith(('http://','https://')) or is_search_engine_url(url) or url in seen:
            continue
        seen.add(url)
        source_name=' '.join(str(item.get('source') or '').split())
        domain=' '.join(str(item.get('domain') or '').split())
        date=' '.join(str(item.get('date') or '').split())
        snippet=' · '.join(x for x in (source_name,domain,date,' '.join(str(item.get('snippet') or '').split())) if x)[:12000]
        row=_normalise_result(item.get('title',''),url,snippet)
        row.update({
            '_direct_source':False,
            '_direct_adapter':adapter,
            '_acquisition_path':acquisition_path,
            '_structured_signal_evidence':True,
            '_community_hiring_signal':True,
            '_community_kind':('news_hiring_signal' if news else 'forum_discussion'),
            '_searchapi_source_name':source_name[:220],
            '_searchapi_source_domain':domain[:220],
            'published_at':date[:120],
        })
        if forum:
            row.update({'_forum_source':True,'_source_category_override':'forum','_apply_via':'forum'})
        if news:
            # News is evidence that an employer may be hiring/expanding, never a vacancy URL.
            row.update({'_news_signal':True,'_signal_only':True,'_source_category_override':'news'})
        out.append(row)
        if len(out)>=limit:
            break
    return out


def search_searchapi_google_forums(query,limit=10,source=None,market=None):
    data,size=_searchapi_request(
        source,'google_forums',query,limit=limit,market=market,
        extra_params={'time_period':'last_month','link':'resolved','safe':'active'},
    )
    return _searchapi_signal_rows(
        data,limit,adapter='searchapi_google_forums',
        acquisition_path='SearchAPI Google Forums structured discussion',forum=True,
    ),size


def search_searchapi_google_news(query,limit=10,source=None,market=None):
    data,size=_searchapi_request(
        source,'google_news',query,limit=limit,market=market,
        extra_params={'time_period':'last_month','sort_by':'most_recent','link':'resolved'},
    )
    return _searchapi_signal_rows(
        data,limit,adapter='searchapi_google_news',
        acquisition_path='SearchAPI Google News hiring/expansion signal',news=True,
    ),size


def _searchapi_reference_rows(data,limit=10,adapter='searchapi_ai_research',acquisition_path='SearchAPI AI research'):
    out=[]; seen=set(); items=[]
    for key in ('reference_links','web_results','organic_results'):
        value=(data or {}).get(key) if isinstance(data,dict) else None
        if isinstance(value,list): items.extend(value)
    for item in items:
        if isinstance(item,str):
            url=item; title=item; snippet=''
        elif isinstance(item,dict):
            url=str(item.get('link') or item.get('url') or item.get('source_url') or '').strip()
            title=str(item.get('title') or item.get('name') or url).strip()
            snippet=str(item.get('snippet') or item.get('text') or item.get('description') or '').strip()
        else:
            continue
        url=unwrap_search_result_url(url)
        if not url.startswith(('http://','https://')) or is_search_engine_url(url) or url in seen:
            continue
        seen.add(url); row=_normalise_result(title,url,snippet)
        row.update({'_direct_source':False,'_direct_adapter':adapter,'_acquisition_path':acquisition_path,'_searchapi_ai_reference':True})
        out.append(row)
        if len(out)>=limit: break
    return out


def _searchapi_ai_answer(data):
    if not isinstance(data,dict): return ''
    for key in ('markdown','answer','response','text'):
        value=data.get(key)
        if isinstance(value,str) and value.strip(): return value.strip()
        if isinstance(value,dict):
            for sub in ('markdown','answer','text','content'):
                x=value.get(sub)
                if isinstance(x,str) and x.strip(): return x.strip()
    blocks=data.get('text_blocks') or []
    if isinstance(blocks,list):
        parts=[]
        for block in blocks:
            if isinstance(block,str):
                parts.append(block)
                continue
            if not isinstance(block,dict):
                continue
            # SearchAPI ChatGPT / Google AI Mode text blocks use ``answer`` for
            # paragraphs/headers and may use nested ``items`` for lists.
            val=block.get('answer') or block.get('text') or block.get('markdown') or block.get('content')
            if isinstance(val,str) and val.strip():
                parts.append(val)
            items=block.get('items') or []
            if isinstance(items,list):
                for item in items:
                    if isinstance(item,str) and item.strip():
                        parts.append(item)
                    elif isinstance(item,dict):
                        item_val=item.get('answer') or item.get('text') or item.get('content')
                        if isinstance(item_val,str) and item_val.strip():
                            parts.append(item_val)
        if parts: return '\n\n'.join(x.strip() for x in parts if x.strip()).strip()
    return ''


def _searchapi_reported_model(data, fallback='chatgpt'):
    if isinstance(data,dict):
        for value in (
            (data.get('response_metadata') or {}).get('model') if isinstance(data.get('response_metadata'),dict) else '',
            data.get('model'),
            (data.get('search_metadata') or {}).get('model') if isinstance(data.get('search_metadata'),dict) else '',
            (data.get('response') or {}).get('model') if isinstance(data.get('response'),dict) else '',
        ):
            if isinstance(value,str) and value.strip(): return value.strip()
    return fallback


def _searchapi_direct_request(source,engine,query,extra_params=None,market=None,require_market=False):
    key=_provider_secret(source,provider_capability(source))
    if not key:
        raise RuntimeError('SearchAPI API key is not configured. Save it in the SearchAPI dialog or set SEARCHAPI_API_KEY.')
    params={'engine':engine,'q':query}
    if require_market:
        params.update(_searchapi_locale(market,source))
    for k,v in dict(extra_params or {}).items():
        if v not in (None,''): params[str(k)]=v
    headers={'Authorization':f'Bearer {key}','Accept':'application/json','User-Agent':UA}
    r=requests.get(SEARCHAPI_ENDPOINT,params=params,headers=headers,timeout=35)
    data={}
    try: data=r.json() if r.content else {}
    except Exception: data={}
    if not r.ok:
        if _searchapi_auth_rejected(r,data):
            detail=_searchapi_error_message(data) or f'HTTP {getattr(r,"status_code",0) or 0}'
            _set_searchapi_validation_state('invalid',f'SearchAPI rejected the configured API key ({detail}).',int(getattr(r,'status_code',0) or 0),source=source)
        detail=_searchapi_error_message(data)
        try: r.raise_for_status()
        except requests.RequestException as exc: raise RuntimeError(f'SearchAPI request failed: {detail or exc}') from exc
    if str((data.get('search_metadata') or {}).get('status') or '').lower() in {'error','failed'}:
        raise RuntimeError(_searchapi_error_message(data) or 'SearchAPI request failed')
    _mark_searchapi_authenticated_success(source,int(getattr(r,'status_code',200) or 200))
    return data,len(r.content or b'')


def search_searchapi_google_ai_mode(query,limit=10,source=None,market=None):
    data,size=_searchapi_direct_request(source,'google_ai_mode',query,market=market,require_market=True)
    rows=_searchapi_reference_rows(data,limit,adapter='searchapi_google_ai_mode',acquisition_path='SearchAPI Google AI Mode research')
    answer=_searchapi_ai_answer(data)
    for row in rows:
        row['_searchapi_ai_answer']=answer[:12000]
    return rows,size


def search_searchapi_google_local(query,limit=10,source=None,market=None):
    data,size=_searchapi_request(source,'google_local',query,limit=limit,market=market,extra_params={'link':'resolved'})
    out=[]; seen=set()
    for item in (data.get('local_results') or []):
        if not isinstance(item,dict): continue
        url=unwrap_search_result_url(str(item.get('website') or item.get('link') or '').strip())
        if not url.startswith(('http://','https://')) or is_search_engine_url(url) or url in seen: continue
        seen.add(url)
        title=' '.join(str(item.get('title') or item.get('name') or '').split())
        address=' '.join(str(item.get('address') or '').split())
        kind=' '.join(str(item.get('type') or item.get('category') or '').split())
        snippet=' · '.join(x for x in (kind,address) if x)
        row=_normalise_result(title,url,snippet)
        row.update({
            '_direct_source':False,'_direct_adapter':'searchapi_google_local',
            '_acquisition_path':'SearchAPI Google Local employer discovery',
            '_employer_discovery':True,
            '_community_kind':'employer_discovery','_signal_only':True,
            '_source_category_override':'employer_discovery',
        })
        out.append(row)
        if len(out)>=limit: break
    return out,size


def _direct_cloud_ai_available():
    """Return true only when a user-configured direct cloud LLM credential is available."""
    try:
        for cfg in AIProviderConfig.objects.filter(provider__in=['openai','gemini','openrouter'],enabled=True):
            if str(decrypt(cfg.api_key_enc or '') or '').strip():
                return True
    except Exception:
        return False
    return False


def _searchapi_ai_auto_count(service):
    start=timezone.make_aware(datetime.combine(timezone.localdate(),datetime.min.time()),timezone.get_current_timezone())
    try:
        if service=='chatgpt':
            return AIRequestLog.objects.filter(provider='SearchAPI',stage='searchapi_research',at__gte=start,metadata__searchapi_service='chatgpt',metadata__automatic=True).count()
        source=searchapi_source(service)
        if not source: return 0
        return UsageMetric.objects.filter(provider=source.name,stage='query',at__gte=start,metadata__automatic=True).count()
    except Exception:
        return 0


def searchapi_ai_auto_allowed(service):
    source=searchapi_source(service)
    if not source or not searchapi_service_auto_enabled(source) or not provider_is_usable(source):
        return False
    if provider_budget_remaining(source)<=0:
        return False
    cfg=dict(source.config_json or {})
    default_limit=100 if service in {'chatgpt','ai_mode'} else 0
    try: limit=max(0,min(1000,int(cfg.get('auto_daily_limit',default_limit))))
    except Exception: limit=default_limit
    return bool(limit and _searchapi_ai_auto_count(service)<limit)


def _record_searchapi_chatgpt(source,started,query,data=None,error='',size=0,automatic=False,purpose='research'):
    data=data or {}; latency=int((time.time()-started)*1000); rows=_searchapi_reference_rows(data,20)
    answer=_searchapi_ai_answer(data); reported=_searchapi_reported_model(data,'chatgpt')
    model=('searchapi-'+reported) if not reported.startswith('searchapi-') else reported
    st=_stat(source); old=st.requests; st.requests+=1; st.results+=len(rows); st.quota_units+=1; st.bytes_downloaded+=max(0,int(size or 0))
    st.avg_latency_ms=int(((st.avg_latency_ms*old)+latency)/max(1,st.requests))
    if error: st.errors+=1; st.last_error=str(error)[:1000]
    st.save()
    try:
        from .cloud_budget import _record_threshold
        _record_threshold(f'day:{timezone.localdate().isoformat()}','provider-group:searchapi:requests','SearchAPI requests / day',provider_budget_used(source),provider_budget(source))
    except Exception: pass
    response_meta=data.get('response_metadata') if isinstance(data,dict) and isinstance(data.get('response_metadata'),dict) else {}
    search_queries=(data.get('search_queries') or data.get('web_search_queries') or response_meta.get('search_queries') or []) if isinstance(data,dict) else []
    if not isinstance(search_queries,list): search_queries=[]
    web_performed=bool(response_meta.get('is_web_search_performed') or search_queries)
    metadata=usage_metadata({'searchapi_service':'chatgpt','automatic':bool(automatic),'purpose':purpose,'references':[x.get('url') for x in rows[:10]],'search_queries':search_queries})
    AIRequestLog.objects.create(
        status=('failed' if error else 'completed'),provider='SearchAPI',model=model,stage='searchapi_research',runtime='cloud',
        subject_type='search_research',subject_label=str(purpose or 'SearchAPI research')[:300],input_text=str(query or '')[:12000],
        output_text=answer[:120000],raw_output_text=answer[:120000],duration_ms=latency,ok=not bool(error),error=str(error or '')[:8000],
        web_search_queries=(len(search_queries) if search_queries else (1 if web_performed and not error else 0)),metadata=metadata,
    )
    return {'answer':answer,'results':rows,'model':model,'latency_ms':latency}


def search_searchapi_chatgpt_research(query,limit=10,source=None,automatic=False,purpose='research'):
    source=source or searchapi_source('chatgpt')
    if source is None: raise RuntimeError('SearchAPI ChatGPT Research is not installed.')
    if provider_budget_remaining(source)<=0: raise RuntimeError('SearchAPI daily limit reached.')
    started=time.time(); data={}; size=0
    try:
        data,size=_searchapi_direct_request(source,'chatgpt',query,{'web_search':'true'},require_market=False)
        logged=_record_searchapi_chatgpt(source,started,query,data=data,size=size,automatic=automatic,purpose=purpose)
        return {**logged,'bytes':size}
    except Exception as exc:
        _record_searchapi_chatgpt(source,started,query,data=data,error=str(exc),size=size,automatic=automatic,purpose=purpose)
        raise


def searchapi_research(query,market=None,purpose='research',automatic=True,limit=8):
    """Sparingly perform AI-assisted public-web research.

    Direct OpenAI/Gemini/OpenRouter credentials always win for ordinary reasoning. This
    helper is only for tasks whose value comes from current public-web research/citations.
    """
    if automatic and _direct_cloud_ai_available():
        return {'ok':False,'skipped':'direct_cloud_preferred','results':[],'answer':''}
    if searchapi_ai_auto_allowed('chatgpt'):
        source=searchapi_source('chatgpt')
        try:
            result=search_searchapi_chatgpt_research(query,limit=limit,source=source,automatic=automatic,purpose=purpose)
            return {'ok':True,'service':'chatgpt',**result}
        except Exception as exc:
            last=str(exc)
    else:
        last='ChatGPT Research unavailable or at automatic limit.'
    if searchapi_ai_auto_allowed('ai_mode') and market is not None:
        source=searchapi_source('ai_mode'); started=time.time(); err=''
        try:
            rows,size=search_searchapi_google_ai_mode(query,limit,source=source,market=market)
            _record(source,started,len(rows),'',bytes_downloaded=size,usage_category='searchapi_ai_research',query=query,market=market,metadata_extra={'automatic':bool(automatic),'purpose':purpose})
            answer=str(rows[0].get('_searchapi_ai_answer') or '') if rows else ''
            return {'ok':True,'service':'ai_mode','results':rows,'answer':answer}
        except Exception as exc:
            err=str(exc); _record(source,started,0,err,usage_category='searchapi_ai_research',query=query,market=market,metadata_extra={'automatic':bool(automatic),'purpose':purpose})
            last=err
    return {'ok':False,'error':last,'results':[],'answer':''}


def search_duckduckgo(query,limit=10,market=None):
    r=_get(public_query_url('DuckDuckGo',query,limit,market),market=market); soup=BeautifulSoup(r.text,'html.parser'); out=[]
    for item in soup.select('.result'):
        a=item.select_one('.result__a'); sn=item.select_one('.result__snippet')
        if not a: continue
        href=a.get('href','')
        if href.startswith('//duckduckgo.com/l/?'):
            q=urllib.parse.parse_qs(urllib.parse.urlparse('https:'+href).query); href=(q.get('uddg') or [href])[0]
        out.append(_normalise_result(a.get_text(' ',strip=True),href,sn.get_text(' ',strip=True) if sn else ''))
        if len(out)>=limit: break
    return out,len(r.content)


def search_bing(query,limit=10,market=None):
    r=_get(public_query_url('Bing',query,limit,market),market=market); soup=BeautifulSoup(r.text,'html.parser'); out=[]
    for li in soup.select('li.b_algo'):
        a=li.select_one('h2 a'); p=li.select_one('.b_caption p')
        if a: out.append(_normalise_result(a.get_text(' ',strip=True),a.get('href',''),p.get_text(' ',strip=True) if p else ''))
    return out[:limit],len(r.content)


def _google_interstitial(response):
    final_url=str(getattr(response,'url','') or '').lower()
    text=str(getattr(response,'text','') or '').lower()[:120000]
    markers=('httpservice/retry/enablejs','please click [here]','please click here if you are not redirected','/sorry/','unusual traffic from your computer network')
    try: host=(urllib.parse.urlsplit(final_url).hostname or '').lower()
    except Exception: host=''
    return host in {'localhost','127.0.0.1'} or any(x in final_url or x in text for x in markers)


def _parse_google_public(response,limit):
    soup=BeautifulSoup(response.text,'html.parser'); out=[]; seen=set(); candidates=[]
    # Desktop/basic HTML and the Android client use several different wrappers. Prefer
    # heading-backed results, then fall back to external result anchors when Google
    # revises the wrapper class names.
    for div in soup.select('div.MjjYud, div.tF2Cxc, div.Gx5Zad, div.kCrYT, div[data-snhf]'):
        h=div.select_one('h3'); a=(h.find_parent('a') if h else None) or div.select_one('a[href]')
        if a and (h or len(a.get_text(' ',strip=True))>=12): candidates.append((a,h or a,div))
    for h in soup.select('h3'):
        a=h.find_parent('a')
        if a: candidates.append((a,h,h.find_parent('div') or h.parent))
    for a in soup.select('a[href^="/url?"], a[href^="http://"], a[href^="https://"]'):
        text=a.get_text(' ',strip=True)
        if len(text)>=12: candidates.append((a,a,a.find_parent('div') or a.parent))
    for a,h,container in candidates:
        href=a.get('href','')
        if href.startswith('/url?'):
            params=urllib.parse.parse_qs(urllib.parse.urlparse(href).query); href=(params.get('q') or params.get('url') or [href])[0]
        href=unwrap_search_result_url(href)
        low=href.lower()
        if 'httpservice/retry/enablejs' in low or 'localhost:8989' in low: continue
        if not href.startswith('http') or is_search_engine_url(href): continue
        can=href.split('#',1)[0]
        if can in seen: continue
        title=h.get_text(' ',strip=True) if h else a.get_text(' ',strip=True)
        if len(title)<4: continue
        seen.add(can)
        snippet=(container.get_text(' ',strip=True) if container else '')
        out.append(_normalise_result(title,href,snippet))
        if len(out)>=limit: break
    return out


def _google_public_request(url, timeout=18):
    """Fetch one Google result page with browser-like TLS and conservative pacing."""
    global _GOOGLE_PUBLIC_LAST_REQUEST
    with _GOOGLE_PUBLIC_LOCK:
        wait=_GOOGLE_PUBLIC_MIN_INTERVAL-(time.monotonic()-_GOOGLE_PUBLIC_LAST_REQUEST)
        if wait>0: time.sleep(wait)
        _GOOGLE_PUBLIC_LAST_REQUEST=time.monotonic()
    headers={
        'User-Agent':GOOGLE_PUBLIC_UA,
        'Accept-Language':'en-US,en;q=0.9',
        'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Cache-Control':'no-cache',
        'Pragma':'no-cache',
        'Upgrade-Insecure-Requests':'1',
        'Sec-Fetch-Dest':'document','Sec-Fetch-Mode':'navigate','Sec-Fetch-Site':'none','Sec-Fetch-User':'?1',
    }
    cookies={'CONSENT':'YES+cb','SOCS':'CAESHAgBEhIaAB'}
    if curl_requests is not None:
        # curl_cffi impersonates a current browser TLS/client fingerprint. Let it supply
        # the matching browser User-Agent instead of pairing a new TLS fingerprint with
        # ScoutBox's legacy static UA string.
        browser_headers=dict(headers); browser_headers.pop('User-Agent',None)
        return curl_requests.get(url,headers=browser_headers,cookies=cookies,timeout=timeout,allow_redirects=True,impersonate='chrome')
    return requests.get(url,headers=headers,cookies=cookies,timeout=timeout,allow_redirects=True)


def _google_public_cache_get(query,limit):
    key=(str(query or '').strip().lower(),int(limit))
    row=_GOOGLE_PUBLIC_CACHE.get(key)
    if not row: return None
    at,results,size=row
    if time.monotonic()-at>_GOOGLE_PUBLIC_CACHE_SECONDS:
        _GOOGLE_PUBLIC_CACHE.pop(key,None); return None
    return [dict(x) for x in results],size


def _google_public_cache_put(query,limit,results,size):
    key=(str(query or '').strip().lower(),int(limit))
    _GOOGLE_PUBLIC_CACHE[key]=(time.monotonic(),[dict(x) for x in results],int(size or 0))
    if len(_GOOGLE_PUBLIC_CACHE)>128:
        oldest=min(_GOOGLE_PUBLIC_CACHE,key=lambda k:_GOOGLE_PUBLIC_CACHE[k][0]); _GOOGLE_PUBLIC_CACHE.pop(oldest,None)


def search_google(query,limit=10,source=None,force_public=False,market=None):
    cap=provider_capability(source or 'Google')
    key=_provider_secret(source,cap) if source is not None else (os.getenv('GOOGLE_SEARCH_API_KEY','').strip())
    cx=_provider_extra(source,cap) if source is not None else (os.getenv('GOOGLE_SEARCH_CX','').strip())
    if key and cx and not force_public:
        r=requests.get('https://customsearch.googleapis.com/customsearch/v1',params={'key':key,'cx':cx,'q':query,'num':min(limit,10), **({'gl':market_search_meta(market).get('country_code','').lower()} if market_search_meta(market).get('country_code') else {})},timeout=15)
        r.raise_for_status(); data=r.json(); out=[]
        for item in data.get('items',[]) or []:
            out.append(_normalise_result(item.get('title',''),item.get('link',''),item.get('snippet','')))
        return out,len(r.content)
    if source is not None and not getattr(source,'public_fallback',True):
        raise RuntimeError('Google API key / Search Engine ID are not configured and public fallback is disabled')

    cached=_google_public_cache_get(query,limit)
    if cached is not None: return cached

    # Use one paced browser-fingerprint request rather than rapidly cycling many Google
    # domains. The old retry loop amplified 429 rate limits and often ended on /sorry/.
    encoded=urllib.parse.quote_plus(query); n=max(1,min(int(limit),100))
    configured=public_query_url(source or 'Google',query,limit,market)
    if configured:
        sep='&' if '?' in configured else '?'
        url=configured+sep+'gbv=1&nojs=1&filter=0&pws=0'
    else:
        meta=market_search_meta(market); gl=(('&gl='+meta['country_code'].lower()) if meta.get('country_code') else ''); url=f"https://www.google.com/search?q={encoded}&num={n}&hl={urllib.parse.quote_plus(meta.get('locale') or 'en-US')}{gl}&gbv=1&nojs=1&filter=0&pws=0"
    try:
        r=_google_public_request(url)
    except Exception as exc:
        raise RuntimeError(f'Google public search request failed: {exc}') from exc
    size=len(getattr(r,'content',b'') or b'')
    status=int(getattr(r,'status_code',0) or 0)
    final_url=str(getattr(r,'url','') or url)
    if status==429 or '/sorry/' in final_url.lower():
        raise RuntimeError('Google public search was rate-limited (HTTP 429). ScoutBox did not retry the blocked page and will try again on a later search.')
    if status>=400:
        raise RuntimeError(f'Google public search returned HTTP {status}.')
    if _google_interstitial(r):
        raise RuntimeError('Google returned an interstitial instead of search results. ScoutBox will try again on a later search.')
    out=_parse_google_public(r,limit)
    if not out:
        raise RuntimeError('Google public search returned no usable web results.')
    _google_public_cache_put(query,limit,out,size)
    return out,size

def search_yahoo(query,limit=10,market=None):
    r=_get(public_query_url('Yahoo Search',query,limit,market)); soup=BeautifulSoup(r.text,'html.parser'); out=[]
    for d in soup.select('div#web ol li, div.dd.algo'):
        a=d.select_one('h3 a')
        if a: out.append(_normalise_result(a.get_text(' ',strip=True),a.get('href',''),d.get_text(' ',strip=True)))
        if len(out)>=limit: break
    return out,len(r.content)


def search_brave(query,limit=10,source=None,force_public=False,market=None):
    key=_provider_secret(source,provider_capability(source or 'Brave Search')) if source is not None else os.getenv('BRAVE_SEARCH_API_KEY','').strip()
    if key and not force_public:
        r=requests.get('https://api.search.brave.com/res/v1/web/search',params={'q':query,'count':min(limit,20)},headers={'Accept':'application/json','X-Subscription-Token':key},timeout=15)
        r.raise_for_status(); data=r.json(); out=[]
        for item in (data.get('web') or {}).get('results',[]): out.append(_normalise_result(item.get('title',''),item.get('url',''),item.get('description','')))
        return out,len(r.content)
    if source is not None and not getattr(source,'public_fallback',True):
        raise RuntimeError('Brave API key is not configured and public fallback is disabled')
    r=_get(public_query_url(source or 'Brave Search',query,limit)); soup=BeautifulSoup(r.text,'html.parser'); out=[]; seen=set()
    candidates=[]
    for item in soup.select('.snippet, .result, [data-type="web"], [data-testid="web-result"]'):
        a=item.select_one('a[href]'); title=item.select_one('.title, h2, h3')
        if a: candidates.append((a,title,item))
    # Fallback for public markup revisions: use heading anchors while excluding
    # Brave navigation and search links.
    for title in soup.select('h2, h3'):
        a=title.find_parent('a') or title.select_one('a[href]')
        if a: candidates.append((a,title,title.find_parent('div') or title.parent))
    for a,title,item in candidates:
        href=unwrap_search_result_url(a.get('href',''))
        if not href.startswith('http') or is_search_engine_url(href): continue
        can=href.split('#',1)[0]
        if can in seen: continue
        seen.add(can)
        text=(title.get_text(' ',strip=True) if title else a.get_text(' ',strip=True))
        if not text: continue
        out.append(_normalise_result(text,href,item.get_text(' ',strip=True) if item else ''))
        if len(out)>=limit: break
    return out,len(r.content)


def search_mojeek(query,limit=10,source=None,force_public=False,market=None):
    key=_provider_secret(source,provider_capability(source or 'Mojeek')) if source is not None else os.getenv('MOJEEK_SEARCH_API_KEY','').strip()
    if key and not force_public:
        r=requests.get('https://www.mojeek.com/search',params={'api_key':key,'q':query,'t':min(limit,100),'fmt':'json'},timeout=15)
        r.raise_for_status(); data=r.json(); out=[]
        # Mojeek JSON payloads have used response.results / results across API revisions.
        rows=(data.get('response') or {}).get('results') if isinstance(data.get('response'),dict) else None
        rows=rows or data.get('results') or []
        for item in rows:
            out.append(_normalise_result(item.get('title',''),item.get('url') or item.get('link',''),item.get('desc') or item.get('description') or item.get('snippet','')))
        return out[:limit],len(r.content)
    if source is not None and not getattr(source,'public_fallback',True):
        raise RuntimeError('Mojeek API key is not configured and public fallback is disabled')
    r=_get(public_query_url(source or 'Mojeek',query,limit)); soup=BeautifulSoup(r.text,'html.parser'); out=[]
    for li in soup.select('ul.results-standard li, .results li'):
        a=li.select_one('a.title, h2 a')
        if a: out.append(_normalise_result(a.get_text(' ',strip=True),a.get('href',''),li.get_text(' ',strip=True)))
        if len(out)>=limit: break
    return out,len(r.content)



def _generic_public_search(url, selectors, limit=10):
    r=_get(url); soup=BeautifulSoup(r.text,'html.parser'); out=[]
    for container_sel, link_sel in selectors:
        for item in soup.select(container_sel):
            a=item.select_one(link_sel) if link_sel else (item if item.name=='a' else item.select_one('a[href]'))
            if not a: continue
            href=a.get('href','')
            if href.startswith('//'): href='https:'+href
            if not href.startswith('http'): continue
            title=a.get_text(' ',strip=True) or item.get_text(' ',strip=True)[:180]
            out.append(_normalise_result(title,href,item.get_text(' ',strip=True)))
            if len(out)>=limit: return out,len(r.content)
    return out,len(r.content)


def _naver_public_search(url, limit=10):
    r=_get(url); soup=BeautifulSoup(r.text,'html.parser'); out=[]; seen=set()
    containers=soup.select('.total_wrap, .api_subject_bx, .sc_new')
    for item in containers:
        anchors=item.select('a[href]')
        chosen=None
        for a in anchors:
            href=str(a.get('href') or '').strip()
            if href.startswith('//'): href='https:'+href
            if not href.startswith(('http://','https://')): continue
            host=(urllib.parse.urlsplit(href).netloc or '').casefold()
            if host.endswith('naver.com') or host.endswith('naver.net'): continue
            text=' '.join(a.get_text(' ',strip=True).split())
            score=0
            if text: score+=1
            if _ROLE_TITLE_HINT.search(text): score+=4
            if search_title_contaminated(text,'Naver'): score-=4
            if ' › ' in text: score-=3
            candidate=(score,a,href)
            if chosen is None or candidate[0]>chosen[0]: chosen=candidate
        if not chosen: continue
        _,a,href=chosen
        can=href.split('#',1)[0]
        if can in seen: continue
        seen.add(can)
        item_text=item.get_text(' ',strip=True)
        title=_clean_naver_result_title(a.get_text(' ',strip=True),item_text)
        if not title: continue
        out.append(_normalise_result(title,href,item_text))
        if len(out)>=limit: break
    return out,len(r.content)


def search_startpage(query,limit=10,market=None):
    return _generic_public_search(public_query_url('Startpage',query,limit,market), [('.w-gl__result','a.w-gl__result-title'),('.result','a[href]')], limit)

def search_ecosia(query,limit=10,market=None):
    return _generic_public_search(public_query_url('Ecosia',query,limit,market), [('.result','a.result__link'),('.result','a[href]')], limit)

def search_yandex(query,limit=10,source=None,force_public=False,market=None):
    access=provider_access_type(source,provider_capability(source or 'Yandex')) if source is not None else ('yandex_api_key' if os.getenv('YANDEX_SEARCH_API_KEY') else 'public')
    if access!='public' and not force_public:
        secret,folder_id=_access_credentials(source,access,provider_capability(source or 'Yandex')) if source is not None else (
            (os.getenv('YANDEX_SEARCH_API_KEY','') if access=='yandex_api_key' else os.getenv('YANDEX_SEARCH_IAM_TOKEN','')).strip(),
            os.getenv('YANDEX_SEARCH_FOLDER_ID','').strip(),
        )
        if secret and folder_id:
            headers={'Content-Type':'application/json','User-Agent':UA}
            headers['Authorization']=('Api-Key ' if access=='yandex_api_key' else 'Bearer ')+secret
            payload={
                'query':{'searchType':'SEARCH_TYPE_COM','queryText':query},
                'sortSpec':{'sortMode':'SORT_MODE_BY_RELEVANCE','sortOrder':'SORT_ORDER_DESC'},
                'groupSpec':{'groupMode':'GROUP_MODE_DEEP','groupsOnPage':min(max(1,int(limit)),10),'docsInGroup':1},
                'maxPassages':2,'l10n':'LOCALIZATION_EN','folderId':folder_id,
            }
            r=requests.post('https://searchapi.api.cloud.yandex.net/v2/web/search',json=payload,headers=headers,timeout=20)
            r.raise_for_status(); data=r.json(); encoded=data.get('rawData') or data.get('raw_data') or ''
            if not encoded: raise RuntimeError('Yandex Search API returned no rawData payload')
            raw=base64.b64decode(encoded).decode('utf-8','ignore'); soup=BeautifulSoup(raw,'xml'); out=[]
            for doc in soup.find_all('doc'):
                url=(doc.find('url').get_text(' ',strip=True) if doc.find('url') else '')
                title=(doc.find('title').get_text(' ',strip=True) if doc.find('title') else '')
                passages=' '.join(x.get_text(' ',strip=True) for x in doc.find_all('passage'))
                out.append(_normalise_result(title,url,passages))
                if len(out)>=limit: break
            return out,len(r.content)
        if source is not None and not getattr(source,'public_fallback',True):
            raise RuntimeError('Yandex credentials require both a credential and Yandex Cloud folder ID; public fallback is disabled')
    return _generic_public_search(public_query_url(source or 'Yandex',query,limit), [('.serp-item','a.Link_theme_normal'),('.Organic','a[href]')], limit)

def search_baidu(query,limit=10,source=None,force_public=False,market=None):
    access=provider_access_type(source,provider_capability(source or 'Baidu')) if source is not None else ('baidu_qianfan' if os.getenv('BAIDU_SEARCH_API_KEY') else 'public')
    if access=='baidu_qianfan' and not force_public:
        key,_=_access_credentials(source,access,provider_capability(source or 'Baidu')) if source is not None else (os.getenv('BAIDU_SEARCH_API_KEY','').strip(),'')
        if key:
            payload={'messages':[{'role':'user','content':query}],'search_source':'baidu_search_v2','resource_type_filter':[{'type':'web','top_k':min(max(1,int(limit)),50)}]}
            r=requests.post('https://qianfan.baidubce.com/v2/ai_search/web_search',json=payload,headers={'Authorization':f'Bearer {key}','Content-Type':'application/json','User-Agent':UA},timeout=20)
            r.raise_for_status(); data=r.json(); out=[]
            for item in data.get('references',[]) or []:
                if item.get('type') not in (None,'','web'): continue
                out.append(_normalise_result(item.get('title',''),item.get('url',''),item.get('snippet') or item.get('content','')))
                if len(out)>=limit: break
            return out,len(r.content)
        if source is not None and not getattr(source,'public_fallback',True):
            raise RuntimeError('Baidu Qianfan API key is not configured and public fallback is disabled')
    return _generic_public_search(public_query_url(source or 'Baidu',query,limit), [('div.result','h3 a'),('div.c-container','h3 a')], limit)

def search_naver(query,limit=10,source=None,force_public=False,market=None):
    cap=provider_capability(source or 'Naver')
    access=provider_access_type(source,cap) if source is not None else ('naver_hub' if os.getenv('NAVER_API_HUB_CLIENT_SECRET') else ('naver_legacy' if os.getenv('NAVER_SEARCH_CLIENT_SECRET') else 'public'))
    if access!='public' and not force_public:
        secret,client_id=_access_credentials(source,access,cap) if source is not None else (
            (os.getenv('NAVER_API_HUB_CLIENT_SECRET','') if access=='naver_hub' else os.getenv('NAVER_SEARCH_CLIENT_SECRET','')).strip(),
            (os.getenv('NAVER_API_HUB_CLIENT_ID','') if access=='naver_hub' else os.getenv('NAVER_SEARCH_CLIENT_ID','')).strip(),
        )
    else:
        secret=client_id=''
    if secret and client_id and not force_public:
        if access=='naver_hub':
            endpoint='https://naverapihub.apigw.ntruss.com/search/v1/webkr'
            headers={'X-NCP-APIGW-API-KEY-ID':client_id,'X-NCP-APIGW-API-KEY':secret,'User-Agent':UA}
            params={'query':query,'display':min(limit,100),'start':1,'format':'json'}
        else:
            endpoint='https://openapi.naver.com/v1/search/webkr.json'
            headers={'X-Naver-Client-Id':client_id,'X-Naver-Client-Secret':secret,'User-Agent':UA}
            params={'query':query,'display':min(limit,100),'start':1}
        r=requests.get(endpoint,params=params,headers=headers,timeout=15)
        r.raise_for_status(); data=r.json(); out=[]
        for item in data.get('items',[]) or []:
            title=BeautifulSoup(item.get('title',''),'html.parser').get_text(' ',strip=True)
            desc=BeautifulSoup(item.get('description',''),'html.parser').get_text(' ',strip=True)
            out.append(_normalise_result(title,item.get('link',''),desc))
        return out[:limit],len(r.content)
    if access!='public' and source is not None and not getattr(source,'public_fallback',True):
        raise RuntimeError('Naver Client ID / Client Secret are not configured and public fallback is disabled')
    return _naver_public_search(public_query_url(source or 'Naver',query,limit),limit)

def search_source(source,query,limit=10,usage_category='search',ignore_budget=False,market=None,query_language='English'):
    try:
        from .cloud_budget import usage_context
        if str(usage_context().get('discovery_mode') or '').lower()=='cloud_web':
            raise RuntimeError('Cloud Web routing violation: local search-engine discovery is not permitted for this campaign run.')
    except ImportError:
        pass
    # SearchAPI has no public fallback. An enabled checkbox without a stored/environment
    # credential is configuration state, not a provider request: skip it before pacing,
    # quota accounting, network dispatch, or Search Activity telemetry.
    if str(getattr(source,'name','') or '').startswith('SearchAPI ·'):
        try:
            if not provider_credential_state(source).get('api_configured'):
                return [],'SearchAPI is not configured.'
        except Exception:
            return [],'SearchAPI is not configured.'
    # ScoutBox must never send multiple site: scopes in one provider request. Split
    # first, then run the normal sanitizer/deduper on each actual dispatched query so
    # Search Activity records only single-site searches.
    try:
        from .query_normalizer import split_multi_site_search_queries
        split_queries=split_multi_site_search_queries(query)
    except Exception:
        split_queries=[str(query or '').strip()]
    if len(split_queries)>1:
        combined=[]; errors=[]; seen_urls=set(); started_all=time.time()
        for sq in split_queries:
            rows,err=search_source(source,sq,limit=limit,usage_category=usage_category,ignore_budget=ignore_budget,market=market,query_language=query_language)
            if err:
                errors.append(err)
                continue
            for item in rows:
                key=str(item.get('url') or item.get('link') or '').strip().lower()
                if key and key in seen_urls:
                    continue
                if key:
                    seen_urls.add(key)
                combined.append(item)
                if len(combined)>=limit:
                    break
            if len(combined)>=limit:
                break
        if combined:
            return combined[:limit],''
        return [],'; '.join(dict.fromkeys(errors)) if errors else ''
    query=split_queries[0] if split_queries else ''
    # Never send unary '-' exclusions to public engines; ScoutBox filters after retrieval.
    try:
        from .queryplanner import sanitize_local_search_engine_query
        query=sanitize_local_search_engine_query(query)
    except Exception:
        query=re.sub(r'(?<!\S)-(?:(?:"[^"]+")|(?:\'[^\']+\')|(?:[^\s]+))',' ',str(query or ''))
        parts=[]; seen_site=False
        for token in re.findall(r'"[^"\n]*"|site:[^\s]+|[^\s]+', query, flags=re.I):
            if token.lower().startswith('site:'):
                if seen_site:
                    continue
                value=re.sub(r'^https?://','',token[5:].strip().strip('"\''),flags=re.I)
                host=value.split('/',1)[0].split('?',1)[0].split('#',1)[0].split(':',1)[0].lower().removeprefix('www.')
                if not host:
                    continue
                token='site:'+host; seen_site=True
            parts.append(token)
        query=re.sub(r'\s+',' ',' '.join(parts)).strip()
    try:
        from .query_normalizer import normalize_generated_search_query
        query=normalize_generated_search_query(query)
    except Exception:
        query=re.sub(r'\s+',' ',str(query or '')).strip()
    started=time.time(); out=[]; err=''; size=0
    if not ignore_budget and provider_budget_remaining(source)<=0: return [],'daily provider request budget reached'
    waited=_wait_for_provider_pacing(source)
    if waited:
        try:
            UsageMetric.objects.create(category='search_provider_pacing',provider=source.name,stage='wait',requests=0,pages=0,metadata=usage_metadata({'waited_seconds':round(waited,2),'query':query[:300]}))
        except Exception:
            pass
    try:
        if source.name=='DuckDuckGo': out,size=search_duckduckgo(query,limit,market=market)
        elif source.name=='Bing': out,size=search_bing(query,limit,market=market)
        elif source.name=='Google': out,size=search_google(query,limit,source=source,market=market)
        elif source.name=='Yahoo Search': out,size=search_yahoo(query,limit,market=market)
        elif source.name=='Brave Search': out,size=search_brave(query,limit,source=source,market=market)
        elif source.name=='Mojeek': out,size=search_mojeek(query,limit,source=source,market=market)
        elif source.name=='Startpage': out,size=search_startpage(query,limit,market=market)
        elif source.name=='Ecosia': out,size=search_ecosia(query,limit,market=market)
        elif source.name=='Yandex': out,size=search_yandex(query,limit,source=source,market=market)
        elif source.name=='Baidu': out,size=search_baidu(query,limit,source=source,market=market)
        elif source.name=='Naver': out,size=search_naver(query,limit,source=source,market=market)
        elif source.name=='SearchAPI · Google Jobs': out,size=search_searchapi_google_jobs(query,limit,source=source,market=market)
        elif source.name=='SearchAPI · Google Web': out,size=search_searchapi_google_web(query,limit,source=source,market=market)
        elif source.name=='SearchAPI · Google Forums': out,size=search_searchapi_google_forums(query,limit,source=source,market=market)
        elif source.name=='SearchAPI · Google News': out,size=search_searchapi_google_news(query,limit,source=source,market=market)
        elif source.name=='SearchAPI · Google AI Mode': out,size=search_searchapi_google_ai_mode(query,limit,source=source,market=market)
        elif source.name=='SearchAPI · Google Local': out,size=search_searchapi_google_local(query,limit,source=source,market=market)
        elif source.name=='SearchAPI · ChatGPT Research': return [],'SearchAPI ChatGPT Research is an AI research service; use the dedicated research route.'
        else:
            return [],'No v1 query adapter for this preset; it is used as a target domain/source hint.'
    except Exception as e: err=str(e)
    # Never allow an unresolved provider tracking/search URL into discovery records.
    if not err:
        cleaned=[]
        for item in out:
            item=dict(item); item['url']=unwrap_search_result_url(item.get('url',''))
            if item.get('url','').startswith(('http://','https://')) and not is_search_engine_url(item['url']): cleaned.append(item)
        out=cleaned
    _record(source,started,len(out),err,bytes_downloaded=size,usage_category=usage_category,query=query,market=market,query_language=query_language)
    return ([],err) if err else (out,'')



def test_search_provider(source, query='ScoutBox test', force_public=False, limit=5):
    """Run the real adapter and return parsed result rows for UI inspection.

    SearchAPI tests are real billable/provider requests, count toward the shared SearchAPI
    daily limit, and are logged in the same place as normal activity. ChatGPT is the sole
    exception: its attempts are logged as Cloud AI Requests rather than Search Activity.
    """
    state=provider_credential_state(source)
    query=(query or 'ScoutBox test').strip()[:4000]
    # A missing SearchAPI credential is not an attempted search. Return the UI preflight
    # message without creating Search Activity / AI Request telemetry or consuming quota.
    if str(getattr(source,'name','') or '').startswith('SearchAPI ·') and not state.get('api_configured'):
        return {'ok':False,'message':'SearchAPI API key is not configured. Save the API key before testing.','mode':'Not configured','query':query,'results':[]}
    started=time.time()
    try:
        from .queryplanner import sanitize_local_search_engine_query
        if source.name not in {'SearchAPI · ChatGPT Research','SearchAPI · Google AI Mode'}: query=sanitize_local_search_engine_query(query)
    except Exception:
        pass
    try:
        test_market=None
        if source.name.startswith('SearchAPI ·'):
            if provider_budget_remaining(source)<=0:
                raise RuntimeError('SearchAPI daily limit reached.')
            cfg=PortalSettings.objects.get_or_create(pk=1)[0]
            test_market=next((m for m in enabled_markets(cfg) if m.code!='worldwide'),MARKET_BY_CODE.get('gb'))
            if source.name=='SearchAPI · ChatGPT Research':
                result=search_searchapi_chatgpt_research(query,limit=limit,source=source,automatic=False,purpose='provider_test')
                return {'ok':True,'message':f'{source.name} returned {len(result.get("results") or [])} cited source(s).','mode':'Cloud Runtime','query':query,'results':(result.get('results') or [])[:limit],'answer':result.get('answer',''),'model':result.get('model','searchapi-chatgpt'),'latency_ms':result.get('latency_ms',0),'bytes':result.get('bytes',0)}
            if source.name=='SearchAPI · Google Jobs': results,size=search_searchapi_google_jobs(query,limit,source=source,market=test_market)
            elif source.name=='SearchAPI · Google Web': results,size=search_searchapi_google_web(query,limit,source=source,market=test_market)
            elif source.name=='SearchAPI · Google Forums': results,size=search_searchapi_google_forums(query,limit,source=source,market=test_market)
            elif source.name=='SearchAPI · Google News': results,size=search_searchapi_google_news(query,limit,source=source,market=test_market)
            elif source.name=='SearchAPI · Google AI Mode': results,size=search_searchapi_google_ai_mode(query,limit,source=source,market=test_market)
            elif source.name=='SearchAPI · Google Local': results,size=search_searchapi_google_local(query,limit,source=source,market=test_market)
            else: raise RuntimeError('Unknown SearchAPI service.')
            _record(source,started,len(results),'',bytes_downloaded=size,usage_category='searchapi_test',query=query,market=test_market,metadata_extra={'manual_test':True})
            answer=str(results[0].get('_searchapi_ai_answer') or '') if source.name=='SearchAPI · Google AI Mode' and results else ''
            return {'ok':True,'message':f'{source.name} returned {len(results)} parsed result(s).','mode':'API','query':query,'results':results[:limit],'answer':answer,'latency_ms':int((time.time()-started)*1000),'bytes':size}

        if source.name=='Google': results,size=search_google(query,limit,source=source,force_public=force_public)
        elif source.name=='Brave Search': results,size=search_brave(query,limit,source=source,force_public=force_public)
        elif source.name=='DuckDuckGo': results,size=search_duckduckgo(query,limit)
        elif source.name=='Bing': results,size=search_bing(query,limit)
        elif source.name=='Yahoo Search': results,size=search_yahoo(query,limit)
        elif source.name=='Mojeek': results,size=search_mojeek(query,limit,source=source,force_public=force_public)
        elif source.name=='Startpage': results,size=search_startpage(query,limit)
        elif source.name=='Ecosia': results,size=search_ecosia(query,limit)
        elif source.name=='Yandex': results,size=search_yandex(query,limit,source=source,force_public=force_public)
        elif source.name=='Baidu': results,size=search_baidu(query,limit,source=source,force_public=force_public)
        elif source.name=='Naver': results,size=search_naver(query,limit,source=source,force_public=force_public)
        else: return {'ok':False,'message':'This source is a discovery target/preset, not a direct search engine.','mode':'Preset','results':[]}
        mode='Public search' if force_public or not state.get('api_configured') else state.get('mode','API')
        extra={}
        if not results and source.name!='Google': extra=public_raw_preview(source,query,limit)
        return {'ok':True,'message':f'{source.name} returned {len(results)} parsed result(s).','mode':mode,'query':query,'results':results[:limit],'latency_ms':int((time.time()-started)*1000),'bytes':size,**extra}
    except Exception as exc:
        if source.name.startswith('SearchAPI ·') and source.name!='SearchAPI · ChatGPT Research':
            try: _record(source,started,0,str(exc),usage_category='searchapi_test',query=query,market=test_market,metadata_extra={'manual_test':True})
            except Exception: pass
        extra={}
        if not source.name.startswith('SearchAPI ·') and source.name!='Google' and (force_public or not state.get('api_configured') or provider_capability(source).get('public_fallback')):
            try: extra=public_raw_preview(source,query,limit)
            except Exception: extra={}
        return {'ok':False,'message':str(exc),'mode':('Cloud Runtime' if source.name=='SearchAPI · ChatGPT Research' else ('Public search' if force_public else state.get('mode',''))),'query':query,'results':[],'latency_ms':int((time.time()-started)*1000),**extra}

def _split(v,limit=None):
    out=[x.strip() for x in re.split('[,\n;|]+',v or '') if x.strip()]
    return out[:limit] if limit else out


def enabled_target_domains(limit=8):
    domains=[]
    # User-managed domains are explicit high-value targets and therefore come first.
    for row in CustomSearchDomain.objects.filter(enabled=True).order_by('name','domain'):
        d=str(row.domain or '').strip().lower()
        d=re.sub(r'^https?://','',d).split('/',1)[0].split(':',1)[0].removeprefix('www.')
        if d and d not in domains: domains.append(d)
        if len(domains)>=limit: return domains
    qs=list(SearchSource.objects.filter(enabled=True).exclude(source_type='cloud_ai').exclude(source_type='forum').exclude(name__in=PROVIDER_NAMES).exclude(base_url=''))
    preferred=['GitHub','Hacker News','Reddit','Facebook public posts','LinkedIn Jobs','Indeed','Wellfound','Remote OK','Greenhouse','Lever','MyCareersFuture','SEEK']
    order={name:i for i,name in enumerate(preferred)}
    qs.sort(key=lambda s:(order.get(s.name,999),-s.priority,s.name.lower()))
    for source in qs:
        # Local AI Discovery treats direct acquisition and configured search-engine
        # discovery as additive. Cloud Web never executes this provider path.
        try: d=urllib.parse.urlparse(source.base_url).netloc.lower().removeprefix('www.')
        except Exception: continue
        if d and d not in domains and not d.endswith('example.invalid'): domains.append(d)
        if len(domains)>=limit: break
    return domains


def build_campaign_query_plan(campaign,max_queries=12,rotation_offset=0):
    """Build the Local AI Discovery query plan with explicit configured-source targeting."""
    cfg=PortalSettings.objects.get_or_create(pk=1)[0]
    target_domains=[]; custom_domains=[]; target_sources=[]
    # Every enabled Custom Domain is an explicit operator target and must be searched.
    for row in CustomSearchDomain.objects.filter(enabled=True).order_by('name','domain'):
        d=re.sub(r'^https?://','',str(row.domain or '').strip().lower()).split('/',1)[0].split(':',1)[0].removeprefix('www.')
        if d and d not in custom_domains: custom_domains.append(d)
        if d and d not in target_domains: target_domains.append(d)
    # Campaign-selected built-in sources are also targeted with site:. When no explicit
    # campaign list exists, rotate across enabled non-provider source identities.  Keep
    # identity metadata alongside the base domain so the query planner can schedule one
    # fair source slot before choosing any country/domain variant.
    if campaign.source_names:
        selected=SearchSource.objects.filter(enabled=True,name__in=campaign.source_names).exclude(source_type='cloud_ai').exclude(source_type='forum').exclude(name__in=PROVIDER_NAMES).order_by('-priority','category','name')
    else:
        selected=SearchSource.objects.filter(enabled=True).exclude(source_type='cloud_ai').exclude(source_type='forum').exclude(name__in=PROVIDER_NAMES).exclude(base_url='').order_by('-priority','category','name')
    for source in selected:
        # Local AI Discovery always keeps the search-engine path even when this source
        # also has a direct API/feed/page adapter. Cloud Web bypasses this planner.
        try: d=urllib.parse.urlparse(source.base_url).netloc.lower().removeprefix('www.')
        except Exception: d=''
        if not d or d.endswith('example.invalid'):
            continue
        if d not in target_domains: target_domains.append(d)
        target_sources.append({'source_id':source.pk,'source_name':source.name,'domain':d})
    return build_source_guided_query_plan(
        campaign,max_queries=max_queries,target_domains=target_domains,custom_domains=custom_domains,target_sources=target_sources,
        interval_minutes=_setting_int(cfg,'scraper_interval_minutes',120,minimum=30),rotation_offset=rotation_offset,
    )


def build_campaign_queries(campaign,max_queries=12):
    return [x['query'] for x in build_campaign_query_plan(campaign,max_queries=max_queries)['queries']]

def facebook_index_queries(base_query):
    # Use host-only site: constraints. Path-scoped operators such as
    # Facebook post-path site operators are brittle and often over-constrain search providers;
    # ScoutBox validates Page/post relevance after retrieval instead.
    return [
        f'site:facebook.com {base_query}',
        f'site:facebook.com {base_query} "hiring"',
        f'site:facebook.com {base_query} "remote"',
    ]



_FACEBOOK_WATCH_RELEVANCE=re.compile(r'(?i)\b(careers?|jobs?|hiring|vacanc(?:y|ies)|recruit(?:ing|ment)|talent acquisition|join (?:our|the) team|open roles?|job openings?|work with us|engineering careers?)\b')
_FACEBOOK_WATCH_TECH_RELEVANCE=re.compile(r'(?i)\b(software|firmware|embedded|security|engineering|developer|technical|linux|systems?)\b')
_FACEBOOK_WATCH_NOISE=re.compile(r'(?i)\b(download facebook|messenger|breakfast|cartoon|festival|news|police|grenade|mother.s day|facebook$|dating|entertainment|celebrity|sports news)\b')
_FACEBOOK_SYSTEM_SLUGS={'facebook','reg','dating','android_upgrade','messenger','login','help','watch','marketplace','gaming','groups','events'}
_FACEBOOK_TITLE_SUFFIX_RE=re.compile(r'(?i)\s*(?:[-|·]\s*)?(?:facebook(?:\s*[-|·].*)?|www\.facebook\.com.*|새\s*창\s*열림|keep에\s*저장|keep에\s*바로가기)\s*$')


def _clean_facebook_page_title(value):
    text=' '.join(str(value or '').replace('\xa0',' ').split()).strip()
    # Search engines sometimes prepend breadcrumb chrome before the actual Page name.
    text=re.sub(r'(?i)^facebook\s+www\.facebook\.com\s*[›>·|-]\s*','',text)
    text=re.sub(r'\s*[›>]\s*새\s*창\s*열림\s*$','',text)
    for _ in range(3):
        cleaned=_FACEBOOK_TITLE_SUFFIX_RE.sub('',text).strip(' -|·›>')
        if cleaned==text: break
        text=cleaned
    # A mixed Latin + stray script title should keep the Latin Page name only.
    text=re.sub(r'[\u1100-\u11ff\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\u1780-\u17ff]+',' ',text)
    text=re.sub(r'\s{2,}',' ',text).strip(' -|·›>')
    return text[:300]


def _facebook_payload_from_html(html, final_url=''):
    soup=BeautifulSoup(html or '','html.parser')
    og=soup.find('meta',attrs={'property':'og:title'}) or soup.find('meta',attrs={'name':'og:title'})
    desc=soup.find('meta',attrs={'property':'og:description'}) or soup.find('meta',attrs={'name':'description'})
    h1=soup.find('h1')
    browser_title=' '.join((soup.title.get_text(' ',strip=True) if soup.title else '').split())[:300]
    raw_title=(og.get('content') if og and og.get('content') else (h1.get_text(' ',strip=True) if h1 else browser_title))
    title=_clean_facebook_page_title(raw_title)
    meta_desc=' '.join(str(desc.get('content') if desc and desc.get('content') else '').split())[:2000]
    for bad in soup(['script','style','noscript','svg','nav','header','footer','form']):
        bad.decompose()
    main=soup.find('main') or soup.find(attrs={'role':'main'}) or soup.body or soup
    body=' '.join(main.stripped_strings)[:22000]
    owned=' '.join(x for x in (title,meta_desc,body) if x).strip()
    return {'url':final_url,'title':title,'browser_title':browser_title,'description':meta_desc,'text':owned[:25000]}


def _facebook_identity_key(value):
    return re.sub(r'[^a-z0-9]+','',str(value or '').casefold())


_FACEBOOK_POST_TITLE_RE=re.compile(r'''(?ix)\b(
    are\s+you\s+looking|looking\s+for\s+(?:a\s+)?career|career\s+change|we(?:'re|\s+are)\s+hiring|
    now\s+hiring|join\s+(?:our|the)\s+team|current\s+open\s+positions?|apply\s+(?:now|today)|
    vacancy\s+(?:alert|announcement)|job\s+(?:alert|opening|opportunity)|hiring\s+(?:now|alert)
)\b''')
_FACEBOOK_REGION_SUFFIXES={
    'NA':'North America',
}


def _facebook_page_id_display(page_id):
    raw=urllib.parse.unquote(str(page_id or '')).strip().strip('/')
    if not raw or raw.casefold() in _FACEBOOK_SYSTEM_SLUGS or raw.isdigit():
        return ''
    text=re.sub(r'[_\-.]+',' ',raw)
    # Facebook vanity IDs often preserve the Page's words as CamelCase.  Split those
    # boundaries before cleaning so a stable Page identity is preferable to a post title.
    text=re.sub(r'(?<=[a-z0-9])(?=[A-Z])',' ',text)
    text=re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])',' ',text)
    parts=[x for x in text.split() if x]
    if parts and parts[-1].upper() in _FACEBOOK_REGION_SUFFIXES:
        parts[-1]=_FACEBOOK_REGION_SUFFIXES[parts[-1].upper()]
    text=' '.join(parts).strip()
    return _clean_facebook_page_title(text) if re.search(r'[A-Za-z]',text) else ''


def _facebook_title_looks_like_post(value):
    text=_clean_facebook_page_title(value)
    if not text:
        return False
    return bool(_FACEBOOK_POST_TITLE_RE.search(text) or ('?' in text and len(text)>45) or ('!' in text and len(text)>55))


def _facebook_title_matches_page_id(value, page_id=''):
    title=_clean_facebook_page_title(value)
    if not title or _facebook_title_looks_like_post(title):
        return False
    title_key=_facebook_identity_key(title)
    raw_key=_facebook_identity_key(page_id)
    display_key=_facebook_identity_key(_facebook_page_id_display(page_id))
    for key in (raw_key,display_key):
        if not key or len(key)<3:
            continue
        if title_key==key:
            return True
        shorter=min(len(title_key),len(key)); longer=max(len(title_key),len(key))
        if shorter>=5 and shorter/longer>=0.72 and (title_key in key or key in title_key):
            return True
    return False


def _facebook_identity_from_evidence(evidence_text, page_id=''):
    """Recover only evidence fragments that match the known Facebook Page identity."""
    text=' '.join(str(evidence_text or '').replace('**',' ').replace('__',' ').split()).strip()
    if not text:
        return ''
    page_key=_facebook_identity_key(page_id)
    if not page_key:
        return ''
    candidates=[]
    for part in re.split(r'\s+(?:[-–—|·›])\s+',text[:1200]):
        candidate=_clean_facebook_page_title(part.strip(' .:-'))
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    for candidate in candidates[:12]:
        key=_facebook_identity_key(candidate)
        if len(key)>=3 and (key==page_key or key in page_key or page_key in key):
            return candidate
    return ''


def facebook_page_identity_title(url, title='', evidence_text='', page_id='', *, direct=True):
    """Resolve Page identity independently from hiring/relevance validation.

    Facebook may block direct fetching even when ScoutBox already knows the Page identity.
    Title repair therefore prefers direct Page metadata, then a retained indexed identity that
    matches the Page ID, and finally a non-numeric Page ID.  It never accepts an arbitrary
    hiring/search snippet merely to fill the title column.
    """
    direct_available=False
    direct_title=''
    if direct:
        data,_err=facebook_authenticated_fetch(url)
        if data:
            direct_available=bool(data.get('text') or data.get('title') or data.get('identity_title'))
            direct_title=_clean_facebook_page_title(data.get('identity_title') or data.get('title') or '')
        else:
            try:
                r=_get(url,allow_redirects=True)
                payload=_facebook_payload_from_html(r.text,r.url)
                direct_available=bool(payload.get('text') or payload.get('title'))
                direct_title=_clean_facebook_page_title(payload.get('title') or '')
            except Exception:
                direct_available=False
                direct_title=''
    if direct_title and not _FACEBOOK_WATCH_NOISE.search(direct_title):
        return {'title':direct_title[:300],'source':'direct','direct_available':direct_available}
    seeded=_clean_facebook_page_title(title)
    # Indexed search titles frequently describe the individual post rather than the Page.
    # Reuse a stored/indexed title only when it actually matches the known vanity Page ID.
    if seeded and _facebook_title_matches_page_id(seeded,page_id) and not _FACEBOOK_WATCH_NOISE.search(seeded):
        return {'title':seeded[:300],'source':'stored','direct_available':direct_available}
    evidenced=_facebook_identity_from_evidence(evidence_text,page_id)
    if evidenced and not _FACEBOOK_WATCH_NOISE.search(evidenced):
        return {'title':evidenced[:300],'source':'indexed','direct_available':direct_available}
    page_label=_facebook_page_id_display(page_id)
    if page_label and not _FACEBOOK_WATCH_NOISE.search(page_label):
        return {'title':page_label[:300],'source':'page_id','direct_available':direct_available}
    return {'title':'','source':'','direct_available':direct_available}


def facebook_page_relevant(url, title='', evidence_text='', *, direct=True):
    """Require strong Page-owned hiring evidence before a Page enters Pages to Watch.

    Search snippets only identify a candidate Page. Facebook navigation/recommendation chrome
    must not qualify a random profile, so direct metadata/main-content evidence is required.
    """
    seed=' '.join((str(title or '')+' '+str(evidence_text or '')).split())[:12000]
    clean_seed_title=_clean_facebook_page_title(title)
    try:
        page_id=(urllib.parse.urlparse(url).path.strip('/').split('/',1)[0] or '')
        slug=page_id.casefold()
    except Exception:
        page_id=''; slug=''
    if slug in _FACEBOOK_SYSTEM_SLUGS:
        return False, 'Facebook system/non-Page slug', '', clean_seed_title
    if _FACEBOOK_WATCH_NOISE.search(clean_seed_title or seed[:500]):
        return False, 'obvious non-career/noise content', '', clean_seed_title
    direct_text=''; direct_title=''; direct_browser_title=''
    if direct:
        data,err=facebook_authenticated_fetch(url)
        if data:
            direct_text=str(data.get('text') or '')[:25000]; direct_title=_clean_facebook_page_title(data.get('identity_title') or data.get('title') or ''); direct_browser_title=str(data.get('browser_title') or data.get('title') or '').strip()[:300]
        else:
            try:
                r=_get(url,allow_redirects=True)
                payload=_facebook_payload_from_html(r.text,r.url)
                direct_text=payload['text']; direct_title=payload['title']; direct_browser_title=str(payload.get('browser_title') or payload.get('title') or '').strip()[:300]
            except Exception:
                direct_text=''; direct_title=''; direct_browser_title=''
        try:
            UsageMetric.objects.create(category='direct_site',provider='Facebook',stage='facebook_page_validation',requests=1,pages=1 if direct_text else 0,errors=0 if direct_text else 1,metadata={'url':url[:1000],'title':str(title or '')[:300]})
        except Exception: pass
    if direct and not direct_text:
        # Direct Facebook fetches are frequently blocked. Do not let that preserve legacy
        # junk forever: strong indexed title/snippet evidence can qualify a Page, while
        # weak/noisy legacy rows remain unverified and can be removed by revalidation.
        indexed=' '.join((clean_seed_title,seed)).strip()
        career_hits={m.group(0).casefold() for m in _FACEBOOK_WATCH_RELEVANCE.finditer(indexed)}
        tech=bool(_FACEBOOK_WATCH_TECH_RELEVANCE.search(indexed))
        title_career=bool(_FACEBOOK_WATCH_RELEVANCE.search(clean_seed_title))
        # Facebook blocking/rate limiting is validation unavailable, never implicit acceptance.
        # Only clean indexed identity + explicit career/hiring title evidence may be used as fallback.
        identity_ok=bool(clean_seed_title and clean_seed_title.casefold() not in _FACEBOOK_SYSTEM_SLUGS and len(clean_seed_title)>=3)
        if identity_ok and title_career and not _FACEBOOK_WATCH_NOISE.search(indexed[:1500]):
            identity=facebook_page_identity_title(url,clean_seed_title,evidence_text,page_id,direct=False).get('title','')
            if not identity:
                return False, 'validation unavailable; indexed hiring evidence did not establish a stable Page identity', '', ''
            return True, 'indexed hiring evidence + stable Page identity; direct validation unavailable', '', identity
        return False, 'validation unavailable; indexed evidence is insufficient for Page identity + hiring relevance', '', clean_seed_title
    combined=' '.join((direct_title+' '+direct_text) if direct else (clean_seed_title+' '+seed)).strip()
    if not combined:
        return False, 'no Page-owned content', direct_text, direct_browser_title or direct_title or clean_seed_title
    # Strong qualification: explicit careers/hiring language on the Page itself. A lone
    # generic technology word is not enough because Facebook shells recommend unrelated Pages.
    career_hits={m.group(0).casefold() for m in _FACEBOOK_WATCH_RELEVANCE.finditer(combined)}
    tech=bool(_FACEBOOK_WATCH_TECH_RELEVANCE.search(combined))
    title_career=bool(_FACEBOOK_WATCH_RELEVANCE.search(direct_title or clean_seed_title))
    relevant=title_career or len(career_hits)>=2 or (len(career_hits)>=1 and tech)
    if not relevant:
        return False, 'no strong Page-owned hiring/career relevance', direct_text, direct_browser_title or direct_title or clean_seed_title
    foreign=len(re.findall(r'[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\u0400-\u052f\u1780-\u17ff]',combined[:1200]))
    latin=len(re.findall(r'[A-Za-z]',combined[:1200]))
    if foreign>80 and foreign>latin and not title_career:
        return False, 'foreign-language/non-career page', direct_text, direct_browser_title or direct_title or clean_seed_title
    return True, 'direct Page-owned career/hiring relevance', direct_text, direct_browser_title or direct_title or clean_seed_title


def remember_facebook_page(result):
    """Persist only directly validated, career-relevant Facebook Page watches."""
    url=str((result or {}).get('url') or '').strip()
    title=str((result or {}).get('title') or '').strip()[:300]
    evidence=str((result or {}).get('snippet') or '')[:8000]
    if not url: return None
    try:
        parsed=urllib.parse.urlparse(url); host=parsed.netloc.lower().removeprefix('www.')
        if host not in {'facebook.com','m.facebook.com','web.facebook.com'}: return None
        parts=[urllib.parse.unquote(x) for x in parsed.path.split('/') if x]
        if not parts: return None
        blocked={'posts','groups','watch','marketplace','events','photo','photos','reel','reels','share','story.php','permalink.php','login','help','pages'}|_FACEBOOK_SYSTEM_SLUGS
        candidate=''
        if parts[0].lower()=='profile.php': candidate=(urllib.parse.parse_qs(parsed.query).get('id') or [''])[0]
        elif parts[0].lower() not in blocked: candidate=parts[0]
        if not candidate or len(candidate)>120: return None
        page_url=('https://www.facebook.com/'+candidate) if not candidate.isdigit() else url
        relevant,reason,direct_text,direct_title=facebook_page_relevant(page_url,title,evidence,direct=True)
        if not relevant: return None
        identity=facebook_page_identity_title(page_url,direct_title or title,evidence,candidate,direct=False)
        display_title=_clean_facebook_page_title(identity.get('title') or candidate) or candidate
        state='verified' if reason.startswith('direct Page-owned') else 'indexed'
        defaults={'page_url':page_url[:1000],'page_title':display_title,'evidence_text':evidence,'evidence_url':url[:1000],'enabled':True,'is_read':False,'validation_state':state,'validation_reason':reason[:500],'validated_at':timezone.now()}
        row=FacebookPage.objects.filter(page_id__iexact=candidate).order_by('pk').first()
        created=False
        if row is None:
            row=FacebookPage.objects.create(page_id=candidate,**defaults); created=True
        changed=[]
        if row.validation_state!=state: row.validation_state=state; changed.append('validation_state')
        row.validation_reason=reason[:500]; row.validated_at=timezone.now(); changed.extend(['validation_reason','validated_at'])
        if row.page_url!=page_url[:1000]: row.page_url=page_url[:1000]; changed.append('page_url')
        if display_title and row.page_title!=display_title: row.page_title=display_title; changed.append('page_title')
        if evidence and row.evidence_text!=evidence: row.evidence_text=evidence; changed.append('evidence_text')
        if url and row.evidence_url!=url[:1000]: row.evidence_url=url[:1000]; changed.append('evidence_url')
        if row.deleted_at is None and not row.enabled: row.enabled=True; changed.append('enabled')
        if changed: row.save(update_fields=changed+['updated_at'])
        return row
    except Exception:
        return None

def revalidate_facebook_pages(limit=8, max_age_days=7, full_history=False):
    """Revalidate watched Pages; full_history=True performs the release-wide historical pass."""
    try:
        cap=max(0,min(30,int(limit or 0)))
    except Exception:
        cap=8
    if cap<=0:
        return {'checked':0,'removed':0,'retained_unavailable':0,'titles_cleaned':0}
    cutoff=timezone.now()-timedelta(days=max(1,int(max_age_days or 7)))
    source_qs=FacebookPage.objects.filter(deleted_at__isnull=True) if full_history else FacebookPage.objects.filter(deleted_at__isnull=True,updated_at__lte=cutoff)
    rows=list(source_qs.order_by('updated_at','pk')[:(100000 if full_history else cap)])
    stats={'checked':0,'removed':0,'retained_unavailable':0,'titles_cleaned':0}
    for page in rows:
        stats['checked']+=1
        url=str(page.page_url or f'https://www.facebook.com/{page.page_id}')
        relevant,reason,_text,direct_title=facebook_page_relevant(url,page.page_title,'',direct=True)
        direct_unavailable=('direct Page fetch unavailable' in reason)
        if not relevant:
            # A previously verified Page survives a transient Facebook block; unknown/
            # legacy rows do not survive merely because Facebook is unavailable.
            if direct_unavailable and page.validation_state=='verified':
                page.validation_state='unavailable'; page.validation_reason=reason[:500]; page.validated_at=timezone.now()
                page.save(update_fields=['validation_state','validation_reason','validated_at','updated_at']); stats['retained_unavailable']+=1
                continue
            page.deleted_at=timezone.now(); page.enabled=False; page.is_read=True
            page.save(update_fields=['deleted_at','enabled','is_read','updated_at']); stats['removed']+=1
            continue
        updates=[]; state='verified' if reason.startswith('direct Page-owned') else 'indexed'
        if direct_title and direct_title!=page.page_title:
            page.page_title=direct_title[:300]; updates.append('page_title'); stats['titles_cleaned']+=1
        if not page.enabled: page.enabled=True; updates.append('enabled')
        page.validation_state=state; page.validation_reason=reason[:500]; page.validated_at=timezone.now(); updates.extend(['validation_state','validation_reason','validated_at'])
        page.save(update_fields=list(dict.fromkeys(updates+['updated_at'])))
    return stats


def facebook_graph_posts(base_terms,limit=25):
    cfg=FacebookConfig.objects.get_or_create(pk=1)[0]
    token=decrypt(cfg.graph_access_token_enc) or os.getenv('META_ACCESS_TOKEN','')
    ids=list(FacebookPage.objects.filter(enabled=True,deleted_at__isnull=True).values_list('page_id',flat=True)[:50])
    if not ids: ids=_split(cfg.graph_page_ids or os.getenv('META_PAGE_IDS',''),50)
    if not cfg.use_graph_api or not token or not ids: return [],[]
    terms=[x.lower() for x in base_terms if x]; results=[]; errors=[]
    for page_id in ids:
        try:
            graph_version=os.getenv('META_GRAPH_VERSION','v23.0').strip() or 'v23.0'
            # A configured legacy Graph ID must not silently create a new Pages-to-Watch row.
            # New rows pass the same direct Page relevance check as search-discovered/manual rows.
            existing=FacebookPage.objects.filter(page_id=str(page_id),deleted_at__isnull=True).first()
            try:
                meta=requests.get(f'https://graph.facebook.com/{graph_version}/{page_id}',params={'fields':'id,name,link','access_token':token},timeout=10)
                if meta.ok:
                    md=meta.json(); resolved_id=str(md.get('id') or page_id); resolved_title=str(md.get('name') or '')[:300]
                    resolved_url=str(md.get('link') or f'https://www.facebook.com/{resolved_id}')[:1000]
                    if existing:
                        changed=[]
                        if resolved_title and existing.page_title!=resolved_title: existing.page_title=resolved_title; changed.append('page_title')
                        if resolved_url and existing.page_url!=resolved_url: existing.page_url=resolved_url; changed.append('page_url')
                        if changed: existing.save(update_fields=changed+['updated_at'])
                    else:
                        relevant,_reason,_direct,_page_title=facebook_page_relevant(resolved_url,resolved_title,'',direct=True)
                        if not relevant:
                            errors.append(f'{page_id}: Page skipped because direct career relevance could not be verified')
                            continue
                        existing=FacebookPage.objects.create(page_id=resolved_id,page_title=resolved_title,page_url=resolved_url,enabled=True,is_read=False)
                elif not existing:
                    errors.append(f'{page_id}: Page metadata unavailable; Page was not added without direct validation')
                    continue
            except Exception as exc:
                if not existing:
                    errors.append(f'{page_id}: Page validation failed: {exc}')
                    continue
            r=requests.get(f'https://graph.facebook.com/{graph_version}/{page_id}/posts',params={'fields':'message,permalink_url,created_time','limit':limit,'access_token':token},timeout=15)
            r.raise_for_status()
            for item in r.json().get('data',[]):
                msg=item.get('message','')
                if terms and not any(t in msg.lower() for t in terms): continue
                results.append({'title':(msg[:120] or 'Facebook public Page post'),'url':item.get('permalink_url',''),'snippet':msg,'published_at':item.get('created_time'),'facebook_mode':'graph'})
        except Exception as e: errors.append(f'{page_id}: {e}')
    return results,errors


def facebook_authenticated_fetch(url):
    cfg=FacebookConfig.objects.get_or_create(pk=1)[0]
    cookie=decrypt(cfg.cookie_header_enc)
    if not cfg.use_authenticated_cookie or not cookie: return None,'Authenticated Facebook cookie is not configured'
    try:
        r=_get(url,headers={'Cookie':cookie,'Sec-Fetch-Site':'none'},allow_redirects=True)
        payload=_facebook_payload_from_html(r.text,r.url); text=payload.get('text') or ''
        if 'log in' in text[:1200].lower() and len(text)<5000: return None,'Facebook session appears logged out or challenged'
        return {'url':r.url,'text':text[:25000],'title':payload.get('browser_title') or payload.get('title',''),'browser_title':payload.get('browser_title',''),'identity_title':payload.get('title',''),'html_length':len(r.content)},''
    except Exception as e: return None,str(e)

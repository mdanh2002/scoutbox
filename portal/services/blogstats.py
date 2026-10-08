import json, os, re
from urllib import request as urlrequest, error as urlerror
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from portal.models import BlogStatsConfig, TrackingLink, TrackingClick
from .crypto import decrypt

RUNTIME_PATH=os.getenv('EXTERNAL_STATS_CONFIG','/app/.scoutbox-runtime/external-stats.json')
SERVICE_URL=os.getenv('EXTERNAL_STATS_URL','http://stats_service:8787').rstrip('/')
BOT_RE=re.compile(r'bot|crawler|spider|preview|scanner|safe.?link|security|headless|facebookexternalhit|slackbot|discordbot|whatsapp|telegrambot',re.I)
DEFAULT_CONFIG={'host':'example.invalid','port':3306,'database':'statistics','username':'readonly','password':'change-me','query_mode':'native','view_name':'portal_shortlink_pageviews','table_name':'pageviews','method_column':'','path_column':'page_id','timestamp_column':'last_accessed','user_agent_column':'last_useragent','ip_column':'user_ip','method_value':''}

def looks_bot(ua): return bool(BOT_RE.search(ua or ''))

def _atomic_write(data):
    os.makedirs(os.path.dirname(RUNTIME_PATH),exist_ok=True)
    tmp=RUNTIME_PATH+'.tmp'
    with open(tmp,'w',encoding='utf-8') as f: json.dump(data,f,indent=2,sort_keys=True)
    os.chmod(tmp,0o600); os.replace(tmp,RUNTIME_PATH)

def load_external_config():
    try:
        with open(RUNTIME_PATH,'r',encoding='utf-8') as f: data=json.load(f)
    except Exception: data={}
    out=dict(DEFAULT_CONFIG); out.update(data or {})
    return out

def save_external_config(values,password=''):
    data=load_external_config()
    for k in ['host','database','username','view_name','table_name','method_column','path_column','timestamp_column','user_agent_column','ip_column','method_value','query_mode']:
        if k in values: data[k]=str(values.get(k) or '')
    try:data['port']=int(values.get('port') or data.get('port') or 3306)
    except Exception:data['port']=3306
    if password:data['password']=password
    if data.get('query_mode')=='toughdev_native':data['query_mode']='native'
    _atomic_write(data); return data

def migrate_legacy_config(cfg=None):
    """One-time 0.11.71 handoff from the legacy DB-held connector credentials to the sidecar secret file."""
    cfg=cfg or BlogStatsConfig.objects.get_or_create(pk=1,defaults={'enabled':True})[0]
    if os.path.exists(RUNTIME_PATH): return load_external_config()
    has_legacy=bool((cfg.host or '').strip() or (cfg.database or '').strip() or (cfg.username or '').strip() or (cfg.password_enc or '').strip())
    data=dict(DEFAULT_CONFIG)
    if has_legacy:
        data.update({'host':cfg.host or data['host'],'port':cfg.port or 3306,'database':cfg.database or data['database'],'username':cfg.username or data['username'],'password':decrypt(cfg.password_enc) or data['password'],'query_mode':'native' if cfg.query_mode=='toughdev_native' else (cfg.query_mode or 'native'),'view_name':cfg.view_name or data['view_name'],'table_name':cfg.table_name or data['table_name'],'method_column':cfg.method_column or '','path_column':cfg.path_column or data['path_column'],'timestamp_column':cfg.timestamp_column or data['timestamp_column'],'user_agent_column':cfg.user_agent_column or data['user_agent_column'],'ip_column':cfg.ip_column or data['ip_column'],'method_value':cfg.method_value or ''})
    try:_atomic_write(data)
    except OSError:return data
    if has_legacy:
        cfg.host=''; cfg.database=''; cfg.username=''; cfg.password_enc=''; cfg.query_mode='native'; cfg.view_name=''; cfg.table_name=''; cfg.method_column=''; cfg.path_column=''; cfg.timestamp_column=''; cfg.user_agent_column=''; cfg.ip_column=''; cfg.method_value=''; cfg.save(update_fields=['host','database','username','password_enc','query_mode','view_name','table_name','method_column','path_column','timestamp_column','user_agent_column','ip_column','method_value'])
    return data

def _call(path,payload=None,timeout=12):
    body=None if payload is None else json.dumps(payload).encode('utf-8')
    req=urlrequest.Request(SERVICE_URL+path,data=body,headers={'Content-Type':'application/json'},method='GET' if payload is None else 'POST')
    try:
        with urlrequest.urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode('utf-8'))
    except urlerror.HTTPError as exc:
        try:
            data=json.loads(exc.read().decode('utf-8'))
            return {'ok':False,'message':data.get('message') or 'External statistics data source is unavailable.'}
        except Exception:
            return {'ok':False,'message':'External statistics data source is unavailable.'}
    except Exception:
        return {'ok':False,'message':'External statistics service is unavailable. ScoutBox will continue to operate normally; external click statistics will not be synchronized.'}

def service_status(): return _call('/health',None,3)

def test_connection(cfg=None):
    migrate_legacy_config(cfg)
    return _call('/test',{},10)

def _dt(v):
    if not v:return None
    d=parse_datetime(str(v)); return d

def sync_clicks():
    cfg=BlogStatsConfig.objects.get_or_create(pk=1,defaults={'enabled':True})[0]
    migrate_legacy_config(cfg)
    if not cfg.enabled:return {'ok':False,'message':'External statistics synchronization is disabled.','updated':0}
    links=list(TrackingLink.objects.filter(deleted_at__isnull=True))
    result=_call('/sync',{'links':[{'id':x.pk,'path':x.path} for x in links]},20)
    if not result.get('ok'):return dict(result,updated=0)
    by_id={x.pk:x for x in links}; updated=0; detailed=0
    for row in result.get('results') or []:
        link=by_id.get(row.get('id'))
        if not link:continue
        link.click_count=int(row.get('total') or 0); link.likely_human_clicks=int(row.get('human') or 0); link.first_click=_dt(row.get('first')); link.last_click=_dt(row.get('last')); link.save(update_fields=['click_count','likely_human_clicks','first_click','last_click'])
        if link.click_count:updated+=1
        for ev in row.get('events') or []:
            detailed+=1
            TrackingClick.objects.get_or_create(source_key=str(ev.get('source_key') or ''),defaults={'tracking_link':link,'viewed_at':_dt(ev.get('viewed_at')) or timezone.now(),'ip_address':ev.get('ip_address') or '','user_agent':ev.get('user_agent') or '','referrer':ev.get('referrer') or '','likely_bot':looks_bot(ev.get('user_agent') or ''),'source_table':'external_statistics','raw_uri':ev.get('raw_uri') or ''})
    cfg.last_sync=timezone.now(); cfg.save(update_fields=['last_sync'])
    return {'ok':True,'message':f'Synchronized {updated} tracked link(s); {detailed} detailed event(s) available.','updated':updated,'detailed':detailed}

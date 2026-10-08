from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from portal.models import PortalSettings, CloudBudgetUsage, CloudRunUsage, CampaignRun, UsageMetric, UsageThresholdNotification

_CLOUD_PROVIDERS={'openai','gemini','openrouter'}
_CTX=ContextVar('scoutbox_usage_context', default={})

class CloudLimitReached(RuntimeError):
    def __init__(self, limit_name, used, limit, message='', *, metric_key='', period_key='', attempted=None, campaign_name=''):
        self.limit_name=limit_name; self.used=used; self.limit=limit
        self.metric_key=metric_key; self.period_key=period_key; self.attempted=int(attempted if attempted is not None else used); self.campaign_name=campaign_name
        super().__init__(message or f'Cloud AI limit reached: {limit_name} {used}/{limit}')


def is_cloud_provider(provider):
    return str(provider or '').lower() in _CLOUD_PROVIDERS


def usage_context():
    return dict(_CTX.get() or {})

@contextmanager
def scoped_usage_context(**kwargs):
    previous=usage_context(); merged={**previous,**{k:v for k,v in kwargs.items() if v is not None}}
    token=_CTX.set(merged)
    try:
        yield merged
    finally:
        _CTX.reset(token)


def metadata(extra=None):
    return {**usage_context(), **(extra or {})}


def _limits(settings_obj):
    s=settings_obj
    return {
        'daily_requests':int(s.cloud_daily_requests or 0),
        'daily_web_searches':int(s.cloud_daily_web_searches or 0),
        'daily_input_tokens':int(s.cloud_daily_input_tokens or 0),
        'daily_output_tokens':int(s.cloud_daily_output_tokens or 0),
        'passive_enrichment':int(s.cloud_passive_enrichment_per_day or 0),
        'page_recovery':int(s.cloud_page_recovery_per_day or 0),
        'run_requests':int(s.cloud_requests_per_run or 0),
        'run_web_searches':int(s.cloud_web_searches_per_run or 0),
        'run_candidates':int(s.cloud_discovery_candidates_per_run or 0),
        'run_deep_research':int(s.cloud_deep_research_candidates_per_run or 0),
    }


def today_usage():
    row=CloudBudgetUsage.objects.filter(day=timezone.localdate()).first()
    s=PortalSettings.objects.get_or_create(pk=1)[0]
    lim=_limits(s)
    if not row:
        values={'requests':0,'web_searches':0,'tokens_in':0,'tokens_out':0,'reasoning_tokens':0,'tokens_out_reasoning':0,'passive_enrichment':0,'page_recovery':0}
    else:
        values={k:getattr(row,k) for k in ('requests','web_searches','tokens_in','tokens_out','reasoning_tokens','tokens_out_reasoning','passive_enrichment','page_recovery')}
    return {'day':timezone.localdate().isoformat(), **values, 'limits':lim}


def _send_threshold_email(subject, body):
    try:
        from django.contrib.auth.models import User
        from portal.services.notifications import send_notification
        recipient=User.objects.filter(is_active=True).exclude(email='').values_list('email',flat=True).first()
        if recipient:
            send_notification(recipient,subject,body)
    except Exception:
        # The in-portal threshold row is authoritative even if SMTP is unavailable.
        pass


def _record_threshold(period_key, metric_key, label, used, limit, campaign_name=''):
    used=max(0,int(used or 0)); limit=max(0,int(limit or 0))
    if not period_key or not metric_key or limit<=0:
        return
    pct=(used*100.0/limit)
    crossed=[x for x in (50,80,100) if pct>=x]
    if not crossed:
        return
    missing=[]
    for threshold in crossed:
        _row,created=UsageThresholdNotification.objects.get_or_create(
            period_key=period_key,metric_key=metric_key,threshold=threshold,
            defaults={'metric_label':label[:200],'used':used,'limit':limit,'campaign_name':campaign_name[:200]},
        )
        if created:
            missing.append(threshold)
    if not missing:
        return
    highest=max(missing)
    state='exceeded' if used>limit else ('reached' if highest>=100 else f'{highest}% used')
    context=f' for {campaign_name}' if campaign_name else ''
    subject=f'ScoutBox limit alert — {label} {state}'
    body=(f'{label}{context}: {used:,} / {limit:,} ({pct:.1f}%).\n'
          f'Threshold: {highest}%.\nPeriod: {period_key}.\n'
          'ScoutBox recorded this threshold once for the current accounting period.')
    transaction.on_commit(lambda: _send_threshold_email(subject,body))


def _check(name, used, delta, limit, *, metric_key='', period_key='', campaign_name=''):
    attempted=int(used or 0)+int(delta or 0)
    if int(limit or 0)>0 and attempted>int(limit):
        raise CloudLimitReached(name,int(used or 0),int(limit),metric_key=metric_key,period_key=period_key,attempted=attempted,campaign_name=campaign_name)


def reserve(*, provider, requests=1, web_searches=0, tokens_in=0, tokens_out=0, operation='', campaign_run_id=None, candidates=0, deep_research=0):
    """Atomically reserve cloud capacity before a billable request and emit deduplicated threshold alerts."""
    if not is_cloud_provider(provider): return None
    ctx=usage_context(); campaign_run_id=campaign_run_id or ctx.get('campaign_run_id')
    day_key=f'day:{timezone.localdate().isoformat()}'
    try:
        with transaction.atomic():
            s=PortalSettings.objects.select_for_update().get_or_create(pk=1)[0]
            lim=_limits(s)
            row,_=CloudBudgetUsage.objects.select_for_update().get_or_create(day=timezone.localdate())
            _check('Cloud AI requests / day',row.requests,requests,lim['daily_requests'],metric_key='daily_requests',period_key=day_key)
            _check('AI Web Search Queries / day',row.web_searches,web_searches,lim['daily_web_searches'],metric_key='daily_web_searches',period_key=day_key)
            _check('Cloud input tokens / day',row.tokens_in,tokens_in,lim['daily_input_tokens'],metric_key='daily_input_tokens',period_key=day_key)
            _check('Cloud output + reasoning tokens / day',row.tokens_out_reasoning,tokens_out,lim['daily_output_tokens'],metric_key='daily_output_tokens',period_key=day_key)
            if operation=='passive_enrichment': _check('Passive enrichment / day',row.passive_enrichment,1,lim['passive_enrichment'],metric_key='passive_enrichment',period_key=day_key)
            if operation=='page_recovery': _check('Page-view recovery / day',row.page_recovery,1,lim['page_recovery'],metric_key='page_recovery',period_key=day_key)
            run_usage=None; run_name=''
            if campaign_run_id:
                run=CampaignRun.objects.select_related('campaign').filter(pk=campaign_run_id).first()
                if run:
                    run_name=getattr(run.campaign,'name','') or ''
                    run_key=f'run:{run.pk}'
                    run_usage,_=CloudRunUsage.objects.select_for_update().get_or_create(campaign_run=run)
                    _check('Cloud AI requests / campaign run',run_usage.requests,requests,lim['run_requests'],metric_key='run_requests',period_key=run_key,campaign_name=run_name)
                    _check('AI Web Search Queries / campaign run',run_usage.web_searches,web_searches,lim['run_web_searches'],metric_key='run_web_searches',period_key=run_key,campaign_name=run_name)
                    _check('Discovery candidates / campaign run',run_usage.discovery_candidates,candidates,lim['run_candidates'],metric_key='run_candidates',period_key=run_key,campaign_name=run_name)
                    _check('Deep research candidates / campaign run',run_usage.deep_research_candidates,deep_research,lim['run_deep_research'],metric_key='run_deep_research',period_key=run_key,campaign_name=run_name)
                    run_usage.requests+=max(0,int(requests or 0)); run_usage.web_searches+=max(0,int(web_searches or 0)); run_usage.discovery_candidates+=max(0,int(candidates or 0)); run_usage.deep_research_candidates+=max(0,int(deep_research or 0)); run_usage.save()
                    for key,label,used,limit in (
                        ('run_requests','Cloud AI requests / campaign run',run_usage.requests,lim['run_requests']),
                        ('run_web_searches','AI Web Search Queries / campaign run',run_usage.web_searches,lim['run_web_searches']),
                        ('run_candidates','Discovery candidates / campaign run',run_usage.discovery_candidates,lim['run_candidates']),
                        ('run_deep_research','Deep research candidates / campaign run',run_usage.deep_research_candidates,lim['run_deep_research']),
                    ): _record_threshold(run_key,key,label,used,limit,run_name)
            row.requests+=max(0,int(requests or 0)); row.web_searches+=max(0,int(web_searches or 0)); row.tokens_in+=max(0,int(tokens_in or 0)); row.tokens_out+=max(0,int(tokens_out or 0)); row.tokens_out_reasoning+=max(0,int(tokens_out or 0))
            if operation=='passive_enrichment': row.passive_enrichment+=1
            if operation=='page_recovery': row.page_recovery+=1
            row.save()
            for key,label,used,limit in (
                ('daily_requests','Cloud AI requests / day',row.requests,lim['daily_requests']),
                ('daily_web_searches','AI Web Search Queries / day',row.web_searches,lim['daily_web_searches']),
                ('daily_input_tokens','Cloud input tokens / day',row.tokens_in,lim['daily_input_tokens']),
                ('daily_output_tokens','Cloud output + reasoning tokens / day',row.tokens_out_reasoning,lim['daily_output_tokens']),
                ('passive_enrichment','Passive enrichment / day',row.passive_enrichment,lim['passive_enrichment']),
                ('page_recovery','Page-view recovery / day',row.page_recovery,lim['page_recovery']),
            ): _record_threshold(day_key,key,label,used,limit)
            return {'day_id':row.pk,'reserved_tokens_in':max(0,int(tokens_in or 0)),'reserved_tokens_out':max(0,int(tokens_out or 0)),'reserved_web_searches':max(0,int(web_searches or 0)),'provider':provider,'campaign_run_id':campaign_run_id,'operation':operation}
    except CloudLimitReached as exc:
        # The capacity reservation rolled back, but the blocked attempt itself is a useful
        # limit event. Store/send it in a fresh transaction so the 100% alert survives.
        with transaction.atomic():
            _record_threshold(exc.period_key or day_key,exc.metric_key or 'limit',exc.limit_name,exc.attempted,exc.limit,exc.campaign_name)
        raise

def reconcile(reservation, *, actual_tokens_in=0, actual_tokens_out=0, reasoning_tokens=0, actual_web_searches=None, actual_cost_usd=None):
    if not reservation: return
    with transaction.atomic():
        try: row=CloudBudgetUsage.objects.select_for_update().get(pk=reservation['day_id'])
        except CloudBudgetUsage.DoesNotExist: return
        reserved_in=int(reservation.get('reserved_tokens_in') or 0); reserved_out=int(reservation.get('reserved_tokens_out') or 0)
        actual_in=max(0,int(actual_tokens_in or 0)); visible_out=max(0,int(actual_tokens_out or 0)); reasoning=max(0,int(reasoning_tokens or 0)); actual_out=visible_out+reasoning
        row.tokens_in=max(0,row.tokens_in-reserved_in+actual_in)
        row.tokens_out=max(0,row.tokens_out-reserved_out+visible_out)
        row.reasoning_tokens=max(0,row.reasoning_tokens+reasoning)
        row.tokens_out_reasoning=max(0,row.tokens_out_reasoning-reserved_out+actual_out)
        if actual_web_searches is not None:
            # One web-search unit is normally reserved for each provider-native request.
            reserved_searches=max(0,int(reservation.get('reserved_web_searches') or 0))
            row.web_searches=max(0,row.web_searches-reserved_searches+max(0,int(actual_web_searches or 0)))
            run_id=reservation.get('campaign_run_id')
            if run_id:
                ru=CloudRunUsage.objects.select_for_update().filter(campaign_run_id=run_id).first()
                if ru:
                    ru.web_searches=max(0,ru.web_searches-reserved_searches+max(0,int(actual_web_searches or 0))); ru.save(update_fields=['web_searches','updated_at'])
        # Provider-reported monetary cost, when available, is kept on UsageMetric
        # metadata by the AI adapter.  Daily safety counters remain provider-neutral.
        row.save()
        s=PortalSettings.objects.get_or_create(pk=1)[0]; lim=_limits(s); day_key=f'day:{row.day.isoformat()}'
        _record_threshold(day_key,'daily_input_tokens','Cloud input tokens / day',row.tokens_in,lim['daily_input_tokens'])
        _record_threshold(day_key,'daily_output_tokens','Cloud output + reasoning tokens / day',row.tokens_out_reasoning,lim['daily_output_tokens'])
        _record_threshold(day_key,'daily_web_searches','AI Web Search Queries / day',row.web_searches,lim['daily_web_searches'])


def mark_candidates(count, *, deep=False, campaign_run_id=None):
    ctx=usage_context(); campaign_run_id=campaign_run_id or ctx.get('campaign_run_id')
    if not campaign_run_id: return
    with transaction.atomic():
        run=CampaignRun.objects.filter(pk=campaign_run_id).first()
        if not run: return
        ru,_=CloudRunUsage.objects.select_for_update().get_or_create(campaign_run=run)
        s=PortalSettings.objects.get_or_create(pk=1)[0]; lim=_limits(s)
        field='deep_research_candidates' if deep else 'discovery_candidates'; limit=lim['run_deep_research' if deep else 'run_candidates']
        label='Deep research candidates / campaign run' if deep else 'Discovery candidates / campaign run'
        key='run_deep_research' if deep else 'run_candidates'; period_key=f'run:{run.pk}'; campaign_name=getattr(run.campaign,'name','') or ''
        try:
            _check(label,getattr(ru,field),count,limit,metric_key=key,period_key=period_key,campaign_name=campaign_name)
        except CloudLimitReached:
            # The transaction will roll back; caller's request is blocked.
            raise
        setattr(ru,field,getattr(ru,field)+max(0,int(count or 0))); ru.save()
        _record_threshold(period_key,key,label,getattr(ru,field),limit,campaign_name)


def limit_status(operation=''):
    data=today_usage(); lim=data['limits']
    checks=[
        ('Cloud AI requests',data['requests'],lim['daily_requests']),
        ('AI Web Search Queries',data['web_searches'],lim['daily_web_searches']),
        ('Cloud input tokens',data['tokens_in'],lim['daily_input_tokens']),
        ('Cloud output + reasoning tokens',data['tokens_out_reasoning'],lim['daily_output_tokens']),
    ]
    if operation=='passive_enrichment': checks.append(('Passive enrichment',data['passive_enrichment'],lim['passive_enrichment']))
    if operation=='page_recovery': checks.append(('Page-view recovery',data['page_recovery'],lim['page_recovery']))
    for name,used,limit in checks:
        if int(limit or 0)>0 and int(used or 0)>=int(limit):
            return {'ok':False,'state':'limit_reached','name':name,'used':int(used or 0),'limit':int(limit),'message':f'{name} limit reached: {used} / {limit} today.'}
    return {'ok':True,'state':'available'}


def cloud_usage_by_operation(start=None,end=None):
    qs=UsageMetric.objects.filter(provider__in=list(_CLOUD_PROVIDERS))
    if start: qs=qs.filter(at__gte=start)
    if end: qs=qs.filter(at__lt=end)
    return qs

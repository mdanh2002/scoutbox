import smtplib
import concurrent.futures
import hashlib
import copy
import math
import os
import re
from html import unescape
import shutil
import subprocess
import urllib.parse
import time
import threading
import uuid
from pathlib import Path
from datetime import timedelta, datetime

from celery import shared_task, current_app
from celery.exceptions import Retry
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.cache import cache
from django.db import close_old_connections, transaction
from django.db.models import Q
from django.utils import timezone

from portal.models import (
    PortalSettings, Campaign, Opportunity, CampaignRun, BackgroundJob,
    SearchSource, ImportCandidate, ResourceSample, PerformanceRun, Application, Contact,
    GeneratedTextVersion, UsageMetric, CompanyLead, EmailProfile, BlogStatsConfig, Profile, DocumentAsset, AIProviderConfig, AIRequestLog, ChatbotMessage, MailEvent, FacebookPage, AuditLog, DiagnosticRun, SearchProviderStat, TrackingLinkRule,
)
from portal.services.discovery import (run_campaign, CampaignStopped, SearchProvidersUnavailable, CloudWebUnavailable,
    _is_third_party_job_url, _prefer_exact_employer_role, _direct_fetch)
from portal.services.mailbox import sync_mailbox, connect as imap_connect, folders as imap_folders, save_draft, populate_test_messages, maybe_persist_addressbook_contact, promote_record_contact_to_addressbook, assignable_contact_email, assess_addressbook_contact_fit
from portal.services.blogstats import sync_clicks, test_connection as test_blog_connection
from portal.services.notifications import send_notification, outgoing_method, outgoing_server_label, refresh_resend_delivery_states
from portal.services.digest import build_24h_digest
from portal.services.crypto import decrypt
from portal.services.imports import parse_lines, parse_uploaded
from portal.services.queryplanner import build_search_profile, extract_active_cv_texts
from portal.services.search import choose_providers, provider_selection_details, search_source, build_campaign_query_plan, test_search_provider, facebook_page_relevant, facebook_page_identity_title, remember_facebook_page
from portal.services.cloud_discovery import discover as cloud_discover
from portal.services.cold import scan_hidden_market, generate_cold_draft, short_company_summary, preliminary_company_summary, infer_country, hidden_lead_minibrowser_admission, market_summary_needs_refresh, strip_hidden_lead_evidence_markers
from portal.services.enrichment import enrich
from portal.services.opportunity_filter import classify_existing_opportunity, classify_existing_hidden_lead, classify_existing_contact
from portal.services.freshness import recompute, apply_cloud_post_age, post_age_label_for_days
from portal.services.pagefetch import fetch_target, probe_url_health
from portal.services.content_quality import soft_missing_reason, page_unavailable_reason, sanitize_mixed_script_title, normalize_opportunity_title, normalize_remote_constraints, work_arrangement_evidence, explicit_post_date_signal, extract_role_location
from portal.services.platforms import is_platform_company_name, is_job_board_host
from portal.services.opportunity_urls import looks_like_specific_opportunity_url
from portal.services.highlights import derive_opportunity_highlight, concise_technical_summary
from portal.services.salary import parse_salary_text, apply_salary_info, salary_text_has_numeric_amount
from portal.services.tracking import allocate, allocate_for_url, preview_for_url, reserve_count, resolve_article, clean_article_title, article_title_needs_refresh
from portal.services.application import prepare_application, generate_email_version, generate_application_artifacts
from portal.services.campaign_templates import generate_profile_campaign_templates, generate_resume_campaign_template, generate_all_resume_campaign_templates
from portal.services.ai import AIEmptyOutputWarning, LocalAILaneBusy, generate, test_provider, generate_with, generate_with_route, route_for_stage, effective_route_for_stage, bundle_owners, web_search_with, cloud_discovery_route, pipeline_route_signature, STAGES, STAGE_TOKEN_DEFAULTS, ai_request_timeout, has_usable_cloud_web_model, CloudRateLimited, cloud_rate_limit_cooldown
from portal.services.company_research import (research_company, company_info_has_display_data,
    stored_company_context, enrich_company_intel_from_retained, company_summary_from_intel, company_intel_from_manual_filter,
    refresh_company_domain_registration)
from portal.services.performance import run_lab
from portal.services.cloud_budget import CloudLimitReached, scoped_usage_context, limit_status as cloud_limit_status, is_cloud_provider
from portal.services.readiness import ai_compute_readiness, local_accelerator_state
from portal.services.ai_lifecycle import reserve_attempt, complete_attempt, budget_operation_for_phase
from portal.services.diagnostics import run_system_diagnostics
from portal.services import ollama as ollama_service
from portal.services.resources import gpu_telemetry, gpu_telemetry_detail, host_cpu_percent, host_resource_totals, capture_resource_sample
from portal.services.run_context import inherited_run_context
from portal.services.chatbot import ask as chatbot_answer
from portal.services.fresh_sources import DIRECT_ADAPTERS, FORUM_DIRECT_ADAPTER
from portal.services.focus import FOCUS_TARGET_VERSION, rebuild_all_focus_taxonomies_with_ai, focus_taxonomy_rebuild_due, focus_taxonomy_snapshot, backfill_blank_focuses
from portal.services.blacklist import enforce_active_blacklist
from portal.services.integrity_repair import repair_existing_opportunity_integrity
from portal.services.location import repopulate_country_fields
from portal.services.selectivity import snapshot as selectivity_snapshot
from portal.services.dedup import active_duplicate_lead, active_duplicate_opportunity

HIDDEN_LEAD_REASSESSMENT_RELEASE = '0.11.29'
HIDDEN_LEAD_REASSESSMENT_LABEL = 'Reassess existing Hidden Leads for 0.11.29'
HIDDEN_LEAD_REASSESSMENT_PASS_KEY = 'hidden_lead_minibrowser_reassessment_pass'
HIDDEN_LEAD_REASSESSMENT_SCHEMA = 'hidden_lead_minibrowser_admission_v1'
HIDDEN_LEAD_REASSESSMENT_PER_LEAD_SECONDS = 75
HIDDEN_LEAD_REASSESSMENT_PAGE_TIMEOUT = 6
HIDDEN_LEAD_REASSESSMENT_QUEUE_RECOVERY_SECONDS = 90
HIDDEN_LEAD_REASSESSMENT_LEASE_SECONDS = HIDDEN_LEAD_REASSESSMENT_PER_LEAD_SECONDS + 90


def _yield_after_reassessment_item():
    """Let Django close idle DB handles and briefly yield between heavy items.

    This does not reduce the configured cloud/manual parallelism or force the
    reassessment to single-track. It prevents tight fetch/AI/save loops from
    starving the web process on small self-hosted deployments.
    """
    try:
        close_old_connections()
    except Exception:
        pass
    time.sleep(0.05)


def _safe_setting_attr(obj, name, default=None):
    """Read a setting from either a PortalSettings model row or a dict snapshot.

    A corrupted/cached dict snapshot in the campaign planner previously crashed Local
    Discovery at "Preparing search plan" with ``'dict' object has no attribute
    'scraper_interval_minutes'``. Discovery should use a safe default instead of failing
    the whole campaign before the first query is built.
    """
    try:
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)
    except Exception:
        return default


def _safe_setting_int(obj, name, default, minimum=None, maximum=None):
    try:
        value = int(_safe_setting_attr(obj, name, default) or default)
    except Exception:
        value = int(default)
    if minimum is not None:
        value = max(int(minimum), value)
    if maximum is not None:
        value = min(int(maximum), value)
    return value


def _usage_ids_for_entity(entity):
    """Recover originating campaign/run IDs for asynchronous enrichment accounting."""
    if isinstance(entity, Opportunity):
        data=entity.extracted_facts or {}
    elif isinstance(entity, CompanyLead):
        data=(entity.ai_state or {}).get('_usage') or {}
    else:
        intel=getattr(entity,'company_intel',{}) or {}
        data=intel.get('_usage') or {} if isinstance(intel,dict) else {}
    return data.get('campaign_id'), data.get('campaign_run_id')


def _ollama_accelerator_evidence():
    """Best-effort proof that local inference is accelerator-backed.

    /api/ps and host telemetry are independent signals; failure of either one must not
    discard evidence from the other.
    """
    vram=0; label=''; gpu=None
    try:
        running=ollama_service.running_models() or []
        vram=max([int(float((item or {}).get('size_vram') or 0)) for item in running] or [0])
    except Exception:
        pass
    try:
        gpu,_,label,_,_=gpu_telemetry_detail()
    except Exception:
        pass
    try:
        host_accel=local_accelerator_state()
    except Exception:
        host_accel={}
    host_detected=bool(host_accel.get('detected'))
    host_label=str(host_accel.get('label') or '')
    return {
        'validated':bool(vram > 0 or label or gpu is not None or host_detected),
        'vram_bytes':vram,
        'label':label or host_label,
        'apple_silicon':bool(host_accel.get('apple_silicon')),
    }


def _campaign_criteria(campaign):
    return {
        'name':campaign.name,
        'template':campaign.template,
        'locations':campaign.locations or ([campaign.location] if campaign.location else []),
        'role_families':campaign.role_families,
        'technologies':campaign.technologies,
        'engagement_types':campaign.engagement_types,
        'company_sizes':campaign.company_sizes,
        'languages':campaign.languages,
        'negative_constraints':campaign.negative_constraints,
        'extra_text':campaign.extra_text,
        'recency_days':campaign.recency_days,
        'source_names':campaign.source_names,
        'queries_per_rotation':campaign.queries_per_rotation,
        # Scheduler-critical JSON flags are explicit from 0.10.81 onward.  Older rows
        # omitted false values, which made negated JSON-key lookups backend-dependent.
        'forum_only':False,
        'deferred_local_ai':False,
        'run_kind':'primary',
    }


def _job_start(job, message='Running'):
    job.status='running'; job.started_at=timezone.now(); job.progress=max(1,job.progress); job.message=message
    job.save(update_fields=['status','started_at','progress','message'])


def _job_done(job, result=None, message='Completed'):
    job.refresh_from_db(fields=['status'])
    if job.status=='stopped': return
    job.status='completed'; job.finished_at=timezone.now(); job.progress=100; job.message=message; job.result=result or {}
    job.save(update_fields=['status','finished_at','progress','message','result'])


def _job_fail(job, exc):
    job.refresh_from_db(fields=['status'])
    if job.status=='stopped': return
    job.status='failed'; job.finished_at=timezone.now(); job.message='Failed'; job.error=str(exc)
    job.save(update_fields=['status','finished_at','message','error'])


@shared_task(bind=True)
def chatbot_request_job(self, job_id):
    """Run Ask ScoutBox with an explicit chatbot-only primary/secondary failover.

    The browser queues the request and polls persisted history. The secondary route is
    attempted only when the primary provider/model request fails (or the primary model's
    configured context is too small for the complete workspace index). No discovery,
    enrichment or other ScoutBox stage reads this Chatbot fallback.
    """
    job=BackgroundJob.objects.get(pk=job_id)
    job.celery_task_id=self.request.id or ''
    _job_start(job,'Asking the primary Chatbot provider')
    data=job.result if isinstance(job.result,dict) else {}
    session_key=str(data.get('session_key') or '')[:120]
    question=str(data.get('question') or '').strip()[:1600]
    history=data.get('history') if isinstance(data.get('history'),list) else []
    current_path=str(data.get('current_path') or '')[:500]
    provider=str(data.get('provider') or '').strip().lower()
    model=str(data.get('model') or '').strip()
    allow_internet=bool(data.get('allow_internet_search'))
    secondary_provider=str(data.get('secondary_provider') or '').strip().lower()
    secondary_model=str(data.get('secondary_model') or '').strip()
    secondary_allow_internet=bool(data.get('secondary_allow_internet_search'))

    def safe_error(exc):
        return re.sub(r'(?i)(api[_ -]?key|authorization|bearer|password|token)\s*[:=]\s*[^\s,;]+',r'\1=[redacted]',str(exc or 'Chatbot provider request failed.'))[:600]

    # Chatbot provider timeout is a per-attempt setting. Primary and Secondary each
    # receive the configured window; there is no hidden five-minute aggregate cap that
    # can starve the fallback after a slow primary attempt.
    provider_timeout=ai_request_timeout(provider or secondary_provider or 'ollama','chatbot')

    def run_route(route_provider,route_model,route_internet):
        attempts=0
        while True:
            attempts+=1
            try:
                return chatbot_answer(
                    question,history=history,current_path=current_path,
                    provider_override=route_provider,model_override=route_model,
                    allow_internet_override=route_internet,raise_errors=True,
                    request_timeout=provider_timeout,
                )
            except Exception as exc:
                # HTTP 429 is not helped by a larger socket timeout. Retry it once,
                # honoring Retry-After when practical, before using the failover.
                response=getattr(exc,'response',None)
                status=getattr(response,'status_code',None)
                detail=str(exc or '')
                if attempts>=2 or not (status==429 or '429' in detail or 'Too Many Requests' in detail):
                    raise
                retry_after=0.0
                try:
                    retry_after=float((getattr(response,'headers',{}) or {}).get('Retry-After') or 0)
                except Exception:
                    retry_after=0.0
                wait=max(2.0,min(30.0,retry_after or 5.0))
                time.sleep(wait)

    result=None; used_provider=provider; used_model=model; used_secondary=False; primary_error=''
    try:
        result=run_route(provider,model,allow_internet)
        # A complete workspace that cannot fit the primary model is a route limitation,
        # so allow the explicitly configured secondary to try its own context ceiling.
        if result.get('context_too_large') and secondary_provider and secondary_model:
            primary_error=str(result.get('answer') or 'Primary chatbot context limit exceeded.')[:600]
            job.message='Primary Chatbot context limit reached; trying secondary provider'
            job.save(update_fields=['message'])
            result=run_route(secondary_provider,secondary_model,secondary_allow_internet)
            used_provider=secondary_provider; used_model=secondary_model; used_secondary=True
    except Exception as exc:
        primary_error=safe_error(exc)
        if secondary_provider and secondary_model:
            try:
                job.message='Primary Chatbot failed; trying secondary provider'
                job.save(update_fields=['message'])
                result=run_route(secondary_provider,secondary_model,secondary_allow_internet)
                used_provider=secondary_provider; used_model=secondary_model; used_secondary=True
            except Exception as secondary_exc:
                secondary_error=safe_error(secondary_exc)
                detail=f'Primary failed: {primary_error} · Secondary failed: {secondary_error}'[:1200]
                saved=None
                try:
                    saved=ChatbotMessage.objects.create(
                        session_key=session_key,role='assistant',
                        text='Chatbot primary and secondary provider/model requests failed. '+detail,
                        links=[],source_provider='ScoutBox',source_model='Failover exhausted',
                    )
                except Exception:
                    pass
                job.status='failed'; job.finished_at=timezone.now(); job.progress=100
                job.message='Chatbot primary and secondary routes failed'; job.error=detail
                job.result={**data,'assistant_message_id':saved.pk if saved else None,'primary_error':primary_error,'secondary_error':secondary_error,'failover_attempted':True}
                job.save(update_fields=['status','finished_at','progress','message','error','result'])
                return {'ok':False,'error':detail,'assistant_message_id':saved.pk if saved else None}
        else:
            detail=primary_error
            saved=None
            try:
                saved=ChatbotMessage.objects.create(
                    session_key=session_key,role='assistant',
                    text='Chatbot provider/model request failed: '+detail,
                    links=[],source_provider='ScoutBox',source_model='Primary route failed',
                )
            except Exception:
                pass
            job.status='failed'; job.finished_at=timezone.now(); job.progress=100
            job.message='Chatbot provider/model request failed'; job.error=detail
            job.result={**data,'assistant_message_id':saved.pk if saved else None,'provider_error':detail}
            job.save(update_fields=['status','finished_at','progress','message','error','result'])
            return {'ok':False,'error':detail,'assistant_message_id':saved.pk if saved else None}

    if result is None:
        result={'answer':'ScoutBox returned an empty Chatbot result.','links':[],'used_ai':False,'degraded':True}
    if bool(result.get('used_ai')):
        source_provider={'ollama':'Ollama','openai':'OpenAI','gemini':'Gemini','openrouter':'OpenRouter'}.get(used_provider,used_provider)
        source_model=used_model
    else:
        source_provider='ScoutBox'
        source_model='Context routing' if result.get('context_too_large') else 'Built-in response'
    saved=ChatbotMessage.objects.create(
        session_key=session_key,role='assistant',
        text=str(result.get('answer') or 'ScoutBox returned an empty Chatbot answer.'),
        links=result.get('links') if isinstance(result.get('links'),list) else [],
        source_provider=source_provider[:40],source_model=source_model[:300],
    )
    payload={
        **data,'assistant_message_id':saved.pk,'used_ai':bool(result.get('used_ai')),
        'internet_search':bool(result.get('internet_search')),
        'answer_provider':source_provider,'answer_model':source_model,
        'failover_attempted':bool(used_secondary or primary_error),'used_secondary':used_secondary,
    }
    if primary_error: payload['primary_error']=primary_error
    _job_done(job,payload,'Chatbot answer ready'+(' via secondary' if used_secondary else ''))
    return {'ok':True,'assistant_message_id':saved.pk,'provider':source_provider,'model':source_model,'used_secondary':used_secondary}



@shared_task(bind=True)
def run_campaign_job(self, run_id):
    run=CampaignRun.objects.select_related('campaign').get(pk=run_id)
    worker_started=time.monotonic()
    if run.status in ('stopping','stopped','failed','completed'):
        if run.status in ('stopping','stopped'):
            CampaignRun.objects.filter(pk=run.pk,status__in=['stopping','stopped']).update(
                status='stopped',finished_at=timezone.now(),message='Stopped before execution')
            return {'stopped':True,'run_duration_seconds':0.0}
        return {'skipped':True,'status':run.status,'run_duration_seconds':0.0}

    run.criteria=run.criteria or _campaign_criteria(run.campaign)
    settings_row=PortalSettings.objects.get_or_create(pk=1)[0]
    # Snapshot all three independent selectivity controls when execution begins.  Every
    # stage in this run resolves policy from this immutable snapshot, so changing Config
    # mid-run affects the next run rather than changing admission rules halfway through.
    run.criteria.setdefault('selectivity', selectivity_snapshot(settings_row))
    mode=str((run.criteria or {}).get('discovery_mode') or settings_row.discovery_mode or 'source_guided').strip().lower()
    forum_only=bool((run.criteria or {}).get('forum_only') or (run.criteria or {}).get('run_kind')=='forum_only')
    run.criteria['discovery_mode']=mode
    if forum_only:
        run.criteria['forum_only']=True
        run.criteria['run_kind']='forum_only'
    try:
        from pathlib import Path as _Path
        run.criteria['scoutbox_version']=(_Path(__file__).resolve().parents[1]/'VERSION').read_text().strip()
    except Exception:
        run.criteria['scoutbox_version']='0.8.72'
    run.criteria['worker_id']=str(getattr(self.request,'hostname','') or '')[:160]

    # Cloud Web has its own readiness contract and must never require/probe Ollama.
    execution_provider=''; execution_model=''
    if mode=='cloud_web':
        try:
            if not has_usable_cloud_web_model():
                raise RuntimeError('One or more Cloud Web stages is not configured.')
            cloud_route=cloud_discovery_route(stage='url_scrape')
            execution_provider=str(cloud_route.get('provider') or '')[:80]
            execution_model=str(cloud_route.get('model') or '')[:200]
        except Exception:
            stopped_at=timezone.now(); result={**(run.result or {}),'stopped_reason':'cloud_web_unavailable','discovery_mode':'cloud_web'}
            updated=CampaignRun.objects.filter(pk=run.pk,status='queued').update(
                status='stopped',finished_at=stopped_at,progress=0,message='Cloud Web unavailable — no usable Cloud provider/model',result=result)
            if not updated:
                run.refresh_from_db(); return {'skipped':True,'status':run.status}
            return {'stopped':True,'reason':'cloud_web_unavailable'}
    else:
        readiness=ai_compute_readiness(force=True)
        try:
            local_route=effective_route_for_stage('url_scrape') or effective_route_for_stage('general') or {}
            execution_provider=str(local_route.get('provider') or 'ollama')[:80]
            execution_model=str(local_route.get('model') or '')[:200]
        except Exception:
            execution_provider='ollama'; execution_model=''
        if not readiness.get('ready'):
            stopped_at=timezone.now(); result={**(run.result or {}),'stopped_reason':'ai_compute_unavailable','readiness_reason':readiness.get('reason',''),'discovery_mode':mode}
            updated=CampaignRun.objects.filter(pk=run.pk,status='queued').update(
                status='stopped',finished_at=stopped_at,progress=0,message='AI compute unavailable — run not started',result=result)
            if not updated:
                run.refresh_from_db(); return {'skipped':True,'status':run.status}
            return {'stopped':True,'reason':'ai_compute_unavailable'}

    started_now=timezone.now(); stage=('Browsing forum sources' if forum_only else ('Preparing context' if mode=='cloud_web' else 'Preparing search plan'))
    updated=CampaignRun.objects.filter(pk=run.pk,status='queued').update(
        celery_task_id=self.request.id or run.celery_task_id,status='running',started_at=started_now,heartbeat_at=started_now,progress=2,
        stage=stage,message=stage,execution_provider=execution_provider,execution_model=execution_model,stall_reason='',criteria=run.criteria)
    if not updated:
        run.refresh_from_db()
        return {'skipped':True,'status':run.status,'run_duration_seconds':round(max(0.0,time.monotonic()-worker_started),3)}
    run.refresh_from_db()
    # Forum browsing is split into cheap acquisition and AI-backed qualification.  The
    # acquisition phase may run on the dedicated forum worker even while primary discovery
    # is busy; once candidates have been acquired, Forum work yields before consuming AI.
    forum_acquisition_complete=False

    # Keep a worker-level heartbeat alive even while a search provider, page fetch, or AI
    # call is blocking. Progress callbacks still update the human-readable stage/message,
    # but dashboard stall detection now reflects worker liveness rather than requiring a
    # provider call to return within the warning window. The daemon exits automatically
    # as soon as this run is no longer marked running.
    def _worker_heartbeat():
        close_old_connections()
        try:
            while True:
                time.sleep(15)
                try:
                    updated=CampaignRun.objects.filter(pk=run.pk,status='running').update(heartbeat_at=timezone.now())
                    if not updated:
                        break
                except Exception:
                    # Never fail discovery because a best-effort heartbeat write collided
                    # with another short database transaction. The next tick retries.
                    pass
                finally:
                    close_old_connections()
        finally:
            close_old_connections()
    threading.Thread(target=_worker_heartbeat,name=f'scoutbox-run-heartbeat-{run.pk}',daemon=True).start()

    def _primary_discovery_waiting():
        # Forum work is supplementary. Yield between bounded operations whenever a real
        # non-Forum campaign becomes queued/running, so the Forum worker cannot consume
        # the Local/Cloud AI lane ahead of primary discovery.
        if not forum_only:
            return False
        try:
            rows=CampaignRun.objects.filter(status__in=['queued','running','stopping']).exclude(pk=run.pk).only('criteria','status')
            if _has_non_forum_runs(rows):
                return True
            ai_background_kinds=('company_research','hidden_scan','enrich','summarize','prepare','translate','cold_draft','chatbot')
            return BackgroundJob.objects.filter(status__in=['queued','running'],kind__in=ai_background_kinds).exists()
        except Exception:
            return False

    def stopped():
        if CampaignRun.objects.filter(pk=run.pk,status__in=['stopping','stopped','failed']).exists():
            return True
        # Do not pre-empt the cheap HTTP acquisition phase merely because primary work is
        # active.  Qualification/persistence begins only after progress advances beyond
        # forum browsing, at which point this callback yields immediately to primary AI.
        return bool(forum_acquisition_complete and _primary_discovery_waiting())

    def progress(value, message):
        nonlocal forum_acquisition_complete
        msg=str(message or 'Working')[:500]
        if forum_only and int(value or 0)>=36:
            forum_acquisition_complete=True
        CampaignRun.objects.filter(pk=run.pk,status='running').update(progress=max(0,min(99,int(value))),message=msg,stage=msg[:120],heartbeat_at=timezone.now())

    def elapsed_seconds():
        return max(0.0,time.monotonic()-worker_started)

    try:
        run_context=((run.criteria or {}).get('run_context') or {})
        usage_kwargs={'campaign_id':run.campaign_id,'campaign_run_id':run.pk,'campaign_label':run.campaign.name,'operation':'campaign','discovery_mode':mode,'forum_only':forum_only,'selectivity':dict((run.criteria or {}).get('selectivity') or {})}
        if run_context.get('kind')=='custom_instructions' and str(run_context.get('text') or '').strip():
            usage_kwargs['custom_instructions']=str(run_context.get('text') or '').strip()[:2000]
        if run_context.get('kind')=='custom_instructions':
            usage_kwargs['preferred_company_countries']=list(run_context.get('preferred_company_countries') or [])[:20]
            usage_kwargs['excluded_company_countries']=list(run_context.get('excluded_company_countries') or [])[:20]
        with scoped_usage_context(**usage_kwargs):
            if forum_only:
                run.query_plan={'discovery_mode':mode,'strategy':'idle-only forum browse','forum_only':True,'primary_throughput_isolated':True}
            elif mode=='cloud_web':
                # Do not build the Local AI Discovery query plan: that planner may invoke local AI
                # for aliases. Cloud discovery owns its deterministic/profile-derived planning.
                run.query_plan={'discovery_mode':'cloud_web','strategy':'role-specific Cloud Web research'}
            else:
                run.query_plan=build_campaign_query_plan(
                    run.campaign,
                    max_queries=run.campaign.queries_per_rotation or _safe_setting_int(settings_row,'keywords_per_run',12,minimum=1),
                )
            run.heartbeat_at=timezone.now(); run.stage=('Browsing forum sources' if forum_only else ('Search query generation' if mode!='cloud_web' else 'Preparing context')); run.save(update_fields=['query_plan','heartbeat_at','stage'])
            result=run_campaign(
                run.campaign,progress_callback=progress,should_stop=stopped,
                rotation_offset=int((run.criteria or {}).get('rotation_offset',0) or 0),
                discovery_mode=mode,forum_only=forum_only,
            )
        result={**(result or {}),'run_duration_seconds':round(elapsed_seconds(),3),'discovery_mode':mode,'selectivity':dict((run.criteria or {}).get('selectivity') or {}),'scoutbox_version':run.criteria.get('scoutbox_version',''),'worker_id':run.criteria.get('worker_id','')}
        if forum_only:
            message=f"Completed Forum browse: {result.get('unique',0)} new opportunities · {result.get('new_leads',0)} new leads"
        elif mode=='cloud_web' and int(result.get('unique') or 0)==0:
            if int(result.get('cloud_urls_returned') or 0)>0:
                message=f"Completed: no eligible remote opportunities · {result.get('new_leads',0)} new leads"
            else:
                message='Completed: no matching Cloud Web candidates found'
        else:
            message=f"Completed: {result.get('unique',0)} new opportunities · {result.get('new_leads',0)} new leads"
        # Compare-and-set finalization prevents a late worker from reviving a watchdog-stopped run.
        finished=timezone.now()
        updated=CampaignRun.objects.filter(pk=run.pk,status='running').update(
            status='completed',progress=100,message=message,result=result,finished_at=finished,heartbeat_at=finished,stage='Completed',
            execution_provider=str(result.get('execution_provider') or execution_provider)[:80],execution_model=str(result.get('execution_model') or execution_model)[:200],stall_reason='')
        if not updated:
            run.refresh_from_db()
            return {'stopped':run.status=='stopped','status':run.status,'run_duration_seconds':result['run_duration_seconds']}
        return result
    except CampaignStopped:
        duration=round(elapsed_seconds(),3)
        forum_preempted=bool(forum_only and _primary_discovery_waiting())
        stop_message='Yielded to primary discovery' if forum_preempted else 'Stopped by user'
        stop_reason='forum_yielded_to_primary' if forum_preempted else 'user_stop'
        CampaignRun.objects.filter(pk=run.pk,status__in=['running','stopping']).update(
            status='stopped',message=stop_message,finished_at=timezone.now(),heartbeat_at=timezone.now(),
            result={**(run.result or {}),'run_duration_seconds':duration,'discovery_mode':mode,'stopped_reason':stop_reason,'forum_only':forum_only})
        return {'stopped':True,'reason':stop_reason,'run_duration_seconds':duration}
    except LocalAILaneBusy as exc:
        finished=timezone.now()
        result=dict(run.result or {})
        if forum_only:
            # Forum passes are optional idle-time work. Never turn Local AI contention
            # into a deferred primary-style retry or queue pressure; simply yield and let
            # a later idle scheduler tick try again.
            result.update({'stopped_reason':'forum_yielded_local_ai','timeout_reason':str(exc),'forum_only':True,'retryable':False})
            CampaignRun.objects.filter(pk=run.pk,status='running').update(
                status='stopped',progress=max(0,min(99,int(run.progress or 0))),finished_at=finished,heartbeat_at=finished,
                message='Yielded — Local AI capacity reserved for primary discovery',stage='Forum yielded',
                error='',stall_reason='',result=result,criteria=run.criteria)
            return {'stopped':True,'reason':'forum_yielded_local_ai','retryable':False,'run_duration_seconds':round(elapsed_seconds(),3)}
        result.update({'stopped_reason':'local_ai_lane_busy','timeout_reason':str(exc),'deferred_local_ai':True,'retryable':True})
        run.criteria=dict(run.criteria or {})
        run.criteria['deferred_local_ai']=True
        run.criteria['retryable']=True
        CampaignRun.objects.filter(pk=run.pk,status='running').update(
            status='stopped',progress=max(0,min(99,int(run.progress or 0))),finished_at=finished,heartbeat_at=finished,
            message='Deferred — local AI lane busy; will retry later',stage='Local AI deferred',
            error='',stall_reason='',result=result,criteria=run.criteria)
        return {'stopped':True,'reason':'local_ai_lane_busy','retryable':True,'run_duration_seconds':round(elapsed_seconds(),3)}
    except CloudRateLimited as exc:
        duration=round(elapsed_seconds(),3)
        retry_after=max(30,int(getattr(exc,'retry_after_seconds',300) or 300))
        retry_at=timezone.now()+timedelta(seconds=retry_after)
        provider=str(getattr(exc,'provider','cloud') or 'cloud').title()
        if forum_only:
            # Idle Forum passes do not back off/retry against a rate-limited Cloud route.
            # Stop quietly and preserve scheduler/Cloud retry capacity for primary work.
            message=f'Forum pass yielded — {provider} is rate limited'
            CampaignRun.objects.filter(pk=run.pk,status__in=['queued','running','stopping']).update(
                status='stopped',message=message[:500],finished_at=timezone.now(),heartbeat_at=timezone.now(),
                stall_reason='',
                result={**(run.result or {}),'stopped_reason':'forum_yielded_cloud_rate_limit','forum_only':True,
                        'retry_after_seconds':retry_after,'retry_at':retry_at.isoformat(),
                        'provider':str(getattr(exc,'provider','') or ''),'model':str(getattr(exc,'model','') or ''),
                        'run_duration_seconds':duration,'discovery_mode':mode})
            return {'stopped':True,'reason':'forum_yielded_cloud_rate_limit','retryable':False,'run_duration_seconds':duration}
        message=f'{provider} rate limit did not clear after automatic backoff. Run stopped; retry after {timezone.localtime(retry_at).strftime("%H:%M:%S")}.'
        CampaignRun.objects.filter(pk=run.pk,status__in=['queued','running','stopping']).update(
            status='stopped',message=message[:500],finished_at=timezone.now(),heartbeat_at=timezone.now(),
            stall_reason='Cloud provider rate limited',
            result={**(run.result or {}),'stopped_reason':'cloud_provider_rate_limited','retry_after_seconds':retry_after,
                    'retry_at':retry_at.isoformat(),'provider':str(getattr(exc,'provider','') or ''),
                    'model':str(getattr(exc,'model','') or ''),'run_duration_seconds':duration,'discovery_mode':mode})
        return {'stopped':True,'reason':'cloud_provider_rate_limited','retry_after_seconds':retry_after,'retry_at':retry_at.isoformat(),'run_duration_seconds':duration}
    except (SearchProvidersUnavailable, CloudWebUnavailable) as exc:
        duration=round(elapsed_seconds(),3)
        if isinstance(exc,SearchProvidersUnavailable):
            reason=exc.stopped_reason; extra={'provider_selection':exc.provider_selection}
        else:
            reason='cloud_web_unavailable'; extra={}
        CampaignRun.objects.filter(pk=run.pk,status__in=['queued','running','stopping']).update(
            status='stopped',message=str(exc)[:500],finished_at=timezone.now(),
            result={**(run.result or {}),'stopped_reason':reason,'run_duration_seconds':duration,'discovery_mode':mode,**extra})
        return {'stopped':True,'reason':reason,'run_duration_seconds':duration,**extra}
    except Exception as exc:
        duration=round(elapsed_seconds(),3)
        # A stop request/watchdog wins over a late exception from an external call.
        if CampaignRun.objects.filter(pk=run.pk,status__in=['stopping','stopped']).exists():
            CampaignRun.objects.filter(pk=run.pk,status='stopping').update(status='stopped',finished_at=timezone.now(),message='Stopped by user')
            return {'stopped':True,'run_duration_seconds':duration}
        failed_at=timezone.now()
        partial=_campaign_partial_discovery_result(run, now=failed_at)
        CampaignRun.objects.filter(pk=run.pk).update(
            status='failed',error=str(exc),message=('Campaign failed — partial discoveries saved' if partial.get('partial_result_finalized') else 'Campaign failed'),finished_at=failed_at,heartbeat_at=failed_at,
            stall_reason=str(exc)[:500],execution_provider=execution_provider,execution_model=execution_model,
            result={**(run.result or {}),**partial,'run_duration_seconds':duration,'discovery_mode':mode,'execution_provider':execution_provider,'execution_model':execution_model})
        raise


@shared_task(bind=True)
def import_text_job(self, job_id, text):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Interpreting pasted application history')
    try:
        job.progress=20; job.save(update_fields=['progress'])
        created=parse_lines(text,'text')
        _job_done(job,{'created':len(created),'candidate_ids':[x.pk for x in created]},f'Found {len(created)} proposed application(s)')
        return job.result
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task(bind=True)
def import_document_job(self, job_id, storage_path, original_name):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,f'Interpreting {original_name}')
    try:
        class StoredUpload:
            def __init__(self, fh, name): self._fh=fh; self.name=name
            def read(self,*a,**k): return self._fh.read(*a,**k)
            def seek(self,*a,**k): return self._fh.seek(*a,**k)
        job.progress=15; job.save(update_fields=['progress'])
        with default_storage.open(storage_path,'rb') as fh:
            created=parse_uploaded(StoredUpload(fh,original_name),'document')
        try: default_storage.delete(storage_path)
        except Exception: pass
        _job_done(job,{'created':len(created),'candidate_ids':[x.pk for x in created]},f'Found {len(created)} proposed application(s)')
        return job.result
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task(bind=True)
def mailbox_import_job(self, job_id):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Scanning application mailbox')
    try:
        result=sync_mailbox(); _job_done(job,result if isinstance(result,dict) else {'result':str(result)},'Mailbox scan completed'); return result
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task(bind=True)
def local_accelerator_probe_job(self, job_id):
    """Automatically identify whether local Ollama inference is accelerator-backed.

    Test Selection is not a prerequisite for Local AI readiness. This lightweight probe
    runs once when ScoutBox has a working Ollama installation but no current accelerator
    evidence. It records evidence on the Ollama provider configuration for readiness use.
    """
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Identifying local accelerator…')
    try:
        cfg=AIProviderConfig.objects.filter(provider='ollama',enabled=True).first()
        if not cfg: raise RuntimeError('Ollama is disabled or not configured.')
        models=ollama_service.list_models() or []
        if not models: raise RuntimeError('No local Ollama model is installed.')
        # Prefer the smallest installed model so automatic identification is quick and
        # does not unnecessarily load a large model merely to prove accelerator use.
        def _size(row):
            try:return int((row or {}).get('size') or 0)
            except Exception:return 0
        ordered=sorted(models,key=lambda x:(_size(x) or 10**30,str((x or {}).get('name') or (x or {}).get('model') or '')))
        model=str((ordered[0] or {}).get('name') or (ordered[0] or {}).get('model') or '').strip()
        if not model: raise RuntimeError('No usable local Ollama model is installed.')
        answer,data=ollama_service.generate('Reply with exactly: OK',model=model,stage='local_accelerator_probe',timeout=90,max_output_tokens=4,metadata_extra={'automatic':True})
        evidence=_ollama_accelerator_evidence()
        host=local_accelerator_state()
        # A successful local Ollama request on a positively identified Apple Silicon
        # host is accelerator-backed even though macOS uses unified memory and may not
        # expose a discrete VRAM counter. For other hosts require direct GPU evidence.
        validated=bool(evidence.get('validated') or (host.get('apple_silicon') and str(answer or '').strip()))
        conclusive=bool(validated or evidence.get('vram_bytes') or host.get('detected'))
        probe={
            'at':timezone.now().isoformat(),'ok':validated,'conclusive':conclusive,
            'model':model,'label':evidence.get('label') or host.get('label') or '',
            'vram_bytes':int(evidence.get('vram_bytes') or 0),
            'apple_silicon':bool(host.get('apple_silicon')),
            'host_os_label':host.get('host_os_label') or '',
            'host_platform':host.get('host_platform') or '',
        }
        caps=dict(cfg.capabilities or {}); caps['local_accelerator_probe']=probe; cfg.capabilities=caps; cfg.save(update_fields=['capabilities'])
        result={'ok':validated,'kind':'local_accelerator_probe','model':model,'accelerator':probe}
        if validated:
            _job_done(job,result,f"Local accelerator identified{': '+probe['label'] if probe['label'] else ''}")
        else:
            # A successful inference without enough host/GPU evidence is still unknown,
            # not proof of CPU-only execution. Keep readiness in Identifying state.
            _job_done(job,result,'Local inference works; accelerator identity is still being identified')
        try: ai_compute_readiness(force=True)
        except Exception: pass
        return result
    except Exception as exc:
        try:
            cfg=AIProviderConfig.objects.filter(provider='ollama').first()
            if cfg:
                caps=dict(cfg.capabilities or {}); caps['local_accelerator_probe']={'at':timezone.now().isoformat(),'ok':False,'conclusive':False,'error':str(exc)[:500]}; cfg.capabilities=caps; cfg.save(update_fields=['capabilities'])
        except Exception: pass
        _job_fail(job,exc)
        try: ai_compute_readiness(force=True)
        except Exception: pass
        return {'ok':False,'error':str(exc)}


@shared_task(bind=True)
def ai_provider_test_job(self, job_id, provider, prompt=''):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,f'Testing {provider}')
    try:
        result=test_provider(provider,prompt=prompt or None)
        if result.get('state')=='limit_reached':
            _job_done(job,result,'Not executed — Cloud AI limit reached')
        elif result.get('ok'):
            _job_done(job,result,result.get('message') or 'Provider test succeeded')
        else:
            job.status='failed'; job.finished_at=timezone.now(); job.progress=100; job.message='Provider test failed'; job.error=str(result.get('message') or 'Provider test failed'); job.result=result; job.save()
        # Refresh the shared readiness cache immediately so the global status icon and
        # campaign launch gate agree with the test the user just completed.
        try: ai_compute_readiness(force=True)
        except Exception: pass
        return result
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task(bind=True)
def ollama_test_job(self, job_id, mode='connection', model='', prompt=''):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Testing Ollama')
    try:
        if mode=='chat':
            answer,data=ollama_service.generate(prompt or 'Briefly explain what ScoutBox does.',model=model or None,stage='lab_ollama_test',timeout=90,max_output_tokens=500)
            evidence=_ollama_accelerator_evidence()
            accelerator_validated=evidence['validated']; accelerator_label=evidence['label']; accelerator_vram_bytes=evidence['vram_bytes']
            result={'ok':True,'kind':'ollama_chat','model':data.get('model') or model,'answer':answer,'tokens_in':data.get('prompt_eval_count',0),'tokens_out':data.get('eval_count',0),'accelerator_validated':accelerator_validated,'accelerator_label':accelerator_label,'accelerator_vram_bytes':accelerator_vram_bytes}
            _job_done(job,result,'Ollama response received')
        else:
            d=ollama_service.diagnostics(); result={'kind':'ollama_diagnostics',**d}
            if d.get('ok'):
                _job_done(job,result,d.get('message') or 'Ollama reachable')
            else:
                job.status='failed'; job.finished_at=timezone.now(); job.progress=100; job.message='Ollama test failed'; job.error=str(d.get('message') or 'Ollama unavailable'); job.result=result; job.save()
        try: ai_compute_readiness(force=True)
        except Exception: pass
        return result
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task(bind=True)
def email_profile_test_job(self, job_id, profile_id, action, recipient='', subject='', body=''):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Testing email configuration')
    try:
        profile=EmailProfile.objects.get(pk=profile_id); result={}
        if action in ('imap','imap_config'):
            im=imap_connect(profile); im.logout()
            rows=imap_folders(profile)
            result={'message':f'IMAP connection succeeded · {len(rows)} folder(s) detected.','folders':rows}
        elif action=='smtp':
            if outgoing_method(profile)=='resend':
                raise RuntimeError('This External Mail profile uses Resend API, not SMTP. Use the outgoing send test.')
            smtp=smtplib.SMTP(profile.smtp_host,profile.smtp_port,timeout=10); smtp.ehlo()
            if profile.smtp_tls: smtp.starttls(); smtp.ehlo()
            if profile.smtp_username: smtp.login(profile.smtp_username,decrypt(profile.smtp_password_enc))
            smtp.quit(); result={'message':'Notification SMTP connection succeeded.'}
        elif action=='folders':
            rows=imap_folders(profile); result={'message':'IMAP folders refreshed.','folders':rows}
        elif action=='populate_test':
            count=populate_test_messages(profile)
            result={'message':f'Generated {count} IMAP test emails — one each in Inbox, Drafts and Sent.','count':count}
        elif action=='send':
            if not recipient: raise RuntimeError('Enter a test recipient.')
            send_notification(recipient,subject or f'{settings.PORTAL_SHORT_NAME} outgoing-mail test',body or f'This is an outgoing-mail test from the {profile.get_template_display()} profile.',profile=profile)
            result={'message':f'Test notification sent to {recipient} via {outgoing_server_label(profile)}.'}
        else:
            raise RuntimeError('Unknown email test.')
        _job_done(job,result,result['message']); return result
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task(bind=True)
def search_provider_test_job(self, job_id, source_id, force_public=False, query='ScoutBox test', service=''):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Testing search provider')
    try:
        source=SearchSource.objects.get(pk=source_id)
        if service and source.name=='SearchAPI · Google Jobs':
            from .services.search import searchapi_source
            source=searchapi_source(service) or source
        result=test_search_provider(source,query=query or 'ScoutBox test',force_public=bool(force_public),limit=5)
        if result.get('ok'):
            _job_done(job,{'source_id':source.pk,**result},result.get('message') or 'Search provider test passed')
        else:
            job.status='failed'; job.finished_at=timezone.now(); job.progress=100; job.message='Search provider test failed'; job.error=result.get('message','Unknown error'); job.result={'source_id':source.pk,**result}; job.save()
        return result
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task(bind=True)
def diagnostic_search_job(self, job_id, source_id=None, keyword='', cloud_route_lane='primary'):
    """Small non-persistent discovery test based on the real Resume/profile configuration."""
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Building a small Resume-based test search')
    try:
        cfg=PortalSettings.objects.get_or_create(pk=1)[0]
        keyword=str(keyword or '').strip()[:240]
        profile=build_search_profile()
        top=[x.get('term') for x in profile.get('skills',[])[:6] if x.get('term')]
        role_names=[x.get('role') for x in profile.get('role_families',[])[:3] if x.get('role')]
        dummy=Campaign(
            name='Test discovery', location='', locations=[], role_families=', '.join(role_names),
            technologies=', '.join(top), engagement_types='contract, part-time, full-time',
            negative_constraints='', extra_text=(f'Test keyword: {keyword}' if keyword else ''), recency_days=30, source_names=[]
        )
        rows=[]; errors=[]; queries=[]; stages=[{'stage':'Candidate profile','status':'ok','detail':f'{len(top)} skill terms · {len(role_names)} role families','output':{'profile_terms':top,'role_families':role_names}}]
        job.progress=25; job.message='Testing discovery providers'; job.save(update_fields=['progress','message'])
        use_cloud=(cfg.discovery_mode=='cloud_web')
        providers=[]; cloud={}
        if use_cloud:
            # Test Discovery is one role focus. Skills/preferences are supplied separately
            # by Cloud discovery's candidate brief rather than mashed into a pseudo-role.
            role_focus=keyword or (role_names[0] if role_names else 'Specialist Software Engineer')
            cloud_instruction=f'For this test, concentrate on the primary role: {role_focus}.'
            dummy.extra_text=''
            with scoped_usage_context(cloud_route_lane=(cloud_route_lane or 'primary')):
                cloud=cloud_discover(dummy,max_results=min(10,int(cfg.cloud_test_candidates or 10)),test=True,test_instruction=role_focus)
            queries=cloud.get('queries',[])
            cloud_rows=cloud.get('results',[])[:12]
            rows=[{'provider':cloud.get('provider','Cloud AI'),'title':r.get('title',''),'url':r.get('url',''),'snippet':r.get('snippet','')[:600]} for r in cloud_rows]
            stages.append({'stage':'Cloud Web Discovery','status':'ok' if rows else 'warning','detail':f'{len(rows)} result(s) returned','output':{'provider':cloud.get('provider','Cloud AI'),'model':cloud.get('model',''),'research_instruction':cloud_instruction,'queries':queries,'results':rows}})
        else:
            if keyword:
                queries=[keyword]
                stages.append({'stage':'Test keyword','status':'ok','detail':'Using the keyword entered for this diagnostic','output':{'queries':queries}})
            else:
                # Backward compatibility for older queued jobs created before 0.8.43.
                plan=build_campaign_query_plan(dummy,max_queries=min(4,max(1,cfg.keywords_per_run)))
                queries=[x.get('query','') for x in plan.get('queries',[])[:4]]
                stages.append({'stage':'Query planning','status':'ok' if queries else 'warning','detail':f'{len(queries)} test query/queries built','output':{'queries':queries}})
            provider_budget_override=False
            if source_id:
                selected=SearchSource.objects.filter(pk=source_id,enabled=True).first()
                providers=[selected] if selected else []
            else:
                # Backward compatibility for an older queued task without an explicit engine.
                providers=choose_providers(limit=4)
                if not providers:
                    providers=choose_providers(limit=4,ignore_budget=True)
                    provider_budget_override=bool(providers)
            if not providers:
                stages.append({'stage':'Provider selection','status':'error','detail':'The selected search provider is unavailable','output':{'enabled':[],'selected_source_id':source_id}})
            else:
                chosen=providers[0].name if source_id else ', '.join(x.name for x in providers)
                stages.append({'stage':'Provider selection','status':'warning' if provider_budget_override else 'ok','detail':(('Selected search engine: '+chosen) if source_id else ('Enabled providers found; diagnostic is bypassing temporary provider budget/backoff.' if provider_budget_override else f'{len(providers)} campaign-eligible provider(s) selected.')),'output':{'providers':[x.name for x in providers],'selected_source_id':source_id,'budget_override':provider_budget_override}})
            for source in providers:
                provider_output=[]; provider_errors=[]
                for query in queries[:1] if keyword else queries[:2]:
                    # Use the same adapter execution function as campaigns. The diagnostic
                    # usage category keeps the traffic distinguishable in Resource Usage.
                    found,err=search_source(source,query,limit=5,usage_category='lab',ignore_budget=True)
                    if err:
                        msg=f'{source.name}: {err}'; errors.append(msg); provider_errors.append({'query':query,'error':err})
                    else:
                        parsed=[{'provider':source.name,'query':query,'title':r.get('title',''),'url':r.get('url',''),'snippet':r.get('snippet','')[:600]} for r in found[:5]]
                        rows.extend(parsed); provider_output.extend(parsed)
                stages.append({'stage':source.name,'status':'error' if provider_errors and not provider_output else ('warning' if provider_errors or not provider_output else 'ok'),'detail':f'{len(provider_output)} result(s), {len(provider_errors)} error(s)','output':{'results':provider_output,'errors':provider_errors}})
        selected_provider=(cloud.get('provider','Cloud AI') if use_cloud else (providers[0].name if providers else ''))
        result={'mode':'cloud_web' if use_cloud else cfg.discovery_mode,'selected_provider':selected_provider,'criteria':{'profile_terms':top,'role_families':role_names,'test_keyword':keyword,'cloud_research_instruction':cloud_instruction if use_cloud else '','cloud_route_lane':cloud_route_lane if use_cloud else ''},'queries':queries,'results':rows[:20],'errors':errors,'stages':stages}
        _job_done(job,result,f'Test complete: {len(rows[:20])} result(s)'); return result
    except CloudLimitReached as exc:
        result={'state':'limit_reached','limit_name':exc.limit_name,'used':exc.used,'limit':exc.limit,'message':str(exc),'results':[],'stages':[{'stage':'Cloud AI safety limits','status':'limit_reached','detail':str(exc),'output':{'used':exc.used,'limit':exc.limit}}]}
        _job_done(job,result,'Not executed — Cloud AI limit reached'); return result
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task(bind=True)
def pipeline_model_test_job(self, job_id, route_snapshot=None, discovery_mode=''):
    """Validate every resolved pipeline route and persist progress after each attempt.

    Local AI Discovery URL discovery validates two independent concerns: the configured
    primary/fallback model routes and several enabled search engines.  The former makes
    the per-route status icons meaningful; the latter prevents one blocked engine from
    causing a false URL-discovery failure.
    """
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Validating pipeline models')
    try:
        cfg=PortalSettings.objects.get_or_create(pk=1)[0]
        discovery_mode=(discovery_mode or cfg.discovery_mode or 'source_guided').strip()
        route_snapshot=route_snapshot if isinstance(route_snapshot,dict) else None
        stage_names=[s for s in STAGES if s!='chatbot']
        effective_bundles=bundle_owners(route_snapshot,discovery_mode)

        def snapshot_route(stage):
            """Resolve the exact selection submitted by the Discovery form.

            A blank primary means Automatic, so resolve it the same way production
            routing does. Test Selection now saves the browser selections before this
            worker starts, so normal runs use the persisted configuration path.
            """
            raw=dict((route_snapshot or {}).get(stage) or {}) if route_snapshot is not None else None
            if discovery_mode=='cloud_web':
                # Cloud Web has an independent provider + Primary/Failover pair for every
                # pipeline stage. Never read the Local Discovery snapshot in this mode.
                return cloud_discovery_route(stage=stage)
            if raw is None:
                return route_for_stage(stage) or {}
            defaults=STAGE_TOKEN_DEFAULTS.get(stage,STAGE_TOKEN_DEFAULTS['general'])
            route={
                'max_input_tokens':raw.get('max_input_tokens') or defaults['max_input_tokens'],
                'max_output_tokens':raw.get('max_output_tokens') or defaults['max_output_tokens'],
            }
            if raw.get('provider'):
                route.update({'provider':raw.get('provider'),'model':raw.get('model') or ''})
            else:
                # Automatic must resolve through the same <=12B-aware production
                # route selection used by campaigns, otherwise validation can test a
                # different (and much slower) Ollama default model.
                resolved=route_for_stage(stage) or {}
                if resolved.get('provider'):
                    route.update({'provider':resolved.get('provider'),'model':resolved.get('model') or ''})
            if raw.get('fallback_provider'):
                route.update({'fallback_provider':raw.get('fallback_provider'),'fallback_model':raw.get('fallback_model') or ''})
            return route

        def stamp(dt=None):
            return timezone.localtime(dt or timezone.now()).strftime('%d/%m/%Y %H:%M:%S')

        result={
            'route_signature':pipeline_route_signature(discovery_mode,route_snapshot),
            'discovery_mode':discovery_mode,
            'test_schema':3,
            'stages':[], 'ok_count':0, 'failed_count':0, 'route_warning_count':0,
            'current_stage':'', 'in_progress':True,
            'started_at':stamp(),
        }

        def recalc():
            complete=[x for x in result['stages'] if x.get('complete')]
            result['ok_count']=sum(1 for x in complete if x.get('status')=='ok')
            result['failed_count']=sum(1 for x in complete if x.get('status')!='ok')
            # Only model-route failures are route warnings. Search-provider probe
            # failures are reported separately and should not be mislabeled as a
            # primary/fallback model problem.
            result['route_warning_count']=sum(
                1 for x in complete for a in (x.get('attempts') or [])
                if a.get('role') in ('primary','fallback') and a.get('ok') is False
            )

        def persist(progress=None,message=None):
            recalc()
            if progress is not None: job.progress=max(1,min(99,int(progress)))
            if message is not None: job.message=str(message)[:500]
            job.result=result
            job.save(update_fields=['progress','message','result'])

        def test_timeout(provider, model):
            # Local models need a larger compatibility-test window than cloud APIs.
            # A timeout is reported as a speed warning, not as model incompatibility.
            if provider!='ollama':
                return 45
            match=re.search(r'(?<![\d.])(\d+(?:\.\d+)?)\s*[bB](?![A-Za-z])',str(model or ''))
            try: size=float(match.group(1)) if match else 0.0
            except Exception: size=0.0
            if size>12: return 150
            if size>8: return 105
            return 75

        def timed_model_attempt(stage, role, provider, model, route):
            started_dt=timezone.now(); started_clock=time.monotonic(); timeout_seconds=test_timeout(provider,model)
            attempt={
                'role':role,'provider':provider or '','model':model or '',
                'ok':False,'state':'testing','detail':'Testing…','started_at':stamp(started_dt),
                'timeout_seconds':timeout_seconds,
            }
            try:
                prompt='ScoutBox compatibility test. Reply with exactly: OK'
                limits={'max_input_tokens':route.get('max_input_tokens'),'max_output_tokens':route.get('max_output_tokens')}
                with scoped_usage_context(operation='ad_hoc',subject_type='model_test',subject_id=stage):
                    if stage=='url_scrape' and discovery_mode=='cloud_web':
                        response=web_search_with(
                            provider,model,
                            'ScoutBox capability test: find the official Python programming language website and return one concise result.',
                            stage=stage,timeout=timeout_seconds,limits_override=limits,budget_operation='ad_hoc',
                        )
                        text=response[0] if isinstance(response,tuple) else response
                    else:
                        text=generate_with(
                            provider,model,prompt,stage=stage,timeout=timeout_seconds,
                            subject={'type':'model_test','id':stage,'label':f'{stage} {role} model validation','budget_operation':'ad_hoc'},
                            limits_override=limits,
                        )
                ok=bool(str(text or '').strip())
                attempt.update({'ok':ok,'state':'ok' if ok else 'error','detail':'Response received' if ok else 'Request completed with an empty response'})
                # Capture accelerator evidence while the tested Ollama model is still
                # loaded. /api/ps exposes size_vram on GPU-backed local inference and
                # is more reliable here than a later host-telemetry sample in Docker.
                if ok and provider == 'ollama':
                    evidence=_ollama_accelerator_evidence()
                    attempt['accelerator_validated']=evidence['validated']
                    if evidence['vram_bytes'] > 0: attempt['accelerator_vram_bytes']=evidence['vram_bytes']
                    if evidence['label']: attempt['accelerator_label']=evidence['label']
            except CloudLimitReached as exc:
                attempt.update({'ok':None,'state':'limit_reached','detail':f'Not executed — {exc}'[:1000],'limit_name':exc.limit_name,'used':exc.used,'limit':exc.limit})
            except Exception as exc:
                detail=str(exc)[:1000]
                timeout_like=('timeout' in exc.__class__.__name__.lower() or 'timed out' in detail.lower() or 'read timeout' in detail.lower())
                if timeout_like:
                    attempt.update({'ok':None,'state':'timeout','detail':f'Timed out after {timeout_seconds}s; the model may be usable but too slow for this test window. {detail}'[:1000]})
                else:
                    attempt.update({'ok':False,'state':'error','detail':detail})
            ended_dt=timezone.now()
            attempt.update({
                'ended_at':stamp(ended_dt),
                'duration_seconds':round(max(0.0,time.monotonic()-started_clock),3),
            })
            return attempt

        persist(2,'Preparing stage validation')
        total=max(1,len(stage_names))
        for index,stage in enumerate(stage_names,1):
            stage_started_dt=timezone.now(); stage_started_clock=time.monotonic()
            base_progress=3+int((index-1)/total*92)
            result['current_stage']=stage
            stage_row={
                'stage':stage,'status':'running','complete':False,'provider':'','model':'','detail':'Testing…','attempts':[],
                'primary_state':'unknown','primary_title':'Not tested yet','fallback_state':'unknown','fallback_title':'Not tested yet',
                'started_at':stamp(stage_started_dt),
            }
            result['stages'].append(stage_row)
            persist(base_progress,f'Testing {stage.replace("_"," ")}')
            try:
                # Resolve and exercise the configured model routes for every stage,
                # including URL discovery.  Even in Local AI Discovery mode this is useful
                # compatibility validation for the routing table the user configured.
                route=snapshot_route(stage)
                pairs=[]; inherited=(effective_bundles.get(stage) or {})
                for role,pkey,mkey in (('primary','provider','model'),('fallback','fallback_provider','fallback_model')):
                    owner=inherited.get(role)
                    if owner:
                        detail=f"Bundled with {owner.get('stage','').replace('_',' ').title()} · {owner.get('provider','')} · {owner.get('model','')}"
                        stage_row['attempts'].append({'role':role,'provider':owner.get('provider',''),'model':owner.get('model',''),'ok':True,'state':'bundled','detail':detail,'bundled_from':owner.get('stage','')})
                        stage_row[role+'_state']='ok'; stage_row[role+'_title']=detail
                        if role=='primary': stage_row['provider']=owner.get('provider',''); stage_row['model']=owner.get('model','')
                    elif route.get(pkey):
                        pairs.append((role,route.get(pkey),route.get(mkey)))
                    elif role=='primary':
                        stage_row['primary_state']='warning'; stage_row['primary_title']='No enabled model resolves for this stage'
                    else:
                        stage_row['fallback_state']='na'; stage_row['fallback_title']='No fallback configured'

                for aindex,(role,provider,model) in enumerate(pairs,1):
                    stage_row[role+'_state']='testing'; stage_row[role+'_title']=f'Testing {provider} · {model or "default model"}'
                    stage_row['detail']=f'Testing {role} model route'
                    persist(base_progress+max(1,int((aindex-1)/max(1,len(pairs)+1)*(76/total))),f'Testing {stage.replace("_"," ")} · {role}')
                    attempt=timed_model_attempt(stage,role,provider,model,route)
                    stage_row['attempts'].append(attempt)
                    stage_row[role+'_state']='ok' if attempt['ok'] else 'warning'
                    stage_row[role+'_title']=' · '.join(x for x in [provider,model or '',attempt.get('detail','')] if x)
                    if role=='primary':
                        stage_row['provider']=provider or ''; stage_row['model']=model or ''
                    persist(base_progress+max(1,int(aindex/max(1,len(pairs)+1)*(76/total))),f'Tested {stage.replace("_"," ")} · {role}')

                primary=next((a for a in stage_row['attempts'] if a.get('role')=='primary'),None)
                fallback=next((a for a in stage_row['attempts'] if a.get('role')=='fallback'),None)
                model_usable=bool((primary and primary.get('ok')) or (fallback and fallback.get('ok')))

                # Local AI Discovery URL discovery also depends on real search providers.
                # Probe up to three engines and accept the provider portion when any
                # one of them returns parsed results.
                if stage=='url_scrape' and discovery_mode!='cloud_web' and not is_cloud_provider((route or {}).get('provider')):
                    providers=choose_providers(limit=3,preferred_only=True,ignore_budget=True)
                    if len(providers)<2:
                        seen={p.pk for p in providers}
                        for extra in choose_providers(limit=3,preferred_only=False,ignore_budget=True):
                            if extra.pk not in seen:
                                providers.append(extra); seen.add(extra.pk)
                            if len(providers)>=3: break
                    successful=0; query='embedded firmware engineer'
                    if not providers:
                        stage_row['search_provider_error']='No enabled search provider is configured for Local AI Discovery URL discovery'
                    for pindex,source in enumerate(providers[:3],1):
                        stage_row['detail']=f'Testing search provider {pindex}/{min(3,len(providers))}: {source.name}'
                        persist(base_progress+max(1,int((len(pairs)+pindex-1)/max(1,len(pairs)+len(providers[:3]))*(82/total))),stage_row['detail'])
                        attempt_started=timezone.now(); attempt_clock=time.monotonic()
                        try:
                            probe=test_search_provider(source,query=query,limit=3)
                            count=len(probe.get('results') or [])
                            ok=bool(probe.get('ok')) and count>0
                            if ok: successful+=1
                            attempt={
                                'role':f'search provider {pindex}','provider':source.name,'model':'','ok':ok,
                                'detail':probe.get('message') or (f'{count} parsed result(s)' if ok else 'No parsed results returned'),
                                'result_count':count,'latency_ms':probe.get('latency_ms',0),'mode':probe.get('mode',''),
                                'query':probe.get('query') or query,
                            }
                        except Exception as exc:
                            attempt={'role':f'search provider {pindex}','provider':source.name,'model':'','ok':False,'detail':str(exc)[:1000],'result_count':0}
                        attempt.update({
                            'started_at':stamp(attempt_started),'ended_at':stamp(),
                            'duration_seconds':round(max(0.0,time.monotonic()-attempt_clock),3),
                        })
                        stage_row['attempts'].append(attempt)
                        stage_row['search_provider_successes']=successful
                        stage_row['search_provider_tests']=pindex
                        persist(base_progress+max(1,int((len(pairs)+pindex)/max(1,len(pairs)+len(providers[:3]))*(82/total))),f'Tested URL discovery provider {pindex}/{len(providers[:3])}')

                    provider_usable=successful>0
                    stage_ok=bool(model_usable and provider_usable)
                    if not model_usable and provider_usable:
                        detail='Search providers are usable, but neither configured model route passed compatibility validation.'
                    elif model_usable and not provider_usable:
                        detail='Model route is usable, but no tested search provider returned parsed results.'
                    elif stage_ok:
                        detail=f'Compatible · {successful}/{len(providers[:3])} search providers returned parsed results'
                    else:
                        detail=stage_row.get('search_provider_error') or 'No usable model route or search provider was found.'
                    stage_row.update({'complete':True,'status':'ok' if stage_ok else 'warning','detail':detail})
                else:
                    failed_routes=[a for a in stage_row['attempts'] if a.get('role') in ('primary','fallback') and a.get('ok') is False]
                    timed_out_routes=[a for a in stage_row['attempts'] if a.get('role') in ('primary','fallback') and a.get('state')=='timeout']
                    if model_usable and failed_routes:
                        detail='Stage usable; '+('; '.join(f"{a.get('role','route').title()} failed: {a.get('detail','')}" for a in failed_routes))[:900]
                    elif model_usable and timed_out_routes:
                        detail='Stage usable; '+('; '.join(f"{a.get('role','route').title()} timed out: {a.get('detail','')}" for a in timed_out_routes))[:900]
                    elif model_usable:
                        detail='Compatible'
                    elif timed_out_routes and not failed_routes:
                        detail='Timeout / too slow; compatibility was not disproved. '+('; '.join(a.get('detail','') for a in timed_out_routes))[:850]
                    else:
                        detail='; '.join(a.get('detail','') for a in failed_routes)[:1000] or 'No tested route returned a usable response'
                    stage_row.update({'complete':True,'status':'ok' if model_usable else 'warning','detail':detail})
            except Exception as exc:
                stage_row.update({'complete':True,'status':'warning','detail':str(exc)[:1000]})
                if stage_row.get('primary_state') in ('unknown','testing'):
                    stage_row['primary_state']='warning'; stage_row['primary_title']=str(exc)[:1000]
            finally:
                stage_row['ended_at']=stamp()
                stage_row['duration_seconds']=round(max(0.0,time.monotonic()-stage_started_clock),3)
                persist(base_progress+max(2,int(84/total)),f'Completed {stage.replace("_"," ")}' if stage_row.get('status')=='ok' else f'{stage.replace("_"," ")} needs attention')

        result['current_stage']=''; result['in_progress']=False
        result['tested_at']=stamp()
        result['ended_at']=result['tested_at']
        recalc()
        message=f"Model validation complete: {result['ok_count']} compatible, {result['failed_count']} need attention"
        if result['route_warning_count']:
            message+=f" · {result['route_warning_count']} route warning(s)"
        _job_done(job,result,message)
        try: ai_compute_readiness(force=True)
        except Exception: pass
        return result
    except Exception as exc:
        if isinstance(job.result,dict):
            partial=dict(job.result); partial['in_progress']=False; partial['fatal_error']=str(exc)[:1000]; partial['ended_at']=timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M:%S'); job.result=partial; job.save(update_fields=['result'])
        _job_fail(job,exc); raise


@shared_task(bind=True)
def hidden_market_scan_job(self, job_id):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Scanning public technical signals')
    try:
        job.progress=10; job.save(update_fields=['progress'])
        def progress(done,total,message):
            # Keep the dashboard moving during the network-heavy scan instead of sitting
            # at 10% until every provider/page fetch has completed.
            pct=12+int(78*(max(0,done)/max(1,total)))
            BackgroundJob.objects.filter(pk=job.pk,status='running').update(progress=min(90,max(12,pct)),message=str(message or 'Scanning public technical signals')[:500])
        result=scan_hidden_market(progress_callback=progress,max_seconds=2400)
        suffix=' (time-bounded partial scan)' if result.get('partial') else ''
        _job_done(job,result,f"Scan complete{suffix}: {result.get('new_leads',0)} new lead(s) from {result.get('results_seen',0)} result(s)")
        # Refinement is intentionally asynchronous. The deterministic preliminary
        # summary is already visible, so a slow/failed AI provider never leaves a row
        # stuck at a blank "Summary pending" state.
        for lead_id in result.get('changed_lead_ids',[]) or []:
            lead=CompanyLead.objects.filter(pk=lead_id,user_deleted=False).first()
            if not lead: continue
            company_route=effective_route_for_stage('company_enrichment') or {}
            cloud_hidden=company_route.get('provider') in ('openai','gemini','openrouter')
            # Hidden Leads deliberately bypass JD Analysis. When their effective Company
            # Research route is cloud, that single grounded request also supplies the lead
            # summary/actionability judgment, so do not enqueue a redundant summary call.
            if not cloud_hidden:
                allowed,_=reserve_attempt(lead,'summary','initial')
                if allowed:
                    sj=BackgroundJob.objects.create(kind='summarize',label=f'Refine Hidden Lead: {lead.company}'[:300],message='Queued',result={'market_lead_id':lead.pk,'phase':'initial'})
                    task=market_lead_summary_job.delay(sj.pk,lead.pk,'initial'); sj.celery_task_id=task.id or ''; sj.save(update_fields=['celery_task_id'])
            allowed,_=reserve_attempt(lead,'company','initial')
            if allowed:
                cj=BackgroundJob.objects.create(kind='company_research',label=f'Hidden Lead research: {lead.company}'[:300],message='Queued',result={'lead_id':lead.pk,'hidden_lead':True,'phase':'initial','jd_analysis_bypassed':True})
                task=lead_company_research_job.delay(cj.pk,lead.pk,'initial'); cj.celery_task_id=task.id or ''; cj.save(update_fields=['celery_task_id'])
        return result
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task(bind=True)
def translate_lead_job(self, job_id, lead_id):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Translating lead evidence to English')
    try:
        lead=CompanyLead.objects.get(pk=lead_id,user_deleted=False)
        source=(lead.match_summary+'\n\n'+lead.evidence).strip()
        if not source: raise RuntimeError('No lead evidence is available to translate.')
        translated=generate('Translate the following technical/company evidence to natural English. Preserve meaning and structure. Do not add facts.\n\n'+source[:18000],stage='page_summary',timeout=120,subject={'type':'hidden lead','id':lead.pk,'label':lead.company}).strip()
        lead.evidence_translation=translated; lead.save(update_fields=['evidence_translation','updated_at'])
        _job_done(job,{'lead_id':lead.pk},'English translation ready'); return {'lead_id':lead.pk}
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task(bind=True)
def cold_draft_job(self, job_id, lead_id, provider='', model=''):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Preparing outreach draft')
    try:
        from portal.models import CompanyLead
        lead=CompanyLead.objects.get(pk=lead_id,user_deleted=False)
        app=generate_cold_draft(lead,provider or None,model or None)
        imap_saved=False; imap_uid=''; imap_error=''
        try:
            imap_uid=save_draft(app) or ''; imap_saved=True
        except Exception as mail_exc:
            # The ScoutBox record is the source of truth. Missing/unavailable IMAP must
            # not make Prepare Outreach appear to have lost the generated draft.
            imap_error=str(mail_exc)
        result={'lead_id':lead.pk,'application_id':app.pk,'imap_saved':imap_saved,'imap_uid':imap_uid,'imap_error':imap_error}
        message='Outreach prepared in Applications & Outreach'
        if imap_saved: message+=' and IMAP Drafts'
        elif imap_error: message+='; IMAP copy was not saved'
        _job_done(job,result,message); return result
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task(bind=True)
def market_lead_summary_job(self, job_id, lead_id, phase='manual'):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Refining Hidden Leads company summary')
    lead=None
    try:
        lead=CompanyLead.objects.get(pk=lead_id,user_deleted=False)
        evidence=lead.evidence or ''; page_title=''
        target=(lead.target_url or lead.source_url or '').strip()
        if target.startswith(('http://','https://')):
            try:
                parsed=urllib.parse.urlsplit(target); home=urllib.parse.urlunsplit((parsed.scheme,parsed.netloc,'/','',''))
                home_page=fetch_target(home,'','')
                if home_page.get('ok'):
                    page_title=(home_page.get('title') or '').strip(); home_text=(home_page.get('text') or '').strip()[:9000]
                    if home_text: evidence=(home_text+'\n\n'+evidence)[:18000]
            except Exception: pass
        with scoped_usage_context(campaign_id=_usage_ids_for_entity(lead)[0], campaign_run_id=_usage_ids_for_entity(lead)[1], operation=budget_operation_for_phase(phase), subject_type='hidden_lead', subject_id=str(lead.pk)):
            refined=short_company_summary(lead.company,page_title,evidence,lead.company_intel)
        if not refined:
            fallback=preliminary_company_summary(lead.company,page_title,evidence,[x.strip() for x in str(lead.match_summary or '').split(',') if x.strip()],company_intel=lead.company_intel)
            if fallback:
                lead.summary=fallback
                lead.save(update_fields=['summary','updated_at'])
            elif str(lead.summary or '').strip().casefold()=='summary pending.':
                # Do not persist a placeholder. With an empty stored summary, list/detail
                # rendering can show cleaned source prose while later research/refinement
                # remains free to replace it with a company-specific summary.
                lead.summary=''
                lead.save(update_fields=['summary','updated_at'])
            complete_attempt(lead,'summary',phase,'success','Rebuilt from available evidence')
            result={'market_lead_id':lead.pk,'refined':False}; _job_done(job,result,'Hidden Leads summary retained readable source text while refinement remains available'); return result
        lead.summary=refined; lead.save(update_fields=['summary','updated_at']); complete_attempt(lead,'summary',phase,'success')
        result={'market_lead_id':lead.pk,'refined':True}; _job_done(job,result,'Hidden Leads summary refined'); return result
    except CloudLimitReached as exc:
        if lead: complete_attempt(lead,'summary',phase,'skipped_budget',str(exc))
        result={'market_lead_id':lead_id,'state':'limit_reached','detail':str(exc)}; _job_done(job,result,'Not executed — Cloud AI limit reached'); return result
    except Exception as exc:
        if lead: complete_attempt(lead,'summary',phase,'failed',str(exc))
        _job_fail(job,exc); raise


def _maintenance_company_info_missing(opportunity):
    """Mirror the Company Info badge's unknown state without importing template code."""
    intel=getattr(opportunity,'company_intel',{}) or {}
    if not isinstance(intel,dict):
        return True
    structured=intel.get('structured') if isinstance(intel.get('structured'),dict) else {}
    if structured.get('domain_age_refresh_needed'):
        return True
    for key in ('founded_year','age_range','domain_age_label','size_range'):
        if str(structured.get(key) or '').strip():
            return False
    for item in (intel.get('facts') or []):
        if not isinstance(item,dict):
            continue
        label=str(item.get('label') or '').strip().casefold()
        value=str(item.get('value') or '').strip()
        if value and any(token in label for token in ('founded','established','domain age','size','employee')):
            return False
    return True


def _maintenance_company_location_missing(opportunity):
    """Company/HQ location belongs to Company Info, not Opportunity.country.

    Opportunity.country is the job/role country in 0.10.103.  Maintenance therefore
    checks only researched company-intel location fields and must never fill the role
    country from an employer HQ.
    """
    return not bool(_maintenance_location_from_company_intel(opportunity))


def _maintenance_location_from_company_intel(opportunity):
    intel=getattr(opportunity,'company_intel',{}) or {}
    if not isinstance(intel,dict):
        return ''
    structured=intel.get('structured') if isinstance(intel.get('structured'),dict) else {}
    candidates=[structured.get('location')]
    for item in (intel.get('facts') or []):
        if not isinstance(item,dict):
            continue
        label=str(item.get('label') or '').strip().casefold()
        if label in {'location','company location','headquarters','hq','base'} or 'headquarter' in label:
            candidates.append(item.get('value'))
    for candidate in candidates:
        text=' '.join(str(candidate or '').split()).strip()[:120]
        low=text.casefold()
        if not text:
            continue
        if 'remote' in low or 'home based' in low or 'home-based' in low or low in {'worldwide','global','anywhere','distributed'}:
            continue
        return text
    return ''


def _maintenance_remote_missing(opportunity):
    facts=getattr(opportunity,'extracted_facts',{}) or {}
    row=facts.get('remote_classification') if isinstance(facts,dict) else None
    status=str((row or {}).get('status') or 'unknown').strip().casefold() if isinstance(row,dict) else 'unknown'
    return status not in {'fully_remote','remote','hybrid','onsite'}


def _maintenance_post_age_missing(opportunity):
    label=str(getattr(opportunity,'freshness_label','') or '').strip()
    try:
        confidence=int(getattr(opportunity,'freshness_confidence',0) or 0)
    except Exception:
        confidence=0
    return (not label) or label in {'?','Age unknown'} or confidence<=0


def _maintenance_fit_confidence(opportunity):
    facts=getattr(opportunity,'extracted_facts',{}) or {}
    if not isinstance(facts,dict):
        return 0
    fc=facts.get('fit_classification') if isinstance(facts.get('fit_classification'),dict) else {}
    cloud=facts.get('cloud_research') if isinstance(facts.get('cloud_research'),dict) else {}
    for candidate in (fc.get('confidence'),cloud.get('confidence'),facts.get('confidence')):
        if candidate in (None,''):
            continue
        try:
            if isinstance(candidate,str) and not candidate.strip().isdigit():
                text=candidate.strip().casefold(); value=25 if text.startswith('low') else (60 if text.startswith('medium') else (85 if text.startswith('high') else 0))
            else:
                value=max(0,min(100,int(candidate)))
        except Exception:
            value=0
        if value:
            return value
    return 0


def _maintenance_fit_missing(opportunity):
    try:
        score=max(0,min(100,int(getattr(opportunity,'fit_score',0) or 0)))
    except Exception:
        score=0
    if score<=0:
        return True
    # The shared Fit renderer deliberately presents low-confidence Poor Fit as '?'.
    # Treat that visible uncertain state as rebuildable as well.
    confidence=_maintenance_fit_confidence(opportunity)
    return score<50 and confidence<45


def _maintenance_source_text(opportunity):
    facts=getattr(opportunity,'extracted_facts',{}) or {}
    source=(getattr(opportunity,'description','') or getattr(opportunity,'raw_search_snippet','') or '').strip()
    if not source and isinstance(facts,dict):
        summary=facts.get('ai_job_summary') if isinstance(facts.get('ai_job_summary'),dict) else {}
        source=str(summary.get('source_text') or '').strip()
    if source:
        return source[:30000]
    target=(getattr(opportunity,'target_url','') or getattr(opportunity,'url','') or '').strip()
    if not target:
        return ''
    try:
        page=fetch_target(target,getattr(opportunity,'title','') or '',getattr(opportunity,'raw_search_snippet','') or '',timeout=22)
        if page.get('ok'):
            return str(page.get('text') or '').strip()[:30000]
    except Exception:
        pass
    return ''


@shared_task(bind=True)
def rebuild_missing_ai_data_job(self, job_id, period='24h'):
    """Repair only visible unknown AI-derived fields for active Opportunities.

    This maintenance action is deliberately available only while Discovery Method is
    Cloud Web. Existing populated fields and workflow state are never overwritten.
    """
    job=BackgroundJob.objects.get(pk=job_id)
    job.celery_task_id=self.request.id or ''
    _job_start(job,'Inspecting records with missing AI data')
    try:
        cfg=PortalSettings.objects.get_or_create(pk=1)[0]
        if str(cfg.discovery_mode or '').strip().casefold()!='cloud_web':
            raise RuntimeError('Rebuild Missing AI Data is available only when Discovery Method is set to Cloud Web.')

        period=str(period or '24h').strip().casefold()
        if period=='today': period='24h'  # backward compatibility with queued pre-0.8.97 jobs
        allowed={'24h','3d','7d','14d','30d','all'}
        if period not in allowed:
            raise ValueError('Unsupported rebuild period.')
        now=timezone.now()
        start=None
        if period=='24h': start=now-timedelta(hours=24)
        elif period=='3d': start=now-timedelta(days=3)
        elif period=='7d': start=now-timedelta(days=7)
        elif period=='14d': start=now-timedelta(days=14)
        elif period=='30d': start=now-timedelta(days=30)

        qs=Opportunity.objects.filter(user_deleted=False,suppressed=False).order_by('pk')
        if start is not None:
            qs=qs.filter(first_seen_by_portal__gte=start)
        ids=list(qs.values_list('pk',flat=True))
        total=len(ids)
        stats={
            'maintenance_rebuild':True,'period':period,'records_inspected':0,
            'records_with_missing_data':0,'fields_attempted':0,'fields_rebuilt':0,
            'fields_already_populated':0,'fields_still_unknown':0,'errors':[],
        }
        profile=Profile.objects.get_or_create(pk=1)[0]

        for index,opportunity_id in enumerate(ids,1):
            job.refresh_from_db(fields=['status'])
            if job.status=='stopped':
                return {'stopped':True,**stats}
            opp=Opportunity.objects.get(pk=opportunity_id)
            before={
                'company':_maintenance_company_info_missing(opp),
                'company_location':_maintenance_company_location_missing(opp),
                'remote':_maintenance_remote_missing(opp),
                'post_age':_maintenance_post_age_missing(opp),
                'fit':_maintenance_fit_missing(opp),
                'summary':not bool(str(opp.list_highlight or '').strip()),
            }
            stats['records_inspected']+=1
            stats['fields_already_populated']+=sum(1 for missing in before.values() if not missing)
            if not any(before.values()):
                if total:
                    job.progress=max(1,min(99,int(index*100/total)))
                    job.message=f'Checked {index:,} of {total:,} records'
                    job.save(update_fields=['progress','message'])
                continue
            stats['records_with_missing_data']+=1

            # Company Info + Company Location share the same grounded Cloud Web research.
            # Snapshot non-target values because company research persists its result; this
            # maintenance operation may fill only fields that were visibly unknown before it.
            if before['company'] or before['company_location']:
                stats['fields_attempted']+=int(before['company'])+int(before['company_location'])
                old_company=opp.company
                old_country=opp.country
                old_company_intel=copy.deepcopy(opp.company_intel or {})
                try:
                    _cid,_rid=_usage_ids_for_entity(opp)
                    with scoped_usage_context(campaign_id=_cid,campaign_run_id=_rid,operation='manual_rebuild',subject_type='opportunity',subject_id=str(opp.pk)):
                        research_company(opp)
                    opp.refresh_from_db()
                    researched_intel=copy.deepcopy(opp.company_intel or {})
                    researched_location=_maintenance_location_from_company_intel(opp) if before['company_location'] else ''
                    # Company name is not a maintenance target. Company Info is retained only
                    # when it was missing; otherwise restore the pre-existing card verbatim.
                    opp.company=old_company
                    if not before['company']:
                        opp.company_intel=old_company_intel
                    else:
                        opp.company_intel=researched_intel
                    # Company/HQ location remains inside company_intel. Never overwrite
                    # the role-country field with employer-research location.
                    opp.country=old_country
                    opp.save(update_fields=['company','company_intel','country','updated_at'])
                    opp.refresh_from_db()
                except Exception as exc:
                    # Restore all snapshot values if company research failed after partially saving.
                    try:
                        opp.company=old_company; opp.country=old_country; opp.company_intel=old_company_intel
                        opp.save(update_fields=['company','country','company_intel','updated_at'])
                    except Exception:
                        pass
                    if len(stats['errors'])<25:
                        stats['errors'].append({'opportunity_id':opp.pk,'field':'company_info_location','error':str(exc)[:500]})

            # Post Age: refresh only when the displayed field is currently unknown.
            if before['post_age']:
                stats['fields_attempted']+=1
                try:
                    _cid,_rid=_usage_ids_for_entity(opp)
                    with scoped_usage_context(campaign_id=_cid,campaign_run_id=_rid,operation='manual_rebuild',subject_type='opportunity',subject_id=str(opp.pk)):
                        recompute(opp)
                    opp.refresh_from_db()
                except Exception as exc:
                    if len(stats['errors'])<25:
                        stats['errors'].append({'opportunity_id':opp.pk,'field':'post_age','error':str(exc)[:500]})

            # Fit + Remote share one classifier call. Snapshot every pre-existing value
            # and retain only fields that were visibly '?' before this maintenance run.
            if before['fit'] or before['remote']:
                stats['fields_attempted']+=int(before['fit'])+int(before['remote'])
                try:
                    from portal.services.enrichment import _llm_fit_remote
                    source=_maintenance_source_text(opp)
                    if not source:
                        raise RuntimeError('No source text is available for Fit/Remote rebuild.')
                    old_facts=copy.deepcopy(opp.extracted_facts or {})
                    old_fit=opp.fit_score
                    old_remote=opp.remote_text
                    old_status=opp.status
                    old_reason=opp.recommendation_reason
                    _cid,_rid=_usage_ids_for_entity(opp)
                    with scoped_usage_context(campaign_id=_cid,campaign_run_id=_rid,operation='manual_rebuild',subject_type='opportunity',subject_id=str(opp.pk)):
                        _llm_fit_remote(opp,source,profile)
                    new_facts=copy.deepcopy(opp.extracted_facts or {})
                    if not before['fit']:
                        if 'fit_classification' in old_facts: new_facts['fit_classification']=copy.deepcopy(old_facts['fit_classification'])
                        else: new_facts.pop('fit_classification',None)
                        opp.fit_score=old_fit
                    if not before['remote']:
                        if 'remote_classification' in old_facts: new_facts['remote_classification']=copy.deepcopy(old_facts['remote_classification'])
                        else: new_facts.pop('remote_classification',None)
                        opp.remote_text=old_remote
                    # A maintenance enrichment must never change workflow/recommendation state.
                    opp.status=old_status
                    opp.recommendation_reason=old_reason
                    opp.extracted_facts=new_facts
                    fields=['extracted_facts','updated_at']
                    if before['fit']: fields.append('fit_score')
                    if before['remote']: fields.append('remote_text')
                    opp.save(update_fields=list(dict.fromkeys(fields)))
                    opp.refresh_from_db()
                except Exception as exc:
                    if len(stats['errors'])<25:
                        stats['errors'].append({'opportunity_id':opp.pk,'field':'fit_remote','error':str(exc)[:500]})

            # Opportunity list Summary: Cloud mode asks the selected Cloud AI directly for
            # a compact candidate-fit sentence. Do not locally synthesize Cloud wording.
            if before['summary']:
                stats['fields_attempted']+=1
                try:
                    from portal.services.highlights import normalize_ai_fit_summary
                    source=_maintenance_source_text(opp)
                    if not source:
                        raise RuntimeError('No source text is available for Opportunity summary rebuild.')
                    route=cloud_discovery_route('primary',stage='first_filter')
                    preferences={
                        'high_priority':profile.high_priority_text or '',
                        'medium_priority':profile.medium_priority_text or '',
                        'low_priority':profile.low_priority_text or '',
                        'scope':profile.scope_json if isinstance(profile.scope_json,dict) else {},
                    }
                    prompt=(
                        'Write one compact technical Opportunity-list summary of what the role involves. '
                        "Prefer 25-40 words and never exceed 50 words. Ground every claim in the supplied role/JD; candidate preferences may guide which technical details are most useful, but do not add generic fit commentary. Do not end with a generic label such as 'fit', 'good fit', or 'technical fit'; state the concrete reason instead. "
                        'Mention concrete technologies, subsystems, tools, architectures, protocols, specialist responsibilities, or documentation audience when present. Avoid em dashes; use ordinary sentence punctuation. '
                        'If the fit is weak or adjacent, say that plainly. Do not repeat the company, do not quote a long JD passage, and do not use search-query wording. '
                        'Return only the summary sentence, with no label.\n\n'
                        f'CANDIDATE PREFERENCES: {json.dumps(preferences,ensure_ascii=False)}\n\n'
                        f'ROLE: {opp.title}\nCOMPANY: {opp.company}\n\nJD / SOURCE:\n{source[:18000]}'
                    )
                    _cid,_rid=_usage_ids_for_entity(opp)
                    with scoped_usage_context(campaign_id=_cid,campaign_run_id=_rid,operation='manual_rebuild',subject_type='opportunity',subject_id=str(opp.pk)):
                        value=generate_with_route(route,prompt,stage='first_filter',timeout=90,subject={'type':'opportunity','id':opp.pk,'label':f'{opp.company} — {opp.title} · list summary'})
                    value=normalize_ai_fit_summary(value,max_words=50)
                    if not value:
                        raise RuntimeError('Cloud AI returned an empty Opportunity summary.')
                    opp.list_highlight=value[:600]
                    opp.save(update_fields=['list_highlight','updated_at'])
                    opp.refresh_from_db()
                except Exception as exc:
                    if len(stats['errors'])<25:
                        stats['errors'].append({'opportunity_id':opp.pk,'field':'summary','error':str(exc)[:500]})

            after={
                'company':_maintenance_company_info_missing(opp),
                'company_location':_maintenance_company_location_missing(opp),
                'remote':_maintenance_remote_missing(opp),
                'post_age':_maintenance_post_age_missing(opp),
                'fit':_maintenance_fit_missing(opp),
                'summary':not bool(str(opp.list_highlight or '').strip()),
            }
            for key,was_missing in before.items():
                if not was_missing:
                    continue
                if after[key]: stats['fields_still_unknown']+=1
                else: stats['fields_rebuilt']+=1
            if total:
                job.progress=max(1,min(99,int(index*100/total)))
                job.message=f'Rebuilding missing AI data · {index:,}/{total:,}'
                job.result={**stats,'errors':stats['errors'][-25:]}
                job.save(update_fields=['progress','message','result'])

        message=(f"Rebuild complete · {stats['fields_rebuilt']:,} fields filled · "
                 f"{stats['fields_still_unknown']:,} still unknown")
        _job_done(job,stats,message)
        return stats
    except Exception as exc:
        _job_fail(job,exc)
        raise


def _manual_company_info_label(entity):
    intel=getattr(entity,'company_intel',{}) or {}
    structured=intel.get('structured') if isinstance(intel,dict) and isinstance(intel.get('structured'),dict) else {}
    age=str(structured.get('age_range') or structured.get('domain_age_label') or '').strip()
    size=str(structured.get('size_range') or '').strip()
    return ' · '.join(x for x in (age,size) if x) or '?'


def _manual_remote_label(entity):
    facts=getattr(entity,'extracted_facts',{}) or {}
    row=facts.get('remote_classification') if isinstance(facts,dict) else {}
    if not isinstance(row,dict): row={}
    return str(row.get('label') or {'fully_remote':'Fully remote','remote':'Remote','hybrid':'Hybrid','onsite':'On-site','unknown':'Unknown'}.get(str(row.get('status') or 'unknown'),'Unknown'))


def _manual_apply_label(entity):
    channel=str(getattr(entity,'channel','') or 'unknown').lower()
    if channel=='ats': return 'ATS'
    if channel=='email': return 'Email'
    if channel in {'website','public','community'}: return 'Website / form'
    return 'Email' if str(getattr(entity,'contact_email','') or '').strip() else 'Website / form'


def _valid_public_email(value, context=''):
    value=str(value or '').strip()
    if not re.fullmatch(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',value):
        return ''
    return value if assignable_contact_email(value,context) else ''


def _manual_opportunity_metadata_refresh(opp, review, provider, model):
    """Persist list metadata returned by the same grounded Cloud manual-filter request."""
    meta=review.get('metadata_refresh') if isinstance(review,dict) else {}
    if not isinstance(meta,dict):
        return {'refreshed':[],'changes':[]}
    refreshed=[]; changes=[]; sources=meta.get('sources') or []

    # Repair employer identity before any company-age/location enrichment. A listing
    # platform is never the employer; when Cloud Internet Search finds the exact same
    # vacancy, promote that direct employer/ATS URL while retaining the old URL as
    # provenance. Local GPU re-evaluation can still repair the company name from retained
    # evidence even though it cannot search for a new URL.
    identity=meta.get('identity') if isinstance(meta.get('identity'),dict) else {}
    company_name=' '.join(str(identity.get('company_name') or '').split()).strip()[:220]
    try: company_conf=int(identity.get('company_confidence') or 0)
    except Exception: company_conf=0
    if company_name and not is_platform_company_name(company_name) and company_conf>=60:
        current_company=str(opp.company or '').strip()
        if not current_company or is_platform_company_name(current_company) or company_conf>=80:
            if company_name.casefold()!=current_company.casefold():
                before=current_company or 'Unknown'
                opp.company=company_name
                # Wrong platform identity can poison retained company-age/location data.
                # Clear it now; a grounded cloud pass below will repopulate it.
                if is_platform_company_name(current_company):
                    opp.company_intel={}
                    opp.save(update_fields=['company','company_intel','updated_at'])
                else:
                    opp.save(update_fields=['company','updated_at'])
                refreshed.append('Company')
                changes.append({'field':'Company','before':before,'after':company_name})

    if meta.get('enabled') and review.get('internet_search') and provider in ('openai','gemini','openrouter'):
        direct_url=str(identity.get('direct_role_url') or '').strip()[:1000]
        try: same_role_conf=int(identity.get('same_role_confidence') or 0)
        except Exception: same_role_conf=0
        if (direct_url.startswith(('http://','https://')) and same_role_conf>=75
                and looks_like_specific_opportunity_url(direct_url) and not is_job_board_host(direct_url)):
            current_url=str(opp.target_url or opp.url or '').strip()
            if direct_url.rstrip('/')!=current_url.rstrip('/'):
                facts=dict(opp.extracted_facts or {})
                history=list(facts.get('direct_role_resolution_history') or [])
                history.append({
                    'at':timezone.now().isoformat(),'provider':provider,'model':model,
                    'from_url':current_url,'to_url':direct_url,'same_role_confidence':same_role_conf,
                    'reason':str(identity.get('url_reason') or '')[:1200],
                })
                facts['direct_role_resolution_history']=history[-8:]
                if current_url:
                    facts['original_job_board_url']=facts.get('original_job_board_url') or current_url
                opp.search_url=opp.search_url or current_url
                opp.url=direct_url; opp.target_url=direct_url; opp.canonical_url=direct_url
                opp.extracted_facts=facts
                opp.save(update_fields=['search_url','url','target_url','canonical_url','extracted_facts','updated_at'])
                refreshed.append('Direct Role URL')
                changes.append({'field':'Direct Role URL','before':current_url or 'Unknown','after':direct_url})

    role=meta.get('role_location') if isinstance(meta.get('role_location'),dict) else {}
    try: role_conf=int(role.get('confidence') or 0)
    except Exception: role_conf=0
    facts_now=dict(opp.extracted_facts or {})
    location_hint=facts_now.get('jobLocation') or ((facts_now.get('original_job_board_evidence') or {}).get('role_location') if isinstance(facts_now.get('original_job_board_evidence'),dict) else '') or ''
    deterministic_location=extract_role_location(opp.description or opp.raw_search_snippet,location_hint)
    if deterministic_location:
        role=dict(role); role['location']=deterministic_location; role['country']=infer_country(opp.target_url or opp.url,deterministic_location,location_hint=location_hint,strict=True) or role.get('country') or ''; role['confidence']=max(96,role_conf); role['reason']='Explicit retained Job Location / role-location evidence.'; role_conf=int(role['confidence'])
    if role_conf>=55:
        role_location=' '.join(str(role.get('location') or '').split()).strip()[:240]
        # Never persist a bare model-supplied country. It must resolve from the explicit
        # role-location text or retained structured JobPosting evidence.
        role_country=infer_country(opp.target_url or opp.url,role_location,location_hint=location_hint,strict=True)
        changed_fields=[]
        if role_location and role_location!=str(getattr(opp,'role_location','') or ''):
            before=str(getattr(opp,'role_location','') or '') or 'Unknown'; opp.role_location=role_location; changed_fields.append('role_location')
            changes.append({'field':'Role Location','before':before,'after':role_location}); refreshed.append('Role Location')
        if role_country and role_country!=str(opp.country or ''):
            before=str(opp.country or '') or 'Unknown'; opp.country=role_country; changed_fields.append('country')
            changes.append({'field':'Role Country','before':before,'after':role_country}); refreshed.append('Role Country')
        if changed_fields:
            facts=dict(opp.extracted_facts or {}); facts['role_location_classification']={'location':role_location,'country':role_country,'confidence':role_conf,'reason':str(role.get('reason') or '')[:1000],'provider':provider,'model':model,'at':timezone.now().isoformat()}; opp.extracted_facts=facts; changed_fields.append('extracted_facts')
            opp.save(update_fields=list(dict.fromkeys(changed_fields+['updated_at'])))
    # Company/apply/remote/post-age refresh still requires explicit Cloud Internet Search.
    if not meta.get('enabled') or not review.get('internet_search') or provider not in ('openai','gemini','openrouter'):
        return {'refreshed':list(dict.fromkeys(refreshed)),'changes':changes}

    company=meta.get('company_info') if isinstance(meta.get('company_info'),dict) else {}
    meaningful_company=any(str(company.get(k) or '').strip() for k in ('founded_year','employee_count_or_range','size_structure','what_they_do','products_technology','location'))
    if meaningful_company and int(company.get('confidence') or 0)>=45:
        before=_manual_company_info_label(opp)
        opp.company_intel=company_intel_from_manual_filter(opp,company,provider,model,sources)
        opp.save(update_fields=['company_intel','updated_at'])
        after=_manual_company_info_label(opp)
        refreshed.append('Company Info')
        if before!=after: changes.append({'field':'Company Info','before':before,'after':after})

    apply=meta.get('apply_via') if isinstance(meta.get('apply_via'),dict) else {}
    try: apply_conf=int(apply.get('confidence') or 0)
    except Exception: apply_conf=0
    allowed={'email','ats','website','public','community','unknown'}
    new_channel=str(apply.get('channel') or 'unknown').lower()
    if apply_conf>=55 and new_channel in allowed and new_channel!='unknown':
        before=_manual_apply_label(opp)
        changed_fields=[]
        opp.channel=new_channel; changed_fields.append('channel')
        email=_valid_public_email(apply.get('contact_email'),' '.join(str(apply.get(k) or '') for k in ('reason','application_url','channel')))
        if apply.get('contact_email') and not email:
            apply['contact_email']=''
        if email and (not opp.contact_email or apply_conf>=75):
            opp.contact_email=email; changed_fields.append('contact_email')
        if email:
            try:
                contact,created,_outcome=promote_record_contact_to_addressbook(
                    opp,source=f'Manual Filter · {provider}',
                    source_url=(str(apply.get('application_url') or '').strip() or opp.target_url or opp.canonical_url or opp.url),
                    texts=(opp.description,opp.raw_search_snippet,str(apply.get('reason') or ''),str(apply.get('application_url') or '')),
                    confidence=apply_conf,queue_research=False,
                )
                if contact is not None and created:
                    refreshed.append('Address Book')
                    changes.append({'field':'Address Book','before':'Not saved','after':contact.email})
            except Exception:
                pass
        facts=dict(opp.extracted_facts or {})
        facts['application_path']={
            'channel':new_channel,'application_url':str(apply.get('application_url') or '')[:1000],
            'contact_email':email,'confidence':apply_conf,'reason':str(apply.get('reason') or '')[:1000],
            'source':'Manual filter web research','provider':provider,'model':model,'at':timezone.now().isoformat(),
        }
        opp.extracted_facts=facts; changed_fields.append('extracted_facts')
        opp.save(update_fields=list(dict.fromkeys(changed_fields+['updated_at'])))
        after=_manual_apply_label(opp)
        refreshed.append('Contact Method')
        if before!=after: changes.append({'field':'Contact Method','before':before,'after':after})

    remote=meta.get('remote') if isinstance(meta.get('remote'),dict) else {}
    try: remote_conf=int(remote.get('confidence') or 0)
    except Exception: remote_conf=0
    remote_status=str(remote.get('status') or 'unknown').lower()
    current_remote=(opp.extracted_facts or {}).get('remote_classification') or {}
    current_remote_status=str(current_remote.get('status') or 'unknown').lower() if isinstance(current_remote,dict) else 'unknown'
    arrangement=work_arrangement_evidence(opp.description or opp.raw_search_snippet,'',opp.title,structured_remote=False)
    grounded_status=str(arrangement.get('status') or 'unknown') if arrangement.get('confirmed') else 'unknown'
    # Manual/Cloud refresh may suggest a working arrangement, but it may only overwrite
    # the list badge when the retained role text independently supports that same status.
    remote_grounded=(remote_status=='unknown' or (arrangement.get('confirmed') and (remote_status==grounded_status or {remote_status,grounded_status}<={'remote','fully_remote'})))
    if remote_conf>=55 and remote_status in {'fully_remote','remote','hybrid','onsite','unknown'} and remote_grounded and (remote_status!='unknown' or current_remote_status=='unknown'):
        before=_manual_remote_label(opp)
        if remote_status!='unknown':
            remote_conf=max(remote_conf,int(arrangement.get('confidence') or 0))
            remote['reason']=str(arrangement.get('reason') or remote.get('reason') or '')
        default={'fully_remote':'Fully remote','remote':'Remote','hybrid':'Hybrid','onsite':'On-site','unknown':'Unknown'}[remote_status]
        label=' '.join(str(remote.get('label') or default).split())[:60] or default
        facts=dict(opp.extracted_facts or {})
        facts['remote_classification']={
            'status':remote_status,'label':label,'confidence':max(0,min(100,remote_conf)),
            'reason':str(remote.get('reason') or '')[:1200],'source':'Manual filter web research',
            'provider':provider,'model':model,'at':timezone.now().isoformat(),
        }
        opp.extracted_facts=facts
        opp.remote_text=(label+((' — '+facts['remote_classification']['reason']) if facts['remote_classification']['reason'] else ''))[:220]
        opp.save(update_fields=['remote_text','extracted_facts','updated_at'])
        after=_manual_remote_label(opp)
        refreshed.append('Remote')
        if before!=after: changes.append({'field':'Remote','before':before,'after':after})

    post=meta.get('post_age') if isinstance(meta.get('post_age'),dict) else {}
    try: post_conf=int(post.get('post_age_confidence') or 0)
    except Exception: post_conf=0
    has_post_evidence=bool(str(post.get('posted_date') or '').strip() or post.get('age_days') not in (None,'') or (str(post.get('post_age_class') or '').lower()=='evergreen' and int(post.get('evergreen_confidence') or 0)>=60))
    if has_post_evidence and post_conf>=40:
        before=str(opp.freshness_label or '?')
        payload=dict(post); payload['cloud_provider']=provider
        try:
            apply_cloud_post_age(opp,payload)
            after=str(opp.freshness_label or '?')
            refreshed.append('Post Age')
            if before!=after: changes.append({'field':'Post Age','before':before,'after':after})
        except Exception as exc:
            changes.append({'field':'Post Age','before':before,'after':before,'note':'Refresh failed: '+str(exc)[:180]})

    # Retain a compact audit marker even when the visible values did not change.
    facts=dict(opp.extracted_facts or {})
    facts['manual_metadata_refresh']={
        'at':timezone.now().isoformat(),'provider':provider,'model':model,'internet_search':True,
        'refreshed':list(dict.fromkeys(refreshed)),'changes':changes,'sources':sources[:8],
    }
    opp.extracted_facts=facts
    opp.save(update_fields=['extracted_facts','updated_at'])
    return {'refreshed':list(dict.fromkeys(refreshed)),'changes':changes}


def _manual_hidden_lead_metadata_refresh(lead, review, provider, model):
    """Refresh company/contact metadata for a web-grounded Hidden Lead second pass."""
    meta=review.get('metadata_refresh') if isinstance(review,dict) else {}
    if not isinstance(meta,dict) or not meta.get('enabled') or not review.get('internet_search') or provider not in ('openai','gemini','openrouter'):
        return {'refreshed':[],'changes':[]}
    refreshed=[]; changes=[]; sources=meta.get('sources') or []
    company=meta.get('company_info') if isinstance(meta.get('company_info'),dict) else {}
    meaningful_company=any(str(company.get(k) or '').strip() for k in ('founded_year','employee_count_or_range','size_structure','what_they_do','products_technology','location'))
    if meaningful_company and int(company.get('confidence') or 0)>=45:
        before=_manual_company_info_label(lead)
        lead.company_intel=company_intel_from_manual_filter(lead,company,provider,model,sources)
        lead.save(update_fields=['company_intel','updated_at'])
        after=_manual_company_info_label(lead)
        refreshed.append('Company Info')
        if before!=after: changes.append({'field':'Company Info','before':before,'after':after})
    apply=meta.get('apply_via') if isinstance(meta.get('apply_via'),dict) else {}
    try: apply_conf=int(apply.get('confidence') or 0)
    except Exception: apply_conf=0
    if apply_conf>=55:
        before='Email' if lead.contact_email else ('Contact page' if lead.contact_url else 'Unknown')
        fields=[]; email=_valid_public_email(apply.get('contact_email'),' '.join(str(apply.get(k) or '') for k in ('reason','application_url','channel'))); url=str(apply.get('application_url') or '').strip()
        if apply.get('contact_email') and not email:
            apply['contact_email']=''
        if email and (not lead.contact_email or apply_conf>=75): lead.contact_email=email; fields.append('contact_email')
        if url.startswith(('http://','https://')) and (not lead.contact_url or apply_conf>=70): lead.contact_url=url[:1000]; fields.append('contact_url')
        if fields:
            lead.save(update_fields=list(dict.fromkeys(fields+['updated_at'])))
            after='Email' if lead.contact_email else ('Contact page' if lead.contact_url else 'Unknown')
            refreshed.append('Contact Path')
            if before!=after: changes.append({'field':'Contact Path','before':before,'after':after})
        if email:
            try:
                contact,created,_outcome=promote_record_contact_to_addressbook(
                    lead,source=f'Manual Filter · {provider}',
                    source_url=(url if url.startswith(('http://','https://')) else (lead.target_url or lead.source_url or lead.search_url)),
                    texts=(lead.evidence,lead.summary,lead.match_summary,str(apply.get('reason') or ''),url),
                    confidence=apply_conf,queue_research=False,
                )
                if contact is not None and created:
                    refreshed.append('Address Book')
                    changes.append({'field':'Address Book','before':'Not saved','after':contact.email})
            except Exception:
                pass
    remote=meta.get('remote') if isinstance(meta.get('remote'),dict) else {}
    try: remote_conf=int(remote.get('confidence') or 0)
    except Exception: remote_conf=0
    status=str(remote.get('status') or 'unknown').lower()
    arrangement=work_arrangement_evidence(' '.join(x for x in (lead.evidence,lead.summary,lead.match_summary) if x),'',lead.company,structured_remote=False)
    grounded_status=str(arrangement.get('status') or 'unknown') if arrangement.get('confirmed') else 'unknown'
    remote_grounded=(status=='unknown' or (arrangement.get('confirmed') and (status==grounded_status or {status,grounded_status}<={'remote','fully_remote'})))
    if remote_conf>=55 and status in {'fully_remote','remote','hybrid','onsite','unknown'} and remote_grounded:
        if status!='unknown':
            remote_conf=max(remote_conf,int(arrangement.get('confidence') or 0))
            remote['reason']=str(arrangement.get('reason') or remote.get('reason') or '')
        state=dict(lead.ai_state or {})
        state['remote_classification']={
            'status':status,'label':str(remote.get('label') or '')[:60],
            'confidence':max(0,min(100,remote_conf)),'reason':str(remote.get('reason') or '')[:1200],
            'source':'Manual filter web research','provider':provider,'model':model,'at':timezone.now().isoformat(),
        }
        lead.ai_state=state; lead.save(update_fields=['ai_state','updated_at'])
        refreshed.append('Remote')
    state=dict(lead.ai_state or {})
    state['manual_metadata_refresh']={
        'at':timezone.now().isoformat(),'provider':provider,'model':model,'internet_search':True,
        'refreshed':list(dict.fromkeys(refreshed)),'changes':changes,'sources':sources[:8],
    }
    lead.ai_state=state; lead.save(update_fields=['ai_state','updated_at'])
    return {'refreshed':list(dict.fromkeys(refreshed)),'changes':changes}


def _manual_contact_metadata_refresh(contact, review, provider, model):
    """Refresh Address Book company facts from the same grounded Cloud second pass."""
    meta=review.get('metadata_refresh') if isinstance(review,dict) else {}
    if not isinstance(meta,dict) or not meta.get('enabled') or not review.get('internet_search') or provider not in ('openai','gemini','openrouter'):
        return {'refreshed':[],'changes':[]}
    company=meta.get('company_info') if isinstance(meta.get('company_info'),dict) else {}
    meaningful=any(str(company.get(k) or '').strip() for k in ('founded_year','employee_count_or_range','size_structure','what_they_do','products_technology','location'))
    if not meaningful or int(company.get('confidence') or 0)<45:
        return {'refreshed':[],'changes':[]}
    before=_manual_company_info_label(contact)
    previous=dict(contact.company_intel or {})
    fresh=company_intel_from_manual_filter(contact,company,provider,model,meta.get('sources') or [])
    for key in ('fit_classification','manual_contact_filter','discovery_origin','_usage'):
        if key in previous and key not in fresh: fresh[key]=previous[key]
    contact.company_intel=fresh
    summary=company_summary_from_intel(fresh,1200)
    fields=['company_intel']
    if summary:
        contact.company_summary=summary[:2000]; fields.append('company_summary')
    location=' '.join(str(company.get('location') or '').split())[:120]
    if location and int(company.get('confidence') or 0)>=70:
        contact.company_country=location; fields.append('company_country')
    contact.save(update_fields=list(dict.fromkeys(fields)))
    after=_manual_company_info_label(contact)
    changes=[]
    if before!=after: changes.append({'field':'Company Info','before':before,'after':after})
    return {'refreshed':['Company Info'],'changes':changes}


def _manual_filter_notification(job, stats, label, recipient, *, failed=False):
    """Send and persist a detailed completion/failure notice for a manual filter."""
    recipient=str(recipient or '').strip()
    if not recipient:
        stats['notification_sent']=False
        stats['notification_error']='Logged-in account has no email address.'
        return
    provider=str(stats.get('provider') or 'AI')
    model=str(stats.get('model') or '').strip()
    web='enabled' if stats.get('internet_search') else 'disabled'
    state='failed' if failed else 'complete'
    subject=f'{settings.PORTAL_SHORT_NAME} {label} filter {state}'
    items=[row for row in (stats.get('items') or []) if isinstance(row,dict)]
    scored=[row for row in items if row.get('fit_before') is not None or row.get('fit_after') is not None]
    recycled=[row for row in items if str(row.get('decision') or '')=='recycled']

    def entry_name(row):
        company=' '.join(str(row.get('company') or '').split())
        title=' '.join(str(row.get('title') or '').split())
        if company and title:
            return f'{company} — {title}'
        return company or title or f'{label} #{row.get("id") or "?"}'

    def fit_text(row):
        before=row.get('fit_before')
        after=row.get('fit_after')
        if before is None and after is None:
            return 'Fit unchanged/unavailable'
        if before is None:
            return f'Fit → {after}'
        if after is None:
            return f'Fit {before} → unchanged'
        return f'Fit {before} → {after}'

    lines=[
        f'{label} filter {state}.', '',
        f'Provider: {provider}',
        f'Model: {model or "Not set"}',
        f'Internet search: {web}',
        f'Selected: {int(stats.get("selected") or 0)}',
        f'Processed: {int(stats.get("processed") or 0)}',
        f'Kept: {int(stats.get("kept") or 0)}',
        f'Recycled: {int(stats.get("recycled") or 0)}',
    ]
    if stats.get('converted_to_hidden_lead'):
        lines.append(f'Converted to Hidden Leads: {int(stats.get("converted_to_hidden_lead") or 0)}')
    if stats.get('converted_to_opportunity'):
        lines.append(f'Converted to Opportunities: {int(stats.get("converted_to_opportunity") or 0)}')
    lines.extend([
        f'Protected: {int(stats.get("protected") or 0)}',
        f'Need review: {int(stats.get("review") or 0)}',
        f'Failed: {int(stats.get("failed") or 0)}',
        f'Unprocessed: {int(stats.get("unprocessed") or 0)}',
    ])
    circuit=stats.get('circuit_breaker') if isinstance(stats.get('circuit_breaker'),dict) else {}
    if circuit.get('triggered'):
        lines.append(f'Automatic stop: {circuit.get("reason") or "Re-evaluation circuit breaker triggered."}')
        if circuit.get('kind')=='repeated_internal_error':
            lines.extend([
                f'Internal error type: {circuit.get("error_type") or "Error"}',
                f'Repeated identical failures: {int(circuit.get("count") or 0)}',
                f'Failure detail: {str(circuit.get("error") or "")[:500]}',
            ])
        else:
            lines.append(f'Empty response attempts in streak: {int(circuit.get("consecutive_empty_responses") or 0)}')
    lines.extend(['', 'Fit score results:'])
    if scored:
        for row in scored:
            decision=str(row.get('decision') or 'review').replace('_',' ').title()
            changed_note=' (changed)' if row.get('fit_changed') else ''
            refreshed=', '.join(str(x) for x in (row.get('metadata_refreshed') or []) if str(x).strip())
            refresh_note=f' — Refreshed: {refreshed}' if refreshed else ''
            lines.append(f'- {entry_name(row)} [#{row.get("id")}] — {fit_text(row)}{changed_note} — {decision}{refresh_note}')
    else:
        lines.append('- No Fit scores were recalculated.')

    refreshed_rows=[row for row in items if row.get('metadata_refreshed')]
    lines.extend(['', 'Metadata refreshed by Cloud Internet Search:'])
    if refreshed_rows:
        for row in refreshed_rows:
            fields=', '.join(str(x) for x in row.get('metadata_refreshed') or [])
            changes=[]
            for change in row.get('metadata_changes') or []:
                if not isinstance(change,dict): continue
                field=str(change.get('field') or '').strip()
                before=str(change.get('before') or '?').strip(); after=str(change.get('after') or '?').strip()
                if field and before!=after: changes.append(f'{field}: {before} -> {after}')
            suffix=(' — '+'; '.join(changes[:6])) if changes else ''
            lines.append(f'- {entry_name(row)} [#{row.get("id")}] — {fields}{suffix}')
    else:
        lines.append('- None (web metadata refresh was disabled or no sufficiently confident metadata was returned).')

    lines.extend(['', 'Recycled entries:'])
    if recycled:
        for row in recycled:
            reason=' '.join(str(row.get('reason') or '').split())
            suffix=f' — {reason[:300]}' if reason else ''
            lines.append(f'- {entry_name(row)} [#{row.get("id")}] — {fit_text(row)}{suffix}')
    else:
        lines.append('- None.')

    page='Opportunities' if label=='Opportunity' else ('Address Book' if label=='Address Book' else 'Hidden Leads')
    lines.extend(['', f'Open ScoutBox > {page} to review the latest re-evaluation result.'])
    body='\n'.join(lines)
    attempted_at=timezone.now()
    try:
        send_notification(recipient,subject,body)
        stats['notification_sent']=True
        stats['notification_error']=''
    except Exception as exc:
        stats['notification_sent']=False
        stats['notification_error']=str(exc)[:1000]
        # send_notification logs delivery failures after it has a usable mail profile.
        # If it failed before creating an event (for example, no active profile), retain
        # the attempted message in Email History so the result remains auditable.
        exists=MailEvent.objects.filter(
            kind='notification',recipients=recipient,subject=subject,occurred_at__gte=attempted_at-timedelta(seconds=5)
        ).exists()
        if not exists:
            MailEvent.objects.create(
                kind='notification',subject=subject,sender='',recipients=recipient,
                body_excerpt=body[:1000],body_text=body,delivery_status='failed',
                delivery_error=str(exc)[:1000],server='Notification not configured',
                occurred_at=timezone.now(),metadata={'source':'manual_filter','job_id':job.pk},
            )


def _manual_filter_progress(stats, total=None, *, terminal=False):
    """One authoritative percentage based on completed selected items."""
    try: selected=max(0,int(total if total is not None else stats.get('selected') or 0))
    except Exception: selected=0
    try: processed=max(0,min(selected,int(stats.get('processed') or 0)))
    except Exception: processed=0
    if selected<=0: return 100 if terminal else 0
    pct=int(round(processed*100.0/selected))
    if terminal and processed>=selected: return 100
    return max(0,min(99,pct))


def _stop_manual_filter_after_empty_responses(job, stats, label, recipient, index, total, empty_streak):
    """Stop a paid manual batch after repeated provider HTTP-200/empty responses."""
    stats['unprocessed']=max(0,total-index)
    stats['consecutive_empty_responses']=int(empty_streak or 0)
    stats['circuit_breaker']={
        'triggered':True,
        'kind':'empty_response',
        'reason':'Provider returned 3 or more consecutive empty response attempts. Filter stopped to avoid unnecessary Cloud usage.',
        'consecutive_empty_responses':int(empty_streak or 0),
        'threshold':3,
        'provider':str(stats.get('provider') or ''),
        'model':str(stats.get('model') or ''),
    }
    job.status='stopped'
    job.finished_at=timezone.now()
    job.progress=_manual_filter_progress(stats,total)
    job.message=f'{label} filter stopped automatically · repeated empty AI responses · {stats.get("processed",0)}/{total} checked'
    job.error=''
    job.result=stats
    job.save(update_fields=['status','finished_at','progress','message','error','result'])
    _manual_filter_notification(job,stats,label,recipient,failed=True)
    # Persist notification outcome back into the durable result after sending.
    job.result=stats
    job.save(update_fields=['result'])
    return stats


def _stop_manual_filter(job, stats, label, recipient, total, message):
    """Persist an early stop without falsifying completion percentage."""
    stats['unprocessed']=max(0,int(total or 0)-int(stats.get('processed') or 0))
    job.status='stopped'
    job.finished_at=timezone.now()
    job.progress=_manual_filter_progress(stats,total)
    job.message=message
    job.error=''
    job.result=stats
    job.save(update_fields=['status','finished_at','progress','message','error','result'])
    _manual_filter_notification(job,stats,label,recipient)
    job.result=stats
    job.save(update_fields=['result'])
    return stats


def _manual_filter_item_started(job, stats, *, noun, index, total, provider, model, internet_search, item_label=''):
    """Persist the in-flight row before the provider call so bulk filters never look frozen.

    The durable deadline also gives the status endpoint a safe way to retire a provider call
    that has exceeded every configured request attempt instead of leaving a permanent
    running lock after a broken HTTP/worker path.
    """
    now=timezone.now()
    request_timeout=max(30,int(ai_request_timeout(provider,'first_filter') or 120))
    # Grounded web calls can perform one compatibility/empty-output retry. Allow both
    # configured request windows plus a small persistence/parsing grace period.
    attempt_windows=2 if internet_search else 1
    deadline_seconds=(request_timeout*attempt_windows)+45
    label=' '.join(str(item_label or '').split())[:180]
    current={
        'index':int(index),'total':int(total),'started_at':now.isoformat(),
        'deadline_at':(now+timedelta(seconds=deadline_seconds)).isoformat(),
        'request_timeout_seconds':request_timeout,'deadline_seconds':deadline_seconds,
        'provider':str(provider or ''),'model':str(model or ''),'label':label,
    }
    stats['current_item']=current
    stats['last_progress_at']=now.isoformat()
    try:
        progress=int(round(max(0,min(int(total),int(index)))*100.0/max(1,int(total))))
    except Exception:
        progress=0
    progress=max(1,min(99,progress)) if int(total or 0)>0 else 0
    subject=(f' · {label}' if label else '')
    job.progress=progress
    job.message=f'Checking {noun} {index}/{total}{subject} · {provider} · {model}'[:500]
    job.result=stats
    job.save(update_fields=['progress','message','result'])


def _manual_filter_item_finished(stats):
    stats.pop('current_item',None)
    stats['last_progress_at']=timezone.now().isoformat()



MANUAL_FILTER_CLOUD_PARALLELISM = 5


def _manual_filter_parallel_enabled(provider):
    return str(provider or '').strip().lower() in {'openai','gemini','openrouter'}


def _parallel_manual_filter_empty_response_budget(provider):
    """Keep Gemini's one compatibility retry enabled in parallel manual re-evaluation.

    Gemini 3.x grounded structured requests can occasionally return HTTP 200 with no
    visible final text. ``_run_manual_filter`` already has a same-model compatibility
    retry (minimal thinking and no forced JSON MIME), but a budget of 1 disables it.
    Cloud parallelism must not change that provider reliability behavior.
    """
    return 2 if str(provider or '').strip().lower() == 'gemini' else 1


def _bounded_items_append(stats, item, limit=500):
    items=stats.setdefault('items',[])
    items.append(item)
    if len(items)>limit:
        del items[:-limit]


MANUAL_FILTER_INTERNAL_FAILURE_THRESHOLD = 3
MANUAL_FILTER_INTERNAL_EXCEPTIONS = (
    TypeError, AttributeError, NameError, UnboundLocalError, ImportError,
    KeyError, IndexError, AssertionError, ZeroDivisionError,
)


def _manual_filter_exception_result(item, exc):
    """Return one bounded item failure plus diagnostics used by the batch circuit breaker."""
    error_type=exc.__class__.__name__
    reason=str(exc)[:600]
    row=dict(item or {})
    row.update({'decision':'failed','reason':reason})
    return {
        'stat':'failed','item':row,'error_type':error_type,
        'internal_error':isinstance(exc,MANUAL_FILTER_INTERNAL_EXCEPTIONS),
    }


def _manual_filter_internal_failure_signature(result):
    if not isinstance(result,dict) or not result.get('internal_error'):
        return ''
    item=result.get('item') if isinstance(result.get('item'),dict) else {}
    reason=' '.join(str(item.get('reason') or '').split())[:500]
    error_type=' '.join(str(result.get('error_type') or 'Error').split())[:80]
    return f'{error_type}: {reason}' if reason else error_type


def _manual_filter_common_failure_reason(stats):
    rows=[row for row in (stats.get('items') or []) if isinstance(row,dict) and str(row.get('decision') or '')=='failed']
    counts={}
    for row in rows:
        reason=' '.join(str(row.get('reason') or '').split())[:600]
        if reason:
            counts[reason]=counts.get(reason,0)+1
    if not counts:
        return 'Every selected item failed before a re-evaluation decision could be recorded.'
    reason,count=max(counts.items(),key=lambda pair:pair[1])
    return (f'{reason} (repeated on {count} item{"" if count==1 else "s"})')[:1000]


def _fail_manual_filter_job(job, stats, label, recipient, total, reason, message=''):
    """Persist a failed manual-filter batch without pretending it completed normally."""
    processed=max(0,int(stats.get('processed') or 0))
    stats['unprocessed']=max(0,int(total or 0)-processed)
    stats['fatal_error']=str(reason or 'Manual re-evaluation failed.')[:1000]
    job.status='failed'
    job.finished_at=timezone.now()
    job.progress=_manual_filter_progress(stats,total,terminal=processed>=int(total or 0))
    job.message=(message or f'{label} re-evaluation failed · {processed}/{int(total or 0)} checked')[:500]
    job.error=str(reason or 'Manual re-evaluation failed.')[:4000]
    job.result=stats
    job.save(update_fields=['status','finished_at','progress','message','error','result'])
    _manual_filter_notification(job,stats,label,recipient,failed=True)
    job.result=stats
    job.save(update_fields=['result'])
    return stats


def _fail_manual_filter_repeated_internal_error(job, stats, label, recipient, total, signature, count):
    if ': ' in signature:
        error_type,error_detail=signature.split(': ',1)
    else:
        error_type,error_detail=signature,''
    stats['circuit_breaker']={
        'triggered':True,
        'kind':'repeated_internal_error',
        'reason':'Repeated identical internal re-evaluation error. Batch stopped to avoid failing every remaining item.',
        'threshold':MANUAL_FILTER_INTERNAL_FAILURE_THRESHOLD,
        'count':int(count or 0),
        'error_type':error_type[:80],
        'error':error_detail[:600],
        'provider':str(stats.get('provider') or ''),
        'model':str(stats.get('model') or ''),
    }
    return _fail_manual_filter_job(
        job,stats,label,recipient,total,signature,
        f'{label} re-evaluation failed early · repeated internal error · {int(stats.get("processed") or 0)}/{int(total or 0)} checked',
    )


def _manual_filter_all_selected_failed(stats, total):
    total=max(0,int(total or 0))
    processed=max(0,int(stats.get('processed') or 0))
    failed=max(0,int(stats.get('failed') or 0))
    return bool(total and processed>=total and failed>=total)


def _bounded_parallel_futures(pool, worker, items, max_in_flight):
    """Yield futures while keeping only a small bounded set submitted at once.

    This makes fail-fast circuit breakers meaningful: after a repeated internal error, at
    most the already-running tracks can finish instead of hundreds of queued items.
    """
    iterator=iter(items)
    pending={}
    for _ in range(max(1,int(max_in_flight or 1))):
        try:
            item=next(iterator)
        except StopIteration:
            break
        pending[pool.submit(worker,item)]=item
    while pending:
        done,_=concurrent.futures.wait(tuple(pending),return_when=concurrent.futures.FIRST_COMPLETED)
        for future in done:
            item=pending.pop(future)
            yield future,item
            try:
                next_item=next(iterator)
            except StopIteration:
                continue
            pending[pool.submit(worker,next_item)]=next_item


def _parallel_filter_finalize(job, stats, label, notify_email, total):
    message=(f'{label} re-evaluation complete · {stats["kept"]} kept · {stats["recycled"]} recycled'
             + (f' · {stats.get("converted_to_hidden_lead",0)} → Hidden Leads' if stats.get('converted_to_hidden_lead') else '')
             + (f' · {stats.get("converted_to_opportunity",0)} → Opportunities' if stats.get('converted_to_opportunity') else '')
             + (f' · {stats["protected"]} protected' if stats.get('protected') else '')
             + (f' · {stats["review"]} need review' if stats.get('review') else '')
             + (f' · {stats["timed_out"]} timed out' if stats.get('timed_out') else '')
             + (f' · {stats["failed"]} failed' if stats.get('failed') else ''))
    stats['parallel_tracks']=MANUAL_FILTER_CLOUD_PARALLELISM
    stats['unprocessed']=max(0,int(total or 0)-int(stats.get('processed') or 0))
    if _manual_filter_all_selected_failed(stats,total):
        reason=_manual_filter_common_failure_reason(stats)
        return _fail_manual_filter_job(
            job,stats,label,notify_email,total,reason,
            f'{label} re-evaluation failed · every selected item failed · {int(stats.get("processed") or 0)}/{int(total or 0)} checked',
        )
    _manual_filter_notification(job,stats,label,notify_email)
    _job_done(job,stats,message)
    return stats


def _parallel_progress_update(job, stats, total, label, provider, model):
    job.refresh_from_db(fields=['status'])
    job.progress=_manual_filter_progress(stats,total)
    job.message=f'Re-evaluated {label} · {stats.get("processed",0)}/{total} · {provider} · {model} · {MANUAL_FILTER_CLOUD_PARALLELISM} tracks'
    job.result=stats
    job.save(update_fields=['progress','message','result'])



def _manual_convert_opportunity_to_hidden_lead(opp, review, new_fit, now):
    """Move a misclassified Opportunity into Hidden Leads after a high-confidence re-evaluation."""
    target=(opp.target_url or opp.canonical_url or opp.url or opp.search_url or '').strip()
    if not target.startswith(('http://','https://')):
        raise ValueError('Cannot convert Opportunity to Hidden Lead without a valid target URL.')
    reason=str(review.get('conversion_reason') or review.get('reason') or 'High-confidence cross-list correction.').strip()
    with transaction.atomic():
        existing=active_duplicate_lead(opp.company,target)
        if existing:
            lead=existing
            changed=[]
            if int(new_fit or 0)>int(lead.score or 0): lead.score=int(new_fit or 0); changed.append('score')
            if not lead.source_id and opp.source_id: lead.source=opp.source; changed.append('source')
            if not lead.target_url: lead.target_url=target; changed.append('target_url')
            if not lead.source_url: lead.source_url=target; changed.append('source_url')
            if not lead.search_url and opp.search_url: lead.search_url=opp.search_url; changed.append('search_url')
            if not lead.contact_email and opp.contact_email: lead.contact_email=opp.contact_email; changed.append('contact_email')
            if not lead.contact_name and opp.contact_name: lead.contact_name=opp.contact_name; changed.append('contact_name')
            if not lead.summary: lead.summary=(opp.list_highlight or opp.recommendation_reason or reason)[:2000]; changed.append('summary')
            if not lead.evidence: lead.evidence=(opp.description or opp.raw_search_snippet or '')[:12000]; changed.append('evidence')
            if not lead.company_intel and opp.company_intel: lead.company_intel=opp.company_intel; changed.append('company_intel')
            state=dict(lead.ai_state or {}); state['converted_from_opportunity']={'opportunity_id':opp.pk,'at':now.isoformat(),'reason':reason[:1200]}; lead.ai_state=state; changed.append('ai_state')
            if changed: lead.save(update_fields=list(dict.fromkeys(changed+['updated_at'])))
            reused=True
        else:
            lead=CompanyLead.objects.create(
                company=opp.company or 'Unknown', origin_campaign=opp.origin_campaign, source=opp.source,
                match_summary=reason[:2000], summary=(opp.list_highlight or opp.recommendation_reason or reason)[:2000],
                evidence=(opp.description or opp.raw_search_snippet or '')[:12000], company_intel=opp.company_intel or {},
                ai_state={'converted_from_opportunity':{'opportunity_id':opp.pk,'at':now.isoformat(),'reason':reason[:1200]}},
                search_url=opp.search_url, target_url=target, source_url=target,
                contact_name=opp.contact_name, contact_email=opp.contact_email, score=max(0,min(100,int(new_fit or 0))),
                status='review', is_read=False,
            )
            reused=False
        try:
            lead.campaigns.add(*opp.campaigns.all())
        except Exception:
            pass
        opp.suppressed=True; opp.user_deleted=True; opp.deleted_at=now; opp.is_read=True
        opp.rejection_reason=('Converted to Hidden Lead by re-evaluation: '+reason)[:4000]
        opp.save(update_fields=['suppressed','user_deleted','deleted_at','is_read','rejection_reason','updated_at'])
        AuditLog.objects.create(action='manual_cross_list_conversion',object_type='Opportunity',object_id=str(opp.pk),summary=f'Opportunity converted to Hidden Lead #{lead.pk}.',metadata={'from':'opportunity','to':'hidden_lead','target_id':lead.pk,'reused':reused,'confidence':review.get('conversion_confidence',0),'reason':reason[:1200]})
    return lead,reused


def _manual_convert_hidden_lead_to_opportunity(lead, review, new_fit, now):
    """Move a misclassified Hidden Lead into Opportunities after a high-confidence re-evaluation."""
    title=' '.join(str(review.get('conversion_title') or '').split())[:300]
    company=' '.join(str(review.get('conversion_company') or lead.company or '').split())[:220]
    target=str(review.get('conversion_url') or '').strip()[:1000]
    if not title or not target.startswith(('http://','https://')):
        raise ValueError('Cannot convert Hidden Lead to Opportunity without a specific role title and URL.')
    reason=str(review.get('conversion_reason') or review.get('reason') or 'High-confidence cross-list correction.').strip()
    with transaction.atomic():
        existing=active_duplicate_opportunity(title,company,target)
        if existing:
            opp=existing; reused=True
            facts=dict(opp.extracted_facts or {}); facts.setdefault('converted_hidden_lead_ids',[])
            if lead.pk not in facts['converted_hidden_lead_ids']: facts['converted_hidden_lead_ids'].append(lead.pk)
            facts['manual_cross_list_conversion']={'from':'hidden_lead','lead_id':lead.pk,'at':now.isoformat(),'reason':reason[:1200]}
            opp.extracted_facts=facts
            if int(new_fit or 0)>int(opp.fit_score or 0): opp.fit_score=int(new_fit or 0)
            if not opp.contact_email and lead.contact_email: opp.contact_email=lead.contact_email
            if not opp.contact_name and lead.contact_name: opp.contact_name=lead.contact_name
            opp.save(update_fields=['extracted_facts','fit_score','contact_email','contact_name','updated_at'])
        else:
            description='\n\n'.join(x for x in (lead.summary,lead.match_summary,lead.evidence) if str(x or '').strip())[:45000]
            facts={'market_study_lead_id':lead.pk,'converted_from_hidden_lead':True,'manual_cross_list_conversion':{'from':'hidden_lead','lead_id':lead.pk,'at':now.isoformat(),'reason':reason[:1200]}}
            opp=Opportunity.objects.create(
                title=title, company=company, url=target, search_url=lead.search_url, target_url=target, canonical_url=target,
                source=lead.source, origin_campaign=lead.origin_campaign, channel='email' if lead.contact_email else 'website',
                contact_email=lead.contact_email, contact_name=lead.contact_name, description=description,
                raw_search_snippet=lead.match_summary[:4000], extracted_facts=facts, company_intel=lead.company_intel or {},
                ai_state={'converted_from_hidden_lead':{'lead_id':lead.pk,'at':now.isoformat(),'reason':reason[:1200]}},
                status='review', fit_score=max(0,min(100,int(new_fit or 0))), recommendation_reason=reason[:2000],
                list_highlight=(lead.summary or lead.match_summary or '')[:600], is_read=False,
            )
            reused=False
        try:
            opp.campaigns.add(*lead.campaigns.all())
        except Exception:
            pass
        lead.user_deleted=True; lead.deleted_at=now; lead.is_read=True
        state=dict(lead.ai_state or {}); state['manual_hidden_lead_filter']={**review,'at':now.isoformat(),'applied_decision':'converted_to_opportunity','fit_after':int(new_fit or 0),'converted_opportunity_id':opp.pk}; lead.ai_state=state
        lead.save(update_fields=['user_deleted','deleted_at','is_read','ai_state','updated_at'])
        AuditLog.objects.create(action='manual_cross_list_conversion',object_type='CompanyLead',object_id=str(lead.pk),summary=f'Hidden Lead converted to Opportunity #{opp.pk}.',metadata={'from':'hidden_lead','to':'opportunity','target_id':opp.pk,'reused':reused,'confidence':review.get('conversion_confidence',0),'reason':reason[:1200]})
    return opp,reused


def _parallel_opportunity_filter(job, ids, provider, model, internet_search, notify_email, cloud_policy_prompt=''):
    total=len(ids)
    _job_start(job,f'Re-evaluating opportunities · 0/{total} · {provider} · {model} · {MANUAL_FILTER_CLOUD_PARALLELISM} tracks')
    stats={'selected':total,'processed':0,'kept':0,'recycled':0,'protected':0,'converted_to_hidden_lead':0,'converted_to_opportunity':0,'review':0,'failed':0,'timed_out':0,'unprocessed':0,'items':[],
           'provider':provider,'model':model,'internet_search':internet_search,'cloud_re_evaluation_prompt':cloud_policy_prompt,'parallel_tracks':MANUAL_FILTER_CLOUD_PARALLELISM,
           'empty_response_attempts':0,'consecutive_empty_responses':0,'circuit_breaker':{}}
    lock=threading.Lock()
    def worker(item):
        close_old_connections()
        opportunity_id=item
        opp=Opportunity.objects.filter(pk=opportunity_id,suppressed=False,user_deleted=False).first()
        if not opp:
            return {'stat':'review','item':{'id':opportunity_id,'decision':'review','reason':'Opportunity is no longer active.'}}
        old_fit=int(opp.fit_score or 0)
        protected=bool(Application.objects.filter(opportunity=opp).exists() or opp.application_draft_requested_at or BackgroundJob.objects.filter(kind='prepare',status__in=['queued','running'],result__opportunity_id=opp.pk).exclude(pk=job.pk).exists())
        try:
            campaign_id,run_id=_usage_ids_for_entity(opp)
            with scoped_usage_context(campaign_id=campaign_id,campaign_run_id=run_id,operation=budget_operation_for_phase('manual'),subject_type='opportunity',subject_id=str(opp.pk)):
                review=classify_existing_opportunity(opp,provider=provider,model=model,internet_search=internet_search,empty_response_budget=_parallel_manual_filter_empty_response_budget(provider),cloud_policy_prompt=cloud_policy_prompt)
            now=timezone.now(); decision=str(review.get('decision') or 'review'); applied_decision=decision
            raw_fit=review.get('fit_score')
            try: new_fit=max(0,min(100,int(raw_fit))) if raw_fit is not None else old_fit
            except Exception: new_fit=old_fit
            refreshed_summary=''
            try:
                from portal.services.highlights import normalize_ai_fit_summary
                refreshed_summary=normalize_ai_fit_summary(review.get('highlight') or '',max_words=50)
                if not refreshed_summary:
                    refreshed_summary=derive_opportunity_highlight(opportunity=opp,title=opp.title,description=opp.description or opp.raw_search_snippet,facts=opp.extracted_facts or {},remote_text=opp.remote_text)
                if refreshed_summary: opp.list_highlight=refreshed_summary[:600]
            except Exception: refreshed_summary=''
            try: metadata_result=_manual_opportunity_metadata_refresh(opp,review,provider,model)
            except Exception as meta_exc: metadata_result={'refreshed':[],'changes':[{'field':'Metadata','note':str(meta_exc)[:240]}]}
            facts=dict(opp.extracted_facts or {})
            if raw_fit is not None:
                facts['fit_classification']={'score':new_fit,'confidence':int(review.get('fit_confidence') or 0),'reason':str(review.get('fit_reason') or '')[:1600],'recommendation':str((facts.get('fit_classification') or {}).get('recommendation') or 'Unknown')[:80],'source':'Manual re-evaluation','provider':provider,'model':model,'at':now.isoformat()}
            opp.fit_score=new_fit
            if decision=='recycle' and protected:
                applied_decision='protected'; facts['manual_opportunity_filter']={**review,'at':now.isoformat(),'applied_decision':'protected','fit_before':old_fit,'fit_after':new_fit}; opp.extracted_facts=facts
                opp.save(update_fields=['fit_score','list_highlight','extracted_facts','updated_at']); stat='protected'
            elif decision=='convert_to_hidden_lead':
                facts['manual_opportunity_filter']={**review,'at':now.isoformat(),'applied_decision':'converted_to_hidden_lead','fit_before':old_fit,'fit_after':new_fit}; opp.extracted_facts=facts
                opp.save(update_fields=['fit_score','list_highlight','extracted_facts','updated_at'])
                converted,reused=_manual_convert_opportunity_to_hidden_lead(opp,review,new_fit,now); applied_decision='converted_to_hidden_lead'; stat='converted_to_hidden_lead'
            elif decision=='recycle':
                reason=str(review.get('reason') or 'High-confidence manual Opportunity re-evaluation rejection.').strip()
                opp.suppressed=True; opp.user_deleted=True; opp.deleted_at=now; opp.is_read=True; opp.rejection_reason=('Opportunity re-evaluation: '+reason)[:4000]
                facts['manual_opportunity_filter']={**review,'at':now.isoformat(),'applied_decision':'recycled','fit_before':old_fit,'fit_after':new_fit}; opp.extracted_facts=facts
                opp.save(update_fields=['fit_score','list_highlight','suppressed','user_deleted','deleted_at','is_read','rejection_reason','extracted_facts','updated_at']); stat='recycled'
            else:
                facts['manual_opportunity_filter']={**review,'at':now.isoformat(),'applied_decision':decision,'fit_before':old_fit,'fit_after':new_fit}; opp.extracted_facts=facts
                opp.save(update_fields=['fit_score','list_highlight','extracted_facts','updated_at']); stat='kept' if decision=='keep' else 'review'
            return {'stat':stat,'item':{'id':opp.pk,'title':opp.title[:300],'company':opp.company[:220],'decision':applied_decision,'purpose':review.get('purpose',''),'confidence':review.get('confidence',0),'reason':str(review.get('reason') or '')[:600],'fit_before':old_fit,'fit_after':new_fit,'fit_changed':new_fit!=old_fit,'fit_confidence':int(review.get('fit_confidence') or 0),'fit_reason':str(review.get('fit_reason') or '')[:600],'provider':review.get('provider',''),'model':review.get('model',''),'internet_search':bool(review.get('internet_search')),'web_sources':(review.get('web_sources') or [])[:8],'web_queries_count':int(review.get('web_queries_count') or 0),'metadata_refreshed':list(dict.fromkeys((metadata_result.get('refreshed') or [])+(['Summary'] if refreshed_summary else []))),'metadata_changes':metadata_result.get('changes') or [],'converted_id':(converted.pk if decision=='convert_to_hidden_lead' else None),'converted_reused':(reused if decision=='convert_to_hidden_lead' else False)}}
        except CloudLimitReached as exc:
            return {'fatal':'cloud_limit','stat':'failed','item':{'id':opportunity_id,'decision':'failed','reason':str(exc)[:600]}}
        except AIEmptyOutputWarning as exc:
            return {'stat':'failed','empty_attempts':max(1,int(getattr(exc,'empty_attempts',1) or 1)),'item':{'id':opportunity_id,'decision':'failed','reason':str(exc)[:600]}}
        except Exception as exc:
            return _manual_filter_exception_result({'id':opportunity_id,'title':opp.title[:300],'company':opp.company[:220]},exc)
        finally:
            close_old_connections()
    failure_signatures={}
    empty_streak=0
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=MANUAL_FILTER_CLOUD_PARALLELISM) as pool:
            for future,item_id in _bounded_parallel_futures(pool,worker,ids,MANUAL_FILTER_CLOUD_PARALLELISM):
                with lock:
                    job.refresh_from_db(fields=['status'])
                    if job.status=='stopped':
                        stats['unprocessed']=max(0,total-stats.get('processed',0)); job.result=stats; job.save(update_fields=['result']); return stats
                    try: result=future.result()
                    except Exception as exc: result=_manual_filter_exception_result({'id':item_id},exc)
                    stat=result.get('stat') or 'review'; stats['processed']+=1; stats[stat]=int(stats.get(stat) or 0)+1
                    empty_attempts=int(result.get('empty_attempts') or 0)
                    if empty_attempts:
                        stats['empty_response_attempts']+=empty_attempts; empty_streak+=empty_attempts; stats['consecutive_empty_responses']=empty_streak
                    else:
                        empty_streak=0; stats['consecutive_empty_responses']=0
                    _bounded_items_append(stats,result.get('item') or {'id':item_id,'decision':stat})
                    if result.get('fatal')=='cloud_limit':
                        return _stop_manual_filter(job,stats,'Opportunity',notify_email,total,f'Opportunity re-evaluation stopped early · Cloud AI limit reached · {stats["processed"]}/{total} checked')
                    if empty_streak>=3:
                        return _stop_manual_filter_after_empty_responses(job,stats,'Opportunity',notify_email,stats['processed'],total,empty_streak)
                    signature=_manual_filter_internal_failure_signature(result)
                    if signature:
                        count=failure_signatures.get(signature,0)+1; failure_signatures[signature]=count
                        if count>=MANUAL_FILTER_INTERNAL_FAILURE_THRESHOLD and count==int(stats.get('processed') or 0):
                            return _fail_manual_filter_repeated_internal_error(job,stats,'Opportunity',notify_email,total,signature,count)
                    _parallel_progress_update(job,stats,total,'opportunities',provider,model)
        return _parallel_filter_finalize(job,stats,'Opportunity',notify_email,total)
    except Exception as exc:
        try: stats['fatal_error']=str(exc)[:1000]; job.result=stats; job.save(update_fields=['result'])
        except Exception: pass
        _job_fail(job,exc); raise


def _parallel_hidden_lead_filter(job, ids, provider, model, internet_search, notify_email, cloud_policy_prompt=''):
    total=len(ids); _job_start(job,f'Re-evaluating Hidden Leads · 0/{total} · {provider} · {model} · {MANUAL_FILTER_CLOUD_PARALLELISM} tracks')
    stats={'selected':total,'processed':0,'kept':0,'recycled':0,'protected':0,'converted_to_hidden_lead':0,'converted_to_opportunity':0,'review':0,'failed':0,'timed_out':0,'unprocessed':0,'items':[], 'provider':provider,'model':model,'internet_search':internet_search,'cloud_re_evaluation_prompt':cloud_policy_prompt,'parallel_tracks':MANUAL_FILTER_CLOUD_PARALLELISM,'empty_response_attempts':0,'consecutive_empty_responses':0,'circuit_breaker':{}}
    def worker(lead_id):
        close_old_connections()
        lead=CompanyLead.objects.filter(pk=lead_id,user_deleted=False).first()
        if not lead: return {'stat':'review','item':{'id':lead_id,'decision':'review','reason':'Hidden Lead is no longer active.'}}
        old_fit=int(lead.score or 0)
        protected=_hidden_lead_has_outreach(lead)
        try:
            campaign_id,run_id=_usage_ids_for_entity(lead)
            with scoped_usage_context(campaign_id=campaign_id,campaign_run_id=run_id,operation=budget_operation_for_phase('manual'),subject_type='hidden lead',subject_id=str(lead.pk)):
                review=classify_existing_hidden_lead(lead,provider=provider,model=model,internet_search=internet_search,empty_response_budget=_parallel_manual_filter_empty_response_budget(provider),cloud_policy_prompt=cloud_policy_prompt)
            now=timezone.now(); decision=str(review.get('decision') or 'review'); applied_decision=decision; raw_fit=review.get('fit_score')
            try: new_fit=max(0,min(100,int(raw_fit))) if raw_fit is not None else old_fit
            except Exception: new_fit=old_fit
            try: metadata_result=_manual_hidden_lead_metadata_refresh(lead,review,provider,model)
            except Exception as meta_exc: metadata_result={'refreshed':[],'changes':[{'field':'Metadata','note':str(meta_exc)[:240]}]}
            state=dict(lead.ai_state or {})
            if raw_fit is not None: state['fit_classification']={'score':new_fit,'confidence':int(review.get('fit_confidence') or 0),'reason':str(review.get('fit_reason') or '')[:1600],'source':'Manual re-evaluation','provider':provider,'model':model,'at':now.isoformat()}
            lead.score=new_fit
            if decision=='recycle' and protected:
                applied_decision='protected'; state['manual_hidden_lead_filter']={**review,'at':now.isoformat(),'applied_decision':'protected','fit_before':old_fit,'fit_after':new_fit}; lead.ai_state=state; lead.save(update_fields=['score','ai_state','updated_at']); stat='protected'
            elif decision=='convert_to_opportunity':
                state['manual_hidden_lead_filter']={**review,'at':now.isoformat(),'applied_decision':'converted_to_opportunity','fit_before':old_fit,'fit_after':new_fit}; lead.ai_state=state; lead.save(update_fields=['score','ai_state','updated_at'])
                converted,reused=_manual_convert_hidden_lead_to_opportunity(lead,review,new_fit,now); applied_decision='converted_to_opportunity'; stat='converted_to_opportunity'
            elif decision=='recycle':
                lead.user_deleted=True; lead.deleted_at=now; lead.is_read=True; state['manual_hidden_lead_filter']={**review,'at':now.isoformat(),'applied_decision':'recycled','fit_before':old_fit,'fit_after':new_fit}; lead.ai_state=state; lead.save(update_fields=['score','user_deleted','deleted_at','is_read','ai_state','updated_at']); stat='recycled'
            else:
                state['manual_hidden_lead_filter']={**review,'at':now.isoformat(),'applied_decision':decision,'fit_before':old_fit,'fit_after':new_fit}; lead.ai_state=state; lead.save(update_fields=['score','ai_state','updated_at']); stat='kept' if decision=='keep' else 'review'
            return {'stat':stat,'item':{'id':lead.pk,'company':lead.company[:220],'decision':applied_decision,'purpose':review.get('purpose',''),'confidence':review.get('confidence',0),'reason':str(review.get('reason') or '')[:600],'fit_before':old_fit,'fit_after':new_fit,'fit_changed':new_fit!=old_fit,'fit_confidence':int(review.get('fit_confidence') or 0),'fit_reason':str(review.get('fit_reason') or '')[:600],'provider':review.get('provider',''),'model':review.get('model',''),'internet_search':bool(review.get('internet_search')),'web_sources':(review.get('web_sources') or [])[:8],'web_queries_count':int(review.get('web_queries_count') or 0),'metadata_refreshed':metadata_result.get('refreshed') or [],'metadata_changes':metadata_result.get('changes') or [],'converted_id':(converted.pk if decision=='convert_to_opportunity' else None),'converted_reused':(reused if decision=='convert_to_opportunity' else False)}}
        except CloudLimitReached as exc: return {'fatal':'cloud_limit','stat':'failed','item':{'id':lead_id,'decision':'failed','reason':str(exc)[:600]}}
        except AIEmptyOutputWarning as exc: return {'stat':'failed','empty_attempts':max(1,int(getattr(exc,'empty_attempts',1) or 1)),'item':{'id':lead_id,'decision':'failed','reason':str(exc)[:600]}}
        except Exception as exc: return _manual_filter_exception_result({'id':lead_id,'company':lead.company[:220]},exc)
        finally: close_old_connections()
    failure_signatures={}
    empty_streak=0
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=MANUAL_FILTER_CLOUD_PARALLELISM) as pool:
            for future,item_id in _bounded_parallel_futures(pool,worker,ids,MANUAL_FILTER_CLOUD_PARALLELISM):
                job.refresh_from_db(fields=['status'])
                if job.status=='stopped': stats['unprocessed']=max(0,total-stats.get('processed',0)); job.result=stats; job.save(update_fields=['result']); return stats
                try: result=future.result()
                except Exception as exc: result=_manual_filter_exception_result({'id':item_id},exc)
                stat=result.get('stat') or 'review'; stats['processed']+=1; stats[stat]=int(stats.get(stat) or 0)+1
                empty_attempts=int(result.get('empty_attempts') or 0)
                if empty_attempts:
                    stats['empty_response_attempts']+=empty_attempts; empty_streak+=empty_attempts; stats['consecutive_empty_responses']=empty_streak
                else:
                    empty_streak=0; stats['consecutive_empty_responses']=0
                _bounded_items_append(stats,result.get('item') or {'id':item_id,'decision':stat})
                if result.get('fatal')=='cloud_limit': return _stop_manual_filter(job,stats,'Hidden Lead',notify_email,total,f'Hidden Lead re-evaluation stopped early · Cloud AI limit reached · {stats["processed"]}/{total} checked')
                if empty_streak>=3: return _stop_manual_filter_after_empty_responses(job,stats,'Hidden Lead',notify_email,stats['processed'],total,empty_streak)
                signature=_manual_filter_internal_failure_signature(result)
                if signature:
                    count=failure_signatures.get(signature,0)+1; failure_signatures[signature]=count
                    if count>=MANUAL_FILTER_INTERNAL_FAILURE_THRESHOLD and count==int(stats.get('processed') or 0):
                        return _fail_manual_filter_repeated_internal_error(job,stats,'Hidden Lead',notify_email,total,signature,count)
                _parallel_progress_update(job,stats,total,'Hidden Leads',provider,model)
        return _parallel_filter_finalize(job,stats,'Hidden Lead',notify_email,total)
    except Exception as exc:
        try: stats['fatal_error']=str(exc)[:1000]; job.result=stats; job.save(update_fields=['result'])
        except Exception: pass
        _job_fail(job,exc); raise


def _parallel_contact_filter(job, ids, provider, model, internet_search, notify_email):
    total=len(ids); _job_start(job,f'Re-evaluating Address Book · 0/{total} · {provider} · {model} · {MANUAL_FILTER_CLOUD_PARALLELISM} tracks')
    stats={'selected':total,'processed':0,'kept':0,'recycled':0,'protected':0,'review':0,'failed':0,'timed_out':0,'unprocessed':0,'items':[], 'provider':provider,'model':model,'internet_search':internet_search,'parallel_tracks':MANUAL_FILTER_CLOUD_PARALLELISM,'empty_response_attempts':0,'consecutive_empty_responses':0,'circuit_breaker':{}}
    def worker(contact_id):
        close_old_connections()
        contact=Contact.objects.filter(pk=contact_id,deleted_at__isnull=True).first()
        if not contact: return {'stat':'review','item':{'id':contact_id,'decision':'review','reason':'Address Book entry is no longer active.'}}
        current_intel=dict(contact.company_intel or {}); current_fit=current_intel.get('fit_classification') if isinstance(current_intel.get('fit_classification'),dict) else {}
        try: old_fit=max(0,min(100,int(current_fit.get('score') or 0)))
        except Exception: old_fit=0
        try:
            with scoped_usage_context(operation=budget_operation_for_phase('manual'),subject_type='contact',subject_id=str(contact.pk)):
                review=classify_existing_contact(contact,provider=provider,model=model,internet_search=internet_search,empty_response_budget=_parallel_manual_filter_empty_response_budget(provider))
            now=timezone.now(); decision=str(review.get('decision') or 'review'); raw_fit=review.get('fit_score')
            try: new_fit=max(0,min(100,int(raw_fit))) if raw_fit is not None else old_fit
            except Exception: new_fit=old_fit
            try: metadata_result=_manual_contact_metadata_refresh(contact,review,provider,model)
            except Exception as meta_exc: metadata_result={'refreshed':[],'changes':[{'field':'Company Info','note':str(meta_exc)[:240]}]}
            intel=dict(contact.company_intel or {})
            if raw_fit is not None: intel['fit_classification']={'score':new_fit,'confidence':int(review.get('fit_confidence') or 0),'reason':str(review.get('fit_reason') or '')[:1600],'source':'Manual re-evaluation','provider':provider,'model':model,'at':now.isoformat()}
            intel['manual_contact_filter']={**review,'at':now.isoformat(),'applied_decision':decision,'fit_before':old_fit,'fit_after':new_fit}; contact.company_intel=intel; fields=['company_intel']
            protected_manual=str(contact.source or '').strip().lower()=='manual'; protected_history=bool(Application.objects.filter(opportunity__contact_email__iexact=contact.email,deleted_at__isnull=True).exists())
            if decision=='recycle' and (protected_manual or protected_history):
                decision='review'; intel['manual_contact_filter']['protection_reason']='Manual contact' if protected_manual else 'Application/outreach history'; stat='protected'
            elif decision=='recycle':
                contact.deleted_at=now; contact.is_read=True; fields+=['deleted_at','is_read']; stat='recycled'
            elif decision=='keep': stat='kept'
            else: stat='review'
            contact.save(update_fields=list(dict.fromkeys(fields)))
            return {'stat':stat,'item':{'id':contact.pk,'title':contact.name[:200],'company':contact.company[:200],'email':contact.email[:254],'decision':'recycled' if decision=='recycle' else decision,'purpose':review.get('purpose',''),'confidence':review.get('confidence',0),'reason':str(review.get('reason') or '')[:600],'fit_before':old_fit,'fit_after':new_fit,'fit_changed':new_fit!=old_fit,'fit_confidence':int(review.get('fit_confidence') or 0),'fit_reason':str(review.get('fit_reason') or '')[:600],'provider':review.get('provider',''),'model':review.get('model',''),'internet_search':bool(review.get('internet_search')),'web_sources':(review.get('web_sources') or [])[:8],'metadata_refreshed':metadata_result.get('refreshed') or [],'metadata_changes':metadata_result.get('changes') or []}}
        except CloudLimitReached as exc: return {'fatal':'cloud_limit','stat':'failed','item':{'id':contact_id,'decision':'failed','reason':str(exc)[:600]}}
        except AIEmptyOutputWarning as exc: return {'stat':'failed','empty_attempts':max(1,int(getattr(exc,'empty_attempts',1) or 1)),'item':{'id':contact_id,'decision':'failed','reason':str(exc)[:600]}}
        except Exception as exc: return _manual_filter_exception_result({'id':contact_id,'title':contact.name[:200],'company':contact.company[:200],'email':contact.email[:254]},exc)
        finally: close_old_connections()
    failure_signatures={}
    empty_streak=0
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=MANUAL_FILTER_CLOUD_PARALLELISM) as pool:
            for future,item_id in _bounded_parallel_futures(pool,worker,ids,MANUAL_FILTER_CLOUD_PARALLELISM):
                job.refresh_from_db(fields=['status'])
                if job.status=='stopped': stats['unprocessed']=max(0,total-stats.get('processed',0)); job.result=stats; job.save(update_fields=['result']); return stats
                try: result=future.result()
                except Exception as exc: result=_manual_filter_exception_result({'id':item_id},exc)
                stat=result.get('stat') or 'review'; stats['processed']+=1; stats[stat]=int(stats.get(stat) or 0)+1
                empty_attempts=int(result.get('empty_attempts') or 0)
                if empty_attempts:
                    stats['empty_response_attempts']+=empty_attempts; empty_streak+=empty_attempts; stats['consecutive_empty_responses']=empty_streak
                else:
                    empty_streak=0; stats['consecutive_empty_responses']=0
                _bounded_items_append(stats,result.get('item') or {'id':item_id,'decision':stat})
                if result.get('fatal')=='cloud_limit': return _stop_manual_filter(job,stats,'Address Book',notify_email,total,f'Address Book re-evaluation stopped early · Cloud AI limit reached · {stats["processed"]}/{total} checked')
                if empty_streak>=3: return _stop_manual_filter_after_empty_responses(job,stats,'Address Book',notify_email,stats['processed'],total,empty_streak)
                signature=_manual_filter_internal_failure_signature(result)
                if signature:
                    count=failure_signatures.get(signature,0)+1; failure_signatures[signature]=count
                    if count>=MANUAL_FILTER_INTERNAL_FAILURE_THRESHOLD and count==int(stats.get('processed') or 0):
                        return _fail_manual_filter_repeated_internal_error(job,stats,'Address Book',notify_email,total,signature,count)
                _parallel_progress_update(job,stats,total,'Address Book',provider,model)
        return _parallel_filter_finalize(job,stats,'Address Book',notify_email,total)
    except Exception as exc:
        try: stats['fatal_error']=str(exc)[:1000]; job.result=stats; job.save(update_fields=['result'])
        except Exception: pass
        _job_fail(job,exc); raise


@shared_task(bind=True)
def opportunity_filter_job(self, job_id, opportunity_ids, provider='', model='', internet_search=False, cloud_policy_prompt=''):
    """Re-run the configured first-filter gate on selected persisted Opportunities.

    The task is deliberately conservative: only high-confidence rejects are moved to the
    Recycle Bin, uncertain rows stay put, and anything with application/outreach history
    or application preparation already requested is protected from automatic recycling.
    """
    job=BackgroundJob.objects.get(pk=job_id)
    initial=dict(job.result or {})
    provider=str(provider or initial.get('provider') or '').strip().lower()
    model=str(model or initial.get('model') or '').strip()
    internet_search=bool(internet_search if internet_search is not None else initial.get('internet_search')) and provider in ('openai','gemini','openrouter')
    cloud_policy_prompt=str(cloud_policy_prompt or initial.get('cloud_re_evaluation_prompt') or '').strip()[:4000] if provider in ('openai','gemini','openrouter') else ''
    notify_email=str(initial.get('notify_email') or '').strip()
    job.celery_task_id=self.request.id or ''
    ids=[]
    for raw in opportunity_ids or []:
        try:
            value=int(raw)
        except Exception:
            continue
        if value > 0 and value not in ids:
            ids.append(value)
    total=len(ids)
    _job_start(job,f'Re-evaluating opportunities · 0/{total} · {provider} · {model}')
    stats={
        'selected':total,'processed':0,'kept':0,'recycled':0,'protected':0,
        'converted_to_hidden_lead':0,'converted_to_opportunity':0,
        'review':0,'failed':0,'timed_out':0,'unprocessed':0,'items':[],
        'provider':provider,'model':model,'internet_search':internet_search,'cloud_re_evaluation_prompt':cloud_policy_prompt,
        'empty_response_attempts':0,'consecutive_empty_responses':0,'circuit_breaker':{},
    }
    empty_streak=0
    failure_signatures={}
    if _manual_filter_parallel_enabled(provider):
        return _parallel_opportunity_filter(job,ids,provider,model,internet_search,notify_email,cloud_policy_prompt)
    try:
        for index,opportunity_id in enumerate(ids,1):
            job.refresh_from_db(fields=['status'])
            if job.status=='stopped':
                stats['unprocessed']=max(0,total-stats['processed'])
                job.result=stats
                job.save(update_fields=['result'])
                return stats

            opp=Opportunity.objects.filter(pk=opportunity_id,suppressed=False,user_deleted=False).first()
            if not opp:
                stats['processed']+=1
                stats['review']+=1
                stats['items'].append({'id':opportunity_id,'decision':'review','reason':'Opportunity is no longer active.'})
            else:
                old_fit=int(opp.fit_score or 0)
                protected=bool(
                    Application.objects.filter(opportunity=opp).exists()
                    or opp.application_draft_requested_at
                    or BackgroundJob.objects.filter(
                        kind='prepare',status__in=['queued','running'],result__opportunity_id=opp.pk
                    ).exclude(pk=job.pk).exists()
                )
                _manual_filter_item_started(
                    job,stats,noun='opportunity',index=index,total=total,provider=provider,model=model,
                    internet_search=internet_search,item_label=' — '.join(x for x in (opp.company,opp.title) if x),
                )
                try:
                    campaign_id,run_id=_usage_ids_for_entity(opp)
                    with scoped_usage_context(
                        campaign_id=campaign_id,campaign_run_id=run_id,operation=budget_operation_for_phase('manual'),
                        subject_type='opportunity',subject_id=str(opp.pk),
                    ):
                        review=classify_existing_opportunity(opp,provider=provider,model=model,internet_search=internet_search,empty_response_budget=max(1,3-empty_streak),cloud_policy_prompt=cloud_policy_prompt)
                    empty_streak=0
                    stats['consecutive_empty_responses']=0
                    decision=str(review.get('decision') or 'review')
                    applied_decision=decision
                    now=timezone.now()
                    raw_fit=review.get('fit_score')
                    try:
                        new_fit=max(0,min(100,int(raw_fit))) if raw_fit is not None else old_fit
                    except Exception:
                        new_fit=old_fit
                    fit_changed=new_fit!=old_fit
                    refreshed_summary=''
                    try:
                        from portal.services.highlights import normalize_ai_fit_summary
                        refreshed_summary=normalize_ai_fit_summary(review.get('highlight') or '',max_words=50)
                        if not refreshed_summary:
                            refreshed_summary=derive_opportunity_highlight(opportunity=opp,title=opp.title,description=opp.description or opp.raw_search_snippet,facts=opp.extracted_facts or {},remote_text=opp.remote_text)
                        if refreshed_summary:
                            opp.list_highlight=refreshed_summary[:600]
                    except Exception:
                        refreshed_summary=''
                    metadata_result={'refreshed':[],'changes':[]}
                    try:
                        metadata_result=_manual_opportunity_metadata_refresh(opp,review,provider,model)
                    except Exception as meta_exc:
                        metadata_result={'refreshed':[],'changes':[{'field':'Metadata','before':'','after':'','note':str(meta_exc)[:240]}]}
                    facts=dict(opp.extracted_facts or {})
                    if raw_fit is not None:
                        facts['fit_classification']={
                            'score':new_fit,'confidence':int(review.get('fit_confidence') or 0),
                            'reason':str(review.get('fit_reason') or '')[:1600],
                            'recommendation':str((facts.get('fit_classification') or {}).get('recommendation') or 'Unknown')[:80],
                            'source':'Manual re-evaluation','provider':provider,'model':model,'at':now.isoformat(),
                        }
                    opp.fit_score=new_fit
                    converted=None; reused=False
                    if decision=='recycle' and protected:
                        applied_decision='protected'
                        facts['manual_opportunity_filter']={**review,'at':now.isoformat(),'applied_decision':'protected','fit_before':old_fit,'fit_after':new_fit}
                        opp.extracted_facts=facts
                        opp.save(update_fields=['fit_score','list_highlight','extracted_facts','updated_at'])
                        stats['protected']+=1
                    elif decision=='convert_to_hidden_lead':
                        facts['manual_opportunity_filter']={**review,'at':now.isoformat(),'applied_decision':'converted_to_hidden_lead','fit_before':old_fit,'fit_after':new_fit}
                        opp.extracted_facts=facts
                        opp.save(update_fields=['fit_score','list_highlight','extracted_facts','updated_at'])
                        converted,reused=_manual_convert_opportunity_to_hidden_lead(opp,review,new_fit,now)
                        applied_decision='converted_to_hidden_lead'; stats['converted_to_hidden_lead']+=1
                    elif decision=='recycle':
                        reason=str(review.get('reason') or 'High-confidence manual Opportunity re-evaluation rejection.').strip()
                        opp.suppressed=True
                        opp.user_deleted=True
                        opp.deleted_at=now
                        opp.is_read=True
                        opp.rejection_reason=('Opportunity re-evaluation: '+reason)[:4000]
                        facts['manual_opportunity_filter']={**review,'at':now.isoformat(),'applied_decision':'recycled','fit_before':old_fit,'fit_after':new_fit}
                        opp.extracted_facts=facts
                        opp.save(update_fields=['fit_score','list_highlight','suppressed','user_deleted','deleted_at','is_read','rejection_reason','extracted_facts','updated_at'])
                        stats['recycled']+=1
                    else:
                        facts['manual_opportunity_filter']={**review,'at':now.isoformat(),'applied_decision':decision,'fit_before':old_fit,'fit_after':new_fit}
                        opp.extracted_facts=facts
                        opp.save(update_fields=['fit_score','list_highlight','extracted_facts','updated_at'])
                        if decision=='keep': stats['kept']+=1
                        else: stats['review']+=1
                    stats['processed']+=1
                    stats['items'].append({
                        'id':opp.pk,'title':opp.title[:300],'company':opp.company[:220],
                        'decision':applied_decision,'purpose':review.get('purpose',''),
                        'confidence':review.get('confidence',0),'reason':str(review.get('reason') or '')[:600],
                        'fit_before':old_fit,'fit_after':new_fit,'fit_changed':fit_changed,
                        'fit_confidence':int(review.get('fit_confidence') or 0),'fit_reason':str(review.get('fit_reason') or '')[:600],
                        'provider':review.get('provider',''),'model':review.get('model',''),
                        'internet_search':bool(review.get('internet_search')),'web_sources':(review.get('web_sources') or [])[:8],
                        'web_queries_count':int(review.get('web_queries_count') or 0),
                        'empty_output_retry':bool(review.get('empty_output_retry')),
                        'metadata_refreshed':list(dict.fromkeys((metadata_result.get('refreshed') or [])+(['Summary'] if refreshed_summary else []))),
                        'metadata_changes':metadata_result.get('changes') or [],
                        'converted_id':converted.pk if converted else None,'converted_reused':reused,
                    })
                except AIEmptyOutputWarning as exc:
                    try:
                        empty_attempts=max(1,int(getattr(exc,'empty_attempts',1) or 1))
                    except Exception:
                        empty_attempts=1
                    empty_streak+=empty_attempts
                    stats['empty_response_attempts']+=empty_attempts
                    stats['consecutive_empty_responses']=empty_streak
                    stats['failed']+=1
                    stats['processed']+=1
                    stats['items'].append({
                        'id':opp.pk,'title':opp.title[:300],'company':opp.company[:220],
                        'decision':'failed','reason':(
                            f'AI provider returned no visible output after {empty_attempts} attempt'
                            f'{"" if empty_attempts==1 else "s"}. '
                            f'Consecutive empty-response streak: {empty_streak}.'
                        )[:600],
                    })
                    if empty_streak>=3:
                        _manual_filter_item_finished(stats)
                        return _stop_manual_filter_after_empty_responses(job,stats,'Opportunity',notify_email,index,total,empty_streak)
                except CloudLimitReached as exc:
                    stats['failed']+=1
                    stats['processed']+=1
                    stats['unprocessed']=max(0,total-index)
                    stats['items'].append({'id':opp.pk,'title':opp.title[:300],'company':opp.company[:220],'decision':'failed','reason':str(exc)[:600]})
                    _manual_filter_item_finished(stats)
                    return _stop_manual_filter(
                        job,stats,'Opportunity',notify_email,total,
                        f'Opportunity re-evaluation stopped early · Cloud AI limit reached · {stats["processed"]}/{total} checked'
                    )
                except Exception as exc:
                    empty_streak=0
                    stats['consecutive_empty_responses']=0
                    stats['failed']+=1
                    stats['processed']+=1
                    result=_manual_filter_exception_result({'id':opp.pk,'title':opp.title[:300],'company':opp.company[:220]},exc)
                    stats['items'].append(result['item'])
                    signature=_manual_filter_internal_failure_signature(result)
                    if signature:
                        count=failure_signatures.get(signature,0)+1; failure_signatures[signature]=count
                        if count>=MANUAL_FILTER_INTERNAL_FAILURE_THRESHOLD and count==int(stats.get('processed') or 0):
                            _manual_filter_item_finished(stats)
                            return _fail_manual_filter_repeated_internal_error(job,stats,'Opportunity',notify_email,total,signature,count)

            _manual_filter_item_finished(stats)
            job.progress=_manual_filter_progress(stats,total)
            job.message=f'Re-evaluated opportunities · {stats.get("processed",0)}/{total} · {provider} · {model}'
            job.result=stats
            job.save(update_fields=['progress','message','result'])

        message=(f'Opportunity re-evaluation complete · {stats["kept"]} kept · {stats["recycled"]} recycled'
                 + (f' · {stats.get("converted_to_hidden_lead",0)} → Hidden Leads' if stats.get('converted_to_hidden_lead') else '')
                 + (f' · {stats["protected"]} protected' if stats['protected'] else '')
                 + (f' · {stats["review"]} need review' if stats['review'] else '')
                 + (f' · {stats["timed_out"]} timed out' if stats['timed_out'] else '')
               + (f' · {stats.get("skipped_current",0)} skipped' if stats.get('skipped_current') else '')
               + (f' · {stats["failed"]} failed' if stats['failed'] else ''))
        if _manual_filter_all_selected_failed(stats,total):
            reason=_manual_filter_common_failure_reason(stats)
            return _fail_manual_filter_job(job,stats,'Opportunity',notify_email,total,reason,f'Opportunity re-evaluation failed · every selected item failed · {stats["processed"]}/{total} checked')
        _manual_filter_notification(job,stats,'Opportunity',notify_email)
        _job_done(job,stats,message)
        return stats
    except Exception as exc:
        try:
            stats['unprocessed']=max(0,total-stats.get('processed',0))
            stats['fatal_error']=str(exc)[:1000]
            _manual_filter_notification(job,stats,'Opportunity',notify_email,failed=True)
            job.result=stats; job.save(update_fields=['result'])
        except Exception:
            pass
        _job_fail(job,exc)
        raise


@shared_task(bind=True)
def hidden_lead_filter_job(self, job_id, lead_ids, provider='', model='', internet_search=False, cloud_policy_prompt=''):
    """Re-run the configured first-filter gate on selected persisted Hidden Leads.

    Only high-confidence noise/irrelevance is recycled. Concrete jobs/contracts and
    ambiguous rows stay visible for review. Existing outreach/application work protects
    a lead from automatic recycling, but a high-confidence cross-list conversion is still allowed.
    """
    job=BackgroundJob.objects.get(pk=job_id)
    initial=dict(job.result or {})
    provider=str(provider or initial.get('provider') or '').strip().lower()
    model=str(model or initial.get('model') or '').strip()
    internet_search=bool(internet_search if internet_search is not None else initial.get('internet_search')) and provider in ('openai','gemini','openrouter')
    cloud_policy_prompt=str(cloud_policy_prompt or initial.get('cloud_re_evaluation_prompt') or '').strip()[:4000] if provider in ('openai','gemini','openrouter') else ''
    notify_email=str(initial.get('notify_email') or '').strip()
    job.celery_task_id=self.request.id or ''
    ids=[]
    for raw in lead_ids or []:
        try:
            value=int(raw)
        except Exception:
            continue
        if value > 0 and value not in ids:
            ids.append(value)
    total=len(ids)
    _job_start(job,f'Re-evaluating Hidden Leads · 0/{total} · {provider} · {model}')
    stats={
        'selected':total,'processed':0,'kept':0,'recycled':0,'protected':0,
        'converted_to_hidden_lead':0,'converted_to_opportunity':0,
        'review':0,'failed':0,'timed_out':0,'unprocessed':0,'items':[],
        'provider':provider,'model':model,'internet_search':internet_search,'cloud_re_evaluation_prompt':cloud_policy_prompt,
        'empty_response_attempts':0,'consecutive_empty_responses':0,'circuit_breaker':{},
    }
    empty_streak=0
    failure_signatures={}
    if _manual_filter_parallel_enabled(provider):
        return _parallel_hidden_lead_filter(job,ids,provider,model,internet_search,notify_email,cloud_policy_prompt)
    try:
        for index,lead_id in enumerate(ids,1):
            job.refresh_from_db(fields=['status'])
            if job.status=='stopped':
                stats['unprocessed']=max(0,total-stats['processed'])
                job.result=stats
                job.save(update_fields=['result'])
                return stats

            lead=CompanyLead.objects.filter(pk=lead_id,user_deleted=False).first()
            if not lead:
                stats['processed']+=1
                stats['review']+=1
                stats['items'].append({'id':lead_id,'decision':'review','reason':'Hidden Lead is no longer active.'})
            else:
                old_fit=int(lead.score or 0)
                protected=_hidden_lead_has_outreach(lead)
                _manual_filter_item_started(
                    job,stats,noun='Hidden Lead',index=index,total=total,provider=provider,model=model,
                    internet_search=internet_search,item_label=lead.company,
                )
                try:
                    campaign_id,run_id=_usage_ids_for_entity(lead)
                    with scoped_usage_context(
                        campaign_id=campaign_id,campaign_run_id=run_id,operation=budget_operation_for_phase('manual'),
                        subject_type='hidden lead',subject_id=str(lead.pk),
                    ):
                        review=classify_existing_hidden_lead(lead,provider=provider,model=model,internet_search=internet_search,empty_response_budget=max(1,3-empty_streak),cloud_policy_prompt=cloud_policy_prompt)
                    empty_streak=0
                    stats['consecutive_empty_responses']=0
                    decision=str(review.get('decision') or 'review')
                    applied_decision=decision
                    now=timezone.now()
                    raw_fit=review.get('fit_score')
                    try:
                        new_fit=max(0,min(100,int(raw_fit))) if raw_fit is not None else old_fit
                    except Exception:
                        new_fit=old_fit
                    fit_changed=new_fit!=old_fit
                    metadata_result={'refreshed':[],'changes':[]}
                    try:
                        metadata_result=_manual_hidden_lead_metadata_refresh(lead,review,provider,model)
                    except Exception as meta_exc:
                        metadata_result={'refreshed':[],'changes':[{'field':'Metadata','before':'','after':'','note':str(meta_exc)[:240]}]}
                    state=dict(lead.ai_state or {})
                    if raw_fit is not None:
                        state['fit_classification']={
                            'score':new_fit,'confidence':int(review.get('fit_confidence') or 0),
                            'reason':str(review.get('fit_reason') or '')[:1600],
                            'source':'Manual re-evaluation','provider':provider,'model':model,'at':now.isoformat(),
                        }
                    lead.score=new_fit
                    converted=None; reused=False
                    if decision=='recycle' and protected:
                        applied_decision='protected'
                        state['manual_hidden_lead_filter']={**review,'at':now.isoformat(),'applied_decision':'protected','fit_before':old_fit,'fit_after':new_fit}
                        lead.ai_state=state
                        lead.save(update_fields=['score','ai_state','updated_at'])
                        stats['protected']+=1
                    elif decision=='convert_to_opportunity':
                        state['manual_hidden_lead_filter']={**review,'at':now.isoformat(),'applied_decision':'converted_to_opportunity','fit_before':old_fit,'fit_after':new_fit}
                        lead.ai_state=state
                        lead.save(update_fields=['score','ai_state','updated_at'])
                        converted,reused=_manual_convert_hidden_lead_to_opportunity(lead,review,new_fit,now)
                        applied_decision='converted_to_opportunity'; stats['converted_to_opportunity']+=1
                    elif decision=='recycle':
                        lead.user_deleted=True
                        lead.deleted_at=now
                        lead.is_read=True
                        state['manual_hidden_lead_filter']={**review,'at':now.isoformat(),'applied_decision':'recycled','fit_before':old_fit,'fit_after':new_fit}
                        lead.ai_state=state
                        lead.save(update_fields=['score','user_deleted','deleted_at','is_read','ai_state','updated_at'])
                        stats['recycled']+=1
                    else:
                        state['manual_hidden_lead_filter']={**review,'at':now.isoformat(),'applied_decision':decision,'fit_before':old_fit,'fit_after':new_fit}
                        lead.ai_state=state
                        lead.save(update_fields=['score','ai_state','updated_at'])
                        if decision=='keep': stats['kept']+=1
                        else: stats['review']+=1
                    stats['processed']+=1
                    stats['items'].append({
                        'id':lead.pk,'company':lead.company[:220],
                        'decision':applied_decision,'purpose':review.get('purpose',''),
                        'confidence':review.get('confidence',0),'reason':str(review.get('reason') or '')[:600],
                        'fit_before':old_fit,'fit_after':new_fit,'fit_changed':fit_changed,
                        'fit_confidence':int(review.get('fit_confidence') or 0),'fit_reason':str(review.get('fit_reason') or '')[:600],
                        'provider':review.get('provider',''),'model':review.get('model',''),
                        'internet_search':bool(review.get('internet_search')),'web_sources':(review.get('web_sources') or [])[:8],
                        'web_queries_count':int(review.get('web_queries_count') or 0),
                        'empty_output_retry':bool(review.get('empty_output_retry')),
                        'metadata_refreshed':metadata_result.get('refreshed') or [],
                        'metadata_changes':metadata_result.get('changes') or [],
                        'converted_id':converted.pk if converted else None,'converted_reused':reused,
                    })
                except AIEmptyOutputWarning as exc:
                    try:
                        empty_attempts=max(1,int(getattr(exc,'empty_attempts',1) or 1))
                    except Exception:
                        empty_attempts=1
                    empty_streak+=empty_attempts
                    stats['empty_response_attempts']+=empty_attempts
                    stats['consecutive_empty_responses']=empty_streak
                    stats['failed']+=1
                    stats['processed']+=1
                    stats['items'].append({
                        'id':lead.pk,'company':lead.company[:220],
                        'decision':'failed','reason':(
                            f'AI provider returned no visible output after {empty_attempts} attempt'
                            f'{"" if empty_attempts==1 else "s"}. '
                            f'Consecutive empty-response streak: {empty_streak}.'
                        )[:600],
                    })
                    if empty_streak>=3:
                        _manual_filter_item_finished(stats)
                        return _stop_manual_filter_after_empty_responses(job,stats,'Hidden Lead',notify_email,index,total,empty_streak)
                except CloudLimitReached as exc:
                    stats['failed']+=1
                    stats['processed']+=1
                    stats['unprocessed']=max(0,total-index)
                    stats['items'].append({'id':lead.pk,'company':lead.company[:220],'decision':'failed','reason':str(exc)[:600]})
                    _manual_filter_item_finished(stats)
                    return _stop_manual_filter(
                        job,stats,'Hidden Lead',notify_email,total,
                        f'Hidden Lead re-evaluation stopped early · Cloud AI limit reached · {stats["processed"]}/{total} checked'
                    )
                except Exception as exc:
                    empty_streak=0
                    stats['consecutive_empty_responses']=0
                    stats['failed']+=1
                    stats['processed']+=1
                    result=_manual_filter_exception_result({'id':lead.pk,'company':lead.company[:220]},exc)
                    stats['items'].append(result['item'])
                    signature=_manual_filter_internal_failure_signature(result)
                    if signature:
                        count=failure_signatures.get(signature,0)+1; failure_signatures[signature]=count
                        if count>=MANUAL_FILTER_INTERNAL_FAILURE_THRESHOLD and count==int(stats.get('processed') or 0):
                            _manual_filter_item_finished(stats)
                            return _fail_manual_filter_repeated_internal_error(job,stats,'Hidden Lead',notify_email,total,signature,count)

            _manual_filter_item_finished(stats)
            job.progress=_manual_filter_progress(stats,total)
            job.message=f'Re-evaluated Hidden Leads · {stats.get("processed",0)}/{total} · {provider} · {model}'
            job.result=stats
            job.save(update_fields=['progress','message','result'])

        message=(f'Hidden Lead re-evaluation complete · {stats["kept"]} kept · {stats["recycled"]} recycled'
                 + (f' · {stats.get("converted_to_opportunity",0)} → Opportunities' if stats.get('converted_to_opportunity') else '')
                 + (f' · {stats["protected"]} protected' if stats['protected'] else '')
                 + (f' · {stats["review"]} need review' if stats['review'] else '')
                 + (f' · {stats["timed_out"]} timed out' if stats['timed_out'] else '')
               + (f' · {stats.get("skipped_current",0)} skipped' if stats.get('skipped_current') else '')
               + (f' · {stats["failed"]} failed' if stats['failed'] else ''))
        if _manual_filter_all_selected_failed(stats,total):
            reason=_manual_filter_common_failure_reason(stats)
            return _fail_manual_filter_job(job,stats,'Hidden Lead',notify_email,total,reason,f'Hidden Lead re-evaluation failed · every selected item failed · {stats["processed"]}/{total} checked')
        _manual_filter_notification(job,stats,'Hidden Lead',notify_email)
        _job_done(job,stats,message)
        return stats
    except Exception as exc:
        try:
            stats['unprocessed']=max(0,total-stats.get('processed',0))
            stats['fatal_error']=str(exc)[:1000]
            _manual_filter_notification(job,stats,'Hidden Lead',notify_email,failed=True)
            job.result=stats; job.save(update_fields=['result'])
        except Exception:
            pass
        _job_fail(job,exc)
        raise


@shared_task(bind=True)
def opportunity_enrich_job(self, job_id, opportunity_id):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Fetching and analysing opportunity')
    try:
        opp=Opportunity.objects.get(pk=opportunity_id); job.progress=20; job.save(update_fields=['progress'])
        result=enrich(opp,allow_ai=True); _job_done(job,result,'Opportunity enrichment completed'); return result
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task(bind=True)
def opportunity_summary_job(self, job_id, opportunity_id, phase='manual'):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Summarizing job / lead text')
    try:
        opp=Opportunity.objects.get(pk=opportunity_id)
        facts=opp.extracted_facts or {}
        source=(opp.description or opp.raw_search_snippet or '').strip()
        if not source:
            html_source=str(facts.get('description_html') or '')
            source=unescape(re.sub(r'<[^>]+>', ' ', html_source))
            source=re.sub(r'\s+', ' ', source).strip()
        if not source:
            raise RuntimeError('No job / lead text is available to summarize.')
        source_hash=hashlib.sha256(source.encode('utf-8','ignore')).hexdigest()
        prompt=(
            'Summarize the following job or lead text for a technical candidate reviewing whether to pursue it.\n'
            'Use only facts present in the source. Do not invent requirements, compensation, company facts, or an open role if none is stated.\n'
            'Write four concise paragraphs with these labels: Role / need, Technical areas, Engagement clues, Caveats.\n'
            'Keep the whole summary around 120-220 words. Explicitly say when the source appears to be a technical/project signal rather than a formal vacancy.\n\n'
            'SOURCE:\n' + source[:24000]
        )
        _cid,_rid=_usage_ids_for_entity(opp)
        with scoped_usage_context(campaign_id=_cid,campaign_run_id=_rid,operation=budget_operation_for_phase(phase),subject_type='opportunity',subject_id=str(opp.pk)):
            summary=generate(prompt,stage='page_summarization',timeout=120,subject={'type':'opportunity','id':opp.pk,'label':f'{opp.company} — {opp.title}','budget_operation':budget_operation_for_phase(phase)}).strip()
            # Some providers occasionally stop after the first labelled paragraph despite a
            # much larger output cap. Retry once only when a substantive source produced an
            # obviously incomplete answer. Both requests remain visible in AI Requests.
            if len(source) >= 500 and len(summary.split()) < 80:
                retry_prompt=(
                    prompt + '\n\nThe previous response ended too early. Return the complete 120-220 word review now, '
                    'including all four labelled paragraphs. Do not mention this retry or add facts.'
                )
                retry=generate(retry_prompt,stage='page_summarization',timeout=120,subject={'type':'opportunity','id':opp.pk,'label':f'{opp.company} — {opp.title} · complete summary','budget_operation':budget_operation_for_phase(phase)}).strip()
                if len(retry) > len(summary): summary=retry
        if not summary:
            raise RuntimeError('The AI provider returned an empty summary.')
        facts=opp.extracted_facts or {}
        facts['ai_job_summary']={'text':summary,'at':timezone.now().isoformat(),'source_hash':source_hash,'source_text':source[:45000]}
        opp.extracted_facts=facts
        opp.save(update_fields=['extracted_facts','updated_at'])
        result={'opportunity_id':opp.pk,'source_hash':source_hash}
        complete_attempt(opp,'summary',phase,'success')
        _job_done(job,result,'AI summary ready'); return result
    except CloudLimitReached as exc:
        if 'opp' in locals(): complete_attempt(opp,'summary',phase,'skipped_budget',str(exc))
        result={'opportunity_id':opportunity_id,'state':'limit_reached','detail':str(exc)}; _job_done(job,result,'Not executed — Cloud AI limit reached'); return result
    except Exception as exc:
        if 'opp' in locals(): complete_attempt(opp,'summary',phase,'failed',str(exc))
        _job_fail(job,exc); raise


@shared_task(bind=True)
def contact_filter_job(self, job_id, contact_ids, provider='', model='', internet_search=False):
    """Re-evaluate selected Address Book contacts with the same manual second-opinion workflow."""
    job=BackgroundJob.objects.get(pk=job_id)
    initial=dict(job.result or {})
    provider=str(provider or initial.get('provider') or '').strip().lower()
    model=str(model or initial.get('model') or '').strip()
    internet_search=bool(internet_search if internet_search is not None else initial.get('internet_search')) and provider in ('openai','gemini','openrouter')
    notify_email=str(initial.get('notify_email') or '').strip()
    job.celery_task_id=self.request.id or ''
    ids=[]
    for raw in contact_ids or []:
        try: value=int(raw)
        except Exception: continue
        if value>0 and value not in ids: ids.append(value)
    total=len(ids)
    _job_start(job,f'Re-evaluating Address Book · 0/{total} · {provider} · {model}')
    stats={'selected':total,'processed':0,'kept':0,'recycled':0,'protected':0,'review':0,'failed':0,'timed_out':0,'unprocessed':0,'items':[],
           'provider':provider,'model':model,'internet_search':internet_search,'empty_response_attempts':0,'consecutive_empty_responses':0,'circuit_breaker':{}}
    empty_streak=0
    failure_signatures={}
    if _manual_filter_parallel_enabled(provider):
        return _parallel_contact_filter(job,ids,provider,model,internet_search,notify_email)
    try:
        for index,contact_id in enumerate(ids,1):
            job.refresh_from_db(fields=['status'])
            if job.status=='stopped':
                stats['unprocessed']=max(0,total-stats['processed']); job.result=stats; job.save(update_fields=['result']); return stats
            contact=Contact.objects.filter(pk=contact_id,deleted_at__isnull=True).first()
            if not contact:
                stats['processed']+=1; stats['review']+=1
                stats['items'].append({'id':contact_id,'decision':'review','reason':'Address Book entry is no longer active.'})
                _manual_filter_item_finished(stats)
                continue
            current_intel=dict(contact.company_intel or {})
            current_fit=current_intel.get('fit_classification') if isinstance(current_intel.get('fit_classification'),dict) else {}
            try: old_fit=max(0,min(100,int(current_fit.get('score') or 0)))
            except Exception: old_fit=0
            _manual_filter_item_started(job,stats,noun='Address Book contact',index=index,total=total,provider=provider,model=model,internet_search=internet_search,item_label=contact.company or contact.email)
            try:
                with scoped_usage_context(operation=budget_operation_for_phase('manual'),subject_type='contact',subject_id=str(contact.pk)):
                    review=classify_existing_contact(contact,provider=provider,model=model,internet_search=internet_search,empty_response_budget=max(1,3-empty_streak))
                empty_streak=0; stats['consecutive_empty_responses']=0
                decision=str(review.get('decision') or 'review'); now=timezone.now()
                raw_fit=review.get('fit_score')
                try: new_fit=max(0,min(100,int(raw_fit))) if raw_fit is not None else old_fit
                except Exception: new_fit=old_fit
                try: metadata_result=_manual_contact_metadata_refresh(contact,review,provider,model)
                except Exception as meta_exc: metadata_result={'refreshed':[],'changes':[{'field':'Company Info','note':str(meta_exc)[:240]}]}
                intel=dict(contact.company_intel or {})
                if raw_fit is not None:
                    intel['fit_classification']={'score':new_fit,'confidence':int(review.get('fit_confidence') or 0),'reason':str(review.get('fit_reason') or '')[:1600],'source':'Manual re-evaluation','provider':provider,'model':model,'at':now.isoformat()}
                intel['manual_contact_filter']={**review,'at':now.isoformat(),'applied_decision':decision,'fit_before':old_fit,'fit_after':new_fit}
                contact.company_intel=intel
                fields=['company_intel']
                protected_manual=str(contact.source or '').strip().lower()=='manual'
                protected_history=bool(Application.objects.filter(opportunity__contact_email__iexact=contact.email,deleted_at__isnull=True).exists())
                if decision=='recycle' and (protected_manual or protected_history):
                    decision='review'; stats['protected']+=1; stats['review']+=1
                    intel['manual_contact_filter']['protection_reason']='Manual contact' if protected_manual else 'Application/outreach history'
                elif decision=='recycle':
                    contact.deleted_at=now; contact.is_read=True; fields+=['deleted_at','is_read']; stats['recycled']+=1
                elif decision=='keep': stats['kept']+=1
                else: stats['review']+=1
                contact.save(update_fields=list(dict.fromkeys(fields)))
                stats['processed']+=1
                stats['items'].append({'id':contact.pk,'title':contact.name[:200],'company':contact.company[:200],'email':contact.email[:254],'decision':'recycled' if decision=='recycle' else decision,
                    'purpose':review.get('purpose',''),'confidence':review.get('confidence',0),'reason':str(review.get('reason') or '')[:600],
                    'fit_before':old_fit,'fit_after':new_fit,'fit_changed':new_fit!=old_fit,'fit_confidence':int(review.get('fit_confidence') or 0),'fit_reason':str(review.get('fit_reason') or '')[:600],
                    'provider':review.get('provider',''),'model':review.get('model',''),'internet_search':bool(review.get('internet_search')),'web_sources':(review.get('web_sources') or [])[:8],
                    'metadata_refreshed':metadata_result.get('refreshed') or [],'metadata_changes':metadata_result.get('changes') or []})
            except AIEmptyOutputWarning as exc:
                try: empty_attempts=max(1,int(getattr(exc,'empty_attempts',1) or 1))
                except Exception: empty_attempts=1
                empty_streak+=empty_attempts; stats['empty_response_attempts']+=empty_attempts; stats['consecutive_empty_responses']=empty_streak
                stats['failed']+=1; stats['processed']+=1
                stats['items'].append({'id':contact.pk,'title':contact.name[:200],'company':contact.company[:200],'email':contact.email[:254],'decision':'failed','fit_before':old_fit,'fit_after':old_fit,'reason':str(exc)[:600]})
                if empty_streak>=3:
                    _manual_filter_item_finished(stats)
                    return _stop_manual_filter_after_empty_responses(job,stats,'Address Book',notify_email,index,total,empty_streak)
            except CloudLimitReached as exc:
                stats['failed']+=1; stats['processed']+=1; stats['fatal_error']=str(exc)[:1000]
                stats['items'].append({'id':contact.pk,'title':contact.name[:200],'company':contact.company[:200],'email':contact.email[:254],'decision':'failed','fit_before':old_fit,'fit_after':old_fit,'reason':str(exc)[:600]})
                _manual_filter_item_finished(stats)
                return _stop_manual_filter(
                    job,stats,'Address Book',notify_email,total,
                    f'Address Book re-evaluation stopped early · Cloud AI limit reached · {stats["processed"]}/{total} checked'
                )
            except Exception as exc:
                empty_streak=0; stats['consecutive_empty_responses']=0; stats['failed']+=1; stats['processed']+=1
                result=_manual_filter_exception_result({'id':contact.pk,'title':contact.name[:200],'company':contact.company[:200],'email':contact.email[:254],'fit_before':old_fit,'fit_after':old_fit},exc)
                stats['items'].append(result['item'])
                signature=_manual_filter_internal_failure_signature(result)
                if signature:
                    count=failure_signatures.get(signature,0)+1; failure_signatures[signature]=count
                    if count>=MANUAL_FILTER_INTERNAL_FAILURE_THRESHOLD and count==int(stats.get('processed') or 0):
                        _manual_filter_item_finished(stats)
                        return _fail_manual_filter_repeated_internal_error(job,stats,'Address Book',notify_email,total,signature,count)
            _manual_filter_item_finished(stats)
            job.progress=_manual_filter_progress(stats,total)
            job.message=f'Re-evaluated Address Book · {stats.get("processed",0)}/{total} · {provider} · {model}'
            job.result=stats; job.save(update_fields=['progress','message','result'])
        message=(f'Address Book re-evaluation complete · {stats["kept"]} kept · {stats["recycled"]} recycled'+(f' · {stats["review"]} need review' if stats['review'] else '')+(f' · {stats["failed"]} failed' if stats['failed'] else ''))
        if _manual_filter_all_selected_failed(stats,total):
            reason=_manual_filter_common_failure_reason(stats)
            return _fail_manual_filter_job(job,stats,'Address Book',notify_email,total,reason,f'Address Book re-evaluation failed · every selected item failed · {stats["processed"]}/{total} checked')
        _manual_filter_notification(job,stats,'Address Book',notify_email); _job_done(job,stats,message); return stats
    except Exception as exc:
        try:
            stats['unprocessed']=max(0,total-stats.get('processed',0)); stats['fatal_error']=str(exc)[:1000]
            _manual_filter_notification(job,stats,'Address Book',notify_email,failed=True); job.result=stats; job.save(update_fields=['result'])
        except Exception: pass
        _job_fail(job,exc); raise


@shared_task(bind=True)
def opportunity_freshness_job(self, job_id, opportunity_id, phase='manual'):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Refreshing post-age evidence')
    opp=None
    try:
        opp=Opportunity.objects.get(pk=opportunity_id)
        with scoped_usage_context(campaign_id=_usage_ids_for_entity(opp)[0], campaign_run_id=_usage_ids_for_entity(opp)[1], operation=budget_operation_for_phase(phase), subject_type='opportunity', subject_id=str(opp.pk)):
            result=recompute(opp)
        complete_attempt(opp,'freshness',phase,'success')
        _job_done(job,result if isinstance(result,dict) else {'result':str(result)},'Post age refreshed'); return result
    except CloudLimitReached as exc:
        if opp: complete_attempt(opp,'freshness',phase,'skipped_budget',str(exc))
        result={'opportunity_id':opportunity_id,'state':'limit_reached','detail':str(exc)}; _job_done(job,result,'Not executed — Cloud AI limit reached'); return result
    except Exception as exc:
        if opp: complete_attempt(opp,'freshness',phase,'failed',str(exc))
        _job_fail(job,exc); raise


@shared_task(bind=True)
def application_prepare_job(self, job_id, opportunity_id, cv_id=None, cover_id=None):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Preparing application')
    try:
        opp=Opportunity.objects.get(pk=opportunity_id); job.progress=20; job.save(update_fields=['progress'])
        from portal.models import DocumentAsset
        cv=DocumentAsset.objects.filter(pk=cv_id).first() if cv_id else None; cover=DocumentAsset.objects.filter(pk=cover_id).first() if cover_id else None
        app=prepare_application(opp,cv,cover); result={'application_id':app.pk,'opportunity_id':opp.pk}
        _job_done(job,result,'Application prepared'); return result
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task(bind=True)
def application_answers_job(self, job_id, application_id, questions, provider='', model=''):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Drafting application answers')
    try:
        app=Application.objects.select_related('opportunity').get(pk=application_id)
        profile=Profile.objects.get_or_create(pk=1)[0]
        search_profile=build_search_profile()
        def text_values(rows, keys):
            out=[]
            for row in rows or []:
                if isinstance(row,dict):
                    value=next((row.get(k) for k in keys if row.get(k)), '')
                else:
                    value=row
                value=' '.join(str(value or '').split())
                if value: out.append(value)
            return out
        skills=text_values(search_profile.get('skills'),('term','skill','name'))[:80]
        roles=text_values(search_profile.get('role_families'),('role','name','family','term'))[:40]
        job.progress=18; job.message='Building job and candidate context'; job.save(update_fields=['progress','message'])
        cv_evidence='\n'.join(str(x.get('text') or '') for x in extract_active_cv_texts())[:12000]
        profile_context=f"""Candidate name: {profile.display_name}
Candidate phone/contact number: {profile.phone_number}
Operating locations: {profile.operating_locations or ([profile.operating_location] if profile.operating_location else [])}
High-priority background: {profile.high_priority_text}
Medium-priority background: {profile.medium_priority_text}
Low-priority / avoid guidance: {profile.low_priority_text}
Portfolio: {profile.portfolio_url}
Resume concepts/skills: {', '.join(skills)}
Likely role targets: {', '.join(roles)}
Active Resume evidence: {cv_evidence}"""
        prompt=f"""Prepare concise truthful draft answers for these application questions. Do not invent facts. If information is missing, explicitly mark it for human review.
Use both the job-specific evidence and the candidate application profile below. Do not answer from generic assumptions.
Role: {app.opportunity.title} at {app.opportunity.company}
Country / remote context: {app.opportunity.country} · {app.opportunity.remote_text}
Opportunity evidence: {app.opportunity.description[:7000]}
Application profile:
{profile_context[:7000]}
Questions:
{questions[:5000]}"""
        job.progress=42; job.message='Drafting answers with the selected AI route'; job.save(update_fields=['progress','message'])
        started=timezone.now()
        answer=generate(prompt,stage='question_answers',provider=provider or None,model=model or None,subject={'type':'outreach' if (app.opportunity.extracted_facts or {}).get('outreach') else 'application','id':app.pk,'label':f'{app.opportunity.company} — {app.opportunity.title}'})
        metric=UsageMetric.objects.filter(at__gte=started,stage='question_answers').order_by('-at').first()
        used_provider=(metric.provider if metric else (provider or 'automatic'))
        used_model=(metric.model if metric else (model or 'automatic'))
        job.progress=88; job.message='Saving answer history'; job.save(update_fields=['progress','message'])
        version=GeneratedTextVersion.objects.create(application=app,kind='ats',provider=used_provider,model=used_model,subject=questions[:500],body=answer,metadata={'questions':questions,'tokens_in':metric.tokens_in if metric else 0,'tokens_out':metric.tokens_out if metric else 0,'job_id':job.pk,'tool':'answers'})
        app.website_answers={'questions':questions,'draft':answer,'version_id':version.pk}; app.save(update_fields=['website_answers','updated_at'])
        _job_done(job,{'application_id':app.pk,'version_id':version.pk},'Application answers ready'); return {'application_id':app.pk,'version_id':version.pk}
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task(bind=True)
def application_compare_job(self, job_id, application_id, selections):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Comparing application email models')
    try:
        app=Application.objects.select_related('opportunity').get(pk=application_id)
        made=0; errors=[]
        for idx,item in enumerate((selections or [])[:4],1):
            try:
                provider,model=item.split('|',1); started=timezone.now(); subject,body=generate_email_version(app,provider,model)
                metric=UsageMetric.objects.filter(at__gte=started,provider=provider,model=model,stage='email_draft').order_by('-at').first()
                GeneratedTextVersion.objects.create(application=app,kind='email',provider=provider,model=model,subject=subject,body=body,metadata={'tokens_in':metric.tokens_in if metric else 0,'tokens_out':metric.tokens_out if metric else 0,'job_id':job.pk,'tool':'compare_model'})
                made+=1
            except Exception as exc:
                errors.append(f'{item}: {exc}')
            job.progress=min(95,10+int(80*idx/max(1,len(selections)))); job.message=f'Generated {idx}/{len(selections)} comparison(s)'; job.save(update_fields=['progress','message'])
        _job_done(job,{'application_id':app.pk,'generated':made,'errors':errors[:6]},f'{made} comparison output(s) ready'); return job.result
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task(bind=True)
def application_cv_job(self, job_id, application_id, document_kind='cv'):
    document_kind='cover' if document_kind=='cover' else 'cv'
    label='Cover Letter' if document_kind=='cover' else 'Resume'
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,f'Preparing tailored {label} files')
    try:
        app=Application.objects.select_related('opportunity','cv','cover_letter').get(pk=application_id)
        asset=app.cover_letter if document_kind=='cover' else app.cv
        if not asset: raise RuntimeError(f'Select a {label} before generating a tailored version.')
        def progress(value,message):
            job.progress=value; job.message=message; job.save(update_fields=['progress','message'])
        result=generate_application_artifacts(app,document_kind,progress=progress,job_id=job.pk)
        _job_done(job,{'application_id':app.pk,'result':result,'document_kind':document_kind},str(result.get('message') or f'Tailored {label} ready')); return job.result
    except Exception as exc:
        _job_fail(job,exc); raise



@shared_task(bind=True)
def application_imap_save_job(self, job_id, application_id):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Saving IMAP draft')
    try:
        app=Application.objects.select_related('opportunity','cv','cover_letter').get(pk=application_id)
        uid=save_draft(app)
        result={'application_id':app.pk,'uid':uid or '', 'folder':app.imap_draft_folder or ''}
        _job_done(job,result,'IMAP draft saved')
        return result
    except Exception as exc:
        _job_fail(job,exc); raise




_URL_CONTENT_WARNING_PREFIX='CONTENT_NOT_JOB:'

def _generic_200_content_warning(content_sample, url, page_title='', h1_text=''):
    """Soft-404 check for Lead/Address Book pages: prominent page-unavailability only."""
    # Arbitrary footer/body mentions of deleted pages must never poison a live company/contact page.
    top=' '.join(str(content_sample or '').split())[:1400]
    deterministic=page_unavailable_reason(str(page_title or '')+' '+str(h1_text or ''),top)
    if deterministic:
        return (_URL_CONTENT_WARNING_PREFIX+' HTTP 200 soft 404: '+deterministic+'. The source page appears unavailable.')
    return ''



def _role_presence_terms(value):
    text=' '.join(str(value or '').split()).casefold()
    words=[w for w in re.findall(r'[a-z0-9+#/.]+',text) if len(w)>=3]
    stop={'senior','junior','lead','principal','staff','the','and','with','for','remote','engineer','developer'}
    return [w for w in words if w not in stop][:8]


def _job_presence_text_sample(row, content_sample, url=''):
    """Return the evidence-dense text sent to the quick job-presence model.

    Some ATS/career pages expose the real role title followed by a very large theme/CSS or
    JSON shell. Small local models can treat that noise as page content and vote
    JOB_MISSING even though the URL and title are valid. Keep the role/company neighbourhood
    first, trim obvious theme/style blobs, and leave deterministic checks authoritative.
    """
    raw=' '.join(str(content_sample or '').replace('\xa0',' ').split())
    if not raw:
        return ''
    # Remove common career-site theme/style blobs that look like visible text after HTML-to-text.
    raw=re.sub(r'\{\s*"(?:themeOptions|customTheme|varTheme)"\s*:\s*\{[\s\S]{0,45000}$','',raw)
    raw=re.sub(r'"[a-z0-9-]*(?:color|background|border|radius|text)[a-z0-9-]*"\s*:\s*"[^"]{0,120}"',' ',raw,flags=re.I)
    raw=re.sub(r'\b(?:primary|accent|grey|green|button|tab|navbar|card|badge|facet|entity|highlight)-[a-z0-9-]+\s*:\s*#[0-9a-f]{3,8}\b',' ',raw,flags=re.I)
    raw=' '.join(raw.split())
    title=str(getattr(row,'title','') or '').strip()
    company=str(getattr(row,'company','') or '').strip()
    anchors=[]
    if title:
        anchors.append(title)
        anchors.append(re.split(r'\s+[|·-]\s+',title)[0].strip())
    if company:
        anchors.append(company)
    low=raw.casefold(); windows=[]
    for anchor in anchors:
        a=' '.join(str(anchor or '').split())
        if len(a)<4:
            continue
        pos=low.find(a.casefold())
        if pos>=0:
            start=max(0,pos-1800); end=min(len(raw),pos+5000)
            windows.append(raw[start:end])
    if windows:
        merged='\n\n'.join(dict.fromkeys(windows))
        tail=raw[:1800] if raw[:1800] not in merged else ''
        sample=(tail+'\n\n'+merged).strip()
    else:
        sample=raw
    return sample[:12000]


def _opportunity_has_strong_job_presence(row, content_sample, url=''):
    """Positive guard before AI soft-404 classification.

    Some modern job pages, especially Wellfound/AngelList, are long and contain footer/search
    chrome that can make a quick model vote false-negative. If the fetched page clearly shows
    the saved role with live JD structure/application copy, preserve HTTP 200 as healthy.
    """
    text=' '.join(str(content_sample or '').split())[:30000]
    if len(text)<120:
        return False
    low=text.casefold()
    title=str(getattr(row,'title','') or '').strip()
    company=str(getattr(row,'company','') or '').strip()
    terms=_role_presence_terms(title)
    role_hits=sum(1 for t in terms if t in low)
    title_core=' '.join(re.findall(r'[a-z0-9+#/.]+',title.casefold())[:6])
    title_present=bool(title_core and title_core in low) or (role_hits>=max(1,min(3,len(terms))))
    company_present=bool(company and company.casefold() in low)
    live_markers=(
        'apply now','about the job','the role','main responsibilities','responsibilities',
        'what we look for','what we look for in a candidate','requirements','compensation',
        'full time','posted:', 'posted ', 'recruiter recently active', 'actively hiring'
    )
    marker_hits=sum(1 for marker in live_markers if marker in low)
    try:
        parsed=urllib.parse.urlsplit(str(url or ''))
        host=(parsed.hostname or '').lower().removeprefix('www.')
        path=(parsed.path or '').lower()
    except Exception:
        host=''; path=''
    wellfound_job=host in {'wellfound.com','angel.co'} and '/jobs/' in path
    job_detail_url=bool(re.search(r'(?i)/(?:careers/)?job(?:s)?(?:/|\b)|/(?:careers|positions|posting|postings)/',path))
    first_chunk=low[:1800]
    title_early=bool(title and title.casefold() in first_chunk)
    if title_present and marker_hits>=2:
        return True
    if wellfound_job and title_present and (company_present or marker_hits>=1):
        return True
    # Modern ATS shells may expose only the role title and company before a large theme/CSS
    # blob. For a concrete job-detail URL, the exact early title plus company is stronger
    # evidence than a small model's guess over CSS noise.
    if job_detail_url and title_early and (company_present or role_hits>=2):
        return True
    return False

def _opportunity_200_content_warning(row, content_sample, url):
    """Return a user-facing warning when AI says a HTTP-200 page no longer contains this job.

    Routing deliberately follows Discovery Method: Local AI Discovery resolves the saved
    first-filter stage through Ollama; Cloud Web uses only its configured Cloud route. If no
    usable route exists or the quick check fails, HTTP reachability remains authoritative and
    no semantic warning is invented.
    """
    text=_job_presence_text_sample(row, content_sample, url)
    deterministic=soft_missing_reason(str(getattr(row,'title','') or ''), text)
    if deterministic:
        return (_URL_CONTENT_WARNING_PREFIX+' HTTP 200 soft 404: '+deterministic+'. The page no longer represents an active job posting.')
    if len(text)<120:
        return ''
    if _opportunity_has_strong_job_presence(row,text,url):
        return ''
    try:
        route=route_for_stage('first_filter')
    except Exception:
        route={}
    if not route or not route.get('provider') or not route.get('model'):
        return ''
    prompt=(
        'Quick job-presence check. Determine whether the fetched webpage still contains the specific job/opportunity below. '
        'A generic careers/search page, expired/removed-job notice, error shell, unrelated role, sign-in wall with no role evidence, '
        'or page saying the job no longer exists means JOB_MISSING. Clear role details, responsibilities, application details, or an '
        'explicit active listing for this role means JOB_PRESENT. Answer exactly JOB_PRESENT or JOB_MISSING and nothing else.\n\n'
        f'Role: {str(getattr(row,"title","") or "")[:300]}\nCompany: {str(getattr(row,"company","") or "")[:200]}\nURL: {url}\n\nPage text:\n{text}'
    )
    try:
        with scoped_usage_context(operation='ad_hoc',subject_type='url_health',subject_id=str(row.pk)):
            answer=generate_with_route(route,prompt,stage='first_filter',timeout=45,limits_override={'max_input_tokens':3200,'max_output_tokens':32})
        normalized=' '.join(str(answer or '').upper().split())
        if 'JOB_MISSING' in normalized and 'JOB_PRESENT' not in normalized:
            return (_URL_CONTENT_WARNING_PREFIX+' HTTP 200, but the AI content check could not find this job listing on the returned page. '
                    'The portal may be serving a generic, expired, removed, or unrelated page while still returning HTTP 200.')
    except Exception:
        pass
    return ''

@shared_task(bind=True)
def url_health_refresh_job(self, kind, record_id):
    """Refresh one passive external-URL health badge without blocking a list view."""
    if kind=='opportunity':
        model=Opportunity
    elif kind=='hidden_lead':
        model=CompanyLead
    elif kind=='contact':
        model=Contact
    else:
        return {'ok':False,'error':'unknown record kind'}
    lock_key=f'scoutbox:url-health:{kind}:{record_id}'
    row=model.objects.filter(pk=record_id).first()
    if not row:
        cache.delete(lock_key); return {'ok':False,'error':'record not found'}
    # Health badges are for active/recent inventory. Once an item is 3 months old, keep
    # the last-known status but stop making recurring external requests for it.
    age_at=(row.created_at if kind in {'contact','hidden_lead'} else row.first_seen_by_portal)
    if age_at and age_at < timezone.now()-timedelta(days=90):
        cache.delete(lock_key); return {'ok':False,'skipped':'older than 3 months'}
    if kind=='contact':
        # Address Book health represents the displayed source link when available.
        # Fall back to the email domain only for legacy/manual contacts without source_url.
        url=str(getattr(row,'source_url','') or '').strip()
        if not url:
            email=str(getattr(row,'email','') or '').strip().lower()
            domain=email.split('@',1)[1] if '@' in email else ''
            url=('https://'+domain) if domain else ''
    else:
        url=(getattr(row,'target_url','') or getattr(row,'url','') or getattr(row,'source_url','') or '').strip()
    if not url:
        cache.delete(lock_key); return {'ok':False,'error':'no target URL'}
    try:
        result=probe_url_health(url,timeout=15,capture_text=True)
        status=int(result.get('http_status')) if result.get('http_status') is not None else None
        error=str(result.get('error') or '')[:500]
        if status==200 and not error:
            # Opportunity health is role-aware. Leads/Address Book URLs are often company,
            # project or contact pages, so their soft-404 test is deliberately page-only.
            if kind=='opportunity':
                error=_opportunity_200_content_warning(row,result.get('content_sample') or '',result.get('target_url') or url)[:500]
            else:
                error=_generic_200_content_warning(result.get('content_sample') or '',result.get('target_url') or url,result.get('page_title') or '',result.get('h1_text') or '')[:500]
        now=timezone.now()
        old_status=(getattr(row,'domain_http_status',None) if kind=='contact' else getattr(row,'target_http_status',None))
        old_checked=(getattr(row,'domain_checked_at',None) if kind=='contact' else getattr(row,'target_checked_at',None))
        old_bytes=(getattr(row,'domain_response_bytes',0) if kind=='contact' else getattr(row,'target_response_bytes',0))
        observed_bytes=max(0,int(result.get('response_bytes') or 0))
        # 403/429 are frequently transient anti-bot/rate-limit responses. Once a URL has
        # succeeded, retain the last-good visible status while recording the latest recheck.
        retained_transient=bool(status in (403,429) and old_status is not None and 200 <= int(old_status) < 400)
        if retained_transient:
            stamp=timezone.localtime(old_checked).strftime('%d/%m/%Y %H:%M:%S') if old_checked else 'an earlier check'
            error=(f'Latest recheck returned HTTP {status}; retaining last successful HTTP {old_status} from {stamp}.')[:500]
            displayed_status=int(old_status)
        else:
            displayed_status=status
        if kind=='contact':
            row.domain_http_status=displayed_status; row.domain_checked_at=now; row.domain_check_error=error
            if status is not None and 200 <= int(status) < 400 and observed_bytes: row.domain_response_bytes=observed_bytes
            row.save(update_fields=['domain_http_status','domain_checked_at','domain_check_error','domain_response_bytes'])
        else:
            row.target_http_status=displayed_status; row.target_checked_at=now; row.target_check_error=error
            if status is not None and 200 <= int(status) < 400 and observed_bytes: row.target_response_bytes=observed_bytes
            row.save(update_fields=['target_http_status','target_checked_at','target_check_error','target_response_bytes','updated_at'])
        return {'ok':bool(result.get('ok')),'status':displayed_status,'observed_status':status,'retained_transient':retained_transient,'url':result.get('target_url') or url,'error':error,'response_bytes':(old_bytes if retained_transient else observed_bytes)}
    finally:
        cache.delete(lock_key)


@shared_task(bind=True)
def candidate_profile_defaults_job(self, job_id, profile_terms_version='0.11.128'):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Rebuilding Resume concepts and likely roles')
    try:
        from portal.services.queryplanner import (
            extract_active_cv_texts, grounded_resume_concepts, grounded_resume_roles, _profile_concept_supported,
            PROFILE_CONCEPT_LIMIT, PROFILE_ROLE_LIMIT,
        )
        docs=extract_active_cv_texts()
        if not docs:
            raise RuntimeError('No readable active Resume is available. Upload a Resume before rebuilding Candidate Profile defaults.')
        # The AI expands role/domain vocabulary, while deterministic Resume-only extraction
        # guarantees that concrete technologies in the source documents cannot disappear.
        # Preference text is intentionally absent from this payload.
        payload=[{'id':d.get('id'),'label':d.get('label'),'text':(d.get('text') or '')} for d in docs[:8]]
        prompt=(
            'Build a profession-neutral ScoutBox Candidate Profile from the supplied Resume text. '
            f'Return JSON only with keys concepts and likely_roles. concepts may contain up to {PROFILE_CONCEPT_LIMIT} concise, searchable technical skills, technologies, protocols, platforms, frameworks, tools, methods, engineering domains, certifications or specialist subjects that are directly evidenced in the Resume. '
            'Do not put job-search preferences, interview preferences, compensation, company-size preferences, negative constraints, generic prose, personality traits, or phrases such as things to avoid into concepts. Prefer literal technology/product/protocol names and concrete engineering domains over vague summaries. '
            f'likely_roles may contain up to {PROFILE_ROLE_LIMIT} plausible job/engagement role titles supported by the Resume. '
            'Do not invent experience and do not assume any profession unless the Resume supports it.\n\n'+json.dumps(payload,ensure_ascii=False)
        )
        parsed={}
        try:
            # This rebuild is specifically intended to recover nuance from the complete Resume
            # corpus. Do not apply the ordinary compact first-filter input cap here. If the
            # selected route cannot accept the full corpus, deterministic extraction below still
            # preserves literal Resume technologies instead of silently using a truncated prompt.
            route=dict(effective_route_for_stage('first_filter') or {})
            raw=generate_with_route(
                route,prompt,stage='first_filter',timeout=120,
                subject={'type':'profile','id':'1','label':'Candidate Profile defaults'},
                limits_override={'max_input_tokens':0,'max_output_tokens':8000},
            ).strip()
            raw=re.sub(r'^```(?:json)?\s*|\s*```$','',raw,flags=re.I|re.S).strip()
            val=json.loads(raw)
            if isinstance(val,dict): parsed=val
        except Exception:
            parsed={}
        corpus='\n'.join(d.get('text') or '' for d in docs)
        concepts=[]; seen=set()

        # Start with deterministic Resume-only terms so literal technologies such as
        # BACnet/Modbus survive even when a model chooses a more abstract summary.
        for term in grounded_resume_concepts([d.get('text') or '' for d in docs],PROFILE_CONCEPT_LIMIT):
            key=term.casefold()
            if key not in seen:
                seen.add(key); concepts.append(term)

        # AI concepts supplement the deterministic set, but must be substantially grounded
        # in Resume text. This rejects preference leakage caused by one coincidental token.
        for value in parsed.get('concepts') or []:
            term=' '.join(str(value or '').split()).strip()[:120]
            if not term: continue
            if not _profile_concept_supported(term,corpus): continue
            key=term.casefold()
            if key not in seen: seen.add(key); concepts.append(term.lower())
            if len(concepts)>=PROFILE_CONCEPT_LIMIT: break
        if not concepts:
            concepts=grounded_resume_concepts([d.get('text') or '' for d in docs],PROFILE_CONCEPT_LIMIT)

        # Deterministic role families are also retained; the AI can add more specific titles.
        roles=[]; seen_roles=set()
        for value in grounded_resume_roles([d.get('text') or '' for d in docs],PROFILE_ROLE_LIMIT):
            role=' '.join(str(value or '').split()).strip().lower()[:120]
            if role and role not in seen_roles:
                seen_roles.add(role); roles.append(role)
            if len(roles)>=PROFILE_ROLE_LIMIT: break
        for value in parsed.get('likely_roles') or []:
            role=' '.join(str(value or '').split()).strip().lower()[:120]
            if role and role not in seen_roles:
                seen_roles.add(role); roles.append(role)
            if len(roles)>=PROFILE_ROLE_LIMIT: break
        profile=Profile.objects.get_or_create(pk=1)[0]
        scope=dict(profile.scope_json or {})
        scope['cv_concepts']=concepts[:PROFILE_CONCEPT_LIMIT]; scope['likely_roles']=roles[:PROFILE_ROLE_LIMIT]
        scope['profile_extraction_status']='ready' if (concepts or roles) else 'needs_review'
        scope['profile_terms_version']=str(profile_terms_version or '0.11.128')[:32]
        scope['profile_terms_regenerated_at']=timezone.now().isoformat()
        if not scope.get('preferred_languages'): scope['preferred_languages']=['english']
        profile.scope_json=scope; profile.save(update_fields=['scope_json','updated_at'])
        result={'cv_concepts':scope['cv_concepts'],'likely_roles':scope['likely_roles'],'preferred_languages':scope['preferred_languages'],'profile_extraction_status':scope['profile_extraction_status'],'profile_terms_version':scope['profile_terms_version'],'concept_count':len(scope['cv_concepts']),'role_count':len(scope['likely_roles'])}
        _job_done(job,result,'Candidate Profile defaults rebuilt' if (concepts or roles) else 'Candidate Profile needs review')
        return result
    except Exception as exc:
        _job_fail(job,exc); raise

def _profile_autopopulate_key(value):
    """Return a stable case-insensitive key for Candidate Profile de-duplication."""
    text=' '.join(str(value or '').split()).strip().casefold()
    text=re.sub(r'\s*([/+])\s*',r'\1',text)
    text=re.sub(r'[^a-z0-9+#./-]+',' ',text)
    return ' '.join(text.split()).strip(' .,:;-')


def _profile_round_robin_unique(groups, limit):
    """Merge per-Resume terms fairly while de-duplicating and respecting a hard limit.

    A long Resume must not consume the whole Candidate Profile before shorter Resumes have
    a chance to contribute. Terms are therefore taken round-robin from each Resume's
    ordered evidence list. Case/spacing/punctuation-equivalent duplicates are ignored.
    """
    cleaned=[]
    for group in groups or []:
        row=[]; local_seen=set()
        for raw in group or []:
            value=' '.join(str(raw or '').split()).strip()[:120]
            key=_profile_autopopulate_key(value)
            if not value or not key or key in local_seen:
                continue
            local_seen.add(key); row.append(value)
        if row:
            cleaned.append(row)
    out=[]; seen=set(); indexes=[0 for _ in cleaned]
    hard_limit=max(1,int(limit or 1))
    while cleaned and len(out)<hard_limit:
        advanced=False
        for idx,group in enumerate(cleaned):
            while indexes[idx] < len(group):
                value=group[indexes[idx]]; indexes[idx]+=1
                key=_profile_autopopulate_key(value)
                if key in seen:
                    continue
                seen.add(key); out.append(value); advanced=True
                break
            if len(out)>=hard_limit:
                break
        if not advanced:
            break
    return out


@shared_task(bind=True)
def candidate_profile_autopopulate_job(self, job_id):
    """Rebuild Resume concepts/likely roles from every current uploaded Resume.

    Each Resume is analysed independently, then merged round-robin so one long Resume
    cannot crowd out the rest. The task writes Candidate Profile terms only after every
    Resume has been processed, so a Dashboard stop leaves the existing profile unchanged.
    """
    job=BackgroundJob.objects.get(pk=job_id)
    if job.status=='stopped':
        return {'stopped':True,'processed_resumes':0,'total_resumes':0,'profile_committed':False}
    job.celery_task_id=self.request.id or ''
    _job_start(job,'Reading all uploaded Resumes')
    try:
        from portal.services.queryplanner import (
            extract_active_cv_texts, grounded_resume_concepts, grounded_resume_roles,
            _profile_concept_supported, PROFILE_CONCEPT_LIMIT, PROFILE_ROLE_LIMIT,
        )
        uploaded=list(DocumentAsset.objects.filter(kind='cv',active=True).order_by('id').values('id','label','original_name'))
        docs=extract_active_cv_texts()
        if not docs:
            raise RuntimeError('No readable Resume is available. Upload a readable DOCX or PDF Resume before autopopulating Candidate Profile.')
        total=len(docs)
        uploaded_total=len(uploaded)
        readable_ids={int(d.get('id')) for d in docs if d.get('id') is not None}
        unreadable=[str(x.get('label') or x.get('original_name') or f"Resume {x.get('id')}")[:180] for x in uploaded if int(x.get('id')) not in readable_ids]
        route=dict(effective_route_for_stage('first_filter') or {})
        concept_groups=[]; role_groups=[]; per_resume=[]; ai_ok=0; ai_failed=0

        for index,doc in enumerate(docs,1):
            job.refresh_from_db(fields=['status'])
            if job.status=='stopped':
                return {'stopped':True,'processed_resumes':index-1,'total_resumes':total}

            label=str(doc.get('label') or doc.get('name') or f'Resume {index}')[:180]
            text=str(doc.get('text') or '')
            start_progress=5+int(((index-1)/max(1,total))*82)
            job.progress=min(87,max(5,start_progress))
            job.message=f'Analysing Resume {index} of {total}: {label}'[:500]
            job.result={
                'tool':'candidate_profile_autopopulate','phase':'analysing_resumes',
                'processed_resumes':index-1,'total_resumes':uploaded_total,'readable_resumes':total,'unreadable_resumes':len(unreadable),
                'current_resume_id':doc.get('id'),'current_resume_label':label,
                'concept_limit':PROFILE_CONCEPT_LIMIT,'role_limit':PROFILE_ROLE_LIMIT,
            }
            job.save(update_fields=['progress','message','result'])

            deterministic_concepts=grounded_resume_concepts([text],PROFILE_CONCEPT_LIMIT)
            deterministic_roles=grounded_resume_roles([text],PROFILE_ROLE_LIMIT)
            ai_concepts=[]; ai_roles=[]; ai_error=''
            prompt=(
                'Extract a Candidate Profile vocabulary from this single Resume only. '
                'Return JSON only with keys concepts and likely_roles. '
                f'concepts may contain up to {PROFILE_CONCEPT_LIMIT} concise searchable technologies, protocols, platforms, frameworks, tools, languages, engineering methods, certifications, specialist subjects or technical domains directly evidenced by this Resume. '
                'Prefer literal technology/product/protocol names and concrete technical terms. '
                'Do not include job-search preferences, compensation, company-size preferences, interview preferences, negative constraints, generic personality traits, or long prose. '
                f'likely_roles may contain up to {PROFILE_ROLE_LIMIT} concise plausible role titles supported by this Resume. '
                'Do not invent experience. Keep concepts and roles independent: technology/domain terms belong in concepts; job titles belong in likely_roles.\n\n'
                f'Resume label: {label}\nResume text:\n{text}'
            )
            try:
                raw=generate_with_route(
                    route,prompt,stage='first_filter',timeout=120,
                    subject={'type':'profile','id':str(doc.get('id') or index),'label':f'Candidate Profile autopopulate: {label}'},
                    limits_override={'max_input_tokens':0,'max_output_tokens':8000},
                ).strip()
                raw=re.sub(r'^```(?:json)?\s*|\s*```$','',raw,flags=re.I|re.S).strip()
                parsed=json.loads(raw)
                if isinstance(parsed,dict):
                    for value in parsed.get('concepts') or []:
                        term=' '.join(str(value or '').split()).strip()[:120]
                        if term and _profile_concept_supported(term,text):
                            ai_concepts.append(term.lower())
                    for value in parsed.get('likely_roles') or []:
                        role=' '.join(str(value or '').split()).strip().lower()[:120]
                        if role:
                            ai_roles.append(role)
                ai_ok+=1
            except Exception:
                ai_failed+=1; ai_error='AI extraction unavailable; deterministic Resume evidence used.'

            # Deterministic Resume-only evidence leads each per-Resume list. AI adds
            # specific titles/terms the fixed graph does not know about.
            concepts=_profile_round_robin_unique([deterministic_concepts,ai_concepts],PROFILE_CONCEPT_LIMIT)
            roles=_profile_round_robin_unique([deterministic_roles,ai_roles],PROFILE_ROLE_LIMIT)
            concept_groups.append(concepts); role_groups.append(roles)
            per_resume.append({
                'id':doc.get('id'),'label':label,'concept_count':len(concepts),
                'role_count':len(roles),'ai_extraction':'ok' if not ai_error else 'fallback',
                'ai_error':ai_error,
            })

            job.refresh_from_db(fields=['status'])
            if job.status=='stopped':
                return {'stopped':True,'processed_resumes':index,'total_resumes':total}
            job.progress=min(90,5+int((index/max(1,total))*85))
            job.message=f'Processed {index} of {total} Resumes'[:500]
            job.result={
                'tool':'candidate_profile_autopopulate','phase':'analysing_resumes',
                'processed_resumes':index,'total_resumes':uploaded_total,'readable_resumes':total,'unreadable_resumes':len(unreadable),
                'concept_limit':PROFILE_CONCEPT_LIMIT,'role_limit':PROFILE_ROLE_LIMIT,
                'ai_succeeded':ai_ok,'ai_fallbacks':ai_failed,
            }
            job.save(update_fields=['progress','message','result'])

        job.refresh_from_db(fields=['status'])
        if job.status=='stopped':
            return {'stopped':True,'processed_resumes':total,'total_resumes':total}
        job.progress=93; job.message='Merging Resume evidence and removing duplicates'
        job.save(update_fields=['progress','message'])

        concepts=_profile_round_robin_unique(concept_groups,PROFILE_CONCEPT_LIMIT)
        roles=_profile_round_robin_unique(role_groups,PROFILE_ROLE_LIMIT)
        result={
            'tool':'candidate_profile_autopopulate','phase':'completed',
            'total_resumes':uploaded_total,'readable_resumes':total,'unreadable_resumes':len(unreadable),'processed_resumes':total,
            'concept_count':len(concepts),'role_count':len(roles),
            'concept_limit':PROFILE_CONCEPT_LIMIT,'role_limit':PROFILE_ROLE_LIMIT,
            'duplicates_removed':True,'merge_strategy':'round_robin_per_resume',
            'ai_succeeded':ai_ok,'ai_fallbacks':ai_failed,'resumes':per_resume,
            'profile_committed':True,
        }
        if unreadable:
            result['unreadable_resume_labels']=unreadable[:20]
        # Commit the profile update and the job's committed marker in one transaction. If a
        # worker is terminated before this transaction commits, both changes roll back; if
        # the user stops immediately after commit, the UI can accurately report that the
        # new vocabulary had already been saved.
        with transaction.atomic():
            locked_job=BackgroundJob.objects.select_for_update().get(pk=job.pk)
            if locked_job.status=='stopped':
                return {'stopped':True,'processed_resumes':total,'total_resumes':total,'profile_committed':False}
            profile=Profile.objects.get_or_create(pk=1)[0]
            scope=dict(profile.scope_json or {})
            scope['cv_concepts']=concepts[:PROFILE_CONCEPT_LIMIT]
            scope['likely_roles']=roles[:PROFILE_ROLE_LIMIT]
            scope['profile_extraction_status']='ready' if (concepts or roles) else 'needs_review'
            # Keep the 0.11.128 one-time upgrade marker satisfied while recording the newer
            # manual all-Resume aggregation algorithm separately.
            scope['profile_terms_version']='0.11.128'
            scope['profile_terms_regenerated_at']=timezone.now().isoformat()
            scope['profile_autopopulate_version']='0.11.129'
            scope['profile_autopopulated_at']=timezone.now().isoformat()
            scope['profile_autopopulate_resume_count']=total
            if not scope.get('preferred_languages'):
                scope['preferred_languages']=['english']
            profile.scope_json=scope
            profile.save(update_fields=['scope_json','updated_at'])
            locked_job.progress=98
            locked_job.message='Candidate Profile updated; finalizing'
            locked_job.result=result
            locked_job.save(update_fields=['progress','message','result'])
            job=locked_job

        suffix='' if total==1 else 's'
        skipped=f' · {len(unreadable)} unreadable skipped' if unreadable else ''
        _job_done(job,result,f'Candidate Profile autopopulated from {total} readable Resume{suffix}: {len(concepts)} concepts · {len(roles)} roles{skipped}')
        return result
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task(bind=True)
def campaign_templates_job(self, job_id, prompt=''):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Generating role-specific campaign templates')
    try:
        job.progress=15; job.save(update_fields=['progress'])
        result=generate_profile_campaign_templates(prompt)
        _job_done(job,result,f"Generated {result.get('created',0)} campaign template(s)")
        return result
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task(bind=True)
def resume_campaign_template_job(self, job_id, asset_id, resume_concepts=None, likely_roles=None, prompt=''):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Creating campaign from selected Resume')
    try:
        job.progress=15; job.save(update_fields=['progress'])
        result=generate_resume_campaign_template(asset_id,resume_concepts or [],likely_roles or [],prompt)
        _job_done(job,result,f"Created campaign template: {result.get('name','Campaign')}")
        return result
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task(bind=True)
def all_resume_campaign_templates_job(self, job_id, prompt=''):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Generating Campaign Templates from all Resumes')
    try:
        job.progress=10; job.save(update_fields=['progress'])
        result=generate_all_resume_campaign_templates(prompt)
        message=f"Generated/regenerated {result.get('succeeded',0)} Campaign Template(s)"
        _job_done(job,result,message)
        return result
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task(bind=True)
def translate_opportunity_job(self, job_id, opportunity_id, field='description'):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Translating to English')
    try:
        opp=Opportunity.objects.get(pk=opportunity_id)
        if field=='company_info': source='\n'.join(f"{x.get('label','')}: {x.get('value','')}" for x in (opp.company_intel or {}).get('facts',[]))
        else: source=opp.description or opp.raw_search_snippet
        if not source.strip(): raise RuntimeError('No source text is available to translate.')
        prompt='Translate the following content to natural English. Preserve meaning, headings and lists. Do not add facts.\n\n'+source[:18000]
        translated=generate(prompt,stage='page_summary',timeout=120,subject={'type':'opportunity','id':opp.pk,'label':f'{opp.company} — {opp.title}'}).strip()
        facts=opp.extracted_facts or {}; trans=facts.get('translation') or {}; trans[field]={'text':translated,'at':timezone.now().isoformat()}; facts['translation']=trans; opp.extracted_facts=facts; opp.save(update_fields=['extracted_facts','updated_at'])
        _job_done(job,{'opportunity_id':opp.pk,'field':field},'English translation ready'); return {'translated':True}
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task(bind=True)
def company_research_job(self, job_id, opportunity_id, phase='manual'):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Researching company from public sources')
    opp=None
    try:
        opp=Opportunity.objects.get(pk=opportunity_id)
        with scoped_usage_context(campaign_id=_usage_ids_for_entity(opp)[0], campaign_run_id=_usage_ids_for_entity(opp)[1], operation=budget_operation_for_phase(phase), subject_type='opportunity', subject_id=str(opp.pk)):
            result=research_company(opp)
        complete_attempt(opp,'company',phase,'success')
        _job_done(job,result,'Company research updated'); return result
    except CloudLimitReached as exc:
        if opp: complete_attempt(opp,'company',phase,'skipped_budget',str(exc))
        result={'opportunity_id':opportunity_id,'state':'limit_reached','detail':str(exc)}; _job_done(job,result,'Not executed — Cloud AI limit reached'); return result
    except Exception as exc:
        if opp: complete_attempt(opp,'company',phase,'failed',str(exc))
        _job_fail(job,exc); raise


@shared_task(bind=True)
def lead_company_research_job(self, job_id, lead_id, phase='manual'):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Researching Hidden Lead company from public sources')
    lead=None
    try:
        lead=CompanyLead.objects.get(pk=lead_id,user_deleted=False)
        with scoped_usage_context(campaign_id=_usage_ids_for_entity(lead)[0], campaign_run_id=_usage_ids_for_entity(lead)[1], operation=budget_operation_for_phase(phase), subject_type='hidden_lead', subject_id=str(lead.pk)):
            result=research_company(lead)
        lead.refresh_from_db(fields=['company_intel','summary'])
        if market_summary_needs_refresh(lead.summary):
            specific=company_summary_from_intel(lead.company_intel or {},1200)
            if specific:
                lead.summary=specific[:1600]
                lead.save(update_fields=['summary','updated_at'])
        complete_attempt(lead,'company',phase,'success')
        _job_done(job,result,'Hidden Lead company research updated'); return result
    except CloudLimitReached as exc:
        if lead: complete_attempt(lead,'company',phase,'skipped_budget',str(exc))
        result={'lead_id':lead_id,'state':'limit_reached','detail':str(exc)}; _job_done(job,result,'Not executed — Cloud AI limit reached'); return result
    except Exception as exc:
        if lead: complete_attempt(lead,'company',phase,'failed',str(exc))
        _job_fail(job,exc); raise


def _parse_aware_datetime(value):
    if not value:
        return None
    try:
        parsed=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    except Exception:
        return None
    if timezone.is_naive(parsed):
        parsed=timezone.make_aware(parsed,timezone.get_current_timezone())
    return parsed


def _campaign_run_is_live_local(run, now=None):
    """Return True only while a Local Discovery run can actually be consuming resources.

    Queued runs are deliberately not blockers: they are not yet using Ollama/search capacity
    and historically one orphaned queued row could starve Address Book enrichment for hours.
    Running rows must also have a fresh heartbeat. Stopping rows only block during the short
    cooperative cancellation grace period.
    """
    now=now or timezone.now()
    mode=str(((run.criteria or {}).get('discovery_mode') or '')).strip().lower()
    if mode and mode!='source_guided':
        return False
    if run.status=='running':
        fail_minutes=max(5,int(os.environ.get('SCOUTBOX_CAMPAIGN_STALL_FAIL_MINUTES','20') or 20))
        last=run.heartbeat_at or run.started_at or run.created_at
        return bool(last and now-last < timedelta(minutes=fail_minutes))
    if run.status=='stopping':
        result=run.result if isinstance(run.result,dict) else {}
        requested=_parse_aware_datetime(result.get('stop_requested_at')) or run.started_at or run.created_at
        grace=3
        return bool(requested and now-requested < timedelta(minutes=grace))
    return False


def _blocking_local_discovery_run(now=None):
    now=now or timezone.now()
    rows=CampaignRun.objects.select_related('campaign').filter(status__in=['running','stopping']).order_by('-heartbeat_at','-started_at','-created_at')[:20]
    return next((run for run in rows if _campaign_run_is_live_local(run,now)),None)


def _clear_local_wait_state(job):
    result=dict(job.result or {})
    keys=('wait_reason','wait_started_at','last_wait_at','next_retry_at','waited_seconds','retry_count',
          'blocking_campaign_run_id','blocking_campaign_id','blocking_campaign_name','blocking_campaign_stage')
    changed=False
    for key in keys:
        if key in result:
            result.pop(key,None); changed=True
    if changed:
        job.result=result
        job.save(update_fields=['result'])


def _defer_job_for_local_discovery(task, job, blocker, countdown=300):
    """Queue a background research job behind a genuinely running Local Discovery run.

    Waiting is bounded so a continuously busy installation cannot leave a permanent queued
    hourglass. The original job creation time is used as the fallback wait start, which also
    bounds jobs that were already stuck before this release was installed.
    """
    now=timezone.now(); result=dict(job.result or {})
    wait_started=_parse_aware_datetime(result.get('wait_started_at')) or (job.created_at if job.started_at is None else now) or now
    waited=max(0,int((now-wait_started).total_seconds()))
    max_wait=max(15,min(480,int(os.environ.get('SCOUTBOX_LOCAL_BACKGROUND_WAIT_MAX_MINUTES','120') or 120)))
    retries=int(getattr(task.request,'retries',0) or 0)
    max_retries=int(getattr(task,'max_retries',96) or 96)
    stage=str(blocker.stage or blocker.message or 'Local Discovery')[:120]
    campaign_name=str(getattr(blocker.campaign,'name','') or f'Campaign {blocker.campaign_id}')[:200]
    result.update({
        'wait_reason':'local_discovery_active','wait_started_at':wait_started.isoformat(),'last_wait_at':now.isoformat(),
        'waited_seconds':waited,'retry_count':retries,'blocking_campaign_run_id':blocker.pk,
        'blocking_campaign_id':blocker.campaign_id,'blocking_campaign_name':campaign_name,'blocking_campaign_stage':stage,
    })
    if waited >= max_wait*60 or retries >= max_retries:
        detail=f'Expired after waiting {max(1,waited//60)} minutes for Local Discovery ({campaign_name} · {stage}) to become idle.'
        result.update({'state':'expired_waiting_for_local_discovery','expired_at':now.isoformat(),'wait_limit_minutes':max_wait})
        job.status='failed'; job.finished_at=now; job.progress=100; job.message='Expired waiting for Local Discovery'; job.error=detail; job.result=result
        job.save(update_fields=['status','finished_at','progress','message','error','result','celery_task_id'])
        return {'expired':True,'state':'expired_waiting_for_local_discovery','detail':detail}
    next_retry=now+timedelta(seconds=countdown)
    result['next_retry_at']=next_retry.isoformat()
    job.status='queued'; job.message=f'Waiting for Local Discovery · {campaign_name} · {stage}'[:500]; job.result=result
    job.save(update_fields=['status','message','result','celery_task_id'])
    raise task.retry(countdown=countdown)


@shared_task(bind=True, max_retries=96)
def contact_company_research_job(self, job_id, contact_id, phase='initial'):
    """Research one Address Book company without blocking mailbox parsing.

    A queued contact can legitimately disappear meanwhile (delete, recycle-bin purge,
    deduplication); that is a stale job, not an AI failure. Local model generation is
    coordinated per-call by the shared Ollama lane guard rather than by blocking the
    whole job behind a running campaign.
    """
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''
    contact=Contact.objects.filter(pk=contact_id,deleted_at__isnull=True).first()
    if contact is None:
        result={'contact_id':contact_id,'state':'stale_contact','skipped':True}
        _job_done(job,result,'Skipped — Address Book contact no longer exists')
        return result
    # Do not queue Company Enrichment behind an entire Local Discovery campaign. The
    # shared Ollama lane guard in services.ai already arbitrates the short generation
    # calls; waiting for whole campaigns caused persistent Company Enrichment stalls
    # whenever campaign discovery was healthy and continuous.
    _clear_local_wait_state(job)
    _job_start(job,'Researching Address Book company from public sources')
    try:
        # Reuse stronger originating research before spending any network/AI budget.
        summary,intel=stored_company_context(contact.company,contact.email,contact.source_url)
        changed=[]
        if intel and not company_info_has_display_data(contact): contact.company_intel=intel; changed.append('company_intel')
        if summary and not str(contact.company_summary or '').strip(): contact.company_summary=summary[:2000]; changed.append('company_summary')
        if changed: contact.save(update_fields=changed)
        enrich_company_intel_from_retained(contact)
        if not company_info_has_display_data(contact):
            result=research_company(contact)
        else:
            result=contact.company_intel or {}
        if not str(contact.company_summary or '').strip():
            summary=company_summary_from_intel(result,1200)
            if summary: contact.company_summary=summary; contact.save(update_fields=['company_summary'])
        try:
            intel_now=dict(contact.company_intel or {}); fit=intel_now.get('fit_classification') if isinstance(intel_now.get('fit_classification'),dict) else {}
            if not ('score' in fit and fit.get('score') not in (None,'')):
                assessed,_review=assess_addressbook_contact_fit(contact)
                if assessed: contact.save(update_fields=['company_intel'])
        except Exception:
            pass
        _job_done(job,{'contact_id':contact.pk,'company_info':result},'Address Book company information updated')
        return result
    except CloudLimitReached as exc:
        _job_done(job,{'contact_id':contact_id,'state':'limit_reached','detail':str(exc)},'Deferred — Cloud AI limit reached')
        return {'state':'limit_reached'}
    except Exception as exc:
        _job_fail(job,exc); raise


def _complete_release_backfill_without_local_wait(job, ps, counts=None, blocker=None, reason='Local Discovery is active'):
    """Finalize the legacy release backfill instead of leaving a dashboard-blocking waiter.

    The 0.10.41 repair is best-effort historical cleanup. It must never keep an
    installation in a permanent startup/backfill state while Local Discovery is busy or
    while an old Celery retry has been orphaned. Network-heavy cleanup can be skipped;
    the completion marker is authoritative so seed_defaults will not requeue it.
    """
    now=timezone.now()
    result=dict(job.result or {})
    if isinstance(counts,dict):
        result.update(counts)
    result.update({
        'release':'0.10.41',
        'state':'completed_without_waiting_for_local_discovery',
        'network_heavy_repair_skipped':True,
        'reason':str(reason or 'Local Discovery is active')[:500],
        'completed_at':now.isoformat(),
        'fixed_by_release':'0.10.51',
    })
    if blocker is not None:
        stage=str(getattr(blocker,'stage','') or getattr(blocker,'message','') or 'Local Discovery')[:120]
        campaign_name=str(getattr(getattr(blocker,'campaign',None),'name','') or f'Campaign {getattr(blocker,"campaign_id","")}')[:200]
        result.update({
            'blocking_campaign_run_id':getattr(blocker,'pk',None),
            'blocking_campaign_id':getattr(blocker,'campaign_id',None),
            'blocking_campaign_name':campaign_name,
            'blocking_campaign_stage':stage,
        })
    ps.release_backfill_version='0.10.41'
    ps.save(update_fields=['release_backfill_version','updated_at'])
    _job_done(job,result,'0.10.41 backfill finalized without waiting for Local Discovery')
    return result


@shared_task(bind=True, max_retries=96)
def release_company_context_backfill_job(self, job_id):
    """One-time 0.10.41 upgrade repair for retained discovery records and source quality.

    The task is deliberately idle-aware. In Local Discovery mode it never runs Company
    Research while a campaign is active, so the upgrade cannot steal GPU/search capacity
    from a running discovery campaign.
    """
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    _clear_local_wait_state(job)
    _job_start(job,'Checking release backfill prerequisites')
    counts={'opportunities':0,'hidden_leads':0,'contacts':0,'reused':0,'failed':0,'contact_fit_backfilled':0,'legacy_soft404_cleared':0,'contacts_recycled_quality':0,'contacts_review_quality':0,'url_health_requeued':0,'network_research_skipped_due_to_local_discovery':0}
    blocker=_blocking_local_discovery_run() if ps.discovery_mode=='source_guided' else None
    # Clear legacy Opportunity-specific job-presence warnings from company/contact URLs.
    try:
        lead_qs=CompanyLead.objects.filter(target_check_error__startswith=_URL_CONTENT_WARNING_PREFIX)
        contact_qs=Contact.objects.filter(domain_check_error__startswith=_URL_CONTENT_WARNING_PREFIX)
        counts['legacy_soft404_cleared']=lead_qs.count()+contact_qs.count()
        lead_qs.update(target_check_error='')
        contact_qs.update(domain_check_error='')
    except Exception:
        counts['failed']+=1
    if blocker:
        return _complete_release_backfill_without_local_wait(
            job,ps,counts,blocker,
            'Local Discovery is currently running, so the legacy 0.10.41 network-heavy startup repair was finalized instead of retrying behind it.'
        )
    _job_start(job,'Repopulating missing Company Info')
    # Leads first because the reported regression is most visible there, then
    # Opportunities, then Address Book contacts which can reuse those results.
    work=[('hidden_leads',CompanyLead.objects.filter(user_deleted=False,deleted_at__isnull=True).order_by('-updated_at')),
          ('opportunities',Opportunity.objects.filter(user_deleted=False,suppressed=False).order_by('-last_seen'))]
    total=sum(len(rows) for _,rows in work)+Contact.objects.filter(deleted_at__isnull=True).count()
    done=0
    for label,rows in work:
        for entity in rows:
            try:
                if label=='hidden_leads' and not company_info_has_display_data(entity):
                    # Hidden Leads often share a company/domain with an Opportunity that
                    # already has the desired founding/domain-age or size signal. Reuse
                    # that retained result before spending any research budget.
                    _summary,intel=stored_company_context(
                        entity.company,
                        entity.contact_email,
                        entity.target_url or entity.source_url or entity.search_url,
                    )
                    if intel and company_info_has_display_data(intel):
                        entity.company_intel=intel
                        entity.save(update_fields=['company_intel','updated_at'])
                        counts['reused']+=1
                enrich_company_intel_from_retained(entity)
                if not company_info_has_display_data(entity):
                    blocker=_blocking_local_discovery_run() if ps.discovery_mode=='source_guided' else None
                    if blocker:
                        counts['network_research_skipped_due_to_local_discovery']=counts.get('network_research_skipped_due_to_local_discovery',0)+1
                    else:
                        research_company(entity)
                if company_info_has_display_data(entity): counts[label]+=1
            except Retry:
                raise
            except Exception:
                counts['failed']+=1
            done+=1
            if done%5==0:
                BackgroundJob.objects.filter(pk=job.pk,status='running').update(progress=min(94,max(2,int(done/max(1,total)*94))),message=f'Repopulating Company Info · {done}/{total}',result=counts)
    contacts=Contact.objects.filter(deleted_at__isnull=True).order_by('-last_seen')
    for contact in contacts:
        try:
            summary,intel=stored_company_context(contact.company,contact.email,contact.source_url)
            changed=[]
            if intel and not company_info_has_display_data(contact): contact.company_intel=intel; changed.append('company_intel'); counts['reused']+=1
            if summary and not str(contact.company_summary or '').strip(): contact.company_summary=summary[:2000]; changed.append('company_summary')
            if changed: contact.save(update_fields=list(dict.fromkeys(changed)))
            enrich_company_intel_from_retained(contact)
            if not company_info_has_display_data(contact):
                blocker=_blocking_local_discovery_run() if ps.discovery_mode=='source_guided' else None
                if blocker:
                    counts['network_research_skipped_due_to_local_discovery']=counts.get('network_research_skipped_due_to_local_discovery',0)+1
                else:
                    research_company(contact)
            if not str(contact.company_summary or '').strip():
                summary=company_summary_from_intel(contact.company_intel or {},1200)
                if summary: contact.company_summary=summary; contact.save(update_fields=['company_summary'])
            try:
                intel_now=dict(contact.company_intel or {}); fit=intel_now.get('fit_classification') if isinstance(intel_now.get('fit_classification'),dict) else {}
                if not ('score' in fit and fit.get('score') not in (None,'')):
                    assessed,_review=assess_addressbook_contact_fit(contact)
                    if assessed:
                        contact.save(update_fields=['company_intel']); counts['contact_fit_backfilled']+=1
            except Exception:
                counts['failed']+=1
            if company_info_has_display_data(contact): counts['contacts']+=1
        except Retry:
            raise
        except Exception:
            counts['failed']+=1
        done+=1
        if done%5==0:
            BackgroundJob.objects.filter(pk=job.pk,status='running').update(progress=min(94,max(2,int(done/max(1,total)*94))),message=f'Repopulating Company Info · {done}/{total}',result=counts)
    # Historical Address Book quality pass: only automatically collected rows are eligible.
    for contact in Contact.objects.filter(deleted_at__isnull=True).exclude(source__iexact='manual').iterator(chunk_size=100):
        if Application.objects.filter(opportunity__contact_email__iexact=contact.email,deleted_at__isnull=True).exists():
            continue
        email=str(contact.email or '').casefold(); company=str(contact.company or '').strip(); summary=str(contact.company_summary or '').strip()
        obvious=bool(is_non_contact_address(email) or (not company and not summary and contact.confidence<45))
        if obvious:
            contact.deleted_at=timezone.now(); contact.is_read=True; contact.save(update_fields=['deleted_at','is_read']); counts['contacts_recycled_quality']+=1
        elif contact.confidence<60:
            counts['contacts_review_quality']+=1
    # Bounded fresh URL-health recalculation for every active historical record. Queueing is
    # lock-aware in url_health_refresh_job and therefore safe across startup retries.
    for kind,rows in [('opportunity',Opportunity.objects.filter(user_deleted=False,suppressed=False)),('hidden_lead',CompanyLead.objects.filter(user_deleted=False,deleted_at__isnull=True)),('contact',Contact.objects.filter(deleted_at__isnull=True))]:
        for row in rows.only('pk').iterator(chunk_size=250):
            try: url_health_refresh_job.delay(kind,row.pk); counts['url_health_requeued']+=1
            except Exception: counts['failed']+=1

    # Mark the release repair complete only after the task itself finishes. If the
    # worker is restarted mid-backfill, seed_defaults can safely queue it again.
    # 0.10.41: retain third-party discovery provenance, but prefer an exact employer/ATS
    # role URL when it can be independently verified. Generic career roots are never
    # substituted. This is intentionally part of the idle-aware release repair because
    # it can use configured Local search providers.
    counts['job_board_rows']=0; counts['employer_urls_recovered']=0; counts['board_provenance_added']=0
    for opp in Opportunity.objects.filter(user_deleted=False,suppressed=False).order_by('-last_seen').iterator(chunk_size=100):
        board_url=str(opp.target_url or opp.url or '').strip()
        if not _is_third_party_job_url(board_url):
            continue
        counts['job_board_rows']+=1
        try:
            facts=dict(opp.extracted_facts or {})
            original=str(facts.get('original_job_board_url') or board_url).strip()
            facts['original_job_board_url']=original
            marker=f'Original job board URL: {original}'
            description=str(opp.description or '').rstrip()
            # Re-fetch the original board while it is still known so historical rows can
            # recover explicit posted-date and remote-location evidence before URL repair.
            board=_direct_fetch(original,opp.title,description[:3000],purpose='upgrade_original_board',timeout=18) if original else {}
            board_text=str(board.get('text') or description or opp.raw_search_snippet or '')[:45000]
            board_signal=explicit_post_date_signal(board_text,schema_date=str(board.get('jobposting_date_posted') or ''),final_url=original)
            board_remote=normalize_remote_constraints(board_text+' '+str(board.get('jobposting_location') or ''),opp.remote_text)
            board_role_location=extract_role_location(board_text,board.get('jobposting_location') or '')
            facts['original_job_board_evidence']={
                'url':original[:1000], 'title':str(board.get('title') or opp.title)[:300],
                'posted_date':(board_signal.get('date').isoformat() if board_signal and board_signal.get('date') else ''),
                'posted_date_note':str((board_signal or {}).get('note') or '')[:500],
                'posted_date_confidence':int((board_signal or {}).get('confidence') or 0),
                'remote':board_remote or {}, 'role_location':board_role_location[:240],
            }
            if original and marker not in description:
                description=(description+'\n\n'+marker).strip()
                counts['board_provenance_added']+=1
            preferred=_prefer_exact_employer_role(opp.title,opp.company,original)
            changed=['extracted_facts']
            opp.extracted_facts=facts
            if description != str(opp.description or ''):
                opp.description=description; changed.append('description')
            if preferred and preferred.get('url'):
                direct=str(preferred['url']).strip()[:1000]
                facts['preferred_employer_url']=direct
                facts['employer_role_lookup']={
                    'provider':str(preferred.get('provider') or '')[:120],
                    'query':str(preferred.get('query') or '')[:500],
                    'title_similarity':preferred.get('title_similarity'),
                }
                if not opp.search_url:
                    opp.search_url=original[:1000]; changed.append('search_url')
                opp.url=direct; opp.target_url=direct; opp.canonical_url=direct.rstrip('/')
                opp.target_http_status=None; opp.target_checked_at=None; opp.target_check_error=''
                changed.extend(['url','target_url','canonical_url','target_http_status','target_checked_at','target_check_error'])
                counts['employer_urls_recovered']+=1
            opp.save(update_fields=list(dict.fromkeys(changed+['updated_at'])))
        except Exception:
            counts['failed']+=1
    # 0.10.41 retrospective data normalization: repair every stored Opportunity summary
    # (including Recycle Bin rows, so restored records are already clean) and mixed-script
    # title, then apply deterministic remote/post-date evidence already
    # retained in the record. This deliberately replaces old verbose highlights, not only blanks.
    counts.update({'titles_cleaned':0,'title_salary_recovered':0,'summaries_rebuilt':0,'role_locations_repaired':0,'remote_constraints_repaired':0,'post_dates_repaired':0,
                   'facebook_removed':0,'facebook_retained_unavailable':0,'facebook_titles_cleaned':0,'facebook_added':0,'legacy_cloud_sources_hidden':0,'countries_repaired':0})
    try:
        hidden=SearchSource.objects.filter(category__iexact='Cloud AI Discovery').exclude(source_type='cloud_ai').update(source_type='cloud_ai',enabled=True)
        counts['legacy_cloud_sources_hidden']=int(hidden or 0)
    except Exception:
        counts['failed']+=1
    for opp in Opportunity.objects.all().order_by('pk').iterator(chunk_size=200):
        changed=[]
        try:
            clean_title,title_salary=normalize_opportunity_title(opp.title)
            clean_title=sanitize_mixed_script_title(clean_title)[:300]
            if clean_title and clean_title!=opp.title:
                opp.title=clean_title; changed.append('title'); counts['titles_cleaned']+=1
            # Recover compensation embedded in legacy titles before permanently removing it.
            if title_salary and not salary_text_has_numeric_amount(opp.salary_text):
                parsed_salary=parse_salary_text(title_salary)
                if parsed_salary:
                    salary_info={
                        'salary_text':str(parsed_salary.get('text') or title_salary)[:300],
                        'salary_currency':parsed_salary.get('currency',''),
                        'salary_min':parsed_salary.get('min'),'salary_max':parsed_salary.get('max'),
                        'salary_period':parsed_salary.get('period',''),'salary_source_type':'post',
                        'salary_source_url':str(opp.target_url or opp.url or '')[:1000],
                        'salary_confidence':88,'salary_checked_at':timezone.now(),
                    }
                    apply_salary_info(opp,salary_info,save=False)
                    changed.extend(['salary_text','salary_currency','salary_min','salary_max','salary_period','salary_source_type','salary_source_url','salary_confidence','salary_checked_at'])
                    counts['title_salary_recovered']+=1
            # Strip historical display-only provenance/noise from stored salary text.
            salary_clean=re.sub(r'(?i)\s*(?:job\s*post(?:ing)?)\s*$', '', str(opp.salary_text or '')).strip(' \t\r\n√✓|·')
            if salary_clean and salary_clean!=str(opp.salary_text or ''):
                opp.salary_text=salary_clean[:300]; changed.append('salary_text')
            rebuilt=derive_opportunity_highlight(
                opportunity=opp,title=opp.title,
                description=opp.description or opp.raw_search_snippet,
                facts=opp.extracted_facts or {},remote_text=opp.remote_text,
            ) or concise_technical_summary(opp.list_highlight)
            if rebuilt[:600] != str(opp.list_highlight or ''):
                opp.list_highlight=rebuilt[:600]; changed.append('list_highlight'); counts['summaries_rebuilt']+=1
            facts=dict(opp.extracted_facts or {})
            board_evidence=facts.get('original_job_board_evidence') if isinstance(facts.get('original_job_board_evidence'),dict) else {}
            location_hint=facts.get('jobLocation') or board_evidence.get('role_location') or ''
            role_location=extract_role_location(opp.description or opp.raw_search_snippet,location_hint)
            if not role_location and board_evidence.get('role_location'):
                role_location=str(board_evidence.get('role_location') or '')[:240]
            if role_location and role_location != str(getattr(opp,'role_location','') or ''):
                opp.role_location=role_location[:240]; changed.append('role_location'); counts['role_locations_repaired']+=1
            explicit_country=infer_country(opp.target_url or opp.url,role_location or (opp.description or opp.raw_search_snippet),location_hint=location_hint,strict=True)
            if explicit_country and explicit_country != str(opp.country or '').strip():
                opp.country=explicit_country[:120]; changed.append('country'); counts['countries_repaired']+=1
            remote=normalize_remote_constraints(opp.description or opp.raw_search_snippet,opp.remote_text)
            board_remote=board_evidence.get('remote') if isinstance(board_evidence.get('remote'),dict) else {}
            if board_remote.get('country') and not (remote or {}).get('country'):
                remote=board_remote
            if remote:
                current=facts.get('remote_classification') if isinstance(facts.get('remote_classification'),dict) else {}
                if current != remote:
                    facts['remote_classification']={**remote,'source':'0.10.41 deterministic retrospective repair','at':timezone.now().isoformat()}
                    opp.extracted_facts=facts; changed.append('extracted_facts')
                    opp.remote_text=remote['label'][:220]; changed.append('remote_text')
                    if remote.get('country') and opp.country!=remote['country']:
                        opp.country=remote['country'][:120]; changed.append('country')
                    counts['remote_constraints_repaired']+=1
            # Explicit visible/schema board dates override unknown/guessed historical ages.
            sig=explicit_post_date_signal(opp.description or opp.raw_search_snippet,final_url=opp.target_url or opp.url)
            if board_evidence.get('posted_date'):
                try:
                    board_dt=datetime.fromisoformat(str(board_evidence.get('posted_date')).replace('Z','+00:00'))
                    if timezone.is_naive(board_dt): board_dt=timezone.make_aware(board_dt,timezone.get_current_timezone())
                    board_sig={'date':board_dt,'confidence':int(board_evidence.get('posted_date_confidence') or 95),'note':str(board_evidence.get('posted_date_note') or ''),'source':'Original job board'}
                    if not sig or int(board_sig['confidence'])>=int(sig.get('confidence') or 0): sig=board_sig
                except Exception:
                    pass
            post_age_state=facts.get('post_age') if isinstance(facts.get('post_age'),dict) else {}
            should_replace_age=bool(sig and (not opp.declared_posted_at or int(opp.freshness_confidence or 0)<int(sig.get('confidence') or 0) or str(post_age_state.get('method') or '').lower() in {'','unknown','guess','inferred'}))
            if should_replace_age:
                    dt=sig['date']; days=max(0,(timezone.now()-dt).days)
                    label=post_age_label_for_days(days)
                    opp.declared_posted_at=dt; opp.estimated_first_seen=dt; opp.freshness_label=label; opp.freshness_confidence=int(sig.get('confidence') or 96)
                    changed.extend(['declared_posted_at','estimated_first_seen','freshness_label','freshness_confidence'])
                    OpportunityEvidence.objects.update_or_create(opportunity=opp,kind='page_date',label='Explicit posting date',source_url=opp.target_url or opp.url,
                        defaults={'value':dt.isoformat(),'confidence':opp.freshness_confidence,'metadata':{'source':'0.10.41 deterministic retrospective repair','evidence':sig.get('note','')}})
                    counts['post_dates_repaired']+=1
            if changed:
                opp.save(update_fields=list(dict.fromkeys(changed+['updated_at'])))
        except Exception:
            counts['failed']+=1

    # Pages to Watch cleanup is direct-evidence based. Delete noisy/irrelevant legacy rows;
    # then use configured Local search providers to find a small set of new career Pages and
    # persist only Pages that pass the same direct validation as ordinary discovery.
    try:
        for page in list(FacebookPage.objects.filter(deleted_at__isnull=True)):
            url=str(page.page_url or f'https://www.facebook.com/{page.page_id}')
            relevant,_reason,_text,_page_title=facebook_page_relevant(url,page.page_title,'',direct=True)
            direct_unavailable=('direct Page fetch unavailable' in _reason)
            if not relevant:
                if direct_unavailable and getattr(page,'validation_state','unknown')=='verified':
                    page.validation_state='unavailable'; page.validation_reason=_reason[:500]; page.validated_at=timezone.now(); page.save(update_fields=['validation_state','validation_reason','validated_at','updated_at']); counts['facebook_retained_unavailable']+=1
                    continue
                page.deleted_at=timezone.now(); page.enabled=False; page.is_read=True; page.save(update_fields=['deleted_at','enabled','is_read','updated_at']); counts['facebook_removed']+=1
                continue
            updates=[]; state='verified' if _reason.startswith('direct Page-owned') else 'indexed'
            if _page_title and _page_title!=page.page_title:
                page.page_title=_page_title[:300]; updates.append('page_title'); counts['facebook_titles_cleaned']+=1
            if not page.enabled:
                page.enabled=True; updates.append('enabled')
            page.validation_state=state; page.validation_reason=_reason[:500]; page.validated_at=timezone.now(); updates.extend(['validation_state','validation_reason','validated_at'])
            page.save(update_fields=list(dict.fromkeys(updates+['updated_at'])))
        providers,_meta=provider_selection_details(limit=2)
        profile=build_search_profile(use_saved_overrides=True)
        skill_terms=[str(x.get('term') or '') for x in (profile.get('skills') or []) if isinstance(x,dict)][:4]
        focus=' '.join(x for x in skill_terms if x)[:160] or 'software engineering'
        for provider in providers[:2]:
            for query in (f'site:facebook.com careers hiring {focus}',f'site:facebook.com jobs engineering {focus}'):
                rows,err=search_source(provider,query,limit=8,usage_category='facebook_watch_upgrade')
                if err: continue
                for result in rows or []:
                    before=FacebookPage.objects.count()
                    row=remember_facebook_page(result)
                    if row and FacebookPage.objects.count()>before:
                        counts['facebook_added']+=1
    except Exception:
        counts['failed']+=1

    # Mark the release repair complete only after all upgrade passes finish.
    ps.release_backfill_version='0.10.41'
    ps.save(update_fields=['release_backfill_version','updated_at'])
    _job_done(job,counts,f"0.10.41 backfill complete: {counts['employer_urls_recovered']} employer URLs recovered; {counts['summaries_rebuilt']} summaries normalized; {counts['facebook_removed']} irrelevant Facebook Pages removed")
    return counts


@shared_task(bind=True)
def system_diagnostics_job(self, job_id):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Checking system components')
    try:
        rows=run_system_diagnostics()
        _job_done(job,{'diagnostics':rows},'Diagnostics refreshed'); return {'diagnostics':rows}
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task(bind=True)
def diagnostic_export_job(self, job_id):
    """Build the support archive off the web worker and expose a private download."""
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Collecting diagnostic data')
    try:
        from django.test import RequestFactory
        from portal.views import _build_diagnostic_export_response
        seed=dict(job.result or {})
        # Export artifacts are private staging files, not permanent records. Remove files
        # from completed jobs after one day while retaining the job audit/status row.
        cutoff=timezone.now()-timedelta(hours=24)
        for old in BackgroundJob.objects.filter(kind='diagnostic',label='Diagnostic data export',finished_at__lt=cutoff).order_by('finished_at')[:100]:
            old_result=dict(old.result or {}); old_name=str(old_result.get('storage_name') or '')
            if old_name:
                try: default_storage.delete(old_name)
                except Exception: pass
                old_result.pop('storage_name',None); old_result['expired']=True; old.result=old_result; old.save(update_fields=['result'])
        user=User.objects.get(pk=seed.get('requested_by_user_id'))
        categories=[str(x) for x in (seed.get('categories') or []) if str(x)]
        params=[('period',seed.get('period') or '24h')]
        if categories:
            params.extend(('category',value) for value in categories)
        else:
            params.extend([
                ('include_records','1' if seed.get('include_records') else '0'),
                ('include_diagnostics','1' if seed.get('include_diagnostics') else '0'),
            ])
        request=RequestFactory().get('/internal/diagnostic-export/',params)
        request.user=user
        job.progress=20; job.message='Collecting records and operational diagnostics'; seed['phase']='collecting'; job.result=seed; job.save(update_fields=['progress','message','result'])
        response=_build_diagnostic_export_response(request)
        if response.status_code!=200:
            raise RuntimeError(getattr(response,'content',b'Unable to build diagnostic export').decode('utf-8','replace')[:500])
        disposition=str(response.get('Content-Disposition') or '')
        match=re.search(r'filename="?([^";]+)',disposition)
        filename=(match.group(1) if match else f'scoutbox-support-{timezone.now():%Y%m%d-%H%M%S}.zip')
        job.progress=85; job.message='Saving diagnostic archive'; seed['phase']='saving'; job.result=seed; job.save(update_fields=['progress','message','result'])
        storage_name=default_storage.save(f'diagnostic_exports/{job.pk}/{filename}',ContentFile(bytes(response.content)))
        result={**seed,'phase':'ready','storage_name':storage_name,'filename':filename,'download_url':f'/settings/export-diagnostics/{job.pk}/download/','size_bytes':len(response.content)}
        _job_done(job,result,'Diagnostic export ready to download')
        return result
    except Exception as exc:
        _job_fail(job,exc); raise

@shared_task(bind=True)
def blog_stats_test_job(self, job_id, config_id=1):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Testing external statistics data source')
    try:
        cfg=BlogStatsConfig.objects.get(pk=config_id)
        result=test_blog_connection(cfg)
        if result.get('ok'):
            _job_done(job,result,result.get('message') or 'External statistics connection test completed')
        else:
            job.status='failed'; job.finished_at=timezone.now(); job.progress=100; job.message='External statistics connection test failed'; job.error=result.get('message') or 'Connection test failed'; job.result=result; job.save()
        return result
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task(bind=True)
def performance_lab_job(self, job_id, params, storage_path='', original_name=''):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Running Performance Lab test')
    try:
        upload=None
        if storage_path:
            class StoredUpload:
                def __init__(self, fh, name): self._fh=fh; self.name=name
                def read(self,*a,**k): return self._fh.read(*a,**k)
                def seek(self,*a,**k): return self._fh.seek(*a,**k)
            fh=default_storage.open(storage_path,'rb'); upload=StoredUpload(fh,original_name)
        run=run_lab(params.get('kind','chat'),params.get('provider','ollama'),params.get('model',''),params.get('device','auto'),params.get('input_text',''),params.get('input_url',''),upload,params.get('temp_ollama_url',''))
        if storage_path:
            try: fh.close(); default_storage.delete(storage_path)
            except Exception: pass
        result={'performance_run_id':run.pk,'ok':run.ok,'error':run.error,'latency_ms':run.latency_ms}
        if run.ok: _job_done(job,result,'Performance test completed')
        else:
            job.status='failed'; job.finished_at=timezone.now(); job.progress=100; job.message='Performance test failed'; job.error=run.error; job.result=result; job.save();
        return result
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task(bind=True)
def tracking_link_test_job(self, job_id, article_url):
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''; _job_start(job,'Loading article analysis and suffix reserve')
    try:
        job.progress=8; job.message='Resolving article and preparing suffix reserve'; job.save(update_fields=['progress','message'])
        preview=preview_for_url(article_url)
        job.progress=52; job.message=f"Suffix reserve ready · {preview.get('reserve_count',0)} available"; job.save(update_fields=['progress','message'])
        # preview_for_url() has already resolved and validated the destination and prepared
        # its rule/reserve. Allocate from that exact rule so Test & Generate does not fetch
        # the article a second time before creating the tracking link.
        info=dict(preview.get('info') or {})
        link=allocate(preview['rule'])
        info['reserve_remaining']=reserve_count(preview['rule']) if 'reserve_remaining' not in info else info['reserve_remaining']
        job.progress=88; job.message='Tracking link allocated; finalizing result'; job.save(update_fields=['progress','message'])
        result={
            'article_url':article_url,
            'page_title':info.get('title',''),
            'resolved_url':info.get('resolved_url',''),
            'article_path':info.get('article_path',''),
            'words':info.get('words',[]),
            'sample_suffix':preview.get('sample_suffix',''),
            'generated_link':link.full_url,
            'generated_base_url':link.full_url[:-len(link.suffix)] if link.suffix and link.full_url.endswith(link.suffix) else link.full_url,
            'generated_suffix':link.suffix if link.suffix and link.full_url.endswith(link.suffix) else '',
            'reserve_remaining':info.get('reserve_remaining',max(0,preview.get('reserve_count',0)-1)),
            'analysis_cached':bool(info.get('cached')),
        }
        _job_done(job,result,'Tracking link generated')
        return result
    except Exception as exc:
        _job_fail(job,exc); raise


@shared_task
def tracking_article_title_tick(limit=8):
    """Repair missing/link-shaped Tracking Link article titles from live page metadata."""
    limit=max(1,min(20,int(limit or 8)))
    candidates=[]
    for rule in TrackingLinkRule.objects.filter(enabled=True).exclude(destination_url='').order_by('-created_at').only('pk','name','base_path','destination_url','article_title')[:200]:
        if article_title_needs_refresh(rule.article_title,rule.destination_url,rule.name,rule.base_path):
            candidates.append(rule)
            if len(candidates)>=limit:
                break
    counts={'checked':0,'updated':0,'failed':0}
    for rule in candidates:
        counts['checked']+=1
        try:
            info=resolve_article(rule.destination_url,timeout=8)
            title=clean_article_title(info.get('title'))
            if title and title != rule.article_title:
                TrackingLinkRule.objects.filter(pk=rule.pk).update(article_title=title)
                counts['updated']+=1
        except Exception:
            counts['failed']+=1
    return counts


@shared_task
def resource_sample_tick():
    try:
        sample=capture_resource_sample()
        return {
            'sample_id':sample.pk,
            'cpu':float(sample.cpu_percent or 0.0),
            'memory':float(sample.memory_percent or 0.0),
            'gpu':sample.gpu_percent,
            'gpu_state':getattr(sample,'gpu_telemetry_state',''),
            'gpu_age_seconds':getattr(sample,'gpu_sample_age_seconds',None),
        }
    except Exception as exc:
        return {'error':str(exc)}


@shared_task
def facebook_page_title_tick(limit=8):
    """Resolve blank Facebook Page titles with automatic bounded retries.

    Page identity is intentionally independent from career/relevance validation. Facebook can
    block direct validation while ScoutBox still has a trustworthy Page ID or retained indexed
    identity, so those identity sources can repair the visible title without a user click.
    """
    max_attempts=4
    max_window=timedelta(minutes=20)
    now=timezone.now()
    rows=list(FacebookPage.objects.filter(enabled=True,deleted_at__isnull=True,page_title='').exclude(
        validation_state__in=['unavailable','failed']).order_by('validated_at','pk')[:max(1,min(20,int(limit or 8)))])
    counts={'checked':0,'resolved':0,'retrying':0,'unavailable':0}
    for page in rows:
        counts['checked']+=1
        started=page.title_retry_started_at or now
        attempt=max(0,int(page.title_retry_count or 0))+1
        url=str(page.page_url or f'https://www.facebook.com/{page.page_id}')
        reason=''
        try:
            resolved=facebook_page_identity_title(url,'',page.evidence_text or '',page.page_id,direct=True)
            title=str(resolved.get('title') or '').strip()[:300]
            source=str(resolved.get('source') or '')
            reason={
                'direct':'Page title resolved from Facebook Page metadata.',
                'stored':'Page title resolved from retained Page identity.',
                'indexed':'Page title resolved from retained indexed Page identity.',
                'page_id':'Page title resolved from the retained Facebook Page ID while direct metadata was unavailable.',
            }.get(source,'')
        except Exception as exc:
            title=''; reason=str(exc)[:360]
        page.validated_at=now
        page.title_retry_started_at=started
        page.title_retry_count=attempt
        if title:
            page.page_title=title
            old_state=page.validation_state
            if old_state in {'','unknown','pending','unavailable','failed'}:
                page.validation_state='indexed'
            if not page.validation_reason or old_state in {'pending','unavailable','failed'}:
                page.validation_reason=reason[:500]
            counts['resolved']+=1
            page.save(update_fields=['page_title','validation_state','validation_reason','validated_at','title_retry_count','title_retry_started_at','updated_at'])
            continue
        expired=(now-started)>=max_window
        if attempt>=max_attempts or expired:
            page.validation_state='unavailable'
            detail=(' '+reason) if reason else ''
            page.validation_reason=(f'Page title unavailable after {attempt} automatic attempt{"" if attempt==1 else "s"}.'+detail)[:500]
            counts['unavailable']+=1
        else:
            page.validation_state='pending'
            detail=(' Last result: '+reason) if reason else ''
            page.validation_reason=(f'Page-title lookup will retry automatically (attempt {attempt} of {max_attempts}).'+detail)[:500]
            counts['retrying']+=1
        page.save(update_fields=['validation_state','validation_reason','validated_at','title_retry_count','title_retry_started_at','updated_at'])
    return counts


def _domain_refresh_due(entity, now=None):
    """Return True when deterministic domain metadata needs a bounded retry."""
    now=now or timezone.now()
    intel=getattr(entity,'company_intel',{}) or {}
    structured=intel.get('structured') if isinstance(intel,dict) and isinstance(intel.get('structured'),dict) else {}
    if not structured.get('domain_age_refresh_needed'):
        return False
    checked=str(structured.get('domain_age_checked_at') or '').strip()
    if checked:
        try:
            checked_at=datetime.fromisoformat(checked.replace('Z','+00:00'))
            if timezone.is_naive(checked_at):
                checked_at=timezone.make_aware(checked_at,timezone.get_current_timezone())
            # Avoid hammering RDAP when a registrar/network endpoint is temporarily unavailable.
            if now-checked_at < timedelta(hours=6):
                return False
        except Exception:
            pass
    return True


def _domain_refresh_candidates(qs, limit, now):
    """Find marked records while remaining portable across JSONField database backends."""
    limit=max(1,int(limit or 1))
    try:
        rows=list(qs.filter(company_intel__structured__domain_age_refresh_needed=True).order_by('-pk')[:limit*8])
    except Exception:
        rows=list(qs.order_by('-pk')[:max(200,limit*30)])
    return [row for row in rows if _domain_refresh_due(row,now)][:limit]


@shared_task
def company_domain_refresh_tick():
    """Backfill company Domain/Domain age without consuming Local or Cloud AI.

    Work is deliberately small per tick and cached by normalized domain inside the
    company-research service. Failed RDAP lookups are retried no more than every six hours.
    """
    now=timezone.now(); result={'checked':0,'updated':0,'retry':0,'errors':0}
    groups=(
        Opportunity.objects.filter(user_deleted=False,suppressed=False),
        CompanyLead.objects.filter(user_deleted=False,deleted_at__isnull=True),
        Contact.objects.filter(deleted_at__isnull=True),
    )
    for qs in groups:
        for entity in _domain_refresh_candidates(qs,4,now):
            result['checked']+=1
            try:
                status=refresh_company_domain_registration(entity) or {}
                if status.get('changed'): result['updated']+=1
                if status.get('retry'): result['retry']+=1
            except Exception:
                result['errors']+=1
    return result



@shared_task(bind=True)
def focus_taxonomy_rebuild_job(self, job_id):
    """Rare, atomic full Focus population for substantial corpus change.

    Live Focus values are not cleared first. The service builds all assignments in a
    shadow mapping and commits only after every list has been classified successfully.
    """
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''
    _job_start(job,'Refreshing Focus taxonomy with Local AI')
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    try:
        def progress(done,total):
            pct=min(99,int((done/max(1,total))*100))
            job.progress=pct; job.message=f'Refreshing Focus taxonomy · {done} / {total}'
            job.save(update_fields=['progress','message'])
        result=rebuild_all_focus_taxonomies_with_ai(getattr(ps,'max_focus_groups',15) or 15,progress=progress)
        snapshot=focus_taxonomy_snapshot(); now_iso=timezone.now().isoformat(); state={}
        for key,row in snapshot.items():
            state[key]={
                'last_full_population_at':now_iso,
                'last_full_population_count':int(row.get('total') or 0),
                'last_classified_count':int(row.get('classified') or 0),
                'last_group_count':int(row.get('groups') or 0),
                'last_attempt_at':now_iso,'last_error':'',
            }
        state['v010118_focus_quality_repair_pending']=False
        state['v010118_focus_quality_repair_completed_at']=now_iso
        ps.focus_taxonomy_state=state; ps.focus_taxonomy_version=FOCUS_TARGET_VERSION
        ps.save(update_fields=['focus_taxonomy_state','focus_taxonomy_version','updated_at'])
        result['trigger']=((job.result or {}).get('trigger') or {})
        _job_done(job,result,'Focus taxonomy refreshed atomically')
        return result
    except Exception as exc:
        # Keep the live taxonomy unchanged and avoid a perpetual retry loop when Ollama is
        # temporarily unavailable. The scheduler may try again after a 24-hour cooldown.
        state=dict(getattr(ps,'focus_taxonomy_state',{}) or {}); now_iso=timezone.now().isoformat()
        for key in ('opportunities','hidden_leads','address_book'):
            row=dict(state.get(key) or {}); row['last_attempt_at']=now_iso; row['last_error']=str(exc)[:500]; state[key]=row
        ps.focus_taxonomy_state=state; ps.save(update_fields=['focus_taxonomy_state','updated_at'])
        job.status='failed'; job.finished_at=timezone.now(); job.message='Focus taxonomy refresh failed; existing labels were preserved'; job.error=str(exc)[:4000]
        job.save(update_fields=['status','finished_at','message','error'])
        raise


def _queue_focus_taxonomy_rebuild(settings_row):
    decision=focus_taxonomy_rebuild_due(settings_row)
    if not decision.get('due'):
        return None
    label='Repair Focus label evidence for 0.11.3'
    existing=BackgroundJob.objects.filter(kind='other',label=label,status__in=['queued','running']).order_by('-pk').first()
    if existing:
        return existing.pk
    # 0.11.3 is a forced version-gated rebuild. Do not let last_attempt_at from
    # earlier releases suppress the first queue event.
    # After a same-release failure, retry at most once per 24 hours to avoid a loop
    # when Local AI is unavailable.
    latest_same=BackgroundJob.objects.filter(kind='other',label=label,status__in=['failed','stopped']).order_by('-finished_at','-pk').first()
    if latest_same and latest_same.finished_at and timezone.now()-latest_same.finished_at < timedelta(hours=24):
        return None
    job=BackgroundJob.objects.create(kind='other',label=label,status='queued',message='Queued evidence-anchored Focus label repair after 0.11.3 upgrade',result={'focus_taxonomy_rebuild':True,'release':FOCUS_TARGET_VERSION,'trigger':decision})
    task=focus_taxonomy_rebuild_job.delay(job.pk)
    job.celery_task_id=str(task.id or ''); job.save(update_fields=['celery_task_id'])
    return job.pk



@shared_task(bind=True)
def focus_blank_backfill_job(self, job_id):
    """Retry blank Focus classifications without changing established labels."""
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''
    _job_start(job,'Backfilling blank Focus labels')
    try:
        before=focus_taxonomy_snapshot()
        result=backfill_blank_focuses(limit_per_model=80)
        after=focus_taxonomy_snapshot()
        result['snapshot_before']=before
        result['snapshot_after']=after
        result['changed_total']=sum(int((row or {}).get('changed') or 0) for row in result.values() if isinstance(row,dict))
        _job_done(job,result,'Blank Focus backfill completed')
        return result
    except Exception as exc:
        job.status='failed'; job.finished_at=timezone.now(); job.message='Blank Focus backfill failed; existing labels were preserved'; job.error=str(exc)[:4000]
        job.save(update_fields=['status','finished_at','message','error'])
        raise


def _queue_focus_blank_backfill(settings_row):
    snap=focus_taxonomy_snapshot()
    blanks=0
    for key,row in snap.items():
        blanks += max(0,int(row.get('total') or 0)-int(row.get('classified') or 0))
    if blanks<=0:
        return None
    label='Backfill blank Focus labels'
    existing=BackgroundJob.objects.filter(kind='other',label__in=['Refresh Focus taxonomy',label],status__in=['queued','running']).order_by('-pk').first()
    if existing:
        return existing.pk
    # Blank-only repair is deterministic.  Re-running it every scheduler tick after a
    # no-progress pass just creates an endless BackgroundJob loop.  Enforce a normal
    # cooldown between productive passes and a much longer cooldown when the previous
    # pass changed nothing; new records can still trigger classification on save.
    latest=BackgroundJob.objects.filter(kind='other',label=label,status__in=['completed','failed','stopped']).order_by('-finished_at','-pk').first()
    if latest and latest.finished_at:
        age=timezone.now()-latest.finished_at
        payload=latest.result if isinstance(latest.result,dict) else {}
        changed=payload.get('changed_total')
        if changed is None:
            changed=sum(int((row or {}).get('changed') or 0) for row in payload.values() if isinstance(row,dict))
        if int(changed or 0)<=0 and age < timedelta(hours=24):
            return None
        if age < timedelta(minutes=30):
            return None
    job=BackgroundJob.objects.create(kind='other',label=label,status='queued',message='Queued blank-only Focus recovery',result={'focus_blank_backfill':True,'release':FOCUS_TARGET_VERSION,'snapshot':snap})
    task=focus_blank_backfill_job.delay(job.pk)
    job.celery_task_id=str(task.id or ''); job.save(update_fields=['celery_task_id'])
    return job.pk


@shared_task(bind=True)
def v010104_integrity_repair_job(self, job_id):
    """One-time upgrade cleanup for blacklist leaks and invalid Opportunity substitutions."""
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''
    _job_start(job,'Repairing blacklist and Opportunity integrity')
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    try:
        blacklist=enforce_active_blacklist()
        def progress(done,total,stats):
            job.progress=min(99,int((done/max(1,total))*100)); job.message=f'Revalidating retained opportunities · {done} / {total}'
            job.result={'release':'0.10.106','blacklist':blacklist,'opportunity_integrity':dict(stats or {})}
            job.save(update_fields=['progress','message','result'])
        integrity=repair_existing_opportunity_integrity(progress=progress)
        result={'blacklist':blacklist,'opportunity_integrity':integrity}
        ps.integrity_repair_version='0.10.106'; ps.save(update_fields=['integrity_repair_version','updated_at'])
        _job_done(job,result,'Blacklist and Opportunity integrity repair completed')
        return result
    except Exception as exc:
        job.status='failed'; job.error=str(exc)[:4000]; job.message='0.10.106 integrity repair failed'; job.finished_at=timezone.now()
        job.save(update_fields=['status','error','message','finished_at']); raise


def _queue_v010104_integrity_repair(settings_row):
    if str(getattr(settings_row,'integrity_repair_version','') or '')=='0.10.106':
        return None
    label='Repair blacklist and Opportunity integrity for 0.10.106'
    existing=BackgroundJob.objects.filter(kind='other',label=label,status__in=['queued','running']).order_by('-pk').first()
    if existing: return existing.pk
    job=BackgroundJob.objects.create(kind='other',label=label,status='queued',message='Queued one-time 0.10.106 integrity repair',result={'release':'0.10.106','integrity_repair':True})
    task=v010104_integrity_repair_job.delay(job.pk); job.celery_task_id=str(task.id or ''); job.save(update_fields=['celery_task_id'])
    return job.pk




def _hidden_lead_has_outreach(lead):
    """Return True when a Hidden Lead has user/outreach work that must never be auto-recycled.

    Existing outreach is broader than a linked Application: a prepared cold draft, a
    direct opportunity generated from the lead, a running draft/research job, or an
    application created from that direct opportunity all mean the lead should remain
    visible even when the quality reassessment says the source itself is weak.
    """
    try:
        if (getattr(lead, 'draft_subject', '') or '').strip() or (getattr(lead, 'draft_body', '') or '').strip():
            return True
    except Exception:
        pass
    try:
        linked_opps = Opportunity.objects.filter(extracted_facts__market_study_lead_id=lead.pk)
        if linked_opps.exists():
            if Application.objects.filter(opportunity_id__in=list(linked_opps.values_list('pk', flat=True))).exists():
                return True
            if linked_opps.filter(application_draft_requested_at__isnull=False).exists():
                return True
            if linked_opps.filter(extracted_facts__outreach=True).exists():
                return True
    except Exception:
        pass
    try:
        if BackgroundJob.objects.filter(
            status__in=['queued','running'],
        ).filter(
            Q(result__lead_id=lead.pk)|Q(result__market_lead_id=lead.pk)
        ).exists():
            return True
    except Exception:
        pass
    return False


def _lead_reassessment_campaign(lead):
    try:
        if getattr(lead, 'origin_campaign_id', None):
            return lead.origin_campaign
    except Exception:
        pass
    try:
        return lead.campaigns.filter(deleted_at__isnull=True).order_by('pk').first() or lead.campaigns.order_by('pk').first()
    except Exception:
        return None



def _hidden_lead_existing_reassessment_item(lead):
    """Return a durable reassessment item for an already-checked lead.

    Existing Hidden Lead reassessment must survive container restarts and minor
    release bumps.  The only reliable durable cursor is the per-lead ai_state entry
    written after an item is assessed or explicitly skipped.  Accept any sane
    ``hidden_lead_minibrowser_reassessment`` dict instead of tying resume behavior to
    a patch-version string; otherwise each new build can restart at 1/N.
    """
    try:
        state=(lead.ai_state or {}).get('hidden_lead_minibrowser_reassessment')
    except Exception:
        state=None
    if not isinstance(state,dict):
        return None
    source=str(state.get('source') or '')
    release=str(state.get('release') or '')
    # A completed/skipped reassessment item is durable even when it came from an
    # earlier 0.11.x patch.  Only ignore clearly unrelated/empty metadata.
    has_decision = any(k in state for k in ('decision','admit','review','lead_score','score','reason','why_relevant','reason_to_contact','skipped_current','timeout','timed_out'))
    known_release = release.startswith('0.11.') or release.startswith('0.10.')
    known_source = 'hidden_lead_minibrowser_reassessment' in source or 'existing_hidden_lead_minibrowser_reassessment' in source
    if not (has_decision or known_source or known_release):
        return None
    decision=str(state.get('decision') or ('reject' if not state.get('admit') and not state.get('review') else ('admit' if state.get('admit') else 'review'))).lower()
    try: score=max(0,min(100,int(state.get('lead_score') or state.get('score') or getattr(lead,'score',0) or 0)))
    except Exception: score=int(getattr(lead,'score',0) or 0)
    protected=bool(state.get('protected_outreach') or _hidden_lead_has_outreach(lead))
    timed_out=bool(state.get('timeout') or state.get('timed_out') or 'timeout' in str(state.get('reason') or '').lower())
    if decision == 'admit' or state.get('admit'):
        stat='admitted'; applied='admit'
    elif decision == 'reject' and not timed_out:
        stat='protected' if protected else 'rejected'; applied='protected' if protected else 'pending_recycle_after_completion'
    else:
        stat='review'; applied='timeout_review' if timed_out else 'review'
    reason=str(state.get('reason_to_contact') or state.get('why_relevant') or state.get('reason') or '').strip()
    item={
        'id':lead.pk,
        'company':str(lead.company or '')[:220],
        'decision':decision or 'review',
        'applied_decision':applied,
        'lead_score':score,
        'fit_after':score,
        'confidence':int(state.get('confidence') or state.get('fit_confidence') or 0),
        'protected_outreach':protected,
        'timed_out':timed_out,
        'reason':reason[:700],
        'pages':(state.get('pages') or state.get('evidence_urls') or [])[:8],
        'rejection_risks':(state.get('rejection_risks') or [])[:8],
        'resumed_from_previous_reassessment':True,
    }
    skipped_current=bool(state.get('skipped_current') or str(state.get('applied_decision') or '').lower()=='skipped_current_left_unchanged')
    return {
        'stat':stat,
        'item':item,
        'pending_recycle': bool(stat=='rejected' and not protected),
        'timed_out': timed_out,
        'skipped_current': skipped_current,
    }


def _hidden_lead_reassessment_seed_state(lead_ids):
    """Rebuild the durable pass cursor/counters from per-lead state once per launch.

    A restarted worker must not replay already-completed ids merely to rediscover its
    previous position.  Reconstructing the cursor in one database read gives the new
    worker the same monotonic processed count immediately and prevents the UI from
    jumping backwards while old rows are skipped one-by-one.
    """
    ordered=[]
    seen=set()
    for value in lead_ids or []:
        try:
            ident=int(value)
        except Exception:
            continue
        if ident <= 0 or ident in seen:
            continue
        seen.add(ident); ordered.append(ident)
    leads={x.pk:x for x in CompanyLead.objects.filter(pk__in=ordered)}
    seed={
        'processed':0,'admitted':0,'review':0,'rejected':0,'protected':0,
        'failed':0,'timed_out':0,'skipped_current':0,
        'completed_ids':[],'pending_recycle_ids':[],
    }
    for lead_id in ordered:
        lead=leads.get(lead_id)
        if not lead:
            continue
        existing=_hidden_lead_existing_reassessment_item(lead)
        if not existing:
            continue
        seed['processed']+=1
        seed['completed_ids'].append(lead_id)
        stat=str(existing.get('stat') or 'review')
        if stat in seed:
            seed[stat]=int(seed.get(stat) or 0)+1
        else:
            seed['review']=int(seed.get('review') or 0)+1
        if existing.get('timed_out'):
            seed['timed_out']=int(seed.get('timed_out') or 0)+1
        if existing.get('skipped_current'):
            seed['skipped_current']=int(seed.get('skipped_current') or 0)+1
        if existing.get('pending_recycle'):
            seed['pending_recycle_ids'].append(lead_id)
    return seed


def _parse_hidden_lead_reassessment_dt(value):
    try:
        raw=str(value or '').strip()
        if not raw:
            return None
        dt=datetime.fromisoformat(raw.replace('Z','+00:00'))
        if timezone.is_naive(dt):
            dt=timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
    except Exception:
        return None


def _hidden_lead_reassessment_target_ids():
    return list(CompanyLead.objects.filter(
        user_deleted=False,
        deleted_at__isnull=True,
    ).order_by('pk').values_list('pk', flat=True))


def _ensure_hidden_lead_reassessment_pass(settings_row, *, force_pending=False):
    """Return/create the durable Hidden Lead reassessment pass descriptor.

    The pass snapshot is stored in PortalSettings rather than in the transient
    BackgroundJob row.  A container restart can lose the celery execution while the
    database row still exists; keeping the target id list and pass status here lets a
    new worker continue the same pass and skip per-lead completed ai_state items.
    """
    state=dict(getattr(settings_row,'focus_taxonomy_state',{}) or {})
    pass_state=state.get(HIDDEN_LEAD_REASSESSMENT_PASS_KEY)
    if not isinstance(pass_state,dict):
        pass_state={}
    status=str(pass_state.get('status') or '').lower()
    if status=='completed' and not force_pending:
        return pass_state, state
    target_ids=pass_state.get('target_ids')
    if not isinstance(target_ids,list) or not target_ids:
        target_ids=_hidden_lead_reassessment_target_ids()
    clean_ids=[]
    seen=set()
    for value in target_ids:
        try:
            ident=int(value)
        except Exception:
            continue
        if ident in seen:
            continue
        seen.add(ident); clean_ids.append(ident)
    now=timezone.now().isoformat()
    pass_state.update({
        'pass_id': pass_state.get('pass_id') or f'{HIDDEN_LEAD_REASSESSMENT_SCHEMA}:{now}',
        'schema': HIDDEN_LEAD_REASSESSMENT_SCHEMA,
        'release': HIDDEN_LEAD_REASSESSMENT_RELEASE,
        'status': 'pending' if force_pending or status in {'','queued','running','stale','failed','stopped'} else status,
        'target_ids': clean_ids,
        'target_count': len(clean_ids),
        'resume_from_per_lead_state': True,
        'deletions_deferred_until_completed': True,
        'protected_outreach_not_recycled': True,
        'updated_at': now,
    })
    pass_state.setdefault('created_at', now)
    state[HIDDEN_LEAD_REASSESSMENT_PASS_KEY]=pass_state
    state['hidden_lead_minibrowser_reassessment_pending']=pass_state.get('status')!='completed'
    for key in (
        'v0119_hidden_lead_minibrowser_reassessment_pending',
        'v01111_hidden_lead_minibrowser_reassessment_pending',
        'v01115_hidden_lead_minibrowser_reassessment_pending',
        'v01119_hidden_lead_minibrowser_reassessment_pending',
    ):
        state[key]=False
    settings_row.focus_taxonomy_state=state
    settings_row.save(update_fields=['focus_taxonomy_state','updated_at'])
    return pass_state, state


def _clean_hidden_lead_reassessment_ids(values):
    clean=[]; seen=set()
    for value in values or []:
        try:
            ident=int(value)
        except Exception:
            continue
        if ident <= 0 or ident in seen:
            continue
        seen.add(ident); clean.append(ident)
    return clean


def _hidden_lead_reassessment_lease_owned(execution_token, *, pass_id=''):
    token=str(execution_token or '').strip()
    if not token:
        return False
    try:
        ps=PortalSettings.objects.get(pk=1)
        state=dict(ps.focus_taxonomy_state or {})
        pass_state=state.get(HIDDEN_LEAD_REASSESSMENT_PASS_KEY)
        if not isinstance(pass_state,dict):
            return False
        if str(pass_state.get('execution_token') or '') != token:
            return False
        if pass_id and str(pass_state.get('pass_id') or '') != str(pass_id):
            return False
        return str(pass_state.get('status') or '').lower() != 'completed'
    except Exception:
        return False


def _claim_hidden_lead_reassessment_execution(settings_row, job_id, execution_token='', celery_task_id=''):
    """Claim one durable execution lease for the existing-Hidden-Lead pass.

    New dispatches carry an explicit token. A legacy 0.11.26 delivery without one may
    claim only when no live lease exists. This makes delayed/duplicate Celery delivery
    harmless: only the token stored on the durable pass may mutate progress or leads.
    """
    now=timezone.now()
    supplied=str(execution_token or '').strip()
    with transaction.atomic():
        ps=PortalSettings.objects.select_for_update().get(pk=getattr(settings_row,'pk',1) or 1)
        job=BackgroundJob.objects.select_for_update().get(pk=job_id)
        state=dict(ps.focus_taxonomy_state or {})
        pass_state=state.get(HIDDEN_LEAD_REASSESSMENT_PASS_KEY)
        if not isinstance(pass_state,dict):
            pass_state={}
        if str(pass_state.get('status') or '').lower()=='completed':
            return None, None, ''
        current_token=str(pass_state.get('execution_token') or '').strip()
        lease_until=_parse_hidden_lead_reassessment_dt(pass_state.get('lease_expires_at'))
        result=dict(job.result or {}) if isinstance(job.result,dict) else {}
        expected=str(result.get('execution_token') or '').strip()
        if supplied:
            if current_token and current_token != supplied:
                return None, None, ''
            if expected and expected != supplied:
                return None, None, ''
        else:
            # Legacy delivery from 0.11.26: never displace a live 0.11.27 owner.
            if current_token and (lease_until is None or lease_until > now):
                return None, None, ''
            supplied=uuid.uuid4().hex
        pass_state.update({
            'schema':HIDDEN_LEAD_REASSESSMENT_SCHEMA,
            'release':HIDDEN_LEAD_REASSESSMENT_RELEASE,
            'status':'running',
            'execution_token':supplied,
            'execution_job_id':int(job_id),
            'execution_task_id':str(celery_task_id or ''),
            'execution_started_at':now.isoformat(),
            'lease_expires_at':(now+timedelta(seconds=HIDDEN_LEAD_REASSESSMENT_LEASE_SECONDS)).isoformat(),
            'updated_at':now.isoformat(),
        })
        pass_state.pop('dispatch_error',None)
        state[HIDDEN_LEAD_REASSESSMENT_PASS_KEY]=pass_state
        state['hidden_lead_minibrowser_reassessment_pending']=True
        ps.focus_taxonomy_state=state
        ps.save(update_fields=['focus_taxonomy_state','updated_at'])
        result.update({
            'hidden_lead_minibrowser_reassessment':True,
            'release':HIDDEN_LEAD_REASSESSMENT_RELEASE,
            'schema':HIDDEN_LEAD_REASSESSMENT_SCHEMA,
            'pass_id':pass_state.get('pass_id'),
            'execution_token':supplied,
            'execution_task_id':str(celery_task_id or ''),
        })
        job.status='running'
        job.started_at=job.started_at or now
        job.finished_at=None
        job.error=''
        job.celery_task_id=str(celery_task_id or job.celery_task_id or '')
        job.result=result
        job.progress=max(1,int(job.progress or 0))
        job.message='Reassessing existing Hidden Leads · resuming durable pass'
        job.label=HIDDEN_LEAD_REASSESSMENT_LABEL
        job.save(update_fields=['status','started_at','finished_at','error','celery_task_id','result','progress','message','label'])
        return ps, dict(pass_state), supplied


def _save_hidden_lead_reassessment_pass(settings_row, *, status, stats=None, current_item=None,
                                         clear_current=False, execution_token='', recycle_ids=None):
    """Persist monotonic durable progress, optionally under an execution lease.

    The completed-id set is unioned and counters never decrease. If ``execution_token``
    is supplied, a superseded worker is rejected before it can move the cursor, clear a
    newer current item, or finalize/recycle the pass.
    """
    token=str(execution_token or '').strip()
    now=timezone.now()
    with transaction.atomic():
        ps=PortalSettings.objects.select_for_update().get(pk=getattr(settings_row,'pk',1) or 1)
        state=dict(ps.focus_taxonomy_state or {})
        pass_state=state.get(HIDDEN_LEAD_REASSESSMENT_PASS_KEY)
        if not isinstance(pass_state,dict):
            pass_state={}
        current_status=str(pass_state.get('status') or '').lower()
        current_token=str(pass_state.get('execution_token') or '').strip()
        if token and current_token != token:
            return None
        if current_status=='completed' and status!='completed':
            return dict(pass_state)
        pass_state.update({
            'schema':HIDDEN_LEAD_REASSESSMENT_SCHEMA,
            'release':HIDDEN_LEAD_REASSESSMENT_RELEASE,
            'status':status,
            'updated_at':now.isoformat(),
        })
        if stats:
            for key in ('selected','processed','admitted','review','rejected','protected','recycled','failed','timed_out','skipped_current'):
                if key not in stats:
                    continue
                try:
                    incoming=int(stats.get(key) or 0)
                except Exception:
                    incoming=0
                try:
                    existing=int(pass_state.get(key) or 0)
                except Exception:
                    existing=0
                pass_state[key]=max(existing,incoming)
            for key in ('completed_ids','pending_recycle_ids','skip_current_ids'):
                values=stats.get(key)
                if isinstance(values,(list,tuple,set)):
                    merged=_clean_hidden_lead_reassessment_ids(list(pass_state.get(key) or [])+list(values))
                    pass_state[key]=merged
        completed=_clean_hidden_lead_reassessment_ids(pass_state.get('completed_ids') or [])
        pass_state['completed_ids']=completed
        pass_state['processed']=max(int(pass_state.get('processed') or 0),len(completed))
        if current_item is not None:
            pass_state['current_item']=dict(current_item)
        elif clear_current or status!='running':
            pass_state.pop('current_item',None)
        if token and status=='running':
            pass_state['lease_expires_at']=(now+timedelta(seconds=HIDDEN_LEAD_REASSESSMENT_LEASE_SECONDS)).isoformat()
        if status=='completed':
            ids=_clean_hidden_lead_reassessment_ids(list(pass_state.get('pending_recycle_ids') or [])+list(recycle_ids or []))
            if ids:
                recycled=CompanyLead.objects.filter(pk__in=ids,user_deleted=False,deleted_at__isnull=True).update(
                    user_deleted=True,deleted_at=now,is_read=True,updated_at=now)
                pass_state['recycled']=max(int(pass_state.get('recycled') or 0),int(recycled or 0))
            pass_state['processed']=max(int(pass_state.get('processed') or 0),int(pass_state.get('selected') or 0))
            pass_state.setdefault('completed_at',now.isoformat())
            state['hidden_lead_minibrowser_reassessment_completed_at']=pass_state['completed_at']
            pass_state['last_execution_token']=pass_state.get('execution_token') or token
            for key in ('execution_token','execution_job_id','execution_task_id','lease_expires_at','execution_dispatched_at'):
                pass_state.pop(key,None)
        elif status in {'failed','stopped','stale','pending'}:
            pass_state['last_execution_token']=pass_state.get('execution_token') or token
            for key in ('execution_token','execution_job_id','execution_task_id','lease_expires_at'):
                pass_state.pop(key,None)
        state[HIDDEN_LEAD_REASSESSMENT_PASS_KEY]=pass_state
        state['hidden_lead_minibrowser_reassessment_pending']=status!='completed'
        for key in (
            'v0119_hidden_lead_minibrowser_reassessment_pending',
            'v01111_hidden_lead_minibrowser_reassessment_pending',
            'v01115_hidden_lead_minibrowser_reassessment_pending',
            'v01119_hidden_lead_minibrowser_reassessment_pending',
        ):
            state[key]=False
        ps.focus_taxonomy_state=state
        ps.save(update_fields=['focus_taxonomy_state','updated_at'])
        # Keep the caller's long-lived instance coherent enough for subsequent helper calls.
        try:
            settings_row.focus_taxonomy_state=state
        except Exception:
            pass
        return dict(pass_state)


def _update_hidden_lead_reassessment_job(job_id, execution_token, *, progress=None, message=None,
                                         result=None, status=None, error=None, finished=False):
    """Update the shared BackgroundJob only if this execution still owns it."""
    token=str(execution_token or '').strip()
    if not token:
        return None
    with transaction.atomic():
        job=BackgroundJob.objects.select_for_update().get(pk=job_id)
        existing=dict(job.result or {}) if isinstance(job.result,dict) else {}
        if str(existing.get('execution_token') or '') != token:
            return None
        if result is not None:
            merged=dict(result)
            # Preserve user skip requests that may have landed while the AI call ran.
            merged['skip_current_ids']=_clean_hidden_lead_reassessment_ids(
                list(existing.get('skip_current_ids') or [])+list(merged.get('skip_current_ids') or []))
            merged['execution_token']=token
            merged.setdefault('pass_id',existing.get('pass_id'))
            merged.setdefault('hidden_lead_minibrowser_reassessment',True)
            job.result=merged
        if progress is not None:
            job.progress=max(0,min(100,int(progress)))
        if message is not None:
            job.message=str(message)[:500]
        if status is not None:
            job.status=status
        if error is not None:
            job.error=str(error)[:4000]
        if finished:
            job.finished_at=timezone.now()
        fields=[]
        if result is not None: fields.append('result')
        if progress is not None: fields.append('progress')
        if message is not None: fields.append('message')
        if status is not None: fields.append('status')
        if error is not None: fields.append('error')
        if finished: fields.append('finished_at')
        if fields:
            job.save(update_fields=fields)
        return job


def _dispatch_hidden_lead_reassessment_job(job_or_id, settings_row, *, reason='scheduler'):
    """Dispatch/re-dispatch the same durable pass with a fresh single-owner token."""
    job_id=int(getattr(job_or_id,'pk',job_or_id))
    now=timezone.now(); token=uuid.uuid4().hex
    with transaction.atomic():
        ps=PortalSettings.objects.select_for_update().get(pk=getattr(settings_row,'pk',1) or 1)
        job=BackgroundJob.objects.select_for_update().get(pk=job_id)
        state=dict(ps.focus_taxonomy_state or {})
        pass_state=state.get(HIDDEN_LEAD_REASSESSMENT_PASS_KEY)
        if not isinstance(pass_state,dict):
            pass_state={}
        if str(pass_state.get('status') or '').lower()=='completed':
            return None
        pass_state.update({
            'schema':HIDDEN_LEAD_REASSESSMENT_SCHEMA,
            'release':HIDDEN_LEAD_REASSESSMENT_RELEASE,
            'status':'queued',
            'execution_token':token,
            'execution_job_id':job_id,
            'execution_task_id':'',
            'execution_dispatched_at':now.isoformat(),
            'lease_expires_at':(now+timedelta(seconds=HIDDEN_LEAD_REASSESSMENT_QUEUE_RECOVERY_SECONDS)).isoformat(),
            'updated_at':now.isoformat(),
        })
        pass_state.pop('current_item',None)
        if reason!='initial':
            pass_state['recovery_count']=int(pass_state.get('recovery_count') or 0)+1
            pass_state['last_recovery_reason']=reason
        state[HIDDEN_LEAD_REASSESSMENT_PASS_KEY]=pass_state
        state['hidden_lead_minibrowser_reassessment_pending']=True
        ps.focus_taxonomy_state=state
        ps.save(update_fields=['focus_taxonomy_state','updated_at'])
        result=dict(job.result or {}) if isinstance(job.result,dict) else {}
        result.update({
            'hidden_lead_minibrowser_reassessment':True,
            'release':HIDDEN_LEAD_REASSESSMENT_RELEASE,
            'schema':HIDDEN_LEAD_REASSESSMENT_SCHEMA,
            'pass_id':pass_state.get('pass_id'),
            'execution_token':token,
            'execution_dispatched_at':now.isoformat(),
            'dispatch_reason':reason,
            'selected':int(pass_state.get('target_count') or pass_state.get('selected') or result.get('selected') or 0),
            'processed':int(pass_state.get('processed') or 0),
            'skip_current_ids':_clean_hidden_lead_reassessment_ids(list(pass_state.get('skip_current_ids') or [])+list(result.get('skip_current_ids') or [])),
            'deletions_deferred_until_completed':True,
            'protected_outreach_not_recycled':True,
            'skip_current_available':True,
            'resumable_pass':True,
        })
        result.pop('current_item',None); result.pop('current_lead_id',None)
        job.status='queued'; job.finished_at=None; job.error=''; job.label=HIDDEN_LEAD_REASSESSMENT_LABEL
        job.message='Queued resumable Hidden Leads reassessment'
        selected=max(1,int(result.get('selected') or 0)); processed=int(result.get('processed') or 0)
        job.progress=min(99,int((processed/selected)*100))
        job.result=result
        job.save(update_fields=['status','finished_at','error','label','message','progress','result'])
    try:
        task=hidden_lead_minibrowser_reassessment_job.delay(job_id,token)
        task_id=str(task.id or '')
        with transaction.atomic():
            ps=PortalSettings.objects.select_for_update().get(pk=getattr(settings_row,'pk',1) or 1)
            job=BackgroundJob.objects.select_for_update().get(pk=job_id)
            state=dict(ps.focus_taxonomy_state or {})
            pass_state=state.get(HIDDEN_LEAD_REASSESSMENT_PASS_KEY)
            result=dict(job.result or {}) if isinstance(job.result,dict) else {}
            if isinstance(pass_state,dict) and str(pass_state.get('execution_token') or '')==token and str(result.get('execution_token') or '')==token:
                pass_state['execution_task_id']=task_id
                pass_state['updated_at']=timezone.now().isoformat()
                state[HIDDEN_LEAD_REASSESSMENT_PASS_KEY]=pass_state
                ps.focus_taxonomy_state=state
                ps.save(update_fields=['focus_taxonomy_state','updated_at'])
                result['execution_task_id']=task_id
                job.celery_task_id=task_id; job.result=result
                job.save(update_fields=['celery_task_id','result'])
        return job_id
    except Exception as exc:
        with transaction.atomic():
            ps=PortalSettings.objects.select_for_update().get(pk=getattr(settings_row,'pk',1) or 1)
            job=BackgroundJob.objects.select_for_update().get(pk=job_id)
            state=dict(ps.focus_taxonomy_state or {})
            pass_state=state.get(HIDDEN_LEAD_REASSESSMENT_PASS_KEY)
            if isinstance(pass_state,dict) and str(pass_state.get('execution_token') or '')==token:
                pass_state['dispatch_error']=str(exc)[:500]
                pass_state['lease_expires_at']=(timezone.now()+timedelta(seconds=30)).isoformat()
                state[HIDDEN_LEAD_REASSESSMENT_PASS_KEY]=pass_state
                ps.focus_taxonomy_state=state
                ps.save(update_fields=['focus_taxonomy_state','updated_at'])
            result=dict(job.result or {}) if isinstance(job.result,dict) else {}
            if str(result.get('execution_token') or '')==token:
                result['dispatch_error']=str(exc)[:500]
                job.result=result; job.message='Queued — waiting to redispatch Hidden Leads reassessment'
                job.save(update_fields=['result','message'])
        return job_id


@shared_task(bind=True)
def hidden_lead_minibrowser_reassessment_job(self, job_id, execution_token=''):
    """Durable single-owner reassessment of existing Hidden Leads.

    Every completed lead writes per-lead state before the monotonic pass cursor advances.
    A container restart or lost queue delivery therefore resumes from the committed set;
    a delayed old worker cannot write after a replacement execution acquires the lease.
    """
    initial_job=BackgroundJob.objects.get(pk=job_id)
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    ps, pass_state, execution_token=_claim_hidden_lead_reassessment_execution(
        ps,job_id,execution_token,celery_task_id=str(getattr(self.request,'id','') or ''))
    if not ps or not execution_token:
        return {'hidden_lead_minibrowser_reassessment':True,'superseded_execution':True,'job_id':job_id}
    if str((pass_state or {}).get('status') or '').lower()=='completed':
        return {'hidden_lead_minibrowser_reassessment':True,'already_completed':True,'job_id':job_id}
    pass_id=str((pass_state or {}).get('pass_id') or '')
    target_ids=pass_state.get('target_ids') if isinstance(pass_state,dict) else []
    if not isinstance(target_ids,list) or not target_ids:
        target_ids=_hidden_lead_reassessment_target_ids()
    # Keep the pass denominator stable across restarts. Targets that were deleted or
    # otherwise disappeared after the pass began are consumed as completed/missing in
    # the loop rather than silently shrinking 174 to 173 and making progress jump.
    lead_ids=_clean_hidden_lead_reassessment_ids(target_ids)
    total=len(lead_ids)
    previous=dict(initial_job.result or {}) if isinstance(initial_job.result,dict) else {}
    seed=_hidden_lead_reassessment_seed_state(lead_ids)
    completed_ids=set(_clean_hidden_lead_reassessment_ids(list((pass_state or {}).get('completed_ids') or [])+list(seed.get('completed_ids') or [])))
    stats={
        'hidden_lead_minibrowser_reassessment':True,
        'release':HIDDEN_LEAD_REASSESSMENT_RELEASE,
        'schema':HIDDEN_LEAD_REASSESSMENT_SCHEMA,
        'pass_id':pass_id,
        'execution_token':execution_token,
        'selected':total,
        'processed':max(int(seed.get('processed') or 0),int((pass_state or {}).get('processed') or 0),len(completed_ids)),
        'admitted':max(int(seed.get('admitted') or 0),int((pass_state or {}).get('admitted') or 0)),
        'review':max(int(seed.get('review') or 0),int((pass_state or {}).get('review') or 0)),
        'rejected':max(int(seed.get('rejected') or 0),int((pass_state or {}).get('rejected') or 0)),
        'protected':max(int(seed.get('protected') or 0),int((pass_state or {}).get('protected') or 0)),
        'recycled':int((pass_state or {}).get('recycled') or 0),
        'failed':max(int(seed.get('failed') or 0),int((pass_state or {}).get('failed') or 0)),
        'timed_out':max(int(seed.get('timed_out') or 0),int((pass_state or {}).get('timed_out') or 0)),
        'skipped_current':max(int(seed.get('skipped_current') or 0),int((pass_state or {}).get('skipped_current') or 0)),
        'completed_ids':sorted(completed_ids),
        'deletions_deferred_until_completed':True,
        'protected_outreach_not_recycled':True,
        'pending_recycle_ids':_clean_hidden_lead_reassessment_ids(list((pass_state or {}).get('pending_recycle_ids') or [])+list(seed.get('pending_recycle_ids') or [])),
        'skip_current_ids':_clean_hidden_lead_reassessment_ids(list((pass_state or {}).get('skip_current_ids') or [])+list(previous.get('skip_current_ids') or previous.get('skipped_current_ids') or [])),
        'items':[],
    }
    pending_recycle=list(stats.get('pending_recycle_ids') or [])
    if total==0:
        saved=_save_hidden_lead_reassessment_pass(ps,status='completed',stats=stats,clear_current=True,execution_token=execution_token)
        if saved is None:
            return {'hidden_lead_minibrowser_reassessment':True,'superseded_execution':True,'job_id':job_id}
        stats['recycled']=int(saved.get('recycled') or 0)
        _update_hidden_lead_reassessment_job(job_id,execution_token,progress=100,message='Existing Hidden Leads reassessment complete · no active leads',result=stats,status='completed',error='',finished=True)
        return stats
    saved=_save_hidden_lead_reassessment_pass(ps,status='running',stats=stats,clear_current=True,execution_token=execution_token)
    if saved is None:
        return {'hidden_lead_minibrowser_reassessment':True,'superseded_execution':True,'job_id':job_id}
    _update_hidden_lead_reassessment_job(
        job_id,execution_token,
        progress=min(99,int((stats['processed']/max(1,total))*100)),
        message=f'Reassessing existing Hidden Leads · {stats["processed"]}/{total} · resuming durable pass',
        result={k:v for k,v in stats.items() if k!='items'},status='running',error='')
    try:
        for lead_id in lead_ids:
            if lead_id in completed_ids:
                continue
            if not _hidden_lead_reassessment_lease_owned(execution_token,pass_id=pass_id):
                return {'hidden_lead_minibrowser_reassessment':True,'superseded_execution':True,'processed':stats['processed'],'job_id':job_id}
            job=BackgroundJob.objects.get(pk=job_id)
            latest_result=dict(job.result or {}) if isinstance(job.result,dict) else {}
            if str(latest_result.get('execution_token') or '')!=execution_token:
                return {'hidden_lead_minibrowser_reassessment':True,'superseded_execution':True,'processed':stats['processed'],'job_id':job_id}
            for sid in latest_result.get('skip_current_ids') or []:
                if sid not in stats['skip_current_ids']:
                    stats['skip_current_ids'].append(sid)
            if job.status=='stopped':
                stats['stopped']=True; stats['unprocessed']=max(0,total-stats['processed'])
                _save_hidden_lead_reassessment_pass(ps,status='stopped',stats=stats,clear_current=True,execution_token=execution_token)
                _update_hidden_lead_reassessment_job(job_id,execution_token,result=stats)
                return stats
            lead=CompanyLead.objects.filter(pk=lead_id,user_deleted=False,deleted_at__isnull=True).first()
            if not lead:
                stats['processed']+=1
                completed_ids.add(lead_id); stats['completed_ids'].append(lead_id)
                if _save_hidden_lead_reassessment_pass(ps,status='running',stats=stats,clear_current=True,execution_token=execution_token) is None:
                    return {'hidden_lead_minibrowser_reassessment':True,'superseded_execution':True,'processed':stats['processed'],'job_id':job_id}
                continue
            existing_item=_hidden_lead_existing_reassessment_item(lead)
            if existing_item:
                if lead_id not in completed_ids:
                    completed_ids.add(lead_id); stats['completed_ids'].append(lead_id); stats['processed']+=1
                    stat=str(existing_item.get('stat') or 'review')
                    stats[stat if stat in stats else 'review']=int(stats.get(stat if stat in stats else 'review') or 0)+1
                    if existing_item.get('timed_out'): stats['timed_out']=int(stats.get('timed_out') or 0)+1
                    if existing_item.get('skipped_current'): stats['skipped_current']=int(stats.get('skipped_current') or 0)+1
                    if existing_item.get('pending_recycle') and lead.pk not in pending_recycle: pending_recycle.append(lead.pk)
                stats['pending_recycle_ids']=pending_recycle[:]
                if _save_hidden_lead_reassessment_pass(ps,status='running',stats=stats,clear_current=True,execution_token=execution_token) is None:
                    return {'hidden_lead_minibrowser_reassessment':True,'superseded_execution':True,'processed':stats['processed'],'job_id':job_id}
                continue
            if lead_id in set(stats.get('skip_current_ids') or []):
                if not _hidden_lead_reassessment_lease_owned(execution_token,pass_id=pass_id):
                    return {'hidden_lead_minibrowser_reassessment':True,'superseded_execution':True,'processed':stats['processed'],'job_id':job_id}
                now=timezone.now(); protected=_hidden_lead_has_outreach(lead)
                lead_state=dict(lead.ai_state or {})
                lead_state['hidden_lead_minibrowser_reassessment']={
                    'decision':'review','review':True,'admit':False,'lead_score':int(lead.score or 0),
                    'reason':'Skipped by user while reassessment was in progress; lead left unchanged.',
                    'skipped_current':True,'applied_decision':'skipped_current_left_unchanged','at':now.isoformat(),
                    'release':HIDDEN_LEAD_REASSESSMENT_RELEASE,'schema':HIDDEN_LEAD_REASSESSMENT_SCHEMA,'pass_id':pass_id,
                    'source':'existing_hidden_lead_minibrowser_reassessment_skipped_current','protected_outreach':protected,
                }
                lead.ai_state=lead_state; lead.save(update_fields=['ai_state','updated_at'])
                stats['processed']+=1; stats['review']+=1; stats['skipped_current']=int(stats.get('skipped_current') or 0)+1
                completed_ids.add(lead_id); stats['completed_ids'].append(lead_id)
                stats['items'].append({'id':lead.pk,'company':lead.company[:220],'decision':'review','applied_decision':'skipped_current_left_unchanged','lead_score':int(lead.score or 0),'protected_outreach':protected,'timed_out':False,'reason':'Skipped by user while reassessment was in progress; lead left unchanged.','pages':[],'rejection_risks':[]})
                progress=min(99,int((stats['processed']/max(1,total))*100))
                if _save_hidden_lead_reassessment_pass(ps,status='running',stats=stats,clear_current=True,execution_token=execution_token) is None:
                    return {'hidden_lead_minibrowser_reassessment':True,'superseded_execution':True,'processed':stats['processed'],'job_id':job_id}
                _update_hidden_lead_reassessment_job(job_id,execution_token,progress=progress,message=f'Reassessing existing Hidden Leads · {stats["processed"]}/{total} · skipped current lead',result={k:v for k,v in stats.items() if k!='items'})
                _yield_after_reassessment_item(); continue
            protected=_hidden_lead_has_outreach(lead)
            source_url=str(lead.target_url or lead.source_url or lead.search_url or '').strip()
            index=min(total,stats['processed']+1)
            item_started_at=timezone.now(); item_deadline_at=item_started_at+timedelta(seconds=HIDDEN_LEAD_REASSESSMENT_PER_LEAD_SECONDS+30)
            current_item={'id':lead.pk,'company':lead.company[:220],'index':index,'total':total,'state':'running','started_at':item_started_at.isoformat(),'deadline_at':item_deadline_at.isoformat()}
            live={k:v for k,v in stats.items() if k!='items'}; live['current_item']=current_item; live['current_lead_id']=lead.pk
            if _save_hidden_lead_reassessment_pass(ps,status='running',stats=stats,current_item=current_item,execution_token=execution_token) is None:
                return {'hidden_lead_minibrowser_reassessment':True,'superseded_execution':True,'processed':stats['processed'],'job_id':job_id}
            if _update_hidden_lead_reassessment_job(job_id,execution_token,progress=min(99,int(((index-1)/max(1,total))*100)),message=f'Reassessing existing Hidden Leads · {index}/{total} · {lead.company[:80]}',result=live) is None:
                return {'hidden_lead_minibrowser_reassessment':True,'superseded_execution':True,'processed':stats['processed'],'job_id':job_id}
            if not source_url:
                review={'decision':'review','lead_score':int(lead.score or 0),'reason':'No source URL available for minibrowser reassessment.','admit':False,'review':True,'cutoff':75}
            else:
                try:
                    campaign=_lead_reassessment_campaign(lead)
                    with scoped_usage_context(
                        operation='hidden_lead_reassessment', subject_type='hidden_lead', subject_id=str(lead.pk),
                        subject_label=str(lead.company or '')[:220], local_ai_low_priority=True,
                        maintenance_hidden_lead_reassessment=True, disable_ai_fallback=True):
                        review=hidden_lead_minibrowser_admission(
                            campaign,source_url,company=lead.company,initial_title=lead.company,
                            initial_text='\n'.join(str(x or '') for x in (lead.summary,lead.match_summary,lead.evidence,lead.company_intel))[:18000],
                            evidence='\n'.join(str(x or '') for x in (lead.contact_url,lead.contact_email,lead.country))[:4000],
                            max_pages=6,deadline_seconds=HIDDEN_LEAD_REASSESSMENT_PER_LEAD_SECONDS,page_timeout=HIDDEN_LEAD_REASSESSMENT_PAGE_TIMEOUT)
                except LocalAILaneBusy as exc:
                    review={
                        'decision':'review','lead_score':int(lead.score or 0),
                        'reason':f'Automatic reassessment deferred because Local AI was busy: {str(exc)[:360]}',
                        'admit':False,'review':True,'cutoff':75,'timeout':True,'timed_out':True,
                        'local_ai_deferred':True,
                    }
                except Exception as exc:
                    timed_out_exc='timeout' in str(exc).lower() or 'timed out' in str(exc).lower()
                    if not timed_out_exc:
                        stats['failed']+=1
                    review={'decision':'review','lead_score':int(lead.score or 0),'reason':f'Minibrowser reassessment failed or timed out: {str(exc)[:400]}','admit':False,'review':True,'cutoff':75,'timeout':timed_out_exc,'timed_out':timed_out_exc}
            # A replacement execution may have been dispatched while this expensive call ran.
            if not _hidden_lead_reassessment_lease_owned(execution_token,pass_id=pass_id):
                return {'hidden_lead_minibrowser_reassessment':True,'superseded_execution':True,'processed':stats['processed'],'job_id':job_id}
            job=BackgroundJob.objects.get(pk=job_id); latest_result=dict(job.result or {}) if isinstance(job.result,dict) else {}
            if str(latest_result.get('execution_token') or '')!=execution_token:
                return {'hidden_lead_minibrowser_reassessment':True,'superseded_execution':True,'processed':stats['processed'],'job_id':job_id}
            latest_skip_ids=set(latest_result.get('skip_current_ids') or [])
            if lead.pk in latest_skip_ids:
                now=timezone.now(); lead_state=dict(lead.ai_state or {})
                lead_state['hidden_lead_minibrowser_reassessment']={
                    'decision':'review','review':True,'admit':False,'lead_score':int(lead.score or 0),
                    'reason':'Skipped by user while reassessment was in progress; lead left unchanged.',
                    'skipped_current':True,'applied_decision':'skipped_current_left_unchanged','at':now.isoformat(),
                    'release':HIDDEN_LEAD_REASSESSMENT_RELEASE,'schema':HIDDEN_LEAD_REASSESSMENT_SCHEMA,'pass_id':pass_id,
                    'source':'existing_hidden_lead_minibrowser_reassessment_skipped_current','protected_outreach':protected,
                }
                lead.ai_state=lead_state; lead.save(update_fields=['ai_state','updated_at'])
                stats['processed']+=1; stats['review']+=1; stats['skipped_current']=int(stats.get('skipped_current') or 0)+1
                completed_ids.add(lead.pk); stats['completed_ids'].append(lead.pk)
                stats['items'].append({'id':lead.pk,'company':lead.company[:220],'decision':'review','applied_decision':'skipped_current_left_unchanged','lead_score':int(lead.score or 0),'protected_outreach':protected,'timed_out':False,'reason':'Skipped by user while reassessment was in progress; lead left unchanged.','pages':[],'rejection_risks':[]})
                if _save_hidden_lead_reassessment_pass(ps,status='running',stats=stats,clear_current=True,execution_token=execution_token) is None:
                    return {'hidden_lead_minibrowser_reassessment':True,'superseded_execution':True,'processed':stats['processed'],'job_id':job_id}
                _update_hidden_lead_reassessment_job(job_id,execution_token,progress=min(99,int((stats['processed']/max(1,total))*100)),message=f'Reassessing existing Hidden Leads · {stats["processed"]}/{total} · skipped current lead',result={k:v for k,v in stats.items() if k!='items'})
                continue
            decision=str(review.get('decision') or '').lower(); score=int(review.get('lead_score') or 0)
            timed_out=bool(review.get('timeout') or review.get('timed_out') or 'timeout' in str(review.get('reason') or '').lower())
            if timed_out:
                stats['timed_out']+=1; decision='review'
            now=timezone.now(); state=dict(lead.ai_state or {})
            stored_review={k:v for k,v in dict(review or {}).items() if k!='text'}
            stored_review.update({'at':now.isoformat(),'release':HIDDEN_LEAD_REASSESSMENT_RELEASE,'schema':HIDDEN_LEAD_REASSESSMENT_SCHEMA,'pass_id':pass_id,'source':'existing_hidden_lead_minibrowser_reassessment_bounded','protected_outreach':protected})
            state['hidden_lead_minibrowser_reassessment']=stored_review
            update_fields=['ai_state','updated_at']; lead.ai_state=state
            if review.get('company_name') and str(review.get('company_name')).strip():
                lead.company=str(review.get('company_name')).strip()[:220]; update_fields.append('company')
            if review.get('summary') and decision in {'admit','review'}:
                lead.summary=strip_hidden_lead_evidence_markers(review.get('summary'))[:1600]; update_fields.append('summary')
            if review.get('why_relevant') and decision in {'admit','review'}:
                lead.match_summary=str(review.get('why_relevant')).strip()[:2200]; update_fields.append('match_summary')
            if review.get('contact_path') and not (lead.contact_url or lead.contact_email):
                path=str(review.get('contact_path') or '').strip()
                if path.startswith(('http://','https://')):
                    lead.contact_url=path[:1000]; update_fields.append('contact_url')
            try:
                lead.score=max(0,min(100,score)); update_fields.append('score')
            except Exception:
                pass
            lead.save(update_fields=sorted(set(update_fields)))
            if decision=='admit' and bool(review.get('admit')):
                stats['admitted']+=1; applied='admit'
            elif decision=='reject' and not timed_out:
                stats['rejected']+=1
                if protected:
                    stats['protected']+=1; applied='protected'
                else:
                    if lead.pk not in pending_recycle: pending_recycle.append(lead.pk)
                    applied='pending_recycle_after_completion'
            else:
                stats['review']+=1; applied='timeout_review' if timed_out else 'review'
            stats['processed']+=1
            stats['items'].append({'id':lead.pk,'company':lead.company[:220],'decision':decision or 'review','applied_decision':applied,'lead_score':score,'protected_outreach':protected,'timed_out':timed_out,'reason':str(review.get('reason_to_contact') or review.get('why_relevant') or review.get('reason') or '')[:700],'pages':(review.get('pages') or review.get('evidence_urls') or [])[:8],'rejection_risks':(review.get('rejection_risks') or [])[:8]})
            if lead.pk not in completed_ids:
                completed_ids.add(lead.pk); stats['completed_ids'].append(lead.pk)
            stats['pending_recycle_ids']=pending_recycle[:]
            if _save_hidden_lead_reassessment_pass(ps,status='running',stats=stats,clear_current=True,execution_token=execution_token) is None:
                return {'hidden_lead_minibrowser_reassessment':True,'superseded_execution':True,'processed':stats['processed'],'job_id':job_id}
            if _update_hidden_lead_reassessment_job(job_id,execution_token,progress=min(99,int((stats['processed']/max(1,total))*100)),message=f'Reassessing existing Hidden Leads · {stats["processed"]}/{total} · {lead.company[:80]}',result={k:v for k,v in stats.items() if k!='items'}) is None:
                return {'hidden_lead_minibrowser_reassessment':True,'superseded_execution':True,'processed':stats['processed'],'job_id':job_id}
            _yield_after_reassessment_item()
        stats['pending_recycle_ids']=pending_recycle[:]
        saved=_save_hidden_lead_reassessment_pass(ps,status='completed',stats=stats,clear_current=True,execution_token=execution_token,recycle_ids=pending_recycle)
        if saved is None:
            return {'hidden_lead_minibrowser_reassessment':True,'superseded_execution':True,'processed':stats['processed'],'job_id':job_id}
        stats['recycled']=int(saved.get('recycled') or 0); stats['processed']=int(saved.get('processed') or stats['processed'])
        msg=(f'Existing Hidden Leads reassessed · {stats["admitted"]} admitted · {stats["review"]} review'
             f' · {stats["recycled"]} recycled · {stats["protected"]} outreach-protected'
             +(f' · {stats["timed_out"]} timed out' if stats['timed_out'] else '')
             +(f' · {stats.get("skipped_current",0)} skipped' if stats.get('skipped_current') else '')
             +(f' · {stats["failed"]} failed' if stats['failed'] else ''))
        _update_hidden_lead_reassessment_job(job_id,execution_token,progress=100,message=msg,result=stats,status='completed',error='',finished=True)
        return stats
    except Exception as exc:
        stats['fatal_error']=str(exc)[:1000]; stats['pending_recycle_ids']=pending_recycle[:]; stats['recycled']=0
        saved=_save_hidden_lead_reassessment_pass(ps,status='failed',stats=stats,clear_current=True,execution_token=execution_token)
        if saved is not None:
            _update_hidden_lead_reassessment_job(job_id,execution_token,result=stats,status='failed',message='Failed',error=str(exc),finished=True)
        raise


def _queue_hidden_lead_minibrowser_reassessment(settings_row, snapshot=None):
    state=dict(getattr(settings_row,'focus_taxonomy_state',{}) or {})
    pass_state=state.get(HIDDEN_LEAD_REASSESSMENT_PASS_KEY)
    canonical_pending=bool(state.get('hidden_lead_minibrowser_reassessment_pending'))
    legacy_pending=bool(
        state.get('v01119_hidden_lead_minibrowser_reassessment_pending') or
        state.get('v01115_hidden_lead_minibrowser_reassessment_pending') or
        state.get('v01111_hidden_lead_minibrowser_reassessment_pending') or
        state.get('v0119_hidden_lead_minibrowser_reassessment_pending'))
    if not isinstance(pass_state,dict) or not pass_state:
        if not (canonical_pending or legacy_pending):
            return None
        pass_state,state=_ensure_hidden_lead_reassessment_pass(settings_row,force_pending=True)
    status=str(pass_state.get('status') or '').lower()
    if status=='completed':
        if canonical_pending or legacy_pending:
            state=dict(getattr(settings_row,'focus_taxonomy_state',{}) or {})
            state['hidden_lead_minibrowser_reassessment_pending']=False
            for key in ('v01119_hidden_lead_minibrowser_reassessment_pending','v01115_hidden_lead_minibrowser_reassessment_pending','v01111_hidden_lead_minibrowser_reassessment_pending','v0119_hidden_lead_minibrowser_reassessment_pending'):
                state[key]=False
            settings_row.focus_taxonomy_state=state; settings_row.save(update_fields=['focus_taxonomy_state','updated_at'])
        return None
    if status in {'failed','stopped','stale'} or legacy_pending:
        pass_state,state=_ensure_hidden_lead_reassessment_pass(settings_row,force_pending=True)

    active=list(BackgroundJob.objects.filter(
        kind='filter_hidden_leads',status__in=['queued','running'],
        result__hidden_lead_minibrowser_reassessment=True).order_by('-pk'))
    pass_id=str((pass_state or {}).get('pass_id') or '')
    owner_job_id=int((pass_state or {}).get('execution_job_id') or 0)
    def _job_rank(row):
        result=row.result if isinstance(row.result,dict) else {}
        owner=1 if owner_job_id and int(row.pk or 0)==owner_job_id else 0
        matches=1 if pass_id and str(result.get('pass_id') or '')==pass_id else 0
        try: processed=int(result.get('processed') or 0)
        except Exception: processed=0
        return (owner,matches,processed,int(row.progress or 0),int(row.pk or 0))
    existing=max(active,key=_job_rank) if active else None
    if existing:
        now=timezone.now()
        for duplicate in active:
            if duplicate.pk==existing.pk:
                continue
            result=dict(duplicate.result or {}) if isinstance(duplicate.result,dict) else {}
            result['superseded_by_pass_id']=pass_id; result['superseded_by_job_id']=existing.pk
            duplicate.status='stopped'; duplicate.finished_at=now
            duplicate.message='Stopped — duplicate Hidden Lead reassessment worker'; duplicate.result=result
            duplicate.save(update_fields=['status','finished_at','message','result'])
            task_id=str(duplicate.celery_task_id or '')
            if task_id:
                try: current_app.control.revoke(task_id,terminate=True,signal='SIGTERM')
                except Exception: pass
        result=dict(existing.result or {}) if isinstance(existing.result,dict) else {}
        changed=[]
        if str(result.get('pass_id') or '')!=pass_id:
            result['pass_id']=pass_id; result['schema']=HIDDEN_LEAD_REASSESSMENT_SCHEMA; existing.result=result; changed.append('result')
        if existing.label!=HIDDEN_LEAD_REASSESSMENT_LABEL:
            existing.label=HIDDEN_LEAD_REASSESSMENT_LABEL; changed.append('label')
        if changed:
            existing.save(update_fields=changed)
        # Dedicated fast recovery: only when worker inspection is available, the stored
        # task is absent from active/reserved/scheduled/retry ownership, and its short
        # durable dispatch/lease grace has expired.
        snap=snapshot or _celery_worker_snapshot()
        if snap.get('available'):
            settings_row.refresh_from_db(fields=['focus_taxonomy_state'])
            fresh_state=dict(settings_row.focus_taxonomy_state or {})
            fresh_pass=fresh_state.get(HIDDEN_LEAD_REASSESSMENT_PASS_KEY)
            if not isinstance(fresh_pass,dict): fresh_pass={}
            task_id=str(fresh_pass.get('execution_task_id') or existing.celery_task_id or result.get('execution_task_id') or '').strip()
            known=set(snap.get('known_ids') or [])
            lease_until=_parse_hidden_lead_reassessment_dt(fresh_pass.get('lease_expires_at'))
            updated_at=_parse_hidden_lead_reassessment_dt(fresh_pass.get('updated_at'))
            current=fresh_pass.get('current_item') if isinstance(fresh_pass.get('current_item'),dict) else {}
            deadline=_parse_hidden_lead_reassessment_dt(current.get('deadline_at'))
            stale_at=lease_until or deadline or ((updated_at+timedelta(seconds=HIDDEN_LEAD_REASSESSMENT_QUEUE_RECOVERY_SECONDS)) if updated_at else None)
            # With responsive workers, a missing task id is itself unowned. A delayed
            # delivery from an earlier dispatch still cannot write because its token is
            # invalidated before the replacement is queued.
            demonstrably_unowned=(not task_id) or task_id not in known
            # Legacy 0.11.26 queued rows may have no execution-token metadata; fall back
            # to the BackgroundJob Celery id when it exists.
            if not task_id:
                task_id=str(existing.celery_task_id or '').strip()
                demonstrably_unowned=(not task_id) or task_id not in known
            if demonstrably_unowned and stale_at and stale_at <= now:
                return _dispatch_hidden_lead_reassessment_job(existing,settings_row,reason='unowned_worker_recovery')
        return existing.pk

    # Reuse the most advanced failed/stopped automatic row for the same pass when one
    # exists, so recovery does not grow a chain of new jobs after restarts.
    historical=BackgroundJob.objects.filter(kind='filter_hidden_leads',result__hidden_lead_minibrowser_reassessment=True).order_by('-pk')[:50]
    reusable=None
    for row in historical:
        result=row.result if isinstance(row.result,dict) else {}
        if pass_id and str(result.get('pass_id') or '')==pass_id:
            reusable=row; break
    if reusable and reusable.status in {'failed','stopped'}:
        reusable.status='queued'; reusable.finished_at=None; reusable.error=''; reusable.label=HIDDEN_LEAD_REASSESSMENT_LABEL
        reusable.message='Queued resumable Hidden Leads reassessment'; reusable.save(update_fields=['status','finished_at','error','label','message'])
        return _dispatch_hidden_lead_reassessment_job(reusable,settings_row,reason='resume_existing_pass_job')

    target_ids=pass_state.get('target_ids') if isinstance(pass_state,dict) else []
    if not isinstance(target_ids,list) or not target_ids:
        target_ids=_hidden_lead_reassessment_target_ids()
    count=len(target_ids)
    job=BackgroundJob.objects.create(
        kind='filter_hidden_leads',label=HIDDEN_LEAD_REASSESSMENT_LABEL,status='queued',
        message=f'Queued minibrowser reassessment · {int(pass_state.get("processed") or 0)}/{count}',
        result={
            'hidden_lead_minibrowser_reassessment':True,'release':HIDDEN_LEAD_REASSESSMENT_RELEASE,
            'schema':HIDDEN_LEAD_REASSESSMENT_SCHEMA,'pass_id':pass_state.get('pass_id'),'selected':count,
            'processed':int(pass_state.get('processed') or 0),'deletions_deferred_until_completed':True,
            'protected_outreach_not_recycled':True,'skip_current_available':True,'resumable_pass':True,
        })
    return _dispatch_hidden_lead_reassessment_job(job,settings_row,reason='initial')

@shared_task(bind=True)
def country_location_repair_job(self, job_id):
    """One-time 0.11.5 repair of retained Opportunity/Lead/Address Book locations.

    The repair uses deterministic page/source/company evidence only. Candidate operating
    locations and naked AI country guesses are never accepted as location evidence.
    """
    job=BackgroundJob.objects.get(pk=job_id); job.celery_task_id=self.request.id or ''
    _job_start(job,'Repopulating country/location fields from grounded evidence')
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    try:
        last_saved=[0]
        def progress(done,total,stats):
            if done-last_saved[0] < 10 and done < total:
                return
            last_saved[0]=done
            job.progress=min(99,int((done/max(1,total))*100))
            job.message=f'Repopulating country/location fields · {done} / {total}'
            job.result={'country_location_repair':True,'release':'0.11.5','stats':dict(stats or {})}
            job.save(update_fields=['progress','message','result'])
        result=repopulate_country_fields(progress=progress,fetch_pages=True)
        ps.country_repair_version='0.11.5'
        ps.save(update_fields=['country_repair_version','updated_at'])
        _job_done(job,result,'Country/location fields repopulated from grounded evidence')
        return result
    except Exception as exc:
        job.status='failed'; job.error=str(exc)[:4000]; job.message='Country/location repair failed'
        job.finished_at=timezone.now(); job.save(update_fields=['status','error','message','finished_at'])
        raise


def _queue_country_location_repair(settings_row):
    if str(getattr(settings_row,'country_repair_version','') or '')=='0.11.5':
        return None
    label='Rebuild source-readonly location fields for 0.11.5'
    existing=BackgroundJob.objects.filter(kind='other',label=label,status__in=['queued','running']).order_by('-pk').first()
    if existing:
        return existing.pk
    job=BackgroundJob.objects.create(
        kind='other',label=label,status='queued',message='Queued source-readonly location field reconciliation',
        result={'country_location_repair':True,'release':'0.11.5'},
    )
    task=country_location_repair_job.delay(job.pk)
    job.celery_task_id=str(task.id or ''); job.save(update_fields=['celery_task_id'])
    return job.pk

def _delete_old_rows(model, field, cutoff, batch=2000, extra_filter=None):
    qs=model.objects.filter(**{field+'__lt':cutoff})
    if extra_filter:
        qs=qs.filter(**extra_filter)
    deleted=0
    while True:
        ids=list(qs.order_by(field).values_list('pk',flat=True)[:batch])
        if not ids:
            break
        count,_=model.objects.filter(pk__in=ids).delete(); deleted+=int(count or 0)
        if len(ids)<batch:
            break
    return deleted


@shared_task
def retention_cleanup_tick():
    """Daily bounded cleanup of detailed telemetry only; business data survives."""
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    days=max(14,min(180,int(getattr(ps,'detailed_log_retention_days',90) or 90)))
    cutoff=timezone.now()-timedelta(days=days)
    counts={}
    for label,model,field in (
        ('audit',AuditLog,'at'),('usage',UsageMetric,'at'),('resources',ResourceSample,'at'),
        ('ai_requests',AIRequestLog,'at'),('diagnostics',DiagnosticRun,'created_at'),('performance',PerformanceRun,'created_at'),
    ):
        try:
            counts[label]=_delete_old_rows(model,field,cutoff)
        except Exception as exc:
            counts[label+'_error']=str(exc)[:200]
    try:
        counts['finished_jobs']=_delete_old_rows(BackgroundJob,'finished_at',cutoff,extra_filter={'status__in':['completed','failed','stopped']})
    except Exception as exc:
        counts['finished_jobs_error']=str(exc)[:200]
    counts['retention_days']=days
    # Focus labels are deliberately stable between rare, threshold-triggered full
    # populations. Daily retention cleanup must never merge/rename taxonomy groups.
    return counts


def _celery_worker_snapshot(timeout=0.8):
    """Return task IDs currently owned by responding Celery workers.

    Celery's Redis broker does not expose a useful database-side heartbeat for every
    BackgroundJob. Inspecting active/reserved/scheduled tasks lets ScoutBox distinguish an
    actually owned long-running job from a database row orphaned by a worker/container
    restart. Failure to inspect is treated conservatively by the watchdog below.
    """
    known=set(); workers=set(); states={}
    try:
        inspector=current_app.control.inspect(timeout=float(timeout))
        for state_name,getter in (('active',inspector.active),('reserved',inspector.reserved),('scheduled',inspector.scheduled)):
            payload=getter() or {}
            if not isinstance(payload,dict):
                continue
            workers.update(str(name) for name in payload.keys())
            states[state_name]=sum(len(rows or []) for rows in payload.values())
            for rows in payload.values():
                for row in rows or []:
                    request=(row or {}).get('request') if isinstance(row,dict) else None
                    request=request if isinstance(request,dict) else (row if isinstance(row,dict) else {})
                    task_id=str(request.get('id') or '').strip()
                    if task_id:
                        known.add(task_id)
    except Exception:
        return {'known_ids':set(),'workers':set(),'states':{},'available':False}
    return {'known_ids':known,'workers':workers,'states':states,'available':bool(workers)}


def _latest_graceful_service_stop(now=None):
    """Return the latest lifecycle stop only when it is the newest lifecycle event.

    During a full ``restart_scout_box.sh`` upgrade, Docker stops every application
    worker before the new web bootstrap begins. The web entrypoint records that stop in
    AuditLog while PostgreSQL is still available. At the next bootstrap there is no
    responding Celery worker yet by design, so this lifecycle boundary is stronger
    evidence of interruption than a missing ``inspect`` response alone.
    """
    now=now or timezone.now()
    try:
        event=AuditLog.objects.filter(
            action__in=['service_started','service_stopped'],at__lte=now
        ).order_by('-at').first()
    except Exception:
        return None
    return event if event is not None and event.action=='service_stopped' else None


def _activity_predates_restart(last_activity, stop_at, tolerance_seconds=30):
    """True when a task's last activity belongs to the stack that was stopped."""
    if not last_activity or not stop_at:
        return False
    try:
        if timezone.is_naive(last_activity):
            last_activity=timezone.make_aware(last_activity,timezone.get_current_timezone())
        if timezone.is_naive(stop_at):
            stop_at=timezone.make_aware(stop_at,timezone.get_current_timezone())
        return last_activity <= stop_at + timedelta(seconds=max(0,int(tolerance_seconds or 0)))
    except Exception:
        return False


def _clear_restart_local_ai_lanes():
    """Delete only Local-AI mutexes proven stale by a full service restart."""
    result={'deleted':0,'error':''}
    try:
        import redis
        client=redis.Redis.from_url(settings.CELERY_BROKER_URL,socket_connect_timeout=2,socket_timeout=2)
        keys=list(client.scan_iter(match='scoutbox:local-ai:lane:*',count=100))
        result['deleted']=int(client.delete(*keys) or 0) if keys else 0
    except Exception as exc:
        result['error']=str(exc)[:300]
    return result


def _background_job_runtime_limit_minutes(job):
    """Conservative stale limits; provider timeouts are much shorter than these."""
    defaults={
        'chatbot':30,
        # AI-backed background jobs should finish or fail fast. Provider requests are
        # hard-capped separately, so a 20-minute running row is almost always an
        # interrupted worker rather than useful work.
        'company_research':20,
        'summarize':20,
        'cold_draft':45,
        'translate':45,
        'enrich':60,
        'prepare':90,
        'hidden_scan':60,
        'mail_scan':60,
        'import_text':60,
        'import_document':90,
        'diagnostic':90,
        'performance':240,
        'other':120,
    }
    override=int(os.environ.get('SCOUTBOX_BACKGROUND_JOB_STALE_MINUTES','0') or 0)
    return max(15,min(480,override or defaults.get(str(job.kind or ''),90)))


def _expire_stale_background_jobs(now, startup=False, snapshot=None):
    """Finalize BackgroundJob rows whose Celery task is no longer owned by a worker.

    Normal watchdog operation stays deliberately conservative because Celery inspect can
    miss a live task. Startup has one stronger signal: when the newest lifecycle event is
    a graceful ``service_stopped`` and no application worker answers yet, any job that was
    already running at that stop boundary belonged to the old stack and cannot still own
    a worker. Those rows are finalized immediately instead of displaying a stale
    hourglass for 20-90 minutes after every upgrade.
    """
    snapshot=snapshot or _celery_worker_snapshot(); known=snapshot['known_ids']
    failed_running=[]; failed_queued=[]
    restart_event=_latest_graceful_service_stop(now) if startup and not snapshot['available'] else None
    restart_stop_at=getattr(restart_event,'at',None)
    # If no worker answered inspection without a known restart boundary, do not infer that
    # a recently running task died. Very old rows can still be retired normally.
    no_worker_running_floor=30 if startup else 180
    rows=BackgroundJob.objects.filter(status='running').order_by('started_at','created_at')[:500]
    for job in rows:
        if isinstance(job.result,dict) and job.result.get('hidden_lead_minibrowser_reassessment'):
            # This pass has its own short, ownership-aware lease recovery below; the
            # generic watchdog must not fail the canonical row before it can be reused.
            continue
        started=job.started_at or job.created_at
        if not started:
            continue
        age_minutes=max(0,int((now-started).total_seconds()//60))
        task_id=str(job.celery_task_id or '').strip()
        if task_id and task_id in known:
            continue
        interrupted_by_restart=bool(
            restart_stop_at and _activity_predates_restart(started,restart_stop_at)
        )
        limit=_background_job_runtime_limit_minutes(job)
        if not snapshot['available'] and not interrupted_by_restart:
            limit=max(limit,no_worker_running_floor)
        if not interrupted_by_restart and age_minutes < limit:
            continue
        if interrupted_by_restart:
            reason='Background task was interrupted by the ScoutBox service restart.'
            message='Interrupted by ScoutBox restart'
            state='interrupted_service_restart'
        else:
            reason=f'Background task lost its worker ownership after {age_minutes} minutes.'
            message='Interrupted — worker task no longer active'
            state='interrupted_worker_task'
        result=dict(job.result or {})
        result.update({'state':state,'watchdog':'background_job','watchdog_at':now.isoformat(),
                       'watchdog_age_minutes':age_minutes,'celery_task_id':task_id})
        if interrupted_by_restart:
            result.update({'service_restart_interrupted':True,'service_stopped_at':restart_stop_at.isoformat()})
        updated=BackgroundJob.objects.filter(pk=job.pk,status='running').update(
            status='failed',finished_at=now,progress=100,message=message,error=reason,result=result)
        if not updated:
            continue
        failed_running.append(job.pk)
        # QuerySet.update bypasses BackgroundJob.save(), which owns the AI Requests
        # placeholder projection. Re-save the finalized row so the hourglass changes to
        # Failed immediately instead of leaving a stale queued/running AI Request.
        try:
            finalized=BackgroundJob.objects.get(pk=job.pk)
            finalized.save(update_fields=['status','finished_at','progress','message','error','result'])
        except Exception:
            pass
        if task_id:
            try: current_app.control.revoke(task_id,terminate=False)
            except Exception: pass

    queued_limit=max(30,min(480,int(os.environ.get('SCOUTBOX_BACKGROUND_QUEUE_STALE_MINUTES','120') or 120)))
    # Only expire queued rows when at least one worker is responding; otherwise the queue
    # may simply be unavailable during a restart. Scheduled retries are present in `known`.
    if snapshot['available']:
        cutoff=now-timedelta(minutes=queued_limit)
        for job in BackgroundJob.objects.filter(status='queued',created_at__lt=cutoff).order_by('created_at')[:500]:
            if isinstance(job.result,dict) and job.result.get('hidden_lead_minibrowser_reassessment'):
                # Dedicated reassessment recovery redispatches this same row after a
                # short ownership grace instead of expiring it after 120 minutes.
                continue
            task_id=str(job.celery_task_id or '').strip()
            if task_id and task_id in known:
                continue
            result=dict(job.result or {})
            last_wait=_parse_aware_datetime(result.get('last_wait_at'))
            if last_wait and now-last_wait < timedelta(minutes=queued_limit):
                continue
            age_minutes=max(0,int((now-job.created_at).total_seconds()//60))
            reason=f'Background task remained queued without worker ownership for {age_minutes} minutes.'
            result.update({'state':'expired_unowned_queue_job','watchdog':'background_job','watchdog_at':now.isoformat(),
                           'watchdog_age_minutes':age_minutes,'celery_task_id':task_id})
            updated=BackgroundJob.objects.filter(pk=job.pk,status='queued').update(
                status='failed',finished_at=now,progress=100,message='Queue expired — task no longer present',error=reason,result=result)
            if not updated:
                continue
            failed_queued.append(job.pk)
            try:
                finalized=BackgroundJob.objects.get(pk=job.pk)
                finalized.save(update_fields=['status','finished_at','progress','message','error','result'])
            except Exception:
                pass
            if task_id:
                try: current_app.control.revoke(task_id,terminate=False)
                except Exception: pass
    return {'workers':sorted(snapshot['workers']),'states':snapshot['states'],'inspection_available':snapshot['available'],
            'running_failed_ids':failed_running,'queued_failed_ids':failed_queued,'queued_limit_minutes':queued_limit}



def _requeue_interrupted_company_research(watchdog_result):
    """Retry company research once after the ownership watchdog finalizes a lost task.

    Recovery is keyed by the researched entity and therefore remains idempotent when
    several scheduler ticks observe the same old failed row.  This is deliberately
    central rather than detail-page driven: opening an Opportunity is never required
    to make a lost company-research task move again.
    """
    ids=list((watchdog_result or {}).get('running_failed_ids') or [])+list((watchdog_result or {}).get('queued_failed_ids') or [])
    if not ids:
        return []
    launched=[]
    for old in BackgroundJob.objects.filter(pk__in=ids,kind='company_research').order_by('pk'):
        old_result=dict(old.result or {})
        if old_result.get('recovery_requeued_job_id'):
            continue
        target=None; task=None; result_lookup=None
        opp_id=old_result.get('opportunity_id'); lead_id=old_result.get('lead_id'); contact_id=old_result.get('contact_id')
        if opp_id and Opportunity.objects.filter(pk=opp_id,user_deleted=False).exists():
            target=('opportunity_id',int(opp_id)); task=company_research_job
        elif lead_id and CompanyLead.objects.filter(pk=lead_id,user_deleted=False).exists():
            target=('lead_id',int(lead_id)); task=lead_company_research_job
        elif contact_id and Contact.objects.filter(pk=contact_id,deleted_at__isnull=True).exists():
            target=('contact_id',int(contact_id)); task=contact_company_research_job
        if not target or not task:
            continue
        key,value=target
        active=BackgroundJob.objects.filter(kind='company_research',status__in=['queued','running'],**{f'result__{key}':value}).exclude(pk=old.pk).order_by('-created_at').first()
        if active:
            old_result['recovery_requeued_job_id']=active.pk; old_result['recovery_reused_existing']=True
            old.result=old_result; old.save(update_fields=['result'])
            continue
        recovery_result={key:value,'phase':'recovery','recovery_of_job_id':old.pk,'auto_recovery':True}
        if key=='lead_id': recovery_result['hidden_lead']=True
        if key=='contact_id': recovery_result['address_book']=True
        job=BackgroundJob.objects.create(kind='company_research',label=(old.label or 'Company research')[:300],message='Queued recovery',result=recovery_result)
        try:
            async_result=task.delay(job.pk,value,'recovery')
            job.celery_task_id=async_result.id or ''; job.save(update_fields=['celery_task_id'])
            old_result['recovery_requeued_job_id']=job.pk; old_result['recovery_requeued_at']=timezone.now().isoformat()
            old.result=old_result; old.save(update_fields=['result'])
            launched.append(job.pk)
        except Exception as exc:
            job.status='failed'; job.finished_at=timezone.now(); job.progress=100; job.message='Recovery queue failed'; job.error=str(exc)[:1000]; job.save(update_fields=['status','finished_at','progress','message','error'])
    return launched


def _campaign_partial_discovery_result(run, now=None):
    """Return persisted discoveries for an interrupted campaign run.

    Opportunities and Hidden Leads are saved incrementally by ``ingest_result``. If a
    worker is interrupted before ``run_campaign`` returns, the old watchdog summary could
    still show zero retained records. This helper reconstructs a conservative partial
    summary from records stamped with the originating ``campaign_run_id`` so the run
    history reflects work that was already safely written.
    """
    now = now or timezone.now()
    result = {}
    try:
        started = run.started_at or run.created_at or now
        opp_ids = list(Opportunity.objects.filter(
            user_deleted=False, suppressed=False, extracted_facts__campaign_run_id=run.pk,
        ).values_list('pk', flat=True)[:2000])
        # Some JSON backends may store the run id as a string; include those rows too.
        if len(opp_ids) < 2000:
            for pk in Opportunity.objects.filter(
                user_deleted=False, suppressed=False, extracted_facts__campaign_run_id=str(run.pk),
            ).values_list('pk', flat=True)[:2000]:
                if pk not in opp_ids:
                    opp_ids.append(pk)
        new_opp = Opportunity.objects.filter(pk__in=opp_ids, first_seen_by_portal__gte=started).count() if opp_ids else 0
        lead_ids = list(CompanyLead.objects.filter(
            user_deleted=False, ai_state___usage__campaign_run_id=run.pk,
        ).values_list('pk', flat=True)[:2000])
        if len(lead_ids) < 2000:
            for pk in CompanyLead.objects.filter(
                user_deleted=False, ai_state___usage__campaign_run_id=str(run.pk),
            ).values_list('pk', flat=True)[:2000]:
                if pk not in lead_ids:
                    lead_ids.append(pk)
        new_leads = CompanyLead.objects.filter(pk__in=lead_ids, created_at__gte=started).count() if lead_ids else 0
        if opp_ids or lead_ids:
            result.update({
                'partial_result_finalized': True,
                'partial_result_reason': 'Campaign worker ended before normal completion; persisted records were reconstructed from campaign_run_id provenance.',
                'partial_finalized_at': now.isoformat(),
                'opportunity_ids': opp_ids,
                'lead_ids': lead_ids,
                'unique': int(new_opp),
                'new_opportunities': int(new_opp),
                'opportunities_found': int(new_opp),
                'rediscovered_opportunities': max(0, len(opp_ids) - int(new_opp)),
                'new_leads': int(new_leads),
                'leads_found': int(new_leads),
                'rediscovered_leads': max(0, len(lead_ids) - int(new_leads)),
            })
    except Exception as exc:
        result.update({'partial_result_error': str(exc)[:300]})
    return result

def _clear_recovery_coordination_keys():
    """Remove only short-lived coordination keys that can outlive a dead worker.

    Celery's broker data is deliberately untouched. These namespaces are ScoutBox-owned
    mutex/pacing keys, so clearing them cannot remove queued tasks or user records.
    """
    patterns=('scoutbox:local-ai:lane:*','scoutbox:search-provider:last:*')
    result={'deleted':0,'patterns':{},'error':''}
    try:
        import redis
        client=redis.Redis.from_url(settings.CELERY_BROKER_URL,socket_connect_timeout=2,socket_timeout=2)
        for pattern in patterns:
            keys=list(client.scan_iter(match=pattern,count=100))
            deleted=int(client.delete(*keys) or 0) if keys else 0
            result['patterns'][pattern]=deleted
            result['deleted']+=deleted
    except Exception as exc:
        result['error']=str(exc)[:300]
    return result


def _recover_campaign_runs_interrupted_by_restart(now=None, snapshot=None):
    """Recover campaign tasks that were cut off by a full ScoutBox stack restart.

    ``restart_scout_box.sh`` performs ``docker compose down`` before rebuilding. A
    campaign task that was already running has normally been acknowledged by Celery, so
    its database row survives while the task itself does not. Historically those rows
    remained ``running`` until the generic 20-minute heartbeat timeout, which also
    blocked replacement campaign scheduling.

    Recovery is intentionally limited to bootstrap conditions where no Celery worker is
    responding *and* the newest lifecycle event is a graceful service stop. A web-only
    restart with still-live workers therefore does not steal their runs. Persisted
    discoveries are reconstructed, the interrupted row is marked coverage-exempt, and an
    equivalent replacement is queued for the new worker generation.
    """
    now=now or timezone.now()
    snapshot=snapshot or _celery_worker_snapshot(timeout=1.2)
    result={
        'inspection_available':bool(snapshot.get('available')),
        'workers':sorted(snapshot.get('workers') or []),
        'service_stopped_at':'',
        'interrupted_ids':[],
        'replacement_run_ids':[],
        'requeue_errors':[],
        'local_ai_locks_cleared':0,
        'local_ai_lock_error':'',
    }
    if snapshot.get('available'):
        result['note']='Workers are responding; restart recovery was not needed.'
        return result
    stop_event=_latest_graceful_service_stop(now)
    if stop_event is None:
        result['note']='No graceful service-stop boundary is available; normal heartbeat watchdog remains authoritative.'
        return result
    stop_at=stop_event.at
    result['service_stopped_at']=stop_at.isoformat()

    lane_cleanup=_clear_restart_local_ai_lanes()
    result['local_ai_locks_cleared']=int(lane_cleanup.get('deleted') or 0)
    result['local_ai_lock_error']=lane_cleanup.get('error') or ''

    rows=list(CampaignRun.objects.select_related('campaign').filter(status='running').order_by('created_at')[:500])
    for run in rows:
        last=run.heartbeat_at or run.started_at or run.created_at
        if not _activity_predates_restart(last,stop_at):
            continue

        original_criteria=copy.deepcopy(run.criteria) if isinstance(run.criteria,dict) else {}
        criteria=copy.deepcopy(original_criteria)
        criteria.update({
            'coverage_exempt':True,
            'interrupted_by_restart':True,
            'retryable':True,
            'restart_interrupted_at':now.isoformat(),
            'service_stopped_at':stop_at.isoformat(),
        })
        partial=_campaign_partial_discovery_result(run,now=now)
        run_result=dict(run.result or {})
        run_result.update(partial)
        run_result.update({
            'stopped_reason':'service_restart_interrupted',
            'service_restart_interrupted':True,
            'service_stopped_at':stop_at.isoformat(),
            'restart_recovery_at':now.isoformat(),
            'previous_stage':run.stage or run.message or '',
            'previous_celery_task_id':str(run.celery_task_id or ''),
        })
        updated=CampaignRun.objects.filter(pk=run.pk,status='running').update(
            status='stopped',finished_at=now,heartbeat_at=now,
            message='Interrupted by ScoutBox restart — recovering',stage='Restart recovery',
            error='',stall_reason='',criteria=criteria,result=run_result)
        if not updated:
            continue
        result['interrupted_ids'].append(run.pk)

        campaign=run.campaign
        if not campaign or not campaign.enabled or getattr(campaign,'deleted_at',None) is not None:
            CampaignRun.objects.filter(pk=run.pk,status='stopped').update(
                message='Interrupted by ScoutBox restart — campaign is no longer enabled')
            continue

        replacement_criteria=copy.deepcopy(original_criteria) if original_criteria else _campaign_criteria(campaign)
        for key in ('worker_id','scoutbox_version','coverage_exempt','interrupted_by_restart','retryable',
                    'restart_interrupted_at','service_stopped_at'):
            replacement_criteria.pop(key,None)
        forum_only=bool(replacement_criteria.get('forum_only') or replacement_criteria.get('run_kind')=='forum_only')
        replacement_criteria['deferred_local_ai']=False
        replacement_criteria['restart_recovery']=True
        replacement_criteria['restart_recovery_of_run_id']=run.pk
        replacement_criteria['restart_recovery_at']=now.isoformat()
        replacement_criteria['forum_only']=forum_only
        replacement_criteria['run_kind']='forum_only' if forum_only else 'primary'
        replacement=CampaignRun.objects.create(
            campaign=campaign,criteria=replacement_criteria,
            message='Queued after ScoutBox restart',stage='Queued')
        try:
            async_result=(run_campaign_job.apply_async(args=[replacement.pk],queue='forum')
                          if forum_only else run_campaign_job.delay(replacement.pk))
            replacement.celery_task_id=async_result.id or ''
            replacement.save(update_fields=['celery_task_id'])
            result['replacement_run_ids'].append(replacement.pk)
            run_result['replacement_run_id']=replacement.pk
            run_result['replacement_celery_task_id']=replacement.celery_task_id
            CampaignRun.objects.filter(pk=run.pk,status='stopped').update(
                message=f'Interrupted by ScoutBox restart — replacement run #{replacement.pk} queued',result=run_result)
        except Exception as exc:
            reason=f'Could not queue restart recovery run: {exc}'[:500]
            CampaignRun.objects.filter(pk=replacement.pk,status='queued').update(
                status='failed',finished_at=timezone.now(),message='Restart recovery queue failed',
                error=reason,stall_reason=reason)
            run_result['restart_requeue_error']=reason
            CampaignRun.objects.filter(pk=run.pk,status='stopped').update(
                message='Interrupted by ScoutBox restart — replacement queue failed',result=run_result)
            result['requeue_errors'].append(reason)

    if result['interrupted_ids'] or result['local_ai_locks_cleared']:
        try:
            AuditLog.objects.create(
                actor='system',action='restart_recovery',
                summary=(f"Recovered {len(result['interrupted_ids'])} campaign run(s) after ScoutBox restart; "
                         f"queued {len(result['replacement_run_ids'])} replacement run(s)."),
                metadata={
                    'service_stopped_at':result['service_stopped_at'],
                    'interrupted_run_ids':result['interrupted_ids'],
                    'replacement_run_ids':result['replacement_run_ids'],
                    'local_ai_locks_cleared':result['local_ai_locks_cleared'],
                    'requeue_errors':result['requeue_errors'],
                },
            )
        except Exception:
            pass
    result['note']='Restart-interrupted campaign rows were finalized immediately and replacements were queued.'
    return result


def recover_stalled_operations_state():
    """Last-resort recovery for persistent in-flight campaign/background state.

    The operation intentionally does not delete discovery/application/contact data. It
    retires current in-flight rows so persistent database state cannot block scheduling,
    revokes their Celery task ids, clears ScoutBox-owned Redis coordination locks, then
    queues one replacement for each affected campaign pass. Hidden Leads scan is the only
    generic BackgroundJob replayed automatically because other job kinds may have external
    side effects and their original task arguments are not always safely reconstructable.
    """
    now=timezone.now()
    active_runs=list(CampaignRun.objects.select_related('campaign').filter(
        status__in=['queued','running','stopping']).order_by('created_at')[:500])
    active_jobs=list(BackgroundJob.objects.filter(status__in=['queued','running']).order_by('created_at')[:500])

    restart_specs={}
    revoked=0
    for run in active_runs:
        run_kind='forum_only' if _run_is_forum_only(run) else 'normal'
        restart_specs[(run.campaign_id,run_kind)]=run
        task_id=str(run.celery_task_id or '').strip()
        if task_id:
            try:
                current_app.control.revoke(task_id,terminate=True,signal='SIGTERM')
                revoked+=1
            except Exception:
                pass
        result=dict(run.result or {})
        result.update(_campaign_partial_discovery_result(run,now=now))
        result.update({
            'stopped_reason':'maintenance_recovery',
            'maintenance_recovery_at':now.isoformat(),
            'previous_status':run.status,
            'previous_stage':run.stage or run.message or '',
            'previous_celery_task_id':task_id,
        })
        CampaignRun.objects.filter(pk=run.pk,status__in=['queued','running','stopping']).update(
            status='stopped',finished_at=now,heartbeat_at=now,
            message='Released by Maintenance recovery',stage='Maintenance recovery',
            error='',stall_reason='',result=result)

    restart_hidden_scan=any(job.kind=='hidden_scan' for job in active_jobs)
    for job in active_jobs:
        task_id=str(job.celery_task_id or '').strip()
        if task_id:
            try:
                current_app.control.revoke(task_id,terminate=True,signal='SIGTERM')
                revoked+=1
            except Exception:
                pass
        result=dict(job.result or {})
        result.update({
            'stopped_reason':'maintenance_recovery',
            'maintenance_recovery_at':now.isoformat(),
            'previous_status':job.status,
            'previous_celery_task_id':task_id,
        })
        updated=BackgroundJob.objects.filter(pk=job.pk,status__in=['queued','running']).update(
            status='stopped',finished_at=now,progress=min(99,max(0,int(job.progress or 0))),
            message='Released by Maintenance recovery',error='',result=result)
        if updated:
            # Run model save hooks once so placeholder AI Request rows are cleaned up.
            try:
                BackgroundJob.objects.get(pk=job.pk).save(update_fields=['status','finished_at','progress','message','error','result'])
            except Exception:
                pass

    coordination=_clear_recovery_coordination_keys()
    replacement_runs=[]; requeue_errors=[]
    for (campaign_id,run_kind), prior in restart_specs.items():
        campaign=Campaign.objects.filter(pk=campaign_id,enabled=True,deleted_at__isnull=True).first()
        if not campaign:
            continue
        criteria=copy.deepcopy(prior.criteria) if isinstance(prior.criteria,dict) and prior.criteria else _campaign_criteria(campaign)
        for key in ('worker_id','scoutbox_version','retryable'):
            criteria.pop(key,None)
        criteria['deferred_local_ai']=False
        if run_kind=='forum_only':
            criteria['forum_only']=True; criteria['run_kind']='forum_only'
        else:
            criteria['forum_only']=False
            criteria['run_kind']='primary'
        new_run=CampaignRun.objects.create(
            campaign=campaign,criteria=criteria,message='Queued by Maintenance recovery',stage='Queued')
        try:
            task=(run_campaign_job.apply_async(args=[new_run.pk],queue='forum') if run_kind=='forum_only' else run_campaign_job.delay(new_run.pk))
            new_run.celery_task_id=task.id or ''
            new_run.save(update_fields=['celery_task_id'])
            replacement_runs.append(new_run.pk)
        except Exception as exc:
            reason=f'Could not queue Maintenance recovery run: {exc}'[:500]
            CampaignRun.objects.filter(pk=new_run.pk,status='queued').update(
                status='failed',finished_at=timezone.now(),message='Maintenance recovery requeue failed',error=reason,stall_reason=reason)
            requeue_errors.append(reason)

    replacement_hidden_scan_id=None
    if restart_hidden_scan:
        new_job=BackgroundJob.objects.create(kind='hidden_scan',label='Hidden Leads scan',message='Queued by Maintenance recovery')
        try:
            task=hidden_market_scan_job.delay(new_job.pk)
            new_job.celery_task_id=task.id or ''
            new_job.save(update_fields=['celery_task_id'])
            replacement_hidden_scan_id=new_job.pk
        except Exception as exc:
            reason=f'Could not queue Hidden Leads recovery scan: {exc}'[:500]
            new_job.status='failed'; new_job.finished_at=timezone.now(); new_job.message='Maintenance recovery requeue failed'; new_job.error=reason
            new_job.save(update_fields=['status','finished_at','message','error'])
            requeue_errors.append(reason)

    return {
        'campaign_runs_released':len(active_runs),
        'background_jobs_released':len(active_jobs),
        'celery_tasks_revoked':revoked,
        'campaign_runs_requeued':len(replacement_runs),
        'replacement_campaign_run_ids':replacement_runs,
        'hidden_scan_requeued':bool(replacement_hidden_scan_id),
        'replacement_hidden_scan_id':replacement_hidden_scan_id,
        'coordination_keys_deleted':int(coordination.get('deleted') or 0),
        'coordination_error':coordination.get('error') or '',
        'requeue_errors':requeue_errors,
    }


def _interrupt_unowned_campaign_runs(now, startup=False, snapshot=None):
    """Annotate missing Celery ownership without killing active campaign runs.

    Celery inspect is advisory only: in the field it can miss long-running discovery
    tasks during provider calls, container load, or control-channel hiccups. Previous
    releases treated a missing inspect entry as proof that the campaign worker died,
    causing false "Campaign worker task is no longer active" failures. From 0.10.55 a
    running CampaignRun is finalized only by the heartbeat stall timeout, not by a
    transient Celery ownership snapshot. Explicit user-stopping runs can still be closed
    after the cancellation grace period.
    """
    snapshot = snapshot or _celery_worker_snapshot()
    known = snapshot['known_ids']
    annotated = []
    stopped = []
    try:
        env_grace = int(os.environ.get('SCOUTBOX_CAMPAIGN_UNOWNED_GRACE_MINUTES', '180') or 180)
    except Exception:
        env_grace = 180
    grace_minutes = max(60, min(720, env_grace if snapshot['available'] else (240 if startup else 360)))
    for run in CampaignRun.objects.filter(status__in=['running','stopping']).order_by('started_at','created_at')[:200]:
        task_id = str(run.celery_task_id or '').strip()
        if task_id and task_id in known:
            if run.stall_reason and 'worker ownership unknown' in str(run.stall_reason).casefold():
                CampaignRun.objects.filter(pk=run.pk,status=run.status).update(stall_reason='')
            continue
        last = run.heartbeat_at or run.started_at or run.created_at
        age_minutes = max(0, int((now-last).total_seconds()//60)) if last else 0
        if run.status == 'stopping':
            # Cooperative stop requests are allowed to close even when the worker is stuck
            # in a blocking external call; _stop_stale_campaign_runs remains the primary
            # cancellation finalizer, but this keeps explicit stops responsive.
            if last and now - last < timedelta(minutes=max(5, min(grace_minutes, 15))):
                continue
            result = dict(run.result or {})
            partial = _campaign_partial_discovery_result(run, now=now)
            result.update(partial)
            result.update({'stopped_reason':'worker_task_stopped','worker_watchdog_at':now.isoformat(),
                           'last_heartbeat_at':last.isoformat() if last else '', 'celery_task_id':task_id,
                           'worker_watchdog_grace_minutes':grace_minutes,
                           'worker_snapshot_available':bool(snapshot.get('available'))})
            updated = CampaignRun.objects.filter(pk=run.pk,status='stopping').update(
                status='stopped', finished_at=now, heartbeat_at=now,
                message='Stopped — worker task ended', error='', stall_reason='', result=result)
            if updated:
                stopped.append(run.pk)
                if task_id:
                    try: current_app.control.revoke(task_id,terminate=False)
                    except Exception: pass
            continue
        # Running rows are not failed solely because inspect omitted the task. Annotate
        # after a long window so diagnostics show the suspicion, then let the database
        # heartbeat/stall path make the final decision if the worker truly died.
        if last and now - last >= timedelta(minutes=grace_minutes):
            reason=f'Campaign worker ownership unknown for {age_minutes} minutes; waiting for heartbeat stall timeout before finalizing.'
            result=dict(run.result or {})
            result.update({'worker_ownership_suspect':True,'worker_watchdog_at':now.isoformat(),
                           'last_heartbeat_at':last.isoformat() if last else '', 'celery_task_id':task_id,
                           'worker_watchdog_grace_minutes':grace_minutes,
                           'worker_snapshot_available':bool(snapshot.get('available'))})
            updated=CampaignRun.objects.filter(pk=run.pk,status='running').update(stall_reason=reason[:500],result=result)
            if updated:
                annotated.append(run.pk)
    return {'inspection_available':snapshot['available'],'workers':sorted(snapshot['workers']),
            'grace_minutes':grace_minutes,'interrupted_ids':[], 'annotated_ids':annotated, 'stopped_ids':stopped,
            'note':'Running campaign rows are no longer failed from Celery inspect alone; stale-heartbeat timeout owns finalization.'}


def _stop_stale_campaign_runs(now, grace_minutes=3):
    """Finalize cooperative stops that are blocked inside a long external request."""
    stopped_ids=[]
    for run in CampaignRun.objects.filter(status='stopping'):
        result=dict(run.result or {})
        raw=result.get('stop_requested_at')
        requested=None
        if raw:
            try: requested=datetime.fromisoformat(str(raw).replace('Z','+00:00'))
            except Exception: requested=None
        if requested is None:
            requested=run.started_at or run.created_at
        if timezone.is_naive(requested):
            requested=timezone.make_aware(requested,timezone.get_current_timezone())
        if now-requested < timedelta(minutes=grace_minutes):
            continue
        result['stopped_reason']='cancellation_watchdog'
        result['stopped_at']=now.isoformat()
        updated=CampaignRun.objects.filter(pk=run.pk,status='stopping').update(
            status='stopped',finished_at=now,message='Stopped after cancellation grace period',result=result)
        if not updated:
            continue
        stopped_ids.append(run.pk)
        if run.celery_task_id:
            try: current_app.control.revoke(run.celery_task_id,terminate=False)
            except Exception: pass
    return stopped_ids


def _expire_stale_queued_campaign_runs(now):
    """Fail CampaignRuns that never reached a worker start.

    A queued row consumes no Local AI capacity and therefore must never block company
    research. It can still block future campaign scheduling, though, so the scheduler
    retires genuinely orphaned queue entries after a bounded window.
    """
    timeout_minutes=max(10,min(240,int(os.environ.get('SCOUTBOX_CAMPAIGN_QUEUE_STALE_MINUTES','30') or 30)))
    cutoff=now-timedelta(minutes=timeout_minutes); failed_ids=[]
    rows=CampaignRun.objects.filter(status='queued',started_at__isnull=True,created_at__lt=cutoff).order_by('created_at')[:100]
    for run in rows:
        age=max(1,int((now-run.created_at).total_seconds()//60))
        reason=f'Campaign remained queued without a worker start for {age} minutes.'
        result=dict(run.result or {})
        result.update({'stopped_reason':'campaign_queue_timeout','queue_timeout_minutes':timeout_minutes,
                       'queued_at':run.created_at.isoformat(),'timeout_reason':reason})
        updated=CampaignRun.objects.filter(pk=run.pk,status='queued',started_at__isnull=True).update(
            status='failed',finished_at=now,message='Campaign queue expired',error=reason,stall_reason=reason,result=result)
        if not updated:
            continue
        failed_ids.append(run.pk)
        if run.celery_task_id:
            try: current_app.control.revoke(run.celery_task_id,terminate=False)
            except Exception: pass
    return {'timeout_minutes':timeout_minutes,'failed_ids':failed_ids}


def _fail_stalled_campaign_runs(now):
    """Warn in UI after idle time and finalize only clearly abandoned campaigns.

    The failure threshold is intentionally conservative. Field diagnostics showed false
    failures while discovery was still doing useful work, especially with slow providers
    and local models. A live worker-level heartbeat updates every few seconds; only a
    long absence of that heartbeat is now considered proof of a dead campaign worker.
    """
    try:
        warn_raw=int(os.environ.get('SCOUTBOX_CAMPAIGN_STALL_WARN_MINUTES','8') or 8)
    except Exception:
        warn_raw=8
    try:
        fail_raw=int(os.environ.get('SCOUTBOX_CAMPAIGN_STALL_FAIL_MINUTES','20') or 20)
    except Exception:
        fail_raw=20
    warn_minutes=max(5, min(180, warn_raw))
    # A dead campaign row blocks the next scheduled discovery pass for that campaign.
    # Keep the finalization threshold below a normal two-hour search window so a lost
    # provider/worker cannot starve Forum browsing for hours, while active workers remain
    # safe because their heartbeat updates independently of progress text.
    fail_minutes=max(warn_minutes+7, max(15, min(1440, fail_raw)))
    failed_ids=[]; warned_ids=[]
    warn_cutoff=now-timedelta(minutes=warn_minutes)
    fail_cutoff=now-timedelta(minutes=fail_minutes)
    warn_text_prefix='No campaign heartbeat for '
    for run in CampaignRun.objects.filter(status='running').filter(Q(heartbeat_at__lt=warn_cutoff) | Q(heartbeat_at__isnull=True,started_at__lt=warn_cutoff)).order_by('started_at','created_at')[:200]:
        last=run.heartbeat_at or run.started_at or run.created_at
        idle=max(1,int((now-last).total_seconds()//60)) if last else warn_minutes
        stage=(run.stage or run.message or 'campaign work')[:120]
        if last and last >= fail_cutoff:
            reason=f'{warn_text_prefix}{idle} minutes during {stage}; still waiting before declaring the worker dead.'
            if str(run.stall_reason or '')[:80] != reason[:80]:
                CampaignRun.objects.filter(pk=run.pk,status='running').update(stall_reason=reason[:500])
            warned_ids.append(run.pk)
            continue
        reason=f'No campaign heartbeat for {idle} minutes during {stage}'
        result=dict(run.result or {})
        partial=_campaign_partial_discovery_result(run, now=now)
        result.update(partial)
        result.update({'stopped_reason':'campaign_stall_timeout','stalled_stage':stage,'last_heartbeat_at':last.isoformat() if last else '',
                       'execution_provider':run.execution_provider,'execution_model':run.execution_model,'timeout_reason':reason,
                       'stall_fail_minutes':fail_minutes})
        updated=CampaignRun.objects.filter(pk=run.pk,status='running').update(status='failed',finished_at=now,message=('Campaign stalled — partial discoveries saved' if partial.get('partial_result_finalized') else 'Campaign stalled / timed out'),
            error=reason,stall_reason=reason,result=result)
        if updated:
            failed_ids.append(run.pk)
            if run.celery_task_id:
                try: current_app.control.revoke(run.celery_task_id,terminate=False)
                except Exception: pass
    return {'warn_minutes':warn_minutes,'fail_minutes':fail_minutes,'warned_ids':warned_ids,'failed_ids':failed_ids}


def _coerce_max_concurrent_campaigns(value=None, default=5):
    """Clamp user-visible primary campaign concurrency to the supported range."""
    try:
        number = int(value if value not in (None, '') else default)
    except Exception:
        number = int(default or 5)
    return max(2, min(10, number))


def _local_discovery_capacity_limit(auto_limit=None, settings_obj=None):
    """Cap automatic Local campaigns independently from local-model generation lanes.

    ``SCOUTBOX_LOCAL_AI_GENERATION_LANES`` remains only a semaphore for short Ollama
    generation calls inside a campaign.  Campaign search/fetch/direct acquisition uses
    the General > Max concurrent campaigns setting, clamped to 2-10, with the legacy
    environment variables kept only as fallback when a settings row is unavailable.
    """
    if settings_obj is not None and hasattr(settings_obj, 'max_concurrent_campaigns'):
        return _coerce_max_concurrent_campaigns(getattr(settings_obj, 'max_concurrent_campaigns', None), 5)
    default = auto_limit if auto_limit is not None else os.getenv('SCOUTBOX_DISCOVERY_AUTO_INFLIGHT', '5')
    raw = os.getenv('SCOUTBOX_LOCAL_CAMPAIGN_INFLIGHT', str(default or 5))
    return _coerce_max_concurrent_campaigns(raw, default or 5)


def _automatic_discovery_inflight_limit(settings_obj=None):
    """Maximum automatic primary campaign runs queued/running at once.

    This is user-visible under General settings.  Keep the legacy environment value as
    a fallback for very early startup or tests without a PortalSettings row. Manual runs
    still count as in-flight.
    """
    if settings_obj is not None and hasattr(settings_obj, 'max_concurrent_campaigns'):
        return _coerce_max_concurrent_campaigns(getattr(settings_obj, 'max_concurrent_campaigns', None), 5)
    return _coerce_max_concurrent_campaigns(os.getenv('SCOUTBOX_DISCOVERY_AUTO_INFLIGHT', '5'), 5)




def _enabled_non_search_discovery_sources():
    """Return enabled direct/forum sources that can run without search engines.

    Automatic Local Discovery used to require at least one normal search provider before
    it would queue a campaign, which meant Forum browsing could be starved whenever all
    search engines were exhausted, disabled, or stuck.  Direct/forum adapters are valid
    discovery surfaces by themselves, so the scheduler should allow a run when any enabled
    direct adapter is configured.
    """
    rows=[]
    try:
        for source in SearchSource.objects.filter(enabled=True).exclude(source_type='cloud_ai')[:500]:
            cfg=source.config_json if isinstance(source.config_json,dict) else {}
            adapter=str(cfg.get('direct_adapter') or '').strip().lower()
            if adapter in DIRECT_ADAPTERS:
                rows.append({'name':source.name,'source_type':source.source_type,'adapter':adapter})
    except Exception:
        return []
    return rows




def _enabled_forum_discovery_sources():
    """Return enabled Forum sources that can run as an independent browse pass."""
    rows=[]
    try:
        for source in SearchSource.objects.filter(enabled=True,source_type='forum')[:500]:
            cfg=source.config_json if isinstance(source.config_json,dict) else {}
            adapter=str(cfg.get('direct_adapter') or '').strip().lower()
            if adapter==FORUM_DIRECT_ADAPTER or adapter in DIRECT_ADAPTERS:
                rows.append({'name':source.name,'source_type':'forum','adapter':adapter or FORUM_DIRECT_ADAPTER})
    except Exception:
        return []
    return rows


def _run_is_forum_only(run):
    try:
        criteria=run.criteria if isinstance(run.criteria,dict) else {}
        return bool(criteria.get('forum_only') or criteria.get('run_kind')=='forum_only')
    except Exception:
        return False


def _run_is_deferred_local_ai(run):
    try:
        criteria=run.criteria if isinstance(run.criteria,dict) else {}
        return bool(criteria.get('deferred_local_ai'))
    except Exception:
        return False


def _non_forum_runs(rows):
    """Filter CampaignRun rows in Python instead of excluding a missing JSON key.

    ``exclude(criteria__forum_only=True)`` is unsafe for historical JSON rows on
    PostgreSQL because a missing key evaluates to SQL NULL and can disappear from a
    negated predicate. Most normal CampaignRun criteria created before 0.10.81 do not
    carry an explicit ``forum_only: false`` value, so the scheduler could incorrectly
    treat those normal runs as absent. Keep the truth rule in one Python helper where a
    missing flag correctly means False.
    """
    return [run for run in rows if not _run_is_forum_only(run)]


def _run_is_coverage_exempt(run):
    """Return True for attempts that must not consume a discovery-window slot.

    A full ScoutBox stack restart can interrupt an otherwise healthy campaign after its
    Celery task has already been acknowledged. Restart recovery creates a replacement
    run for the interrupted attempt, so counting both rows would silently reduce source
    coverage for the rest of the window.
    """
    try:
        criteria=run.criteria if isinstance(run.criteria,dict) else {}
        return bool(criteria.get('coverage_exempt') or criteria.get('interrupted_by_restart'))
    except Exception:
        return False


def _primary_coverage_runs(rows):
    """Return normal discovery attempts that count toward window coverage."""
    return [run for run in rows if not _run_is_forum_only(run) and not _run_is_deferred_local_ai(run) and not _run_is_coverage_exempt(run)]


def _non_forum_run_exists(rows):
    return any(not _run_is_forum_only(run) for run in rows)


def _latest_non_forum_run(rows):
    for run in rows:
        if not _run_is_forum_only(run):
            return run
    return None

def _campaign_run_blocks_scheduling(run, now):
    """Return True only for queued/running rows that are still plausibly active."""
    if run.status=='queued':
        try:
            timeout_minutes=max(10,min(240,int(os.environ.get('SCOUTBOX_CAMPAIGN_QUEUE_STALE_MINUTES','30') or 30)))
        except Exception:
            timeout_minutes=30
        return bool(run.created_at and now-run.created_at < timedelta(minutes=timeout_minutes))
    if run.status=='stopping':
        result=run.result if isinstance(run.result,dict) else {}
        requested=_parse_aware_datetime(result.get('stop_requested_at')) or run.started_at or run.created_at
        return bool(requested and now-requested < timedelta(minutes=3))
    if run.status=='running':
        try:
            fail_minutes=max(5,int(os.environ.get('SCOUTBOX_CAMPAIGN_STALL_FAIL_MINUTES','20') or 20))
        except Exception:
            fail_minutes=20
        last=run.heartbeat_at or run.started_at or run.created_at
        return bool(last and now-last < timedelta(minutes=fail_minutes))
    return False


def _active_campaign_blocker(campaign, now, *, run_kind='any'):
    for run in CampaignRun.objects.filter(campaign=campaign,status__in=['queued','running','stopping']).order_by('-heartbeat_at','-started_at','-created_at')[:10]:
        forum_only=_run_is_forum_only(run)
        if run_kind=='forum_only' and not forum_only:
            continue
        if run_kind=='normal' and forum_only:
            continue
        if _campaign_run_blocks_scheduling(run,now):
            return run
    return None

def _queue_scheduled_url_health(now):
    """Queue a small rotating batch of stale URL-health checks.

    List views are intentionally read-only. A cache reservation prevents the minute-level
    scheduler from publishing the same row repeatedly while a worker is still probing it.
    Rows older than 90 days are excluded permanently from recurring checks.
    """
    stale_before=now-timedelta(hours=24)
    recent_after=now-timedelta(days=90)
    try:
        batch=max(1,min(60,int(os.environ.get('SCOUTBOX_URL_HEALTH_BATCH_PER_TICK','8') or 8)))
    except Exception:
        batch=8
    specs=[
        ('opportunity',Opportunity.objects.filter(user_deleted=False,suppressed=False,first_seen_by_portal__gte=recent_after)
            .exclude(target_url='').filter(Q(target_checked_at__isnull=True)|Q(target_checked_at__lt=stale_before))
            .order_by('target_checked_at','pk')),
        ('hidden_lead',CompanyLead.objects.filter(user_deleted=False,created_at__gte=recent_after)
            .filter(Q(target_url__gt='')|Q(source_url__gt='')).filter(Q(target_checked_at__isnull=True)|Q(target_checked_at__lt=stale_before))
            .order_by('target_checked_at','pk')),
        ('contact',Contact.objects.filter(deleted_at__isnull=True,created_at__gte=recent_after).filter(Q(source_url__gt='')|Q(email__gt=''))
            .filter(Q(domain_checked_at__isnull=True)|Q(domain_checked_at__lt=stale_before)).order_by('domain_checked_at','pk')),
    ]
    queued=[]
    # Round-robin the kinds so a large Opportunity backlog cannot starve Hidden Leads or
    # Address Book domains. Fetch only a small window from each queryset.
    pools=[(kind,list(qs[:batch])) for kind,qs in specs]
    while len(queued)<batch and any(rows for _,rows in pools):
        progressed=False
        for kind,rows in pools:
            if not rows or len(queued)>=batch: continue
            row=rows.pop(0); progressed=True
            key=f'scoutbox:url-health:{kind}:{row.pk}'
            if not cache.add(key,1,timeout=300):
                continue
            try:
                url_health_refresh_job.delay(kind,row.pk)
                queued.append({'kind':kind,'id':row.pk})
            except Exception:
                cache.delete(key)
        if not progressed: break
    return {'queued':queued,'count':len(queued),'stale_after_hours':24,'max_age_days':90,'batch_limit':batch}


def _forum_primary_idle_state(campaigns, now, settings_row, *, cloud_primary, window_start, window_seconds, target_attempts, gap_seconds):
    """Return whether Forum work may start without competing with primary discovery.

    A separate worker is not sufficient isolation by itself: Forum HTTP/AI work still
    shares network, database and local/cloud AI resources. Forum passes therefore require
    a *deep idle* window. Local mode must first complete every campaign's planned search
    rotations for the current window; Cloud mode must have no campaign due inside the
    guard horizon. This makes Forum traffic opportunistic instead of an alternate primary
    workload.
    """
    try:
        guard_minutes=max(2,min(60,int(os.environ.get('SCOUTBOX_FORUM_PRIMARY_GUARD_MINUTES','5') or 5)))
    except Exception:
        guard_minutes=5
    guard_seconds=guard_minutes*60
    campaigns=list(campaigns)
    if not campaigns:
        return False, {'reason':'no enabled campaigns','guard_minutes':guard_minutes}

    if not cloud_primary:
        incomplete=[]
        for campaign in campaigns:
            attempts=len(_primary_coverage_runs(CampaignRun.objects.filter(
                campaign=campaign,created_at__gte=window_start
            ).order_by('created_at')))
            if attempts < int(target_attempts or 1):
                incomplete.append({'campaign_id':campaign.pk,'campaign':campaign.name,'attempts':attempts,'target':int(target_attempts or 1)})
        if incomplete:
            return False, {'reason':'primary search coverage incomplete','guard_minutes':guard_minutes,'incomplete':incomplete[:12]}
        window_end=window_start+timedelta(seconds=int(window_seconds or 0))
        seconds_to_next=max(0,int((window_end-now).total_seconds()))
        if seconds_to_next <= guard_seconds:
            return False, {'reason':'next primary search window is near','guard_minutes':guard_minutes,'next_primary_in_seconds':seconds_to_next}
        return True, {'reason':'primary search coverage complete','guard_minutes':guard_minutes,'next_primary_in_seconds':seconds_to_next}

    today_start=timezone.make_aware(datetime.combine(timezone.localdate(),datetime.min.time()),timezone.get_current_timezone())
    tomorrow_start=today_start+timedelta(days=1)
    due_in=[]
    for campaign in campaigns:
        auto_limit=max(1,int(settings_row.cloud_auto_runs_per_campaign_day or 5))
        auto_used=len(_non_forum_runs(CampaignRun.objects.filter(
            campaign=campaign,created_at__gte=today_start,criteria__automatic=True
        ).order_by('created_at')))
        if auto_used >= auto_limit:
            wait=max(0,int((tomorrow_start-now).total_seconds()))
        else:
            latest=_latest_non_forum_run(CampaignRun.objects.filter(campaign=campaign).order_by('-created_at')[:100])
            effective_minutes=max(_safe_setting_int(settings_row,'scraper_interval_minutes',120,minimum=30),max(15,int(settings_row.cloud_min_interval_minutes or _safe_setting_int(settings_row,'scraper_interval_minutes',120,minimum=30))))
            wait=0 if latest is None else max(0,int(effective_minutes*60-(now-latest.created_at).total_seconds()))
        due_in.append(wait)
    next_primary=min(due_in) if due_in else 0
    if next_primary <= guard_seconds:
        return False, {'reason':'Cloud primary discovery is due soon','guard_minutes':guard_minutes,'next_primary_in_seconds':next_primary}
    return True, {'reason':'Cloud primary discovery has an idle window','guard_minutes':guard_minutes,'next_primary_in_seconds':next_primary}


def _scheduler_lock_client():
    try:
        import redis
        return redis.Redis.from_url(settings.CELERY_BROKER_URL,decode_responses=True,socket_timeout=2,socket_connect_timeout=2)
    except Exception:
        return None


@shared_task
def scheduler_tick():
    """Single-writer scheduler entry point across Beat/process instances."""
    token=f'{os.getpid()}:{time.time_ns()}'
    client=_scheduler_lock_client(); key='scoutbox:scheduler_tick:v01094'
    if client is not None:
        try:
            if not client.set(key,token,nx=True,ex=110):
                return {'skipped':'scheduler_tick_already_owned'}
        except Exception:
            client=None
    try:
        return _scheduler_tick_unlocked()
    finally:
        if client is not None:
            try:
                client.eval("if redis.call('get',KEYS[1]) == ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end",1,key,token)
            except Exception:
                pass


def _scheduler_tick_unlocked():
    # Redis is the fast cross-process guard, but scheduling must remain idempotent when
    # Redis is temporarily unreachable. Claim the tick in the database under a row lock;
    # a second Beat/process entering the same scheduling window observes the fresh claim
    # and exits before it can create CampaignRun/Hidden Lead/Forum work.
    claim_now=timezone.now()
    with transaction.atomic():
        PortalSettings.objects.get_or_create(pk=1)
        s=PortalSettings.objects.select_for_update().get(pk=1)
        previous_tick=s.last_scheduler_tick
        if previous_tick:
            duplicate_age=(claim_now-previous_tick).total_seconds()
            if 0 <= duplicate_age < 20:
                return {'skipped':'scheduler_tick_duplicate_db_claim','last_tick_at':previous_tick.isoformat(),'age_seconds':int(duplicate_age)}
        gap_seconds=max(0,int((claim_now-previous_tick).total_seconds())) if previous_tick else None
        health=dict(getattr(s,'scheduler_health',{}) or {})
        health.update({'last_tick_at':claim_now.isoformat(),'previous_tick_at':previous_tick.isoformat() if previous_tick else None,'last_gap_seconds':gap_seconds,'db_claim_at':claim_now.isoformat()})
        if gap_seconds is not None:
            health['longest_gap_seconds']=max(int(health.get('longest_gap_seconds') or 0),gap_seconds)
        s.last_scheduler_tick=claim_now; s.scheduler_health=health
        s.save(update_fields=['last_scheduler_tick','scheduler_health','updated_at'])
    now=claim_now
    # Scheduler continuity remains available in scheduler_health. Routine gaps are not
    # user-facing audit events; lifecycle and version changes are recorded instead.
    worker_snapshot=_celery_worker_snapshot()
    try:
        health=dict(getattr(s,'scheduler_health',{}) or {})
        health.update({'workers':sorted(worker_snapshot.get('workers') or []),'worker_states':worker_snapshot.get('states') or {},'worker_inspection_available':bool(worker_snapshot.get('available')),'checked_at':now.isoformat()})
        s.scheduler_health=health; s.save(update_fields=['scheduler_health','updated_at'])
    except Exception:
        pass
    campaign_ownership_watchdog=_interrupt_unowned_campaign_runs(now,snapshot=worker_snapshot)
    background_watchdog=_expire_stale_background_jobs(now,snapshot=worker_snapshot)
    background_watchdog['company_research_requeued_ids']=_requeue_interrupted_company_research(background_watchdog)
    stopped_by_watchdog=_stop_stale_campaign_runs(now)
    queued_watchdog=_expire_stale_queued_campaign_runs(now)
    stalled_watchdog=_fail_stalled_campaign_runs(now)
    focus_rebuild_job=None
    country_repair_job=None
    integrity_repair_job=None
    hidden_lead_reassessment_job=None
    if not s.background_paused:
        try: focus_rebuild_job=_queue_focus_taxonomy_rebuild(s) or _queue_focus_blank_backfill(s)
        except Exception: focus_rebuild_job=None
        try: country_repair_job=_queue_country_location_repair(s)
        except Exception: country_repair_job=None
        try: integrity_repair_job=_queue_v010104_integrity_repair(s)
        except Exception: integrity_repair_job=None
        try: hidden_lead_reassessment_job=_queue_hidden_lead_minibrowser_reassessment(s,snapshot=worker_snapshot)
        except Exception: hidden_lead_reassessment_job=None
    if s.background_paused: return {'paused':True,'campaign_ownership_watchdog':campaign_ownership_watchdog,'background_watchdog':background_watchdog,'stopped_by_watchdog':stopped_by_watchdog,'queued_watchdog':queued_watchdog,'stalled_watchdog':stalled_watchdog}
    url_health=_queue_scheduled_url_health(now)
    window_minutes=_safe_setting_int(s,'scraper_interval_minutes',120,minimum=30); window_seconds=window_minutes*60
    epoch=int(now.timestamp()); window_start_ts=(epoch//window_seconds)*window_seconds
    window_start=datetime.fromtimestamp(window_start_ts,tz=timezone.get_current_timezone())
    cloud_primary=(s.discovery_mode=='cloud_web')
    # Local AI Discovery keeps repeated source coverage inside the configured Search
    # window. Cloud Web treats the same value as a hard minimum start-to-start interval;
    # billable discovery must never be accelerated by the local rotation algorithm.
    target_attempts=1 if cloud_primary else max(2,min(8,math.ceil(window_minutes/15)))
    gap_seconds=window_seconds if cloud_primary else max(8*60,int(window_seconds/target_attempts))
    launched=[]
    has_active_cv=DocumentAsset.objects.filter(kind='cv',active=True).exists()
    campaign_qs=Campaign.objects.filter(enabled=True,deleted_at__isnull=True) if has_active_cv else Campaign.objects.none()
    discovery_inflight_limit=_automatic_discovery_inflight_limit(s)
    if not cloud_primary:
        discovery_inflight_limit=min(discovery_inflight_limit,_local_discovery_capacity_limit(discovery_inflight_limit,s))
    discovery_inflight=len(_non_forum_runs(
        CampaignRun.objects.filter(status__in=['queued','running','stopping']).order_by('created_at')
    ))
    if not has_active_cv:
        launched.append({'campaign':'Resume-first Automatic Discovery','status':'waiting for active Resume'})
    if cloud_primary:
        try:
            if not has_usable_cloud_web_model():
                raise RuntimeError('One or more Cloud Web stages is not configured.')
            cloud_discovery_route(stage='url_scrape')
        except Exception:
            return {'window_minutes':window_minutes,'target_attempts':target_attempts,'items':[{'campaign':c.name,'status':'waiting for Cloud Web — no usable Cloud provider/model'} for c in campaign_qs],'hidden_market':'waiting for Cloud Web','url_health':url_health,'campaign_ownership_watchdog':campaign_ownership_watchdog,'background_watchdog':background_watchdog,'stopped_by_watchdog':stopped_by_watchdog,'stalled_watchdog':stalled_watchdog}
        provider_cooldown=cloud_rate_limit_cooldown(now,seconds=300)
        if provider_cooldown:
            provider=str(provider_cooldown.get('provider') or 'cloud').title()
            wait_seconds=int(provider_cooldown.get('seconds_remaining') or 0)
            cooldown_payload={k:(v.isoformat() if hasattr(v,'isoformat') else v) for k,v in provider_cooldown.items()}
            return {'window_minutes':window_minutes,'target_attempts':target_attempts,
                    'items':[{'campaign':c.name,'status':f'waiting for {provider} rate-limit cooldown','next_in_seconds':wait_seconds} for c in campaign_qs],
                    'hidden_market':'handled by Cloud Web campaigns','cloud_provider_cooldown':cooldown_payload,
                    'url_health':url_health,
                    'campaign_ownership_watchdog':campaign_ownership_watchdog,'background_watchdog':background_watchdog,
                    'stopped_by_watchdog':stopped_by_watchdog,'queued_watchdog':queued_watchdog,'stalled_watchdog':stalled_watchdog}
    else:
        readiness=ai_compute_readiness(force=True)
        if not readiness.get('ready'):
            return {'window_minutes':window_minutes,'target_attempts':target_attempts,'items':[{'campaign':c.name,'status':'waiting for AI compute'} for c in campaign_qs],'hidden_market':'waiting for AI compute','ai_readiness':readiness.get('reason',''),'url_health':url_health,'campaign_ownership_watchdog':campaign_ownership_watchdog,'background_watchdog':background_watchdog,'stopped_by_watchdog':stopped_by_watchdog,'stalled_watchdog':stalled_watchdog}
    cloud_fallback=False
    source_preflight=None
    direct_preflight=[]
    forum_preflight=_enabled_forum_discovery_sources()
    if not cloud_primary and not cloud_fallback:
        _,source_preflight=provider_selection_details(limit=1)
        direct_preflight=_enabled_non_search_discovery_sources()

    # Forum discovery is deliberately scheduled only after primary campaign decisions.
    # It has its own single-slot queue and starts only when no primary discovery is active.

    for c in campaign_qs:
        blocker=_active_campaign_blocker(c,now,run_kind='normal')
        if blocker is not None:
            launched.append({'campaign':c.name,'status':'already running','run_id':blocker.pk,'stage':blocker.stage or blocker.message or ''}); continue
        if discovery_inflight>=discovery_inflight_limit:
            launched.append({
                'campaign':c.name,
                'status':f'waiting for discovery worker — {discovery_inflight} active run'+('s' if discovery_inflight!=1 else ''),
                'active_runs':discovery_inflight,
                'capacity':discovery_inflight_limit,
            })
            continue
        if source_preflight is not None and not source_preflight.get('selected') and not direct_preflight:
            if source_preflight.get('usable_count') and source_preflight.get('budget_exhausted'):
                launched.append({'campaign':c.name,'status':'waiting for search provider daily budgets','stopped_reason':'provider_daily_budgets_exhausted','provider_selection':source_preflight})
            else:
                launched.append({'campaign':c.name,'status':'waiting for eligible search provider','stopped_reason':'no_eligible_search_providers','provider_selection':source_preflight})
            continue
        if cloud_primary:
            today_start=timezone.make_aware(datetime.combine(timezone.localdate(),datetime.min.time()),timezone.get_current_timezone())
            cloud_runs=_primary_coverage_runs(_non_forum_runs(
                CampaignRun.objects.filter(campaign=c,created_at__gte=today_start).order_by('-created_at')
            ))
            auto_limit=max(1,int(s.cloud_auto_runs_per_campaign_day or 5))
            auto_used=sum(1 for r in cloud_runs if isinstance(r.criteria,dict) and r.criteria.get('automatic'))
            try:
                from portal.services.cloud_budget import _record_threshold
                _record_threshold(f'day:{timezone.localdate().isoformat()}',f'campaign:{c.pk}:automatic_runs',
                                  'Automatic runs / campaign / day',auto_used,auto_limit,c.name)
            except Exception:
                pass
            if auto_used>=auto_limit:
                launched.append({'campaign':c.name,'status':'cloud daily run limit reached'}); continue
            latest_run=_latest_non_forum_run(CampaignRun.objects.filter(campaign=c).order_by('-created_at')[:100])
            effective_minutes=max(window_minutes,max(15,int(s.cloud_min_interval_minutes or window_minutes)))
            if latest_run:
                age=(now-latest_run.created_at).total_seconds()
                minimum=effective_minutes*60
                if age<minimum:
                    launched.append({'campaign':c.name,'status':'waiting for cloud search window','next_in_seconds':int(minimum-age),'minimum_interval_minutes':effective_minutes}); continue
            attempts=0
            criteria=_campaign_criteria(c); criteria.update({'discovery_mode':s.discovery_mode,'automatic':True,'forum_only':False,'run_kind':'primary','deferred_local_ai':False,'search_interval_minutes':effective_minutes,'rotation_offset':0,'window_attempt':1,'window_attempt_limit':1})
            run_message='Automatic Cloud search'
        else:
            all_primary_runs=_non_forum_runs(
                CampaignRun.objects.filter(campaign=c,created_at__gte=window_start).order_by('created_at')
            )
            runs=_primary_coverage_runs(all_primary_runs)
            attempts=len(runs)
            if attempts>=target_attempts:
                launched.append({'campaign':c.name,'status':'window coverage complete','attempts':attempts}); continue
            if all_primary_runs:
                # Every attempted primary launch, including a Local-AI deferral, gets the
                # normal intra-window backoff.  This prevents a busy lane or fast code
                # failure from generating a fresh CampaignRun on every one-minute tick.
                last_any=all_primary_runs[-1]
                age=(now-last_any.created_at).total_seconds()
                if age<gap_seconds:
                    launched.append({'campaign':c.name,'status':'waiting within window','next_in_seconds':int(gap_seconds-age)}); continue
            if runs:
                # Two recent failed attempts trip a circuit breaker until the next search
                # window.  One broken campaign therefore cannot monopolize scheduler
                # capacity and leave later enabled campaigns permanently due.
                recent=runs[-2:]
                severe=0
                for r in recent:
                    result=r.result or {}; errs=result.get('errors') or []; providers=result.get('providers') or []
                    # 0.10.91 had a release regression in job-board candidate consolidation.
                    # Do not let those known failed rows keep a repaired 0.10.92 campaign
                    # circuit-broken until the next search window after upgrade.
                    known_release_bug='_JOB_AGGREGATOR_BRANDS' in str(r.error or '') or '_JOB_AGGREGATOR_BRANDS' in str(r.stall_reason or '')
                    if not known_release_bug and (r.status=='failed' or (providers and len(errs)>=len(providers)*2 and not result.get('raw_hits'))): severe+=1
                if severe>=2:
                    launched.append({'campaign':c.name,'status':'recent campaign failures; retry next window'}); continue
            criteria=_campaign_criteria(c); criteria.update({'discovery_mode':s.discovery_mode,'automatic':True,'forum_only':False,'run_kind':'primary','deferred_local_ai':False,'window_start':window_start.isoformat(),'rotation_offset':attempts,'window_attempt':attempts+1,'window_attempt_limit':target_attempts,'non_search_direct_sources_available':len(direct_preflight)})
            run_message=f'Automatic search rotation {attempts+1}/{target_attempts}'
        if cloud_primary:
            inherited=inherited_run_context(c,now=now)
            if inherited:
                criteria['run_context']=inherited
        run=CampaignRun.objects.create(campaign=c,criteria=criteria,message=run_message)
        if cloud_primary:
            try:
                from portal.services.cloud_budget import _record_threshold
                used=len(_primary_coverage_runs(_non_forum_runs(
                    CampaignRun.objects.filter(campaign=c,created_at__gte=today_start,criteria__automatic=True).order_by('created_at')
                )))
                _record_threshold(f'day:{timezone.localdate().isoformat()}',f'campaign:{c.pk}:automatic_runs',
                                  'Automatic runs / campaign / day',used,auto_limit,c.name)
            except Exception:
                pass
        task=run_campaign_job.delay(run.pk); run.celery_task_id=task.id or ''; run.save(update_fields=['celery_task_id'])
        discovery_inflight+=1
        launched.append({'campaign':c.name,'run_id':run.pk,'status':'queued','attempt':attempts+1,'attempt_limit':target_attempts,'active_runs':discovery_inflight,'capacity':discovery_inflight_limit})

    # Hidden Market scans are automatic too. They look for technical-work signals rather
    # than explicit vacancies, so run them periodically without requiring a page click.
    hidden_gap=max(15*60,min(60*60,int(window_seconds/4)))
    # scan_hidden_market has a 40-minute wall-clock budget. If a worker dies or is killed,
    # reclaim a stale DB job here (scheduler-side) after 50 minutes so one orphaned row
    # cannot block all future Hidden Leads scans indefinitely. Dashboard views never
    # mutate live job state.
    stale_cutoff=now-timedelta(minutes=50)
    stale_hidden=BackgroundJob.objects.filter(kind='hidden_scan',status__in=['queued','running'],created_at__lt=stale_cutoff)
    if stale_hidden.exists():
        stale_hidden.update(status='failed',finished_at=now,progress=100,message='Hidden Leads scan stopped after exceeding its execution window.',error='Worker heartbeat/execution exceeded 50 minutes; scheduler released the stale scan so a new scan can run.')
    hidden_running=BackgroundJob.objects.filter(kind='hidden_scan',status__in=['queued','running']).exists()
    hidden_due=(not s.last_hidden_scan) or (now-s.last_hidden_scan).total_seconds()>=hidden_gap
    hidden_status='waiting'
    if cloud_primary:
        # Cloud campaign research now yields selective Hidden Leads. Never start the legacy
        # local search-engine Hidden Market scanner while Cloud Web is the discovery method.
        hidden_status='handled by Cloud Web campaigns'
    elif hidden_due and not hidden_running:
        job=BackgroundJob.objects.create(kind='hidden_scan',label='Hidden Leads scan',message='Queued automatically')
        task=hidden_market_scan_job.delay(job.pk); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
        hidden_status='queued'
    elif hidden_running:
        hidden_status='already running'
    # Forum browsing is optional/background acquisition. It is allowed in both Local AI
    # and Cloud Web modes, but only when primary discovery is completely idle. A separate
    # one-slot Celery queue plus cooperative yielding above prevents forum latency, Reddit
    # timeouts, or Cloud forum qualification from reducing primary discovery throughput.
    primary_inflight=len(_non_forum_runs(
        CampaignRun.objects.filter(status__in=['queued','running','stopping']).order_by('created_at')
    ))
    higher_priority_background_work=BackgroundJob.objects.filter(status__in=['queued','running']).count()
    forum_idle_ok,forum_idle_state=_forum_primary_idle_state(
        campaign_qs,now,s,cloud_primary=cloud_primary,window_start=window_start,window_seconds=window_seconds,
        target_attempts=target_attempts,gap_seconds=gap_seconds,
    )
    # Deep-idle remains the normal Forum policy, but it must not be possible for a busy
    # Local campaign rotation to starve forums indefinitely. After six hours without a
    # Forum pass, allow one bounded one-source pass as soon as primary discovery and all
    # higher-priority background work are physically idle. The forum worker still yields
    # immediately if primary work appears or the Local AI lane is busy.
    try:
        forum_starvation_hours=max(2,min(24,int(os.environ.get('SCOUTBOX_FORUM_STARVATION_HOURS','6') or 6)))
    except Exception:
        forum_starvation_hours=6
    latest_forum_global=CampaignRun.objects.filter(criteria__forum_only=True).order_by('-created_at').first()
    forum_age_seconds=((now-latest_forum_global.created_at).total_seconds() if latest_forum_global else None)
    forum_starved=(latest_forum_global is None or forum_age_seconds >= forum_starvation_hours*3600)
    forum_idle_state={**(forum_idle_state or {}),
        'last_forum_at':(latest_forum_global.created_at.isoformat() if latest_forum_global else None),
        'last_forum_age_seconds':forum_age_seconds,'starvation_hours':forum_starvation_hours,
        'starvation_override':bool(forum_starved and not forum_idle_ok),'background_jobs_active':int(higher_priority_background_work or 0),
        'next_eligible_in_seconds':0 if forum_starved else max(0,int(forum_starvation_hours*3600-(forum_age_seconds or 0))),
    }
    forum_launch_allowed=True  # bounded HTTP acquisition is isolated; AI qualification yields in run_campaign_job
    if forum_preflight and has_active_cv and forum_launch_allowed:
        try:
            forum_interval_minutes=max(5,min(240,int(os.environ.get('SCOUTBOX_FORUM_BROWSE_INTERVAL_MINUTES','5') or 5)))
        except Exception:
            forum_interval_minutes=5
        try:
            forum_global_interval_minutes=max(5,min(120,int(os.environ.get('SCOUTBOX_FORUM_GLOBAL_INTERVAL_MINUTES','5') or 5)))
        except Exception:
            forum_global_interval_minutes=5
        # One pass at a time is intentional. A global interval also prevents many
        # campaigns from turning a per-campaign interval into continuous Forum traffic.
        forum_inflight=CampaignRun.objects.filter(status__in=['queued','running','stopping'],criteria__forum_only=True).count()
        forum_global_due=(forum_starved or not latest_forum_global or (now-latest_forum_global.created_at).total_seconds() >= forum_global_interval_minutes*60)
        if forum_inflight==0 and forum_global_due:
            for fc in campaign_qs:
                if _active_campaign_blocker(fc,now,run_kind='forum_only') is not None:
                    continue
                latest_forum=CampaignRun.objects.filter(campaign=fc,criteria__forum_only=True).order_by('-created_at').first()
                if (not forum_starved) and latest_forum and (now-latest_forum.created_at).total_seconds() < forum_interval_minutes*60:
                    continue
                criteria=_campaign_criteria(fc)
                criteria.update({
                    'discovery_mode':s.discovery_mode,'automatic':True,'forum_only':True,'run_kind':'forum_only',
                    'forum_interval_minutes':forum_interval_minutes,'forum_global_interval_minutes':forum_global_interval_minutes,
                    'enabled_forum_sources':len(forum_preflight),'primary_throughput_isolated':True,
                    'forum_starvation_override':bool(forum_starved and not forum_idle_ok),
                    'forum_last_pass_at':(latest_forum_global.created_at.isoformat() if latest_forum_global else None),
                })
                forum_run=CampaignRun.objects.create(campaign=fc,criteria=criteria,message=('Automatic bounded Forum recovery pass' if forum_starved and not forum_idle_ok else 'Automatic bounded Forum browse'))
                task=run_campaign_job.apply_async(args=[forum_run.pk],queue='forum')
                forum_run.celery_task_id=task.id or ''
                forum_run.save(update_fields=['celery_task_id'])
                launched.append({
                    'campaign':fc.name,'run_id':forum_run.pk,'status':'queued bounded forum browse',
                    'forum_only':True,'discovery_mode':s.discovery_mode,'enabled_forum_sources':len(forum_preflight),
                    'active_forum_runs':1,'capacity':1,'forum_global_interval_minutes':forum_global_interval_minutes,
                    'forum_starvation_override':bool(forum_starved and not forum_idle_ok),
                })
                break
    if any(item.get('run_id') and not item.get('forum_only') for item in launched):
        s.last_discovery_run=now; s.save(update_fields=['last_discovery_run','updated_at'])
    return {'window_minutes':window_minutes,'target_attempts':target_attempts,'items':launched,'hidden_market':hidden_status,'forum_idle_state':forum_idle_state,'url_health':url_health,'campaign_ownership_watchdog':campaign_ownership_watchdog,'background_watchdog':background_watchdog,'stopped_by_watchdog':stopped_by_watchdog,'queued_watchdog':queued_watchdog,'stalled_watchdog':stalled_watchdog}


@shared_task
def mail_sync_tick():
    s=PortalSettings.objects.get_or_create(pk=1)[0]
    if s.background_paused: return {'paused':True}
    try:
        result=sync_mailbox() or {}
    except Exception as e:
        result={'error':str(e)}
    try:
        result['resend_delivery_refresh']=refresh_resend_delivery_states(limit=25)
    except Exception as exc:
        result['resend_delivery_refresh']={'error':str(exc)[:200]}
    return result


@shared_task
def blog_click_sync():
    s=PortalSettings.objects.get_or_create(pk=1)[0]
    if s.background_paused or not s.feature_blog_click_sync: return {'paused':s.background_paused,'disabled':not s.feature_blog_click_sync}
    try: return sync_clicks()
    except Exception as e: return {'error':str(e)}


@shared_task
def daily_digest_tick():
    s=PortalSettings.objects.get_or_create(pk=1)[0]
    if s.background_paused or not s.digest_enabled: return {'skipped':True}
    now=timezone.localtime(); today=now.date()
    if s.last_digest_sent==today or (now.hour,now.minute) < (s.digest_hour,s.digest_minute): return {'due':False}
    recipient=(s.digest_recipient_email or '').strip()
    if not recipient:
        recipient=(User.objects.filter(is_active=True,is_staff=True).exclude(email='').order_by('pk').values_list('email',flat=True).first() or '').strip()
        if recipient:
            s.digest_recipient_email=recipient
            s.save(update_fields=['digest_recipient_email','updated_at'])
    if not recipient: return {'error':'No daily digest recipient configured'}
    try:
        generated_at=timezone.now(); digest=build_24h_digest(generated_at)
        scheduled_local=now.replace(hour=int(s.digest_hour),minute=int(s.digest_minute),second=0,microsecond=0)
        delay_seconds=max(0,int((now-scheduled_local).total_seconds()))
        event=send_notification(
            recipient,digest['subject'],digest['body'],html_body=digest.get('html_body'),
            metadata_extra={'digest':True,'scheduled_for':scheduled_local.isoformat(),'submitted_at':now.isoformat(),
                            'submitted_after_scheduler_recovery':bool(delay_seconds>300),'delay_seconds':delay_seconds},
        )
        s.last_digest_sent=today; s.save(update_fields=['last_digest_sent','updated_at'])
        return {'accepted':True,'provider_message_id':getattr(event,'message_id',''),'scheduled_for':scheduled_local.isoformat(),'delay_seconds':delay_seconds,**digest.get('counts',{})}
    except Exception as e: return {'error':str(e)}

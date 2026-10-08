import csv
import io
import math
import hashlib
import html
import tempfile
import json
import logging
import os
import re
import smtplib
import time
import platform
import zipfile
import shutil
import subprocess
import uuid
import unicodedata
import requests
from collections import Counter
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse, parse_qsl
from pathlib import Path
from importlib.metadata import version as package_version, PackageNotFoundError
from types import SimpleNamespace

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import Avg, Case, Count, IntegerField, Max, Min, Q, Sum, Value, When
from django.db.models.functions import Cast, Coalesce, TruncHour, TruncDay
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.clickjacking import xframe_options_sameorigin

from .models import *
from .services.crypto import encrypt, decrypt
from .services.audit import log
from .services import ollama as ollama_service
from .services.ai import test_provider, web_search_with, STAGES, STAGE_TOKEN_DEFAULTS, CLOUD_STAGE_TOKEN_DEFAULTS, default_stage_routes, stage_routes_with_defaults, generate, generate_with, route_for_stage, token_limits_for_stage, pipeline_route_signature, configured_cloud_configs, configured_cloud_web_configs, configured_cloud_web_routes, cloud_web_selection, cloud_web_stage_routes, cloud_provider_priority, has_configured_cloud_model, has_usable_cloud_web_model, configured_cloud_model, bundle_owners, effective_cloud_bundle_anchor, web_capable_cloud_route, cloud_discovery_route, automatic_ollama_model_cap_billions, cloud_rate_limit_cooldown, _recover_truncated_json_list
from .services.discovery import run_campaign
from .services.enrichment import enrich
from .services.application import prepare_application, generate_email_version, generate_cv_artifacts, scan_docx_links, personalize_email_body
from .services.mailbox import active_profile, folders as imap_folders, sync_mailbox, save_draft, delete_draft, connect as imap_connect, fetch_event_body, contact_company_from_email, contact_name_from_email, is_generic, is_non_contact_address, assignable_contact_email, contact_email_has_non_contact_context, contact_ownership_plausible, automatic_addressbook_contact_allowed, clean_contact_email, clean_contact_text, browse_folder, fetch_imap_message, delete_imap_draft, populate_test_messages, promote_record_contact_to_addressbook, assess_addressbook_contact_fit, _sanitize_html as _sanitize_email_html
from .services.notifications import send_notification, outgoing_method, outgoing_server_label
from .services.digest import build_24h_digest
from .services.tracking import allocate_for_url, preview_for_url, blog_base_url, clean_article_title, article_title_needs_refresh
from .services.blogstats import sync_clicks, test_connection as test_blog_connection, load_external_config, save_external_config, migrate_legacy_config, service_status as external_stats_status
from .services.freshness import recompute, opportunity_post_age_sort_days, opportunity_post_age_display_label
from .services.focus import focus_options
from .services.imports import parse_lines, read_uploaded, parse_uploaded, confirm_candidate
from .services.performance import run_lab
from .services.cold import scan_hidden_market, generate_cold_draft, ensure_outreach_application, is_general_market_host, is_general_market_company, is_documentation_like, preliminary_company_summary, market_summary_needs_refresh, display_company_name
from .services.queryplanner import (
    build_search_profile, extract_active_cv_texts, ROLE_FAMILIES, SKILL_GRAPH,
    PROFILE_CONCEPT_LIMIT, PROFILE_ROLE_LIMIT,
)
from .services.languages import language_options, normalise_language
from .services.cloud_discovery import discover as cloud_discover
from .services.search import facebook_authenticated_fetch, facebook_page_relevant, choose_providers, provider_selection_details, provider_budget, provider_budget_used, provider_budget_remaining, provider_budget_kind, build_campaign_queries, build_campaign_query_plan, search_source, provider_credential_state, provider_capability, test_search_provider, validate_searchapi_credential, ACTIVE_PROVIDER_NAMES, SEARCHAPI_SERVICE_SOURCES, SEARCHAPI_SERVICE_LABELS, SEARCHAPI_SHORT_LABELS, SEARCHAPI_DEFAULT_AUTO, searchapi_source, searchapi_service_code
from .services.discovery_markets import MARKETS, MARKET_BY_CODE, DEFAULT_MARKET_CODES, MULTILINGUAL_LANGUAGE_OPTIONS, auto_multilingual_languages, query_language_code, query_language_label, query_language_identity, QUERY_LANGUAGE_NAME_BY_CODE
from .services.chatbot import ask as chatbot_answer
from .services.presentation import rich_html, clean_placeholder
from .services.provenance import has_local_fit_assessment, has_cloud_fit_assessment
from .services.pagefetch import fetch_target
from .services.opportunity_urls import is_disallowed_adult_url
from .services.company_research import (ensure_company_research_baseline, stored_company_context,
    enrich_company_intel_from_retained, company_info_has_display_data, company_summary_from_intel,
    is_job_or_platform_company_name, is_job_or_platform_host)
from .services.cloud_budget import today_usage as cloud_today_usage, limit_status as cloud_limit_status, is_cloud_provider, CloudLimitReached
from .services.readiness import ai_compute_readiness, route_ready, local_accelerator_state
from .services.ai_lifecycle import reserve_attempt, usable_result
from .services.campaign_links import repair_opportunity_campaign_links, repair_lead_campaign_links, copy_lead_campaigns_to_opportunity
from .services.diagnostics import run_system_diagnostics
from .services.blacklist import pattern_for_url, normalize_pattern, normalize_label, normalize_company_blacklist_key, valid_label_only_pattern, valid_company_blacklist_label, company_blacklist_candidate, blacklist_candidate_for_record, company_specific_blacklist_review_domain_for_record, LABEL_BLACKLIST_MIN_CHARS, reset_defaults as reset_blacklist_defaults, enforce_active_blacklist, is_aggregator_blacklist_domain, clean_blacklist_reason
from .services import statistics as stats_service
from .services.resources import gpu_telemetry, gpu_telemetry_detail, host_resource_totals, host_cpu_percent, capture_resource_sample, bridge_telemetry_status
from .services.run_context import make_run_context, display_run_context, describe_run_context, inherited_run_context, default_keep_until
from .services.dedup import clean_contact_name, company_key as dedup_company_key, contact_quality, suppress_overlapping_leads, active_opportunity_for_company, active_duplicate_lead, reconcile_active_duplicates, normalized_url
from .ui import COUNTRIES, CURRENCIES, NAV_GROUPS, NAV_PARENT
from .services.location_values import location_labels, legacy_location_text, normalize_location_items, record_location_items
from .services.world_geo import location_point as world_location_point, project as world_project, COUNTRY_POINTS as WORLD_COUNTRY_POINTS
from .templatetags.portal_extras import (
    company_info_compact, company_info_sort_value, remote_sort_value,
    opportunity_list_summary, hidden_lead_list_summary,
    manual_filter_meaningful_items, manual_filter_decision_label, manual_filter_fit_change,
)
from .tasks import (run_campaign_job, import_text_job, import_document_job, mailbox_import_job, diagnostic_search_job, hidden_market_scan_job, opportunity_enrich_job, opportunity_filter_job, hidden_lead_filter_job, contact_filter_job, opportunity_freshness_job, application_prepare_job, translate_opportunity_job, company_research_job, performance_lab_job, cold_draft_job, application_answers_job, application_compare_job, application_cv_job, system_diagnostics_job, translate_lead_job, opportunity_summary_job, market_lead_summary_job, search_provider_test_job, email_profile_test_job, ai_provider_test_job, ollama_test_job, blog_stats_test_job, tracking_link_test_job, candidate_profile_defaults_job, candidate_profile_autopopulate_job, campaign_templates_job, resume_campaign_template_job, all_resume_campaign_templates_job, url_health_refresh_job, application_imap_save_job, pipeline_model_test_job, lead_company_research_job, rebuild_missing_ai_data_job, chatbot_request_job, recover_stalled_operations_state, diagnostic_export_job, facebook_page_title_tick, tracking_article_title_tick)


logger=logging.getLogger(__name__)


CAMPAIGN_OPTIONS={
    'roles':['Embedded systems','Firmware / hardware','Reverse engineering','Retro / legacy systems','Systems software','Technical writing','Teaching / training','Consulting / specialist support','Technical support'],
    'tech':['PIC','STM32','ESP32','RTOS','Embedded Linux','QEMU','BIOS','x86','DOS','MAME','Firmware analysis','Binary analysis','Device drivers','FPGA','Legacy protocols'],
    'engagement':['Full-time','Part-time','Contract','Agency / consulting','One-time project','Collaboration','Unknown'],
    'sizes':['Solo / very small','Small','Startup','Medium','Large / enterprise','Unknown'],
    'languages':['English','French','German','Japanese','Chinese'],
}


AI_PROVIDER_UI_ORDER=('openai','gemini','openrouter','ollama')
AI_PROVIDER_DEFAULTS={
    'openai':('https://api.openai.com/v1',False),
    'gemini':('https://generativelanguage.googleapis.com/v1beta',False),
    'openrouter':('https://openrouter.ai/api/v1',False),
    'ollama':('http://host.docker.internal:11434',True),
}
AI_PROVIDER_TEST_PROMPT='Reply with exactly: ScoutBox provider test OK.'

def _ordered_ai_configs():
    rows={cfg.provider:cfg for cfg in AIProviderConfig.objects.filter(provider__in=AI_PROVIDER_UI_ORDER)}
    return [rows[p] for p in AI_PROVIDER_UI_ORDER if p in rows]

def _provider_request_settings(request, provider):
    if provider not in AI_PROVIDER_UI_ORDER:
        raise ValueError('Unknown AI provider')
    cfg=AIProviderConfig.objects.filter(provider=provider).first()
    if not cfg:
        base_default,enabled_default=AI_PROVIDER_DEFAULTS[provider]
        cfg=AIProviderConfig.objects.create(provider=provider,base_url=base_default,enabled=enabled_default)
    base_default=AI_PROVIDER_DEFAULTS[provider][0]
    base_url=(request.POST.get('base_url') or cfg.base_url or base_default).strip().rstrip('/')
    if not base_url:
        raise ValueError('Base URL is required.')
    key=''; key_source='not-required'
    if provider!='ollama':
        submitted=(request.POST.get('api_key') or '').strip()
        stored=decrypt(cfg.api_key_enc)
        key=submitted or stored
        key_source='entered on this page' if submitted else ('saved key' if stored else 'missing')
        if not key:
            if cfg.api_key_enc:
                raise ValueError('A saved API key exists but ScoutBox could not decrypt it. Re-enter the API key and save Provider Configuration.')
            raise ValueError('API key is required. Enter a key or save one first.')
    raw=(request.POST.get('max_output_tokens') or '').strip()
    try:
        cap=max(64,min(8192,int(raw))) if raw else int(cfg.max_output_tokens or 8000)
    except Exception:
        cap=int(cfg.max_output_tokens or 8000)
    return cfg,{'enabled':True,'base_url':base_url,'api_key':key,'max_output_tokens':cap},{'key_source':key_source,'has_saved_key':bool(cfg.api_key_enc)}

def _provider_model_catalog(provider, base_url, api_key=''):
    models=[]
    if provider=='ollama':
        for item in ollama_service.list_models(base_url):
            model=str(item.get('name') or item.get('model') or '').strip()
            if model: models.append({'id':model,'label':model})
    elif provider=='openai':
        r=requests.get(base_url.rstrip('/')+'/models',headers={'Authorization':f'Bearer {api_key}'},timeout=20)
        r.raise_for_status()
        for item in (r.json().get('data') or []):
            model=str(item.get('id') or '').strip()
            if model: models.append({'id':model,'label':model})
    elif provider=='gemini':
        token=''
        for _ in range(5):
            params={'pageSize':100}
            if token: params['pageToken']=token
            r=requests.get(base_url.rstrip('/')+'/models',headers={'x-goog-api-key':api_key},params=params,timeout=20)
            r.raise_for_status(); data=r.json()
            for item in (data.get('models') or []):
                methods=item.get('supportedGenerationMethods') or []
                if methods and 'generateContent' not in methods: continue
                model=str(item.get('name') or '').strip()
                if model.startswith('models/'): model=model[7:]
                if model:
                    label=str(item.get('displayName') or model).strip()
                    models.append({'id':model,'label':f'{label} · {model}' if label and label!=model else model})
            token=str(data.get('nextPageToken') or '')
            if not token: break
    elif provider=='openrouter':
        r=requests.get(base_url.rstrip('/')+'/models',headers={'Authorization':f'Bearer {api_key}'},timeout=20)
        r.raise_for_status()
        for item in (r.json().get('data') or []):
            model=str(item.get('id') or '').strip()
            if model:
                label=str(item.get('name') or model).strip()
                models.append({'id':model,'label':f'{label} · {model}' if label and label!=model else model})
    else:
        raise ValueError('Unknown AI provider')
    dedup={}
    for item in models:
        dedup.setdefault(item['id'],item)
    return sorted(dedup.values(),key=lambda row:(row['label'].lower(),row['id'].lower()))

def _provider_auto_test_model(provider, models, configured=''):
    ids=[str(x.get('id') or '').strip() for x in (models or []) if str(x.get('id') or '').strip()]
    preferences={
        'openai':['gpt-5-mini','gpt-4.1-mini','gpt-4o-mini','gpt-5'],
        'gemini':['gemini-3.5-flash-lite','gemini-3.1-flash-lite','gemini-3.5-flash','gemini-3.7-flash','gemini-3.6-flash','gemini-2.5-flash','gemini-2.0-flash'],
        'openrouter':['google/gemini-3.5-flash-lite','google/gemini-3.1-flash-lite','google/gemini-2.5-flash','openai/gpt-4.1-mini','openai/gpt-4o-mini','deepseek/deepseek-chat'],
        'ollama':['qwen3','llama3','gemma3','qwen2.5','mistral'],
    }.get(provider,[])
    lowered=[(x,x.lower()) for x in ids]
    for wanted in preferences:
        for original,low in lowered:
            if low==wanted or low.startswith(wanted+':'):
                return original,'automatic common model'
    for wanted in preferences:
        for original,low in lowered:
            if wanted in low:
                return original,'automatic common model'
    if configured and configured in ids:
        return configured,'configured default'
    if provider=='gemini':
        # Automatic provider resolution stays inside stable Flash-Lite first and prefers
        # the stronger 3.5 Flash-Lite before 3.1 Flash-Lite. Stage-specific resume
        # tailoring can still deliberately select its stronger documented full-Flash model.
        for original,low in lowered:
            if 'flash-lite' in low and not any(x in low for x in ('preview','experimental','exp-')):
                return original,'automatic available Flash-Lite model'
        for original,low in lowered:
            if 'flash' in low and not any(x in low for x in ('preview','experimental','exp-')):
                return original,'automatic available Flash model'
    if provider=='openai':
        for original,low in lowered:
            if low.startswith('gpt-') and not any(x in low for x in ('audio','realtime','image','transcribe','tts')):
                return original,'automatic available GPT model'
    if provider=='openrouter':
        for original,low in lowered:
            if any(x in low for x in ('gemini','gpt','deepseek','claude')) and ':free' not in low:
                return original,'automatic available general model'
    return (ids[0],'automatic first available model') if ids else ('','no model available')

def _cloud_model_quality_score(provider, model):
    """Capability-first score for the strong Cloud Web lane.

    Auto-detect pairs a strong primary with an economical secondary rather than
    spending the strongest model on every routine stage. Non-text/audio/image models are
    excluded here; live web-research probing remains the final eligibility check.
    """
    low=str(model or '').lower()
    if not low or any(x in low for x in ('embedding','audio','realtime','image','tts','transcribe','moderation','live-preview')):
        return -100000
    score=1000
    # Explicit high-capability families. Version bonuses keep newer Gemini Flash releases
    # ordered correctly instead of treating every "gemini-3" model as equivalent.
    for token,bonus in (
        ('gpt-5.6',900),('gpt-5.5',850),('gpt-5.4',800),('gpt-5',700),
        ('gemini-3.7',1400),('gemini-3.6',1250),('gemini-3.5',1050),('gemini-3.1',780),('gemini-3',700),
        ('gemini-2.5-pro',760),('gemini-2.0-pro',700),('claude-opus',850),('claude-sonnet',720),('o3',720),('o4',730),
    ):
        if token in low: score+=bonus
    if 'pro' in low: score+=220
    if 'opus' in low: score+=300
    if 'sonnet' in low: score+=180
    # Small families remain valid economy/fallback choices, but do not win the strong lane.
    for token,penalty in (('nano',620),('mini',420),('lite',420),('flash-lite',560),('flash',260),(':free',650),('/free',650),('small',260)):
        if token in low: score-=penalty
    if any(x in low for x in ('preview','experimental','exp-')): score-=70
    return score


def _cloud_model_economy_score(provider, model):
    """Prefer inexpensive, stable text models for high-volume/simple Cloud stages.

    Gemini has a documented low-cost Flash-Lite lane. The explicit ordering mirrors the
    current paid token economics while still giving a quality floor to newer stable models.
    Other providers use family-size hints and the capability score as a tie-breaker.
    """
    low=str(model or '').lower()
    quality=_cloud_model_quality_score(provider,model)
    if quality <= -100000:
        return -100000
    score=quality//8
    if provider=='gemini':
        # 3.5 Flash-Lite is the current high-throughput Gemini 3 economy lane; 3.1
        # Flash-Lite remains a stable nearby fallback and useful lower-cost bridge.
        ordered=(
            ('gemini-3.1-flash-lite',1800),
            ('gemini-3.5-flash-lite',1750),
            ('gemini-3.5-flash',1100),
            ('gemini-3-flash-preview',1200),
            ('gemini-3.6-flash',1100),
            ('gemini-3.7-flash',1080),
            ('gemini-2.5-flash',1000),
        )
        for token,bonus in ordered:
            if low==token or low.startswith(token+'-'):
                score+=bonus
                break
    else:
        if 'nano' in low: score+=1500
        if 'mini' in low: score+=1250
        if 'lite' in low: score+=1150
        if 'flash' in low: score+=850
        if 'small' in low: score+=700
        if any(x in low for x in (':free','/free')): score+=300
    if any(x in low for x in ('preview','experimental','exp-')): score-=120
    return score


def _cloud_model_candidate_orders(provider, models):
    rows=[str(x.get('id') or '').strip() for x in (models or []) if str(x.get('id') or '').strip()]
    rows=list(dict.fromkeys(rows))
    capable=[m for m in rows if _cloud_model_quality_score(provider,m)>-100000]
    strong=sorted(capable,key=lambda m:(-_cloud_model_quality_score(provider,m),m.lower()))
    economy=sorted(capable,key=lambda m:(-_cloud_model_economy_score(provider,m),-_cloud_model_quality_score(provider,m),m.lower()))
    return strong,economy


DOCUMENTED_CLOUD_AUTODETECT = {
    # Metadata-only fallbacks. Auto-detect never performs a provider request; provider
    # catalogues remain unrestricted for manual selection and Test Selection is the
    # explicit live-capability check.
    'gemini': {
        'discovery_fast': ('gemini-3.5-flash-lite', 'gemini-3.1-flash-lite'),
        'discovery_balanced': ('gemini-3.5-flash-lite', 'gemini-3.1-flash-lite'),
        'discovery_heavy': ('gemini-3.5-flash-lite', 'gemini-3.1-flash-lite'),
        'chatbot': ('gemini-3.5-flash-lite', 'gemini-3.1-flash-lite'),
    },
    'openai': {
        'discovery_fast': ('gpt-5-mini', 'gpt-5-nano'),
        'discovery_balanced': ('gpt-5', 'gpt-5-mini'),
        'discovery_heavy': ('gpt-5', 'gpt-5-mini'),
        'chatbot': ('gpt-5', 'gpt-5-mini'),
    },
    'openrouter': {
        'discovery_fast': ('google/gemini-3.5-flash-lite', 'google/gemini-3.1-flash-lite'),
        'discovery_balanced': ('google/gemini-3.5-flash-lite', 'google/gemini-3.1-flash-lite'),
        'discovery_heavy': ('google/gemini-3.5-flash-lite', 'google/gemini-3.1-flash-lite'),
        'chatbot': ('google/gemini-3.5-flash-lite', 'google/gemini-3.1-flash-lite'),
    },
}

# Gemini Auto-detect is intentionally quality-first within the Flash-Lite tier. Routine
# Discovery, drafting, Q/A and import inference use 3.5 Flash-Lite Primary with 3.1
# Flash-Lite as same-tier Failover, while still preventing automatic routing onto premium
# full Flash/Pro models. Chatbot follows the same Flash-Lite order. Resume tailoring is
# the sole automatic full-Flash quality exception; users can still override every route manually.
DOCUMENTED_GEMINI_DISCOVERY_STAGE_AUTODETECT = {
    'url_scrape':          ('gemini-3.5-flash-lite', 'gemini-3.1-flash-lite'),
    'first_filter':        ('gemini-3.5-flash-lite', 'gemini-3.1-flash-lite'),
    'freshness':           ('gemini-3.5-flash-lite', 'gemini-3.1-flash-lite'),
    'company_enrichment':  ('gemini-3.5-flash-lite', 'gemini-3.1-flash-lite'),
    'page_summarization':  ('gemini-3.5-flash-lite', 'gemini-3.1-flash-lite'),
    'jd_analysis':         ('gemini-3.5-flash-lite', 'gemini-3.1-flash-lite'),
    'cold_contact':        ('gemini-3.5-flash-lite', 'gemini-3.1-flash-lite'),
    'email_draft':         ('gemini-3.5-flash-lite', 'gemini-3.1-flash-lite'),
    'cv_tailoring':        ('gemini-3.5-flash',      'gemini-3.1-flash-lite'),
    'question_answers':    ('gemini-3.5-flash-lite', 'gemini-3.1-flash-lite'),
    'import_inference':    ('gemini-3.5-flash-lite', 'gemini-3.1-flash-lite'),
}
DOCUMENTED_OPENROUTER_GEMINI_DISCOVERY_STAGE_AUTODETECT = {
    stage:(f'google/{primary}',f'google/{secondary}')
    for stage,(primary,secondary) in DOCUMENTED_GEMINI_DISCOVERY_STAGE_AUTODETECT.items()
}

DOCUMENTED_CLOUD_FAST_STAGES = {'url_scrape','first_filter','freshness'}
DOCUMENTED_CLOUD_HEAVY_STAGES = {'cv_tailoring','question_answers','import_inference'}

def _documented_cloud_pair(provider, purpose='discovery', stage=''):
    provider=str(provider or '').strip().lower()
    stage=str(stage or '').strip()
    if purpose=='chatbot':
        key='chatbot'
        pair=(DOCUMENTED_CLOUD_AUTODETECT.get(provider) or {}).get(key)
    elif provider=='gemini' and stage in DOCUMENTED_GEMINI_DISCOVERY_STAGE_AUTODETECT:
        pair=DOCUMENTED_GEMINI_DISCOVERY_STAGE_AUTODETECT[stage]
    elif provider=='openrouter' and stage in DOCUMENTED_OPENROUTER_GEMINI_DISCOVERY_STAGE_AUTODETECT:
        pair=DOCUMENTED_OPENROUTER_GEMINI_DISCOVERY_STAGE_AUTODETECT[stage]
    else:
        if stage in DOCUMENTED_CLOUD_FAST_STAGES:
            key='discovery_fast'
        elif stage in DOCUMENTED_CLOUD_HEAVY_STAGES:
            key='discovery_heavy'
        else:
            key='discovery_balanced'
        pair=(DOCUMENTED_CLOUD_AUTODETECT.get(provider) or {}).get(key)
    if not pair or len(pair)!=2 or not pair[0] or not pair[1] or pair[0]==pair[1]:
        raise ValueError('No documented ScoutBox auto-detect defaults are available for this Cloud provider.')
    return pair[0],pair[1]


def _ollama_parameter_billions(item):
    """Best-effort comparable Ollama model size for Chatbot auto-selection only."""
    if not isinstance(item,dict):
        item={}
    details=item.get('details') if isinstance(item.get('details'),dict) else {}
    # Use the advertised model/name tag first so a model named ``:7b`` remains in
    # the 7B automatic class even if Ollama reports an internal count such as 7.6B.
    candidates=[item.get('model'),item.get('name'),details.get('parameter_size'),item.get('parameter_size')]
    for raw in candidates:
        text=str(raw or '').strip().lower()
        # Ollama commonly reports values such as 7.6B, 14B, 70.6B or model tags like :32b.
        matches=re.findall(r'(?<![a-z0-9])(\d+(?:\.\d+)?)\s*([bm])\b',text)
        if not matches:
            matches=re.findall(r'[:_-](\d+(?:\.\d+)?)([bm])(?:\b|[_-])',text)
        if matches:
            value,unit=matches[-1]
            try:
                number=float(value)
                return number if unit=='b' else number/1000.0
            except Exception:
                pass
    try:
        size=max(0,int(item.get('size') or 0))
        if size:
            # Quantized file size is not parameter count, but is a useful final ordering fallback.
            return size/1_000_000_000.0/0.55
    except Exception:
        pass
    return 0.0


def _ollama_chatbot_candidates():
    """Installed text-generation Ollama models ordered largest/highest first."""
    try:
        installed=list(ollama_service.diagnostics().get('installed') or [])
    except Exception:
        installed=[]
    rows=[]; seen=set()
    for item in installed:
        model=str((item or {}).get('name') or (item or {}).get('model') or '').strip()
        low=model.lower()
        if not model or model in seen or any(x in low for x in ('embed','embedding','rerank')):
            continue
        seen.add(model)
        rows.append({'model':model,'billions':_ollama_parameter_billions(item),'size':int((item or {}).get('size') or 0)})
    rows.sort(key=lambda row:(-row['billions'],-row['size'],row['model'].lower()))
    return rows


def _auto_select_chatbot_routes(provider=''):
    """Prepare Chatbot Primary/Secondary defaults for one explicitly chosen provider.

    Ollama uses the same hardware-aware model ceiling as Local Discovery. Cloud providers
    use documented model-family defaults only; the provider model dropdowns remain fully
    manual and Test Selection performs live verification of both routes.
    """
    provider=str(provider or '').strip().lower()
    if provider not in {'ollama','openai','gemini','openrouter'}:
        raise ValueError('Choose an enabled Chatbot provider for Auto-detect.')
    if not AIProviderConfig.objects.filter(provider=provider,enabled=True).exists():
        raise ValueError('Enable the selected Chatbot provider in Provider Configuration first.')

    if provider=='ollama':
        cap=automatic_ollama_model_cap_billions()
        installed=_ollama_chatbot_candidates()
        local=[row for row in installed if row.get('billions') and float(row['billions'])<=cap]
        if not local:
            raise ValueError(f'No installed generation model fits the {cap:g}B automatic hardware limit. You can still select a larger Ollama model manually.')
        # Match the Discovery policy: use the strongest model at/below the automatic ceiling,
        # then prefer a roughly 4B fallback at a 7B ceiling. On other hardware tiers use the
        # closest smaller installed model. Manual choices are never restricted by this policy.
        primary=max(local,key=lambda row:(float(row.get('billions') or 0),int(row.get('size') or 0),row['model'].lower()))
        smaller=[row for row in local if row['model']!=primary['model'] and float(row.get('billions') or 0)<float(primary.get('billions') or 0)]
        if not smaller:
            raise ValueError(f'Chatbot Local Auto-detect needs a second installed generation model below {primary["model"]}. You can still configure Primary and Secondary manually.')
        fallback_target=4.0 if cap>=7.0 and float(primary.get('billions') or 0)>=6.0 else max(0.0,float(primary.get('billions') or 0)*0.62)
        secondary=min(smaller,key=lambda row:(abs(float(row.get('billions') or 0)-fallback_target),-float(row.get('billions') or 0),row['model'].lower()))
        return {
            'provider':'ollama','runtime':'local',
            'primary':{'provider':'ollama','model':primary['model']},
            'secondary':{'provider':'ollama','model':secondary['model']},
            'message':f"Auto-detected Ollama Chatbot defaults within the {cap:g}B hardware-aware limit: Primary {primary['model']}; Secondary {secondary['model']}. Save config to apply them.",
        }

    primary,secondary=_documented_cloud_pair(provider,'chatbot')
    label=dict(AIProviderConfig.PROVIDERS).get(provider,provider)
    return {
        'provider':provider,'runtime':'cloud',
        'primary':{'provider':provider,'model':primary},
        'secondary':{'provider':provider,'model':secondary},
        'message':'',
    }


def _json_probe_ok(text):
    raw=str(text or '').strip()
    m=re.search(r'```(?:json)?\s*(.*?)```',raw,re.I|re.S)
    if m: raw=m.group(1).strip()
    try:
        data=json.loads(raw)
    except Exception:
        return False
    return isinstance(data,dict) and data.get('ok') is True and str(data.get('echo') or '').strip().lower()=='scoutbox'


def _provider_failure_details(exc, provider, model, override, cfg, meta, selection='explicit', *, tokens_in=0, tokens_out=0, model_count=None):
    response=getattr(exc,'response',None)
    status=getattr(response,'status_code',None)
    provider_detail=''; server_response=''; request_url=''; request_method=''
    if response is not None:
        try:
            request_url=str(getattr(response,'url','') or '')
            request_method=str(getattr(getattr(response,'request',None),'method','') or '')
        except Exception:
            pass
        try:
            server_response=str(response.text or '')[:2400]
        except Exception:
            server_response=''
        try:
            payload=response.json()
            if isinstance(payload,dict):
                err=payload.get('error')
                if isinstance(err,dict): provider_detail=str(err.get('message') or err.get('status') or '')
                else: provider_detail=str(err or payload.get('message') or '')
        except Exception:
            provider_detail=server_response[:700]
    secret=str((override or {}).get('api_key') or '')
    if secret:
        provider_detail=provider_detail.replace(secret,'[REDACTED]')
        server_response=server_response.replace(secret,'[REDACTED]')
    text=str(exc or '').strip()
    low=(provider_detail or server_response or text).lower()
    hint=''
    if status in (401,403) or any(x in low for x in ('api key','unauthorized','permission denied','forbidden','authentication')):
        hint='Check that the saved API key is valid for this provider/project and that the required API/billing access is enabled.'
    elif status==404 or 'not found' in low:
        hint='The selected model or Base URL may not support this request. Test configuration again and retry with a model returned by the provider.'
    elif status==429 or any(x in low for x in ('quota','rate limit','resource exhausted')):
        hint='The provider reported a quota or rate limit. Check provider billing/quota and ScoutBox Cloud AI limits.'
    elif any(x in low for x in ('timeout','timed out','connection','dns','ssl')):
        hint='Check network access from the ScoutBox container and verify the provider Base URL.'
    elif provider=='gemini':
        hint='For Gemini, confirm the saved key belongs to the intended Google AI Studio/Cloud project, billing/model access is enabled, and the tested model supports generateContent.'
    return {
        'provider':provider,'model':model,'model_selection':selection,'base_url':(override or {}).get('base_url') or '',
        'credential_source':meta.get('key_source') if provider!='ollama' else 'not required',
        'saved_key_present':bool(meta.get('has_saved_key')) if provider!='ollama' else False,
        'error_type':exc.__class__.__name__ if exc else 'Error','http_status':status,'provider_detail':provider_detail[:700],
        'server_response':server_response[:2400],'request_url':request_url[:900],'request_method':request_method[:20],
        'tokens_in':max(0,int(tokens_in or 0)),'tokens_out':max(0,int(tokens_out or 0)),
        'model_count':model_count,'hint':hint,'configured_default':cfg.default_model or '',
    }

CV_DISCOVERY_TEMPLATE_KEY='cv-discovery'
CV_DISCOVERY_TEMPLATE_NAME='CV Discovery'

def _cv_discovery_campaign_form():
    """Return the non-deletable Resume/Profile-driven starter used by New Campaign.

    This is intentionally code-defined rather than a CampaignTemplate row so Maintenance
    cleanup cannot remove the basic discovery starting point.
    """
    profile=Profile.objects.get_or_create(pk=1)[0]
    scope=dict(profile.scope_json or {})
    roles=[]; tech=[]
    try:
        search_profile=build_search_profile()
        roles=[str(x.get('role') or '').strip() for x in (search_profile.get('role_families') or []) if str(x.get('role') or '').strip()]
        tech=[str(x.get('term') or '').strip() for x in (search_profile.get('skills') or []) if str(x.get('term') or '').strip()]
    except Exception:
        roles=[]; tech=[]
    if not roles:
        roles=[str(x).strip() for x in (scope.get('likely_roles') or []) if str(x).strip()]
    if not tech:
        tech=[str(x).strip() for x in (scope.get('cv_concepts') or []) if str(x).strip()]
    languages=[str(x).strip() for x in (scope.get('preferred_languages') or []) if str(x).strip()]
    return {
        'name':'','template':CV_DISCOVERY_TEMPLATE_NAME,
        'locations':profile.operating_locations or ([profile.operating_location] if profile.operating_location else ['Singapore']),
        'roles':list(dict.fromkeys(roles))[:16],
        'tech':list(dict.fromkeys(tech)),
        'engagement':list(CAMPAIGN_OPTIONS['engagement']),
        'sizes':list(CAMPAIGN_OPTIONS['sizes']),
        'languages':list(dict.fromkeys(languages))[:12],
        'negative_constraints':'',
        'extra_text':'Resume-first discovery using the Candidate Profile and active Resumes as primary evidence.',
        'recency_days':30,'source_names':[],'queries_per_rotation':'',
    }

def _picked(request,name,advanced=''):
    vals=[x.strip() for x in request.POST.getlist(name) if x.strip()]
    if advanced.strip(): vals += [x.strip() for x in re.split(r'[,;\n]+',advanced) if x.strip()]
    return ', '.join(dict.fromkeys(vals))

NAV=[item for _group,items in NAV_GROUPS for item in items]



_COUNTRY_CANONICAL_ALIASES={
    'United States': {'United States','United States of America','USA','US','U.S.A.','U.S.'},
    'United Kingdom': {'United Kingdom','UK','U.K.','GB','Great Britain','Britain'},
    'United Arab Emirates': {'United Arab Emirates','UAE'},
    'South Korea': {'South Korea','Republic of Korea','Korea, Republic of'},
}

def _structured_country_for_filter(value):
    raw=' '.join(str(value or '').split()).strip()
    if not raw or raw[0] not in '[{':
        return None
    try:
        parsed=json.loads(raw)
    except Exception:
        return ''
    aliases={alias.casefold():canonical for canonical,items in _COUNTRY_CANONICAL_ALIASES.items() for alias in items}
    found=[]
    def add(candidate):
        token=' '.join(str(candidate or '').split()).strip(' \"\'.:,;{}[]()')
        if not token:
            return
        token=aliases.get(token.casefold(),token)
        for country in COUNTRIES:
            if token.casefold()==country.casefold() and country not in found:
                found.append(country)
                return
    def walk(obj):
        if isinstance(obj,dict):
            typ=str(obj.get('@type') or obj.get('type') or '').casefold()
            if 'country' in typ:
                add(obj.get('name') or obj.get('alternateName'))
            for key in ('addressCountry','country','countryCode'):
                if key in obj:
                    val=obj.get(key)
                    if isinstance(val,(dict,list)):
                        walk(val)
                    else:
                        add(val)
            for val in obj.values():
                if isinstance(val,(dict,list)):
                    walk(val)
        elif isinstance(obj,list):
            for item in obj:
                walk(item)
        elif isinstance(obj,str):
            add(obj)
    walk(parsed)
    return found[0] if len(found)==1 else ''


def _canonical_country_name(value):
    """Return a canonical country or recruiter-region label from location text."""
    labels=location_labels(value)
    if len(labels)==1:
        return labels[0]
    raw=' '.join(str(value or '').split()).strip()
    if not raw:
        return ''
    structured=_structured_country_for_filter(raw)
    if structured is not None:
        return structured
    if raw.casefold().strip(' .-_/') in {'unknown','not set','not specified','unspecified','n/a','na','none','null','tbd','other','others'}:
        return ''
    folded=raw.casefold()
    for canonical,aliases in _COUNTRY_CANONICAL_ALIASES.items():
        if folded in {x.casefold() for x in aliases}:
            return canonical
    for country in COUNTRIES:
        if folded==country.casefold():
            return country
    # Company research may retain city/region detail. Prefer a recognized country suffix
    # so Address Book rows and country filters stay concise and flaggable.
    candidates=[]
    for country in COUNTRIES:
        candidates.append((country,country))
    for canonical,aliases in _COUNTRY_CANONICAL_ALIASES.items():
        candidates.extend((alias,canonical) for alias in aliases)
    for candidate,canonical in sorted(candidates,key=lambda row:len(row[0]),reverse=True):
        if re.search(r'(?i)(?:^|[,;|·/\s]|[–—]\s*)'+re.escape(candidate)+r'\s*$',raw):
            return canonical
    return ''

def _country_filter_values(value):
    canonical=_canonical_country_name(value)
    aliases=_COUNTRY_CANONICAL_ALIASES.get(canonical)
    return sorted(aliases) if aliases else [canonical]

def _country_condition(field, values):
    condition=Q()
    for item in values:
        condition |= Q(**{f'{field}__iexact':item})
        for sep in (', ', '; ', ' | ', ' · ', ' — ', ' – ', '/'):
            condition |= Q(**{f'{field}__istartswith':item+sep})
            condition |= Q(**{f'{field}__iendswith':sep+item})
            condition |= Q(**{f'{field}__icontains':sep+item+sep})
    return condition

def _apply_country_filter(qs, field, value):
    canonical=_canonical_country_name(value)
    if not canonical:
        return qs
    values=_country_filter_values(canonical)
    # Opportunity location filters must follow the same role-location-first rule as
    # display. Older releases left expanded region-country text in Opportunity.country;
    # while the 0.11.2 repair is pending, do not let that stale legacy value keep a
    # record under an unrelated country filter. Use role_location when present, and
    # fall back to the legacy country field only for rows without a role location.
    if field=='country' and getattr(getattr(qs,'model',None),'__name__','')=='Opportunity':
        malformed_role = (
            Q(role_location__startswith='[') |
            Q(role_location__startswith='{') |
            Q(role_location__icontains='"@type"') |
            Q(role_location__icontains="'@type'")
        )
        role_condition=_country_condition('role_location',values) & ~malformed_role
        legacy_condition=_country_condition('country',values) & (Q(role_location__isnull=True)|Q(role_location=''))
        return qs.filter(role_condition|legacy_condition)
    return qs.filter(_country_condition(field,values))

def _country_filter_options(qs, field):
    """Countries/regions actually represented by the current list dataset, with counts.

    Opportunity dropdowns use role_location first for the same reason row rendering does:
    stale expanded legacy country strings must not advertise bogus country facets.
    """
    if field=='country' and getattr(getattr(qs,'model',None),'__name__','')=='Opportunity':
        counts={}
        rows=qs.order_by().values('pk','country','role_location','remote_text','locations').distinct()
        for row in rows.iterator(chunk_size=1000):
            record=SimpleNamespace(country=row.get('country') or '', role_location=row.get('role_location') or '', remote_text=row.get('remote_text') or '', locations=row.get('locations') or [])
            for item in record_location_items(record):
                name=item.get('label')
                if name:
                    counts[name]=counts.get(name,0)+1
        return [{'value':name,'label':name,'count':counts[name]} for name in sorted(counts,key=str.casefold)]
    rows=qs.exclude(**{f'{field}__isnull':True}).exclude(**{field:''}).order_by().values(field).annotate(n=Count('pk',distinct=True))
    counts={}
    for row in rows:
        for name in location_labels(row.get(field)):
            counts[name]=counts.get(name,0)+int(row.get('n') or 0)
    return [{'value':name,'label':name,'count':counts[name]} for name in sorted(counts,key=str.casefold)]



def _prune_zero_roundtrip_country_options(options, base_qs, field, *, count_fn=None):
    """Keep only country/region facets that the same filter can actually show.

    Older rows can retain structured location arrays or normalized labels that are
    counted by display helpers but are not matched by the SQL filter path.  Do not
    advertise a facet such as APAC (2) if clicking it would render an empty list.
    """
    pruned=[]
    for opt in options or []:
        value=str(opt.get('value') or opt.get('label') or '').strip()
        if not value:
            continue
        try:
            filtered=_apply_country_filter(base_qs, field, value)
            count=int(count_fn(filtered) if count_fn else filtered.distinct().count())
        except Exception:
            count=int(opt.get('count') or 0)
        if count > 0:
            row=dict(opt); row['count']=count; pruned.append(row)
    return pruned

def _country_filter_total(options):
    """Return the exact number represented by visible country choices.

    Blank, placeholder and unrecognized location strings are intentionally absent from
    location dropdowns, so they must not inflate the corresponding ``All locations`` count.
    """
    return sum(int(row.get('count') or 0) for row in (options or []))

_EMAIL_IN_TEXT_RE=re.compile(r'(?i)(?<![A-Z0-9._%+\-])([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})(?![A-Z0-9._%+\-])')

def _repair_known_contact_email(record):
    """Repair a blank/unsafe structured contact only from evidence on this record.

    Never copy a contact from a sibling Opportunity/Hidden Lead merely because its
    company string matches. Aggregator-hosted postings can otherwise make unrelated
    employers look like one company and permanently spread an address between records.
    """
    values=[]
    for field in ('note','description','raw_search_snippet','summary','match_summary','evidence','evidence_translation'):
        if hasattr(record,field): values.append(getattr(record,field,'') or '')
    for field in ('extracted_facts','company_intel'):
        if hasattr(record,field):
            try: values.append(json.dumps(getattr(record,field,None) or {},ensure_ascii=False,default=str))
            except Exception: pass
    company=' '.join(str(getattr(record,'company','') or '').split()).strip()
    source_url=str(getattr(record,'target_url','') or getattr(record,'source_url','') or getattr(record,'canonical_url','') or getattr(record,'url','') or getattr(record,'search_url','') or '').strip()

    existing=clean_contact_email(getattr(record,'contact_email','') or '')
    if existing:
        unsafe=is_non_contact_address(existing) or any(contact_email_has_non_contact_context(existing,text) for text in values)
        if unsafe:
            type(record).objects.filter(pk=record.pk).update(contact_email='')
            record.contact_email=''
        else:
            try:
                validate_email(existing)
                raw=str(getattr(record,'contact_email','') or '')
                normalized=(existing != raw)
                if normalized:
                    type(record).objects.filter(pk=record.pk).update(contact_email=existing)
                    record.contact_email=existing
                # Older records can already contain a valid structured email yet lack an
                # Address Book row because an earlier host-as-company ownership check
                # rejected the promotion. Retry only when no active contact exists; the
                # shared promotion helper can now recover a strongly evidenced employer.
                if normalized or not Contact.objects.filter(email__iexact=existing,deleted_at__isnull=True).exists():
                    try:
                        promote_record_contact_to_addressbook(record,source='Retained discovery evidence',texts=values,confidence=76,queue_research=False)
                    except Exception:
                        pass
                return normalized
            except ValidationError:
                pass
            return False

    candidates=[]
    for text in values:
        for match in _EMAIL_IN_TEXT_RE.findall(str(text or '')):
            email=clean_contact_email(match.strip('.,;:<>[](){}'))
            try: validate_email(email)
            except ValidationError: continue
            if not assignable_contact_email(email,text): continue
            if not contact_ownership_plausible(email,company,source_url,text): continue
            if email not in candidates: candidates.append(email)
    if not candidates:
        return False
    # Prefer a person/relevant mailbox when available, while still accepting a useful
    # generic address when it is the only concrete contact evidenced on this same record.
    candidates.sort(key=lambda x:(is_generic(x), x))
    record.contact_email=candidates[0]
    type(record).objects.filter(pk=record.pk,contact_email='').update(contact_email=record.contact_email)
    try:
        promote_record_contact_to_addressbook(record,source='Retained discovery evidence',texts=values,confidence=76,queue_research=False)
    except Exception:
        pass
    return True

def ctx(request, active, title, **kw):
    group,label=NAV_PARENT.get(active,('',title))
    breadcrumbs=kw.pop('breadcrumbs',None)
    if breadcrumbs is None:
        breadcrumbs=[]
        if active!='dashboard':
            breadcrumbs.append({'label':'ScoutBox','route':'dashboard'})
            if group and label!=title:
                breadcrumbs.append({'label':label,'route':active})
            elif group:
                breadcrumbs.append({'label':group,'route':None})
            if not breadcrumbs or breadcrumbs[-1].get('label')!=title:
                breadcrumbs.append({'label':title,'route':None})
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    recycle_bin_count=(Campaign.objects.filter(deleted_at__isnull=False).count()+CampaignTemplate.objects.filter(deleted_at__isnull=False).count()+Opportunity.objects.filter(user_deleted=True).count()+Application.objects.filter(deleted_at__isnull=False).count()+CompanyLead.objects.filter(user_deleted=True,deleted_at__isnull=False).count()+Contact.objects.filter(deleted_at__isnull=False).count()+FacebookPage.objects.filter(deleted_at__isnull=False).count()+TrackingLink.objects.filter(deleted_at__isnull=False).count()+SourceBlacklist.objects.filter(deleted_at__isnull=False).count())
    campaign_total_count=Campaign.objects.filter(deleted_at__isnull=True).count()
    campaign_running_count=Campaign.objects.filter(deleted_at__isnull=True,enabled=True).count()
    if str(ps.discovery_mode or '').lower()=='cloud_web':
        try:
            if not has_usable_cloud_web_model():
                raise RuntimeError('One or more Cloud Web stages is not configured.')
            route=cloud_discovery_route(stage='url_scrape'); ai_readiness={'ready':True,'reason':'Cloud Web ready','provider':route.get('provider',''),'model':route.get('model','')}
        except Exception as exc:
            ai_readiness={'ready':False,'reason':str(exc) or 'Cloud Web unavailable.'}
    else:
        try: ai_readiness=ai_compute_readiness()
        except Exception: ai_readiness={'ready':False,'reason':'AI readiness unavailable.'}
    base={
        'nav_items':NAV,'nav_groups':NAV_GROUPS,'active_nav':active,'page_title':title,
        'portal_settings':ps,'attention':_attention_snapshot(ps),'recycle_bin_count':recycle_bin_count,
        'campaign_total_count':campaign_total_count,'campaign_running_count':campaign_running_count,
        'breadcrumbs':breadcrumbs,'countries':COUNTRIES,'currencies':CURRENCIES,'ai_readiness':ai_readiness,'chatbot_summary':_chatbot_summary(),
    }
    base.update(kw)
    return base


def _safe_int(value, default=0):
    try: return int(value)
    except (TypeError,ValueError): return default

def _q(request):
    return request.GET.get('q','').strip()


def _show_deleted_setting(request, list_key):
    """Return the session-persistent recycle-bin visibility for one list view.

    An explicit ``show_deleted=1`` or ``show_deleted=0`` updates the preference.
    Requests without the parameter inherit the preference until the authenticated
    session ends (normally logout).  Each list keeps an independent state.
    """
    key='scoutbox_show_deleted_'+re.sub(r'[^a-z0-9_]+','_',str(list_key or '').casefold()).strip('_')
    param='show_deleted'
    alt='show_deleted_'+re.sub(r'[^a-z0-9_]+','_',str(list_key or '').casefold()).strip('_')
    if alt in request.GET:
        param=alt
    if param in request.GET:
        raw=str(request.GET.get(param) or '').strip().casefold()
        enabled=raw in {'1','true','yes','on'}
        try:
            request.session[key]=enabled
            request.session.modified=True
        except Exception:
            pass
        return enabled
    try:
        return bool(request.session.get(key,False))
    except Exception:
        return False


def _display_domain(value):
    value=str(value or '').strip()
    if not value:
        return ''
    try:
        parsed=urlparse(value if '://' in value else 'https://'+value)
        return (parsed.netloc or parsed.path).lower().split('@')[-1].split(':')[0].removeprefix('www.')
    except Exception:
        return ''


def _engine_from_url(value):
    host=_display_domain(value)
    providers=(
        ('google.', 'Google'), ('bing.com', 'Bing'), ('duckduckgo.com', 'DuckDuckGo'),
        ('yandex.', 'Yandex'), ('baidu.com', 'Baidu'), ('naver.com', 'Naver'),
        ('search.yahoo.', 'Yahoo Search'), ('mojeek.com', 'Mojeek'), ('startpage.com', 'Startpage'),
        ('ecosia.org', 'Ecosia'), ('search.brave.com', 'Brave Search'),
    )
    for needle,label in providers:
        if needle in host:
            return label
    return ''


def _meaningful_source_name(source):
    name=str(getattr(source,'name','') or '').strip()
    if not name or name.lower() in {'source','website','web','unknown','direct'}:
        return ''
    short={'Gemini Web Discovery':'Gemini','OpenAI Web Discovery':'OpenAI','OpenRouter Web Discovery':'OpenRouter'}
    return short.get(name,name)


def _lead_source_label(lead):
    return (_meaningful_source_name(getattr(lead,'source',None)) or _engine_from_url(getattr(lead,'search_url',''))
            or _display_domain(getattr(lead,'target_url','') or getattr(lead,'source_url','')))


def _opportunity_source_label(opportunity):
    label=(_meaningful_source_name(getattr(opportunity,'source',None)) or _engine_from_url(getattr(opportunity,'search_url',''))
           or _display_domain(getattr(opportunity,'target_url','') or getattr(opportunity,'canonical_url','') or getattr(opportunity,'url','')))
    contact=(getattr(opportunity,'contact_email','') or '').strip().lower()
    if not contact:
        contact=_display_domain(getattr(opportunity,'target_url','') or getattr(opportunity,'canonical_url','') or getattr(opportunity,'url','')).lower()
    if label and label.strip().lower()==contact:
        return ''
    return label


def _decorate_opportunity_sources(rows):
    for item in rows:
        item.display_source=_opportunity_source_label(item)
    return rows


def _page(request, qs, default=50, allowed=(25,50,100,200)):
    try:
        per=int(request.GET.get('per_page') or default)
    except Exception:
        per=default
    if per not in allowed:
        per=default
    pager=Paginator(qs,per)
    page=pager.get_page(request.GET.get('page') or 1)
    return page, per


def _opportunity_text_source(opportunity):
    facts=opportunity.extracted_facts or {}
    # Raw text must be content retrieved from the target page. Search snippets and
    # AI summaries are discovery evidence, not website text.
    source=(opportunity.description or '').strip()
    if source:
        return source
    raw=str(facts.get('description_html') or '')
    if raw:
        source=re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', raw))).strip()
        if source:
            return source
    return ''


def _same_url(a,b):
    return bool(a and b and normalized_url(a)==normalized_url(b))


def _clean_url_for_blacklist(raw):
    try:
        return pattern_for_url(raw or '')
    except Exception:
        return ''


def _blacklist_display_name(row):
    return (getattr(row,'domain','') or getattr(row,'label','') or 'blacklist rule').strip()


def _blacklist_reason_suffix(row):
    domain=(getattr(row,'domain','') or '').strip()
    label=(getattr(row,'label','') or '').strip()
    return domain or (f'company {label}' if label else 'blacklist rule')


def _opportunity_blacklist_label(opp):
    """Return the exact company name to blacklist for an Opportunity.

    Opportunity rows can come from aggregators/job boards where the source host is
    not the employer.  To avoid hiding unrelated listings from the same board,
    Opportunity blacklist actions are company-name-only.
    """
    candidate=company_blacklist_candidate(opp)
    return candidate['company'][:255] if candidate.get('valid') else ''


def _hidden_lead_blacklist_label(lead):
    """Return the company or safe direct domain to blacklist for a Hidden Lead."""
    candidate=blacklist_candidate_for_record(lead, allow_domain_only=True)
    if candidate.get('valid'):
        return (candidate.get('company') or candidate.get('domain') or '')[:255]
    return ''


def _blacklist_label_duplicate_qs(label, exclude_pk=None):
    key=normalize_label(label)
    qs=SourceBlacklist.objects.filter(domain='',deleted_at__isnull=True)
    if exclude_pk:
        qs=qs.exclude(pk=exclude_pk)
    return [row for row in qs.only('pk','label') if normalize_label(row.label)==key]


def _upsert_blacklist_rule(domain='', label='', reason='Manually blacklisted', scope='all', *, row_id=None, preserve_enabled=False, allow_short_label=False):
    domain=normalize_pattern(domain)
    label=str(label or '').strip()[:255]
    scope=(scope or 'all').strip()
    if scope not in dict(SourceBlacklist.SCOPE):
        scope='all'
    if domain and is_aggregator_blacklist_domain(domain):
        if valid_company_blacklist_label(label,allow_short=allow_short_label):
            domain=''
        else:
            raise ValueError(f'Job-board and aggregator domains cannot be blacklisted. Enter a Company Name of at least {LABEL_BLACKLIST_MIN_CHARS} characters instead.')
    if not domain and not valid_company_blacklist_label(label,allow_short=allow_short_label):
        if label and len(normalize_label(label)) < LABEL_BLACKLIST_MIN_CHARS:
            raise ValueError(f'Company names shorter than {LABEL_BLACKLIST_MIN_CHARS} characters require a verified company domain.')
        raise ValueError(f'Enter a domain, or enter a valid Company Name of at least {LABEL_BLACKLIST_MIN_CHARS} characters.')
    if domain and (len(domain)<4 or '.' not in domain):
        raise ValueError('Enter a valid domain, for example example.com.')
    if not label and domain:
        label=domain
    reason=clean_blacklist_reason(reason)[:500] or 'Manually blacklisted'
    if row_id:
        row=SourceBlacklist.objects.filter(pk=row_id,deleted_at__isnull=True).first()
        if row is None:
            raise ValueError('Blacklist entry was not found.')
        duplicate=(SourceBlacklist.objects.filter(domain=domain,deleted_at__isnull=True).exclude(pk=row.pk).first() if domain else None)
        if duplicate:
            raise ValueError(f'{domain} is already on the blacklist.')
        if not domain and _blacklist_label_duplicate_qs(label,row.pk):
            raise ValueError(f'{label} is already on the blacklist.')
        created=False
    else:
        if domain:
            row=SourceBlacklist.objects.filter(domain=domain).first()
            created=row is None
            row=row or SourceBlacklist(domain=domain)
        else:
            matches=_blacklist_label_duplicate_qs(label)
            row=matches[0] if matches else None
            created=row is None
            row=row or SourceBlacklist(domain='')
    enabled=True if not preserve_enabled else bool(row.enabled)
    row.deleted_at=None; row.domain=domain; row.label=label; row.reason=reason; row.scope=scope; row.enabled=enabled
    if row.pk:
        row.save(update_fields=['deleted_at','domain','label','reason','scope','enabled'])
    else:
        row.save()
    return row,created


def _blacklist_selected_opportunities(ids):
    rows=list(Opportunity.objects.filter(pk__in=ids,suppressed=False,user_deleted=False))
    added=0; skipped=0; row_ids=[]; affected_ids=[]
    for opp in rows:
        candidate=company_blacklist_candidate(opp)
        label=candidate.get('company','') if candidate.get('valid') else ''
        if not label:
            skipped+=1; continue
        try:
            row,created=_upsert_blacklist_rule('',label,'Added from Opportunities','all',allow_short_label=bool(candidate.get('domain')))
        except ValueError:
            skipped+=1; continue
        row_ids.append(row.pk); affected_ids.append(opp.pk); added+=1
    if added:
        now=timezone.now()
        Opportunity.objects.filter(pk__in=affected_ids,suppressed=False,user_deleted=False).update(suppressed=True,user_deleted=True,deleted_at=now,is_read=True,rejection_reason='Blocked by user blacklist.',updated_at=now)
        Application.objects.filter(opportunity_id__in=affected_ids,deleted_at__isnull=True).update(deleted_at=now,is_read=True)
        try: enforce_active_blacklist()
        except Exception: pass
    return {'added':added,'skipped':skipped,'blacklist_ids':row_ids}


def _parse_user_date(raw):
    raw=(raw or '').strip()
    for fmt in ('%d/%m/%Y','%Y-%m-%d'):
        try: return timezone.make_aware(datetime.strptime(raw,fmt))
        except Exception: pass
    return None


def _validated_custom_date_bounds(raw_from, raw_to):
    """Validate a user-entered date range and return inclusive-day query bounds.

    Custom ranges require both dates, From strictly before To, and neither date may
    be later than tomorrow in the application's local timezone.  Allowing one day
    beyond the local date avoids false future-date rejections around timezone
    boundaries between the browser and server.  The returned end is exclusive so
    the selected To date is included in full.
    """
    start=_parse_user_date(raw_from)
    parsed_to=_parse_user_date(raw_to)
    if not start or not parsed_to:
        return None,None,False
    max_date=timezone.localdate()+timedelta(days=1)
    if start.date()>max_date or parsed_to.date()>max_date or start>=parsed_to:
        return None,None,False
    return start,parsed_to+timedelta(days=1),True


def _period_bounds(request):
    """Statistics uses the same rolling ranges as Dashboard and Resource Usage."""
    raw=(request.GET.get('period') or '24h').strip().lower()
    aliases={'today':'24h','72h':'3d','week':'7d','month':'30d','year':'all'}
    period=aliases.get(raw,raw)
    now=timezone.now(); end=None
    rolling={
        '1h':timedelta(hours=1),'3h':timedelta(hours=3),'6h':timedelta(hours=6),
        '12h':timedelta(hours=12),'24h':timedelta(hours=24),'3d':timedelta(days=3),
        '7d':timedelta(days=7),'14d':timedelta(days=14),'30d':timedelta(days=30),
    }
    if period in rolling:
        start=now-rolling[period]; end=now
    elif period=='custom':
        start,end,valid=_validated_custom_date_bounds(request.GET.get('from',''),request.GET.get('to',''))
        if not valid: period='all'
    elif period=='all':
        start=None
    else:
        period='24h'; start=now-timedelta(hours=24)
    return period,start,end


def _resource_period_bounds(request):
    """Rolling Resource Usage windows with a 24-hour default."""
    raw_period=(request.GET.get('period') or '24h').strip().lower()
    aliases={'today':'24h','72h':'3d','week':'7d','month':'30d','year':'all'}
    period=aliases.get(raw_period,raw_period)
    now=timezone.now(); end=None
    rolling={
        '1h':timedelta(hours=1), '3h':timedelta(hours=3), '6h':timedelta(hours=6),
        '12h':timedelta(hours=12), '24h':timedelta(hours=24), '3d':timedelta(days=3),
        '7d':timedelta(days=7), '14d':timedelta(days=14), '30d':timedelta(days=30),
    }
    if period in rolling:
        start=now-rolling[period]; end=now
    elif period=='custom':
        start,end,valid=_validated_custom_date_bounds(request.GET.get('from',''),request.GET.get('to',''))
        if not valid: period='all'
    elif period=='all':
        start=None
    else:
        period='24h'; start=now-timedelta(hours=24)
    return period,start,end


def _log_date_bounds(request):
    """Shared date filter for history/list screens without changing their default all-time view."""
    period=(request.GET.get('period') or 'all').strip().lower()
    now=timezone.now(); start=None; end=None
    aliases={'today':'24h','72h':'3d','week':'7d','month':'30d'}
    period=aliases.get(period,period)
    if period=='24h': start=now-timedelta(hours=24)
    elif period=='3d': start=now-timedelta(days=3)
    elif period=='7d': start=now-timedelta(days=7)
    elif period=='14d': start=now-timedelta(days=14)
    elif period=='30d': start=now-timedelta(days=30)
    elif period=='custom':
        start,end,valid=_validated_custom_date_bounds(request.GET.get('from',''),request.GET.get('to',''))
        if not valid: period='all'
    elif period!='all':
        period='all'
    def fmt(raw):
        parsed=_parse_user_date(raw)
        return timezone.localtime(parsed).strftime('%d/%m/%Y') if parsed else (raw or '')
    date_from=fmt(request.GET.get('from','')); date_to=fmt(request.GET.get('to',''))
    if period not in {'all','custom'}:
        date_from=date_from or timezone.localtime(start).strftime('%d/%m/%Y')
        date_to=date_to or timezone.localdate().strftime('%d/%m/%Y')
    return period,start,end,date_from,date_to


def _apply_log_date_bounds(qs, field, start=None, end=None):
    if start: qs=qs.filter(**{field+'__gte':start})
    if end: qs=qs.filter(**{field+'__lt':end})
    return qs


def _aggregate_usage_events(qs, limit=2000):
    """Aggregate raw Resource Usage records for readable stage-level event counts."""
    rows=qs.values('category','provider','model','stage').annotate(
        at=Max('at'), events=Count('id'), requests=Sum('requests'), tokens_in=Sum('tokens_in'),
        tokens_out=Sum('tokens_out'), reasoning_tokens=Sum('reasoning_tokens'),
        web_search_queries=Sum('web_search_queries'), pages=Sum('pages'), errors=Sum('errors'),
        latency_ms=Avg('latency_ms'), bytes_downloaded=Sum('bytes_downloaded'),
    ).order_by('-at','category','provider','stage')[:limit]
    out=[]
    for row in rows:
        item=dict(row)
        item['latency_ms']=int(round(float(item.get('latency_ms') or 0)))
        item['metadata']={'aggregated_events':int(item.get('events') or 0)}
        out.append(item)
    return out


def _xlsx(filename, headers, rows):
    from openpyxl import Workbook
    wb=Workbook(); ws=wb.active; ws.title='Export'
    ws.append(list(headers))
    for row in rows:
        ws.append([timezone.localtime(v).replace(tzinfo=None) if hasattr(v,'tzinfo') and getattr(v,'tzinfo',None) else v for v in row])
    for col in ws.columns:
        width=min(70,max(10,max(len(str(c.value or '')) for c in col)+2)); ws.column_dimensions[col[0].column_letter].width=width
    buf=io.BytesIO(); wb.save(buf)
    r=HttpResponse(buf.getvalue(),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    r['Content-Disposition']=f'attachment; filename="{filename}"'
    return r





@login_required
@require_POST
def save_list_filter_state(request):
    """Persist an oversized read-only list query and return a compact GET URL."""
    path=str(request.POST.get('path') or '').strip()
    raw_query=str(request.POST.get('query') or '')
    if not path.startswith('/') or path.startswith('//'):
        return JsonResponse({'ok':False,'error':'Invalid filter path.'},status=400)
    if len(path)>500 or len(raw_query)>65536:
        return JsonResponse({'ok':False,'error':'Filter state is too large.'},status=400)
    try:
        pairs=parse_qsl(raw_query,keep_blank_values=True,max_num_fields=1200)
    except (ValueError,TypeError):
        return JsonResponse({'ok':False,'error':'Invalid filter state.'},status=400)
    clean=[]
    for name,value in pairs:
        name=str(name)[:120]; value=str(value)[:1200]
        if not name or name in {'fs','csrfmiddlewaretoken'}:
            continue
        clean.append([name,value])
    token=uuid.uuid4().hex[:16]
    key='scoutbox_filter_states_v1'
    states=request.session.get(key) or {}
    if not isinstance(states,dict): states={}
    # Keep a small LRU-like collection per browser session.  State is deliberately
    # session-scoped: there is no database table and no cross-user token sharing.
    states[token]={'path':path,'pairs':clean,'created':int(time.time())}
    if len(states)>12:
        ordered=sorted(states.items(),key=lambda item:int((item[1] or {}).get('created') or 0),reverse=True)[:12]
        states=dict(ordered)
    request.session[key]=states; request.session.modified=True
    return JsonResponse({'ok':True,'token':token,'url':f'{path}?fs={token}'})


@login_required
@require_GET
def re_evaluation_results_export(request, kind, pk):
    """Export every stored result row for one re-evaluation run as XLSX.

    The export is intentionally independent of the client-side search, sort, and
    pagination state: selecting Export always downloads the complete selected run.
    """
    kind_key=str(kind or '').strip().lower()
    spec={
        'opportunity':('filter_opportunities','opportunity','Opportunity','opportunity-reevaluation'),
        'hidden-lead':('filter_hidden_leads','lead','Hidden Lead','hidden-lead-reevaluation'),
        'address-book':('filter_contacts','contact','Address Book contact','address-book-reevaluation'),
    }.get(kind_key)
    if not spec:
        return HttpResponse('Unknown re-evaluation type.',status=404,content_type='text/plain; charset=utf-8')
    job_kind,item_kind,default_label,filename_prefix=spec
    job=get_object_or_404(BackgroundJob,pk=pk,kind=job_kind)
    _decorate_manual_filter_item_dates([job],item_kind)
    items=manual_filter_meaningful_items(job.result if isinstance(job.result,dict) else {})
    def entry_label(item):
        if kind_key=='opportunity':
            company=str(item.get('company') or '').strip(); title=str(item.get('title') or '').strip()
            return ' — '.join(x for x in (company,title) if x) or default_label
        if kind_key=='hidden-lead':
            return str(item.get('company') or item.get('title') or default_label).strip() or default_label
        return str(item.get('company') or item.get('title') or item.get('email') or default_label).strip() or default_label
    def item_date(item):
        value=item.get('item_date')
        if hasattr(value,'tzinfo') and getattr(value,'tzinfo',None):
            return timezone.localtime(value).replace(tzinfo=None)
        return value or ''
    def fit_text(item):
        fit=manual_filter_fit_change(item)
        try:
            conf=max(0,min(100,int(float(item.get('confidence') or 0))))
        except Exception:
            conf=0
        return f'{fit} · {conf}% confidence'
    def reason_text(item):
        reason=str(item.get('reason') or '—').strip() or '—'
        fit_reason=str(item.get('fit_reason') or '').strip()
        if fit_reason:
            reason += f'\nFit: {fit_reason}'
        return reason
    rows=[(entry_label(item),item_date(item),manual_filter_decision_label(item),fit_text(item),reason_text(item)) for item in items]
    return _xlsx(f'{filename_prefix}-{job.pk}.xlsx',['Entry','Item Date','Decision','Fit','Reason'],rows)


def _gpt_xlsx(rows):
    """Lossless AI Request XLSX: long payloads are chunked onto a Payloads sheet."""
    from openpyxl import Workbook
    wb=Workbook(); ws=wb.active; ws.title='AI Requests'; payloads=wb.create_sheet('Payloads')
    headers=['ID','Related / Task','Runtime','Provider / Model','Input Tokens','Output Tokens','Reasoning Tokens','AI Web Search Queries','Token Usage Source','Input','Output','Attachments','Status','Duration ms','Error','Date']
    ws.append(headers); payloads.append(['Request ID','Field','Chunk','Characters','Text'])
    chunk_size=30000
    def cell_or_chunks(request_id,field,text):
        text=str(text or '')
        if len(text)<=32700: return text
        chunks=[text[i:i+chunk_size] for i in range(0,len(text),chunk_size)]
        for i,chunk in enumerate(chunks,1): payloads.append([request_id,field,i,len(chunk),chunk])
        return f'[Full {field} in Payloads sheet: {len(chunks)} chunks / {len(text)} characters]'
    for x in rows:
        attachments='; '.join(f"{str(i.get('name') or 'attachment')} ({int(i.get('size') or 0)} bytes)" for i in (x.attachments or []) if isinstance(i,dict))
        related=' · '.join(y for y in [x.subject_label,x.subject_type,x.subject_id,x.stage] if y)
        ws.append([x.pk,related,x.runtime,' / '.join(y for y in [x.provider,x.model] if y),x.tokens_in,x.tokens_out,x.reasoning_tokens,x.web_search_queries,x.token_usage_source,cell_or_chunks(x.pk,'Input',x.input_text),cell_or_chunks(x.pk,'Output',x.output_text),attachments,x.get_status_display(),x.duration_ms if x.duration_ms is not None else '',x.error,timezone.localtime(x.at).replace(tzinfo=None)])
    for sheet in (ws,payloads):
        sheet.freeze_panes='A2'
        for col in sheet.columns:
            sheet.column_dimensions[col[0].column_letter].width=min(70,max(10,max(len(str(c.value or '')) for c in list(col)[:500])+2))
    buf=io.BytesIO(); wb.save(buf); r=HttpResponse(buf.getvalue(),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'); r['Content-Disposition']='attachment; filename="gpt_log.xlsx"'; return r


def _gpt_jsonl(rows):
    body=''.join(json.dumps({'id':x.pk,'status':x.status,'provider':x.provider,'model':x.model,'stage':x.stage,'runtime':x.runtime,'subject_type':x.subject_type,'subject_id':x.subject_id,'subject_label':x.subject_label,'tokens_in':x.tokens_in,'tokens_out':x.tokens_out,'reasoning_tokens':x.reasoning_tokens,'ai_web_search_queries':x.web_search_queries,'token_usage_source':x.token_usage_source,'duration_ms':x.duration_ms,'input_text':x.input_text,'output_text':x.output_text,'raw_output_text':x.raw_output_text,'attachments':x.attachments or [],'metadata':x.metadata or {},'ok':x.ok,'error':x.error,'at':x.at.isoformat()},cls=DjangoJSONEncoder,ensure_ascii=False)+'\n' for x in rows)
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as zf:
        zf.writestr('gpt_log.jsonl',body.encode('utf-8'))
    r=HttpResponse(buf.getvalue(),content_type='application/zip')
    r['Content-Disposition']='attachment; filename="gpt_log-jsonl.zip"'
    return r

def _csv(filename, headers, rows):
    # Backward-compatible internal alias; v0.8 UI exports XLSX only.
    return _xlsx(filename.rsplit('.',1)[0]+'.xlsx',headers,rows)


def _model_choices():
    choices=[]; seen=set()
    d=ollama_service.diagnostics()
    for item in d.get('installed',[]):
        model=item.get('name') or item.get('model')
        value=f'ollama|{model}' if model else ''
        if model and value not in seen:
            choices.append({'value':value,'provider':'ollama','model':model,'label':f'Ollama · {model}'})
            seen.add(value)
    # Keep the configured Ollama default visible even if diagnostics are temporarily unavailable.
    oll=AIProviderConfig.objects.filter(provider='ollama',enabled=True).first()
    if oll and oll.default_model:
        value=f'ollama|{oll.default_model}'
        if value not in seen:
            choices.append({'value':value,'provider':'ollama','model':oll.default_model,'label':f'Ollama · {oll.default_model} (configured)'})
            seen.add(value)
    for cfg in AIProviderConfig.objects.filter(enabled=True).exclude(provider='ollama'):
        model=configured_cloud_model(cfg)
        if model:
            value=f'{cfg.provider}|{model}'
            if value not in seen:
                suffix=' (Automatic resolved)' if not str(cfg.default_model or '').strip() else ''
                choices.append({'value':value,'provider':cfg.provider,'model':model,'label':f'{cfg.get_provider_display()} · {model}{suffix}'})
                seen.add(value)
    return choices


MANUAL_FILTER_MODEL_HINTS={
    'gemini':['gemini-3.5-flash-lite','gemini-3.1-flash-lite','gemini-3.5-flash','gemini-2.5-flash'],
    'openai':['gpt-5-mini','gpt-4.1-mini','gpt-4o-mini'],
    'openrouter':['google/gemini-3.5-flash-lite','google/gemini-3.1-flash-lite','google/gemini-2.5-flash','openai/gpt-4.1-mini','openai/gpt-4o-mini'],
}


def _manual_filter_ai_options():
    """Return explicit provider/model choices for user-requested re-filtering.

    Manual filtering is intentionally independent of the normal Discovery first-filter
    route. Prefer Gemini 3.5 Flash-Lite when Gemini is credentialed; otherwise choose the
    first usable Cloud provider, with Ollama available only as an explicit/local fallback.
    """
    configs={cfg.provider:cfg for cfg in AIProviderConfig.objects.filter(enabled=True)}
    providers=[]
    cloud_order=['gemini']+[x for x in cloud_provider_priority() if x!='gemini']
    ordered=[]
    for provider in cloud_order+['ollama']:
        if provider not in ordered:
            ordered.append(provider)
    labels=dict(AIProviderConfig.PROVIDERS)
    for provider in ordered:
        cfg=configs.get(provider)
        if not cfg:
            continue
        is_cloud=provider in ('openai','gemini','openrouter')
        if is_cloud:
            try:
                if not decrypt(cfg.api_key_enc):
                    continue
            except Exception:
                continue
            models=[]
            preferred=list(MANUAL_FILTER_MODEL_HINTS.get(provider) or [])
            configured=str(configured_cloud_model(cfg) or '').strip()
            explicit=str(cfg.default_model or '').strip()
            for model in ([configured,explicit]+preferred):
                model=str(model or '').strip()
                if model and model not in models:
                    models.append(model)
        else:
            models=[]
            try:
                for item in ollama_service.diagnostics().get('installed',[]):
                    model=str(item.get('name') or item.get('model') or '').strip()
                    if model and model not in models:
                        models.append(model)
            except Exception:
                pass
            configured=str(cfg.default_model or '').strip()
            if configured and configured not in models:
                models.insert(0,configured)
        if not models:
            continue
        providers.append({
            'value':provider,
            'label':f'{labels.get(provider,provider)} — {"Cloud" if is_cloud else "Local"}',
            'is_cloud':is_cloud,
            'models':models,
        })

    default_provider=''; default_model=''
    gemini=next((row for row in providers if row['value']=='gemini'),None)
    if gemini:
        default_provider='gemini'
        default_model='gemini-3.5-flash-lite' if 'gemini-3.5-flash-lite' in gemini['models'] else gemini['models'][0]
    else:
        cloud=next((row for row in providers if row['is_cloud']),None)
        chosen=cloud or (providers[0] if providers else None)
        if chosen:
            default_provider=chosen['value']; default_model=chosen['models'][0]
    settings=PortalSettings.objects.get_or_create(pk=1)[0]
    return {
        'providers':providers,'default_provider':default_provider,'default_model':default_model,
        'opportunity_cloud_prompt':str(settings.opportunity_cloud_reevaluation_prompt or DEFAULT_OPPORTUNITY_CLOUD_REEVALUATION_PROMPT),
        'hidden_lead_cloud_prompt':str(settings.hidden_lead_cloud_reevaluation_prompt or DEFAULT_HIDDEN_LEAD_CLOUD_REEVALUATION_PROMPT),
    }


def _manual_filter_cloud_prompt(request, kind, provider):
    """Return and persist the editable cloud-only decision-policy prompt."""
    if str(provider or '').strip().lower() not in ('openai','gemini','openrouter'):
        return ''
    settings=PortalSettings.objects.get_or_create(pk=1)[0]
    if kind=='hidden_lead':
        field='hidden_lead_cloud_reevaluation_prompt'; fallback=DEFAULT_HIDDEN_LEAD_CLOUD_REEVALUATION_PROMPT
    else:
        field='opportunity_cloud_reevaluation_prompt'; fallback=DEFAULT_OPPORTUNITY_CLOUD_REEVALUATION_PROMPT
    current=str(getattr(settings,field,'') or fallback).strip()
    submitted=str(request.POST.get('cloud_re_evaluation_prompt') or '').strip()[:4000]
    prompt=submitted or current or fallback
    if prompt != getattr(settings,field,''):
        setattr(settings,field,prompt); settings.save(update_fields=[field,'updated_at'])
    return prompt


def _manual_filter_selection(request):
    options=_manual_filter_ai_options()
    provider=str(request.POST.get('filter_provider') or '').strip().lower()
    model=str(request.POST.get('filter_model') or '').strip()
    row=next((x for x in options['providers'] if x['value']==provider),None)
    if not row or model not in row['models']:
        raise ValueError('Select an enabled AI provider and model for this filter.')
    internet_search=bool(row['is_cloud'])
    return provider,model,internet_search,options


def _active_manual_filter():
    return BackgroundJob.objects.filter(
        kind__in=['filter_opportunities','filter_hidden_leads','filter_contacts'],status__in=['queued','running']
    ).order_by('-created_at').first()


def _manual_filter_is_placeholder_value(value):
    text=str(value or '').strip().lower()
    return text in {'', '-', '—', 'not recalculated', 'not calculated', 'n/a', 'none', 'null'}


def _manual_filter_row_has_numeric_score(row):
    if not isinstance(row, dict):
        return False
    for key in ('fit_after','lead_score','fit_before','confidence'):
        value=row.get(key)
        if value in (None, ''):
            continue
        text=str(value).strip().replace('%','')
        if text.lower() in {'not recalculated','not calculated','n/a','none','null','-','—'}:
            continue
        try:
            float(text)
            return True
        except Exception:
            continue
    return False


def _manual_filter_row_is_meaningful(row):
    if not isinstance(row,dict):
        return False
    decision=str(row.get('decision') or '').strip().lower()
    applied=str(row.get('applied_decision') or '').strip().lower()
    name=str(row.get('company') or row.get('title') or row.get('email') or '').strip()
    if name.lower() in {'hidden lead', 'hidden lead #', 'opportunity', 'opportunity #', 'address book contact', 'contact', 'contact #'}:
        name=''
    reason=str(row.get('reason') or row.get('fit_reason') or '').strip()
    if _manual_filter_is_placeholder_value(reason):
        reason=''
    has_score=_manual_filter_row_has_numeric_score(row)
    try:
        confidence=float(str(row.get('confidence') or '').replace('%','').strip())
    except Exception:
        confidence=None
    has_nonzero_confidence=confidence is not None and confidence > 0
    has_details=bool(row.get('metadata_refreshed') or row.get('metadata_changes') or row.get('web_sources') or row.get('pages') or row.get('rejection_risks') or row.get('refreshed'))
    if decision in {'keep','admit','recycled','protected','failed','timeout','timed_out','reject','converted_to_hidden_lead','converted_to_opportunity'}:
        return bool(name or reason or has_score or has_nonzero_confidence or has_details)
    if applied and applied != 'review':
        return bool(name or reason or has_score or has_nonzero_confidence or has_details)
    return bool(name and (reason or has_score or has_nonzero_confidence or has_details))


def _manual_filter_result_has_visible_entries(result):
    if not isinstance(result,dict):
        return False
    return any(_manual_filter_row_is_meaningful(row) for row in (result.get('items') or []))


def _latest_meaningful_manual_filter(history):
    """Return the latest completed run with actual useful entries/actions only."""
    for job in history or []:
        result=job.result if isinstance(job.result,dict) else {}
        if _manual_filter_result_has_visible_entries(result):
            return job
        # Error cards are meaningful only if they actually contain a non-placeholder message.
        err=str(result.get('fatal_error') or result.get('error') or result.get('circuit_breaker') or '').strip()
        if err and not _manual_filter_is_placeholder_value(err):
            return job
    return None


def _manual_filter_run_has_visible_history(job):
    """True only for re-evaluation runs worth showing in history.

    Active queued/running jobs are visible as work-in-progress. Completed no-op
    shells and legacy placeholder runs such as "0 kept / 0 recycled / 0 Strong
    Fit" with only blank Review rows are hidden entirely from history and latest
    result cards. A checked/review count by itself is not a useful result.
    """
    status=str(getattr(job,'status','') or '').lower()
    if status in {'queued','running'}:
        return True
    result=getattr(job,'result',None)
    if not isinstance(result,dict):
        return False
    if _manual_filter_result_has_visible_entries(result):
        return True
    err=str(result.get('fatal_error') or result.get('error') or result.get('circuit_breaker') or '').strip()
    if err and not _manual_filter_is_placeholder_value(err):
        return True
    return False



def _manual_filter_history_for_view(kind, active_job=None, *, canonicalize_active=None):
    """Return every stored re-evaluation job for the list-page history dialog.

    The history popup is intentionally DB-complete: no last-N cap and no latest-row
    pre-slice.  The currently active job is placed first and, when needed, can be
    overlaid with its durable progress snapshot before the remaining persisted jobs
    are appended newest-first.
    """
    rows=[]
    seen=set()
    if active_job:
        active=canonicalize_active(active_job) if canonicalize_active else active_job
        rows.append(active)
        try:
            seen.add(int(active_job.pk))
        except Exception:
            pass
    for job in BackgroundJob.objects.filter(kind=kind).order_by('-created_at','-pk'):
        try:
            ident=int(job.pk)
        except Exception:
            ident=None
        if ident is not None and ident in seen:
            continue
        if not _manual_filter_run_has_visible_history(job):
            continue
        rows.append(job)
    return rows


def _manual_filter_history_label(history, subject='Re-evaluation'):
    """Human-readable history count used in the three re-evaluation dialogs."""
    count=len(history or [])
    suffix='' if count == 1 else 's'
    return f'Showing {count} {subject} re-evaluation result{suffix}'


def _decorate_manual_filter_item_dates(history, item_kind):
    """Attach the original record date to stored re-evaluation rows for list display.

    BackgroundJob result JSON intentionally stays unchanged in the database.  The
    history popup needs a sortable Item Date even for older runs, so decorate an
    in-memory copy from the surviving/recycled source records in one bulk query.
    """
    rows=list(history or [])
    ids=set()
    for job in rows:
        result=getattr(job,'result',None)
        if not isinstance(result,dict):
            continue
        for item in result.get('items') or []:
            if not isinstance(item,dict):
                continue
            try:
                ident=int(item.get('id') or 0)
            except Exception:
                ident=0
            if ident:
                ids.add(ident)
    if not ids:
        return rows
    kind=str(item_kind or '').strip().lower()
    if kind=='opportunity':
        date_map=dict(Opportunity.objects.filter(pk__in=ids).values_list('pk','first_seen_by_portal'))
    elif kind=='lead':
        date_map=dict(CompanyLead.objects.filter(pk__in=ids).values_list('pk','created_at'))
    elif kind=='contact':
        date_map=dict(Contact.objects.filter(pk__in=ids).values_list('pk','created_at'))
    else:
        date_map={}
    for job in rows:
        result=getattr(job,'result',None)
        if not isinstance(result,dict):
            continue
        copied=dict(result)
        copied_items=[]
        for raw in result.get('items') or []:
            if not isinstance(raw,dict):
                copied_items.append(raw)
                continue
            item=dict(raw)
            try:
                ident=int(item.get('id') or 0)
            except Exception:
                ident=0
            item['item_date']=date_map.get(ident)
            copied_items.append(item)
        copied['items']=copied_items
        job.result=copied
    return rows


def _is_existing_hidden_lead_reassessment_job(job):
    if not job or str(getattr(job,'kind','') or '')!='filter_hidden_leads':
        return False
    result=getattr(job,'result',None)
    if isinstance(result,dict) and result.get('hidden_lead_minibrowser_reassessment'):
        return True
    return str(getattr(job,'label','') or '').startswith('Reassess existing Hidden Leads')


def _hidden_lead_reassessment_pass_snapshot():
    try:
        ps=PortalSettings.objects.get_or_create(pk=1)[0]
        state=dict(ps.focus_taxonomy_state or {})
        row=state.get('hidden_lead_minibrowser_reassessment_pass')
        return dict(row) if isinstance(row,dict) else {}
    except Exception:
        return {}


def _canonicalize_hidden_lead_reassessment_job(job):
    """Overlay the transient BackgroundJob with the durable pass cursor.

    The durable pass is the sole progress source for the automatic existing-lead
    reassessment.  This prevents list polling and the status dialog from showing
    different old worker snapshots after a restart/revive.
    """
    if not _is_existing_hidden_lead_reassessment_job(job):
        return job
    snap=_hidden_lead_reassessment_pass_snapshot()
    if not snap:
        return job
    result=dict(getattr(job,'result',{}) or {}) if isinstance(getattr(job,'result',None),dict) else {}
    for key in ('pass_id','schema','release','selected','processed','admitted','review','rejected','protected','recycled','converted_to_hidden_lead','converted_to_opportunity','failed','timed_out','skipped_current','current_item'):
        if key in snap:
            result[key]=snap.get(key)
    result['hidden_lead_minibrowser_reassessment']=True
    total=int(snap.get('target_count') or snap.get('selected') or result.get('selected') or 0)
    processed=int(snap.get('processed') or result.get('processed') or 0)
    current=snap.get('current_item') if isinstance(snap.get('current_item'),dict) else {}
    if total:
        job.progress=min(100,max(0,int((processed/max(1,total))*100)))
    company=str(current.get('company') or '').strip()
    current_index=int(current.get('index') or min(total,processed+1) or processed) if (total or processed) else 0
    if str(snap.get('status') or '').lower() in {'running','pending','queued'}:
        job.message=f'Reassessing existing Hidden Leads · {current_index or processed}/{total}' + (f' · {company}' if company else '')
    job.result=result
    return job


def _hidden_lead_filter_history_for_view(active_job=None):
    """Return every stored Hidden Lead re-evaluation job for the history dialog."""
    return _manual_filter_history_for_view(
        'filter_hidden_leads',
        active_job,
        canonicalize_active=_canonicalize_hidden_lead_reassessment_job,
    )

def _claim_manual_filter_job(kind, label, message, result):
    """Atomically reserve the single global manual re-evaluation slot."""
    with transaction.atomic():
        # Row-locking PortalSettings serializes starts across Opportunities, Hidden Leads
        # and Address Book without adding a schema field or migration.
        PortalSettings.objects.select_for_update().get_or_create(pk=1)
        active=_active_manual_filter()
        if active:
            return None,active
        job=BackgroundJob.objects.create(kind=kind,label=label[:300],message=message[:500],result=result)
        return job,None


def _local_assessment_ids(rows):
    """Return IDs whose currently displayed Fit was assessed locally/legacy."""
    return [row.pk for row in rows if has_local_fit_assessment(row)]


def _cloud_assessment_ids(rows):
    """Return IDs whose currently displayed Fit has Cloud AI provenance."""
    return [row.pk for row in rows if has_cloud_fit_assessment(row)]


def _manual_filter_recipient(request):
    email=str(getattr(request.user,'email','') or '').strip()
    if not email:
        username=str(getattr(request.user,'username','') or '').strip()
        if '@' in username:
            email=username
    return email


def _chatbot_summary():
    route=route_for_stage('chatbot')
    provider=route.get('provider','') if route else ''
    runtime=(route.get('execution_mode') or ('local' if provider=='ollama' else ('cloud' if provider else ''))).lower() if route else ''
    runtime_label='Local Ollama' if runtime=='local' else ('Cloud AI' if runtime=='cloud' else 'Not configured')
    labels={'ollama':'Ollama','openai':'OpenAI','gemini':'Gemini','openrouter':'OpenRouter'}
    label=labels.get(provider,provider or 'Not configured')
    secondary_provider=str(route.get('fallback_provider') or '') if route else ''
    secondary_model=str(route.get('fallback_model') or '') if route else ''
    secondary_runtime=(route.get('fallback_execution_mode') or ('local' if secondary_provider=='ollama' else ('cloud' if secondary_provider else ''))).lower() if route else ''
    limits=token_limits_for_stage('chatbot',provider=provider)
    return {
        'runtime':runtime, 'runtime_label':runtime_label, 'provider':provider, 'provider_label':label,
        'model':route.get('model','') if route else '',
        'allow_internet_search':bool(route.get('allow_internet_search')) if route and provider in {'openai','gemini','openrouter'} else False,
        'is_cloud':provider in {'openai','gemini','openrouter'},
        'secondary_provider':secondary_provider,
        'secondary_provider_label':labels.get(secondary_provider,secondary_provider or 'Not configured'),
        'secondary_model':secondary_model,
        'secondary_runtime':secondary_runtime,
        'secondary_runtime_label':'Local Ollama' if secondary_runtime=='local' else ('Cloud AI' if secondary_runtime=='cloud' else 'Not configured'),
        'secondary_allow_internet_search':bool(route.get('fallback_allow_internet_search')) if route and secondary_provider in {'openai','gemini','openrouter'} else False,
        'secondary_is_cloud':secondary_provider in {'openai','gemini','openrouter'},
        'max_input_tokens':limits.get('max_input_tokens'),
        'max_output_tokens':limits.get('max_output_tokens'),
        'model_value':f"{provider}|{route.get('model','')}" if provider and route and route.get('model') else '',
        'secondary_model_value':f"{secondary_provider}|{secondary_model}" if secondary_provider and secondary_model else '',
    }


def _chatbot_test_status(summary=None):
    """Return persisted test state for the currently selected Chatbot routes.

    Chatbot tests are synchronous, so AuditLog is enough to retain lightweight
    validation state without adding another settings migration. A test only applies
    to the exact provider/model pair that was tested; changing either selection
    naturally falls back to the unknown/question-mark state.
    """
    summary=summary or _chatbot_summary()
    lanes={
        'primary': (str(summary.get('provider') or ''), str(summary.get('model') or '')),
        'secondary': (str(summary.get('secondary_provider') or ''), str(summary.get('secondary_model') or '')),
    }
    result={lane:{'state':'unknown','title':'Not tested','tested_at':'','tested_at_iso':''} for lane in lanes}
    wanted={(provider,model) for provider,model in lanes.values() if provider and model}
    if not wanted:
        return result
    rows=list(AuditLog.objects.filter(action='chatbot.test').order_by('-at')[:160])
    for lane,(provider,model) in lanes.items():
        if not provider or not model:
            continue
        for row in rows:
            meta=row.metadata or {}
            row_provider=str(meta.get('provider') or '').strip().lower()
            row_model=str(meta.get('model') or '').strip()
            if not row_provider or not row_model:
                parts=[x.strip() for x in str(row.summary or '').split('·',1)]
                if len(parts)==2:
                    row_provider,row_model=parts[0].lower(),parts[1]
            if row_provider!=provider.lower() or row_model!=model:
                continue
            recorded_lane=str(meta.get('lane') or '').strip().lower()
            if recorded_lane and recorded_lane!=lane:
                continue
            ok=bool(meta.get('ok'))
            local_at=timezone.localtime(row.at) if row.at else None
            stamp=local_at.strftime('%d/%m/%Y %H:%M:%S') if local_at else ''
            detail=str(meta.get('error') or ('Validated' if ok else 'Test failed')).strip()
            result[lane]={
                'state':'ok' if ok else 'warning',
                'title':' · '.join(x for x in [provider,model,detail] if x)[:700],
                'tested_at':stamp,
                'tested_at_iso':row.at.isoformat() if row.at else '',
            }
            break
    return result


@login_required
@require_POST
def chatbot_ask(request):
    """Persist and queue one Ask ScoutBox turn, then return immediately.

    The actual provider call runs in Celery so the browser does not need to keep a
    long-running fetch alive. The answer is persisted to ChatbotMessage and appears via
    chatbot_history polling even if the user navigates away while the model is working.
    """
    try:
        payload=json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload={}
    question=str(payload.get('question','')).strip()
    history=payload.get('history') if isinstance(payload.get('history'),list) else []
    if not question:
        return JsonResponse({'ok':False,'error':'Ask a brief question about ScoutBox.'},status=400)
    if not request.session.session_key:
        request.session.save()
    session_key=str(request.session.session_key or '')[:120]
    summary=_chatbot_summary()
    provider=str(summary.get('provider') or '').strip().lower()
    model=str(summary.get('model') or '').strip()
    if not provider or not model:
        return JsonResponse({'ok':False,'error':'Chatbot provider/model is not configured.'},status=400)
    try:
        user_message=ChatbotMessage.objects.create(session_key=session_key,role='user',text=question,links=[])
        data={
            'session_key':session_key,'question':question,'history':history[-12:],
            'current_path':str(payload.get('current_path','') or '')[:500],
            'provider':provider,'model':model,
            'allow_internet_search':bool(summary.get('allow_internet_search')),
            'secondary_provider':str(summary.get('secondary_provider') or ''),
            'secondary_model':str(summary.get('secondary_model') or ''),
            'secondary_allow_internet_search':bool(summary.get('secondary_allow_internet_search')),
            'user_message_id':user_message.pk,
        }
        job=BackgroundJob.objects.create(kind='chatbot',label='Ask ScoutBox'[:300],message='Queued',result=data)
        task=chatbot_request_job.delay(job.pk)
        job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
        try:
            log('chatbot.ask',request,summary=question[:240],metadata={'queued':True,'job_id':job.pk,'provider':provider,'model':model,'internet_search':bool(summary.get('allow_internet_search')),'secondary_provider':summary.get('secondary_provider',''),'secondary_model':summary.get('secondary_model','')})
        except Exception:
            pass
        return JsonResponse({'ok':True,'queued':True,'job_id':job.pk,'user_message_id':user_message.pk},status=202)
    except Exception as exc:
        logger.exception('Unable to queue Chatbot request')
        detail=str(exc or 'Unable to queue Chatbot request.')[:500]
        try:
            ChatbotMessage.objects.create(session_key=session_key,role='assistant',text='ScoutBox could not queue that Chatbot request: '+detail,links=[],source_provider='ScoutBox',source_model='Queue error')
        except Exception:
            pass
        return JsonResponse({'ok':False,'error':'ScoutBox could not queue the Chatbot request. Check worker/broker status and retry.','detail':detail},status=503)


@login_required
def chatbot_history(request):
    """Canonical persisted history plus pending-count for navigation-safe Chatbot UI."""
    if not request.session.session_key:
        request.session.save()
    session_key=str(request.session.session_key or '')[:120]
    rows=list(ChatbotMessage.objects.filter(session_key=session_key).order_by('-id')[:60])
    rows.reverse()
    payload=[]
    for row in rows:
        payload.append({'id':row.pk,'role':row.role,'text':row.text,'links':row.links if isinstance(row.links,list) else [],'source_provider':row.source_provider or '','source_model':row.source_model or '','at':row.at.isoformat() if row.at else ''})
    latest=max((x['id'] for x in payload if x['role']=='assistant'),default=0)
    pending=BackgroundJob.objects.filter(kind='chatbot',status__in=['queued','running'],result__session_key=session_key).count()
    return JsonResponse({'ok':True,'messages':payload,'latest_assistant_id':latest,'pending_count':pending})


def _chat_export_inline_html(value):
    """Safe inline Markdown subset used by standalone chat exports."""
    text=html.escape(str(value or ''),quote=True)
    # Markdown links are converted after escaping, so labels remain escaped and hrefs
    # cannot inject markup. Only http(s) destinations are accepted.
    text=re.sub(r'\[([^\]]+)\]\(((?:https?://|/)[^\s)]+)\)',r'<a href="\2" target="_blank" rel="noreferrer">\1</a>',text)
    text=re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',text)
    text=re.sub(r'__([^_]+)__',r'<u>\1</u>',text)
    text=re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)',r'<em>\1</em>',text)
    text=re.sub(r'(?<!_)_([^_\n]+)_(?!_)',r'<em>\1</em>',text)
    return text


def _chat_export_markdown_html(value):
    """Render chat Markdown as readable HTML instead of a Markdown source dump."""
    lines=str(value or '').replace('\r\n','\n').replace('\r','\n').split('\n')
    out=[]; in_list=False; pending_gap=False
    def close_list():
        nonlocal in_list
        if in_list:
            out.append('</ul>'); in_list=False
    for raw in lines:
        line=raw.rstrip()
        if not line.strip():
            close_list()
            if out and not pending_gap:
                out.append('<div class="chat-gap"></div>')
            pending_gap=True
            continue
        pending_gap=False
        bullet=re.match(r'^\s*[-*]\s+(.+)$',line)
        if bullet:
            if not in_list:
                out.append('<ul>'); in_list=True
            out.append('<li>'+_chat_export_inline_html(bullet.group(1))+'</li>')
            continue
        close_list()
        heading=re.match(r'^\s*#{1,6}\s+(.+)$',line)
        if heading:
            out.append('<div class="chat-heading"><strong>'+_chat_export_inline_html(heading.group(1))+'</strong></div>')
            continue
        if re.match(r'^\s*---+\s*$',line):
            out.append('<hr>'); continue
        out.append('<div class="chat-line">'+_chat_export_inline_html(line.strip())+'</div>')
    close_list()
    return ''.join(out)


def _chat_docx_hyperlink(paragraph, label, url, *, bold=False, italic=False):
    """Append a real clickable hyperlink, preserving surrounding emphasis."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    relation_id=paragraph.part.relate_to(str(url),RT.HYPERLINK,is_external=True)
    hyperlink=OxmlElement('w:hyperlink'); hyperlink.set(qn('r:id'),relation_id)
    run=OxmlElement('w:r'); props=OxmlElement('w:rPr')
    color=OxmlElement('w:color'); color.set(qn('w:val'),'0563C1'); props.append(color)
    underline=OxmlElement('w:u'); underline.set(qn('w:val'),'single'); props.append(underline)
    if bold: props.append(OxmlElement('w:b'))
    if italic: props.append(OxmlElement('w:i'))
    run.append(props)
    text=OxmlElement('w:t'); text.text=str(label or url); run.append(text); hyperlink.append(run)
    paragraph._p.append(hyperlink)


def _chat_docx_inline(paragraph, value, request=None, *, inherited_bold=False, inherited_italic=False, inherited_underline=False):
    """Render lightweight Markdown into DOCX runs, including links nested inside emphasis."""
    text=str(value or '')
    token=re.compile(r'(\[[^\]\n]+\]\\?\((?:https?://|/)[^\s)]+\)|\*\*[^*\n]+\*\*|__[^_\n]+__|`[^`\n]+`|(?<!\*)\*[^*\n]+\*(?!\*)|https?://[^\s<>]+)')

    def add_plain(raw):
        if not raw: return
        run=paragraph.add_run(raw)
        run.bold=inherited_bold
        run.italic=inherited_italic
        run.underline=inherited_underline
        return run

    pos=0
    for match in token.finditer(text):
        if match.start()>pos: add_plain(text[pos:match.start()])
        raw=match.group(0)
        md_link=re.fullmatch(r'\[([^\]\n]+)\]\\?\(((?:https?://|/)[^\s)]+)\)',raw)
        if md_link:
            label,url=md_link.groups()
            if url.startswith('/') and request is not None: url=request.build_absolute_uri(url)
            _chat_docx_hyperlink(paragraph,label,url,bold=inherited_bold,italic=inherited_italic)
        elif raw.startswith('**') and raw.endswith('**'):
            _chat_docx_inline(paragraph,raw[2:-2],request,inherited_bold=True,inherited_italic=inherited_italic,inherited_underline=inherited_underline)
        elif raw.startswith('__') and raw.endswith('__'):
            _chat_docx_inline(paragraph,raw[2:-2],request,inherited_bold=inherited_bold,inherited_italic=inherited_italic,inherited_underline=True)
        elif raw.startswith('`') and raw.endswith('`'):
            run=add_plain(raw[1:-1]); run.font.name='Consolas'
        elif raw.startswith('*') and raw.endswith('*'):
            _chat_docx_inline(paragraph,raw[1:-1],request,inherited_bold=inherited_bold,inherited_italic=True,inherited_underline=inherited_underline)
        elif raw.startswith(('http://','https://')):
            url=raw.rstrip('.,;:!?]')
            suffix=raw[len(url):]
            _chat_docx_hyperlink(paragraph,url,url,bold=inherited_bold,italic=inherited_italic)
            if suffix: add_plain(suffix)
        else:
            add_plain(raw)
        pos=match.end()
    if pos<len(text): add_plain(text[pos:])


def _chat_docx_para_spacing(paragraph, *, before=0, after=4, line=1.08):
    """Use compact, readable paragraph spacing for exported Chatbot transcripts."""
    from docx.shared import Pt
    fmt=paragraph.paragraph_format
    fmt.space_before=Pt(before)
    fmt.space_after=Pt(after)
    fmt.line_spacing=line
    return paragraph


def _chat_docx_message_header(document, label, at='', role='assistant'):
    """Create a visually distinct message header without adding a blank spacer paragraph."""
    from docx.shared import Pt, RGBColor
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    paragraph=document.add_paragraph()
    _chat_docx_para_spacing(paragraph,before=9,after=4,line=1.0)
    props=paragraph._p.get_or_add_pPr()
    shd=props.find(qn('w:shd'))
    if shd is None:
        shd=OxmlElement('w:shd'); props.append(shd)
    shd.set(qn('w:fill'),'EAF4FB' if role=='assistant' else 'EEF7F0')
    role_run=paragraph.add_run(label)
    role_run.bold=True; role_run.font.size=Pt(14)
    role_run.font.color.rgb=RGBColor(20,73,104) if role=='assistant' else RGBColor(35,92,55)
    if at:
        time_run=paragraph.add_run('   '+at)
        time_run.font.size=Pt(10.5); time_run.font.color.rgb=RGBColor(82,101,115)
    return paragraph


def _chat_docx_format_timestamp(value):
    raw=str(value or '').strip()
    if not raw:
        return ''
    try:
        parsed=datetime.fromisoformat(raw.replace('Z','+00:00'))
        if timezone.is_naive(parsed):
            parsed=timezone.make_aware(parsed,timezone.get_current_timezone())
        return timezone.localtime(parsed).strftime('%d/%m/%Y %H:%M:%S')
    except Exception:
        return raw


def _chat_docx_markdown(document, value, request=None):
    """Render chat Markdown compactly, collapsing blank lines and hard-wrapped prose."""
    from docx.shared import RGBColor
    lines=str(value or '').replace('\r\n','\n').replace('\r','\n').split('\n')
    plain=[]
    pending_gap=False

    def add_spacing(paragraph, *, list_item=False, heading=False):
        nonlocal pending_gap
        before=4 if pending_gap else (2 if heading else 0)
        after=2 if list_item else (3 if heading else 4)
        _chat_docx_para_spacing(paragraph,before=before,after=after,line=1.08)
        pending_gap=False
        return paragraph

    def flush_plain():
        nonlocal plain
        if not plain:
            return
        # Consecutive plain lines are usually model hard-wraps. Word should wrap them itself.
        text=' '.join(x.strip() for x in plain if x.strip())
        if text:
            paragraph=add_spacing(document.add_paragraph())
            _chat_docx_inline(paragraph,text,request)
        plain=[]

    for raw in lines:
        line=raw.rstrip()
        if not line.strip():
            flush_plain(); pending_gap=True; continue
        bullet=re.match(r'^\s*[-*]\s+(.+)$',line)
        numbered=re.match(r'^\s*\d+[.)]\s+(.+)$',line)
        heading=re.match(r'^\s*(#{1,6})\s+(.+)$',line)
        rule=re.match(r'^\s*---+\s*$',line)
        if not (bullet or numbered or heading or rule):
            plain.append(line)
            continue
        flush_plain()
        if bullet:
            paragraph=add_spacing(document.add_paragraph(style='List Bullet'),list_item=True)
            _chat_docx_inline(paragraph,bullet.group(1),request); continue
        if numbered:
            paragraph=add_spacing(document.add_paragraph(style='List Number'),list_item=True)
            _chat_docx_inline(paragraph,numbered.group(1),request); continue
        if heading:
            paragraph=add_spacing(document.add_paragraph(style=f'Heading {min(6,len(heading.group(1)))}'),heading=True)
            _chat_docx_inline(paragraph,heading.group(2),request); continue
        paragraph=add_spacing(document.add_paragraph(),heading=True)
        run=paragraph.add_run('────────────────────────────────────────')
        run.font.color.rgb=RGBColor(170,184,194)
    flush_plain()


@login_required
@require_POST
def chatbot_export(request):
    """Export the browser chat transcript as a native DOCX without persisting it server-side."""
    from docx import Document
    from docx.shared import Pt, RGBColor
    try:
        payload=json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload={}
    transcript=payload.get('transcript') if isinstance(payload.get('transcript'),list) else []
    rows=[]
    for item in transcript[-200:]:
        if not isinstance(item,dict): continue
        role=str(item.get('role') or '')[:30]
        text=str(item.get('text') or '')[:30000]
        at=str(item.get('at') or '')[:80]
        source_provider=str(item.get('source_provider') or '')[:40]
        source_model=str(item.get('source_model') or '')[:300]
        links=item.get('links') if isinstance(item.get('links'),list) else []
        clean_links=[]
        for link in links[:50]:
            if not isinstance(link,dict): continue
            label=str(link.get('label') or link.get('url') or '').strip()[:300]
            url=str(link.get('url') or '').strip()[:2000]
            if label and url.startswith(('http://','https://','/')): clean_links.append((label,url))
        if text: rows.append((at,role,text,source_provider,source_model,clean_links))

    document=Document()
    section=document.sections[0]
    from docx.shared import Inches
    section.top_margin=Inches(0.65); section.bottom_margin=Inches(0.65)
    section.left_margin=Inches(0.72); section.right_margin=Inches(0.72)
    normal=document.styles['Normal']; normal.font.name='Aptos'; normal.font.size=Pt(11.5)
    normal.paragraph_format.space_after=Pt(4); normal.paragraph_format.line_spacing=1.08
    for style_name,size in [('Heading 1',14),('Heading 2',13),('Heading 3',12.5),('Heading 4',12),('Heading 5',11.5),('Heading 6',11.5)]:
        try:
            style=document.styles[style_name]; style.font.name='Aptos'; style.font.size=Pt(size); style.font.bold=True
            style.paragraph_format.space_before=Pt(4); style.paragraph_format.space_after=Pt(3)
        except Exception:
            pass
    title=document.add_heading('ScoutBox Chat',0)
    title.paragraph_format.space_after=Pt(2)
    generated=document.add_paragraph()
    generated.paragraph_format.space_after=Pt(8)
    generated_run=generated.add_run('Exported '+timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M:%S'))
    generated_run.font.size=Pt(10); generated_run.font.color.rgb=RGBColor(92,108,120)

    if not rows:
        document.add_paragraph('No chat messages were supplied for export.')
    for at,role,text,source_provider,source_model,links in rows:
        label='ScoutBox' if role=='assistant' else ('You' if role=='user' else (role.title() or 'Message'))
        _chat_docx_message_header(document,label,_chat_docx_format_timestamp(at),role)
        _chat_docx_markdown(document,text,request)
        if links:
            link_paragraph=document.add_paragraph()
            _chat_docx_para_spacing(link_paragraph,before=1,after=3)
            lead=link_paragraph.add_run('Links: '); lead.bold=True
            for idx,(link_label,link_url) in enumerate(links):
                if idx: link_paragraph.add_run('  ·  ')
                if link_url.startswith('/'): link_url=request.build_absolute_uri(link_url)
                _chat_docx_hyperlink(link_paragraph,link_label,link_url)
        if role=='assistant' and (source_provider or source_model):
            source=document.add_paragraph()
            _chat_docx_para_spacing(source,before=1,after=6,line=1.0)
            run=source.add_run(' · '.join(x for x in (source_provider,source_model) if x))
            run.font.size=Pt(9.5); run.font.color.rgb=RGBColor(105,122,134)

    buffer=io.BytesIO(); document.save(buffer)
    stamp=timezone.localtime(timezone.now()).strftime('%Y%m%d-%H%M%S')
    response=HttpResponse(buffer.getvalue(),content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition']=f'attachment; filename="ScoutBox-chat-{stamp}.docx"'
    return response


@login_required
@require_POST
def chatbot_test(request):
    """Test the same Chatbot reasoning/provider path used by queued Ask ScoutBox jobs."""
    provider=(request.POST.get('provider') or '').strip().lower()
    model=(request.POST.get('model') or '').strip()
    allowed={'ollama','openai','gemini','openrouter'}
    if provider not in allowed or not model:
        return JsonResponse({'ok':False,'error':'Select an enabled provider and exact model first.'},status=400)
    cfg=AIProviderConfig.objects.filter(provider=provider,enabled=True).first()
    if not cfg:
        return JsonResponse({'ok':False,'error':'The selected provider is not enabled.'},status=400)
    lane=(request.POST.get('lane') or 'primary').strip().lower()
    if lane not in {'primary','secondary'}: lane='primary'
    allow_internet=provider in {'openai','gemini','openrouter'} and str(request.POST.get('allow_internet_search') or '').lower() in {'1','true','yes','on'}
    question=(
        'Use live internet search to identify the official Python programming language website and give its explicit URL in one or two sentences.'
        if allow_internet else
        'Where do deleted items go in ScoutBox, and what happens to recycled opportunities and Hidden Leads?'
    )
    try:
        result=chatbot_answer(
            question,history=[],current_path='/ai/',force_ai=True,
            provider_override=provider,model_override=model,
            allow_internet_override=allow_internet,raise_errors=True,
        )
        answer=str(result.get('answer') or '').strip()
        sources=[str(x.get('url') or '') for x in (result.get('links') or []) if isinstance(x,dict) and str(x.get('url') or '').startswith(('http://','https://'))][:6]
        ok=bool(answer)
        try:
            log('chatbot.test',request,summary=f'{provider} · {model}',metadata={'ok':ok,'provider':provider,'model':model,'lane':lane,'question':question,'internet_search':allow_internet,'sources':sources,'execution_path':'chatbot.ask'})
        except Exception:
            pass
        tested_at=timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M:%S')
        return JsonResponse({'ok':ok,'question':question,'answer':answer or 'The selected model returned an empty answer.','provider':provider,'model':model,'lane':lane,'tested_at':tested_at,'used_ai':True,'internet_search':allow_internet,'sources':sources})
    except Exception as exc:
        detail=re.sub(r'(?i)(api[_ -]?key|authorization|bearer|password|token)\s*[:=]\s*[^\s,;]+',r'\1=[redacted]',str(exc or 'Chatbot provider request failed.'))[:800]
        try:
            log('chatbot.test',request,summary=f'{provider} · {model}',metadata={'ok':False,'provider':provider,'model':model,'lane':lane,'question':question,'internet_search':allow_internet,'error':detail,'execution_path':'chatbot.ask'})
        except Exception:
            pass
        tested_at=timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M:%S')
        return JsonResponse({'ok':False,'question':question,'provider':provider,'model':model,'lane':lane,'tested_at':tested_at,'internet_search':allow_internet,'error':detail},status=200)


def login_view(request):
    if request.user.is_authenticated: return redirect('dashboard')
    if request.method=='POST':
        email=request.POST.get('email','').strip()
        u=authenticate(request,username=email,password=request.POST.get('password',''))
        if not u:
            found=User.objects.filter(email__iexact=email).first()
            if found: u=authenticate(request,username=found.username,password=request.POST.get('password',''))
        if u:
            login(request,u); log('login',request,summary='Successful login'); return redirect('dashboard')
        messages.error(request,'Invalid email or password.')
    return render(request,'portal/login.html',{})



@login_required
def logout_view(request):
    log('logout',request,summary='User logged out'); logout(request); return redirect('login')


@login_required
def toggle_background(request):
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    ps.background_paused=not ps.background_paused; ps.background_state_changed_at=timezone.now(); ps.save(update_fields=['background_paused','background_state_changed_at','updated_at'])
    log('background.pause' if ps.background_paused else 'background.resume',request,summary='Background work state changed')
    nxt=request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse('dashboard')
    return redirect(nxt)


def _activity_timing_text(started_at,last_activity=None):
    if not started_at:
        return ''
    started=timezone.localtime(started_at)
    last=timezone.localtime(last_activity) if last_activity else None
    now=timezone.localtime(timezone.now())
    start_fmt='%d %b %H:%M' if started.year==now.year else '%d %b %Y %H:%M'
    started_text=started.strftime(start_fmt)
    if not last or abs((last-started).total_seconds())<60:
        return f'started {started_text}'
    if last.date()==started.date():
        last_text=last.strftime('%H:%M')
    elif last.year==started.year:
        last_text=last.strftime('%d %b %H:%M')
    else:
        last_text=last.strftime('%d %b %Y %H:%M')
    return f'started {started_text} · last activity {last_text}'


def _running_activity_rows():
    rows=[]
    now=timezone.now()
    warn_minutes=max(1,int(os.environ.get('SCOUTBOX_CAMPAIGN_STALL_WARN_MINUTES','30') or 30))
    for run in CampaignRun.objects.select_related('campaign').filter(status__in=['queued','running','stopping']).order_by('created_at')[:20]:
        last_activity=run.heartbeat_at or run.started_at or run.created_at
        stalled=bool(run.status=='running' and last_activity and now-last_activity>=timedelta(minutes=warn_minutes))
        message=run.message or run.stage or run.get_status_display()
        if stalled:
            idle=max(1,int((now-last_activity).total_seconds()//60))
            stage=(run.stage or run.message or 'campaign work').strip()
            message=f'Possible stall · {stage} · no update for {idle} min'
        rows.append({'kind':'Campaign','label':run.campaign.name,'status':run.get_status_display(),'progress':run.progress,'message':message,'url':reverse('campaign_detail',args=[run.campaign_id]),'cancelable':False,'started_at':timezone.localtime(run.started_at or run.created_at).strftime('%d/%m/%Y %H:%M:%S'),'last_activity':timezone.localtime(last_activity).strftime('%d/%m/%Y %H:%M:%S') if last_activity else '', 'activity_timing':_activity_timing_text(run.started_at or run.created_at,last_activity),'stalled':stalled})
    active_jobs=BackgroundJob.objects.filter(status__in=['queued','running'])
    activity_jobs=list(active_jobs.filter(kind='company_research').order_by('created_at'))
    activity_jobs+=list(active_jobs.exclude(kind='company_research').order_by('created_at')[:200])
    for job in activity_jobs:
        result=job.result or {}
        opp_id=result.get('opportunity_id'); lead_id=result.get('lead_id') or result.get('market_lead_id')
        if opp_id and Opportunity.objects.filter(pk=opp_id,user_deleted=True).exists(): continue
        if lead_id and CompanyLead.objects.filter(pk=lead_id,user_deleted=True).exists(): continue
        if job.kind in ('import_text','import_document','mail_scan'): url=reverse('applications')+'#import-history'
        elif job.kind=='diagnostic': url=(reverse('dashboard')+'#diagnostics') if job.label=='System diagnostics' else reverse('ai')
        elif job.kind=='performance': url=reverse('performance')
        elif (job.result or {}).get('application_id'): url=reverse('application_edit',args=[job.result['application_id']])
        elif job.kind=='cold_draft': url=reverse('applications')
        elif job.kind=='filter_opportunities': url=reverse('opportunities')
        elif job.kind=='filter_hidden_leads': url=reverse('cold_contact')
        elif job.kind=='filter_contacts': url=reverse('contacts')
        elif job.kind in ('enrich','prepare','translate','company_research') and (job.result or {}).get('opportunity_id'): url=reverse('opportunity_detail',args=[job.result['opportunity_id']])
        else: url=reverse('dashboard')
        tool=str((job.result or {}).get('tool') or '')
        compact_tool=tool in ('compare_model','generate_cv','generate_cover','answers')
        kind_label={'hidden_scan':'Hidden Leads','filter_opportunities':'Opportunity re-evaluation','filter_hidden_leads':'Hidden Lead re-evaluation','filter_contacts':'Re-evaluating…'}.get(job.kind,job.get_kind_display())
        if tool=='candidate_profile_autopopulate': kind_label='Candidate Profile'
        rows.append({'kind':kind_label,'job_kind':job.kind,'label':job.label,'status':job.get_status_display(),'progress':job.progress,'message':job.message,'url':url,'compact':compact_tool,'cancelable':True,'job_id':job.pk,'started_at':timezone.localtime(job.started_at or job.created_at).strftime('%d/%m/%Y %H:%M:%S'),'activity_timing':_activity_timing_text(job.started_at or job.created_at)})
    return rows


def _readiness_items():
    ps=PortalSettings.objects.get_or_create(pk=1)[0]; p=Profile.objects.get_or_create(pk=1)[0]
    ai_configs=list(AIProviderConfig.objects.filter(enabled=True))
    ai_state=ai_compute_readiness()
    active_ai=bool(ai_state.get('ready'))
    accelerator=local_accelerator_state()
    local_gpu=bool(accelerator.get('detected'))
    local_models=[]
    try: local_models=ollama_service.list_models()
    except Exception: local_models=[]
    cloud_cfgs=[x for x in ai_configs if x.provider!='ollama']
    cloud_tested=any(bool(x.last_test_ok) for x in cloud_cfgs)
    cloud_credentialed=False
    for cfg in cloud_cfgs:
        try:
            if decrypt(cfg.api_key_enc):
                cloud_credentialed=True; break
        except Exception:
            continue
    cloud_states=[x for x in (ai_state.get('states') or []) if x.get('provider')!='ollama']
    cloud_ready=sum(1 for x in cloud_states if x.get('ready'))
    if local_gpu:
        ai_runtime_ok=True; ai_runtime_info=False
        gpu_label=str(accelerator.get('label') or 'Local GPU')
        ai_runtime_detail=f'{gpu_label} detected · {len(local_models)} local model{"" if len(local_models)==1 else "s"} installed'
    elif cloud_tested or cloud_ready:
        ai_runtime_ok=True; ai_runtime_info=False
        ai_runtime_detail=f'{max(cloud_ready,1)} tested cloud AI provider{"" if max(cloud_ready,1)==1 else "s"} ready · no local GPU detected'
    elif cloud_credentialed:
        ai_runtime_ok=False; ai_runtime_info=True
        ai_runtime_detail='Cloud AI credentials configured but not successfully tested · no local GPU detected'
    else:
        ai_runtime_ok=False; ai_runtime_info=False
        ai_runtime_detail='No local GPU detected and no Cloud AI credentials configured'
    cv_count=DocumentAsset.objects.filter(kind='cv',active=True).count(); cover_count=DocumentAsset.objects.filter(kind='cover',active=True).count()
    search_profile=build_search_profile()
    skills=len(search_profile.get('skills') or []); roles=len(search_profile.get('role_families') or [])
    campaigns=Campaign.objects.filter(deleted_at__isnull=True).count(); generated_templates=CampaignTemplate.objects.filter(Q(description__startswith='[Generated from Candidate Profile]')|Q(description__startswith='[Generated from Resume #]')).count(); running_campaigns=CampaignRun.objects.filter(campaign__deleted_at__isnull=True,status__in=['queued','running','stopping']).values('campaign_id').distinct().count(); running=running_campaigns; pending=max(0,Campaign.objects.filter(enabled=True,deleted_at__isnull=True).count()-running_campaigns)
    enabled_sources=SearchSource.objects.filter(enabled=True).count(); total_sources=SearchSource.objects.count(); search_engines=SearchSource.objects.filter(enabled=True,source_type__in=['search_engine','regional_search']).count()
    if ps.discovery_mode=='cloud_web':
        search_ok=active_ai; mode='cloud AI'; search_route='ai'
    else:
        search_ok=search_engines>0; mode='Local AI Discovery' if any(x.provider=='ollama' for x in ai_configs) else 'Local AI Discovery (local model not ready)'; search_route='sources'
    email=EmailProfile.objects.filter(active=True).first()
    if email:
        incoming=(email.imap_email or email.imap_username or email.imap_host or 'not configured').strip(); outgoing=(('Resend API' if outgoing_method(email)=='resend' else (email.smtp_host or email.smtp_username or 'not configured')) if email else 'not configured'); email_detail=f'Incoming: {incoming} · Outgoing: {outgoing} ({email.get_template_display()})'
    else:
        email_detail='Incoming: not configured · Outgoing: not configured'
    return [
        {'label':'Candidate profile','ok':bool(p.display_name and (p.operating_locations or p.operating_location)),'detail':f'{skills} skill{"" if skills==1 else "s"} · {roles} role target{"" if roles==1 else "s"}','route':'profile'},
        {'label':'Resumes & Cover Letters','ok':cv_count>0,'detail':f'{cv_count} Resume{"" if cv_count==1 else "s"} · {cover_count} Cover Letter{"" if cover_count==1 else "s"}','route':'profile'},
        {'label':'Discovery path','ok':search_ok and active_ai,'detail':f'{search_engines} search engine{"" if search_engines==1 else "s"} configured · {total_sources} source{"" if total_sources==1 else "s"} total ({enabled_sources} enabled) · {mode}','route':search_route},
        {'label':'Campaigns','ok':generated_templates>0,'detail':f"{generated_templates} generated template{' ' if generated_templates==1 else 's'} · {campaigns} campaign{' ' if campaigns==1 else 's'} · {running} running · {pending} scheduled/pending".replace('template  ·','template ·').replace('campaign  ·','campaign ·'),'route':'campaigns','optional':True},
        {'label':'Email profile','ok':bool(email),'detail':email_detail,'route':'email_config','optional':True},
        {'label':'AI runtime','ok':ai_runtime_ok,'detail':ai_runtime_detail,'route':'ai','informational':ai_runtime_info},
    ]


@login_required
def quick_start(request):
    # Quick Start now lives on Dashboard; retain this route for old bookmarks.
    return redirect(reverse('dashboard') + '#first-run-readiness')


def _runtime_component_versions():
    """Best-effort About-page component versions; never make About depend on them."""
    def pkg(name):
        try: return package_version(name)
        except Exception: return ''
    info={'django':pkg('Django'),'gunicorn':pkg('gunicorn'),'celery':pkg('celery'),'postgresql':'','redis':''}
    try:
        with connection.cursor() as cur:
            cur.execute('SHOW server_version')
            info['postgresql']=str(cur.fetchone()[0] or '')
    except Exception:
        pass
    try:
        import redis as redis_client
        client=redis_client.Redis.from_url(settings.CELERY_BROKER_URL,socket_connect_timeout=1.5,socket_timeout=1.5)
        info['redis']=str((client.info(section='server') or {}).get('redis_version') or '')
    except Exception:
        info['redis']=pkg('redis')
    return info


def _about_mail_servers():
    profile=EmailProfile.objects.filter(active=True).first()
    if not profile: return {'incoming':'Not configured','outgoing':'Not configured'}
    incoming=(f'{profile.imap_host}:{profile.imap_port}' if profile.imap_host else 'Not configured')
    if outgoing_method(profile)=='resend':
        outgoing='Resend API · api.resend.com'
    else:
        outgoing=(f'{profile.smtp_host}:{profile.smtp_port}' if profile.smtp_host else 'SMTP not configured')
    return {'incoming':incoming,'outgoing':outgoing}


def _about_architecture_stats():
    """Live, non-secret counts shown only for orientation on About ScoutBox."""
    stats={
        'opportunities':Opportunity.objects.filter(suppressed=False,user_deleted=False).count(),
        'leads':CompanyLead.objects.filter(user_deleted=False,deleted_at__isnull=True).count(),
        'contacts':Contact.objects.filter(deleted_at__isnull=True).count(),
        'applications':Application.objects.filter(opportunity__user_deleted=False,deleted_at__isnull=True).count(),
        'local_ollama_models':0,'cloud_provider_count':0,'cloud_provider_names':[],
        'persistent_storage':'0.0 MB',
    }
    try:
        diag=_safe_ollama_diagnostics()
        stats['local_ollama_models']=len(diag.get('installed') or [])
    except Exception:
        diag={'installed':[]}
    try:
        configs=list(configured_cloud_configs(require_key=True,require_model=True))
        names=[]
        aliases={'openai':'OpenAI','gemini':'Gemini','openrouter':'OpenRouter'}
        for cfg in configs:
            name=aliases.get(str(getattr(cfg,'provider','') or '').lower(),str(getattr(cfg,'provider','') or '').title())
            if name and name not in names: names.append(name)
        stats['cloud_provider_names']=names; stats['cloud_provider_count']=len(names)
    except Exception:
        pass
    try:
        stats['persistent_storage']=_disk_usage_breakdown(_system_snapshot(),diag).get('scoutbox_used_pretty') or '0.0 MB'
    except Exception:
        pass
    return stats


def _about_discovery_config(arch_stats=None):
    """Return a concise, non-secret snapshot of the discovery configuration for About."""
    arch_stats=arch_stats or {}
    try:
        ps=PortalSettings.objects.get_or_create(pk=1)[0]
        mode=str(ps.discovery_mode or 'source_guided').strip().lower()
    except Exception:
        mode='source_guided'
    try:
        enabled=list(SearchSource.objects.filter(enabled=True).only('name','config_json'))
    except Exception:
        enabled=[]
    direct_count=0
    for source in enabled:
        cfg=source.config_json if isinstance(source.config_json,dict) else {}
        if str(cfg.get('direct_adapter') or '').strip():
            direct_count+=1
    try:
        from portal.services.discovery_markets import enabled_markets
        market_count=len(enabled_markets(ps))
    except Exception:
        market_count=0
    if mode=='cloud_web':
        providers=', '.join(arch_stats.get('cloud_provider_names') or []) or 'no cloud API provider configured'
        summary=f'{providers} · {direct_count} direct source{"" if direct_count==1 else "s"} enabled'
        label='Cloud Web Discovery'
    else:
        local_models=int(arch_stats.get('local_ollama_models') or 0)
        summary=(f'{local_models} Ollama model{"" if local_models==1 else "s"} detected · '
                 f'{len(enabled)} source{"" if len(enabled)==1 else "s"} enabled · '
                 f'{market_count} discovery market{"" if market_count==1 else "s"} enabled')
        label='Local AI Discovery'
    return {'mode_key':mode,'mode_label':label,'summary':summary}


def _about_page_context(request):
    arch_stats=_about_architecture_stats()
    return ctx(request,'about','About ScoutBox',arch_versions=_runtime_component_versions(),arch_mail=_about_mail_servers(),arch_stats=arch_stats,discovery_config=_about_discovery_config(arch_stats))


def _about_docx_from_html(html_text, request=None):
    """Convert the rendered About ScoutBox reference into a troubleshooting-friendly DOCX."""
    from bs4 import BeautifulSoup
    from docx import Document
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    soup=BeautifulSoup(str(html_text or ''),'html.parser')
    root=soup.select_one('.about-scoutbox')
    if root is None:
        raise ValueError('About ScoutBox content could not be rendered for export.')
    for node in root.select('[data-docx-skip],script,style'):
        node.decompose()

    document=Document()
    section=document.sections[0]
    section.top_margin=Inches(0.65); section.bottom_margin=Inches(0.65)
    section.left_margin=Inches(0.72); section.right_margin=Inches(0.72)
    normal=document.styles['Normal']; normal.font.name='Aptos'; normal.font.size=Pt(10.5)
    normal.paragraph_format.space_after=Pt(4); normal.paragraph_format.line_spacing=1.08
    for style_name,size in [('Title',18),('Heading 1',15),('Heading 2',13.5),('Heading 3',12),('Heading 4',11)]:
        try:
            style=document.styles[style_name]; style.font.name='Aptos'; style.font.size=Pt(size); style.font.bold=True
            style.paragraph_format.space_before=Pt(7); style.paragraph_format.space_after=Pt(4)
        except Exception:
            pass
    document.add_heading('About ScoutBox',0)
    meta=document.add_paragraph('Exported '+timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M:%S'))
    meta.runs[0].font.size=Pt(9); meta.runs[0].font.color.rgb=RGBColor(92,108,120)

    selected='.about-build,h2,h3,h4,p,pre,.terminal-command,.workflow-step,.architecture-diagram,.architecture-notes-column > div,.database-table-list > div,.database-command-copy,.redis-learning-card,.about-links'
    blocks=list(root.select(selected))
    block_ids={id(x) for x in blocks}

    def has_selected_parent(node):
        parent=getattr(node,'parent',None)
        while parent is not None and parent is not root:
            if id(parent) in block_ids: return True
            parent=getattr(parent,'parent',None)
        return False

    def add_plain(text, *, bold_lead=''):
        text=' '.join(str(text or '').split())
        if not text: return
        paragraph=document.add_paragraph()
        if bold_lead and text.startswith(bold_lead):
            lead=paragraph.add_run(bold_lead); lead.bold=True
            paragraph.add_run(text[len(bold_lead):])
        else:
            paragraph.add_run(text)

    def add_code(text):
        value=str(text or '').strip('\n')
        if not value: return
        paragraph=document.add_paragraph()
        paragraph.paragraph_format.space_before=Pt(2); paragraph.paragraph_format.space_after=Pt(5)
        run=paragraph.add_run(value); run.font.name='Aptos Mono'; run.font.size=Pt(8.5)
        run.font.color.rgb=RGBColor(40,58,70)

    def _cell_shading(cell, fill):
        tcPr=cell._tc.get_or_add_tcPr()
        shd=tcPr.find(qn('w:shd'))
        if shd is None:
            shd=OxmlElement('w:shd'); tcPr.append(shd)
        shd.set(qn('w:fill'),fill)

    def _cell_margins(cell, top=70, start=85, bottom=70, end=85):
        tc=cell._tc; tcPr=tc.get_or_add_tcPr()
        tcMar=tcPr.first_child_found_in('w:tcMar')
        if tcMar is None:
            tcMar=OxmlElement('w:tcMar'); tcPr.append(tcMar)
        for tag,value in [('top',top),('start',start),('bottom',bottom),('end',end)]:
            node=tcMar.find(qn('w:'+tag))
            if node is None:
                node=OxmlElement('w:'+tag); tcMar.append(node)
            node.set(qn('w:w'),str(value)); node.set(qn('w:type'),'dxa')

    def _architecture_boxes(diagram):
        boxes={}
        for group in diagram.select('g.arch-box'):
            lines=[]
            for node in group.select('text'):
                value=' '.join(node.get_text(' ',strip=True).split())
                if value:
                    lines.append((value,'arch-hint' in (node.get('class') or [])))
            if not lines:
                continue
            boxes[lines[0][0]]={'lines':lines,'classes':set(group.get('class') or [])}
        return boxes

    def _add_architecture_box(cell, box):
        cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
        classes=set((box or {}).get('classes') or [])
        fill='EAF5FA' if 'arch-runtime' in classes else ('EEF3F7' if 'arch-data' in classes else ('F3F5F7' if 'arch-external' in classes else 'F1F6F4'))
        _cell_shading(cell,fill); _cell_margins(cell)
        paragraph=cell.paragraphs[0]; paragraph.alignment=WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_before=Pt(1); paragraph.paragraph_format.space_after=Pt(1)
        lines=list((box or {}).get('lines') or [])
        for idx,(value,is_hint) in enumerate(lines):
            if idx:
                paragraph.add_run('\n')
            run=paragraph.add_run(value)
            run.font.name='Aptos'; run.font.size=Pt(7.7 if is_hint else (9.0 if idx else 9.5))
            run.bold=(not is_hint and idx<=1)
            if is_hint:
                run.font.color.rgb=RGBColor(86,105,117)
            else:
                run.font.color.rgb=RGBColor(28,54,70)

    def _add_architecture_flow(label, keys, boxes):
        phase=document.add_paragraph()
        phase.paragraph_format.space_before=Pt(5); phase.paragraph_format.space_after=Pt(2)
        r=phase.add_run(label); r.bold=True; r.font.size=Pt(9.2); r.font.color.rgb=RGBColor(46,83,103)
        table=document.add_table(rows=1,cols=5)
        table.alignment=WD_TABLE_ALIGNMENT.CENTER; table.autofit=False
        widths=[Inches(1.92),Inches(0.22),Inches(1.92),Inches(0.22),Inches(1.92)]
        for idx,width in enumerate(widths):
            table.columns[idx].width=width
            table.cell(0,idx).width=width
        for pos,key in enumerate(keys):
            _add_architecture_box(table.cell(0,pos*2),boxes.get(key,{'lines':[(key,False)],'classes':set()}))
            if pos<2:
                arrow=table.cell(0,pos*2+1); arrow.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER; _cell_margins(arrow,0,0,0,0)
                ap=arrow.paragraphs[0]; ap.alignment=WD_ALIGN_PARAGRAPH.CENTER; ap.paragraph_format.space_after=Pt(0)
                ar=ap.add_run('→'); ar.font.name='Aptos'; ar.font.size=Pt(14); ar.font.color.rgb=RGBColor(82,126,150)
        # Remove the grid/borders; the shaded component cells provide the visual boxes.
        tblPr=table._tbl.tblPr
        borders=tblPr.first_child_found_in('w:tblBorders')
        if borders is None:
            borders=OxmlElement('w:tblBorders'); tblPr.append(borders)
        for edge in ('top','left','bottom','right','insideH','insideV'):
            node=borders.find(qn('w:'+edge))
            if node is None:
                node=OxmlElement('w:'+edge); borders.append(node)
            node.set(qn('w:val'),'nil')

    def add_architecture_diagram(diagram):
        desc=diagram.select_one('desc')
        if desc:
            intro=document.add_paragraph(' '.join(desc.get_text(' ',strip=True).split()))
            intro.paragraph_format.space_after=Pt(5)
            for run in intro.runs:
                run.italic=True; run.font.size=Pt(9); run.font.color.rgb=RGBColor(83,101,113)
        boxes=_architecture_boxes(diagram)
        flows=[
            ('Web request path',('Browser / UI','Django','PostgreSQL')),
            ('Queue and scheduling',('Celery Beat','Redis','Celery Worker')),
            ('Discovery execution',('Discovery','Cloud AI / Ollama','Search + HTTP')),
            ('Qualification and records',('Qualification','ScoutBox Records','Applications')),
            ('Outreach and persistent files',('SMTP / IMAP','Applications','Media / Files')),
        ]
        for label,keys in flows:
            _add_architecture_flow(label,keys,boxes)
        note=document.add_paragraph('Arrows show the primary operational flow. The component notes below describe the persistent and cross-service relationships in more detail.')
        note.paragraph_format.space_before=Pt(4); note.paragraph_format.space_after=Pt(6)
        for run in note.runs:
            run.font.size=Pt(8.6); run.font.color.rgb=RGBColor(83,101,113)

    for node in blocks:
        if has_selected_parent(node):
            continue
        classes=set(node.get('class') or [])
        name=(node.name or '').lower()
        if 'about-build' in classes:
            add_plain(node.get_text(' · ',strip=True)); continue
        if name in {'h2','h3','h4'}:
            value=node.get_text(' ',strip=True)
            if not value or (name=='h2' and value=='ScoutBox'): continue
            document.add_heading(value,level={'h2':1,'h3':2,'h4':3}[name]); continue
        if 'architecture-diagram' in classes:
            add_architecture_diagram(node); continue
        if name=='pre':
            add_code(node.get_text('\n',strip=False)); continue
        if 'terminal-command' in classes:
            code=node.find('code'); description=node.find('span')
            if code: add_code(code.get_text('\n',strip=False))
            if description: add_plain(description.get_text(' ',strip=True))
            continue
        if 'workflow-step' in classes:
            title=node.find('b'); detail=node.find('small')
            paragraph=document.add_paragraph()
            if title:
                run=paragraph.add_run(title.get_text(' ',strip=True)+': '); run.bold=True
            if detail: paragraph.add_run(detail.get_text(' ',strip=True))
            continue
        if 'redis-learning-card' in classes:
            title=node.find('b'); detail=node.find('span')
            paragraph=document.add_paragraph()
            if title:
                run=paragraph.add_run(title.get_text(' ',strip=True)+': '); run.bold=True
            if detail: paragraph.add_run(detail.get_text(' ',strip=True))
            continue
        if 'database-command-copy' in classes:
            title=node.find('b'); detail=node.find('span')
            paragraph=document.add_paragraph()
            if title:
                run=paragraph.add_run(title.get_text(' ',strip=True)+': '); run.bold=True
            if detail: paragraph.add_run(detail.get_text(' ',strip=True))
            continue
        if 'database-table-list' in set((getattr(node.parent,'get',lambda *_:[])('class') or [])):
            code=node.find('code'); detail=node.find('span')
            paragraph=document.add_paragraph()
            if code:
                run=paragraph.add_run(code.get_text(' ',strip=True)+': '); run.bold=True; run.font.name='Aptos Mono'
            if detail: paragraph.add_run(detail.get_text(' ',strip=True))
            continue
        if 'architecture-notes-column' in set((getattr(node.parent,'get',lambda *_:[])('class') or [])):
            title=node.find('b'); detail=node.find('span')
            paragraph=document.add_paragraph()
            if title:
                run=paragraph.add_run(title.get_text(' ',strip=True)+': '); run.bold=True
            if detail: paragraph.add_run(detail.get_text(' ',strip=True))
            continue
        if 'about-links' in classes:
            for link in node.find_all('a',href=True):
                paragraph=document.add_paragraph(style='List Bullet')
                label=link.get_text(' ',strip=True); href=str(link.get('href') or '').strip()
                if href.startswith('/') or href.startswith('#'):
                    run=paragraph.add_run(label); run.bold=True
                elif href.startswith(('http://','https://')):
                    _chat_docx_hyperlink(paragraph,label,href)
                else:
                    run=paragraph.add_run(label); run.bold=True
            continue
        if name=='p':
            # Internal ScoutBox navigation labels are useful prose in the Word export,
            # but internal portal URLs are not. Render those labels as bold text;
            # retain real hyperlinks only for explicit external references.
            from bs4.element import NavigableString, Tag
            paragraph=document.add_paragraph()
            def append_piece(value, *, bold=False, external_url=''):
                value=' '.join(str(value or '').split())
                if not value:
                    return
                existing=''.join(run.text for run in paragraph.runs)
                if existing and not existing.endswith((' ','/','–','—','(')) and not value.startswith(('.',',',';',':',')','/','–','—')):
                    paragraph.add_run(' ')
                if external_url:
                    _chat_docx_hyperlink(paragraph,value,external_url,bold=bold)
                else:
                    run=paragraph.add_run(value); run.bold=bold
            def walk(child, inherited_bold=False):
                if isinstance(child,NavigableString):
                    append_piece(str(child),bold=inherited_bold); return
                if not isinstance(child,Tag):
                    return
                child_name=(child.name or '').lower()
                bold=inherited_bold or child_name in {'b','strong'}
                if child_name=='a':
                    label=child.get_text(' ',strip=True)
                    href=str(child.get('href') or '').strip()
                    if href.startswith('/') or href.startswith('#'):
                        append_piece(label,bold=True)
                    elif href.startswith(('http://','https://')):
                        append_piece(label,external_url=href,bold=bold)
                    else:
                        append_piece(label,bold=True)
                    return
                for sub in child.children:
                    walk(sub,bold)
            for child in node.children:
                walk(child)
            if not ''.join(run.text for run in paragraph.runs).strip():
                p_el=paragraph._element; p_el.getparent().remove(p_el)

    buffer=io.BytesIO(); document.save(buffer)
    return buffer.getvalue()


@login_required
def about_view(request):
    return render(request,'portal/about.html',_about_page_context(request))


@login_required
def about_export_docx(request):
    """Export the complete rendered About ScoutBox reference as a Word document."""
    from django.template.loader import render_to_string
    page_context=_about_page_context(request)
    html_text=render_to_string('portal/about.html',page_context,request=request)
    payload=_about_docx_from_html(html_text,request)
    stamp=timezone.localtime(timezone.now()).strftime('%Y%m%d-%H%M%S')
    response=HttpResponse(payload,content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition']=f'attachment; filename="ScoutBox-about-{stamp}.docx"'
    return response


def _error_notification_components(hours=24):
    """Return recent error notifications grouped by component/provider.

    The notification badges are a rolling operational view, not an unread inbox:
    clicking Dashboard, Recent Errors, Resource Usage, Statistics, Settings or the
    top-right notification control must not acknowledge/reset them.  A component
    remains represented for 24 hours after its latest recorded error.
    """
    since=timezone.now()-timedelta(hours=max(1,int(hours or 24)))
    groups={}

    def add(component, label, detail, at, count=1, url=''):
        component=' '.join(str(component or 'ScoutBox').split()).strip() or 'ScoutBox'
        label=' '.join(str(label or component).split()).strip() or component
        detail=' '.join(str(detail or 'Request failed').split()).strip() or 'Request failed'
        at=at or timezone.now()
        try: count=max(1,int(count or 1))
        except Exception: count=1
        key=component.casefold()
        row=groups.get(key)
        if row is None:
            groups[key]={'component':key,'label':label,'detail':detail,'at':at,'count':count,'url':url}
            return
        row['count']+=count
        if at >= (row.get('at') or at):
            row.update({'label':label,'detail':detail,'at':at,'url':url or row.get('url','')})

    def metric_component(metric):
        provider=str(metric.provider or '').strip()
        if provider: return provider
        stage=str(metric.stage or '').strip()
        category=str(metric.category or '').strip()
        return stage or category or 'ScoutBox'

    def job_component(job):
        label=str(job.label or '').strip()
        lowered=label.casefold()
        if lowered.startswith('search test:'):
            return label.split(':',1)[1].strip() or 'Search provider'
        m=re.match(r'^(openai|gemini|openrouter|ollama)\b', lowered)
        if m: return m.group(1).title()
        kind=str(job.kind or '').strip()
        return kind or (label.split(':',1)[0].strip() if label else 'Background job')

    try:
        for metric in UsageMetric.objects.filter(at__gte=since,errors__gt=0).exclude(category='lab').exclude(stage='provider_test').order_by('-at')[:2000]:
            meta=metric.metadata or {}
            detail=str(meta.get('error') or meta.get('message') or '').strip()
            label=metric_component(metric)
            count=max(1,int(metric.errors or 1))
            add(label,label,detail or f'{count} failed request{"s" if count != 1 else ""}',metric.at,count,reverse('telemetry')+'?errors=1')
        for job in BackgroundJob.objects.filter(status='failed',finished_at__gte=since).order_by('-finished_at','-created_at')[:500]:
            component=job_component(job)
            module=(str(job.label or '').split(':',1)[0].strip() or job.get_kind_display() or component)
            add(component,module,job.error or job.message or 'Background task failed',job.finished_at or job.created_at,1,reverse('dashboard')+'#recent-errors')
    except Exception:
        return []
    return sorted(groups.values(),key=lambda x:x.get('at') or timezone.now(),reverse=True)


def _new_error_count(ps=None):
    """Rolling 24-hour count of distinct error-notification components."""
    return len(_error_notification_components(24))


def _ack_dashboard_errors(request, ps=None):
    """Compatibility no-op: recent error badges are rolling 24-hour indicators."""
    return ps or PortalSettings.objects.get_or_create(pk=1)[0]


def _maybe_ack_dashboard_errors(request, ps=None):
    return ps or PortalSettings.objects.get_or_create(pk=1)[0]


@login_required
@require_POST
def dashboard_error_ack(request):
    # Older front ends may still call this endpoint. Do not reset anything: the
    # badge is derived from the last 24 hours of grouped notification components.
    return JsonResponse({'ok':True,'new_errors':_new_error_count()})


def _new_error_notifications(ps=None, limit=5):
    """Latest error notification components from the rolling 24-hour window."""
    selected=_error_notification_components(24)[:max(0,int(limit or 0))]
    now=timezone.now()
    out=[]
    for row in selected:
        count=max(1,int(row.get('count') or 1))
        detail=_pulse_text(row.get('detail') or 'Request failed',108)
        out.append({
            'kind':'Error',
            'label':row.get('label') or 'ScoutBox',
            'detail':detail,
            'text':_pulse_text(f'{row.get("label") or "ScoutBox"}: {detail}',120),
            'url':row.get('url') or reverse('telemetry')+'?errors=1',
            'at':row.get('at'),
            'count':count,
            'age_text':_relative_popup_time(row.get('at'),now=now),
        })
    return out


AI_EMPTY_OUTPUT_WARNING_WINDOW_MINUTES=15
AI_EMPTY_OUTPUT_WARNING_THRESHOLD=3


def _ai_empty_output_warning_notifications(limit=5):
    """Operational warnings for repeated AI calls that returned no usable text.

    A single blank response remains visible in AI Requests as Empty response. The global
    notification surface only lights up after repeated blanks so one transient model
    miss does not create alert noise.
    """
    now=timezone.now()
    since=now-timedelta(minutes=AI_EMPTY_OUTPUT_WARNING_WINDOW_MINUTES)
    try:
        rows=list(AIRequestLog.objects.filter(at__gte=since,status='empty_response').exclude(provider='').order_by('-at')[:1000])
    except Exception:
        return []
    groups={}
    total=[]
    for row in rows:
        if str(row.output_text or '').strip():
            continue
        meta=row.metadata if isinstance(row.metadata,dict) else {}
        code=str(meta.get('warning_code') or '').strip().lower()
        # 0.8.124 is the first version with warning_code. Historical blank rows are
        # intentionally counted too after migration so the Dashboard reflects reality
        # immediately after upgrade.
        if code and code!='empty_output':
            continue
        provider=str(row.provider or 'AI').strip() or 'AI'
        model=str(row.model or '').strip()
        stage=str(row.stage or 'AI request').strip() or 'AI request'
        key=(provider.casefold(),model.casefold(),stage.casefold())
        group=groups.setdefault(key,{'provider':provider,'model':model,'stage':stage,'count':0,'at':row.at})
        group['count']+=1
        if row.at and (not group.get('at') or row.at>group['at']):
            group['at']=row.at
        total.append(row)
    selected=[]
    for group in groups.values():
        if group['count'] < AI_EMPTY_OUTPUT_WARNING_THRESHOLD:
            continue
        model_part=f" · {group['model']}" if group['model'] else ''
        label=f"{group['provider']}{model_part}"
        detail=(
            f"{group['count']} {group['stage'].replace('_',' ')} AI requests returned no visible output "
            f"in the last {AI_EMPTY_OUTPUT_WARNING_WINDOW_MINUTES} minutes. Classification/filtering may be dropping candidates."
        )
        selected.append({
            'kind':'Warning','label':label,'detail':detail,'text':_pulse_text(f'{label}: {detail}',150),
            'url':reverse('gpt_log')+'?status=empty_response&period=24h','at':group.get('at'),'count':group['count'],
            'age_text':_relative_popup_time(group.get('at'),now=now),
        })
    # If warning volume is spread across several models/stages, still surface a single
    # aggregate alert once it is clearly systemic.
    if not selected and len(total)>=5:
        latest=total[0].at if total else now
        detail=(
            f"{len(total)} AI requests returned no visible output in the last "
            f"{AI_EMPTY_OUTPUT_WARNING_WINDOW_MINUTES} minutes. Review AI Requests and local model selection."
        )
        selected.append({
            'kind':'Warning','label':'AI output','detail':detail,'text':detail,
            'url':reverse('gpt_log')+'?status=empty_response&period=24h','at':latest,'count':len(total),
            'age_text':_relative_popup_time(latest,now=now),
        })
    selected.sort(key=lambda x:x.get('at') or now,reverse=True)
    return selected[:max(0,int(limit or 0))]


def _new_ai_output_warning_count():
    return len(_ai_empty_output_warning_notifications(100))


def _recent_alert_notifications(ps=None, limit=5):
    """Merge recent errors, AI-output warnings and quota events into one history."""
    now=timezone.now()
    alerts=list(_new_error_notifications(ps,max(10,int(limit or 5)*2)))
    alerts.extend(_ai_empty_output_warning_notifications(max(10,int(limit or 5)*2)))
    # Crossing 50% and 80% in one usage jump writes two durable threshold rows with the
    # same current used/limit. Collapse those rows by metric/scope/period and retain the
    # highest/latest crossed threshold so the status popover never repeats 42/50 twice.
    latest={}
    try:
        rows=UsageThresholdNotification.objects.filter(sent_at__gte=now-timedelta(hours=24)).order_by('-sent_at','-threshold')[:100]
        for row in rows:
            key=(str(row.period_key or ''),str(row.metric_key or ''),str(row.campaign_name or ''))
            current=latest.get(key)
            if current is None or float(row.threshold or 0)>float(current.threshold or 0) or (row.threshold==current.threshold and row.sent_at>current.sent_at):
                latest[key]=row
        for row in latest.values():
            pct=(100*float(row.used or 0)/float(row.limit)) if row.limit else float(row.threshold or 0)
            scope=f' on {row.campaign_name}' if row.campaign_name else ''
            detail=f'{row.metric_label}{scope}: {int(row.used or 0):,} / {int(row.limit or 0):,} ({pct:.0f}%)'
            alerts.append({
                'kind':'Limit','label':'Limit','detail':detail,'text':_pulse_text(detail,150),
                'url':reverse('telemetry'),'at':row.sent_at,'count':1,
                'age_text':_relative_popup_time(row.sent_at,now=now),
            })
    except Exception:
        pass
    alerts.sort(key=lambda x:x.get('at') or (now-timedelta(days=36500)),reverse=True)
    return alerts[:max(0,int(limit or 0))]


def _relative_popup_time(value, now=None):
    if not value: return ''
    now=now or timezone.now()
    delta=max(0,int((now-value).total_seconds()))
    if delta < 60: return 'just now'
    if delta < 3600:
        n=max(1,delta//60); return f'{n} min ago'
    if delta < 86400:
        n=max(1,delta//3600); return f'{n} hour{"s" if n != 1 else ""} ago'
    days=max(1,delta//86400)
    if days == 1: return 'yesterday'
    if days <= 7: return f'{days} days ago'
    return timezone.localtime(value).strftime('%d/%m/%Y')


def _lead_popup_hint(lead, words=4):
    """Return a tiny descriptive suffix for the top-bar Hidden Lead list."""
    company=str(getattr(lead,'company','') or '').strip()
    candidates=[getattr(lead,'summary',''),getattr(lead,'match_summary',''),getattr(lead,'evidence','')]
    for raw in candidates:
        text=re.sub(r'\s+',' ',str(raw or '')).strip()
        if not text: continue
        if company:
            text=re.sub(r'^'+re.escape(company)+r'\s*[-—:;]*\s*','',text,flags=re.I)
        text=re.sub(r'(?i)\bother projects\b','',text)
        tokens=re.findall(r"[A-Za-z0-9][A-Za-z0-9+./#-]*",text)
        tokens=[x for x in tokens if x.lower() not in {'the','a','an','and','or','with','for','of','to','their','its','other','projects'}]
        if len(tokens)>=3:
            return ' '.join(tokens[:words])
    return 'technical engineering work'


def _attention_snapshot(ps=None):
    ps=ps or PortalSettings.objects.get_or_create(pk=1)[0]
    unread_opportunities=Opportunity.objects.filter(suppressed=False,user_deleted=False,is_read=False).count()
    unread_market=CompanyLead.objects.filter(user_deleted=False,is_read=False).count()
    unread_applications=Application.objects.filter(opportunity__user_deleted=False,deleted_at__isnull=True,is_read=False).count()
    unread_contacts=Contact.objects.filter(deleted_at__isnull=True,is_read=False).filter(Q(generic=False)|Q(source__iexact='manual')).count()
    unread_facebook_pages=FacebookPage.objects.filter(deleted_at__isnull=True,is_read=False).count()
    new_errors=_new_error_count(ps)
    new_warnings=_new_ai_output_warning_count()
    active_run=CampaignRun.objects.select_related('campaign').filter(status__in=['queued','running','stopping']).order_by('-started_at','-created_at').first()
    active_job=BackgroundJob.objects.filter(status__in=['queued','running']).order_by('-started_at','-created_at').first()
    active_hidden=BackgroundJob.objects.filter(status__in=['queued','running'],kind='hidden_scan').order_by('-started_at','-created_at').first()
    if str(ps.discovery_mode or '').lower()=='cloud_web':
        try:
            if not has_usable_cloud_web_model():
                raise RuntimeError('One or more Cloud Web stages is not configured.')
            cloud_discovery_route(stage='url_scrape'); ai_status={'ready':True,'identifying':False,'reason':'Cloud Web ready'}
        except Exception as exc:
            ai_status={'ready':False,'identifying':False,'reason':str(exc)}
    else:
        ai_status=ai_compute_readiness()
    ai_ready=bool(ai_status.get('ready')); ai_identifying=bool(ai_status.get('identifying'))
    scheduled_next=None
    if not active_run and not active_job and not ps.background_paused and ai_ready:
        scheduled=[]
        now=timezone.now()
        for campaign in Campaign.objects.filter(enabled=True,deleted_at__isnull=True).order_by('name'):
            due=_campaign_next_run(campaign,ps,now)
            if due: scheduled.append((due,campaign))
        scheduled.sort(key=lambda x:x[0])
        scheduled_next=scheduled[0] if scheduled else None

    if active_run:
        activity_state='active'; status_text='Scanning for opportunities'
        campaign_name=active_run.campaign.name; campaign_id=active_run.campaign_id; campaign_created=active_run.campaign.created_at; campaign_started=active_run.started_at or active_run.created_at; campaign_due=None
    elif active_hidden:
        activity_state='active'; status_text='Scanning for hidden leads'
        campaign_name=''; campaign_id=None; campaign_created=None; campaign_started=active_hidden.started_at or active_hidden.created_at; campaign_due=None
    elif active_job:
        activity_state='active'; status_text='Background work in progress'
        campaign_name=''; campaign_started=active_job.started_at or active_job.created_at; campaign_due=None
        campaign_id=None; campaign_created=None
    elif scheduled_next:
        due,campaign=scheduled_next
        local_due=timezone.localtime(due)
        status_text=f'Next search scheduled for {local_due.strftime("%d %b %Y at %H:%M")}'
        activity_state='scheduled'
        campaign_name=campaign.name; campaign_id=campaign.pk; campaign_created=campaign.created_at; campaign_started=None; campaign_due=due
    elif not ai_ready:
        activity_state='paused'; status_text='Identifying local accelerator…' if ai_identifying else 'AI unavailable — AI actions are paused.'
        campaign_name=''; campaign_id=None; campaign_created=None; campaign_started=None; campaign_due=None
    elif ps.background_paused:
        activity_state='paused'; status_text='Opportunity Search paused'
        campaign_name=''; campaign_id=None; campaign_created=None; campaign_started=None; campaign_due=None
    else:
        activity_state='idle'; status_text='No search currently scheduled.'
        campaign_name=''; campaign_id=None; campaign_created=None; campaign_started=None; campaign_due=None

    opportunity_notes=[{'kind':'opportunity','text':_pulse_text((f'{o.title} · {o.company}' if str(o.company or '').strip() else str(o.title or 'Opportunity')),110),'url':reverse('opportunity_detail',args=[o.pk]),'at':o.first_seen_by_portal} for o in Opportunity.objects.filter(suppressed=False,user_deleted=False,is_read=False).order_by('-first_seen_by_portal')[:6]]
    lead_notes=[{'kind':'lead','text':_pulse_text(f'{lead.company} · {_lead_popup_hint(lead)}',110),'url':f"{reverse('cold_contact')}?lead={lead.pk}",'at':lead.created_at} for lead in CompanyLead.objects.filter(user_deleted=False,is_read=False).order_by('-created_at')[:6]]
    for item in opportunity_notes+lead_notes: item['age_text']=_relative_popup_time(item.get('at'))
    content_notifications=(opportunity_notes+lead_notes)[:12]

    # Keep campaign state visible from the status popover without requiring Dashboard navigation.
    # Active and scheduled campaigns are reserved first, then the most recently edited rows fill
    # the five-item list.  Every row carries the timestamp that is relevant to its state.
    latest_campaigns=[]; seen_campaigns=set(); now=timezone.now()
    active_by_campaign={r.campaign_id:r for r in CampaignRun.objects.select_related('campaign').filter(status__in=['queued','running','stopping']).order_by('-created_at')[:20]}
    candidates=[]
    for r in active_by_campaign.values(): candidates.append(r.campaign)
    for c in Campaign.objects.filter(enabled=True,deleted_at__isnull=True).order_by('-updated_at')[:20]:
        if c.pk not in {x.pk for x in candidates}: candidates.append(c)
    for c in Campaign.objects.filter(deleted_at__isnull=True).order_by('-updated_at')[:30]:
        if c.pk not in {x.pk for x in candidates}: candidates.append(c)
    for c in candidates:
        if c.pk in seen_campaigns: continue
        seen_campaigns.add(c.pk); active=active_by_campaign.get(c.pk); due=None
        if active:
            state='Stopping' if active.status=='stopping' else ('Queued' if active.status=='queued' else 'Running')
            stamp=active.started_at or active.created_at
            prefix='Since' if state=='Running' else 'Updated'
        elif c.enabled:
            due=_campaign_next_run(c,ps,now)
            state='Scheduled' if due else 'Enabled'; stamp=due or c.updated_at; prefix='Next' if due else 'Updated'
        else:
            state='Paused'; stamp=c.updated_at; prefix='Updated'
        local=timezone.localtime(stamp) if stamp else None
        latest_campaigns.append({'id':c.pk,'name':c.name,'state':state,'state_class':state.lower(),'timestamp':(f'{prefix} {local.strftime("%d %b %Y %H:%M")}' if local else '')})
        if len(latest_campaigns)>=5: break

    alert_notifications=_recent_alert_notifications(ps,5)
    alert_heading=f'Last {len(alert_notifications)} alert{"" if len(alert_notifications)==1 else "s"}' if alert_notifications else ''
    notifications=(content_notifications+alert_notifications)[:7]
    provider_budget_warning=''
    try:
        _,selection=provider_selection_details(limit=4)
        exhausted=selection.get('budget_exhausted') or []
        selected=selection.get('selected') or []
        fallback_selected=selection.get('fallback_selected') or []
        if exhausted and not selected and selection.get('usable_count'):
            provider_budget_warning='Search paused — provider budgets exhausted. All enabled search providers have reached their ScoutBox daily limits; automatic Local AI Discovery resumes after the daily reset.'
        elif exhausted:
            provider_budget_warning=f"Search quota warning — {len(exhausted)} local provider{'s' if len(exhausted)!=1 else ''} fully used today." + (' ScoutBox is using available fallback providers.' if fallback_selected or selected else '')
    except Exception:
        provider_budget_warning=''
    # Daily Cloud quotas are visible in the same notification surface as local search quotas.
    try:
        cloud_state=cloud_limit_status()
        if cloud_state and not cloud_state.get('ok',True):
            cloud_message=str(cloud_state.get('message') or 'Cloud discovery quota has been fully used for today.')
            provider_budget_warning=(provider_budget_warning+' ' if provider_budget_warning else '')+'Cloud quota reached — '+cloud_message
    except Exception:
        pass
    # Per-run Cloud search/research caps are quota surfaces too. If any run today has
    # fully consumed one, keep that visible in Notifications even when the larger daily
    # allowance still has room.
    try:
        run_limits=[
            ('Cloud AI requests / run','requests',int(ps.cloud_requests_per_run or 0)),
            ('AI Web Search Queries / run','web_searches',int(ps.cloud_web_searches_per_run or 0)),
            ('Discovery candidates / run','discovery_candidates',int(ps.cloud_discovery_candidates_per_run or 0)),
            ('Deep-research candidates / run','deep_research_candidates',int(ps.cloud_deep_research_candidates_per_run or 0)),
        ]
        saturated=None
        recent_usage=CloudRunUsage.objects.select_related('campaign_run__campaign').filter(updated_at__date=timezone.localdate()).order_by('-updated_at')[:30]
        for ru in recent_usage:
            for label,field,limit in run_limits:
                used=int(getattr(ru,field,0) or 0)
                if limit>0 and used>=limit:
                    saturated=(label,used,limit,getattr(getattr(ru,'campaign_run',None),'campaign',None))
                    break
            if saturated:
                break
        if saturated:
            label,used,limit,campaign_obj=saturated
            cname=(getattr(campaign_obj,'name','') or 'campaign')[:120]
            message=f'Cloud run quota reached — {label}: {used} / {limit} on {cname}.'
            if message not in provider_budget_warning:
                provider_budget_warning=(provider_budget_warning+' ' if provider_budget_warning else '')+message
    except Exception:
        pass
    except Exception:
        pass
    return {
        'unread_opportunities':unread_opportunities,
        'unread_market':unread_market,
        'unread_hidden_leads':unread_market,
        'unread_applications':unread_applications,
        'unread_contacts':unread_contacts,
        'unread_facebook_pages':unread_facebook_pages,
        'unread_total':unread_opportunities+unread_market,
        'recent_opportunities':opportunity_notes,
        'recent_leads':lead_notes,
        'new_errors':new_errors,
        'new_warnings':new_warnings,
        'alert_count':new_errors+new_warnings,
        'search_active':activity_state=='active',
        'activity_state':activity_state,
        'status_text':status_text,
        'status_since':ps.background_state_changed_at,
        'campaign_name':campaign_name,
        'campaign_id':campaign_id,
        'campaign_created':campaign_created,
        'campaign_started':campaign_started,
        'campaign_due':campaign_due,
        'content_notifications':content_notifications[:10],
        'latest_campaigns':latest_campaigns,
        'alert_heading':alert_heading,
        'alert_notifications':alert_notifications[:5],
        'error_heading':alert_heading,
        'error_notifications':alert_notifications[:5],
        'notifications':notifications,
        'provider_budget_warning':provider_budget_warning,
    }


def _error_signature(category='', provider='', stage='', detail=''):
    detail=re.sub(r'\s+',' ',str(detail or '')).strip().lower()
    # Normalize volatile IDs/numbers so one repeated provider/dependency failure is
    # represented as one diagnostic incident rather than hundreds of request errors.
    detail=re.sub(r'\b[0-9a-f]{12,}\b','<id>',detail)
    detail=re.sub(r'\b\d{4,}\b','<n>',detail)
    return (str(category or '').lower(),str(provider or '').lower(),str(stage or '').lower(),detail[:500] or 'error')


def _dashboard_stats():
    today=timezone.localdate()
    return {
        'campaigns':Campaign.objects.filter(deleted_at__isnull=True).count(),
        'new_opportunities':Opportunity.objects.filter(suppressed=False,user_deleted=False,is_read=False).count(),
        'new_market':CompanyLead.objects.filter(user_deleted=False,is_read=False).count(),
        'new_contacts':Contact.objects.filter(deleted_at__isnull=True,is_read=False).filter(Q(generic=False)|Q(source__iexact='manual')).count(),
        'facebook_pages':FacebookPage.objects.filter(deleted_at__isnull=True).count(),
        'applications':Application.objects.filter(deleted_at__isnull=True,opportunity__user_deleted=False).count(),
        'replies':MailEvent.objects.filter(kind='inbox',occurred_at__date=today).count(),
        'tracking_links':TrackingLink.objects.filter(deleted_at__isnull=True).count(),
        'errors':_new_error_count(),
    }


def _capture_resource_sample(force=False, allow_stale_fallback=True):
    """Persist a coherent resource sample through the continuity-aware collector."""
    latest=ResourceSample.objects.order_by('-at').first()
    if latest and not force and latest.at >= timezone.now()-timedelta(seconds=12):
        return latest
    try:
        return capture_resource_sample()
    except Exception:
        return latest if allow_stale_fallback else None


def _system_snapshot(sample=None):
    sample=sample or _capture_resource_sample() or ResourceSample()
    totals=host_resource_totals()
    platform_label=str(totals.get('platform') or f'{platform.system()} {platform.machine()}'.strip())
    os_label=str(totals.get('os_label') or totals.get('platform') or f'{platform.system()} {platform.release()}'.strip())
    is_macos=('macos' in os_label.lower() or 'darwin' in platform_label.lower())
    return {
        'hostname':platform.node() or 'runtime',
        'platform':platform_label,
        'os_label':os_label,
        'is_macos':is_macos,
        'storage_label':str(totals.get('storage_label') or 'disk'),
        'cpu_count':int(totals.get('cpu_count') or os.cpu_count() or 0),
        'cpu_percent':round(float(getattr(sample,'cpu_percent',0) or 0),1),
        'memory_percent':round(float(getattr(sample,'memory_percent',0) or totals.get('memory_percent',0) or 0),1),
        'memory_used_mb':int(getattr(sample,'memory_used_mb',0) or totals.get('memory_used_mb',0) or 0),
        'memory_total_mb':int(getattr(sample,'memory_total_mb',0) or totals.get('memory_total_mb',0) or 0),
        'disk_used_mb':int(getattr(sample,'disk_used_mb',0) or totals.get('disk_used_mb',0) or 0),
        'disk_total_mb':int(getattr(sample,'disk_total_mb',0) or totals.get('disk_total_mb',0) or 0),
        'disk_free_mb':int(totals.get('disk_free_mb',0) or 0),
        'gpu_percent':getattr(sample,'gpu_percent',None),
        'gpu_memory_percent':getattr(sample,'gpu_memory_percent',None),
        'gpu_label':getattr(sample,'gpu_label','') or '',
        'gpu_vram_used_mb':getattr(sample,'gpu_vram_used_mb',None),
        'gpu_vram_total_mb':getattr(sample,'gpu_vram_total_mb',None),
    }


def _recent_errors(limit=20, seen_at=None):
    """Group recent incidents by component while preserving distinct messages.

    The Dashboard needs an operational signal, not a firehose of identical provider
    failures. Raw UsageMetric/BackgroundJob rows remain intact for deeper telemetry.
    """
    since=timezone.now()-timedelta(hours=24)
    groups={}

    def add(source, message, at, count=1, severity='error'):
        source=' '.join(str(source or 'ScoutBox').split()).strip() or 'ScoutBox'
        message=' '.join(str(message or 'Request failed').split()).strip() or 'Request failed'
        at=at or timezone.now()
        try: count=max(1,int(count or 1))
        except Exception: count=1
        key=source.casefold()
        group=groups.setdefault(key,{'source':source,'at':at,'count':0,'severity':severity,'_messages':{}})
        group['count']+=count
        if at > group['at']:
            group['at']=at
        if severity=='error': group['severity']='error'
        sig=_error_signature('recent',source,'group',message)
        item=group['_messages'].get(sig)
        if item:
            item['count']+=count
            if at > item['at']: item['at']=at
        else:
            group['_messages'][sig]={'message':message,'count':count,'at':at}

    today_stats=list(SearchProviderStat.objects.filter(day=timezone.localdate()).select_related('source'))
    total_requests=sum(int(x.requests or 0) for x in today_stats)
    total_errors=sum(int(x.errors or 0) for x in today_stats)
    elevated=bool(total_requests >= 5 and (total_errors >= 5 or total_errors/max(1,total_requests) >= .30))
    if elevated:
        add('Search providers',f'Elevated search engine errors: {total_errors} failed requests across {total_requests} requests. Check Configuration > Search Sources.',timezone.now(),max(1,total_errors),'warning')
    stalled=[x for x in today_stats if int(x.requests or 0) >= 5 and int(x.results or 0) == 0 and int(x.errors or 0) == 0]
    if stalled:
        names=', '.join(x.source.name for x in stalled[:5])
        add('Search providers',f'No-result search providers detected: {names}. Requests are succeeding but returning no pages; check provider configuration and query settings.',timezone.now(),1,'warning')

    for metric in UsageMetric.objects.filter(at__gte=since,errors__gt=0).exclude(category='lab').exclude(stage='provider_test').order_by('-at')[:1000]:
        meta=metric.metadata or {}
        detail=str(meta.get('error') or meta.get('message') or '').strip()
        source=str(metric.provider or metric.stage or metric.category or 'ScoutBox')
        count=max(1,int(metric.errors or 1))
        message=detail or f'{count} failed request{"s" if count!=1 else ""}'
        add(source,message,metric.at,count,'error')

    for job in BackgroundJob.objects.filter(status='failed',finished_at__gte=since).order_by('-finished_at','-created_at')[:300]:
        detail=job.error or job.message or 'Background task failed'
        add(job.get_kind_display(),detail,job.finished_at or job.created_at,1,'error')

    rows=[]
    for group in groups.values():
        messages_sorted=sorted(group.pop('_messages').values(),key=lambda x:x['at'] or timezone.now(),reverse=True)
        group['messages']=messages_sorted[:5]
        group['message']=messages_sorted[0]['message'] if messages_sorted else ''
        group['is_new']=bool(group.get('at') and group['at'] >= since)
        rows.append(group)
    rows.sort(key=lambda x:x['at'] or timezone.now(),reverse=True)
    return rows[:limit]


def _pulse_text(text, limit=150):
    text=re.sub(r'\s+',' ',str(text or '')).strip()
    return text if len(text)<=limit else text[:limit-1].rstrip()+'…'


def _dashboard_activity_pulse(limit=12):
    """Return only genuinely current work; otherwise describe the next scheduled run.

    Historical UsageMetric rows are deliberately not allowed to masquerade as current
    activity.  A short telemetry grace window covers requests that do not have a
    BackgroundJob/CampaignRun row, while chatbot telemetry is excluded because the
    chat panel has its own in-flight indicator.
    """
    items=[]
    now=timezone.now()
    active_runs=list(CampaignRun.objects.select_related('campaign').filter(status__in=['queued','running','stopping']).order_by('-created_at')[:4])
    # Running Hidden Market tasks are no longer mutated by a dashboard request. The scan
    # itself has a time budget and progress heartbeat, avoiding the old race where viewing
    # Dashboard could mark a still-running worker task as failed after 75 minutes.
    active_jobs=list(BackgroundJob.objects.filter(status__in=['queued','running']).order_by('-created_at')[:5])
    for run in active_runs:
        detail=_pulse_text(run.message or run.get_status_display())
        started=timezone.localtime(run.started_at or run.created_at).strftime('%d/%m/%Y %H:%M:%S')
        text=(f'{detail} · {run.campaign.name}' if detail.lower().startswith('searching ') else f'{run.campaign.name}: {detail}') + f' (started on {started})'
        items.append({'text':text,'kind':'campaign','at':run.started_at or run.created_at})
    for job in active_jobs:
        detail=_pulse_text(job.message or job.get_status_display())
        items.append({'text':f'{job.label}: {detail}','kind':job.kind,'at':job.started_at or job.created_at})

    # Do not infer live work from completed UsageMetric rows. A CampaignRun or
    # BackgroundJob is the source of truth for activity; otherwise show the next due run.

    items.sort(key=lambda x:x.get('at') or now, reverse=True)
    clean=[]; seen=set()
    for item in items:
        key=item['text'].lower()
        if key in seen: continue
        seen.add(key)
        at=item.get('at') or now
        clean.append({'text':item['text'],'kind':item.get('kind','activity'),'at':timezone.localtime(at).strftime('%d/%m/%Y %H:%M:%S')})
        if len(clean)>=limit: break
    if clean:
        return clean

    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    readiness=ai_compute_readiness()
    if not readiness.get('ready'):
        text='Identifying local accelerator…' if readiness.get('identifying') else 'AI unavailable — AI actions are paused.'
        state_kind='paused'
    elif ps.background_paused:
        text='Opportunity search is paused.'
        state_kind='paused'
    else:
        scheduled=[]
        for campaign in Campaign.objects.filter(enabled=True,deleted_at__isnull=True).order_by('name'):
            due=_campaign_next_run(campaign,ps,now)
            if due: scheduled.append((due,campaign))
        scheduled.sort(key=lambda x:x[0])
        if scheduled:
            due,campaign=scheduled[0]
            if due <= now+timedelta(seconds=60):
                text=f'Next campaign ({campaign.name}) is due now'
            else:
                text=f'Next campaign ({campaign.name}) will start at {timezone.localtime(due).strftime("%d/%m/%Y %H:%M:%S")}'
            state_kind='scheduled'
        else:
            text='No campaign is currently running; no scheduled campaign is enabled.'
            state_kind='idle'
    return [{'text':text,'kind':state_kind,'at':timezone.localtime(now).strftime('%d/%m/%Y %H:%M:%S')}]


def _usage_region_context(metadata):
    meta=metadata if isinstance(metadata,dict) else {}
    setting=' '.join(str(meta.get('region_setting') or '').split())[:24]
    if not setting:
        return None
    market=_market_name_for_region_setting(setting,meta.get('market'))
    return {
        'setting':setting,
        'market':market,
        'market_code':' '.join(str(meta.get('market_code') or '').split())[:24],
        'title':f'Regional setting: {setting}'+(f' · Target market: {market}' if market else ''),
    }


def _market_name_for_region_setting(setting, fallback=''):
    """Resolve both language-country and country-language provider settings."""
    value='-'.join(str(setting or '').strip().replace('_','-').split('-')).casefold()
    if value:
        for market in MARKETS:
            aliases={str(market.locale or '').casefold(),str(market.ddg_region or '').casefold()}
            if value in aliases:
                return market.name
    return ' '.join(str(fallback or '').split())[:80]


def _dashboard_latest_search_region():
    cutoff=timezone.now()-timedelta(hours=24)
    try:
        rows=UsageMetric.objects.filter(stage='query',at__gte=cutoff).exclude(provider='').order_by('-at')[:200]
        for row in rows:
            region=_usage_region_context(row.metadata)
            if region:
                return {**region,'provider':' '.join(str(row.provider or '').split())[:120],
                        'at':timezone.localtime(row.at).strftime('%d/%m/%Y %H:%M:%S')}
    except Exception:
        pass
    return None


def _dashboard_recent_activity(limit=12):
    """Compact noisy automatic Address Book promotions for Dashboard only.

    The underlying AuditLog rows remain untouched for the full audit screen. With no
    explicit run id on legacy promotion records, a 15-minute window is the safest
    dashboard-only aggregation boundary. Detailed AuditLog rows remain separate.
    """
    raw=list(AuditLog.objects.all()[:max(240,int(limit or 12)*20)])
    groups={}; items=[]
    for row in raw:
        if row.action!='addressbook_promotion':
            items.append(SimpleNamespace(at=row.at,action=row.action,summary=row.summary))
            continue
        meta=row.metadata if isinstance(row.metadata,dict) else {}
        source=' '.join(str(meta.get('source') or '').split()).strip()[:120]
        try: bucket=int(row.at.timestamp()//900)
        except Exception: bucket=0
        key=bucket
        group=groups.get(key)
        if group is None:
            group={'at':row.at,'processed':0,'added':0,'updated':0,'skipped':0}
            groups[key]=group
        group['processed']+=1
        outcome=str(meta.get('outcome') or '').strip().casefold()
        if outcome=='created': group['added']+=1
        elif outcome=='updated': group['updated']+=1
        else: group['skipped']+=1
        if row.at>group['at']: group['at']=row.at
    for group in groups.values():
        summary=(f"{group['processed']} processed · {group['added']} added · "
                 f"{group['updated']} updated · {group['skipped']} skipped")
        items.append(SimpleNamespace(at=group['at'],action='Address Book promotion',summary=summary))
    items.sort(key=lambda x:x.at,reverse=True)
    return items[:max(1,int(limit or 12))]


@login_required
def dashboard_live_data(request):
    return JsonResponse({
        'stats':_dashboard_stats(),
        'pulse':_dashboard_activity_pulse(),
        'running':_running_activity_rows(),
        'recent_activity':[{'at':timezone.localtime(x.at).strftime('%d/%m/%Y %H:%M:%S'),'action':x.action,'summary':_pulse_text(x.summary,150)} for x in _dashboard_recent_activity(12)],
        'updated_at':timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M:%S'),
        'system':_system_snapshot(),
    })


@login_required
def activity_status(request):
    return JsonResponse({'items':_running_activity_rows()})


def _activity_buckets(range_name):
    now=timezone.localtime(timezone.now())
    aliases={'today':'24h','week':'7d','month':'30d'}
    range_name=aliases.get((range_name or '24h').strip().lower(),(range_name or '24h').strip().lower())
    buckets=[]
    rolling_specs={
        '1h':(12,timedelta(minutes=5),'%H:%M'),
        '3h':(12,timedelta(minutes=15),'%H:%M'),
        '6h':(12,timedelta(minutes=30),'%H:%M'),
        '12h':(12,timedelta(hours=1),'%H:%M'),
        '24h':(24,timedelta(hours=1),'%H:%M'),
        '3d':(12,timedelta(hours=6),'%d %b %H:%M'),
    }
    if range_name in rolling_specs:
        count,step,label_fmt=rolling_specs[range_name]
        start=now-(step*count)
        for i in range(count):
            a=start+(step*i); b=min(a+step,now)
            buckets.append((a,b,a.strftime(label_fmt)))
    elif range_name in {'7d','14d'}:
        days=7 if range_name=='7d' else 14
        start=(now-timedelta(days=days-1)).replace(hour=0,minute=0,second=0,microsecond=0)
        for i in range(days):
            a=start+timedelta(days=i); buckets.append((a,a+timedelta(days=1),a.strftime('%a %d' if days==7 else '%d/%m')))
    elif range_name=='all':
        candidates=[]
        for model,field in ((UsageMetric,'at'),(Opportunity,'first_seen_by_portal'),(CompanyLead,'created_at'),(Contact,'created_at')):
            try:
                value=model.objects.aggregate(v=Min(field)).get('v')
                if value: candidates.append(timezone.localtime(value))
            except Exception:
                pass
        earliest=min(candidates) if candidates else now
        a=earliest.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
        while a<=now:
            b=a.replace(year=a.year+1,month=1) if a.month==12 else a.replace(month=a.month+1)
            buckets.append((a,b,a.strftime('%b %y')))
            a=b
    else:
        start=(now-timedelta(days=29)).replace(hour=0,minute=0,second=0,microsecond=0)
        for i in range(30):
            a=start+timedelta(days=i); buckets.append((a,a+timedelta(days=1),a.strftime('%d/%m')))
    return buckets


def _dashboard_activity_payload(range_name):
    out=[]
    for a,b,label in _activity_buckets(range_name):
        um=UsageMetric.objects.filter(at__gte=a,at__lt=b).exclude(category='lab')
        sums=um.aggregate(requests=Sum('requests'),tokens_in=Sum('tokens_in'),tokens_out=Sum('tokens_out'),errors=Sum('errors'))
        search_sums=um.filter(Q(stage='query') | Q(category='fresh_source')).aggregate(v=Sum('requests'))
        out.append({
            'label':label, 'at_iso':a.isoformat(), 'searches':search_sums['v'] or 0,
            'opportunities':Opportunity.objects.filter(first_seen_by_portal__gte=a,first_seen_by_portal__lt=b,suppressed=False,user_deleted=False).count(),
            'leads':CompanyLead.objects.filter(created_at__gte=a,created_at__lt=b,user_deleted=False).count(),
            'contacts':Contact.objects.filter(created_at__gte=a,created_at__lt=b,deleted_at__isnull=True).count(),
            'tokens':(sums['tokens_in'] or 0)+(sums['tokens_out'] or 0), 'errors':sums['errors'] or 0,
        })
    return out



def _safe_setting_attr(obj, name, default=None):
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

def _campaign_next_run(campaign, portal_settings=None, now=None):
    """Estimate the next scheduler launch using the scheduler's real gating rules.

    In Cloud Web mode this includes the per-campaign Cloud interval, daily automatic-run
    limit, recent provider-rate-limit cooldown and the current coverage window. Returning
    a past window boundary made Dashboard claim a campaign would start at e.g. 10:00 even
    after 11:00; clamp genuinely-due work to now instead.
    """
    if not campaign or not campaign.enabled:
        return None
    if not DocumentAsset.objects.filter(kind='cv',active=True).exists():
        return None
    ps=portal_settings or PortalSettings.objects.get_or_create(pk=1)[0]
    now=now or timezone.now()
    def _is_forum_only(run):
        criteria=run.criteria if isinstance(run.criteria,dict) else {}
        return bool(criteria.get('forum_only') or criteria.get('run_kind')=='forum_only')
    def _is_deferred_local(run):
        criteria=run.criteria if isinstance(run.criteria,dict) else {}
        return bool(criteria.get('deferred_local_ai'))
    window_minutes=_safe_setting_int(ps,'scraper_interval_minutes',120,minimum=30); window_seconds=window_minutes*60
    if str(_safe_setting_attr(ps,'discovery_mode','source_guided') or '').strip().lower()=='cloud_web':
        effective_minutes=max(window_minutes,_safe_setting_int(ps,'cloud_min_interval_minutes',window_minutes,minimum=15))
        cloud_rows=list(CampaignRun.objects.filter(campaign=campaign).order_by('-created_at')[:100])
        latest=next((r for r in cloud_rows if not _is_forum_only(r)),None)
        due=(latest.created_at+timedelta(minutes=effective_minutes)) if latest else now
        today_start=timezone.make_aware(datetime.combine(timezone.localdate(),datetime.min.time()),timezone.get_current_timezone())
        auto_limit=_safe_setting_int(ps,'cloud_auto_runs_per_campaign_day',5,minimum=1)
        auto_used=sum(1 for r in CampaignRun.objects.filter(campaign=campaign,created_at__gte=today_start,criteria__automatic=True) if not _is_forum_only(r))
        if auto_used>=auto_limit:
            tomorrow=timezone.localdate()+timedelta(days=1)
            due=max(due,timezone.make_aware(datetime.combine(tomorrow,datetime.min.time()),timezone.get_current_timezone()))
        cooldown=cloud_rate_limit_cooldown(now,seconds=300)
        if cooldown and cooldown.get('until'):
            due=max(due,cooldown['until'])
        return max(due,now)
    epoch=int(now.timestamp()); window_start_ts=(epoch//window_seconds)*window_seconds
    window_start=datetime.fromtimestamp(window_start_ts,tz=timezone.get_current_timezone())
    window_end=window_start+timedelta(seconds=window_seconds)
    target_attempts=max(2,min(8,math.ceil(window_minutes/15)))
    gap_seconds=max(8*60,int(window_seconds/target_attempts))
    all_primary=[r for r in CampaignRun.objects.filter(campaign=campaign,created_at__gte=window_start).order_by('created_at')
                 if not _is_forum_only(r)]
    runs=[r for r in all_primary if not _is_deferred_local(r)]

    if len(runs)>=target_attempts:
        due=window_end
    elif all_primary:
        recent=runs[-2:]
        severe=0
        for r in recent:
            result=r.result or {}; errs=result.get('errors') or []; providers=result.get('providers') or []
            if r.status=='failed' or (providers and len(errs)>=len(providers)*2 and not result.get('raw_hits')):
                severe+=1
        due=window_end if severe>=2 else all_primary[-1].created_at+timedelta(seconds=gap_seconds)
    elif campaign.last_run and campaign.last_run>=window_start:
        due=campaign.last_run+timedelta(seconds=gap_seconds)
    else:
        due=window_start

    return max(due,now)


@login_required
def dashboard_activity_data(request):
    range_name=(request.GET.get('range') or '24h').strip().lower()
    aliases={'today':'24h','week':'7d','month':'30d'}
    range_name=aliases.get(range_name,range_name)
    if range_name not in ('1h','3h','6h','12h','24h','3d','7d','30d','year'): range_name='24h'
    return JsonResponse({'range':range_name,'series':_dashboard_activity_payload(range_name),'updated_at':timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M:%S')})


@login_required
def dashboard(request):
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    if request.method=='POST' and request.POST.get('action')=='refresh_diagnostics':
        active=BackgroundJob.objects.filter(kind='diagnostic',label='System diagnostics',status__in=['queued','running']).first()
        if not active:
            job=BackgroundJob.objects.create(kind='diagnostic',label='System diagnostics',message='Queued')
            task=system_diagnostics_job.delay(job.pk); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
            messages.success(request,'Diagnostics refresh queued.')
        return redirect(reverse('dashboard')+'#diagnostics')
    stats=_dashboard_stats()
    recent_runs=_daily_campaign_run_rows(CampaignRun.objects.select_related('campaign').exclude(status__in=['queued','running','stopping']).order_by('-created_at')[:1000])[:200]
    readiness=_readiness_items()
    chart=_dashboard_activity_payload('24h')
    _capture_resource_sample()
    resources=list(ResourceSample.objects.order_by('-at')[:60]); resources.reverse()
    diagnostic_job=BackgroundJob.objects.filter(kind='diagnostic',label='System diagnostics').order_by('-created_at').first()
    health=(diagnostic_job.result or {}).get('diagnostics',[]) if diagnostic_job and diagnostic_job.status=='completed' else []
    if not health and not (diagnostic_job and diagnostic_job.status in ('queued','running')):
        try:
            health=run_system_diagnostics() or []
            now_diag=timezone.now()
            diagnostic_job=BackgroundJob.objects.create(kind='diagnostic',label='System diagnostics',status='completed',progress=100,message='Diagnostics refreshed on Dashboard',started_at=now_diag,finished_at=now_diag,result={'diagnostics':health})
        except Exception as exc:
            health=[('Diagnostics','WARN',f'Live diagnostic check failed: {exc}')]
    # Scheduler health is persisted by the scheduler itself so a long overnight gap is
    # still visible after the process resumes.  Do not let a healthy HTTP/AI diagnostic
    # mask a silent scheduler/worker stack.
    scheduler_health=dict(getattr(ps,'scheduler_health',{}) or {})
    scheduler_gap=int(scheduler_health.get('last_gap_seconds') or 0)
    longest_gap=int(scheduler_health.get('longest_gap_seconds') or 0)
    stale_seconds=int((timezone.now()-ps.last_scheduler_tick).total_seconds()) if ps.last_scheduler_tick else None
    if not ps.background_paused and stale_seconds is not None and stale_seconds>=180:
        health=list(health)+[('Scheduler','WARN',f'No scheduler tick for {stale_seconds//60} minute(s). Last tick: {timezone.localtime(ps.last_scheduler_tick).strftime("%d/%m/%Y %H:%M:%S")}')]
    elif scheduler_gap>=300:
        health=list(health)+[('Scheduler','WARN',f'Recovered after a {scheduler_gap//60}-minute scheduler gap. Longest recorded gap: {max(scheduler_gap,longest_gap)//60} minutes.')]
    elif ps.last_scheduler_tick:
        workers=len(scheduler_health.get('workers') or [])
        health=list(health)+[('Scheduler','OK',f'Last tick {timezone.localtime(ps.last_scheduler_tick).strftime("%d/%m/%Y %H:%M:%S")} · {workers} responding worker(s) in last scheduler inspection.')]
    provider_health=[_search_provider_health(x) for x in SearchSource.objects.filter(name__in=ACTIVE_PROVIDER_NAMES).order_by('name')]
    search_health_summary={k:sum(1 for x in provider_health if x.get('health_state')==k) for k in ('ok','idle','warn','stalled','error')}
    # Surface hard quota stops directly beside the Dashboard Search window so a
    # stalled scheduler is immediately explainable and one click opens the setting.
    dashboard_quota_warnings=[]
    try:
        exhausted=[]
        for source in SearchSource.objects.filter(enabled=True,name__in=ACTIVE_PROVIDER_NAMES).order_by('name'):
            budget=provider_budget(source)
            remaining=provider_budget_remaining(source)
            if budget>0 and remaining<=0:
                exhausted.append(f'{source.name} ({budget}/{budget})')
        if exhausted:
            dashboard_quota_warnings.append({
                'label':f'Search quota reached ({len(exhausted)})',
                'title':'ScoutBox daily search-provider quota reached: '+', '.join(exhausted),
                'url':reverse('sources')+'#source-schedule',
                'kind':'search',
            })
    except Exception:
        pass
    try:
        usage=cloud_today_usage(); limits=usage.get('limits') or {}
        cloud_checks=[
            ('Cloud AI requests','requests','daily_requests'),
            ('AI Web Search Queries','web_searches','daily_web_searches'),
            ('Cloud input tokens','tokens_in','daily_input_tokens'),
            ('Cloud output + reasoning tokens','tokens_out_reasoning','daily_output_tokens'),
            ('Passive enrichment','passive_enrichment','passive_enrichment'),
            ('Page-view recovery','page_recovery','page_recovery'),
        ]
        for label,key,lkey in cloud_checks:
            used=int(usage.get(key) or 0); limit=int(limits.get(lkey) or 0)
            if limit>0 and used>=limit:
                dashboard_quota_warnings.append({
                    'label':f'{label} reached ({used}/{limit})',
                    'title':f'{label} quota has been reached. Open Cloud AI Limits to review or change it.',
                    'url':reverse('sources')+'#cloud-ai-limits',
                    'kind':'cloud',
                })
    except Exception:
        pass
    scheduled=[]
    if ai_compute_readiness().get('ready'):
        for campaign in Campaign.objects.filter(enabled=True,deleted_at__isnull=True).order_by('name'):
            due=_campaign_next_run(campaign,ps)
            if due: scheduled.append((due,campaign))
    scheduled.sort(key=lambda x:x[0])
    next_scheduled_campaign=scheduled[0] if scheduled else None
    recent_errors=_recent_errors(seen_at=ps.error_notifications_seen_at)
    latest_activity_error=recent_errors[0] if recent_errors else None
    ai_output_warnings=_ai_empty_output_warning_notifications(1)
    ai_output_warning=ai_output_warnings[0] if ai_output_warnings else None
    return render(request,'portal/dashboard.html',ctx(request,'dashboard','Dashboard',stats=stats,events=_dashboard_recent_activity(12),health=health,diagnostic_job=diagnostic_job,running=_running_activity_rows(),pulse=_dashboard_activity_pulse(),recent_runs=recent_runs,readiness=readiness,chart_data=chart,chart_json=json.dumps(chart),resource_data=[{'at':timezone.localtime(x.at).strftime('%H:%M:%S'),'cpu':x.cpu_percent,'memory':x.memory_percent,'gpu':x.gpu_percent} for x in resources],system_info=_system_snapshot(),recent_errors=recent_errors,latest_activity_error=latest_activity_error,search_health_summary=search_health_summary,next_scheduled_campaign=next_scheduled_campaign,dashboard_quota_warnings=dashboard_quota_warnings,ai_output_warning=ai_output_warning,latest_search_region=_dashboard_latest_search_region()))



def _clean_profile_tokens(values, lower=True, limit=60):
    out=[]; seen=set()
    for raw in values:
        value=' '.join(str(raw or '').strip().split())
        if lower: value=value.lower()
        key=value.lower()
        if value and key not in seen:
            seen.add(key); out.append(value)
        if len(out)>=limit: break
    return out


DEFAULT_CAMPAIGN_TEMPLATE_PROMPT = (
    'Create one focused campaign template for each likely role. Use only technologies and '
    'specialist concepts evidenced by my configured Candidate Profile or active Resumes that '
    'are directly relevant to that role. Keep the role templates distinct; do not copy the same '
    'technology list into every template.'
)


def _campaign_role_tokens(text):
    return {x for x in re.findall(r'[a-z0-9+#]+',str(text or '').lower()) if len(x)>2 and x not in {'engineer','engineering','specialist','software','technical'}}


def _role_specific_campaign_terms(role, search_profile, limit=6):
    """Choose role-specific terms strictly from the configured profile/CV evidence.

    The previous generator copied the same top-N profile terms into every template.  Here
    CV/profile evidence remains the admission criterion, while known role families and CV
    labels only *rank* that evidence for the current role.
    """
    rows=[dict(x) for x in (search_profile.get('skills') or []) if str(x.get('term') or '').strip()]
    if not rows:
        return []
    role_low=' '.join(str(role or '').lower().split())
    role_tokens=_campaign_role_tokens(role_low)

    # Find the closest built-in role family, if any.  Custom roles are still supported by
    # the generic token/category scoring below.
    best_role=''; best_score=0.0
    for known in ROLE_FAMILIES:
        kt=_campaign_role_tokens(known)
        if role_low==known:
            best_role=known; best_score=999; break
        overlap=len(role_tokens & kt)
        score=(2*overlap/max(1,len(role_tokens|kt))) if overlap else 0
        if known in role_low or role_low in known: score+=1.5
        if score>best_score: best_role,best_score=known,score
    triggers=list(ROLE_FAMILIES.get(best_role,[])) if best_score>=0.45 else []
    trigger_lows={x.lower() for x in triggers}
    target_categories={SKILL_GRAPH[x].get('category') for x in triggers if x in SKILL_GRAPH}

    # Infer useful categories from custom role wording without inventing skills.
    category_hints={
        'embedded':{'embedded','embedded-niche','systems'}, 'firmware':{'embedded','embedded-niche','systems'},
        'driver':{'systems','embedded'}, 'kernel':{'systems'}, 'reverse':{'reverse','protocol-niche'},
        'security':{'security','reverse'}, 'emulation':{'retro','retro-niche','virtualization'},
        'emulator':{'retro','retro-niche','virtualization'}, 'virtualization':{'virtualization','systems'},
        'legacy':{'retro','retro-niche'}, 'retro':{'retro','retro-niche'}, 'systems':{'systems','virtualization'},
        'writer':{'writing'}, 'writing':{'writing'}, 'trainer':{'writing'}, 'training':{'writing'},
        'documentation':{'writing'}, 'protocol':{'reverse','protocol-niche','systems'},
    }
    for token,cats in category_hints.items():
        if token in role_low: target_categories.update(cats)

    cv_focus_terms={}
    for cv in search_profile.get('cv_focus') or []:
        label=str(cv.get('label') or '').lower(); label_match=bool(role_tokens & _campaign_role_tokens(label))
        for item in cv.get('terms') or []:
            term=str(item.get('term') or '').lower()
            if term: cv_focus_terms[term]=max(cv_focus_terms.get(term,0),20 if label_match else 7)

    ranked=[]
    for row in rows:
        term=str(row.get('term') or '').strip(); low=term.lower(); cat=str(row.get('category') or '')
        score=float(row.get('score') or 0)
        sources=row.get('sources') or {}
        if sources.get('cv'): score+=10
        if sources.get('profile_override'): score+=9
        if sources.get('high_preference'): score+=7
        elif sources.get('medium_preference'): score+=3
        if low in trigger_lows: score+=90
        if cat in target_categories: score+=28
        term_tokens=_campaign_role_tokens(term+' '+' '.join(row.get('aliases') or []))
        score+=18*len(role_tokens & term_tokens)
        score+=cv_focus_terms.get(low,0)
        ranked.append((score,term,cat,low in trigger_lows or cat in target_categories or bool(role_tokens & term_tokens)))

    ranked.sort(key=lambda x:(-x[0],x[1].lower()))
    relevant=[x for x in ranked if x[3]]
    pool=relevant if relevant else ranked
    selected=[]; seen=set()
    for _score,term,_cat,_relevant in pool:
        key=term.lower()
        if key in seen: continue
        seen.add(key); selected.append(term)
        if len(selected)>=limit: break
    # Keep custom/weakly matched roles useful, but never flood them with the old global list.
    if len(selected)<3:
        for _score,term,_cat,_relevant in ranked:
            key=term.lower()
            if key in seen: continue
            seen.add(key); selected.append(term)
            if len(selected)>=min(limit,4): break
    return selected



def _campaign_role_term_map(roles, search_profile, prompt=''):
    """Build distinct role-specific keyword sets from Candidate Profile + active Resume evidence.

    The allowed vocabulary is always the evidence-backed ``build_search_profile`` skill list.
    AI, when configured, may rank those exact terms but cannot introduce new technologies.
    A deterministic usage penalty then prevents the old failure mode where every role got the
    same global six terms.
    """
    roles=[str(r or '').strip() for r in roles if str(r or '').strip()]
    available=[str(x.get('term') or '').strip() for x in (search_profile.get('skills') or []) if str(x.get('term') or '').strip()]
    allowed={x.lower():x for x in available}
    ai_map={}
    if roles and allowed:
        try:
            ai_prompt=(
                "Select role-specific search technologies/skills from the ALLOWED TERMS only. "
                "Return JSON only: an object whose keys exactly match the supplied roles and whose values are arrays of 3-6 exact allowed terms. "
                "Use Candidate Profile and active Resume evidence implicitly represented by the allowed list. "
                "Keep roles genuinely distinct: do not copy a global technology list into every role; only repeat a term when it is strongly relevant to both roles. "
                "Technical writer/trainer roles should prefer writing/documentation/education evidence rather than emulator/firmware terms unless the role genuinely combines them. "
                f"User generation guidance: {prompt or DEFAULT_CAMPAIGN_TEMPLATE_PROMPT}\n"
                f"ROLES: {json.dumps(roles)}\nALLOWED TERMS: {json.dumps(available)}"
            )
            raw=generate(ai_prompt,stage='first_filter',timeout=90).strip()
            raw=re.sub(r'^```(?:json)?\\s*|\\s*```$','',raw,flags=re.I|re.S).strip()
            parsed=json.loads(raw)
            if isinstance(parsed,dict):
                for role in roles:
                    vals=parsed.get(role) or []
                    clean=[]
                    for v in vals if isinstance(vals,list) else []:
                        canonical=allowed.get(str(v or '').strip().lower())
                        if canonical and canonical.lower() not in {x.lower() for x in clean}: clean.append(canonical)
                    ai_map[role]=clean[:6]
        except Exception:
            ai_map={}

    usage=Counter()
    out={}
    for role in roles:
        direct=_role_specific_campaign_terms(role,search_profile,limit=12)
        candidates=[]
        for term in (ai_map.get(role) or []) + direct:
            canonical=allowed.get(str(term).lower())
            if canonical and canonical.lower() not in {x.lower() for x in candidates}: candidates.append(canonical)
        role_low=role.lower(); known_triggers=set()
        for known,triggers in ROLE_FAMILIES.items():
            if known==role_low or known in role_low or role_low in known:
                known_triggers={x.lower() for x in triggers}; break
        selected=[]
        # Direct role-family matches are allowed to repeat; everything else pays a global
        # usage penalty so adjacent roles naturally separate into different focus areas.
        scored=[]
        for idx,term in enumerate(candidates):
            base=100-idx*4
            if term.lower() in known_triggers: base+=55
            base-=usage[term.lower()]*30
            scored.append((base,term))
        scored.sort(key=lambda x:(-x[0],x[1].lower()))
        for _score,term in scored:
            if usage[term.lower()]>=2 and term.lower() not in known_triggers: continue
            selected.append(term); usage[term.lower()]+=1
            if len(selected)>=5: break
        if len(selected)<3:
            for term in direct:
                if term.lower() in {x.lower() for x in selected}: continue
                selected.append(term); usage[term.lower()]+=1
                if len(selected)>=3: break
        out[role]=selected[:6]
    return out


@login_required
def profile_view(request):
    p=Profile.objects.get_or_create(pk=1)[0]
    active=active_profile()
    if active and active.imap_email and p.application_email!=active.imap_email:
        p.application_email=active.imap_email; p.save(update_fields=['application_email','updated_at'])
    if not p.operating_locations:
        p.operating_locations=[p.operating_location] if p.operating_location else ['Singapore']
    if request.method=='POST':
        action=request.POST.get('action')
        if action=='save_profile':
            name=request.POST.get('display_name','').strip()
            locations=[]
            for value in request.POST.getlist('operating_locations'):
                if value in COUNTRIES and value not in locations:
                    locations.append(value)
                if len(locations)>=10:
                    break
            errors=[]
            if len(name)<2: errors.append('Name must contain at least 2 characters.')
            if name and (sum(1 for ch in name if ch.isalpha()) < 2 or any(not (ch.isalpha() or ch.isspace() or ch in ".'’‑-") for ch in name)): errors.append('Name must contain at least two letters and may use spaces, apostrophes, periods and hyphens.')
            if not locations: errors.append('Select at least one operating country/region.')
            portfolio=request.POST.get('portfolio_url','').strip()
            if portfolio and not re.match(r'^https?://',portfolio,re.I): errors.append('Portfolio / blog must be a complete http:// or https:// URL.')
            phone=(request.POST.get('phone_number') or '').strip()
            if phone:
                if len(phone)>32 or not re.fullmatch(r'[0-9+() .-]+',phone):
                    errors.append('Phone number may contain only digits, spaces, +, parentheses, periods and hyphens, up to 32 characters.')
                elif phone.count('+')>1 or ('+' in phone and not phone.startswith('+')):
                    errors.append('The + sign in a phone number may only appear once at the beginning.')
                else:
                    digits=re.sub(r'\D','',phone)
                    if not 7 <= len(digits) <= 20:
                        errors.append('Phone number must contain between 7 and 20 digits.')
            if errors:
                for e in errors: messages.error(request,e)
            else:
                p.display_name=name; p.operating_locations=locations; p.operating_location=locations[0]
                p.phone_number=phone
                p.portfolio_url=portfolio
                p.high_priority_text=request.POST.get('high_priority_text','').strip(); p.medium_priority_text=request.POST.get('medium_priority_text','').strip(); p.low_priority_text=request.POST.get('low_priority_text','').strip()
                if not active or not active.imap_email: p.application_email=request.POST.get('application_email','').strip()
                scope=dict(p.scope_json or {})
                scope['cv_concepts']=_clean_profile_tokens(request.POST.getlist('cv_concepts'),lower=True,limit=PROFILE_CONCEPT_LIMIT)
                scope['likely_roles']=_clean_profile_tokens(request.POST.getlist('likely_roles'),lower=True,limit=PROFILE_ROLE_LIMIT)
                langs=_clean_profile_tokens(request.POST.getlist('preferred_languages'),lower=False,limit=20)
                scope['preferred_languages']=[normalise_language(x) for x in langs if normalise_language(x)] or ['english']
                p.scope_json=scope
                p.save(); messages.success(request,'Profile and preferences saved.'); log('profile.update',request,p)
        elif action=='generate_campaign_templates':
            # Legacy non-JavaScript fallback: queue the same asynchronous worker rather than
            # blocking the profile request on AI generation.
            prompt=' '.join((request.POST.get('campaign_template_prompt') or DEFAULT_CAMPAIGN_TEMPLATE_PROMPT).split())[:1800]
            job=BackgroundJob.objects.create(kind='prepare',label='Generate campaign templates',message='Queued')
            task=campaign_templates_job.delay(job.pk,prompt); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
            messages.success(request,'Campaign template generation queued. You can continue using ScoutBox while it runs.')
        elif action=='upload':
            files=request.FILES.getlist('file'); kind=request.POST.get('kind','cv') if request.POST.get('kind') in ('cv','cover') else 'cv'; ok=0
            for f in files:
                if f.name.lower().endswith(('.docx','.pdf')):
                    DocumentAsset.objects.create(kind=kind,label=request.POST.get('label') or f.name,original_name=f.name,file=f,notes=request.POST.get('notes','')); ok+=1
            if ok: messages.success(request,f'{ok} {"Resume" if kind=="cv" else "Cover Letter"} file(s) uploaded.')
            else: messages.error(request,'Upload DOCX or PDF files.')
        elif action=='create_resume_campaign':
            a=get_object_or_404(DocumentAsset,pk=request.POST.get('asset_id'),kind='cv',active=True)
            concepts=_clean_profile_tokens(request.POST.getlist('resume_concepts'),lower=True,limit=PROFILE_CONCEPT_LIMIT)
            roles=_clean_profile_tokens(request.POST.getlist('resume_roles'),lower=True,limit=PROFILE_ROLE_LIMIT)
            prompt=' '.join((request.POST.get('resume_campaign_prompt') or '').split())[:1800]
            job=BackgroundJob.objects.create(kind='prepare',label=f'Generate Campaign Template from Resume #{a.pk}',message='Queued')
            task=resume_campaign_template_job.delay(job.pk,a.pk,concepts,roles,prompt); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
            messages.success(request,f'Campaign Template generation queued for {a.label}. Its linked generated template will be replaced if one already exists. Existing Campaigns will not be changed.')
        elif action=='auto_create_resume_templates':
            prompt=' '.join((request.POST.get('resume_campaign_prompt') or '').split())[:1800]
            job=BackgroundJob.objects.create(kind='prepare',label='Auto-create Campaign Templates from Resumes',message='Queued')
            task=all_resume_campaign_templates_job.delay(job.pk,prompt); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
            messages.success(request,'Campaign Template generation queued for all Resumes. Existing linked generated templates will be replaced; existing Campaigns will not be changed.')
        elif action=='delete_asset':
            a=get_object_or_404(DocumentAsset,pk=request.POST.get('asset_id'))
            label=a.label
            try: a.file.delete(save=False)
            except Exception: pass
            a.delete(); messages.success(request,f'Deleted {label}.')
        return redirect('profile')
    search_profile=build_search_profile()
    saved_scope=dict(p.scope_json or {})
    preferred=saved_scope.get('preferred_languages') or ['english']
    campaign_template_prompt=saved_scope.get('campaign_template_prompt') or DEFAULT_CAMPAIGN_TEMPLATE_PROMPT
    if 'cv_concepts' in saved_scope:
        profile_concepts=[str(x).strip() for x in (saved_scope.get('cv_concepts') or []) if str(x).strip()][:PROFILE_CONCEPT_LIMIT]
    else:
        profile_concepts=[x.get('term','') for x in search_profile.get('skills',[]) if (x.get('sources') or {}).get('cv')][:PROFILE_CONCEPT_LIMIT]
    if 'likely_roles' in saved_scope:
        profile_roles=[str(x).strip() for x in (saved_scope.get('likely_roles') or []) if str(x).strip()][:PROFILE_ROLE_LIMIT]
    else:
        profile_roles=[x.get('role','') for x in search_profile.get('role_families',[]) if str(x.get('source') or '').startswith('cv')][:PROFILE_ROLE_LIMIT]
    campaign_template_job=BackgroundJob.objects.filter(kind='prepare',label='Generate campaign templates',status__in=['queued','running']).order_by('-created_at').first()
    candidate_profile_autopopulate_job_row=BackgroundJob.objects.filter(label='Autopopulate Candidate Profile',status__in=['queued','running']).order_by('-created_at').first()
    return render(request,'portal/profile.html',ctx(request,'profile','Candidate Profile',profile=p,campaign_template_job=campaign_template_job,candidate_profile_autopopulate_job=candidate_profile_autopopulate_job_row,cvs=DocumentAsset.objects.filter(kind='cv',active=True),covers=DocumentAsset.objects.filter(kind='cover',active=True),active_mail=active,search_profile=search_profile,profile_concepts=profile_concepts,profile_roles=profile_roles,profile_concept_limit=PROFILE_CONCEPT_LIMIT,profile_role_limit=PROFILE_ROLE_LIMIT,preferred_languages=[str(x).title() for x in preferred],language_options=language_options(),campaign_template_prompt=campaign_template_prompt))


@login_required
@require_POST
def profile_defaults_async(request):
    active=BackgroundJob.objects.filter(status__in=['queued','running']).filter(
        Q(label='Candidate Profile defaults')|Q(label='Autopopulate Candidate Profile')|Q(label__endswith='Candidate Profile vocabulary refresh')
    ).order_by('-created_at').first()
    if active:
        return JsonResponse({'ok':True,'job_id':active.pk,'existing':True})
    job=BackgroundJob.objects.create(kind='prepare',label='Candidate Profile defaults',message='Queued')
    task=candidate_profile_defaults_job.delay(job.pk); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
    return JsonResponse({'ok':True,'job_id':job.pk,'existing':False})


@login_required
@require_POST
def profile_autopopulate_async(request):
    active=BackgroundJob.objects.filter(status__in=['queued','running']).filter(
        Q(label='Candidate Profile defaults')|Q(label='Autopopulate Candidate Profile')|Q(label__endswith='Candidate Profile vocabulary refresh')
    ).order_by('-created_at').first()
    if active:
        if active.label=='Autopopulate Candidate Profile':
            return JsonResponse({'ok':True,'job_id':active.pk,'existing':True})
        return JsonResponse({'ok':False,'job_id':active.pk,'error':'Another Candidate Profile rebuild is already running. Monitor or stop it from Dashboard before starting autopopulation.'},status=409)
    resume_count=DocumentAsset.objects.filter(kind='cv',active=True).count()
    if resume_count<1:
        return JsonResponse({'ok':False,'error':'Upload at least one Resume before autopopulating Candidate Profile.'},status=400)
    result={'tool':'candidate_profile_autopopulate','phase':'queued','total_resumes':resume_count,'concept_limit':PROFILE_CONCEPT_LIMIT,'role_limit':PROFILE_ROLE_LIMIT}
    job=BackgroundJob.objects.create(kind='other',label='Autopopulate Candidate Profile',message=f'Queued — {resume_count} Resume{"" if resume_count==1 else "s"}',result=result)
    task=candidate_profile_autopopulate_job.delay(job.pk)
    job.celery_task_id=task.id or ''
    job.save(update_fields=['celery_task_id'])
    try:
        log('profile.autopopulate',request,job,summary=f'Queued Candidate Profile autopopulation from {resume_count} Resume{"" if resume_count==1 else "s"}')
    except Exception:
        pass
    return JsonResponse({'ok':True,'job_id':job.pk,'existing':False,'resume_count':resume_count})


@login_required
@require_POST
def profile_campaign_templates_async(request):
    active=BackgroundJob.objects.filter(kind='prepare',label='Generate campaign templates',status__in=['queued','running']).order_by('-created_at').first()
    if active:
        return JsonResponse({'ok':True,'job_id':active.pk,'existing':True})
    prompt=' '.join((request.POST.get('campaign_template_prompt') or DEFAULT_CAMPAIGN_TEMPLATE_PROMPT).split())[:1800]
    job=BackgroundJob.objects.create(kind='prepare',label='Generate campaign templates',message='Queued')
    task=campaign_templates_job.delay(job.pk,prompt); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
    return JsonResponse({'ok':True,'job_id':job.pk})


@login_required
def scope_view(request):
    p=Profile.objects.get_or_create(pk=1)[0]
    defaults={'engagement':['full-time','part-time','contract','agency/consulting','one-time project','collaboration','unknown'],'company_size':['solo/very small','small','startup','medium','unknown'],'pay_preferences':[],'hard_geo':False,'exclude_marketplaces':True,'interview_notes':'Prefer 1-2 sessions; take-home acceptable; avoid LeetCode/live coding/psychometric tests and long forms.'}
    data=defaults|p.scope_json
    from .services.salary import normalized_pay_preferences
    data['pay_preferences']=normalized_pay_preferences(data)
    if request.method=='POST':
        errors=[]; pay_preferences=[]
        amounts=request.POST.getlist('pay_amount'); currencies=request.POST.getlist('pay_currency_row'); periods=request.POST.getlist('pay_period_row')
        valid_periods={'year','month','day','hour','project'}
        for i,raw in enumerate(amounts):
            raw=(raw or '').strip()
            if not raw: continue
            try:
                amount=float(raw)
                if amount<=0: raise ValueError
            except Exception:
                errors.append(f'Pay preference {i+1} must be a positive number.'); continue
            currency=(currencies[i] if i<len(currencies) else 'SGD').upper(); period=(periods[i] if i<len(periods) else 'year')
            if currency not in CURRENCIES: errors.append(f'Pay preference {i+1} has an unsupported currency.'); continue
            if period not in valid_periods: errors.append(f'Pay preference {i+1} has an invalid period.'); continue
            pay_preferences.append({'amount':raw,'currency':currency,'period':period})
        locations=[x for x in request.POST.getlist('operating_locations') if x in COUNTRIES]
        if not locations: errors.append('Add at least one operating country/region.')
        if errors:
            for e in errors: messages.error(request,e)
        else:
            data={'engagement':request.POST.getlist('engagement'),'company_size':request.POST.getlist('company_size'),'pay_preferences':pay_preferences,'hard_geo':False,'exclude_marketplaces':bool(request.POST.get('exclude_marketplaces')),'interview_notes':request.POST.get('interview_notes','').strip()}
            # Keep legacy keys for older ranking code/custom reports; first matching rule is only a compatibility mirror.
            if pay_preferences:
                data.update({'min_pay':pay_preferences[0]['amount'],'pay_currency':pay_preferences[0]['currency'],'pay_period':pay_preferences[0]['period']})
            merged_scope=dict(p.scope_json or {}); merged_scope.update(data)
            p.scope_json=merged_scope; p.operating_locations=locations; p.operating_location=locations[0]
            p.save(update_fields=['scope_json','operating_locations','operating_location','updated_at']); messages.success(request,'Engagement preferences saved.'); return redirect('scope')
    return render(request,'portal/scope.html',ctx(request,'scope','Engagement Preferences',profile=p,scope=data,operating_locations=p.operating_locations or ([p.operating_location] if p.operating_location else [])))


def _search_provider_health(source):
    state=provider_credential_state(source)
    today=timezone.localdate()
    stat=SearchProviderStat.objects.filter(source=source,day=today).first()
    requests=int(getattr(stat,'requests',0) or 0); errors=int(getattr(stat,'errors',0) or 0); results=int(getattr(stat,'results',0) or 0)
    error_rate=(errors/requests) if requests else 0.0
    public_selected=state.get('access_type')=='public'
    public_ready=bool(state.get('public_query_template') and (public_selected or (state.get('public_fallback') and source.public_fallback)))
    api_ready=bool(state.get('api_configured'))
    ready=bool(source.enabled and (api_ready or public_ready or (not state.get('api_name') and state.get('public_query_template'))))
    recent=SearchProviderStat.objects.filter(source=source,day__gte=today-timedelta(days=6)).aggregate(requests=Sum('requests'),results=Sum('results'),errors=Sum('errors'))
    recent_requests=int(recent.get('requests') or 0); recent_results=int(recent.get('results') or 0); recent_errors=int(recent.get('errors') or 0)
    common={'requests_today':requests,'errors_today':errors,'results_today':results,'error_rate':error_rate,'recent_requests':recent_requests,'recent_results':recent_results,'recent_errors':recent_errors}
    if not ready:
        return {**state,**common,'health_state':'error','health_icon':'provider_error_v3','health_title':'Not configured or disabled'}
    # Zero-result detection deliberately considers recent persisted provider statistics, not only
    # the current calendar day. This prevents a provider from looking merely idle after repeated
    # successful HTTP requests that never produced a parsed result.
    if requests>=5 and results==0 and errors==0:
        return {**state,**common,'health_state':'stalled','health_icon':'provider_no_results_v3','health_title':f'No results returned from {requests} error-free requests today'}
    if requests==0 and recent_requests>=5 and recent_results==0 and recent_errors==0:
        return {**state,**common,'health_state':'stalled','health_icon':'provider_no_results_v3','health_title':f'No results returned from {recent_requests} error-free requests in the last 7 days'}
    if requests>=3 and (errors>=5 or error_rate>=.35):
        return {**state,**common,'health_state':'warn','health_icon':'provider_warn_v3','health_title':f"Configured, but today's error rate is {error_rate:.0%} ({errors}/{requests})"}
    if requests==0:
        return {**state,**common,'health_state':'idle','health_icon':'provider_idle_ready_v3','health_title':'Configured and ready; no requests have been made today'}
    return {**state,**common,'health_state':'ok','health_icon':'provider_ok_v3','health_title':'Configured and healthy'}


def _forum_source_health(source):
    """Forum checklist health marker using the same visual vocabulary as search engines."""
    today=timezone.localdate()
    try:
        stat=SearchProviderStat.objects.filter(source=source,day=today).first()
        requests=int(getattr(stat,'requests',0) or 0)
        errors=int(getattr(stat,'errors',0) or 0)
        results=int(getattr(stat,'results',0) or 0)
    except Exception:
        requests=errors=results=0
    try:
        recent=SearchProviderStat.objects.filter(source=source,day__gte=today-timedelta(days=6)).aggregate(requests=Sum('requests'),results=Sum('results'),errors=Sum('errors'))
        recent_requests=int(recent.get('requests') or 0); recent_results=int(recent.get('results') or 0); recent_errors=int(recent.get('errors') or 0)
    except Exception:
        recent_requests=requests; recent_results=results; recent_errors=errors
    error_rate=(errors/requests) if requests else 0.0
    if not getattr(source,'enabled',False):
        return {'state':'idle','icon':'provider_idle_ready_v3','title':'Disabled'}
    if requests>=3 and (errors>=5 or error_rate>=.35):
        return {'state':'warn','icon':'provider_warn_v3','title':f"Elevated forum error rate today: {error_rate:.0%} ({errors}/{requests})"}
    if recent_requests>=5 and recent_results==0 and recent_errors==0:
        return {'state':'stalled','icon':'provider_no_results_v3','title':f'No results from {recent_requests} error-free forum requests in the last 7 days'}
    if requests>=3 and results==0 and errors==0:
        return {'state':'stalled','icon':'provider_no_results_v3','title':f'No results from {requests} error-free forum requests today'}
    if results>0 and error_rate<.20:
        return {'state':'ok','icon':'provider_ok_v3','title':f'Forum returned {results} result{("" if results==1 else "s")} today with low error rate'}
    if requests==0:
        return {'state':'idle','icon':'provider_idle_ready_v3','title':'Forum enabled; no requests have been made today'}
    if errors:
        return {'state':'warn','icon':'provider_warn_v3','title':f'Forum had {errors} error{("" if errors==1 else "s")} today'}
    return {'state':'idle','icon':'provider_idle_ready_v3','title':'Forum checked; no accepted results yet'}


def _provider_request_history(source, limit=20):
    rows=[]
    try:
        qs=UsageMetric.objects.filter(provider=source.name,stage='query').order_by('-at')[:limit]
        for m in qs:
            meta=m.metadata or {}
            rows.append({
                'at':m.at, 'query':str(meta.get('query') or ''),
                'results':int(meta.get('results') or 0), 'errors':int(m.errors or 0),
                'status':('Error' if m.errors else ('No results' if int(meta.get('results') or 0)==0 else 'OK')),
                'detail':str(meta.get('error') or meta.get('message') or ''),
            })
    except Exception:
        return []
    return rows


def _provider_error_history(source, limit=20):
    rows=[]
    try:
        qs=UsageMetric.objects.filter(provider=source.name,stage='query',errors__gt=0).order_by('-at')[:limit]
        for m in qs:
            meta=m.metadata or {}
            rows.append({'at':m.at,'query':str(meta.get('query') or ''),'detail':str(meta.get('error') or meta.get('message') or 'Search request failed')})
    except Exception:
        pass
    # SearchProviderStat preserves the last adapter error even on older databases where
    # UsageMetric metadata did not yet carry the error text.
    try:
        for st in SearchProviderStat.objects.filter(source=source).exclude(last_error='').order_by('-day')[:limit]:
            # ``SearchProviderStat.day`` is a DateField.  The Search Sources template
            # renders request/error timestamps with hour/minute/second specifiers, and
            # Django correctly rejects time-related format specifiers for a bare date.
            # Promote historical day-only rows to local midnight so one old provider
            # error cannot force the entire Search Sources screen into safe mode.
            at = datetime.combine(st.day, datetime.min.time())
            if timezone.is_naive(at):
                at = timezone.make_aware(at, timezone.get_current_timezone())
            rows.append({'at':at,'query':'','detail':st.last_error})
    except Exception:
        pass
    return rows[:limit]



def _quota_pressure_state(used, limit):
    """Schedule/Limit gauge state: gray unused, green <60%, amber 60-90%, red >90%."""
    try: used=max(0,int(used or 0)); limit=max(0,int(limit or 0))
    except Exception: return 'unused'
    if not limit or not used: return 'unused'
    ratio=float(used)/float(limit)
    if ratio>0.90: return 'critical'
    if ratio>=0.60: return 'warning'
    return 'healthy'


def _searchapi_histories(limit=20):
    """Aggregate SearchAPI history while preserving the logging split requested by the UI.

    Non-ChatGPT SearchAPI work comes from Search Activity (UsageMetric stage=query).
    ChatGPT comes from AIRequestLog/Cloud Runtime and is not duplicated into Search Activity.
    """
    names=list(SEARCHAPI_SERVICE_SOURCES.values())
    source_to_code={v:k for k,v in SEARCHAPI_SERVICE_SOURCES.items()}
    requests=[]; errors=[]
    try:
        for m in UsageMetric.objects.filter(provider__in=names,stage='query').order_by('-at')[:max(80,limit*4)]:
            code=source_to_code.get(m.provider,''); meta=m.metadata or {}; err=int(m.errors or 0)
            row={'at':m.at,'service':SEARCHAPI_SHORT_LABELS.get(code,code or 'SearchAPI'),'query':str(meta.get('query') or ''),'results':int(meta.get('results') or 0),'errors':err,'status':('Error' if err else ('No results' if int(meta.get('results') or 0)==0 else 'OK')),'detail':str(meta.get('error') or meta.get('message') or '')}
            requests.append(row)
            if err: errors.append(dict(row))
    except Exception:
        pass
    try:
        for logrow in AIRequestLog.objects.filter(provider='SearchAPI',runtime='cloud',stage='searchapi_research').order_by('-at')[:max(40,limit*2)]:
            meta=logrow.metadata or {}; code=str(meta.get('searchapi_service') or 'chatgpt')
            refs=meta.get('references') or []
            row={'at':logrow.at,'service':SEARCHAPI_SHORT_LABELS.get(code,'ChatGPT'),'query':str(logrow.input_text or '')[:500],'results':len(refs) if isinstance(refs,list) else 0,'errors':0 if logrow.ok else 1,'status':('OK' if logrow.ok else 'Error'),'detail':str(logrow.error or '')}
            requests.append(row)
            if not logrow.ok: errors.append(dict(row))
    except Exception:
        pass
    requests.sort(key=lambda x:x.get('at') or timezone.now(),reverse=True)
    errors.sort(key=lambda x:x.get('at') or timezone.now(),reverse=True)
    return requests[:limit],errors[:limit]


def _searchapi_service_ui_rows():
    rows=[]
    for code,name in SEARCHAPI_SERVICE_SOURCES.items():
        source=SearchSource.objects.filter(name=name).first()
        if not source: continue
        cfg=dict(source.config_json or {})
        auto=bool(cfg.get('auto_enabled',SEARCHAPI_DEFAULT_AUTO.get(code,False)))
        state='disabled'; label='Disabled'
        if auto and source.enabled:
            try:
                health=_search_provider_health(source)
                state=health.get('health_state','idle'); label=health.get('health_title','Configured')
            except Exception:
                state='idle'; label='Enabled'
        try: cap=int(cfg.get('auto_daily_limit',100 if code in {'chatgpt','ai_mode'} else 0) or 0)
        except Exception: cap=100 if code in {'chatgpt','ai_mode'} else 0
        rows.append({'code':code,'name':name,'label':SEARCHAPI_SERVICE_LABELS.get(code,name),'short_label':SEARCHAPI_SHORT_LABELS.get(code,code),'auto_enabled':auto,'effective_enabled':bool(source.enabled and auto),'health_state':state,'health_title':label,'auto_daily_limit':cap})
    return rows

def _sources_view_impl(request):
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    # Facebook is an optional discovery integration.  A stale/missing FacebookConfig
    # schema on an upgraded installation must never make the core Search Sources
    # configuration page fail.  Use an unsaved default object until migrations catch up.
    try:
        fb=FacebookConfig.objects.get_or_create(pk=1)[0]
    except Exception:
        logger.exception('Facebook configuration unavailable while rendering Search Sources')
        fb=FacebookConfig()
    export_kind=(request.GET.get('export') or '').strip().lower()
    if export_kind=='facebook':
        rows=FacebookPage.objects.all().order_by('page_title','page_id')
        return _xlsx('facebook_pages.xlsx',['Page ID','Title','URL','Added'],[(x.page_id,x.page_title,x.page_url,x.discovered_at) for x in rows[:10000]])
    if export_kind=='provider_stats':
        rows=SearchProviderStat.objects.filter(day=timezone.localdate()).select_related('source').order_by('-requests')
        return _xlsx('discovery_source_activity_today.xlsx',['Discovery Source','Requests','Returned results','Unique matches','Applied matches','Duplicates','Errors','Avg latency ms','Size bytes','Last error'],[(x.source.name,x.requests,x.results,x.unique_results,x.applied_matches,x.duplicates,x.errors,x.avg_latency_ms,x.bytes_downloaded,x.last_error) for x in rows[:10000]])
    provider_test=None
    if request.method=='POST':
        action=request.POST.get('action')
        if action in ('select_all','clear_all'):
            if action=='select_all':
                SearchSource.objects.exclude(source_type__in=['cloud_ai','forum']).filter(low_value_marketplace=False).update(enabled=True)
                SearchSource.objects.exclude(source_type__in=['cloud_ai','forum']).filter(low_value_marketplace=True).update(enabled=False)
            else:
                SearchSource.objects.exclude(source_type__in=['cloud_ai','forum']).update(enabled=False)
            messages.success(request,'Source selection updated.')
            return redirect('sources')
        elif action=='save_discovery_markets':
            ps=PortalSettings.objects.get_or_create(pk=1)[0]
            allowed={m.code for m in MARKETS}; selected=[x for x in request.POST.getlist('discovery_market') if x in allowed]
            ps.discovery_markets=selected or list(DEFAULT_MARKET_CODES)
            strategy=(request.POST.get('discovery_market_strategy') or 'global').strip().lower()
            ps.discovery_market_strategy=strategy if strategy in {'global','balanced','adaptive','even'} else 'global'
            # Local-language exploration is always active. Strength remains the bounded
            # workload control and additional languages always have an observable effect.
            ps.multilingual_exploration_enabled=True
            # Market-native languages are always inferred. This legacy field is retained
            # for schema compatibility but no longer controls discovery behavior.
            ps.multilingual_language_mode='auto'
            langs=[]; language_lookup={name.casefold():name for name,_flag in MULTILINGUAL_LANGUAGE_OPTIONS}
            for raw in request.POST.getlist('multilingual_languages'):
                for piece in re.split(r'[,;|\n]+',str(raw or '')):
                    submitted=' '.join(piece.split())[:40]; val=language_lookup.get(submitted.casefold(),'')
                    if val and val.casefold() not in {x.casefold() for x in langs}: langs.append(val)
            ps.multilingual_languages=langs[:20]
            strength=(request.POST.get('multilingual_exploration_strength') or 'balanced').strip().lower(); ps.multilingual_exploration_strength=strength if strength in {'low','balanced','high'} else 'balanced'
            ps.save(update_fields=['discovery_markets','discovery_market_strategy','multilingual_exploration_enabled','multilingual_language_mode','multilingual_languages','multilingual_exploration_strength','updated_at'])
            messages.success(request,'Discovery Markets saved.'); return redirect(reverse('sources')+'#source-markets')
        elif action=='save_custom_domain':
            row_id=(request.POST.get('row_id') or '').strip(); name=(request.POST.get('name') or '').strip(); domain=(request.POST.get('domain') or '').strip().lower(); note=(request.POST.get('note') or '').strip()
            domain=re.sub(r'^https?://','',domain).split('/',1)[0].split(':',1)[0].removeprefix('www.')
            if len(name)<2 or not re.match(r'^[a-z0-9.-]+\.[a-z]{2,}$',domain,re.I):
                messages.error(request,'Enter a name and a valid domain such as example.com.')
            elif CustomSearchDomain.objects.exclude(pk=row_id if row_id.isdigit() else None).filter(domain__iexact=domain).exists():
                messages.error(request,'That custom domain already exists.')
            else:
                row=CustomSearchDomain.objects.filter(pk=row_id).first() if row_id.isdigit() else CustomSearchDomain()
                row.name=name[:160]; row.domain=domain[:255]; row.note=note; row.enabled=bool(request.POST.get('enabled')); row.save(); messages.success(request,'Custom search domain saved.')
            return redirect('sources')
        elif action=='delete_custom_domain':
            CustomSearchDomain.objects.filter(pk=request.POST.get('row_id')).delete(); messages.success(request,'Custom search domain removed.'); return redirect('sources')
        elif action=='save_forum_sources':
            ids=set(request.POST.getlist('forum_source_ids'))
            for source in SearchSource.objects.filter(source_type='forum'):
                source.enabled=str(source.pk) in ids
                source.save(update_fields=['enabled'])
            messages.success(request,'Forum source selection saved.'); return redirect(reverse('sources')+'#source-forums')
        elif action=='save_sources':
            ids=set(request.POST.getlist('source_ids')); profile=Profile.objects.get_or_create(pk=1)[0]
            # SearchAPI is one visible source. Its child services keep their individual
            # auto_enabled flags from the unified dialog and follow the one master checkbox.
            searchapi_hub=searchapi_source('jobs')
            searchapi_master=bool(searchapi_hub and str(searchapi_hub.pk) in ids)
            for source in SearchSource.objects.exclude(source_type='cloud_ai').exclude(source_type='forum'):
                if source.name.startswith('SearchAPI ·'):
                    cfg=dict(source.config_json or {})
                    auto=bool(cfg.get('auto_enabled',SEARCHAPI_DEFAULT_AUTO.get(searchapi_service_code(source),False)))
                    source.enabled=bool(searchapi_master and auto)
                    if source is searchapi_hub or source.pk==getattr(searchapi_hub,'pk',None):
                        cfg['searchapi_master_enabled']=searchapi_master
                        source.config_json=cfg; source.save(update_fields=['enabled','config_json'])
                    else:
                        source.save(update_fields=['enabled'])
                    continue
                enabled=str(source.pk) in ids
                if source.low_value_marketplace and enabled and profile.scope_json.get('exclude_marketplaces',True): enabled=False
                source.enabled=enabled; source.save(update_fields=['enabled'])
            messages.success(request,'Discovery source selection saved.'); return redirect('sources')
        elif action=='save_source_advanced':
            source=get_object_or_404(SearchSource,pk=request.POST.get('source_id'))
            try: source.provider_weight=max(1,min(500,int(request.POST.get('provider_weight') or 100)))
            except Exception: source.provider_weight=100
            raw=request.POST.get('daily_budget_override','').strip(); source.daily_budget_override=max(1,min(10000,int(raw))) if raw.isdigit() else None
            source.save(update_fields=['provider_weight','daily_budget_override'])
            messages.success(request,f'Advanced settings saved for {source.name}.'); return redirect('sources')
        elif action=='reset_source_advanced':
            source=get_object_or_404(SearchSource,pk=request.POST.get('source_id'))
            source.provider_weight=100; source.daily_budget_override=None; source.save(update_fields=['provider_weight','daily_budget_override'])
            messages.success(request,f'{source.name} now inherits the recommended provider defaults.'); return redirect('sources')
        elif action=='save_provider_config':
            source=get_object_or_404(SearchSource,pk=request.POST.get('source_id'))
            if source.name=='SearchAPI · Google Jobs':
                hub_cfg=dict(source.config_json or {})
                master=bool(hub_cfg.get('searchapi_master_enabled',source.enabled))
                api_key=request.POST.get('api_key','').strip()
                if api_key:
                    source.api_key_enc=encrypt(api_key)
                    # SearchAPI is one credential pool. Remove legacy child-service keys
                    # so a stale pre-unification key can never override the hub credential.
                    SearchSource.objects.filter(name__startswith='SearchAPI ·').exclude(pk=source.pk).update(api_key_enc='')
                if request.POST.get('clear_api_key'):
                    SearchSource.objects.filter(name__startswith='SearchAPI ·').update(api_key_enc='')
                    source.api_key_enc=''
                selected=set(request.POST.getlist('searchapi_services'))
                for code,name in SEARCHAPI_SERVICE_SOURCES.items():
                    sibling=SearchSource.objects.filter(name=name).first()
                    if not sibling: continue
                    cfg=dict(sibling.config_json or {})
                    auto=code in selected; cfg['auto_enabled']=auto
                    if code=='chatgpt':
                        try: cfg['auto_daily_limit']=max(0,min(1000,int(request.POST.get('chatgpt_auto_daily_limit') or 100)))
                        except Exception: cfg['auto_daily_limit']=100
                    if code=='ai_mode':
                        try: cfg['auto_daily_limit']=max(0,min(1000,int(request.POST.get('ai_mode_auto_daily_limit') or 100)))
                        except Exception: cfg['auto_daily_limit']=100
                    if sibling.pk==source.pk:
                        cfg['searchapi_master_enabled']=master
                        sibling.api_key_enc=source.api_key_enc
                    sibling.config_json=cfg; sibling.enabled=bool(master and auto)
                    fields=['config_json','enabled']+(['api_key_enc'] if sibling.pk==source.pk else [])
                    sibling.save(update_fields=fields)

                # Validate the effective shared credential after saving it. This is a
                # configuration check only: validate_searchapi_credential deliberately
                # creates no Search Activity, provider-yield, or AI Request telemetry.
                state=provider_credential_state(source)
                hub_cfg=dict(source.config_json or {})
                if state.get('api_configured'):
                    validation=validate_searchapi_credential(source)
                    validation_state=str(validation.get('status') or 'unavailable')
                    validation_message=str(validation.get('message') or '')[:1000]
                    hub_cfg['searchapi_validation_status']=validation_state
                    hub_cfg['searchapi_validation_message']=validation_message
                    hub_cfg['searchapi_validation_http_status']=int(validation.get('http_status') or 0)
                    hub_cfg['searchapi_validated_at']=timezone.now().isoformat()
                    source.config_json=hub_cfg; source.save(update_fields=['config_json'])
                    if validation_state=='valid':
                        messages.success(request,'SearchAPI API key saved and validated.')
                    elif validation_state=='invalid':
                        messages.warning(request,'SearchAPI API key saved, but SearchAPI rejected it during validation. The key remains saved so you can correct or retry it.')
                    else:
                        messages.warning(request,'SearchAPI API key saved. Validation could not be completed; any successful SearchAPI request will confirm it automatically.')
                else:
                    hub_cfg['searchapi_validation_status']='unconfigured'
                    hub_cfg['searchapi_validation_message']='No SearchAPI API key is configured.'
                    hub_cfg.pop('searchapi_validation_http_status',None)
                    hub_cfg['searchapi_validated_at']=timezone.now().isoformat()
                    source.config_json=hub_cfg; source.save(update_fields=['config_json'])
                    messages.success(request,'SearchAPI configuration saved. Add an API key to enable SearchAPI requests.')
                return redirect('sources')
            state=provider_credential_state(source)
            source.public_fallback=bool(request.POST.get('public_fallback'))
            cfg=dict(source.config_json or {})
            options=state.get('access_options') or provider_capability(source).get('access_options') or []
            if options:
                allowed={str(x.get('value')):x for x in options}
                access_type=(request.POST.get('access_type') or 'public').strip()
                if access_type not in allowed:
                    messages.error(request,'Invalid access type for this search provider.'); return redirect('sources')
                cfg['access_type']=access_type
                slots=dict(cfg.get('access_credentials') or {}); slot=dict(slots.get(access_type) or {})
                api_key=request.POST.get('api_key','').strip(); extra=request.POST.get('api_extra','').strip()
                if api_key: slot['secret_enc']=encrypt(api_key)
                if request.POST.get('clear_api_key'): slot.pop('secret_enc',None)
                if extra: slot['extra']=extra[:500]
                if request.POST.get('clear_api_extra'): slot.pop('extra',None)
                slots[access_type]=slot; cfg['access_credentials']=slots
            else:
                api_key=request.POST.get('api_key','').strip()
                if api_key: source.api_key_enc=encrypt(api_key)
                if request.POST.get('clear_api_key'): source.api_key_enc=''
                if state.get('extra_key'):
                    extra=request.POST.get('api_extra','').strip()
                    if extra: cfg['api_extra']=extra
                    if request.POST.get('clear_api_extra'): cfg.pop('api_extra',None)
            public_template=request.POST.get('public_query_template','').strip()
            if public_template:
                if '{query}' not in public_template:
                    messages.error(request,'Public query template must include {query}.')
                    return redirect('sources')
                if not public_template.startswith(('http://','https://')):
                    messages.error(request,'Public query template must be a complete http:// or https:// URL.')
                    return redirect('sources')
                cfg['public_query_template']=public_template[:1500]
            else:
                cfg.pop('public_query_template',None)
            source.config_json=cfg
            source.save(update_fields=['public_fallback','api_key_enc','config_json'])
            messages.success(request,f'{source.name} search configuration saved.'); return redirect('sources')
        elif action=='test_provider':
            source=get_object_or_404(SearchSource,pk=request.POST.get('source_id'))
            provider_test={'source_id':source.pk, **test_search_provider(source,force_public=bool(request.POST.get('force_public')))}
        elif action=='save_scheduler':
            allowed_intervals={30,60,120,180,360,720}
            try: interval=int(request.POST.get('scraper_interval_minutes') or 120)
            except Exception: interval=120
            ps.scraper_interval_minutes=interval if interval in allowed_intervals else 120
            limits={
                'keywords_per_run':(1,100,SEARCH_SCHEDULE_DEFAULTS['keywords_per_run']),
                'queries_per_provider':(1,100,SEARCH_SCHEDULE_DEFAULTS['queries_per_provider']),
                'provider_public_daily_request_budget':(1,10000,SEARCH_SCHEDULE_DEFAULTS['provider_public_daily_request_budget']),
                'provider_api_daily_request_budget':(1,10000,SEARCH_SCHEDULE_DEFAULTS['provider_api_daily_request_budget']),
                'searchapi_daily_limit':(0,10000,SEARCH_SCHEDULE_DEFAULTS['searchapi_daily_limit']),
                'max_results_per_query':(1,100,SEARCH_SCHEDULE_DEFAULTS['max_results_per_query']),
                'followup_pages_per_run':(0,250,SEARCH_SCHEDULE_DEFAULTS['followup_pages_per_run']),
                'followup_link_depth':(0,5,SEARCH_SCHEDULE_DEFAULTS['followup_link_depth']),
            }
            for field,(lo,hi,default) in limits.items():
                try: setattr(ps,field,max(lo,min(hi,int(request.POST.get(field,default)))))
                except Exception: setattr(ps,field,default)
            cloud_limits={
                'cloud_min_interval_minutes':(15,1440,SEARCH_SCHEDULE_DEFAULTS['cloud_min_interval_minutes']),
                'cloud_auto_runs_per_campaign_day':(1,48,SEARCH_SCHEDULE_DEFAULTS['cloud_auto_runs_per_campaign_day']),
                'cloud_requests_per_run':(1,500,SEARCH_SCHEDULE_DEFAULTS['cloud_requests_per_run']),
                'cloud_web_searches_per_run':(1,500,SEARCH_SCHEDULE_DEFAULTS['cloud_web_searches_per_run']),
                'cloud_discovery_candidates_per_run':(1,500,SEARCH_SCHEDULE_DEFAULTS['cloud_discovery_candidates_per_run']),
                'cloud_deep_research_candidates_per_run':(1,500,SEARCH_SCHEDULE_DEFAULTS['cloud_deep_research_candidates_per_run']),
                'cloud_daily_requests':(1,10000,SEARCH_SCHEDULE_DEFAULTS['cloud_daily_requests']),
                'cloud_daily_web_searches':(1,10000,SEARCH_SCHEDULE_DEFAULTS['cloud_daily_web_searches']),
                'cloud_daily_input_tokens':(1000,50000000,SEARCH_SCHEDULE_DEFAULTS['cloud_daily_input_tokens']),
                'cloud_daily_output_tokens':(1000,10000000,SEARCH_SCHEDULE_DEFAULTS['cloud_daily_output_tokens']),
                'cloud_passive_enrichment_per_day':(0,1000,SEARCH_SCHEDULE_DEFAULTS['cloud_passive_enrichment_per_day']),
                'cloud_page_recovery_per_day':(0,2000,SEARCH_SCHEDULE_DEFAULTS['cloud_page_recovery_per_day']),
                'cloud_test_searches_per_run':(1,100,SEARCH_SCHEDULE_DEFAULTS['cloud_test_searches_per_run']),
                'cloud_test_candidates':(1,100,SEARCH_SCHEDULE_DEFAULTS['cloud_test_candidates']),
            }
            for field,(lo,hi,default) in cloud_limits.items():
                try: setattr(ps,field,max(lo,min(hi,int(request.POST.get(field,default)))))
                except Exception: setattr(ps,field,default)
            ps.save(); messages.success(request,'Search schedule and safety limits saved.'); return redirect('sources')
        elif action=='restore_defaults':
            for field,value in SEARCH_SCHEDULE_DEFAULTS.items():
                setattr(ps,field,value)
            ps.save(update_fields=[*SEARCH_SCHEDULE_DEFAULTS.keys(),'updated_at'])
            SearchSource.objects.filter(name__in=ACTIVE_PROVIDER_NAMES).update(provider_weight=100,daily_budget_override=None)
            messages.success(request,'Recommended search defaults restored.'); return redirect('sources')
        elif action=='save_facebook':
            fb.use_search_index=bool(request.POST.get('use_search_index')); fb.use_graph_api=bool(request.POST.get('use_graph_api')); fb.use_authenticated_cookie=bool(request.POST.get('use_authenticated_cookie'))
            if request.POST.get('graph_access_token'): fb.graph_access_token_enc=encrypt(request.POST.get('graph_access_token'))
            if request.POST.get('cookie_header'): fb.cookie_header_enc=encrypt(request.POST.get('cookie_header'))
            fb.save(); messages.success(request,'Facebook discovery settings saved.'); return redirect('sources')
        elif action=='save_facebook_page':
            page_id=request.POST.get('page_id','').strip()
            page_title=request.POST.get('page_title','').strip()
            if not page_id: messages.error(request,'Page ID is required.')
            else:
                candidate_url=f'https://www.facebook.com/{page_id}'
                relevant,reason,_direct,_page_title=facebook_page_relevant(candidate_url,page_title,'',direct=True)
                if not relevant:
                    messages.error(request,'Page was not added: direct Page validation found '+reason+'.')
                    return redirect(reverse('sources')+'#source-facebook')
                row_id=(request.POST.get('row_id') or '').strip()
                row=FacebookPage.objects.filter(pk=int(row_id)).first() if row_id.isdigit() else None
                if row:
                    if FacebookPage.objects.exclude(pk=row.pk).filter(page_id=page_id).exists(): messages.error(request,'That Page ID already exists.')
                    else:
                        old_page_id=row.page_id
                        row.page_id=page_id
                        # Pages to Watch no longer has a separate Use toggle: a row
                        # exists because it is being watched; delete it to stop using it.
                        row.enabled=True
                        row.page_title=(_page_title or page_title or page_id)[:300]
                        row.validation_state='verified' if reason.startswith('direct Page-owned') else 'indexed'; row.validation_reason=reason[:500]; row.validated_at=timezone.now()
                        if not row.page_url or old_page_id!=page_id: row.page_url=f'https://www.facebook.com/{page_id}'[:1000]
                        row.save(); messages.success(request,'Facebook Page watch updated.')
                else:
                    if not page_title:
                        messages.error(request,'Page Title is required when adding a page.')
                    elif FacebookPage.objects.filter(page_id=page_id).exists():
                        messages.error(request,'That Page ID already exists.')
                    else:
                        FacebookPage.objects.create(page_id=page_id,page_title=(_page_title or page_title or page_id)[:300],page_url=f'https://www.facebook.com/{page_id}'[:1000],evidence_text=page_title[:8000],enabled=True,is_read=True,validation_state=('verified' if reason.startswith('direct Page-owned') else 'indexed'),validation_reason=reason[:500],validated_at=timezone.now())
                        messages.success(request,'Facebook Page added to the watch list.')
            return redirect(reverse('sources')+'#source-facebook')
        elif action=='delete_facebook_page':
            row_id=(request.POST.get('row_id') or '').strip()
            if row_id.isdigit(): FacebookPage.objects.filter(pk=int(row_id),deleted_at__isnull=True).update(deleted_at=timezone.now(),enabled=False,is_read=True)
            messages.success(request,'Facebook Page removed from watch list.'); return redirect(reverse('sources')+'#source-facebook')
        elif action=='delete_facebook_pages':
            ids=[x for x in request.POST.getlist('facebook_page_ids') if str(x).isdigit()]
            deleted=FacebookPage.objects.filter(pk__in=ids,deleted_at__isnull=True).update(deleted_at=timezone.now(),enabled=False,is_read=True) if ids else 0
            messages.success(request,f'Removed {deleted} Facebook Page{"" if deleted==1 else "s"} from the watch list.')
            return redirect(reverse('sources')+'#source-facebook')
        elif action=='test_facebook_cookie':
            url=request.POST.get('facebook_test_url','https://www.facebook.com/')
            data,err=facebook_authenticated_fetch(url); fb.last_test_ok=not bool(err); fb.last_test_message=err or f'Fetched {len(data.get("text", ""))} visible characters'; fb.save()
            messages.success(request,fb.last_test_message) if fb.last_test_ok else messages.error(request,fb.last_test_message)

    categories={}; source_load_error=''
    try:
        source_rows=list(SearchSource.objects.exclude(source_type='cloud_ai').exclude(source_type='forum').exclude(category__in=['Specialist / custom','Feeds / announcements','Europe / international','Cloud AI Discovery']).exclude(category__iexact='Cloud AI Discovery').exclude(name='RSS / Atom feeds').order_by('category','name'))
    except Exception as exc:
        # Search Sources is a configuration/debugging screen. A telemetry/provider
        # problem must never turn the whole screen into HTTP 500.
        source_rows=[]; source_load_error=str(exc)[:500]
    searchapi_hub=next((x for x in source_rows if x.name=='SearchAPI · Google Jobs'),None)
    searchapi_requests,searchapi_errors=_searchapi_histories(20)
    searchapi_services=_searchapi_service_ui_rows()
    for source in source_rows:
        tags=[]; cat=(source.category or '').lower()
        source_cfg=source.config_json if isinstance(source.config_json,dict) else {}
        source.direct_adapter=str(source_cfg.get('direct_adapter') or '').strip()
        source.direct_capability=str(source_cfg.get('direct_capability') or '').strip()
        source.discovery_capability=str(source_cfg.get('discovery_capability') or source.direct_capability or 'Search engine · always').strip()
        if source.direct_adapter: tags.append('Direct')
        if source.source_type=='ats' or 'ats' in cat: tags.append('ATS')
        if 'developer' in cat or 'engineering' in cat: tags.append('Developer')
        if 'europe' in cat: tags.append('Europe')
        if 'singapore' in cat or 'apac' in cat: tags.append('APAC')
        if 'remote' in cat: tags.append('Remote')
        if 'startup' in cat: tags.append('Startup')
        if source.source_type in ('community','social'): tags.append(source.source_type.title())
        if source.low_value_marketplace: tags.append('Excluded')
        source.display_tags=list(dict.fromkeys(tags))
        source.openable_url=(source.base_url or '') if source.base_url and 'example.invalid' not in source.base_url else ''
        health=_forum_source_health(source)
        source.forum_health_state=health.get('state','idle')
        source.forum_health_icon=health.get('icon','provider_idle_ready_v3')
        source.forum_health_title=health.get('title','Forum status unavailable')
        source.provider_ui=None
        source.recent_requests=[]; source.recent_errors=[]
        if source.name in ACTIVE_PROVIDER_NAMES:
            cap=provider_capability(source)
            try:
                source.provider_ui=_search_provider_health(source)
            except Exception as exc:
                # Keep provider configuration usable even when telemetry/health diagnostics fail.
                # Access choices come from the adapter capability table, never from the health path.
                access_options=list(cap.get('access_options') or [])
                access_type='public' if access_options else ''
                source.provider_ui={**cap,'health_state':'error','health_icon':'provider_error_v3','health_title':'Provider diagnostics unavailable','mode':'Unavailable','api_configured':False,'api_name':'','stored_key':False,'env_key_present':False,'extra_key':'','extra_label':'','extra_configured':False,'public_query_template':'','error_detail':str(exc)[:240],'access_options':access_options,'api_access_options':[x for x in access_options if x.get('value')!='public'],'access_type':access_type,'access_type_label':'Public Access'}
            # Multi-access engines must always render their complete adapter-defined choices.
            # This prevents a diagnostic/config-state failure from collapsing the select to Public Access only.
            if cap.get('access_options'):
                source.provider_ui['access_options']=list(cap['access_options'])
                source.provider_ui['api_access_options']=[x for x in cap['access_options'] if x.get('value')!='public']
                valid={str(x.get('value') or '') for x in cap['access_options']}
                if str(source.provider_ui.get('access_type') or '') not in valid:
                    source.provider_ui['access_type']='public'
                selected=next((x for x in cap['access_options'] if x.get('value')==source.provider_ui['access_type']),cap['access_options'][0])
                source.provider_ui['access_type_label']=selected.get('label') or 'Public Access'
                source.provider_ui['api_name']=selected.get('api_name') or ''
                source.provider_ui['secret_label']=selected.get('secret_label') or 'API key / secret'
                source.provider_ui['extra_label']=selected.get('extra_label') or ''
            source.recent_requests=_provider_request_history(source,20)
            source.recent_errors=_provider_error_history(source,20)
            try:
                used=provider_budget_used(source); budget=provider_budget(source); remaining=max(0,budget-used)
                tomorrow=timezone.localdate()+timedelta(days=1)
                reset_at=timezone.make_aware(datetime.combine(tomorrow,datetime.min.time()),timezone.get_current_timezone())
                source.quota_used=used; source.quota_budget=budget; source.quota_remaining=remaining
                source.quota_kind=provider_budget_kind(source)
                source.quota_consumed=used>0; source.quota_exhausted=remaining<=0
                access_label='API-key provider' if source.quota_kind=='api' else 'Public / no-key provider'
                reset_label=f'{timezone.localtime(reset_at):%d/%m/%Y %H:%M}'
                source.quota_info=(
                    f'Consumed today: {used:,} requests\n'
                    f'Daily cap: {budget:,} requests\n'
                    f'Remaining: {remaining:,} requests\n'
                    f'Applies to: {source.name} · {access_label}\n'
                    f'Resets: {reset_label}'
                )
            except Exception:
                source.quota_used=0; source.quota_budget=0; source.quota_remaining=0; source.quota_kind='public'; source.quota_consumed=False; source.quota_exhausted=False; source.quota_info='Status: Quota telemetry unavailable'
            source.provider_test_job=BackgroundJob.objects.filter(kind='diagnostic',label__startswith=f'Search test: {source.name}').order_by('-created_at').first()
            if source.pk==getattr(searchapi_hub,'pk',None):
                source.searchapi_hub=True
                source.display_name='SearchAPI'
                hub_cfg=dict(source.config_json or {})
                source.searchapi_master_enabled=bool(hub_cfg.get('searchapi_master_enabled',source.enabled))
                source.searchapi_services=searchapi_services
                source.recent_requests=searchapi_requests
                source.recent_errors=searchapi_errors
                source.provider_test_job=BackgroundJob.objects.filter(kind='diagnostic',label__startswith='Search test: SearchAPI').order_by('-created_at').first() or source.provider_test_job
                source.provider_ui=dict(source.provider_ui or {})
                source.provider_ui['api_name']='SearchAPI API'
                source.provider_ui['secret_label']='SearchAPI API key'
                validation_state=str(hub_cfg.get('searchapi_validation_status') or '').strip().lower()
                validation_message=str(hub_cfg.get('searchapi_validation_message') or '').strip()
                configured=bool(source.provider_ui.get('api_configured'))
                if not configured:
                    status_state='unconfigured'; status_label='Not configured'; status_icon='provider_error_v3'; status_class='amber'
                    status_title='SearchAPI API key is not configured.'
                    source_health_state='error'
                elif validation_state=='invalid':
                    status_state='invalid'; status_label='Saved, validation failed'; status_icon='provider_warn_v3'; status_class='amber'
                    status_title=validation_message or 'The saved SearchAPI API key was rejected during validation.'
                    source_health_state='warn'
                elif validation_state=='unavailable':
                    status_state='unavailable'; status_label='Saved, validation unavailable'; status_icon='provider_warn_v3'; status_class='amber'
                    status_title=validation_message or 'The saved SearchAPI API key could not be validated.'
                    source_health_state='warn'
                else:
                    status_state='valid' if validation_state=='valid' else 'configured'
                    status_label='Configured'; status_icon='provider_ok_v3'; status_class='green'
                    status_title=('SearchAPI API key validated successfully.' if validation_state=='valid' else 'SearchAPI API key is configured.')
                    source_health_state='ok'
                source.provider_ui.update({
                    'mode':status_label,
                    'searchapi_validation_state':status_state,
                    'searchapi_validation_label':status_label,
                    'searchapi_validation_icon':status_icon,
                    'searchapi_validation_class':status_class,
                    'searchapi_validation_title':status_title,
                    'health_title':status_title,
                    'health_state':source_health_state,
                    'health_icon':status_icon,
                })
        source.source_category_search=source.category or ''
        display_category={
            'ATS / hosted career pages':'Hosted career pages',
            'Developer / engineering communities':'Developer communities',
            'Excluded / low-value marketplaces':'Low-value marketplaces',
            'Singapore / APAC':'Other Sources',
            'Startup / technology jobs':'Other Sources',
            'SearchAPI Discovery':'Search APIs / SERP',
        }.get(source.category,source.category)
        if source.name.startswith('SearchAPI ·') and source.pk!=getattr(searchapi_hub,'pk',None):
            continue
        if source.pk==getattr(searchapi_hub,'pk',None):
            display_category='Search APIs / SERP'
        categories.setdefault(display_category,[]).append(source)
    for category_items in categories.values():
        category_items.sort(key=lambda item:str(item.name or '').casefold())
    quota_summaries={
        'public':{'used':0,'budget':0,'exhausted':False,'providers':[],'info':'Status: No enabled public/no-key providers use this default.'},
        'api':{'used':0,'budget':0,'exhausted':False,'providers':[],'info':'Status: No enabled API-key providers use this default.'},
    }
    quota_groups_seen=set()
    for source in source_rows:
        if source.name not in ACTIVE_PROVIDER_NAMES or not source.enabled or not getattr(source,'provider_ui',None):
            continue
        cap=provider_capability(source)
        quota_group=str(cap.get('shared_budget_group') or '').strip().lower() or f'source:{source.pk}'
        if quota_group=='searchapi':
            continue
        if quota_group in quota_groups_seen:
            continue
        quota_groups_seen.add(quota_group)
        kind=getattr(source,'quota_kind','public')
        bucket=quota_summaries['api' if kind=='api' else 'public']
        used=int(getattr(source,'quota_used',0) or 0); budget=int(getattr(source,'quota_budget',0) or 0)
        bucket['used']+=used; bucket['budget']+=budget
        provider_label=('SearchAPI shared pool' if quota_group=='searchapi' else source.name)
        bucket['providers'].append((provider_label,used,budget,max(0,budget-used)))
    tomorrow=timezone.localdate()+timedelta(days=1)
    quota_reset=timezone.make_aware(datetime.combine(tomorrow,datetime.min.time()),timezone.get_current_timezone())
    for kind,bucket in quota_summaries.items():
        label='Enabled API-key providers' if kind=='api' else 'Enabled public/no-key providers'
        remaining=max(0,int(bucket['budget'])-int(bucket['used']))
        bucket['remaining']=remaining
        bucket['exhausted']=bool(bucket['budget'] and bucket['used']>=bucket['budget'])
        bucket['state']=_quota_pressure_state(bucket['used'],bucket['budget'])
        if bucket['budget']:
            lines=[
                f"Used today: {bucket['used']:,} requests",
                f"Daily capacity: {bucket['budget']:,} requests",
                f"Remaining: {remaining:,} requests",
                f"Applies to: {label}",
                f"Resets: {timezone.localtime(quota_reset):%d/%m/%Y %H:%M}",
            ]
            for name,used,budget,provider_remaining in bucket.get('providers') or []:
                lines.append(f"{name}: {used:,} / {budget:,} used · {provider_remaining:,} remaining")
            bucket['info']='\n'.join(lines)
        else:
            bucket['info']=f'Status: No {label.lower()} currently use this default.'
    cloud_quota_summaries={}
    try:
        cloud_usage=cloud_today_usage(); cloud_limits=cloud_usage.get('limits') or {}
        cloud_quota_map={
            'cloud_daily_requests':('requests','daily_requests','Cloud AI requests'),
            'cloud_daily_web_searches':('web_searches','daily_web_searches','AI Web Search Queries'),
            'cloud_daily_input_tokens':('tokens_in','daily_input_tokens','Cloud input tokens'),
            'cloud_daily_output_tokens':('tokens_out_reasoning','daily_output_tokens','Cloud output + reasoning tokens'),
            'cloud_passive_enrichment_per_day':('passive_enrichment','passive_enrichment','Passive enrichment'),
            'cloud_page_recovery_per_day':('page_recovery','page_recovery','Page-view recovery'),
        }
        for field,(used_key,limit_key,label) in cloud_quota_map.items():
            used=int(cloud_usage.get(used_key) or 0); limit=int(cloud_limits.get(limit_key) or getattr(ps,field,0) or 0)
            remaining=max(0,limit-used) if limit else 0
            cloud_quota_summaries[field]={
                'used':used,'limit':limit,'remaining':remaining,'exhausted':bool(limit and used>=limit),'state':_quota_pressure_state(used,limit),
                'info':(
                    f'Used today: {used:,}\n'
                    f'Daily limit: {limit:,}\n'
                    f'Remaining: {remaining:,}\n'
                    f'Metric: {label}\n'
                    f'Resets: {timezone.localtime(quota_reset):%d/%m/%Y %H:%M}'
                ) if limit else f'Metric: {label}\nStatus: No active daily limit.',
            }
    except Exception:
        cloud_quota_summaries={}
    searchapi_quota_summary={'used':0,'limit':int(getattr(ps,'searchapi_daily_limit',500) or 0),'remaining':0,'state':'unused','info':'SearchAPI quota telemetry unavailable.','breakdown':[]}
    try:
        sap=searchapi_hub or SearchSource.objects.filter(name__startswith='SearchAPI ·').first()
        sap_used=provider_budget_used(sap) if sap else 0
        sap_limit=max(0,min(10000,int(getattr(ps,'searchapi_daily_limit',500))))
        sap_remaining=max(0,sap_limit-sap_used)
        breakdown=[]
        today=timezone.localdate()
        for code,name in SEARCHAPI_SERVICE_SOURCES.items():
            child=SearchSource.objects.filter(name=name).first()
            if not child: continue
            st=SearchProviderStat.objects.filter(source=child,day=today).first()
            used=int(getattr(st,'requests',0) or 0)
            if used: breakdown.append((SEARCHAPI_SHORT_LABELS.get(code,code),used))
        lines=[f'Used today: {sap_used:,} requests',f'Daily limit: {sap_limit:,} requests',f'Remaining: {sap_remaining:,} requests',f'Resets: {timezone.localtime(quota_reset):%d/%m/%Y %H:%M}']
        for label,used in breakdown: lines.append(f'{label}: {used:,} request{"" if used==1 else "s"}')
        searchapi_quota_summary={'used':sap_used,'limit':sap_limit,'remaining':sap_remaining,'state':_quota_pressure_state(sap_used,sap_limit),'info':'\n'.join(lines),'breakdown':breakdown}
    except Exception:
        pass
    try: stats=list(SearchProviderStat.objects.filter(day=timezone.localdate()).select_related('source').order_by('-requests'))
    except Exception: stats=[]
    try:
        market_settings=PortalSettings.objects.get_or_create(pk=1)[0]
        enabled_market_codes=set(market_settings.discovery_markets or DEFAULT_MARKET_CODES)
        display_markets=sorted(MARKETS,key=lambda m:(m.code=='worldwide',m.name.casefold()))
        discovery_markets=[{'code':m.code,'name':m.name,'flag':m.flag,'enabled':m.code in enabled_market_codes} for m in display_markets]
        multilingual_auto_languages=auto_multilingual_languages(market_settings)
        multilingual_language_options=[{'name':name,'flag':flag} for name,flag in sorted(MULTILINGUAL_LANGUAGE_OPTIONS,key=lambda row:row[0].casefold())]
    except Exception:
        market_settings=PortalSettings(); discovery_markets=[]; multilingual_auto_languages=[]; multilingual_language_options=[]
    try: custom_domains=list(CustomSearchDomain.objects.all().order_by('name','domain'))
    except Exception: custom_domains=[]
    try: facebook_pages=list(FacebookPage.objects.all())
    except Exception: facebook_pages=[]
    try: forum_sources=list(SearchSource.objects.filter(source_type='forum').order_by('name'))
    except Exception: forum_sources=[]
    for source in forum_sources:
        cfg=source.config_json if isinstance(source.config_json,dict) else {}
        source.direct_adapter=str(cfg.get('direct_adapter') or '').strip()
        source.discovery_capability=str(cfg.get('discovery_capability') or 'Forum native search · indexed fallback').strip()
        source.forum_software=str(cfg.get('forum_software') or '').strip()
        source.openable_url=(source.base_url or '') if source.base_url and 'example.invalid' not in source.base_url else ''
        health=_forum_source_health(source)
        source.forum_health_state=health.get('state','idle')
        source.forum_health_icon=health.get('icon','provider_idle_ready_v3')
        source.forum_health_title=health.get('title','Forum status unavailable')
    return render(request,'portal/sources.html',ctx(request,'settings','Search Sources',system_tab='sources',categories=categories,provider_stats=stats,facebook=fb,facebook_pages=facebook_pages,provider_test=provider_test,discovery_markets=discovery_markets,market_settings=market_settings,multilingual_auto_languages=multilingual_auto_languages,multilingual_language_options=multilingual_language_options,custom_domains=custom_domains,forum_sources=forum_sources,source_load_error=source_load_error,quota_summaries=quota_summaries,cloud_quota_summaries=cloud_quota_summaries,searchapi_quota_summary=searchapi_quota_summary))


@login_required
def sources_view(request):
    """Render Search Sources without allowing diagnostics/catalog drift to produce HTTP 500.

    Search Sources is itself the debugging/configuration screen.  Older upgraded databases
    or a single malformed provider row must not make it inaccessible.  The normal view is
    attempted first; GET failures fall back to a deliberately simple configuration page
    that uses only long-established columns.  POST failures are surfaced as a message and
    redirected instead of returning a server error.
    """
    try:
        return _sources_view_impl(request)
    except Exception as exc:
        logger.exception('Search Sources page failed; using safe fallback')
        if request.method == 'POST':
            messages.error(request, f'Search Sources could not complete that action: {str(exc)[:240]}')
            return redirect('sources')
        try:
            ps=PortalSettings.objects.get_or_create(pk=1)[0]
            safe_rows=[]
            try:
                values=SearchSource.objects.exclude(source_type='cloud_ai').order_by('category','name').values('pk','category','name','enabled','base_url','low_value_marketplace','source_type')
                for row in values:
                    base=(row.get('base_url') or '').strip()
                    row['openable_url']=base if base and 'example.invalid' not in base else ''
                    safe_rows.append(row)
            except Exception:
                safe_rows=[]
            try:
                fb=FacebookConfig.objects.filter(pk=1).first()
            except Exception:
                fb=None
            data=ctx(request,'settings','Search Sources',system_tab='sources',safe_sources=safe_rows,source_page_error=str(exc)[:600],facebook=fb)
            return render(request,'portal/sources_recovery.html',data)
        except Exception as fallback_exc:
            logger.exception('Search Sources safe fallback also failed')
            # Last-resort response intentionally avoids template/model dependencies so
            # /sources/ remains reachable and reports the actionable error rather than 500.
            msg=html.escape(str(exc)[:600]); fallback=html.escape(str(fallback_exc)[:300])
            return HttpResponse(
                '<!doctype html><html><head><meta charset="utf-8"><title>ScoutBox · Search Sources</title></head>'
                '<body style="font-family:system-ui;background:#07111c;color:#dbe9f2;padding:32px">'
                '<h1>Search Sources</h1><p>ScoutBox kept this configuration route available, but provider diagnostics could not be rendered.</p>'
                f'<pre style="white-space:pre-wrap">{msg}\n{fallback}</pre><p><a style="color:#77d9ff" href="/">Go to Dashboard</a></p></body></html>',
                status=200,
            )


@login_required
def facebook_pages_view(request):
    """Standalone Facebook Pages watch list with review and recycle semantics."""
    if request.method=='POST':
        action=(request.POST.get('action') or '').strip()
        ids=[int(x) for x in request.POST.getlist('facebook_page_ids') if str(x).isdigit()]
        wants_json=request.headers.get('X-Requested-With')=='fetch'
        if action in {'mark_seen','mark_new'}:
            seen=action=='mark_seen'
            count=FacebookPage.objects.filter(pk__in=ids,deleted_at__isnull=True).update(is_read=seen)
            if wants_json: return JsonResponse({'ok':True,'updated':count,'is_read':seen})
            messages.success(request,f'Marked {count} Facebook Page{("" if count==1 else "s")} as {"Seen" if seen else "New"}.')
        elif action=='delete_selected':
            count=FacebookPage.objects.filter(pk__in=ids,deleted_at__isnull=True).update(deleted_at=timezone.now(),is_read=True,enabled=False)
            messages.success(request,f'Moved {count} Facebook Page{("" if count==1 else "s")} to the Recycle Bin.')
        elif action=='restore_selected':
            count=FacebookPage.objects.filter(pk__in=ids,deleted_at__isnull=False).update(deleted_at=None,is_read=True,enabled=True)
            messages.success(request,f'Restored {count} Facebook Page{("" if count==1 else "s")}.')
        elif action=='save':
            row_id=(request.POST.get('row_id') or '').strip(); page_id=(request.POST.get('page_id') or '').strip().strip('/')
            evidence_text=' '.join((request.POST.get('evidence_text') or '').split())[:8000]
            evidence_url=(request.POST.get('evidence_url') or '').strip()[:1000]
            if not page_id:
                messages.error(request,'Page ID is required.')
            elif FacebookPage.objects.exclude(pk=int(row_id) if row_id.isdigit() else None).filter(page_id__iexact=page_id,deleted_at__isnull=True).exists():
                messages.error(request,'That Facebook Page is already being watched.')
            else:
                page_url=f'https://www.facebook.com/{page_id}'
                relevant,reason,_direct,page_title=facebook_page_relevant(page_url,evidence_text,evidence_text,direct=True)
                if not relevant:
                    messages.error(request,'Page was not saved: '+reason+'.')
                else:
                    row=FacebookPage.objects.filter(pk=int(row_id)).first() if row_id.isdigit() else FacebookPage()
                    row.page_id=page_id[:120]; row.page_url=page_url[:1000]; row.page_title=(page_title or '')[:300]
                    row.evidence_text=evidence_text; row.evidence_url=evidence_url; row.enabled=True; row.is_read=True; row.deleted_at=None
                    row.validation_state=('verified' if page_title and reason.startswith('direct Page-owned') else ('indexed' if page_title else 'pending'))
                    row.validation_reason=(reason[:500] if page_title else 'Page-title validation queued for automatic retries.')
                    row.validated_at=timezone.now(); row.title_retry_count=0; row.title_retry_started_at=(None if page_title else timezone.now()); row.save()
                    if not page_title:
                        try: facebook_page_title_tick.delay(1)
                        except Exception: logger.exception('Unable to queue Facebook Page title resolution for page %s',row.pk)
                    messages.success(request,'Facebook Page saved.')
        return redirect('facebook_pages')

    q=_q(request); read_state=(request.GET.get('read') or '').strip().lower(); show_deleted=request.GET.get('show_deleted')=='1'
    base=FacebookPage.objects.all() if show_deleted else FacebookPage.objects.filter(deleted_at__isnull=True)
    active=FacebookPage.objects.filter(deleted_at__isnull=True)
    read_counts={'total':active.count(),'new':active.filter(is_read=False).count(),'seen':active.filter(is_read=True).count()}
    # Do not make users wait for the periodic beat after upgrading or opening the list.
    # A short cache gate keeps this opportunistic repair bounded across concurrent views.
    if active.filter(page_title='').exists() and cache.add('facebook-page-title-refresh',True,timeout=120):
        try: facebook_page_title_tick.delay(8)
        except Exception: logger.exception('Unable to queue Facebook Page title repair')
    if read_state=='new': base=base.filter(is_read=False)
    elif read_state=='seen': base=base.filter(is_read=True)
    else: read_state=''
    if q: base=base.filter(Q(page_id__icontains=q)|Q(page_title__icontains=q)|Q(evidence_text__icontains=q)|Q(evidence_url__icontains=q))
    sort_mode=(request.GET.get('sort') or '').strip().lower()
    sort_orders={
        'page_id_asc':('page_id','pk'),'page_id_desc':('-page_id','-pk'),
        'title_asc':('page_title','page_id','pk'),'title_desc':('-page_title','page_id','pk'),
        'evidence_asc':('evidence_text','page_id','pk'),'evidence_desc':('-evidence_text','page_id','pk'),
        'added_asc':('discovered_at','pk'),'added_desc':('-discovered_at','-pk'),
    }
    if sort_mode not in sort_orders: sort_mode=''
    ordered=base.order_by(*(sort_orders.get(sort_mode) or ('-discovered_at','-pk')))
    if request.GET.get('export')=='1':
        return _xlsx('facebook_pages.xlsx',['Page ID','Page Title','Discovery Evidence','Evidence URL','Page URL','State','Added'],[(x.page_id,x.page_title,x.evidence_text,x.evidence_url,x.page_url,'Deleted' if x.deleted_at else ('Seen' if x.is_read else 'New'),x.discovered_at) for x in ordered[:10000]])
    try: per_page=int(request.GET.get('per_page') or 25)
    except Exception: per_page=25
    if per_page not in (10,25,50,100): per_page=25
    page=Paginator(ordered,per_page).get_page(request.GET.get('page') or 1)
    for row in page.object_list:
        row.title_validation_pending=bool(not row.page_title and row.validation_state not in {'unavailable','failed'})
        if not row.page_title:
            row.title_validation_message=(row.validation_reason or ('Page-title validation will retry automatically.' if row.title_validation_pending else 'Page title is unavailable.'))[:500]
    return render(request,'portal/facebook_pages.html',ctx(request,'facebook_pages','Facebook Pages',pages=page,page_obj=page,q=q,read_state=read_state,read_counts=read_counts,show_deleted=show_deleted,per_page=per_page,sort_mode=sort_mode))


def _split_selected(value):
    return [x.strip() for x in re.split(r'[,;\n|]+',value or '') if x.strip()]


def _campaign_form_from(obj=None):
    if not obj:
        profile=Profile.objects.get_or_create(pk=1)[0]
        return {'name':'','template':'','locations':profile.operating_locations or ([profile.operating_location] if profile.operating_location else ['Singapore']),'roles':[],'tech':[],'engagement':[],'sizes':[],'languages':[],'negative_constraints':'','extra_text':'','recency_days':30,'source_names':[],'queries_per_rotation':''}
    if isinstance(obj,CampaignTemplate):
        return {'name':'','template':obj.name,'locations':obj.locations,'roles':obj.role_families,'tech':obj.technologies,'engagement':obj.engagement_types,'sizes':obj.company_sizes,'languages':obj.languages,'negative_constraints':obj.negative_constraints,'extra_text':obj.extra_text,'recency_days':obj.recency_days,'source_names':obj.source_names,'queries_per_rotation':obj.queries_per_rotation or ''}
    return {'name':obj.name,'template':obj.template,'locations':obj.locations or ([obj.location] if obj.location else []),'roles':_split_selected(obj.role_families),'tech':_split_selected(obj.technologies),'engagement':_split_selected(obj.engagement_types),'sizes':_split_selected(obj.company_sizes),'languages':_split_selected(obj.languages),'negative_constraints':obj.negative_constraints,'extra_text':obj.extra_text,'recency_days':obj.recency_days,'source_names':obj.source_names,'queries_per_rotation':obj.queries_per_rotation or ''}


def _save_campaign_fields(obj, request, prefix=''):
    locations=[x for x in request.POST.getlist(prefix+'locations') if x in COUNTRIES]
    obj.locations=locations; obj.location=(locations[0] if locations else '')
    obj.role_families=_picked(request,prefix+'role_choice',request.POST.get(prefix+'role_advanced',''))
    obj.technologies=_picked(request,prefix+'tech_choice',request.POST.get(prefix+'tech_advanced',''))
    obj.engagement_types=_picked(request,prefix+'engagement_choice')
    obj.company_sizes=_picked(request,prefix+'size_choice')
    obj.languages=_picked(request,prefix+'language_choice')
    obj.negative_constraints=request.POST.get(prefix+'negative_constraints','').strip()
    obj.extra_text=request.POST.get(prefix+'extra_text','').strip()
    try: obj.recency_days=max(1,min(3650,int(request.POST.get(prefix+'recency_days') or 30)))
    except Exception: obj.recency_days=30
    obj.source_names=request.POST.getlist(prefix+'source_name')
    raw=request.POST.get(prefix+'queries_per_rotation','').strip()
    obj.queries_per_rotation=max(1,min(100,int(raw))) if raw.isdigit() else None
    return obj


def _template_payload():
    return [{'id':t.pk,'name':t.name,'description':t.description,'locations':t.locations,'roles':t.role_families,'tech':t.technologies,'engagement':t.engagement_types,'sizes':t.company_sizes,'languages':t.languages,'negative_constraints':t.negative_constraints,'extra_text':t.extra_text,'recency_days':t.recency_days,'source_names':t.source_names,'queries_per_rotation':t.queries_per_rotation} for t in CampaignTemplate.objects.filter(deleted_at__isnull=True)]


def _daily_campaign_run_rows(runs):
    # Run History is grouped by campaign/day. Token usage is attributed from the
    # same UsageMetric rows that power Resource Usage, so local/cloud totals stay
    # aligned with the provider that actually executed each request. Input, output,
    # and reasoning tokens are additive; cached-token metadata is informational and
    # is not added again because it is a subset of provider-reported input usage.
    runs=list(runs)
    groups={}
    for run in runs:
        stamp=run.started_at or run.created_at
        local=timezone.localtime(stamp) if stamp else timezone.localtime(timezone.now())
        key=(run.campaign_id,local.date())
        row=groups.get(key)
        result=run.result or {}
        if row is None:
            row={'campaign':run.campaign,'date':local.date(),'first_run':stamp,'last_run':run.finished_at or stamp,'run_count':0,'opportunities':0,'leads':0,'local_tokens':0,'cloud_tokens':0,'failed':0,'stopped':0,'latest_run':run,'cloud_urls':0,'cloud_verified':0,'cloud_leads_qualified':0,'cloud_leads_rejected':0,'cloud_contacts_validated':0,'cloud_contacts_rejected':0,'cloud_rejections':{},'source_queries':0,'source_urls':0,'source_verified':0,'source_leads':0}
            groups[key]=row
        row['run_count']+=1
        row['opportunities']+=int(result.get('new_opportunities') if result.get('new_opportunities') is not None else (result.get('unique') or 0))
        row['leads']+=int(result.get('new_leads') or 0)
        row['cloud_urls']+=int(result.get('cloud_urls_returned') or 0)
        row['cloud_verified']+=int(result.get('cloud_verified_candidates') or 0)
        row['cloud_leads_qualified']+=int(result.get('cloud_hidden_leads_qualified') or 0)
        row['cloud_leads_rejected']+=int(result.get('cloud_hidden_leads_rejected') or 0)
        row['cloud_contacts_validated']+=int(result.get('cloud_contacts_validated') or 0)
        row['cloud_contacts_rejected']+=int(result.get('cloud_contacts_rejected') or 0)
        if str(result.get('discovery_mode') or '').lower()=='source_guided':
            row['source_queries']+=len(result.get('queries') or [])
            row['source_urls']+=int(result.get('raw_hits') or 0)
            row['source_verified']+=int(result.get('consolidated_hits') or 0)
            row['source_leads']+=int(result.get('new_leads') or 0)
        for reason,count in (result.get('cloud_persistence_rejections') or {}).items():
            row['cloud_rejections'][str(reason)]=int(row['cloud_rejections'].get(str(reason)) or 0)+int(count or 0)
        if stamp and (not row['first_run'] or stamp<row['first_run']): row['first_run']=stamp
        end=run.finished_at or stamp
        if end and (not row['last_run'] or end>row['last_run']): row['last_run']=end
        if run.created_at and run.created_at>row['latest_run'].created_at: row['latest_run']=run
        if run.status=='failed': row['failed']+=1
        if run.status=='stopped': row['stopped']+=1

    # Add per-day AI token totals after the run grouping so UsageMetric is queried
    # once for all visible campaign rows instead of once per run. metadata.campaign_id
    # is written by both Ollama and Cloud AI paths inside the campaign usage context.
    if groups:
        campaign_ids={int(key[0]) for key in groups if key[0] is not None}
        dates=[key[1] for key in groups]
        usage_q=UsageMetric.objects.filter(metadata__campaign_id__in=list(campaign_ids))
        if dates:
            first_day=min(dates); last_day=max(dates)
            day_start=timezone.make_aware(datetime.combine(first_day, datetime.min.time())) if timezone.is_naive(datetime.combine(first_day, datetime.min.time())) else datetime.combine(first_day, datetime.min.time())
            day_end=timezone.make_aware(datetime.combine(last_day + timedelta(days=1), datetime.min.time())) if timezone.is_naive(datetime.combine(last_day + timedelta(days=1), datetime.min.time())) else datetime.combine(last_day + timedelta(days=1), datetime.min.time())
            usage_q=usage_q.filter(at__gte=day_start,at__lt=day_end)
        for metric in usage_q.only('at','provider','tokens_in','tokens_out','reasoning_tokens','metadata'):
            meta=metric.metadata or {}
            try: campaign_id=int(meta.get('campaign_id'))
            except Exception: continue
            try: metric_day=timezone.localtime(metric.at).date()
            except Exception: metric_day=metric.at.date()
            row=groups.get((campaign_id,metric_day))
            if row is None: continue
            total=max(0,int(metric.tokens_in or 0))+max(0,int(metric.tokens_out or 0))+max(0,int(metric.reasoning_tokens or 0))
            if is_cloud_provider(metric.provider): row['cloud_tokens']+=total
            else: row['local_tokens']+=total

    rows=list(groups.values())
    for row in rows:
        latest=row.get('latest_run')
        row['run_context_meta']=describe_run_context((latest.criteria if latest else {}))
        row['run_context']=row['run_context_meta'].get('display','')
        latest_result=(latest.result or {}) if latest else {}
        row['execution_path']=str(latest_result.get('execution_path') or ('Cloud Web' if (latest.criteria or {}).get('discovery_mode')=='cloud_web' else 'Local AI Discovery') if latest else '')
        row['cloud_rejection_text']=' · '.join(f'{name.replace("_"," ")} {count}' for name,count in sorted(row.get('cloud_rejections',{}).items(), key=lambda kv:(-kv[1],kv[0]))[:4])
        if row['failed']:
            if row['failed']==row['run_count']:
                row['status']='Failed'; row['status_key']='failed'
            else:
                row['status']='Completed with errors'; row['status_key']='warning'
        elif row['stopped']:
            if row['stopped']==row['run_count']:
                row['status']='Stopped'; row['status_key']='stopped'
            else:
                row['status']='Completed / stopped'; row['status_key']='stopped_partial'
        else:
            row['status']='Completed'; row['status_key']='completed'
    rows.sort(key=lambda r:(r['date'],r['last_run'] or r['first_run']),reverse=True)
    return rows


def _brief_elapsed_since(start, now=None):
    """Compact elapsed time for Campaign list status text."""
    if not start:
        return ''
    now=now or timezone.now()
    try:
        seconds=max(0,int((now-start).total_seconds()))
    except Exception:
        return ''
    if seconds < 60:
        return '<1 min'
    minutes=seconds//60
    if minutes < 60:
        return f'{minutes} min'
    hours=minutes//60
    if hours < 24:
        rem=minutes%60
        return f'{hours} hr' + (f' {rem} min' if rem else '')
    days=hours//24
    rem=hours%24
    return f'{days}d' + (f' {rem}h' if rem else '')


def _brief_since_label(dt, now=None):
    if not dt:
        return ''
    now=now or timezone.now()
    local_dt=timezone.localtime(dt)
    local_now=timezone.localtime(now)
    if local_dt.date()==local_now.date():
        return local_dt.strftime('%H:%M')
    return local_dt.strftime('%d/%m %H:%M')




@login_required
def campaigns_view(request):
    if request.method=='POST':
        action=request.POST.get('action','create_campaign')
        if action=='restore_row':
            row_id=(request.POST.get('row_id') or '').strip()
            item_type=(request.POST.get('item_type') or 'campaign').strip()
            if item_type not in {'campaign','campaign_template'}:
                item_type='campaign'
            ok,label=_restore_recycle_item(item_type,int(row_id)) if row_id.isdigit() else (False,'Campaign Template' if item_type=='campaign_template' else 'Campaign')
            label_word='campaign template' if item_type=='campaign_template' else 'campaign'
            if request.headers.get('X-Requested-With')=='fetch':
                return JsonResponse({'ok':ok,'label':label,'error':'' if ok else f'This {label_word} is not in the Recycle Bin.'},status=200 if ok else 404)
            (messages.success if ok else messages.warning)(request,(f'Restored {label}.' if ok else f'This {label_word} is not in the Recycle Bin.'))
            return redirect(request.get_full_path())
        if action=='delete_selected':
            ids=[x for x in request.POST.getlist('campaign_ids') if str(x).isdigit()]
            if not ids:
                messages.error(request,'Select at least one campaign to delete.')
            else:
                selected=Campaign.objects.filter(pk__in=ids,deleted_at__isnull=True)
                already_deleted=Campaign.objects.filter(pk__in=ids,deleted_at__isnull=False).count()
                if not selected.exists():
                    messages.info(request,f'{already_deleted or len(ids)} selected campaign{" is" if (already_deleted or len(ids)) == 1 else "s are"} already in the Recycle Bin.')
                else:
                    active=CampaignRun.objects.filter(campaign_id__in=selected.values_list('pk',flat=True),status__in=['queued','running','stopping']).select_related('campaign')
                    enabled=selected.filter(enabled=True)
                    if active.exists() or enabled.exists():
                        blocked=list(dict.fromkeys([x.campaign.name for x in active[:6]]+list(enabled.values_list('name',flat=True)[:6])))
                        messages.error(request,f'Only paused campaigns can be deleted. Pause/disable first: {", ".join(blocked)}.')
                    else:
                        count=selected.count(); now=timezone.now()
                        selected.update(enabled=False,deleted_at=now)
                        suffix=(f' {already_deleted} selected campaign{" is" if already_deleted == 1 else "s are"} already in the Recycle Bin and were ignored.' if already_deleted else '')
                        messages.success(request,f'Moved {count} selected campaign{"" if count == 1 else "s"} to the Recycle Bin.'+suffix)
            return redirect('campaigns')
        elif action in ('pause_campaign','enable_campaign'):
            c=get_object_or_404(Campaign,pk=request.POST.get('campaign_id'),deleted_at__isnull=True)
            if action=='pause_campaign':
                c.enabled=False; c.save(update_fields=['enabled','updated_at'])
                active=CampaignRun.objects.filter(campaign=c,status__in=['queued','running']).order_by('-created_at').first()
                if active:
                    active.status='stopping'; active.message='Pause requested'; active.result={**(active.result or {}),'stop_requested_at':timezone.now().isoformat()}; active.save(update_fields=['status','message','result'])
                    messages.success(request,f'{c.name} paused. The active run will stop at the next safe checkpoint.')
                else:
                    messages.success(request,f'{c.name} paused. Scheduled runs are disabled.')
            else:
                if CampaignRun.objects.filter(campaign=c,status='stopping').exists():
                    messages.warning(request,f'{c.name} is still stopping. Wait for the active run to finish before resuming scheduled runs.')
                else:
                    c.enabled=True; c.save(update_fields=['enabled','updated_at'])
                    messages.success(request,f'{c.name} enabled. Scheduled runs are active.')
            return redirect('campaigns')
        elif action=='template_delete_selected':
            ids=[x for x in request.POST.getlist('template_ids') if str(x).isdigit()]
            if not ids:
                messages.error(request,'Select at least one campaign template to delete.')
            else:
                qs=CampaignTemplate.objects.filter(pk__in=ids,deleted_at__isnull=True)
                count=qs.count()
                qs.update(deleted_at=timezone.now())
                already_deleted=max(0,len(ids)-count)
                suffix=(f' {already_deleted} selected template{" is" if already_deleted == 1 else "s are"} already in the Recycle Bin and were ignored.' if already_deleted else '')
                messages.success(request,f'Moved {count} selected campaign template{"" if count == 1 else "s"} to the Recycle Bin. Existing campaigns were not changed.'+suffix)
            return redirect(reverse('campaigns')+'#campaign-templates')
        elif action=='create_campaign':
            name=request.POST.get('name','').strip()
            if not name:
                messages.error(request,'Campaign name is required. Enter a name before creating the campaign.')
            elif len(name)<3:
                messages.error(request,'Campaign name must be at least 3 characters.')
            elif Campaign.objects.filter(name=name).exists():
                messages.error(request,'A campaign with that name already exists, including items in the Recycle Bin.')
            else:
                c=Campaign(name=name,template=request.POST.get('template','').strip(),enabled=bool(request.POST.get('enabled')))
                _save_campaign_fields(c,request); c.save(); messages.success(request,'Campaign created.'); return redirect('campaign_detail',pk=c.pk)
        elif action in ('template_create','template_update'):
            t=CampaignTemplate.objects.filter(pk=request.POST.get('template_id'),deleted_at__isnull=True).first() if action=='template_update' else CampaignTemplate()
            if t is None: messages.error(request,'Template not found.')
            else:
                name=request.POST.get('template_name','').strip()
                if not name: messages.error(request,'Template name is required.')
                elif CampaignTemplate.objects.exclude(pk=t.pk).filter(name=name).exists(): messages.error(request,'A template with that name already exists, including items in the Recycle Bin.')
                else:
                    t.name=name; t.description=request.POST.get('template_description','').strip(); t.built_in=False
                    t.locations=[x for x in request.POST.getlist('tpl_locations') if x in COUNTRIES]
                    t.role_families=request.POST.getlist('tpl_role_choice'); t.technologies=request.POST.getlist('tpl_tech_choice'); t.engagement_types=request.POST.getlist('tpl_engagement_choice'); t.company_sizes=request.POST.getlist('tpl_size_choice'); t.languages=request.POST.getlist('tpl_language_choice')
                    t.negative_constraints=request.POST.get('tpl_negative_constraints','').strip(); t.extra_text=request.POST.get('tpl_extra_text','').strip(); t.source_names=request.POST.getlist('tpl_source_name')
                    try: t.recency_days=max(1,min(3650,int(request.POST.get('tpl_recency_days') or 30)))
                    except Exception: t.recency_days=30
                    raw=request.POST.get('tpl_queries_per_rotation','').strip(); t.queries_per_rotation=max(1,min(100,int(raw))) if raw.isdigit() else None
                    t.save(); messages.success(request,'Campaign template saved.'); return redirect('campaigns')
        elif action=='template_duplicate':
            src=get_object_or_404(CampaignTemplate,pk=request.POST.get('template_id'),deleted_at__isnull=True)
            base=f'{src.name} copy'; name=base; n=2
            while CampaignTemplate.objects.filter(name=name).exists():
                name=f'{base} {n}'; n+=1
            clone=CampaignTemplate.objects.create(
                name=name, description=src.description, built_in=False,
                locations=list(src.locations or []), role_families=list(src.role_families or []),
                technologies=list(src.technologies or []), engagement_types=list(src.engagement_types or []),
                company_sizes=list(src.company_sizes or []), languages=list(src.languages or []),
                negative_constraints=src.negative_constraints, extra_text=src.extra_text,
                recency_days=src.recency_days, source_names=list(src.source_names or []),
                queries_per_rotation=src.queries_per_rotation,
            )
            messages.success(request,f'Template duplicated as {clone.name}.')
            return redirect(f'{reverse("campaigns")}?edit_template={clone.pk}#campaign-templates')
        elif action=='template_delete':
            t=get_object_or_404(CampaignTemplate,pk=request.POST.get('template_id'),deleted_at__isnull=True)
            name=t.name; t.deleted_at=timezone.now(); t.save(update_fields=['deleted_at','updated_at'])
            messages.success(request,f'Moved campaign template to the Recycle Bin: {name}. Existing campaigns were not changed.')
            return redirect(reverse('campaigns')+'#campaign-templates')
    q=_q(request); show_deleted=_show_deleted_setting(request,'campaigns'); show_deleted_templates=_show_deleted_setting(request,'templates'); qs=(Campaign.objects.all() if show_deleted else Campaign.objects.filter(deleted_at__isnull=True)).order_by('-updated_at')
    if q: qs=qs.filter(Q(name__icontains=q)|Q(template__icontains=q)|Q(technologies__icontains=q)|Q(role_families__icontains=q))
    campaign_rows=list(qs)
    schedule_settings=PortalSettings.objects.get_or_create(pk=1)[0]
    now_for_status=timezone.now()
    for c in campaign_rows:
        c.display_changed_at=max(x for x in (c.created_at,c.updated_at,c.deleted_at) if x is not None)
        c.ui_opportunities=c.opportunities.filter(suppressed=False,user_deleted=False).count()
        c.ui_leads=c.leads.filter(user_deleted=False).count()
        c.ui_status_detail=''
        if c.deleted_at:
            c.next_run_at=None
            c.ui_run_context_meta={'display':'','icon':'','note_only':False}
            c.ui_run_context=''
            c.ui_run_status='deleted'
            active=None
            latest=CampaignRun.objects.filter(campaign=c).order_by('-created_at').first()
        else:
            c.next_run_at=_campaign_next_run(c,schedule_settings)
            active=CampaignRun.objects.filter(campaign=c,status__in=['queued','running','stopping']).order_by('-created_at').first()
            latest=active or CampaignRun.objects.filter(campaign=c).order_by('-created_at').first()
            c.ui_run_context_meta=describe_run_context(latest.criteria if latest else {})
            c.ui_run_context=c.ui_run_context_meta.get('display','')
            c.ui_run_status=(active.status if active else ('scheduled' if c.enabled else 'paused'))
        if active:
            stamp=active.started_at or active.created_at
            since=_brief_since_label(stamp,now_for_status)
            if active.status=='running':
                elapsed=_brief_elapsed_since(stamp,now_for_status)
                c.ui_status_detail=(f'For {elapsed} · since {since}' if elapsed and since else (f'Since {since}' if since else 'Running'))
            elif active.status=='queued':
                c.ui_status_detail=(f'Queued since {since}' if since else 'Queued')
            elif active.status=='stopping':
                c.ui_status_detail=(f'Stopping since {since}' if since else 'Stopping')
        
    export_kind=(request.GET.get('export') or '').strip().lower()
    if export_kind=='1':
        return _xlsx('campaigns.xlsx',['Name','Enabled','Location','Roles','Technologies','Engagement','Opportunities','Leads','Recency days','Created','Last Run','Next Run','Updated'],[(c.name,c.enabled,c.location,c.role_families,c.technologies,c.engagement_types,c.ui_opportunities,c.ui_leads,c.recency_days,c.created_at,c.last_run or '',_campaign_next_run(c,schedule_settings) or '',c.updated_at) for c in campaign_rows[:5000]])
    if export_kind=='templates':
        tqs=(CampaignTemplate.objects.all() if show_deleted_templates else CampaignTemplate.objects.filter(deleted_at__isnull=True)).order_by('name')
        return _xlsx('campaign_templates.xlsx',['Name','Description','Locations','Roles','Technologies','Engagement','Company sizes','Languages','Recency days','Sources','Built in'],[(t.name,t.description,', '.join(t.locations or []),', '.join(t.role_families or []),', '.join(t.technologies or []),', '.join(t.engagement_types or []),', '.join(t.company_sizes or []),', '.join(t.languages or []),t.recency_days,', '.join(t.source_names or []),t.built_in) for t in tqs[:5000]])
    from_campaign=Campaign.objects.filter(pk=request.GET.get('from_campaign'),deleted_at__isnull=True).first()
    template_key=(request.GET.get('template') or '').strip()
    use_cv_discovery=(template_key == CV_DISCOVERY_TEMPLATE_KEY)
    from_template=CampaignTemplate.objects.filter(pk=template_key,deleted_at__isnull=True).first() if template_key.isdigit() else None
    from_run=CampaignRun.objects.select_related('campaign').filter(pk=request.GET.get('from_run')).first()
    if from_run and from_run.criteria:
        form=dict(from_run.criteria)
        form.setdefault('roles',form.pop('role_families',[]) if isinstance(form.get('role_families'),list) else _split_selected(form.get('role_families','')))
        form.setdefault('tech',form.pop('technologies',[]) if isinstance(form.get('technologies'),list) else _split_selected(form.get('technologies','')))
        form.setdefault('engagement',form.pop('engagement_types',[]) if isinstance(form.get('engagement_types'),list) else _split_selected(form.get('engagement_types','')))
        form.setdefault('sizes',form.pop('company_sizes',[]) if isinstance(form.get('company_sizes'),list) else _split_selected(form.get('company_sizes','')))
        form.setdefault('languages',[])
        form.setdefault('locations',[])
        form.setdefault('source_names',[])
        form['name']=''
    else:
        form=_cv_discovery_campaign_form() if use_cv_discovery else _campaign_form_from(from_campaign or from_template)
        if from_campaign:
            form['name']=''
        elif use_cv_discovery or from_template:
            base_name=(CV_DISCOVERY_TEMPLATE_NAME if use_cv_discovery else from_template.name).strip()[:135]
            prefix=timezone.localtime(timezone.now()).strftime('%d%b-%H%M').upper()
            candidate=f'[{prefix}] - {base_name}'[:160]; suffix=2
            while candidate and Campaign.objects.filter(name=candidate).exists():
                candidate=f'[{prefix}-{suffix}] - {base_name}'[:160]; suffix+=1
            form['name']=candidate
    edit_template=CampaignTemplate.objects.filter(pk=request.GET.get('edit_template'),deleted_at__isnull=True).first()
    return render(request,'portal/campaigns.html',ctx(request,'campaigns','Campaigns',campaigns=campaign_rows,q=q,choices=CAMPAIGN_OPTIONS,sources=SearchSource.objects.filter(enabled=True).order_by('category','name'),templates=(CampaignTemplate.objects.all() if show_deleted_templates else CampaignTemplate.objects.filter(deleted_at__isnull=True)),active_templates=CampaignTemplate.objects.filter(deleted_at__isnull=True),templates_data=_template_payload(),campaign_form=form,edit_template=edit_template,show_deleted=show_deleted,show_deleted_templates=show_deleted_templates,show_create=bool(request.GET.get('new') or request.GET.get('template') or request.GET.get('from_campaign') or request.GET.get('from_run'))))


@login_required
def campaign_rotation_data(request,pk):
    c=get_object_or_404(Campaign,pk=pk,deleted_at__isnull=True)
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    limit=c.queries_per_rotation or ps.keywords_per_run
    raw_offset=(request.GET.get('offset') or '').strip()
    if raw_offset.lstrip('-').isdigit(): offset=max(0,int(raw_offset))
    else: offset=1 if request.GET.get('which','next')=='next' else 0
    plan=build_campaign_query_plan(c,max_queries=limit,rotation_offset=offset)
    interval=_safe_setting_int(ps,'scraper_interval_minutes',120,minimum=30)*60; now=timezone.now(); next_ts=(int(now.timestamp()//interval)+1)*interval
    next_rotation=datetime.fromtimestamp(next_ts,tz=now.tzinfo)
    return JsonResponse({'ok':True,'which':'current' if offset==0 else 'preview','offset':offset,'next_rotation':next_rotation.strftime('%d/%m/%Y %H:%M:%S'),'queries':[{'kind':q.get('kind',''),'query':q.get('query',''),'rationale':q.get('rationale','')} for q in plan.get('queries',[])]})


def _campaign_found_chart_data(campaign):
    """Historical discovery and explicitly-attributed local/cloud token usage.

    Token rows are classified by the provider that actually executed the request.
    This keeps campaign analytics correct when a local primary falls back to cloud
    (or the reverse) and avoids inferring runtime from campaign configuration.
    """
    opportunities=[]; leads=[]; address_book=[]; requests=[]; duplicates=[]; errors=[]; local_tokens=[]; cloud_tokens=[]
    for run in CampaignRun.objects.filter(campaign=campaign).order_by('created_at').only('created_at','started_at','finished_at','result','status','error'):
        stamp=run.finished_at or run.started_at or run.created_at
        if not stamp: continue
        try: local=timezone.localtime(stamp)
        except Exception: local=stamp
        try: day=local.date().isoformat(); at=local.isoformat()
        except Exception: continue
        result=run.result or {}; opp_count=result.get('new_opportunities')
        if opp_count is None: opp_count=int(result.get('unique') or 0)
        lead_count=int(result.get('new_leads') or 0)
        try: opp_count=max(0,int(opp_count or 0))
        except Exception: opp_count=0
        try: lead_count=max(0,int(lead_count or 0))
        except Exception: lead_count=0
        dup_count=result.get('duplicates')
        if dup_count is None: dup_count=result.get('duplicates_merged_before_enrichment',0)
        err_count=result.get('error_count')
        if err_count is None:
            err_count=len(result.get('errors') or [])
            if not err_count and (str(run.status or '').lower()=='failed' or str(run.error or '').strip()): err_count=1
        try: dup_count=max(0,int(dup_count or 0))
        except Exception: dup_count=0
        try: err_count=max(0,int(err_count or 0))
        except Exception: err_count=0
        opportunities.append({'at':at,'date':day,'count':opp_count}); leads.append({'at':at,'date':day,'count':lead_count})
        duplicates.append({'at':at,'date':day,'count':dup_count}); errors.append({'at':at,'date':day,'count':err_count})
    # New requests carry campaign attribution directly on UsageMetric.  For older
    # Ollama history, recover only unambiguous entity-linked AIRequestLog rows:
    # an Opportunity/Hidden Lead must belong to this campaign and to no other one.
    # This avoids inventing attribution for shared discoveries while restoring useful
    # local-token history from releases that omitted campaign_id on UsageMetric.
    explicit_usage=list(UsageMetric.objects.filter(metadata__campaign_id=campaign.pk).order_by('at').values('at','provider','category','stage','requests','tokens_in','tokens_out','metadata'))
    for m in explicit_usage:
        try: local=timezone.localtime(m['at']); day=local.date().isoformat(); at=local.isoformat()
        except Exception: continue
        meta=m.get('metadata') or {}; reasoning=int(meta.get('reasoning_tokens') or 0); cached=int(meta.get('cached_tokens') or 0)
        tin=int(m.get('tokens_in') or 0); tout=int(m.get('tokens_out') or 0)
        row={'at':at,'date':day,'count':tin+tout+reasoning,'tokens_in':tin,'tokens_out':tout,'reasoning_tokens':reasoning,'cached_tokens':cached}
        (cloud_tokens if is_cloud_provider(m.get('provider')) else local_tokens).append(row)
        req=max(0,int(m.get('requests') or 0)); category=str(m.get('category') or '').casefold(); stage=str(m.get('stage') or '').casefold()
        # Request chart is acquisition traffic, not local Ollama analysis calls: Local is
        # search-engine + direct/follow-up HTTP discovery, while Cloud is Cloud AI/web.
        if req:
            if is_cloud_provider(m.get('provider')) or category.startswith('cloud'):
                requests.append({'at':at,'date':day,'local_requests':0,'cloud_requests':req})
            elif category in {'search','fresh_source','fresh_source_result','direct_site','company_career_discovery','followup_discovery','facebook_watch_upgrade'} or category.startswith('fresh_') or stage in {'query','bounded_followup','company_career_pages'}:
                requests.append({'at':at,'date':day,'local_requests':req,'cloud_requests':0})

    unique_opp_ids=[str(x) for x in Opportunity.objects.filter(campaigns=campaign).annotate(_campaign_count=Count('campaigns')).filter(_campaign_count=1).values_list('pk',flat=True)]
    unique_lead_ids=[str(x) for x in CompanyLead.objects.filter(campaigns=campaign).annotate(_campaign_count=Count('campaigns')).filter(_campaign_count=1).values_list('pk',flat=True)]
    historical_local=AIRequestLog.objects.filter(runtime='local',provider='ollama').filter(
        Q(subject_type='opportunity',subject_id__in=unique_opp_ids)|Q(subject_type='hidden_lead',subject_id__in=unique_lead_ids)
    ).exclude(metadata__campaign_id=campaign.pk).order_by('at').values('at','tokens_in','tokens_out')
    explicit_local_times=[m['at'] for m in explicit_usage if not is_cloud_provider(m.get('provider'))]
    for rowlog in historical_local:
        stamp=rowlog.get('at')
        # A current request writes AIRequestLog and UsageMetric together.  If a tagged
        # metric exists within a few seconds, do not double-count the historical fallback.
        if any(abs((stamp-x).total_seconds()) <= 5 for x in explicit_local_times if stamp and x):
            continue
        try: local=timezone.localtime(stamp); day=local.date().isoformat(); at=local.isoformat()
        except Exception: continue
        tin=int(rowlog.get('tokens_in') or 0); tout=int(rowlog.get('tokens_out') or 0)
        local_tokens.append({'at':at,'date':day,'count':tin+tout,'tokens_in':tin,'tokens_out':tout,'reasoning_tokens':0,'cached_tokens':0,'historical_fallback':True})
    # 0.10.94 stores campaign/run provenance on Address Book contacts instead of
    # generating high-volume addressbook_promotion AuditLog rows.
    for contact in Contact.objects.filter(origin_provenance__campaign_id=campaign.pk).order_by('created_at').values('created_at','origin_provenance'):
        try:
            local=timezone.localtime(contact['created_at']); day=local.date().isoformat(); at=local.isoformat()
        except Exception:
            continue
        address_book.append({'at':at,'date':day,'count':1})
    return {'opportunities':opportunities,'leads':leads,'address_book':address_book,'requests':requests,'duplicates':duplicates,'errors':errors,'local_tokens':local_tokens,'cloud_tokens':cloud_tokens}


@login_required
def campaign_detail(request,pk):
    c=get_object_or_404(Campaign,pk=pk,deleted_at__isnull=True)
    export_kind=(request.GET.get('export') or '').strip().lower()
    if export_kind=='runs':
        rows=_daily_campaign_run_rows(CampaignRun.objects.filter(campaign=c).select_related('campaign').order_by('-created_at')[:20000])
        return _xlsx(f'campaign_{c.pk}_runs.xlsx',['Date','First run','Last run','Runs','Opportunities','Leads','Local tokens','Cloud tokens','Execution','Status'],[(x['date'],x['first_run'],x['last_run'],x['run_count'],x['opportunities'],x['leads'],x.get('local_tokens',0),x.get('cloud_tokens',0),(' · '.join(v for v in (x.get('execution_path',''),x.get('run_context','')) if v)),x['status']) for x in rows])
    if export_kind=='leads':
        rows=c.leads.filter(user_deleted=False).select_related('source').order_by('-created_at')
        return _xlsx(f'campaign_{c.pk}_leads.xlsx',['Company','Location','Source','Fit','Added','Target URL'],[(display_company_name(x.company,x.target_url or x.source_url),x.country,x.source.name if x.source else '',x.score,x.created_at,x.target_url or x.source_url) for x in rows[:10000]])
    if export_kind=='opportunities':
        rows=c.opportunities.filter(suppressed=False,user_deleted=False).order_by('-created_at')
        return _xlsx(f'campaign_{c.pk}_opportunities.xlsx',['Company','Role','Location','Source','Status','Fit','Added','URL'],[(x.company,x.title,x.country,x.source.name if x.source else '',x.get_status_display(),x.fit_score,x.first_seen_by_portal,x.target_url or x.url) for x in rows[:10000]])
    if request.method=='POST':
        action=request.POST.get('action')
        if action=='save':
            name=request.POST.get('name','').strip()
            if not name:
                messages.error(request,'Campaign name is required.')
            elif len(name)<3:
                messages.error(request,'Campaign name must be at least 3 characters.')
            elif Campaign.objects.exclude(pk=c.pk).filter(name=name).exists():
                messages.error(request,'A campaign with that name already exists.')
            else:
                requested_enabled=bool(request.POST.get('enabled'))
                stopping=CampaignRun.objects.filter(campaign=c,status='stopping').exists()
                c.name=name; c.template=request.POST.get('template','').strip(); c.description=request.POST.get('description','').strip()[:2000]
                c.enabled=(False if stopping and requested_enabled else requested_enabled)
                _save_campaign_fields(c,request); c.save()
                if stopping and requested_enabled:
                    messages.warning(request,'Campaign settings were saved, but scheduled runs remain disabled until the active run finishes stopping.')
                else:
                    messages.success(request,'Campaign saved.')
        elif action=='save_rotation':
            raw=(request.POST.get('queries_per_rotation') or '').strip()
            if not raw:
                c.queries_per_rotation=None; c.save(update_fields=['queries_per_rotation','updated_at']); messages.success(request,'Query rotation now uses the global default.')
            else:
                try:
                    value=int(raw)
                    if not 1 <= value <= 100: raise ValueError
                    c.queries_per_rotation=value; c.save(update_fields=['queries_per_rotation','updated_at']); messages.success(request,'Queries per rotation updated.')
                except Exception:
                    messages.error(request,'Queries per rotation must be between 1 and 100.')
        elif action=='pause':
            c.enabled=False; c.save(update_fields=['enabled','updated_at'])
            active=CampaignRun.objects.filter(campaign=c,status__in=['queued','running']).order_by('-created_at').first()
            if active:
                active.status='stopping'; active.message='Pause requested'; active.result={**(active.result or {}),'stop_requested_at':timezone.now().isoformat()}; active.save(update_fields=['status','message','result'])
                messages.success(request,'Campaign paused. The active run will stop at the next safe checkpoint.')
            else:
                messages.success(request,'Campaign paused. Scheduled runs are disabled.')
        elif action=='enable':
            if CampaignRun.objects.filter(campaign=c,status='stopping').exists():
                messages.warning(request,'This campaign is still stopping. Wait for the active run to finish before enabling it again.')
            else:
                c.enabled=True; c.save(update_fields=['enabled','updated_at']); messages.success(request,'Campaign enabled. Scheduled runs are active.')
        elif action=='run':
            if CampaignRun.objects.filter(campaign=c,status__in=['queued','running','stopping']).exists(): messages.warning(request,'This campaign already has an active run.')
            else:
                settings_obj=PortalSettings.objects.get_or_create(pk=1)[0]
                cloud_context=(settings_obj.discovery_mode=='cloud_web')
                ready=True; readiness={}
                if cloud_context:
                    try:
                        if not has_usable_cloud_web_model():
                            raise RuntimeError('One or more Cloud Web stages is not configured.')
                        cloud_discovery_route(stage='url_scrape')
                    except Exception:
                        ready=False
                        messages.warning(request,'Cloud Web unavailable — no usable Cloud provider/model. The campaign was not started and will not fall back to local AI.')
                else:
                    readiness=ai_compute_readiness(force=True)
                    ready=bool(readiness.get('ready'))
                    if not ready:
                        messages.warning(request,f"AI compute is unavailable. The campaign was not started. {readiness.get('reason','Configure Local AI in AI & Discovery.')}")
                if ready:
                    criteria=_campaign_form_from(c)
                    criteria['discovery_mode']=settings_obj.discovery_mode
                    criteria['forum_only']=False
                    criteria['run_kind']='primary'
                    criteria['deferred_local_ai']=False
                    run_context=None
                    if cloud_context:
                        custom_text=(request.POST.get('custom_instructions') or '').strip()[:2000]
                        preferred=[x for x in request.POST.getlist('preferred_company_countries') if x in COUNTRIES][:20]
                        excluded=[x for x in request.POST.getlist('excluded_company_countries') if x in COUNTRIES][:20]
                        keep_until=None
                        if (custom_text or preferred or excluded) and request.POST.get('keep_until_enabled'):
                            raw_until=(request.POST.get('keep_until') or '').strip()
                            try:
                                keep_until=datetime.fromisoformat(raw_until) if raw_until else default_keep_until()
                                if timezone.is_naive(keep_until): keep_until=timezone.make_aware(keep_until,timezone.get_current_timezone())
                                if keep_until<=timezone.now(): keep_until=default_keep_until()
                            except Exception:
                                keep_until=default_keep_until()
                        if custom_text or preferred or excluded:
                            run_context=make_run_context('custom_instructions',custom_text,keep_until=keep_until,origin='manual',preferred_company_countries=preferred,excluded_company_countries=excluded)
                        else:
                            run_context=inherited_run_context(c)
                    else:
                        run_context=make_run_context('note',(request.POST.get('run_note') or '').strip()[:1200],origin='manual')
                    if run_context: criteria['run_context']=run_context
                    run=CampaignRun.objects.create(campaign=c,criteria=criteria,message='Queued by user')
                    task=run_campaign_job.delay(run.pk); run.celery_task_id=task.id or ''; run.save(update_fields=['celery_task_id']); messages.success(request,'Campaign queued. Progress is visible here and on the Dashboard.')
        elif action=='stop':
            run=CampaignRun.objects.filter(campaign=c,status__in=['queued','running']).order_by('-created_at').first()
            if run:
                run.status='stopping'; run.message='Stop requested'; run.result={**(run.result or {}),'stop_requested_at':timezone.now().isoformat()}; run.save(update_fields=['status','message','result']); messages.success(request,'Stop requested. ScoutBox will stop at the next safe checkpoint.')
            else: messages.warning(request,'No active run to stop.')
        elif action=='duplicate':
            original=c; original.pk=None; original.name=f'{c.name} copy {timezone.now():%H%M%S}'; original.enabled=False; original.save(); messages.success(request,'Campaign duplicated.'); return redirect('campaign_detail',pk=original.pk)
        elif action=='delete':
            active_delete=CampaignRun.objects.filter(campaign=c,status__in=['queued','running','stopping']).exists()
            if c.enabled or active_delete:
                messages.error(request,'Only paused campaigns can be deleted. Pause/disable this campaign and wait for any active run to stop first.')
            else:
                name=c.name; c.enabled=False; c.deleted_at=timezone.now(); c.save(update_fields=['enabled','deleted_at','updated_at']); messages.success(request,f'Moved campaign to the Recycle Bin: {name}.'); return redirect('campaigns')
        return redirect('campaign_detail',pk=c.pk)
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    limit=c.queries_per_rotation or ps.keywords_per_run
    offset=1 if request.GET.get('rotation')=='next' else 0
    preview=build_campaign_query_plan(c,max_queries=limit,rotation_offset=offset)
    interval=_safe_setting_int(ps,'scraper_interval_minutes',120,minimum=30)*60; now=timezone.now(); next_ts=(int(now.timestamp()//interval)+1)*interval; next_rotation=datetime.fromtimestamp(next_ts,tz=now.tzinfo)
    active_run=CampaignRun.objects.filter(campaign=c,status__in=['queued','running','stopping']).order_by('-created_at').first()
    next_run_at=_campaign_next_run(c,ps)
    raw_runs=CampaignRun.objects.filter(campaign=c).select_related('campaign').order_by('-created_at')[:5000]
    runs=_daily_campaign_run_rows(raw_runs)[:120]
    form=_campaign_form_from(c)
    campaign_opportunities=list(c.opportunities.filter(suppressed=False,user_deleted=False).select_related('source').order_by('-created_at')[:200])
    _decorate_opportunity_sources(campaign_opportunities)
    campaign_leads=list(c.leads.filter(user_deleted=False).select_related('source').order_by('-created_at')[:200])
    for lead in campaign_leads:
        lead.display_company=display_company_name(lead.company,lead.target_url or lead.source_url) or lead.company
        lead.display_source=_lead_source_label(lead)
    run_context_mode='custom_instructions' if ps.discovery_mode=='cloud_web' else 'note'
    keep_dt=timezone.localtime(default_keep_until())
    keep_default=keep_dt.strftime('%Y-%m-%dT%H:%M')
    keep_default_date=keep_dt.strftime('%d/%m/%Y')
    keep_default_time=keep_dt.strftime('%H:%M')
    retained_custom=inherited_run_context(c)
    return render(request,'portal/campaign_detail.html',ctx(request,'campaigns',c.name,breadcrumbs=[{'label':'ScoutBox','route':'dashboard'},{'label':'Campaigns','route':'campaigns'},{'label':c.name,'route':None}],campaign=c,form=form,opportunities=campaign_opportunities,leads=campaign_leads,opportunity_count=c.opportunities.filter(suppressed=False,user_deleted=False).count(),lead_count=c.leads.filter(user_deleted=False).count(),campaign_chart_data=_campaign_found_chart_data(c),choices=CAMPAIGN_OPTIONS,sources=SearchSource.objects.filter(enabled=True).order_by('category','name'),templates=CampaignTemplate.objects.all(),query_plan=preview,rotation_preview=offset,next_rotation=next_rotation,next_run_at=next_run_at,active_run=active_run,runs=runs,run_context_mode=run_context_mode,run_keep_default=keep_default,run_keep_default_date=keep_default_date,run_keep_default_time=keep_default_time,retained_custom=retained_custom))


@login_required
@require_POST
def search_provider_test_async(request,pk):
    source=get_object_or_404(SearchSource,pk=pk)
    service=(request.POST.get('service') or '').strip()
    label=source.name
    if source.name=='SearchAPI · Google Jobs' and service in SEARCHAPI_SERVICE_SOURCES:
        label='SearchAPI · '+SEARCHAPI_SHORT_LABELS.get(service,service)
    query=request.POST.get('query','ScoutBox test')[:4000]
    job=BackgroundJob.objects.create(kind='diagnostic',label=f'Search test: {label}'[:300],message='Queued',result={'source_id':source.pk,'service':service})
    task=search_provider_test_job.delay(job.pk,source.pk,bool(request.POST.get('force_public')),query,service); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
    return JsonResponse({'ok':True,'job_id':job.pk})


@login_required
def search_provider_raw_preview(request,pk):
    job=get_object_or_404(BackgroundJob,pk=pk,kind='diagnostic')
    raw=str((job.result or {}).get('raw_html') or '')
    if not raw:
        return HttpResponse('<!doctype html><meta charset="utf-8"><title>No raw response</title><p>No raw HTML was captured for this test.</p>',content_type='text/html; charset=utf-8',status=404)
    response=HttpResponse(raw,content_type='text/html; charset=utf-8')
    # Preview untrusted provider HTML in a deliberately scriptless sandbox. Images and
    # styles remain visible so CAPTCHAs/interstitials can still be diagnosed.
    response['Content-Security-Policy']="sandbox; default-src 'none'; img-src data: http: https:; style-src 'unsafe-inline' http: https:; font-src data: http: https:;"
    response['X-Content-Type-Options']='nosniff'
    return response


@login_required
@require_POST
def item_read_state(request,kind,pk):
    read_value=(request.POST.get('read','1') or '1').strip().lower()
    is_read=read_value not in ('0','false','no','unread')
    if kind=='opportunity':
        count=Opportunity.objects.filter(pk=pk,suppressed=False,user_deleted=False).update(is_read=is_read)
    elif kind=='market':
        count=CompanyLead.objects.filter(pk=pk,user_deleted=False).update(is_read=is_read)
    elif kind in ('application','draft'):
        count=Application.objects.filter(pk=pk,opportunity__user_deleted=False,deleted_at__isnull=True).update(is_read=is_read)
    else:
        return JsonResponse({'ok':False,'error':'Unknown read-state type.'},status=404)
    if not count:
        return JsonResponse({'ok':False,'error':'Item not found.'},status=404)
    return JsonResponse({'ok':True,'id':pk,'kind':kind,'is_read':is_read})


@login_required
def attention_counts(request):
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    snap=_attention_snapshot(ps)
    return JsonResponse({
        'ok':True,
        'opportunities':snap['unread_opportunities'],
        'hidden_leads':snap['unread_hidden_leads'],
        'applications':snap['unread_applications'],
        'contacts':snap['unread_contacts'],
        'facebook_pages':snap['unread_facebook_pages'],
        'errors':snap['new_errors'],
        'warnings':snap.get('new_warnings',0),
        'alerts':snap.get('alert_count',snap['new_errors']),
        'total':snap['unread_total'],
        'recent_opportunities':snap.get('recent_opportunities') or [],
        'recent_leads':snap.get('recent_leads') or [],
        'alert_heading':snap.get('alert_heading') or '',
        'alert_notifications':snap.get('alert_notifications') or [],
    })



_ADV_APPLY_VIA={'web','email','ats','forum','unknown'}
_ADV_CONTACT_METHOD={'web','email','ats','forum','unknown'}
_ADV_REMOTE={'none','conditional','fully','unknown'}
_ADV_POST_AGE={'unknown','lt3d','lt1w','lt2w','lt1m','lt2m','lt3m','older','evergreen'}
_ADV_POST_AGE_THRESHOLDS=('lt3d','lt1w','lt2w','lt1m','lt2m','lt3m')
_ADV_COMPANY_SIZE={'lt10','lt50','lt100','lt500','lt1000','gte1000','unknown'}
_ADV_COMPANY_AGE={'lt1','lt2','lt5','lt10','gte10','unknown'}
_ADV_OPPORTUNITY_SESSION_KEY='scoutbox_opportunity_advanced_filters'
_COMPANY_FILTER_SESSION_KEYS={
    'hidden_lead':'scoutbox_hidden_lead_company_filters',
    'contact':'scoutbox_contact_company_filters',
}
_URL_CONTENT_WARNING_PREFIX='CONTENT_NOT_JOB:'




def _advanced_opportunity_filters(request):
    def normalize_group(values, allowed, name=''):
        out=[]
        for raw in values or []:
            for value in str(raw or '').split(','):
                value=value.strip().lower()
                if value in allowed and value not in out:
                    out.append(value)
        # Range-bucket filters are independent. Selecting every value in a group is
        # unrestricted/default; otherwise every checked bucket matches only itself.
        if out and set(out)==set(allowed):
            return []
        return out

    if request.GET.get('adv_reset')=='1':
        request.session.pop(_ADV_OPPORTUNITY_SESSION_KEY,None)
        request.session.modified=True
        return {'apply_via':[],'remote':[],'post_age':[],'company_size':[],'company_age':[]}

    has_request_filters=any(key in request.GET for key in ('adv_apply','adv_remote','adv_age','adv_size','adv_company_age'))
    if has_request_filters:
        selected={
            'apply_via':normalize_group(request.GET.getlist('adv_apply'),_ADV_APPLY_VIA,'adv_apply'),
            'remote':normalize_group(request.GET.getlist('adv_remote'),_ADV_REMOTE,'adv_remote'),
            'post_age':normalize_group(request.GET.getlist('adv_age'),_ADV_POST_AGE,'adv_age'),
            'company_size':normalize_group(request.GET.getlist('adv_size'),_ADV_COMPANY_SIZE,'adv_size'),
            'company_age':normalize_group(request.GET.getlist('adv_company_age'),_ADV_COMPANY_AGE,'adv_company_age'),
        }
        # Persist only normalized, safe values in the authenticated Django session. Logout
        # flushes this state. This keeps the Opportunity filter stable across navigation.
        request.session[_ADV_OPPORTUNITY_SESSION_KEY]=selected
        request.session.modified=True
        return selected

    stored=request.session.get(_ADV_OPPORTUNITY_SESSION_KEY) or {}
    if isinstance(stored,dict):
        return {
            'apply_via':normalize_group(stored.get('apply_via') or [],_ADV_APPLY_VIA,'adv_apply'),
            'remote':normalize_group(stored.get('remote') or [],_ADV_REMOTE,'adv_remote'),
            'post_age':normalize_group(stored.get('post_age') or [],_ADV_POST_AGE,'adv_age'),
            'company_size':normalize_group(stored.get('company_size') or [],_ADV_COMPANY_SIZE,'adv_size'),
            'company_age':normalize_group(stored.get('company_age') or [],_ADV_COMPANY_AGE,'adv_company_age'),
        }
    return {'apply_via':[],'remote':[],'post_age':[],'company_size':[],'company_age':[]}


def _opportunity_remote_bucket(row):
    facts=row.extracted_facts if isinstance(getattr(row,'extracted_facts',None),dict) else {}
    data=facts.get('remote_classification') if isinstance(facts.get('remote_classification'),dict) else {}
    status=str(data.get('status') or '').strip().lower().replace('-','_').replace(' ','_')
    if status=='fully_remote': return 'fully'
    if status in {'remote','hybrid'}: return 'conditional'
    if status in {'onsite','on_site','no_remote'}: return 'none'
    return 'unknown'


def _opportunity_apply_bucket(row):
    channel=str(getattr(row,'channel','') or '').strip().lower()
    facts=getattr(row,'extracted_facts',None) if isinstance(getattr(row,'extracted_facts',None),dict) else {}
    if channel=='forum' or isinstance(facts.get('forum'),dict) or (facts.get('acquisition') or {}).get('source_category')=='forum': return 'forum'
    if channel=='ats': return 'ats'
    if channel=='email': return 'email'
    if channel in {'website','public','community'}: return 'web'
    if str(getattr(row,'contact_email','') or '').strip(): return 'email'
    return 'unknown'


def _opportunity_post_age_bucket(row):
    # Match the visible table contract first. If the list renders ``?`` because the
    # age is not displayable or has no confidence, it belongs to Unknown/Others even
    # when retained evidence still contains an internal age_days estimate.
    try: confidence=int(getattr(row,'freshness_confidence',0) or 0)
    except Exception: confidence=0
    visible_label=opportunity_post_age_display_label(row)
    if confidence<=0 or visible_label=='Age unknown':
        return 'unknown'
    if visible_label=='Evergreen':
        return 'evergreen'
    age=opportunity_post_age_sort_days(row)
    if age is None:
        return 'unknown'
    try: age=max(0,int(age))
    except Exception: return 'unknown'
    if age < 3: return 'lt3d'
    if age < 7: return 'lt1w'
    if age < 14: return 'lt2w'
    if age < 31: return 'lt1m'
    if age < 61: return 'lt2m'
    if age < 91: return 'lt3m'
    return 'older'


def _company_info_real_identity(row, intel=None):
    """Return True only when size/age metadata is tied to a real employer/company.

    Job boards, ATS hosts and social/search platforms such as JobsDB/LinkedIn/Workday
    must never provide the company identity for filtering or Company Info. If ScoutBox
    cannot name a non-platform employer, the record remains Unknown for size/age.
    """
    intel=intel if isinstance(intel,dict) else (getattr(row,'company_intel',{}) or {})
    candidates=[getattr(row,'company',''), intel.get('company','')]
    for fact in (intel.get('facts') or []):
        if isinstance(fact,dict) and str(fact.get('label') or '').strip().casefold()=='company':
            candidates.append(fact.get('value',''))
    for value in candidates:
        text=str(value or '').strip()
        if text and not is_job_or_platform_company_name(text) and re.search(r'[A-Za-z0-9]',text):
            return True
    return False

def _company_info_structured(row):
    intel=getattr(row,'company_intel',{}) or {}
    if not isinstance(intel,dict):
        return {},{}
    structured=intel.get('structured') if isinstance(intel.get('structured'),dict) else {}
    return intel,structured

def _company_size_upper_bound(row):
    intel,structured=_company_info_structured(row)
    if not _company_info_real_identity(row,intel):
        return None
    raw=str(structured.get('size_range') or structured.get('employee_count_or_range') or '')
    nums=[int(x.replace(',','')) for x in re.findall(r'\d[\d]*',raw)]
    if not nums: return None
    return max(nums)

def _company_size_bucket(row):
    n=_company_size_upper_bound(row)
    if n is None:return 'unknown'
    if n<=10:return 'lt10'
    if n<=50:return 'lt50'
    if n<=100:return 'lt100'
    if n<=500:return 'lt500'
    if n<=1000:return 'lt1000'
    return 'gte1000'

def _normalize_threshold_filter(values, allowed, order=None):
    selected=[]
    for raw in values or []:
        for value in str(raw or '').split(','):
            value=value.strip().lower()
            if value in allowed and value not in selected:
                selected.append(value)
    if selected and set(selected)==set(allowed):
        return []
    return selected

def _normalize_company_size_filter(values):
    return _normalize_threshold_filter(values,_ADV_COMPANY_SIZE,['lt10','lt50','lt100','lt500','lt1000','gte1000'])

def _normalize_company_age_filter(values):
    return _normalize_threshold_filter(values,_ADV_COMPANY_AGE,['lt1','lt2','lt5','lt10','gte10'])


def _record_contact_method_bucket(row):
    """Presentation-level Contact Method bucket for Opportunities, Hidden Leads and Address Book."""
    # Forum wins over email because Address Book rows often have an email plus an origin URL.
    try:
        source=getattr(row,'source',None)
        if getattr(source,'source_type','') == 'forum':
            return 'forum'
    except Exception:
        pass
    facts=getattr(row,'extracted_facts',None) if isinstance(getattr(row,'extracted_facts',None),dict) else {}
    state=getattr(row,'ai_state',None) if isinstance(getattr(row,'ai_state',None),dict) else {}
    for payload in (facts,state):
        if isinstance(payload.get('forum'),dict) or (payload.get('acquisition') or {}).get('source_category') == 'forum':
            return 'forum'
    blob=' '.join(str(getattr(row,k,'') or '') for k in ('source','source_url','target_url','search_url','contact_url','url')).casefold()
    if 'forum' in blob or any(x in blob for x in ('eevblog.com/forum','forum.arduino.cc','forum.kicad.info','forums.raspberrypi.com','vogons.org','microchip.com','community.st.com','devzone.nordicsemi.com','e2e.ti.com','forums.freertos.org','forums.debian.net','bbs.archlinux.org','forums.gentoo.org','linuxquestions.org')):
        return 'forum'
    channel=str(getattr(row,'channel','') or '').strip().lower()
    if channel=='forum': return 'forum'
    if channel=='ats': return 'ats'
    if str(getattr(row,'contact_email','') or getattr(row,'email','') or '').strip(): return 'email'
    if str(getattr(row,'contact_url','') or getattr(row,'source_url','') or getattr(row,'target_url','') or getattr(row,'url','') or '').strip(): return 'web'
    return 'unknown'

def _company_filter_state(request, kind):
    """Return session-persisted company size/age filters for compact list dialogs."""
    session_key=_COMPANY_FILTER_SESSION_KEYS.get(kind,'')
    if request.GET.get('company_filter_reset')=='1':
        if session_key:
            request.session.pop(session_key,None)
            request.session.modified=True
        return [],[],[]
    has_request_filters=('company_size' in request.GET) or ('company_age' in request.GET) or ('contact_method' in request.GET)
    if has_request_filters:
        size=_normalize_company_size_filter(request.GET.getlist('company_size'))
        age=_normalize_company_age_filter(request.GET.getlist('company_age'))
        method=_normalize_threshold_filter(request.GET.getlist('contact_method'),_ADV_CONTACT_METHOD)
        if session_key:
            request.session[session_key]={'company_size':size,'company_age':age,'contact_method':method}
            request.session.modified=True
        return size,age,method
    stored=request.session.get(session_key) if session_key else None
    if isinstance(stored,dict):
        return _normalize_company_size_filter(stored.get('company_size') or []), _normalize_company_age_filter(stored.get('company_age') or []), _normalize_threshold_filter(stored.get('contact_method') or [],_ADV_CONTACT_METHOD)
    return [],[],[]

def _company_filter_reset_query(request):
    params=request.GET.copy()
    for key in ('company_size','company_age','contact_method','company_filter_reset','page'):
        if key in params: del params[key]
    params['company_filter_reset']='1'
    return params.urlencode()

def _company_filter_clean_redirect(request):
    params=request.GET.copy()
    for key in ('company_size','company_age','contact_method','company_filter_reset','page'):
        params.pop(key,None)
    target=request.path + (('?' + params.urlencode()) if params else '')
    return redirect(target)

def _apply_company_info_quick_filter(qs, size_selected=None, age_selected=None, method_selected=None):
    size_selected=_normalize_company_size_filter(size_selected)
    age_selected=_normalize_company_age_filter(age_selected)
    method_selected=_normalize_threshold_filter(method_selected,_ADV_CONTACT_METHOD)
    if not size_selected and not age_selected and not method_selected:
        return qs
    keep=[]
    for row in qs.select_related(None).prefetch_related(None).only('pk','company','company_intel').iterator(chunk_size=500):
        if not _threshold_selected(_company_size_bucket(row),size_selected,['lt10','lt50','lt100','lt500','lt1000','gte1000']):
            continue
        if not _threshold_selected(_company_age_bucket(row),age_selected,['lt1','lt2','lt5','lt10','gte10']):
            continue
        if method_selected and _record_contact_method_bucket(row) not in method_selected:
            continue
        keep.append(row.pk)
    return qs.filter(pk__in=keep)

def _apply_company_size_quick_filter(qs, selected):
    return _apply_company_info_quick_filter(qs, selected, [])

def _company_age_years(row):
    intel,structured=_company_info_structured(row)
    if not _company_info_real_identity(row,intel):
        return None
    year=structured.get('founded_year')
    if year:
        try:return max(0,timezone.localdate().year-int(year))
        except Exception:pass
    domain=str(structured.get('domain_age_domain') or '').strip()
    if domain and is_job_or_platform_host(domain):
        return None
    raw=str(structured.get('domain_age_label') or '')
    m=re.search(r'(\d+)',raw)
    return int(m.group(1)) if m else None

def _company_age_bucket(row):
    years=_company_age_years(row)
    if years is None:return 'unknown'
    if years<1:return 'lt1'
    if years<2:return 'lt2'
    if years<5:return 'lt5'
    if years<10:return 'lt10'
    return 'gte10'

def _threshold_selected(bucket, selected, order=None):
    if not selected:
        return True
    return bucket in selected

def _apply_advanced_opportunity_filters(qs, request):
    """Apply the modal-only Opportunity filters and return a QuerySet.

    These fields are partly presentation-derived. Evaluating the candidate rows once and
    folding the matching IDs back into a QuerySet keeps the visible list, counts, export,
    pagination and re-evaluation scopes on exactly the same semantics.
    """
    selected=_advanced_opportunity_filters(request)
    if not any(selected.values()):
        return qs,selected
    # Restrict database-side where it is exact, then use shared presentation buckets for
    # Remote/Post Age and fallback Apply Via behavior.
    # The list QuerySet carries select_related(source/application/origin_campaign).
    # Calling only() without those relation fields makes Django raise FieldError
    # (a traversed relation cannot also be deferred). The bucket calculation needs no
    # related objects, so drop select_related on this temporary evaluation QuerySet.
    candidates=qs.select_related(None).prefetch_related(None).only('pk','channel','contact_email','extracted_facts','company_intel','freshness_label','freshness_confidence','declared_posted_at','estimated_first_seen')
    keep=[]
    for row in candidates.iterator(chunk_size=500):
        if selected['apply_via'] and _opportunity_apply_bucket(row) not in selected['apply_via']:
            continue
        if selected['remote'] and _opportunity_remote_bucket(row) not in selected['remote']:
            continue
        if selected['post_age'] and _opportunity_post_age_bucket(row) not in selected['post_age']:
            continue
        if not _threshold_selected(_company_size_bucket(row),selected.get('company_size') or [],['lt10','lt50','lt100','lt500','lt1000','gte1000']): continue
        if not _threshold_selected(_company_age_bucket(row),selected.get('company_age') or [],['lt1','lt2','lt5','lt10','gte10']): continue
        keep.append(row.pk)
    return qs.filter(pk__in=keep),selected


def _advanced_opportunity_filter_summary(selected):
    # Kept for diagnostics/tooltips; the main Opportunity list intentionally shows only
    # the count summary so long range selections do not crowd the page header.
    apply_labels={'web':'Web','email':'Email','ats':'ATS','forum':'Forum','unknown':'Unknown / Others'}
    remote_labels={'none':'No Remote','conditional':'Remote with Condition','fully':'Fully Remote','unknown':'Unknown / Others'}
    post_age_labels={'lt3d':'< 3 days','lt1w':'< 1 week','lt2w':'~2 weeks','lt1m':'2 weeks-1 month','lt2m':'1-2 months','lt3m':'2-3 months','older':'3+ months','evergreen':'Evergreen','unknown':'Unknown / Others'}
    size_labels={'lt10':'0-10','lt50':'10-50','lt100':'50-100','lt500':'100-500','lt1000':'500-1,000','gte1000':'1,000+','unknown':'Unknown / Others'}
    company_age_labels={'lt1':'0-1 year','lt2':'1-2 years','lt5':'2-5 years','lt10':'5-10 years','gte10':'10+ years','unknown':'Unknown / Others'}
    parts=[]
    apply_vals=selected.get('apply_via') or []
    if apply_vals:
        parts.append('Contact Method: '+', '.join(apply_labels.get(x,x) for x in apply_vals))
    remote_vals=selected.get('remote') or []
    if remote_vals:
        parts.append('Remote: '+', '.join(remote_labels.get(x,x) for x in remote_vals))
    age_vals=selected.get('post_age') or []
    if age_vals:
        order=list(_ADV_POST_AGE_THRESHOLDS)+['older','evergreen','unknown']
        parts.append('Post Age: '+', '.join(post_age_labels.get(v,v) for v in order if v in age_vals))
    size_vals=selected.get('company_size') or []
    if size_vals:
        order=['lt10','lt50','lt100','lt500','lt1000','gte1000','unknown']
        parts.append('Company Size: '+', '.join(size_labels.get(v,v) for v in order if v in size_vals))
    company_age_vals=selected.get('company_age') or []
    if company_age_vals:
        order=['lt1','lt2','lt5','lt10','gte10','unknown']
        parts.append('Company/Domain Age: '+', '.join(company_age_labels.get(v,v) for v in order if v in company_age_vals))
    return ' · '.join(parts)

def _advanced_opportunity_reset_query(request):
    params=request.GET.copy()
    for key in ('adv_apply','adv_remote','adv_age','adv_size','adv_company_age','page'):
        if key in params: del params[key]
    params['adv_reset']='1'
    return params.urlencode()



def _apply_focus_filter(qs, focus_filter):
    focus=str(focus_filter or '').strip()
    if not focus:
        return qs
    if focus.casefold()=='unclassified':
        return qs.filter(Q(focus='') | Q(focus__isnull=True) | Q(focus__iexact='Unclassified'))
    return qs.filter(focus=focus)


def _request_multi_filter_state(request, name, *, canonicalizer=None, integer=False):
    mode=str(request.GET.get(f'{name}_mode') or '').strip().lower()
    if mode not in {'all','custom'}:
        mode=''
    raw_values=[]
    for raw in request.GET.getlist(name):
        for part in str(raw or '').split(','):
            value=part.strip()
            if value and value.lower() not in {'all','*'}:
                raw_values.append(value)
    values=[]
    for value in raw_values:
        try:
            if integer:
                if not str(value).isdigit():
                    continue
                value=int(value)
            elif canonicalizer:
                value=canonicalizer(value)
        except Exception:
            value=''
        if value not in ('', None) and value not in values:
            values.append(value)
    if not mode:
        mode='custom' if values else 'all'
    return {
        'mode':mode,
        'values':values,
        'is_all':mode!='custom',
        'is_none':mode=='custom' and not values,
    }


def _multi_filter_label(noun, values, labels, mode, total=None):
    if mode!='custom':
        if total is not None:
            return f'All {noun} ({int(total or 0)})'
        return f'All {noun}'
    if not values:
        return f'No {noun}'
    if len(values)==1:
        return (labels[0] if labels else str(values[0]))
    return f'{len(values)} {noun}'


def _option_selection_state(options, values, mode='all'):
    selected={str(x) for x in (values or [])}
    for row in options:
        row['selected'] = (mode != 'custom' or str(row.get('value')) in selected)
    return options


def _filter_options_label(noun, options, values, mode, total=None):
    labels=[]
    lookup={str(row.get('value')):str(row.get('label') or row.get('value') or '') for row in options}
    for value in values or []:
        label=lookup.get(str(value),str(value))
        if label:
            labels.append(label)
    return _multi_filter_label(noun, values or [], labels, mode, total)


def _selected_filter_values(request, name, allowed_values=None):
    state=_request_multi_filter_state(request,name)
    values=[str(x).strip() for x in state['values'] if str(x).strip()]
    if allowed_values is not None:
        allowed={str(x) for x in allowed_values}
        values=[x for x in values if x in allowed]
    state['values']=values
    state['is_none']=state['mode']=='custom' and not values
    state['is_all']=state['mode']!='custom'
    return state


def _apply_values_filter(qs, field, values, mode='all'):
    if mode=='custom' and not values:
        return qs.none()
    if mode=='custom':
        return qs.filter(**{field+'__in':list(values)})
    return qs


def _stats_record_locations(*values):
    seen=set(); out=[]
    for value in values:
        for item in normalize_location_items(value):
            label=str(item.get('label') or '').strip()
            if label and label.casefold() not in seen:
                seen.add(label.casefold()); out.append(label)
    return out


def _stats_record_map_locations(record):
    """Use the same source-faithful locations shown by ScoutBox list views."""
    try:
        return [str(x.get('label') or '').strip() for x in record_location_items(record) if str(x.get('label') or '').strip()]
    except Exception:
        return []



def _stats_map_truncate(value, limit=96):
    text=' '.join(str(value or '').split())
    return text if len(text)<=limit else text[:max(0,limit-1)].rstrip()+'…'


def _stats_map_line(label, value, limit=96):
    text=_stats_map_truncate(value, limit)
    return f'{label}: {text}' if text else ''


def _stats_map_date(value):
    if not value:
        return ''
    try:
        return timezone.localtime(value).strftime('%d/%m/%Y %H:%M:%S')
    except Exception:
        return ''


def _stats_public_url(value):
    text=str(value or '').strip()
    if not text:
        return ''
    return text if len(text)<=120 else text[:117].rstrip()+'…'


_STATS_MAP_CACHE_KEY='stats_map_geo_v4'
_STATS_MAP_UNRESOLVED_HOURS=72
_STATS_MAP_PLACE_POINTS={
    # North America
    'new york':(-74.0060,40.7128,'New York, United States'),'los angeles':(-118.2437,34.0522,'Los Angeles, United States'),
    'san francisco':(-122.4194,37.7749,'San Francisco, United States'),'san jose':(-121.8863,37.3382,'San Jose, United States'),
    'mountain view':(-122.0839,37.3861,'Mountain View, United States'),'seattle':(-122.3321,47.6062,'Seattle, United States'),
    'portland':(-122.6765,45.5152,'Portland, United States'),'austin':(-97.7431,30.2672,'Austin, United States'),
    'dallas':(-96.7970,32.7767,'Dallas, United States'),'houston':(-95.3698,29.7604,'Houston, United States'),
    'chicago':(-87.6298,41.8781,'Chicago, United States'),'boston':(-71.0589,42.3601,'Boston, United States'),
    'washington dc':(-77.0369,38.9072,'Washington, DC, United States'),'denver':(-104.9903,39.7392,'Denver, United States'),
    'atlanta':(-84.3880,33.7490,'Atlanta, United States'),'miami':(-80.1918,25.7617,'Miami, United States'),
    'california':(-119.4179,36.7783,'California, United States'),'texas':(-99.9018,31.9686,'Texas, United States'),
    'toronto':(-79.3832,43.6532,'Toronto, Canada'),'vancouver':(-123.1207,49.2827,'Vancouver, Canada'),
    'montreal':(-73.5673,45.5017,'Montréal, Canada'),'ottawa':(-75.6972,45.4215,'Ottawa, Canada'),
    'calgary':(-114.0719,51.0447,'Calgary, Canada'),'mexico city':(-99.1332,19.4326,'Mexico City, Mexico'),
    # Europe and Russia
    'london':(-0.1276,51.5072,'London, United Kingdom'),'paris':(2.3522,48.8566,'Paris, France'),
    'berlin':(13.4050,52.5200,'Berlin, Germany'),'munich':(11.5820,48.1351,'Munich, Germany'),
    'madrid':(-3.7038,40.4168,'Madrid, Spain'),'barcelona':(2.1734,41.3851,'Barcelona, Spain'),
    'rome':(12.4964,41.9028,'Rome, Italy'),'amsterdam':(4.9041,52.3676,'Amsterdam, Netherlands'),
    'dublin':(-6.2603,53.3498,'Dublin, Ireland'),'stockholm':(18.0686,59.3293,'Stockholm, Sweden'),
    'oslo':(10.7522,59.9139,'Oslo, Norway'),'helsinki':(24.9384,60.1699,'Helsinki, Finland'),
    'warsaw':(21.0122,52.2297,'Warsaw, Poland'),'prague':(14.4378,50.0755,'Prague, Czechia'),
    'vienna':(16.3738,48.2082,'Vienna, Austria'),'zurich':(8.5417,47.3769,'Zurich, Switzerland'),
    'moscow':(37.6173,55.7558,'Moscow, Russia'),'saint petersburg':(30.3351,59.9343,'Saint Petersburg, Russia'),
    'st petersburg':(30.3351,59.9343,'Saint Petersburg, Russia'),'novosibirsk':(82.9357,55.0084,'Novosibirsk, Russia'),
    'yekaterinburg':(60.6122,56.8431,'Yekaterinburg, Russia'),'kazan':(49.1064,55.7961,'Kazan, Russia'),
    'vladivostok':(131.8869,43.1155,'Vladivostok, Russia'),
    # Asia / Middle East / Oceania
    'singapore':(103.8198,1.3521,'Singapore'),'tokyo':(139.6917,35.6895,'Tokyo, Japan'),
    'seoul':(126.9780,37.5665,'Seoul, South Korea'),'beijing':(116.4074,39.9042,'Beijing, China'),
    'shanghai':(121.4737,31.2304,'Shanghai, China'),'shenzhen':(114.0579,22.5431,'Shenzhen, China'),
    'hong kong':(114.1694,22.3193,'Hong Kong'),'taipei':(121.5654,25.0330,'Taipei, Taiwan'),
    'bengaluru':(77.5946,12.9716,'Bengaluru, India'),'bangalore':(77.5946,12.9716,'Bengaluru, India'),
    'mumbai':(72.8777,19.0760,'Mumbai, India'),'delhi':(77.1025,28.7041,'Delhi, India'),
    'hyderabad':(78.4867,17.3850,'Hyderabad, India'),'pune':(73.8567,18.5204,'Pune, India'),
    'chennai':(80.2707,13.0827,'Chennai, India'),'dubai':(55.2708,25.2048,'Dubai, United Arab Emirates'),
    'tel aviv':(34.7818,32.0853,'Tel Aviv, Israel'),'istanbul':(28.9784,41.0082,'Istanbul, Turkey'),
    'kuala lumpur':(101.6869,3.1390,'Kuala Lumpur, Malaysia'),'bangkok':(100.5018,13.7563,'Bangkok, Thailand'),
    'jakarta':(106.8456,-6.2088,'Jakarta, Indonesia'),'manila':(120.9842,14.5995,'Manila, Philippines'),
    'sydney':(151.2093,-33.8688,'Sydney, Australia'),'melbourne':(144.9631,-37.8136,'Melbourne, Australia'),
    'auckland':(174.7633,-36.8485,'Auckland, New Zealand'),
    # Africa / Latin America
    'lagos':(3.3792,6.5244,'Lagos, Nigeria'),'nairobi':(36.8219,-1.2921,'Nairobi, Kenya'),
    'johannesburg':(28.0473,-26.2041,'Johannesburg, South Africa'),'cape town':(18.4241,-33.9249,'Cape Town, South Africa'),
    'cairo':(31.2357,30.0444,'Cairo, Egypt'),'casablanca':(-7.5898,33.5731,'Casablanca, Morocco'),
    'accra':(-0.1870,5.6037,'Accra, Ghana'),'sao paulo':(-46.6333,-23.5505,'São Paulo, Brazil'),
    'são paulo':(-46.6333,-23.5505,'São Paulo, Brazil'),'buenos aires':(-58.3816,-34.6037,'Buenos Aires, Argentina'),
    'santiago':(-70.6693,-33.4489,'Santiago, Chile'),'bogota':(-74.0721,4.7110,'Bogotá, Colombia'),
    'bogotá':(-74.0721,4.7110,'Bogotá, Colombia'),'lima':(-77.0428,-12.0464,'Lima, Peru'),
}
_STATS_MAP_SAFE_COUNTRY_CENTROIDS={'Singapore','Hong Kong','Taiwan','Netherlands','Belgium','Switzerland','Ireland','United Kingdom','Israel','United Arab Emirates','Qatar','Kuwait','Luxembourg','Denmark','Czechia','Austria','Slovakia','Slovenia','Portugal'}
_STATS_MAP_BROAD_LABELS={'Worldwide','Global','Unknown','Africa','North America','South America','Americas','LATAM','Central America','Caribbean','Europe','EU','EEA','EU/EEA','UK & Europe','UK & Ireland','DACH','CEE','Benelux','Nordics','APAC','ASEAN','ANZ','Asia','EMEA','MENA','GCC','Middle East'}
_STATS_MAP_LARGE_COUNTRY_CENTROIDS={'United States','Canada','Russia','China','India','Australia','Brazil','Mexico','Indonesia','Argentina','Chile','South Africa'}


def _stats_map_word(term):
    return r'(?<![A-Za-z0-9])'+re.escape(str(term or '').casefold()).replace('\\ ', r'[-\s]+')+r'(?![A-Za-z0-9])'


def _stats_project_geo(lon, lat, label, *, source='direct'):
    try:
        lon=float(lon); lat=float(lat)
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            return {}
        x,y=world_project(lon,lat)
        return {'label':_stats_map_truncate(label or f'{lat:.4f}, {lon:.4f}',80),'lon':round(lon,6),'lat':round(lat,6),'x':x,'y':y,'source':source,'precise':True}
    except Exception:
        return {}


def _stats_structured_coordinate_point(*values):
    """Extract explicit lat/lon evidence already retained in location payloads."""
    seen=set()

    def walk(node, depth=0, fallback=''):
        if depth>7 or node is None:
            return {}
        marker=id(node) if isinstance(node,(dict,list,tuple)) else None
        if marker is not None:
            if marker in seen:
                return {}
            seen.add(marker)
        if isinstance(node,dict):
            lat=node.get('latitude',node.get('lat'))
            lon=node.get('longitude',node.get('lon',node.get('lng')))
            if lat not in (None,'') and lon not in (None,''):
                address=node.get('address') if isinstance(node.get('address'),dict) else {}
                parts=[address.get('addressLocality'),address.get('addressRegion'),address.get('addressCountry')]
                label=', '.join(str(x).strip() for x in parts if str(x or '').strip())
                label=label or str(node.get('label') or node.get('name') or fallback or '').strip()
                point=_stats_project_geo(lon,lat,label or 'Explicit coordinates',source='structured_location')
                if point:
                    return point
            child_fallback=str(node.get('label') or node.get('name') or fallback or '').strip()
            for child in node.values():
                point=walk(child,depth+1,child_fallback)
                if point:
                    return point
            return {}
        if isinstance(node,(list,tuple)):
            for child in node:
                point=walk(child,depth+1,fallback)
                if point:
                    return point
            return {}
        if isinstance(node,str):
            raw=node.strip()
            if not raw or len(raw)>12000:
                return {}
            if raw[:1] in ('{','['):
                try:
                    decoded=json.loads(raw)
                except Exception:
                    decoded=None
                if decoded is not None:
                    point=walk(decoded,depth+1,fallback)
                    if point:
                        return point
            # Some retained evidence embeds a JSON fragment inside a larger string.
            lat_m=re.search(r'["\']?(?:latitude|lat)["\']?\s*[:=]\s*([+-]?\d+(?:\.\d+)?)',raw,re.I)
            lon_m=re.search(r'["\']?(?:longitude|lon|lng)["\']?\s*[:=]\s*([+-]?\d+(?:\.\d+)?)',raw,re.I)
            if lat_m and lon_m:
                labels=_stats_record_locations(raw)
                point=_stats_project_geo(lon_m.group(1),lat_m.group(1),labels[0] if labels else (fallback or 'Explicit coordinates'),source='structured_location')
                if point:
                    return point
        return {}

    for value in values:
        point=walk(value)
        if point:
            return point
    return {}


def _stats_direct_location_point(*values):
    explicit=_stats_structured_coordinate_point(*values)
    if explicit:
        return explicit
    text=' '.join(str(v or '') for v in values if v)[:5000].casefold()
    if text:
        for name,(lon,lat,label) in sorted(_STATS_MAP_PLACE_POINTS.items(),key=lambda item:len(item[0]),reverse=True):
            if re.search(_stats_map_word(name), text, flags=re.I):
                return _stats_project_geo(lon,lat,label,source='text')
    for value in values:
        for label in _stats_record_locations(value):
            if label in _STATS_MAP_SAFE_COUNTRY_CENTROIDS:
                point=world_location_point(label)
                if point:
                    point=dict(point); point['precise']=False; point['source']='compact_country'
                    return point
    return {}


def _stats_map_cache_container(record):
    if hasattr(record,'ai_state'):
        return 'ai_state'
    if hasattr(record,'company_intel'):
        return 'company_intel'
    return ''


def _stats_map_evidence_fingerprint(*values):
    """Stable fingerprint for the location evidence used to place a map record."""
    parts=[]
    for value in values:
        if isinstance(value,(dict,list,tuple)):
            try:
                text=json.dumps(value,sort_keys=True,ensure_ascii=False,default=str)
            except Exception:
                text=str(value or '')
        else:
            text=str(value or '')
        text=' '.join(text.split()).strip().casefold()
        if text:
            parts.append(text)
    raw=' | '.join(parts)[:12000]
    return hashlib.sha1(raw.encode('utf-8')).hexdigest() if raw else ''


def _stats_map_cached_point(record, fingerprint=''):
    field=_stats_map_cache_container(record)
    data=getattr(record,field,{}) if field else {}
    if not isinstance(data,dict):
        return {}
    geo=data.get(_STATS_MAP_CACHE_KEY)
    if not isinstance(geo,dict) or geo.get('status')!='ok':
        return {}
    if fingerprint and str(geo.get('evidence_fingerprint') or '') != fingerprint:
        return {}
    return _stats_project_geo(geo.get('lon'),geo.get('lat'),geo.get('label') or geo.get('location') or 'Resolved location',source='ai_cache')


def _stats_map_has_recent_unresolved(record, fingerprint=''):
    field=_stats_map_cache_container(record)
    data=getattr(record,field,{}) if field else {}
    geo=data.get(_STATS_MAP_CACHE_KEY) if isinstance(data,dict) else None
    if not isinstance(geo,dict) or geo.get('status')!='unresolved':
        return False
    if fingerprint and str(geo.get('evidence_fingerprint') or '') != fingerprint:
        return False
    raw=geo.get('attempted_at') or ''
    try:
        dt=datetime.fromisoformat(str(raw).replace('Z','+00:00'))
        if timezone.is_naive(dt): dt=timezone.make_aware(dt, timezone.get_current_timezone())
        return dt >= timezone.now()-timedelta(hours=_STATS_MAP_UNRESOLVED_HOURS)
    except Exception:
        return False


def _stats_map_store_geo(record, geo, fingerprint=''):
    field=_stats_map_cache_container(record)
    if not field:
        return
    data=getattr(record,field,{})
    if not isinstance(data,dict):
        data={}
    data=dict(data)
    payload=dict(geo or {}, updated_at=timezone.now().isoformat())
    if fingerprint:
        payload['evidence_fingerprint']=fingerprint
    data[_STATS_MAP_CACHE_KEY]=payload
    setattr(record,field,data)
    try:
        record.save(update_fields=[field,'updated_at'] if hasattr(record,'updated_at') else [field])
    except Exception:
        logger.exception('Failed to store Statistics map coordinate cache')


def _stats_map_store_unresolved(record, reason='unresolved', fingerprint=''):
    _stats_map_store_geo(record, {'status':'unresolved','reason':str(reason or 'unresolved')[:160],'attempted_at':timezone.now().isoformat()}, fingerprint=fingerprint)


def _stats_map_record_point(record, labels, *, salt='', raw_values=()):
    fingerprint=_stats_map_evidence_fingerprint(*raw_values, *labels)
    cached=_stats_map_cached_point(record, fingerprint)
    if cached:
        return _stats_jittered_point(cached, salt)
    direct=_stats_direct_location_point(*raw_values, *labels)
    if direct:
        return _stats_jittered_point(direct, salt)
    return {}


def _stats_map_geo_is_specific(label):
    text=_stats_map_truncate(label,120).strip(' .,:;|/\\')
    if not text:
        return False
    head=text.split(',')[0].strip()
    if text in _STATS_MAP_BROAD_LABELS or text in _STATS_MAP_LARGE_COUNTRY_CENTROIDS:
        return False
    if head in _STATS_MAP_BROAD_LABELS or head in WORLD_COUNTRY_POINTS:
        return False
    return bool(len(head)>=3)


def _stats_parse_geo_json(text):
    raw=str(text or '').strip()
    if not raw:
        return {}
    m=re.search(r'```(?:json)?\s*(.*?)```', raw, re.I|re.S)
    if m:
        raw=m.group(1).strip()
    try:
        data=json.loads(raw)
    except Exception:
        m=re.search(r'\{.*\}', raw, re.S)
        if not m:
            return {}
        try:
            data=json.loads(m.group(0))
        except Exception:
            return {}
    return data if isinstance(data,dict) else {}


def _stats_location_evidence_text(value):
    text=unicodedata.normalize('NFKD',str(value or '')).encode('ascii','ignore').decode('ascii').casefold()
    return re.sub(r'[^a-z0-9]+',' ',text).strip()


def _stats_location_label_supported(label, details):
    """Require resolved city/region and country to be present in location evidence."""
    parts=[_stats_location_evidence_text(x) for x in str(label or '').split(',') if _stats_location_evidence_text(x)]
    haystack=_stats_location_evidence_text(details)
    if not parts or len(parts[0])<3 or not haystack:
        return False
    def present(value):
        return re.search(r'(?<![a-z0-9])'+re.escape(value)+r'(?![a-z0-9])',haystack) is not None
    if not present(parts[0]):
        return False
    # The final component is normally a country. Requiring it when present prevents
    # same-city-name coordinates from silently drifting to a different country.
    if len(parts)>1 and len(parts[-1])>=3 and not present(parts[-1]):
        return False
    return True


def _stats_ai_resolve_map_geo(kind, title, labels, details, url=''):
    route=route_for_stage('company_enrichment') or route_for_stage('page_summarization') or route_for_stage('first_filter')
    provider=str((route or {}).get('provider') or '').strip()
    model=str((route or {}).get('model') or '').strip()
    if not provider or not model:
        return {}, 'no configured AI route'
    prompt=(
        'Return JSON only. Determine a precise map coordinate for this ScoutBox record. '
        'Use only the supplied LOCATION EVIDENCE. Do not infer from the company/name, URL, outside knowledge, or unrelated page content. '
        'The returned city/region must be explicitly written in the supplied location evidence. Do not use a country, continent, broad region, or worldwide centroid. '
        'If the location evidence does not identify a reasonably specific city, state/province, or office location, return {"ok":false}. '
        'JSON schema: {"ok":boolean,"label":"City/region, Country","lat":number,"lon":number,"confidence":integer,"reason":"brief"}.\n'
        f'Type: {kind}\nKnown location labels: {", ".join(labels) or "unknown"}\nLocation evidence: {_stats_map_truncate(details,900)}'
    )
    try:
        raw=generate_with(provider,model,prompt,stage='company_enrichment',timeout=24,subject='Statistics map coordinate',limits_override={'max_output_tokens':220})
    except Exception as exc:
        logger.info('Statistics map AI coordinate failed: %s', exc)
        return {}, str(exc)[:160]
    data=_stats_parse_geo_json(raw)
    if not data or not data.get('ok'):
        return {}, (data.get('reason') if isinstance(data,dict) else '') or 'not specific enough'
    label=_stats_map_truncate(data.get('label') or data.get('location') or '',100)
    if not _stats_map_geo_is_specific(label):
        return {}, 'AI returned a non-specific location'
    if not _stats_location_label_supported(label, details):
        return {}, 'AI location was not explicitly supported by location evidence'
    try:
        conf=int(data.get('confidence') or 0)
    except Exception:
        conf=0
    if conf < 65:
        return {}, 'AI confidence too low'
    point=_stats_project_geo(data.get('lon'),data.get('lat'),label,source='ai')
    if not point:
        return {}, 'invalid coordinates'
    return {**point,'status':'ok','confidence':conf,'reason':_stats_map_truncate(data.get('reason'),160)}, ''


def _stats_jittered_point(point, salt):
    if not point:
        return {}
    out=dict(point)
    # Precise coordinates must stay on their real map position. Earlier releases
    # jittered every marker to reduce overlap, which could visibly move a city-level
    # point into a neighbouring region or offshore. Only coarse centroid points spread.
    if out.get('precise') is True:
        return out
    label=str(out.get('label') or '')
    try:
        digest=hashlib.sha1(str(salt or label).encode('utf-8')).digest()
        angle=(int.from_bytes(digest[:2],'big')/65535.0)*math.pi*2
        # Keep shared regional/world points usable without stacking every marker exactly together.
        base_radius=8 if label.casefold() in {'worldwide','global','unknown'} else 3
        spread=22 if label.casefold() in {'worldwide','global','unknown'} else 10
        radius=base_radius+(digest[2] % spread)
        out['x']=round(max(8,min(1432,float(out.get('x') or 0)+math.cos(angle)*radius)),1)
        out['y']=round(max(8,min(712,float(out.get('y') or 0)+math.sin(angle)*radius)),1)
    except Exception:
        pass
    return out


def _stats_first_map_point(labels, salt):
    for location in labels[:8]:
        if location in _STATS_MAP_BROAD_LABELS or location in _STATS_MAP_LARGE_COUNTRY_CENTROIDS:
            continue
        if location not in _STATS_MAP_SAFE_COUNTRY_CENTROIDS:
            continue
        point=world_location_point(location)
        if point:
            return _stats_jittered_point(point, salt)
    return {}


_BLACKLIST_TLD_LOCATIONS={
    'au':'Australia','br':'Brazil','ca':'Canada','ch':'Switzerland','cn':'China','de':'Germany','dk':'Denmark','es':'Spain','eu':'Europe','fi':'Finland','fr':'France','hk':'Hong Kong','ie':'Ireland','in':'India','it':'Italy','jp':'Japan','kr':'South Korea','mx':'Mexico','my':'Malaysia','nl':'Netherlands','no':'Norway','nz':'New Zealand','ph':'Philippines','pl':'Poland','ru':'Russia','se':'Sweden','sg':'Singapore','uk':'United Kingdom','us':'United States','za':'South Africa'
}


def _stats_blacklist_locations(row):
    # Do not infer map coordinates from TLDs, company names, reasons, or broad defaults.
    # Blacklist rows have no dedicated location field, so only matched ScoutBox records
    # with retained location evidence are allowed to place a blacklist marker.
    return []


def _stats_blacklist_evidence_index(company_labels=None, domain_keys=None):
    """Return evidence-grounded map points for blacklist companies/domains.

    Blacklist rows do not carry a location field of their own. 0.11.42 correctly
    stopped guessing from TLDs/country centroids, but that also left the layer empty
    for normal company-name rules. Reuse locations already retained on Opportunities,
    Hidden Leads and Address Book records instead. Company matching uses the same
    conservative blacklist key and domain review logic as blacklist enforcement, so a
    LinkedIn/ATS listing URL cannot accidentally become a company's map location.
    """
    labels={str(x or '').strip() for x in (company_labels or ()) if str(x or '').strip()}
    wanted_companies={normalize_company_blacklist_key(x) for x in labels if normalize_company_blacklist_key(x)}
    wanted_domains={normalize_pattern(x) for x in (domain_keys or ()) if normalize_pattern(x)}
    by_company={}; by_domain={}
    if not wanted_companies and not wanted_domains:
        return {'company':by_company,'domain':by_domain}

    def add(record, location_labels, raw_values, source_label):
        company_key=normalize_company_blacklist_key(getattr(record,'company',''))
        try:
            domain_key=normalize_pattern(company_specific_blacklist_review_domain_for_record(record))
        except Exception:
            domain_key=''
        if company_key not in wanted_companies and domain_key not in wanted_domains:
            return
        point=_stats_map_cached_point(record, _stats_map_evidence_fingerprint(*raw_values, *location_labels)) or _stats_direct_location_point(*raw_values, *location_labels)
        if not point:
            return
        evidence={'point':dict(point),'labels':list(location_labels),'source':source_label}
        if company_key and company_key not in by_company:
            by_company[company_key]=evidence
        if domain_key and domain_key not in by_domain:
            by_domain[domain_key]=evidence

    company_q=Q()
    for label in labels:
        company_q |= Q(company__iexact=label)

    opp_q=company_q
    for domain in wanted_domains:
        opp_q |= Q(url__icontains=domain)|Q(target_url__icontains=domain)|Q(canonical_url__icontains=domain)|Q(search_url__icontains=domain)
    if opp_q:
        for row in Opportunity.objects.filter(opp_q).exclude(company='').only(
            'pk','company','country','locations','role_location','url','target_url','canonical_url','search_url',
            'company_intel','extracted_facts','ai_state','updated_at'
        ).order_by('-updated_at')[:4000]:
            location_labels=_stats_record_map_locations(row)
            add(row,location_labels,(row.role_location,row.locations,row.country),'Opportunity')

    lead_q=company_q
    for domain in wanted_domains:
        lead_q |= Q(target_url__icontains=domain)|Q(source_url__icontains=domain)|Q(search_url__icontains=domain)|Q(contact_url__icontains=domain)
    if lead_q:
        for row in CompanyLead.objects.filter(lead_q).exclude(company='').only(
            'pk','company','country','locations','target_url','source_url','search_url','contact_url','company_intel','ai_state','updated_at'
        ).order_by('-updated_at')[:3000]:
            location_labels=_stats_record_map_locations(row)
            add(row,location_labels,(row.locations,row.country),'Hidden Lead')

    contact_q=company_q
    for domain in wanted_domains:
        contact_q |= Q(source_url__icontains=domain)
    if contact_q:
        for row in Contact.objects.filter(contact_q).exclude(company='').only(
            'pk','company','company_country','company_locations','source_url','company_intel','last_seen'
        ).order_by('-last_seen')[:2000]:
            location_labels=_stats_record_map_locations(row)
            add(row,location_labels,(row.company_locations,row.company_country),'Address Book')
    return {'company':by_company,'domain':by_domain}

def _stats_blacklist_evidence(row, index):
    company_key=normalize_company_blacklist_key(getattr(row,'label',''))
    domain_key=normalize_pattern(getattr(row,'domain',''))
    return (index.get('company',{}).get(company_key) if company_key else None) or (index.get('domain',{}).get(domain_key) if domain_key else None) or {}


def _stats_add_record_point(points, labels, *, salt, title, url='', count=1, tooltip_lines=None, target_url='', point=None, record_item=None):
    point=point or _stats_first_map_point(labels, salt)
    if not point:
        return False
    location_label=_stats_map_truncate(point.get('label') or (labels[0] if labels else 'Unknown'))
    point['id']=str(salt or '')[:80]
    point['title']=_stats_map_truncate(title)
    point['location']=location_label
    point['url']=url
    point['target_url']=_stats_public_url(target_url)
    point['count']=int(count or 1)
    lines=[line for line in (tooltip_lines or []) if line]
    if not lines:
        lines=[_stats_map_line('Name', title), _stats_map_line('Location', location_label)]
    point['tooltip']='\n'.join(lines[:8])
    item=dict(record_item or {})
    if not item:
        item={'label':_stats_map_truncate(title,120),'date':'','url':url}
    item['label']=_stats_map_truncate(item.get('label') or title,120)
    item['date']=_stats_map_truncate(item.get('date') or '',40)
    item['url']=str(item.get('url') or url or '')
    item['id']=str(item.get('id') or '').strip()[:24]
    point['items']=[item]
    points.append(point)
    return True


def _stats_aggregate_map_points(points, *, radius=12.0):
    """Collapse markers that would visually occupy the same map area.

    Each representative marker retains the number of underlying records so the legend
    can report how many records are actually represented on the map, even when several
    records share one visual pin.
    """
    grouped=[]
    for raw in (points or []):
        if not raw:
            continue
        point=dict(raw)
        try:
            x=float(point.get('x')); y=float(point.get('y'))
        except Exception:
            continue
        match=None
        for existing in grouped:
            try:
                dx=x-float(existing.get('x')); dy=y-float(existing.get('y'))
            except Exception:
                continue
            if (dx*dx+dy*dy) ** .5 <= radius:
                match=existing; break
        if match is None:
            point['count']=max(1,int(point.get('count') or 1))
            grouped.append(point)
            continue
        match['count']=int(match.get('count') or 1)+max(1,int(point.get('count') or 1))
        merged_items=list(match.get('items') or [])
        for item in (point.get('items') or []):
            if len(merged_items)>=25:
                break
            key=(str(item.get('url') or ''),str(item.get('label') or ''),str(item.get('date') or ''))
            if not any((str(x.get('url') or ''),str(x.get('label') or ''),str(x.get('date') or ''))==key for x in merged_items):
                merged_items.append(item)
        match['items']=merged_items
    return grouped


def _stats_geo_layer(key, label, points, *, total=None):
    visible=[p for p in points if p]
    count=int(total if total is not None else sum(int(x.get('count') or 1) for x in visible))
    displayed=_stats_aggregate_map_points(visible)[:800]
    mapped_count=sum(max(1,int(x.get('count') or 1)) for x in displayed)
    return {'key':key,'label':label,'count':count,'mapped_count':mapped_count,'points':displayed}


def _statistics_world_map_payload(opportunities, leads, contacts, applications, *, start=None, end=None, q=''):
    # Applications & Outreach intentionally stays out of the Global Activity Map.
    # Those rows are already derived from Opportunities/Hidden Leads and plotting them here
    # double-counts the same real-world activity while adding a redundant legend layer.
    buckets={k:[] for k in ('opportunities','hidden_leads','contacts','blacklist')}
    for row in opportunities.only('pk','title','company','country','locations','role_location','url','status','fit_score','created_at')[:800]:
        labels=_stats_record_map_locations(row)
        title=f"{row.company} — {row.title}" if row.company else (row.title or f"Opportunity #{row.pk}")
        status=dict(Opportunity.STATUS).get(row.status,row.status or '') if hasattr(row,'status') else ''
        tooltip=[_stats_map_line('Opportunity', title),_stats_map_line('Location', ', '.join(labels) or 'Unknown'),_stats_map_line('Date added', _stats_map_date(getattr(row,'created_at',None)))]
        point=_stats_map_record_point(row,labels,salt=f"opp:{row.pk}",raw_values=(row.role_location,row.locations,row.country))
        _stats_add_record_point(buckets['opportunities'],labels,salt=f"opp:{row.pk}",title=title,url=reverse('opportunity_detail',args=[row.pk]),target_url=getattr(row,'url',''),tooltip_lines=tooltip,point=point,record_item={'id':row.pk,'label':title,'date':_stats_map_date(getattr(row,'created_at',None)),'url':reverse('opportunity_detail',args=[row.pk])})
    for row in leads.only('pk','company','country','locations','target_url','source_url','search_url','score','created_at')[:800]:
        labels=_stats_record_map_locations(row)
        title=row.company or f"Hidden Lead #{row.pk}"
        tooltip=[_stats_map_line('Hidden Lead', title),_stats_map_line('Location', ', '.join(labels) or 'Unknown'),_stats_map_line('Date added', _stats_map_date(getattr(row,'created_at',None)))]
        point=_stats_map_record_point(row,labels,salt=f"lead:{row.pk}",raw_values=(row.locations,row.country))
        _stats_add_record_point(buckets['hidden_leads'],labels,salt=f"lead:{row.pk}",title=title,url=reverse('hidden_lead_detail',args=[row.pk]),target_url=(getattr(row,'target_url','') or getattr(row,'source_url','') or getattr(row,'search_url','')),tooltip_lines=tooltip,point=point,record_item={'id':row.pk,'label':title,'date':_stats_map_date(getattr(row,'created_at',None)),'url':reverse('hidden_lead_detail',args=[row.pk])})
    for row in contacts.only('pk','email','name','company','title','source_url','company_country','company_locations','created_at')[:800]:
        labels=_stats_record_map_locations(row)
        bits=[x for x in (row.name,row.company,row.email) if x]
        title=' — '.join(bits[:2]) if bits else f"Contact #{row.pk}"
        tooltip=[
            _stats_map_line('Contact', title),
            _stats_map_line('Email', row.email),
            _stats_map_line('Title', row.title),
            _stats_map_line('Location', ', '.join(labels) or 'Unknown'),
            _stats_map_line('Date added', _stats_map_date(getattr(row,'created_at',None))),
        ]
        point=_stats_map_record_point(row,labels,salt=f"contact:{row.pk}",raw_values=(row.company_locations,row.company_country))
        edit_url=reverse('contacts')+'?edit='+str(row.pk)
        _stats_add_record_point(buckets['contacts'],labels,salt=f"contact:{row.pk}",title=title,url=edit_url,target_url=getattr(row,'source_url',''),tooltip_lines=tooltip,point=point,record_item={'id':row.pk,'label':title,'date':_stats_map_date(getattr(row,'created_at',None)),'url':edit_url})
    blacklisted=SourceBlacklist.objects.filter(deleted_at__isnull=True)
    if start:
        blacklisted=blacklisted.filter(created_at__gte=start)
    if end:
        blacklisted=blacklisted.filter(created_at__lt=end)
    if q:
        blacklisted=blacklisted.filter(Q(domain__icontains=q)|Q(label__icontains=q)|Q(reason__icontains=q)|Q(scope__icontains=q))
    blacklist_total=blacklisted.count()
    blacklist_rows=list(blacklisted.only('pk','domain','label','reason','scope','enabled','created_at')[:800])
    company_labels={str(row.label or '').strip() for row in blacklist_rows if str(row.label or '').strip()}
    # Domain lookup is only needed for true domain-only rules. Named rules are matched
    # through the company identity, which avoids turning a job-board URL into evidence.
    domain_keys={normalize_pattern(row.domain) for row in blacklist_rows if row.domain and (not row.label or normalize_pattern(row.label)==normalize_pattern(row.domain))}
    blacklist_evidence=_stats_blacklist_evidence_index(company_labels,domain_keys) if blacklist_rows else {'company':{},'domain':{}}
    for row in blacklist_rows:
        labels=_stats_blacklist_locations(row)
        name=(row.label or row.domain or f'Blacklist #{row.pk}')
        display_url=('https://'+row.domain.strip()) if row.domain and not str(row.domain).startswith(('http://','https://')) else str(row.domain or '')
        scope=dict(SourceBlacklist.SCOPE).get(row.scope,row.scope or '') if hasattr(row,'scope') else ''
        point={}
        evidence=_stats_blacklist_evidence(row,blacklist_evidence)
        if evidence.get('point'):
            point=_stats_jittered_point(evidence['point'],f"blacklist:{row.pk}")
            labels=evidence.get('labels') or labels
        location_label=(point or {}).get('label') or (', '.join(labels) if labels else 'Location unavailable')
        tooltip=[
            _stats_map_line('Blacklist', name),
            _stats_map_line('Location', location_label),
            _stats_map_line('Location source', ('Matched '+str(evidence.get('source'))+' record') if evidence else 'Blacklist entry'),
            _stats_map_line('Scope', scope),
            _stats_map_line('Date added', _stats_map_date(getattr(row,'created_at',None))),
            _stats_map_line('Reason', getattr(row,'reason',''), 120),
        ]
        edit_url=reverse('blacklist')+'?edit='+str(row.pk)
        _stats_add_record_point(buckets['blacklist'],labels,salt=f"blacklist:{row.pk}",title=name,url=edit_url,target_url=display_url,tooltip_lines=tooltip,point=point,record_item={'id':row.pk,'label':name,'date':_stats_map_date(getattr(row,'created_at',None)),'url':edit_url})
    return {
        'viewBox': {'width':1440,'height':720},
        'layers': [
            _stats_geo_layer('opportunities','Opportunities',buckets['opportunities'],total=opportunities.count()),
            _stats_geo_layer('hidden_leads','Hidden Leads',buckets['hidden_leads'],total=leads.count()),
            _stats_geo_layer('contacts','Contact',buckets['contacts'],total=contacts.count()),
            _stats_geo_layer('blacklist','Blacklist',buckets['blacklist'],total=blacklist_total),
        ],
    }

def _apply_focus_filters(qs, values, mode='all'):
    if mode=='custom' and not values:
        return qs.none()
    if mode!='custom':
        return qs
    condition=Q()
    for focus in values:
        focus=str(focus or '').strip()
        if not focus:
            continue
        if focus.casefold()=='unclassified':
            condition |= (Q(focus='') | Q(focus__isnull=True) | Q(focus__iexact='Unclassified'))
        else:
            condition |= Q(focus=focus)
    return qs.filter(condition) if condition else qs.none()


def _apply_country_filters(qs, field, values, mode='all'):
    if mode=='custom' and not values:
        return qs.none()
    if mode!='custom':
        return qs
    condition=Q()
    for value in values:
        canonical=_canonical_country_name(value)
        if not canonical:
            continue
        country_values=_country_filter_values(canonical)
        if field=='country' and getattr(getattr(qs,'model',None),'__name__','')=='Opportunity':
            malformed_role = (
                Q(role_location__startswith='[') |
                Q(role_location__startswith='{') |
                Q(role_location__icontains='"@type"') |
                Q(role_location__icontains="'@type'")
            )
            condition |= (_country_condition('role_location',country_values) & ~malformed_role)
            condition |= (_country_condition('country',country_values) & (Q(role_location__isnull=True)|Q(role_location='')))
        else:
            condition |= _country_condition(field,country_values)
    return qs.filter(condition) if condition else qs.none()


def _apply_campaign_filters(qs, values, mode='all'):
    if mode=='custom' and not values:
        return qs.none()
    if mode!='custom':
        return qs
    ids=[int(x) for x in values if str(x).isdigit() or isinstance(x,int)]
    if not ids:
        return qs.none()
    return qs.filter(Q(origin_campaign_id__in=ids)|Q(campaigns__pk__in=ids))


def _selected_labels(options, values, value_key='value', label_key='label'):
    wanted={str(v) for v in (values or [])}
    labels=[]
    for row in options or []:
        if isinstance(row,dict):
            value=row.get(value_key)
            label=row.get(label_key) or value
        else:
            value=getattr(row,value_key,'')
            label=getattr(row,label_key,'') or value
        if str(value) in wanted:
            labels.append(str(label))
    return labels

def _opportunity_re_evaluate_ids(request, local_only=False, cloud_only=False):
    """IDs matching the current Opportunity list filters, optionally filtered by Fit provenance."""
    qs=Opportunity.objects.filter(suppressed=False,user_deleted=False)
    q=_q(request)
    if q:
        visible_match=(
            Q(title__icontains=q)|Q(company__icontains=q)|Q(country__icontains=q)|Q(role_location__icontains=q)|
            Q(contact_email__icontains=q)|Q(note__icontains=q)|Q(remote_text__icontains=q)|Q(list_highlight__icontains=q)|
            Q(freshness_label__icontains=q)|Q(salary_text__icontains=q)|
            Q(target_url__icontains=q)|Q(url__icontains=q)
        )
        qs=qs.filter(visible_match)
    qs,_=_apply_advanced_opportunity_filters(qs,request)
    focus_state=_request_multi_filter_state(request,'focus')
    country_state=_request_multi_filter_state(request,'country',canonicalizer=_canonical_country_name)
    campaign_state=_request_multi_filter_state(request,'campaign',integer=True)
    channel_filter=(request.GET.get('channel') or '').strip()
    read_state=(request.GET.get('read') or '').strip().lower()
    hide_non_200=(request.GET.get('healthy') or '')=='1'
    source=(request.GET.get('source') or '').strip()
    qs=_apply_focus_filters(qs, focus_state['values'], focus_state['mode'])
    if channel_filter: qs=qs.filter(channel=channel_filter)
    if read_state=='unread': qs=qs.filter(is_read=False)
    elif read_state=='read': qs=qs.filter(is_read=True)
    if hide_non_200: qs=qs.filter(Q(contact_email__gt='')|Q(target_http_status=200))
    qs=_apply_campaign_filters(qs,campaign_state['values'],campaign_state['mode'])
    if source: qs=qs.filter(source_id=source)
    qs=_apply_country_filters(qs,'country',country_state['values'],country_state['mode'])
    qs=qs.distinct()
    if local_only or cloud_only:
        rows=qs.select_related('source').only('pk','extracted_facts','company_intel','source__name')
        return _local_assessment_ids(rows) if local_only else _cloud_assessment_ids(rows)
    return list(qs.values_list('pk',flat=True))


def _hidden_lead_re_evaluate_ids(request, local_only=False, cloud_only=False):
    """IDs matching the current Hidden Leads list filters, optionally filtered by Fit provenance."""
    qs=CompanyLead.objects.filter(user_deleted=False).prefetch_related('campaigns').order_by('-created_at','-pk')
    # This probe needs no related rows. Strip relation loading before only() so this
    # helper stays safe if its base QuerySet gains select_related fields later.
    noisy_probe=qs.select_related(None).prefetch_related(None).only('pk','company','target_url','source_url','evidence')
    noisy_ids=[x.pk for x in noisy_probe if is_general_market_company(x.company) or is_general_market_host(x.target_url) or is_general_market_host(x.source_url) or any(is_documentation_like(url,'',x.evidence) for url in (x.target_url,x.source_url) if url)]
    if noisy_ids: qs=qs.exclude(pk__in=noisy_ids,user_deleted=False)
    q=_q(request)
    if q:
        visible_match=(
            Q(company__icontains=q)|Q(summary__icontains=q)|Q(contact_email__icontains=q)|Q(contact_url__icontains=q)|
            Q(country__icontains=q)|Q(note__icontains=q)|Q(target_url__icontains=q)|Q(source_url__icontains=q)
        )
        qs=qs.filter(visible_match)
    company_size_filter,company_age_filter,contact_method_filter=_company_filter_state(request,'hidden_lead')
    qs=_apply_company_info_quick_filter(qs,company_size_filter,company_age_filter,contact_method_filter)
    campaign_state=_request_multi_filter_state(request,'campaign',integer=True)
    country_state=_request_multi_filter_state(request,'country',canonicalizer=_canonical_country_name)
    focus_state=_request_multi_filter_state(request,'focus')
    hide_non_200=(request.GET.get('healthy') or '')=='1'
    read_state=(request.GET.get('read') or '').strip().lower()
    qs=_apply_campaign_filters(qs,campaign_state['values'],campaign_state['mode'])
    if hide_non_200: qs=qs.filter(target_http_status=200)
    qs=_apply_country_filters(qs,'country',country_state['values'],country_state['mode'])
    qs=_apply_focus_filters(qs, focus_state['values'], focus_state['mode'])
    if read_state=='unread': qs=qs.filter(is_read=False)
    elif read_state=='read': qs=qs.filter(is_read=True)
    # Match the list's legacy duplicate suppression: one row per normalized company.
    ids=[]; seen=set()
    for lead in qs.distinct():
        key=re.sub(r'[^a-z0-9]+','',str(lead.company or '').lower()) or f'lead{lead.pk}'
        if key in seen: continue
        seen.add(key); ids.append(lead.pk)
    if local_only or cloud_only:
        rows=list(CompanyLead.objects.filter(pk__in=ids).select_related('source').only('pk','ai_state','company_intel','source__name'))
        scoped=set(_local_assessment_ids(rows) if local_only else _cloud_assessment_ids(rows))
        ids=[pk for pk in ids if pk in scoped]
    return ids


@login_required
def opportunities_view(request):
    # An explicit advanced-filter reset clears the session-persisted state, then returns a
    # clean URL so the reset marker itself does not leak into paging/navigation links.
    if request.method=='GET' and request.GET.get('adv_reset')=='1':
        request.session.pop(_ADV_OPPORTUNITY_SESSION_KEY,None); request.session.modified=True
        params=request.GET.copy(); params.pop('adv_reset',None)
        target=request.path + (('?' + params.urlencode()) if params else '')
        return redirect(target)
    # 0.8.87: list views are read-only. Never recycle/dedupe records merely because a user opened a page.
    if request.method == 'POST' and request.POST.get('action') in ('delete_selected','blacklist_selected','filter_selected','mark_unread','mark_read','mark_all_read','mark_all_unread','restore_row'):
        action=request.POST.get('action')
        if action=='restore_row':
            row_id=(request.POST.get('row_id') or '').strip()
            ok,label=_restore_recycle_item('opportunity',int(row_id)) if row_id.isdigit() else (False,'Opportunity')
            if request.headers.get('X-Requested-With')=='fetch':
                return JsonResponse({'ok':ok,'label':label,'error':'' if ok else 'This opportunity is not in the Recycle Bin.'},status=200 if ok else 404)
            (messages.success if ok else messages.warning)(request,(f'Restored {label}.' if ok else 'This opportunity is not in the Recycle Bin.'))
            return redirect(request.get_full_path())
        ids=[x for x in request.POST.getlist('opportunity_ids') if str(x).isdigit()]
        filter_scope=(request.POST.get('filter_scope') or '').strip().lower()
        filter_all=(request.POST.get('filter_all') or '')=='1' or filter_scope in {'all','local','cloud'}
        filter_local=filter_scope=='local'
        filter_cloud=filter_scope=='cloud'
        if action in ('mark_all_read','mark_all_unread'):
            is_read=action=='mark_all_read'
            count=Opportunity.objects.filter(suppressed=False,user_deleted=False).update(is_read=is_read)
            if request.headers.get('X-Requested-With')=='fetch':
                return JsonResponse({'ok':True,'count':count,'is_read':is_read,'all':True})
            messages.success(request,f'Marked all {count} opportunities as {"read" if is_read else "unread"}.')
        elif not ids and not (action=='filter_selected' and filter_all):
            if request.headers.get('X-Requested-With')=='fetch':
                return JsonResponse({'ok':False,'error':'Select at least one opportunity.'},status=400)
            messages.error(request,'Select at least one opportunity.')
        elif action in ('mark_unread','mark_read'):
            is_read=action=='mark_read'
            count=Opportunity.objects.filter(pk__in=ids,suppressed=False,user_deleted=False).update(is_read=is_read)
            if request.headers.get('X-Requested-With')=='fetch':
                return JsonResponse({'ok':True,'count':count,'is_read':is_read})
            messages.success(request,f'Marked {count} selected opportunit{"y" if count == 1 else "ies"} as {"read" if is_read else "unread"}.')
        elif action=='blacklist_selected':
            result=_blacklist_selected_opportunities(ids)
            parts=[]
            if result['added']:
                parts.append(f'Blacklisted {result["added"]} compan{"y" if result["added"] == 1 else "ies"} and hid matching opportunities.')
            if result['skipped']:
                parts.append(f'{result["skipped"]} selected row{" was" if result["skipped"] == 1 else "s were"} invalid and ignored.')
            if parts:
                (messages.success if result['added'] else messages.warning)(request,' '.join(parts))
        elif action=='filter_selected':
            try:
                provider,model,internet_search,_options=_manual_filter_selection(request)
                cloud_policy_prompt=_manual_filter_cloud_prompt(request,'opportunity',provider)
            except ValueError as exc:
                if request.headers.get('X-Requested-With')=='fetch':
                    return JsonResponse({'ok':False,'error':str(exc)},status=400)
                messages.error(request,str(exc))
                return redirect('opportunities')
            selected=_opportunity_re_evaluate_ids(request,local_only=filter_local,cloud_only=filter_cloud) if filter_all else list(Opportunity.objects.filter(pk__in=ids,suppressed=False,user_deleted=False).values_list('pk',flat=True))
            count=len(selected)
            if not count:
                error=('No matching Local AI assessments are available to re-evaluate.' if filter_local else ('No matching Cloud AI assessments are available to re-evaluate.' if filter_cloud else 'None of the selected opportunities are still active.'))
                if request.headers.get('X-Requested-With')=='fetch':
                    return JsonResponse({'ok':False,'error':error},status=400)
                messages.error(request,error)
            else:
                scope='Local AI' if filter_local else ('Cloud AI' if filter_cloud else ('matching' if filter_all else 'selected'))
                label=f'Re-evaluate {count} {scope} opportunit{"y" if count == 1 else "ies"}'
                result={
                    'selected':count,'opportunity_ids':selected,'processed':0,'kept':0,'recycled':0,'protected':0,'review':0,'failed':0,
                    'provider':provider,'model':model,'internet_search':internet_search,'scope':('local' if filter_local else ('cloud' if filter_cloud else ('all' if filter_all else 'selected'))),
                    'notify_email':_manual_filter_recipient(request),'cloud_re_evaluation_prompt':cloud_policy_prompt,
                }
                job,active=_claim_manual_filter_job('filter_opportunities',label,f'Queued · 0/{count} · {provider} · {model}',result)
                if active:
                    error='A re-evaluation is already running. Stop it from Dashboard > Background Work before starting another re-evaluation.'
                    if request.headers.get('X-Requested-With')=='fetch':
                        return JsonResponse({'ok':False,'error':error,'job_id':active.pk,'active_kind':active.kind,'active_label':active.label},status=409)
                    messages.error(request,error)
                else:
                    task=opportunity_filter_job.delay(job.pk,selected,provider,model,internet_search,cloud_policy_prompt)
                    job.celery_task_id=task.id or ''
                    job.save(update_fields=['celery_task_id'])
                    if request.headers.get('X-Requested-With')=='fetch':
                        return JsonResponse({'ok':True,'count':count,'job_id':job.pk,'message':job.message,'provider':provider,'model':model,'internet_search':internet_search})
                    messages.success(request,f'Opportunity re-evaluation queued for {count} {scope} item{"" if count == 1 else "s"}.')
        else:
            doomed=Opportunity.objects.filter(pk__in=ids,suppressed=False,user_deleted=False)
            count=doomed.count(); now=timezone.now()
            Application.objects.filter(opportunity__in=doomed,deleted_at__isnull=True).update(deleted_at=now,is_read=True)
            doomed.update(suppressed=True,user_deleted=True,deleted_at=now,is_read=True,rejection_reason='Moved to Recycle Bin by user.')
            if count:
                messages.success(request,f'Moved {count} selected opportunit{"y" if count == 1 else "ies"} to the Recycle Bin.')
            else:
                messages.info(request,'The selected opportunities are already in the Recycle Bin or are no longer active.')
        return redirect(request.get_full_path())
    latest_run=CampaignRun.objects.filter(status='completed').order_by('-finished_at','-created_at').first()
    show_deleted=_show_deleted_setting(request,'opportunities')
    if show_deleted:
        qs=Opportunity.objects.filter(Q(user_deleted=True)|Q(user_deleted=False,suppressed=False))
    else:
        qs=Opportunity.objects.filter(suppressed=False,user_deleted=False)
    qs=qs.prefetch_related('campaigns').select_related('source','application','origin_campaign'); q=_q(request)
    # Keep the list as the complete current Opportunity inventory. The latest run is
    # shown as metadata below the table; it must not hide older still-actionable rows.
    if q:
        # Search fields represented on the list row. Avoid matching hidden description
        # text, which made apparently unrelated rows survive a list search.
        visible_match=(
            Q(title__icontains=q)|Q(company__icontains=q)|Q(country__icontains=q)|Q(role_location__icontains=q)|
            Q(contact_email__icontains=q)|Q(note__icontains=q)|Q(remote_text__icontains=q)|Q(list_highlight__icontains=q)|
            Q(freshness_label__icontains=q)|Q(salary_text__icontains=q)|Q(target_url__icontains=q)|Q(url__icontains=q)
        )
        qs=qs.filter(visible_match)
    pre_advanced_qs=qs
    qs,advanced_filters=_apply_advanced_opportunity_filters(qs,request)
    base_qs=qs
    focus_state=_request_multi_filter_state(request,'focus')
    country_state=_request_multi_filter_state(request,'country',canonicalizer=_canonical_country_name)
    campaign_state=_request_multi_filter_state(request,'campaign',integer=True)
    focus_filter_values=list(focus_state['values'])
    country_filter_values=list(country_state['values'])
    campaign_filter_values=list(campaign_state['values'])
    focus_filter=focus_filter_values[0] if len(focus_filter_values)==1 else ''
    country_filter=country_filter_values[0] if len(country_filter_values)==1 else ''
    campaign=str(campaign_filter_values[0]) if len(campaign_filter_values)==1 else ''
    channel_filter=(request.GET.get('channel') or '').strip()
    read_state=(request.GET.get('read') or '').strip().lower()
    hide_non_200=(request.GET.get('healthy') or '')=='1'
    source=(request.GET.get('source') or '').strip()
    sort_mode=(request.GET.get('sort') or '').strip().lower()
    if sort_mode not in {
        'fit_desc','fit_asc','age_asc','age_desc','role_asc','role_desc',
        'summary_asc','summary_desc','company_info_asc','company_info_desc',
        'remote_asc','remote_desc','added_asc','added_desc',
    }:
        sort_mode=''

    def _opportunity_filtered(exclude=(), base=None):
        filtered=base if base is not None else base_qs
        excluded=set(exclude)
        if 'focus' not in excluded: filtered=_apply_focus_filters(filtered, focus_filter_values, focus_state['mode'])
        if channel_filter and 'channel' not in excluded: filtered=filtered.filter(channel=channel_filter)
        if read_state=='unread' and 'read' not in excluded: filtered=filtered.filter(is_read=False)
        elif read_state=='read' and 'read' not in excluded: filtered=filtered.filter(is_read=True)
        if hide_non_200 and 'healthy' not in excluded:
            filtered=filtered.filter(Q(contact_email__gt='')|(Q(target_http_status=200)&~Q(target_check_error__startswith=_URL_CONTENT_WARNING_PREFIX)))
        if 'campaign' not in excluded: filtered=_apply_campaign_filters(filtered,campaign_filter_values,campaign_state['mode'])
        if source and 'source' not in excluded: filtered=filtered.filter(source_id=source)
        if 'country' not in excluded: filtered=_apply_country_filters(filtered,'country',country_filter_values,country_state['mode'])
        return filtered

    qs=_opportunity_filtered()
    unadvanced_filtered=_opportunity_filtered(base=pre_advanced_qs)
    focus_count_base=_opportunity_filtered({'focus'}).distinct()
    read_count_base=_opportunity_filtered({'read'}).distinct()
    country_count_base=_opportunity_filtered({'country'}).distinct()
    campaign_count_base=_opportunity_filtered({'campaign'}).distinct()
    opportunity_filter_counts={
        'total':qs.distinct().count(),
        'read_total':read_count_base.count(),
        'read':read_count_base.filter(is_read=True).count(),
        'unread':read_count_base.filter(is_read=False).count(),
    }
    opportunity_focus_options=focus_options(focus_count_base)
    opportunity_focus_total=sum(int(x.get('count') or 0) for x in opportunity_focus_options)
    country_options=_country_filter_options(country_count_base,'country')
    country_options=_prune_zero_roundtrip_country_options(country_options,country_count_base,'country')
    # "All locations" means exactly what happens when no country restriction is
    # applied. Blank/unrecognized legacy values are not individual dropdown options,
    # but they remain part of this complete result universe.
    country_total=country_count_base.count()
    campaign_counts={}
    for row in campaign_count_base.select_related(None).prefetch_related(None).only('pk','origin_campaign_id').distinct().prefetch_related('campaigns'):
        ids=set()
        if row.origin_campaign_id: ids.add(row.origin_campaign_id)
        ids.update(c.pk for c in row.campaigns.all())
        for cid in ids: campaign_counts[cid]=campaign_counts.get(cid,0)+1
    campaign_options=[]
    for campaign_row in Campaign.objects.filter(deleted_at__isnull=True).order_by('name'):
        campaign_row.entry_count=int(campaign_counts.get(campaign_row.pk,0) or 0)
        if campaign_row.entry_count:
            campaign_options.append(campaign_row)
    campaign_total=campaign_count_base.distinct().count()
    selected_campaign_ids={int(x) for x in campaign_filter_values if str(x).isdigit() or isinstance(x,int)}
    for campaign_row in campaign_options:
        campaign_row.selected=(campaign_state['mode']!='custom' or campaign_row.pk in selected_campaign_ids)
    selected_countries={str(x) for x in country_filter_values}
    for row in country_options:
        row['selected']=(country_state['mode']!='custom' or str(row.get('value')) in selected_countries)
    selected_focuses={str(x) for x in focus_filter_values}
    for row in opportunity_focus_options:
        row['selected']=(focus_state['mode']!='custom' or str(row.get('value')) in selected_focuses)
    campaign_filter_label=_multi_filter_label('campaigns',campaign_filter_values,_selected_labels(campaign_options,campaign_filter_values,value_key='pk',label_key='name'),campaign_state['mode'],campaign_total)
    country_filter_label=_multi_filter_label('locations',country_filter_values,_selected_labels(country_options,country_filter_values),country_state['mode'],country_total)
    focus_filter_label=_multi_filter_label('focuses',focus_filter_values,_selected_labels(opportunity_focus_options,focus_filter_values),focus_state['mode'],opportunity_focus_total)
    if sort_mode=='fit_desc':
        ordered_qs=qs.distinct().order_by('-fit_score','-first_seen_by_portal','-pk')
    elif sort_mode=='fit_asc':
        ordered_qs=qs.distinct().order_by('fit_score','-first_seen_by_portal','-pk')
    elif sort_mode=='added_asc':
        ordered_qs=qs.distinct().order_by('first_seen_by_portal','pk')
    elif sort_mode=='added_desc':
        ordered_qs=qs.distinct().order_by('-first_seen_by_portal','-pk')
    elif sort_mode in {'age_asc','age_desc'}:
        # Post Age is presentation-derived (raw age_days, retained dates, then legacy
        # buckets), so sort the complete filtered result set before pagination. Unknown
        # ages are deliberately last in BOTH directions rather than becoming the
        # newest/oldest item merely because the visible cell is ``?``.
        ordered_qs=list(qs.distinct())
        descending=sort_mode=='age_desc'
        def _post_age_order(row):
            age=opportunity_post_age_sort_days(row)
            try:
                added=row.first_seen_by_portal.timestamp() if row.first_seen_by_portal else 0
            except Exception:
                added=0
            return (age is None, (-(age or 0) if descending else (age or 0)), -added, -int(row.pk or 0))
        ordered_qs.sort(key=_post_age_order)
    elif sort_mode in {'role_asc','role_desc','summary_asc','summary_desc','company_info_asc','company_info_desc','remote_asc','remote_desc'}:
        # These columns contain presentation-derived values. Sort the complete filtered
        # result set in memory before pagination; client-side table sorting would only
        # reorder the current page and therefore produce a misleading global order.
        ordered_qs=list(qs.distinct())
        reverse=sort_mode.endswith('_desc')
        if sort_mode.startswith('role_'):
            key=lambda row: (str(row.title or '').casefold(),str(row.company or '').casefold(),int(row.pk or 0))
        elif sort_mode.startswith('summary_'):
            key=lambda row: (str(opportunity_list_summary(row) or '').casefold(),str(row.title or '').casefold(),int(row.pk or 0))
        elif sort_mode.startswith('company_info_'):
            key=lambda row: (company_info_sort_value(row),str(row.company or '').casefold(),int(row.pk or 0))
        else:
            key=lambda row: (remote_sort_value(row),str(row.title or '').casefold(),int(row.pk or 0))
        ordered_qs.sort(key=key,reverse=reverse)
    else:
        ordered_qs=qs.distinct().order_by('-first_seen_by_portal','-pk')
    if request.GET.get('export')=='1':
        rows=[]
        for o in ordered_qs[:5000]:
            rows.append((
                o.first_seen_by_portal,o.title,o.company,o.focus,o.country,o.remote_text,o.freshness_label,o.fit_score,
                o.get_channel_display(),o.get_status_display(),'Read' if o.is_read else 'New',
                (o.application.applied_at if getattr(o,'application',None) and o.application.applied_at else ''),
                o.source.name if o.source else '',o.target_url or o.url,
                opportunity_list_summary(o),company_info_compact(o),o.salary_text,o.contact_email,o.note,
                o.target_http_status if o.target_http_status is not None else '',o.origin_campaign.name if o.origin_campaign else '',', '.join(c.name for c in o.campaigns.all()),
            ))
        return _xlsx(
            'opportunities.xlsx',
            ['Added','Role','Company','Focus','Location','Remote','Age','Fit','Channel','Status','Read status','Applied Date','Source','URL',
             'List Summary','Company Info','Salary','Contact Email','Note','URL HTTP Status','Origin Campaign','Campaigns Seen'],
            rows,
        )
    page,per_page=_page(request,ordered_qs,default=50)
    _decorate_opportunity_sources(page.object_list)
    for row in page.object_list:
        _repair_known_contact_email(row)
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    active_opportunity_filter=BackgroundJob.objects.filter(kind='filter_opportunities',status__in=['queued','running']).order_by('-created_at').first()
    active_manual_filter=_active_manual_filter()
    # 0.11.29: the re-evaluation history dialog is DB-complete after hiding no-result shells; do not cap or
    # pre-slice completed Opportunity runs.
    opportunity_filter_history=_decorate_manual_filter_item_dates(_manual_filter_history_for_view('filter_opportunities',active_opportunity_filter),'opportunity')
    completed_opportunity_filter_history=[x for x in opportunity_filter_history if str(x.status or '').lower() not in {'queued','running'}]
    latest_opportunity_filter=_latest_meaningful_manual_filter(completed_opportunity_filter_history)
    opportunity_filter_history_label=_manual_filter_history_label(opportunity_filter_history,'Opportunity')
    manual_filter_ai=_manual_filter_ai_options()
    advanced_filter_active=any(advanced_filters.values())
    shown_count=qs.distinct().count()
    unadvanced_count=unadvanced_filtered.distinct().count() if advanced_filter_active else shown_count
    advanced_filter_counts={'shown':shown_count,'hidden':max(0,unadvanced_count-shown_count),'available':unadvanced_count}
    return render(request,'portal/opportunities.html',ctx(request,'opportunities','Opportunities',opportunities=page,page_obj=page,per_page=per_page,campaigns=Campaign.objects.filter(deleted_at__isnull=True),campaign_options=campaign_options,campaign_filter=campaign,country_filter=country_filter,country_options=country_options,country_total=country_total,campaign_total=campaign_total,campaign_filter_label=campaign_filter_label,campaign_filter_mode=campaign_state['mode'],country_filter_label=country_filter_label,country_filter_mode=country_state['mode'],focus_filter_label=focus_filter_label,focus_filter_mode=focus_state['mode'],sources=SearchSource.objects.all().order_by('name'),q=q,last_scanned=(latest_run.finished_at if latest_run else ps.last_discovery_run),latest_run=latest_run,read_state=read_state,hide_non_200=hide_non_200,opportunity_filter_counts=opportunity_filter_counts,active_opportunity_filter=active_opportunity_filter,active_manual_filter=active_manual_filter,latest_opportunity_filter=latest_opportunity_filter,opportunity_filter_history=opportunity_filter_history,opportunity_filter_history_label=opportunity_filter_history_label,manual_filter_ai=manual_filter_ai,sort_mode=sort_mode,advanced_filters=advanced_filters,advanced_filter_active=advanced_filter_active,advanced_filter_summary=_advanced_opportunity_filter_summary(advanced_filters),advanced_filter_counts=advanced_filter_counts,advanced_filter_reset_query=_advanced_opportunity_reset_query(request),company_size_filter_options=[('lt10','0-10'),('lt50','10-50'),('lt100','50-100'),('lt500','100-500'),('lt1000','500-1,000'),('gte1000','1,000+'),('unknown','Unknown / Others')],company_age_filter_options=[('lt1','0-1 year'),('lt2','1-2 years'),('lt5','2-5 years'),('lt10','5-10 years'),('gte10','10+ years'),('unknown','Unknown / Others')],focus_filter=focus_filter,focus_options=opportunity_focus_options,focus_total=opportunity_focus_total,show_deleted=show_deleted))


@login_required
def opportunity_detail(request,pk):
    o=get_object_or_404(Opportunity.objects.filter(user_deleted=False).prefetch_related('evidence','campaigns'),pk=pk)
    repair_opportunity_campaign_links(o)
    if not o.is_read:
        Opportunity.objects.filter(pk=o.pk,is_read=False).update(is_read=True)
        o.is_read=True
    if request.method=='POST':
        action=request.POST.get('action')
        if action=='status':
            status=request.POST.get('status','review')
            if status in dict(Opportunity.STATUS):
                o.status=status
            if 'note' in request.POST:
                o.note=request.POST.get('note','').strip()
            if 'country' in request.POST:
                country=request.POST.get('country','').strip()[:120]
                if not country or country in COUNTRIES: o.country=country
            if 'contact_email' in request.POST:
                contact_email=clean_contact_email(request.POST.get('contact_email',''))
                if contact_email:
                    try: validate_email(contact_email)
                    except ValidationError:
                        messages.error(request,'Enter a valid contact email address.')
                        return redirect('opportunity_detail',pk=pk)
                o.contact_email=contact_email
            if 'fit_level' in request.POST:
                try: o.fit_score=max(0,min(5,int(request.POST.get('fit_level') or 0)))*20
                except (TypeError,ValueError): pass
            elif 'fit_score' in request.POST:  # backwards-compatible form/API input
                try: o.fit_score=max(0,min(100,int(request.POST.get('fit_score') or 0)))
                except (TypeError,ValueError): pass
            o.save(update_fields=['status','note','country','contact_email','fit_score','updated_at']); messages.success(request,'Opportunity changes saved.')
            log('opportunity.status',request,o)
            return redirect('opportunities')
        elif action=='apply_now':
            existing=Application.objects.filter(opportunity=o,deleted_at__isnull=True).first()
            if existing:
                return redirect('application_edit',pk=existing.pk)
            if Application.objects.filter(opportunity=o,deleted_at__isnull=False).exists():
                messages.info(request,'This application/outreach record is in the Recycle Bin. Restore it there before preparing it again.')
                return redirect('recycle_bin')
            active_prepare=BackgroundJob.objects.filter(kind='prepare',status__in=['queued','running'],result__opportunity_id=o.pk).order_by('-created_at').first()
            if active_prepare:
                messages.info(request,f'Application preparation is already {active_prepare.get_status_display().lower()} ({active_prepare.progress}%).')
            else:
                update_fields=['status','updated_at']; o.status='apply'
                if not o.application_draft_requested_at:
                    o.application_draft_requested_at=timezone.now(); update_fields.append('application_draft_requested_at')
                o.save(update_fields=update_fields)
                cv=DocumentAsset.objects.filter(kind='cv',active=True).order_by('-created_at').first(); cover=DocumentAsset.objects.filter(kind='cover',active=True).order_by('-created_at').first()
                job=BackgroundJob.objects.create(kind='prepare',label=f'Prepare application: {o.title}'[:300],message='Queued',result={'opportunity_id':o.pk})
                try:
                    task=application_prepare_job.delay(job.pk,o.pk,cv.pk if cv else None,cover.pk if cover else None); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
                    messages.success(request,format_html('<a href="{}">Application preparation</a> queued. You can continue using ScoutBox while it runs.',reverse('applications')),extra_tags='safe-html')
                except Exception as exc:
                    job.status='failed'; job.error=str(exc); job.finished_at=timezone.now(); job.save(update_fields=['status','error','finished_at'])
                    messages.error(request,'Application preparation could not be queued. Check the worker/broker status.')
        elif action=='refresh_age':
            reserve_attempt(o,'freshness','manual')
            active=BackgroundJob.objects.filter(kind='enrich',status__in=['queued','running'],label__startswith='Refresh post age:',result__opportunity_id=o.pk).first()
            job=active or BackgroundJob.objects.create(kind='enrich',label=f'Refresh post age: {o.title}'[:300],message='Queued',result={'opportunity_id':o.pk})
            if not active:
                task=opportunity_freshness_job.delay(job.pk,o.pk,'manual'); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
            if request.headers.get('X-Requested-With')=='fetch':
                return JsonResponse({'ok':True,'job_id':job.pk,'status':job.status})
            messages.success(request,'Post-age refresh queued.')
        elif action=='enrich':
            job=BackgroundJob.objects.create(kind='enrich',label=f'Enrich opportunity: {o.title}'[:300],message='Queued',result={'opportunity_id':o.pk})
            task=opportunity_enrich_job.delay(job.pk,o.pk); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id']); messages.success(request,'Enrichment queued.')
        elif action=='prepare':
            active_prepare=BackgroundJob.objects.filter(kind='prepare',status__in=['queued','running'],result__opportunity_id=o.pk).order_by('-created_at').first()
            if active_prepare:
                messages.info(request,f'Application preparation is already {active_prepare.get_status_display().lower()} ({active_prepare.progress}%).')
            else:
                if not o.application_draft_requested_at:
                    o.application_draft_requested_at=timezone.now(); o.save(update_fields=['application_draft_requested_at','updated_at'])
                cv_raw=(request.POST.get('cv_id') or '').strip(); cover_raw=(request.POST.get('cover_id') or '').strip()
                cv=DocumentAsset.objects.filter(pk=int(cv_raw),kind='cv',active=True).first() if cv_raw.isdigit() else None
                cover=DocumentAsset.objects.filter(pk=int(cover_raw),kind='cover',active=True).first() if cover_raw.isdigit() else None
                job=BackgroundJob.objects.create(kind='prepare',label=f'Prepare application: {o.title}'[:300],message='Queued',result={'opportunity_id':o.pk})
                try:
                    task=application_prepare_job.delay(job.pk,o.pk,cv.pk if cv else None,cover.pk if cover else None); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id']); messages.success(request,format_html('<a href="{}">Application preparation</a> queued.',reverse('applications')),extra_tags='safe-html')
                except Exception as exc:
                    job.status='failed'; job.error=str(exc); job.finished_at=timezone.now(); job.save(update_fields=['status','error','finished_at']); messages.error(request,'Application preparation could not be queued.')
        elif action=='summarize_text':
            existing_summary=((o.extracted_facts or {}).get('ai_job_summary') or {}) if isinstance(o.extracted_facts or {},dict) else {}
            # Cloud discovery already generated the canonical job summary. Do not spend
            # another model call re-summarising the same role text merely because the
            # source hash differs after URL/detail normalization.
            if existing_summary.get('text') and existing_summary.get('cloud_reused'):
                messages.info(request,'The Cloud AI discovery summary is already current for this opportunity.')
            else:
                active=BackgroundJob.objects.filter(kind='summarize',status__in=['queued','running'],result__opportunity_id=o.pk).first()
                if active:
                    messages.info(request,'An AI summary is already being prepared for this opportunity.')
                else:
                    reserve_attempt(o,'summary','manual')
                    job=BackgroundJob.objects.create(kind='summarize',label=f'Summarize: {o.title}'[:300],message='Queued',result={'opportunity_id':o.pk})
                    task=opportunity_summary_job.delay(job.pk,o.pk,'manual'); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id']); messages.success(request,'AI summary queued.')
        elif action=='translate':
            field=request.POST.get('field','description')
            job=BackgroundJob.objects.create(kind='translate',label=f'Translate {o.title}'[:300],message='Queued',result={'opportunity_id':o.pk})
            task=translate_opportunity_job.delay(job.pk,o.pk,field); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id']); messages.success(request,'English translation queued.')
        elif action=='company_research':
            reserve_attempt(o,'company','manual')
            job=BackgroundJob.objects.create(kind='company_research',label=f'Company research: {o.company or o.title}'[:300],message='Queued',result={'opportunity_id':o.pk})
            task=company_research_job.delay(job.pk,o.pk,'manual'); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id']); messages.success(request,'Company research queued.')
        elif action=='blacklist':
            candidate=company_blacklist_candidate(o)
            label=candidate.get('company','') if candidate.get('valid') else ''
            if label:
                row,created=_upsert_blacklist_rule('',label,'Added from Opportunity','all',allow_short_label=bool(candidate.get('domain')))
                try: enforce_active_blacklist()
                except Exception: pass
                o.refresh_from_db(fields=['suppressed','user_deleted','deleted_at','updated_at'])
                blocked=_blacklist_display_name(row)
                messages.success(request,f'Blocked company {blocked}. Matching records were moved to the Recycle Bin.')
                log('opportunity.blacklist',request,o,summary=blocked)
                return redirect('opportunities')
            messages.error(request,f'Could not determine a Company Name of at least {LABEL_BLACKLIST_MIN_CHARS} characters to blacklist.')
        log(f'opportunity.{action}',request,o)
        return redirect('opportunity_detail',pk=pk)

    source_text=_opportunity_text_source(o)
    source_hash=hashlib.sha256(source_text.encode('utf-8','ignore')).hexdigest() if source_text else ''
    summary=(o.extracted_facts or {}).get('ai_job_summary') or {}
    summary_current=bool(summary.get('text') and (summary.get('cloud_reused') or summary.get('source_hash')==source_hash))
    summary_route_available=bool(route_for_stage('page_summarization'))
    # Exactly one automatic recovery pass may be queued on a meaningful detail-page
    # view when discovery-time enrichment did not yield usable data. Further attempts
    # are explicit via the Refresh controls and still respect Cloud AI budgets.
    active_summary=BackgroundJob.objects.filter(kind='summarize',status__in=['queued','running'],result__opportunity_id=o.pk).first()
    active_prepare=BackgroundJob.objects.filter(kind='prepare',status__in=['queued','running'],result__opportunity_id=o.pk).order_by('-created_at').first()
    active_company_research=BackgroundJob.objects.filter(kind='company_research',status__in=['queued','running'],result__opportunity_id=o.pk).order_by('-created_at').first()
    intel=o.company_intel or {}
    if (o.company or o.target_url or o.url) and not intel.get('facts'):
        intel=ensure_company_research_baseline(o) or intel
    if not active_summary and not summary_current:
        allowed,_=reserve_attempt(o,'summary','recovery')
        if allowed:
            auto_job=BackgroundJob.objects.create(kind='summarize',label=f'Summarize: {o.title}'[:300],message='Queued recovery',result={'opportunity_id':o.pk,'phase':'recovery'})
            try:
                task=opportunity_summary_job.delay(auto_job.pk,o.pk,'recovery'); auto_job.celery_task_id=task.id or ''; auto_job.save(update_fields=['celery_task_id']); active_summary=auto_job
            except Exception as exc:
                auto_job.status='failed'; auto_job.error=str(exc); auto_job.finished_at=timezone.now(); auto_job.save(update_fields=['status','error','finished_at'])
    if o.company and not active_company_research and not usable_result(o,'company'):
        allowed,_=reserve_attempt(o,'company','recovery')
        if allowed:
            auto_job=BackgroundJob.objects.create(kind='company_research',label=f'Company research: {o.company or o.title}'[:300],message='Queued recovery',result={'opportunity_id':o.pk,'auto':True,'phase':'recovery'})
            try:
                task=company_research_job.delay(auto_job.pk,o.pk,'recovery'); auto_job.celery_task_id=task.id or ''; auto_job.save(update_fields=['celery_task_id']); active_company_research=auto_job
            except Exception as exc:
                auto_job.status='failed'; auto_job.error=str(exc); auto_job.finished_at=timezone.now(); auto_job.save(update_fields=['status','error','finished_at'])
    active_jobs=BackgroundJob.objects.filter(status__in=['queued','running'],result__opportunity_id=o.pk)[:10]
    target_url=o.target_url or o.url
    title_candidate=(o.title or '').strip()
    company_candidate=(o.company or '').strip()
    reason_heading_re=re.compile(r'(?is)^\s*(?:#{1,6}\s*)?reason\s*:\s*')
    # Historical rows can contain recommendation prose in either title or company. Never
    # promote that prose into the page-level heading/breadcrumb. Prefer the real role title,
    # then a sane company value, then a stable generic identifier.
    if title_candidate and not reason_heading_re.match(title_candidate):
        detail_heading=reason_heading_re.sub('',title_candidate).strip()
    elif company_candidate and not reason_heading_re.match(company_candidate):
        detail_heading=reason_heading_re.sub('',company_candidate).strip()
    else:
        detail_heading='Opportunity'
    clean_company_name=reason_heading_re.sub('',company_candidate).strip() if company_candidate and not reason_heading_re.match(company_candidate) else ''
    if clean_company_name and clean_company_name.casefold() not in detail_heading.casefold():
        detail_heading=f'{detail_heading} · {clean_company_name}'
    detail_heading=f'{detail_heading} (ID #{o.pk})'
    extracted=o.extracted_facts if isinstance(o.extracted_facts,dict) else {}
    cloud_research=extracted.get('cloud_research') if isinstance(extracted.get('cloud_research'),dict) else {}
    role_info=extracted.get('role_info') if isinstance(extracted.get('role_info'),dict) else {}
    hiring_process=extracted.get('hiring_process') if isinstance(extracted.get('hiring_process'),dict) else {}
    if not role_info.get('summary'):
        pieces=[]
        for key,label in (('salary','Salary'),('salary_estimate','Salary estimate'),('role_feedback','Role feedback')):
            value=str(cloud_research.get(key) or '').strip()
            if value: pieces.append(f'{label}: {value}')
        if pieces: role_info={'summary':'\n'.join(pieces),'provenance':'Role-specific','confidence':'Medium','sources':cloud_research.get('sources') or []}
    if not hiring_process.get('summary') and str(cloud_research.get('application_process') or '').strip():
        hiring_process={'summary':str(cloud_research.get('application_process'))[:5000],'provenance':'Role-specific' if cloud_research.get('application_process_role_specific',True) else 'Company/general process','confidence':str(cloud_research.get('hiring_process_confidence') or 'Medium'),'sources':cloud_research.get('sources') or []}
    source_url=o.search_url or o.url or target_url
    return render(request,'portal/opportunity_detail.html',ctx(request,'opportunities',detail_heading,breadcrumbs=[{'label':'ScoutBox','route':'dashboard'},{'label':'Opportunities','route':'opportunities'},{'label':detail_heading,'route':None}],opportunity=o,cvs=DocumentAsset.objects.filter(kind='cv',active=True),covers=DocumentAsset.objects.filter(kind='cover',active=True),active_jobs=active_jobs,job_summary=summary if summary.get('text') else {},summary_current=summary_current,summary_pending=bool(active_summary),summary_job_id=(active_summary.pk if active_summary else None),summary_route_available=summary_route_available,source_text=source_text,target_url=target_url,source_url=source_url,source_target_same=_same_url(source_url,target_url),role_info=role_info,hiring_process=hiring_process,active_prepare=active_prepare,company_research_pending=bool(active_company_research),company_research_job_id=(active_company_research.pk if active_company_research else None),post_age_evidence=o.evidence.filter(kind__in=['page_date_llm','http_last_modified','cloud_posted_date','cloud_age_support']).order_by('-confidence','-observed_at')[:6]))


@login_required
def company_intel_view(request):
    return redirect('opportunities')


@login_required
def import_view(request):
    """Backward-compatible import endpoint; the UI now lives in Applications & Outreach."""
    if request.method=='POST':
        action=request.POST.get('action')
        try:
            if action=='scan_mail':
                active=BackgroundJob.objects.filter(kind='mail_scan',status__in=['queued','running']).first()
                if active:
                    messages.info(request,'A mailbox sync is already running.')
                else:
                    job=BackgroundJob.objects.create(kind='mail_scan',label='Sync application mailbox',message='Queued')
                    task=mailbox_import_job.delay(job.pk); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
                    messages.success(request,'Mailbox sync queued. You can continue using ScoutBox while it runs.')
            elif action=='paste':
                text=request.POST.get('text','').strip()
                if not text: raise ValueError('Paste some application history first.')
                job=BackgroundJob.objects.create(kind='import_text',label='Analyse pasted application history',message='Queued')
                task=import_text_job.delay(job.pk,text); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
                messages.success(request,'Application-history inference queued.')
            elif action=='upload':
                f=request.FILES.get('file')
                if not f: raise ValueError('Choose a document to import.')
                safe=re.sub(r'[^A-Za-z0-9._-]+','_',f.name)[:180] or 'import.bin'
                storage_path=default_storage.save(f'import_queue/{timezone.now().strftime("%Y%m%d%H%M%S")}_{safe}',f)
                job=BackgroundJob.objects.create(kind='import_document',label=f'Analyse {f.name}'[:300],message='Queued')
                task=import_document_job.delay(job.pk,storage_path,f.name); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
                messages.success(request,f'{f.name} queued for automatic processing.')
            elif action=='confirm':
                c=get_object_or_404(ImportCandidate,pk=request.POST.get('candidate_id'),imported=False)
                app=confirm_candidate(c); messages.success(request,'Added to Applications & Outreach.' if app else 'That historical application was already present.')
            elif action in ('confirm_selected','confirm_all'):
                ids=request.POST.getlist('candidate_ids') if action=='confirm_selected' else list(ImportCandidate.objects.filter(imported=False).values_list('pk',flat=True)[:1000])
                count=0
                for c in ImportCandidate.objects.filter(imported=False,pk__in=ids):
                    if confirm_candidate(c): count+=1
                messages.success(request,f'Added {count} historical application{ "" if count==1 else "s"} to Applications & Outreach.')
        except Exception as e:
            messages.error(request,str(e))
    return redirect(reverse('applications')+'?import=1')


@login_required
def applied_view(request):
    """Legacy Applied Roles URL retained as a redirect into the unified application tracker."""
    return redirect(reverse('applications')+'?stage=history')


@login_required
def applied_edit(request,pk):
    """Legacy Applied Role editor now uses the unified Applications & Outreach editor."""
    get_object_or_404(Application,pk=pk)
    return redirect('application_edit',pk=pk)


def _queue_mailbox_sync():
    active=BackgroundJob.objects.filter(kind='mail_scan',status__in=['queued','running']).first()
    if active: return active,False
    job=BackgroundJob.objects.create(kind='mail_scan',label='Sync application mailbox',message='Queued')
    task=mailbox_import_job.delay(job.pk); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
    return job,True


def _handle_application_import_action(request, action):
    if action=='sync_imap' or action=='scan_mail':
        _job,created=_queue_mailbox_sync()
        messages.success(request,'IMAP sync queued for Inbox, Sent and Drafts.' if created else 'A mailbox sync is already running.')
        return True
    if action=='paste':
        text=request.POST.get('text','').strip()
        if not text: raise ValueError('Paste some application history first.')
        job=BackgroundJob.objects.create(kind='import_text',label='Analyse pasted application history',message='Queued')
        task=import_text_job.delay(job.pk,text); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
        messages.success(request,'Application-history inference queued. Proposed applications will appear below when ready.')
        return True
    if action=='upload':
        f=request.FILES.get('file')
        if not f: raise ValueError('Choose a document to import.')
        safe=re.sub(r'[^A-Za-z0-9._-]+','_',f.name)[:180] or 'import.bin'
        storage_path=default_storage.save(f'import_queue/{timezone.now().strftime("%Y%m%d%H%M%S")}_{safe}',f)
        job=BackgroundJob.objects.create(kind='import_document',label=f'Analyse {f.name}'[:300],message='Queued')
        task=import_document_job.delay(job.pk,storage_path,f.name); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
        messages.success(request,f'{f.name} queued for automatic processing.')
        return True
    if action=='confirm':
        c=get_object_or_404(ImportCandidate,pk=request.POST.get('candidate_id'),imported=False)
        app=confirm_candidate(c); messages.success(request,'Added to Applications & Outreach.' if app else 'That historical application was already present.')
        return True
    if action in ('confirm_selected','confirm_all'):
        ids=request.POST.getlist('candidate_ids') if action=='confirm_selected' else list(ImportCandidate.objects.filter(imported=False).values_list('pk',flat=True)[:1000])
        count=0
        for c in ImportCandidate.objects.filter(imported=False,pk__in=ids):
            if confirm_candidate(c): count+=1
        messages.success(request,f'Added {count} historical application{ "" if count==1 else "s"} to Applications & Outreach.')
        return True
    return False


def _public_record_url(*values):
    for value in values:
        text=str(value or '').strip()
        if not text:
            continue
        try:
            host=(urlparse(text).hostname or '').lower()
        except Exception:
            host=''
        if host.endswith('.invalid'):
            continue
        return text
    return ''


@login_required
def applications_view(request):
    action=request.POST.get('action') if request.method=='POST' else ''
    if request.method=='POST' and action=='restore_row':
        row_id=(request.POST.get('row_id') or '').strip()
        ok,label=_restore_recycle_item('application',int(row_id)) if row_id.isdigit() else (False,'Application / Outreach')
        if request.headers.get('X-Requested-With')=='fetch':
            return JsonResponse({'ok':ok,'label':label,'error':'' if ok else 'This application/outreach record is not in the Recycle Bin.'},status=200 if ok else 404)
        (messages.success if ok else messages.warning)(request,(f'Restored {label}.' if ok else 'This application/outreach record is not in the Recycle Bin.'))
        return redirect(request.get_full_path())
    if request.method=='POST' and action in ('mark_read','mark_unread','mark_all_read','mark_all_unread'):
        if action in ('mark_all_read','mark_all_unread'):
            is_read=action=='mark_all_read'; count=Application.objects.filter(opportunity__user_deleted=False,deleted_at__isnull=True).update(is_read=is_read)
        else:
            ids=[x for x in request.POST.getlist('application_ids') if str(x).isdigit()]
            is_read=action=='mark_read'; count=Application.objects.filter(pk__in=ids,opportunity__user_deleted=False,deleted_at__isnull=True).update(is_read=is_read)
        if request.headers.get('X-Requested-With')=='fetch': return JsonResponse({'ok':True,'count':count,'is_read':is_read,'all':action.startswith('mark_all_')})
        messages.success(request,f'Marked {count} application{ "" if count==1 else "s"} as {"read" if is_read else "unread"}.')
        return redirect('applications')
    if request.method=='POST' and action=='delete_selected':
        ids=[x for x in request.POST.getlist('application_ids') if str(x).isdigit()]
        doomed=Application.objects.filter(pk__in=ids,deleted_at__isnull=True,opportunity__user_deleted=False)
        removed=doomed.count()
        doomed.update(deleted_at=timezone.now(),is_read=True)
        if removed: messages.success(request,f'Moved {removed} application/outreach record{"" if removed==1 else "s"} to the Recycle Bin.')
        else: messages.info(request,'The selected application/outreach records are already in the Recycle Bin or no longer active.')
        return redirect(request.get_full_path())
    if request.method=='POST' and action=='manual_create':
        company=request.POST.get('company','').strip(); title=request.POST.get('title','').strip(); url=request.POST.get('url','').strip(); jd=request.POST.get('description','').strip(); country=request.POST.get('country','').strip()[:120]; errors=[]
        if country and country not in COUNTRIES: errors.append('Select a valid country.')
        if len(company)<2: errors.append('Company must contain at least 2 characters.')
        if len(title)<2: errors.append('Role title must contain at least 2 characters.')
        if url and not re.match(r'^https?://',url,re.I): errors.append('Job-description URL must start with http:// or https://.')
        status=request.POST.get('status','prepared'); channel=request.POST.get('channel','unknown')
        if status not in dict(Application.STATUS): errors.append('Select a valid application status.')
        if channel not in dict(Opportunity.CHANNEL): errors.append('Select a valid application channel.')
        applied_at=None; dt_raw=request.POST.get('applied_at','').strip()
        if dt_raw:
            try:
                try: parsed=datetime.strptime(dt_raw,'%Y-%m-%dT%H:%M:%S')
                except ValueError: parsed=datetime.strptime(dt_raw,'%Y-%m-%dT%H:%M')
                applied_at=timezone.make_aware(parsed)
            except Exception: errors.append('Applied date/time is invalid.')
        for e in errors: messages.error(request,e)
        if not errors:
            import uuid
            final_url=url or f'https://manual.invalid/{uuid.uuid4().hex}'
            if Opportunity.objects.filter(url=final_url).exists(): final_url=f'https://manual.invalid/{uuid.uuid4().hex}'
            historical=status in ('applied','reply','interview','rejected','accepted','closed')
            record_type=(request.POST.get('record_type') or 'application').strip().lower()
            outreach=record_type=='outreach'
            opp=Opportunity.objects.create(
                company=company,title=title,country=country,url=final_url,canonical_url=url or '',target_url=url or '',
                description=jd,channel=channel,status='applied' if historical else 'draft',application_draft_requested_at=timezone.now(),is_read=True,
                contact_name=request.POST.get('contact_name','').strip()[:200],contact_email=clean_contact_email(request.POST.get('contact_email','')),
                extracted_facts={'manual_entry':True,'jd_url':url,'outreach':outreach},
            )
            cv_raw=(request.POST.get('cv_id') or '').strip(); cover_raw=(request.POST.get('cover_id') or '').strip()
            cv=DocumentAsset.objects.filter(pk=int(cv_raw),kind='cv',active=True).first() if cv_raw.isdigit() else None
            cover=DocumentAsset.objects.filter(pk=int(cover_raw),kind='cover',active=True).first() if cover_raw.isdigit() else None
            app=Application.objects.create(opportunity=opp,status=status,applied_at=applied_at,cv=cv,cover_letter=cover,notes=request.POST.get('notes','').strip(),is_read=True)
            messages.success(request,'Application / outreach record added.'); return redirect('application_edit',pk=app.pk)
    if request.method=='POST' and action in ('sync_imap','scan_mail','paste','upload','confirm','confirm_selected','confirm_all'):
        try: _handle_application_import_action(request,action)
        except Exception as e: messages.error(request,str(e))
        return redirect(reverse('applications')+('?import=1' if action not in ('sync_imap',) else ''))

    show_deleted=_show_deleted_setting(request,'applications')
    if show_deleted:
        qs=Application.objects.filter(Q(deleted_at__isnull=False)|Q(deleted_at__isnull=True,opportunity__user_deleted=False))
    else:
        qs=Application.objects.filter(opportunity__user_deleted=False,deleted_at__isnull=True)
    qs=qs.select_related('opportunity','cv','cover_letter').order_by('opportunity__title','opportunity__company','pk'); q=_q(request)
    if q: qs=qs.filter(Q(opportunity__company__icontains=q)|Q(opportunity__title__icontains=q)|Q(opportunity__country__icontains=q)|Q(opportunity__contact_email__icontains=q)|Q(opportunity__target_url__icontains=q)|Q(opportunity__url__icontains=q)|Q(status__icontains=q)|Q(opportunity__channel__icontains=q))
    read_state=request.GET.get('read',''); stage=request.GET.get('stage','')
    history_status_token='__history__'
    history_states={'applied','reply','interview','rejected','accepted','closed'}
    valid_status_values={value for value,_label in Application.STATUS}
    valid_channel_values={value for value,_label in Opportunity.CHANNEL}
    def _canonical_application_status(value):
        value=str(value or '').strip()
        if value == history_status_token or value.lower()=='history':
            return history_status_token
        return value if value in valid_status_values else ''
    def _canonical_application_channel(value):
        value=str(value or '').strip()
        return value if value in valid_channel_values else ''
    def _apply_application_status_filters(queryset, values, mode):
        if mode=='custom' and not values:
            return queryset.none()
        if mode!='custom':
            return queryset
        wanted=set()
        for value in values:
            if value==history_status_token:
                wanted.update(history_states)
            elif value in valid_status_values:
                wanted.add(value)
        return queryset.filter(status__in=list(wanted)) if wanted else queryset.none()
    def _apply_application_channel_filters(queryset, values, mode):
        if mode=='custom' and not values:
            return queryset.none()
        if mode!='custom':
            return queryset
        wanted=[value for value in values if value in valid_channel_values]
        return queryset.filter(opportunity__channel__in=wanted) if wanted else queryset.none()
    status_state=_request_multi_filter_state(request,'status',canonicalizer=_canonical_application_status)
    if stage=='history' and not request.GET.getlist('status') and request.GET.get('status_mode','').lower()!='all':
        status_state={'mode':'custom','values':[history_status_token],'is_all':False,'is_none':False}
    status_filter_values=status_state['values']
    status=''
    if len(status_filter_values)==1 and status_filter_values[0] != history_status_token:
        status=status_filter_values[0]
    channel_state=_request_multi_filter_state(request,'channel',canonicalizer=_canonical_application_channel)
    channel_filter_values=channel_state['values']
    channel=channel_filter_values[0] if len(channel_filter_values)==1 else ''
    country_state=_request_multi_filter_state(request,'country',canonicalizer=_canonical_country_name)
    country_filter_values=country_state['values']
    country_filter=country_filter_values[0] if len(country_filter_values)==1 else ''
    country_count_base=qs
    if read_state=='unread': country_count_base=country_count_base.filter(is_read=False)
    elif read_state=='read': country_count_base=country_count_base.filter(is_read=True)
    country_count_base=_apply_application_status_filters(country_count_base,status_filter_values,status_state['mode'])
    country_count_base=_apply_application_channel_filters(country_count_base,channel_filter_values,channel_state['mode'])
    country_options=_country_filter_options(country_count_base,'opportunity__country')
    country_total=_country_filter_total(country_options)
    selected_countries={str(x) for x in country_filter_values}
    for row in country_options:
        row['selected']=(country_state['mode']!='custom' or str(row.get('value')) in selected_countries)
    country_filter_label=_multi_filter_label('locations',country_filter_values,_selected_labels(country_options,country_filter_values),country_state['mode'],country_total)
    qs=_apply_country_filters(qs,'opportunity__country',country_filter_values,country_state['mode'])
    application_count_base=qs
    application_count_rows=list(application_count_base.values('status','is_read','opportunity__channel','opportunity__extracted_facts'))
    application_filter_counts={'total':len(application_count_rows),'read':0,'unread':0,'application':0,'outreach':0,'status':{},'channel':{},'history':0}
    for row in application_count_rows:
        application_filter_counts['read' if row.get('is_read') else 'unread']+=1
        state=str(row.get('status') or '')
        application_filter_counts['status'][state]=application_filter_counts['status'].get(state,0)+1
        if state in history_states: application_filter_counts['history']+=1
        channel_key=str(row.get('opportunity__channel') or '')
        application_filter_counts['channel'][channel_key]=application_filter_counts['channel'].get(channel_key,0)+1
        outreach=bool((row.get('opportunity__extracted_facts') or {}).get('outreach'))
        application_filter_counts['outreach' if outreach else 'application']+=1
    status_options=[{'value':history_status_token,'label':'History','count':application_filter_counts['history']}]
    status_options.extend({'value':value,'label':label,'count':application_filter_counts['status'].get(value,0)} for value,label in Application.STATUS)
    status_options=_option_selection_state(status_options,status_filter_values,status_state['mode'])
    status_filter_label=_filter_options_label('statuses',status_options,status_filter_values,status_state['mode'],application_filter_counts['total'])
    channel_options=_option_selection_state([{'value':value,'label':label,'count':application_filter_counts['channel'].get(value,0)} for value,label in Opportunity.CHANNEL],channel_filter_values,channel_state['mode'])
    channel_filter_label=_filter_options_label('channels',channel_options,channel_filter_values,channel_state['mode'],application_filter_counts['total'])
    if read_state=='unread': qs=qs.filter(is_read=False)
    elif read_state=='read': qs=qs.filter(is_read=True)
    qs=_apply_application_status_filters(qs,status_filter_values,status_state['mode'])
    qs=_apply_application_channel_filters(qs,channel_filter_values,channel_state['mode'])
    if request.GET.get('export')=='1':
        return _xlsx('applications_and_outreach.xlsx',['Company','Role','Type','Location','URL','Channel','Status','Applied','Date Added','Resume','Cover Letter','Contact','Contact Email','Subject','Notes','Created','Updated'],[(a.opportunity.company,a.opportunity.title,'Outreach' if (a.opportunity.extracted_facts or {}).get('outreach') else 'Application',a.opportunity.country,_public_record_url(a.opportunity.target_url,a.opportunity.canonical_url,a.opportunity.url),a.opportunity.get_channel_display(),a.get_status_display(),a.applied_at or '',a.date_added,a.cv.label if a.cv else '',a.cover_letter.label if a.cover_letter else '',a.opportunity.contact_name,a.opportunity.contact_email,a.email_subject,a.notes,a.created_at,a.updated_at) for a in qs[:5000]])
    for app in qs:
        app.display_url=_public_record_url(app.opportunity.target_url,app.opportunity.canonical_url,app.opportunity.url)
    candidates=ImportCandidate.objects.filter(imported=False)[:500]
    last_mail_scan=BackgroundJob.objects.filter(kind='mail_scan').order_by('-created_at').first()
    import_jobs=BackgroundJob.objects.filter(kind__in=['import_text','import_document','mail_scan'],status__in=['queued','running']).order_by('-created_at')[:20]
    queued_preparations=BackgroundJob.objects.filter(kind='prepare',status__in=['queued','running']).order_by('-created_at')[:12]
    return render(request,'portal/applications.html',ctx(request,'applications','Applications & Outreach',applications=qs,q=q,queued_preparations=queued_preparations,cvs=DocumentAsset.objects.filter(kind='cv',active=True),covers=DocumentAsset.objects.filter(kind='cover',active=True),channels=Opportunity.CHANNEL,statuses=Application.STATUS,status_filter=status,channel_filter=channel,status_values=status_filter_values,status_options=status_options,status_filter_label=status_filter_label,status_filter_mode=status_state['mode'],channel_values=channel_filter_values,channel_options=channel_options,channel_filter_label=channel_filter_label,channel_filter_mode=channel_state['mode'],read_state=read_state,stage=stage,candidates=candidates,last_mail_scan=last_mail_scan,import_jobs=import_jobs,application_filter_counts=application_filter_counts,country_filter=country_filter,country_options=country_options,country_total=country_total,country_filter_label=country_filter_label,country_filter_mode=country_state['mode'],show_deleted=show_deleted))


def _save_application_editor_fields(request, app, include_email=True):
    opp=app.opportunity
    if 'company' in request.POST:
        company=request.POST.get('company','').strip()
        if len(company)>=2: opp.company=company[:220]
    if 'title' in request.POST:
        title=request.POST.get('title','').strip()
        if len(title)>=2: opp.title=title[:300]
    if 'country' in request.POST:
        country=request.POST.get('country','').strip()[:120]
        if not country or country in COUNTRIES: opp.country=country
    if 'remote_text' in request.POST: opp.remote_text=request.POST.get('remote_text','').strip()[:220]
    if 'contact_name' in request.POST: opp.contact_name=request.POST.get('contact_name','').strip()[:200]
    if 'contact_email' in request.POST: opp.contact_email=clean_contact_email(request.POST.get('contact_email',''))
    if 'description' in request.POST: opp.description=request.POST.get('description','')
    if 'url' in request.POST:
        url=request.POST.get('url','').strip()
        if url and re.match(r'^https?://',url,re.I):
            opp.url=url; opp.canonical_url=url; opp.target_url=url
    if 'channel' in request.POST and request.POST.get('channel') in dict(Opportunity.CHANNEL): opp.channel=request.POST.get('channel')
    if 'status' in request.POST and request.POST.get('status') in dict(Application.STATUS):
        old=app.status; app.status=request.POST.get('status')
        historical=app.status in ('applied','reply','interview','rejected','accepted','closed')
        if historical:
            opp.status='applied'
            if old not in ('applied','reply','interview','rejected','accepted','closed'): app.date_added=timezone.now()
    if 'applied_at' in request.POST:
        raw=request.POST.get('applied_at','').strip(); app.applied_at=None
        if raw:
            try:
                try: parsed=datetime.strptime(raw,'%Y-%m-%dT%H:%M:%S')
                except ValueError: parsed=datetime.strptime(raw,'%Y-%m-%dT%H:%M')
                app.applied_at=timezone.make_aware(parsed)
            except Exception: pass
    if include_email and 'email_subject' in request.POST: app.email_subject=request.POST.get('email_subject','')
    if include_email and 'email_body' in request.POST: app.email_body=personalize_email_body(request.POST.get('email_body',''), Profile.objects.get_or_create(pk=1)[0], opp)
    if include_email and 'email_mode' in request.POST and request.POST.get('email_mode') in ('plain','html'): app.email_mode=request.POST.get('email_mode')
    if 'notes' in request.POST: app.notes=request.POST.get('notes','')
    if 'cv_id' in request.POST:
        raw=(request.POST.get('cv_id') or '').strip()
        app.cv=DocumentAsset.objects.filter(pk=int(raw),kind='cv',active=True).first() if raw.isdigit() else None
    if 'cover_id' in request.POST:
        raw=(request.POST.get('cover_id') or '').strip()
        app.cover_letter=DocumentAsset.objects.filter(pk=int(raw),kind='cover',active=True).first() if raw.isdigit() else None
    if include_email:
        for field in ('attach_generated_cv','attach_generated_cv_pdf','attach_generated_cover','attach_generated_cover_pdf'):
            if field in request.POST or f'{field}_present' in request.POST:
                setattr(app,field,bool(request.POST.get(field)))
    opp.save(); app.save()


@login_required
def application_edit(request,pk):
    app=get_object_or_404(Application.objects.filter(opportunity__user_deleted=False,deleted_at__isnull=True).select_related('opportunity','cv','cover_letter'),pk=pk)
    profile=Profile.objects.get_or_create(pk=1)[0]
    repaired=personalize_email_body(app.email_body,profile,app.opportunity)
    if repaired!=app.email_body:
        app.email_body=repaired; app.save(update_fields=['email_body','updated_at'])
    if not app.is_read:
        Application.objects.filter(pk=app.pk,is_read=False).update(is_read=True)
        app.is_read=True
    if request.method=='POST':
        action=request.POST.get('action','save')
        if action=='save':
            _save_application_editor_fields(request,app); log('application.edit',request,app)
            job=BackgroundJob.objects.create(kind='prepare',label=f'Save IMAP draft: {app.opportunity.title}'[:300],message='Queued',result={'application_id':app.pk})
            task=application_imap_save_job.delay(job.pk,app.pk); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
            messages.success(request,'Record saved. IMAP Drafts update is running in the background.')
            if request.POST.get('generate_cv'):
                job=BackgroundJob.objects.create(kind='prepare',label=f'Tailor Resume: {app.opportunity.title}'[:300],message='Queued',result={'application_id':app.pk})
                task=application_cv_job.delay(job.pk,app.pk); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id']); messages.success(request,'Tailored Resume generation queued.')
        elif action=='generate_answers':
            questions=request.POST.get('website_questions','').strip()
            if not questions: messages.error(request,'Paste the role-specific questions first.')
            else:
                job=BackgroundJob.objects.create(kind='prepare',label=f'Application answers: {app.opportunity.title}'[:300],message='Queued',result={'application_id':app.pk})
                task=application_answers_job.delay(job.pk,app.pk,questions,request.POST.get('answer_provider') or '',request.POST.get('answer_model') or ''); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id']); messages.success(request,'Application-answer drafting queued.')
        elif action=='compare_models':
            selected=request.POST.getlist('model_choice')[:4]
            if not selected: messages.error(request,'Select at least one model/provider to compare.')
            else:
                job=BackgroundJob.objects.create(kind='prepare',label=f'Compare email drafts: {app.opportunity.title}'[:300],message='Queued',result={'application_id':app.pk})
                task=application_compare_job.delay(job.pk,app.pk,selected); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id']); messages.success(request,'Email comparison queued.')
        elif action=='use_version':
            v=get_object_or_404(GeneratedTextVersion,pk=request.POST.get('version_id'),application=app); app.email_subject=v.subject; app.email_body=personalize_email_body(v.body,Profile.objects.get_or_create(pk=1)[0],app.opportunity); app.email_mode='plain'; app.save(); messages.success(request,f'Loaded {v.provider}/{v.model} output into the editor. Use Save Draft to persist it in ScoutBox and IMAP Drafts.')
        return redirect('application_edit',pk=pk)
    jobs=BackgroundJob.objects.filter(kind='prepare',result__application_id=app.pk).order_by('-created_at')[:30]
    model_choices=_model_choices(); provider_models={}
    provider_labels={'ollama':'Ollama','openai':'OpenAI','gemini':'Gemini','openrouter':'OpenRouter'}
    for choice in model_choices:
        provider_models.setdefault(choice['provider'],[])
        if choice['model'] not in provider_models[choice['provider']]:
            provider_models[choice['provider']].append(choice['model'])
    answer_providers=[{'value':key,'label':provider_labels.get(key,key.replace('_',' ').title())} for key in provider_models]
    app.display_url=_public_record_url(app.opportunity.target_url,app.opportunity.canonical_url,app.opportunity.url)
    return render(request,'portal/application_edit.html',ctx(request,'applications',f'{app.opportunity.company} — {app.opportunity.title}',breadcrumbs=[{'label':'ScoutBox','route':'dashboard'},{'label':'Applications & Outreach','route':'applications'},{'label':f'{app.opportunity.company} — {app.opportunity.title}','route':None}],application=app,cvs=DocumentAsset.objects.filter(kind='cv',active=True),covers=DocumentAsset.objects.filter(kind='cover',active=True),statuses=Application.STATUS,model_choices=model_choices,answer_providers=answer_providers,answer_provider_models=provider_models,versions=app.text_versions.all()[:40],prepared_files=app.prepared_files.all()[:40],jobs=jobs))

@login_required
@require_POST
def application_save_async(request,pk):
    # Persist ScoutBox first. A broker/worker outage must never make a successful database
    # save look like it failed; IMAP synchronization is a separately reported background step.
    try:
        app=get_object_or_404(Application.objects.filter(opportunity__user_deleted=False,deleted_at__isnull=True).select_related('opportunity','cv','cover_letter'),pk=pk)
        save_mode=(request.POST.get('save_mode') or 'draft').strip().lower()
        details_only=(save_mode=='details')
        _save_application_editor_fields(request,app,include_email=not details_only); log('application.edit',request,app)
    except Exception as exc:
        logger.exception('Application database save failed for %s',pk)
        return JsonResponse({'ok':False,'error':str(exc) or 'Unable to save application/outreach draft.'},status=500)
    if details_only:
        messages.success(request,'Application / outreach changes saved.')
        return JsonResponse({'ok':True,'application_id':app.pk,'job_ids':[],'message':'Changes saved in ScoutBox.','redirect_url':reverse('applications')})
    job=BackgroundJob.objects.create(kind='prepare',label=f'Save IMAP draft: {app.opportunity.title}'[:300],message='Queued',result={'application_id':app.pk,'tool':'imap_save'})
    try:
        task=application_imap_save_job.delay(job.pk,app.pk); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
        return JsonResponse({'ok':True,'application_id':app.pk,'job_ids':[job.pk],'message':'Saved in ScoutBox. IMAP Drafts update queued.'})
    except Exception as exc:
        logger.exception('Application IMAP queue submission failed for %s',pk)
        job.status='failed'; job.error=str(exc); job.message='ScoutBox saved; IMAP update could not be queued'; job.finished_at=timezone.now(); job.save(update_fields=['status','error','message','finished_at'])
        return JsonResponse({'ok':True,'application_id':app.pk,'job_ids':[],'imap_queue_failed':True,'message':'Saved in ScoutBox. IMAP Drafts update could not be queued; check worker/broker status.'})


@login_required
@require_POST
def application_tool_async(request,pk):
    """Queue application-editor tools or apply a generated preview. Always returns JSON."""
    try:
        app=get_object_or_404(Application.objects.filter(opportunity__user_deleted=False,deleted_at__isnull=True).select_related('opportunity','cv','cover_letter'),pk=pk)
        action=(request.POST.get('action') or '').strip()
        if action=='compare_model':
            choice=(request.POST.get('model_choice') or '').strip()
            valid={x['value'] for x in _model_choices()}
            if choice not in valid: return JsonResponse({'ok':False,'error':'Choose a valid model.'},status=400)
            job=BackgroundJob.objects.create(kind='prepare',label=f'Tailor email: {app.opportunity.title}'[:300],message='Queued',result={'application_id':app.pk,'tool':'compare_model'})
            task=application_compare_job.delay(job.pk,app.pk,[choice]); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
            return JsonResponse({'ok':True,'job_id':job.pk,'message':'Tailored email generation queued.'})
        if action in ('generate_cv','generate_cover'):
            is_cover=action=='generate_cover'; label='Cover Letter' if is_cover else 'Resume'; asset_field='cover_letter' if is_cover else 'cv'
            raw=(request.POST.get('cover_id' if is_cover else 'cv_id') or '').strip()
            if not raw.isdigit(): return JsonResponse({'ok':False,'error':f'Select a {label}.'},status=400)
            asset=DocumentAsset.objects.filter(kind='cover' if is_cover else 'cv',active=True,pk=int(raw)).first()
            if not asset: return JsonResponse({'ok':False,'error':f'Select a valid {label}.'},status=400)
            setattr(app,asset_field,asset); app.save(update_fields=[asset_field,'updated_at'])
            job=BackgroundJob.objects.create(kind='prepare',label=f'Tailor {label}: {app.opportunity.title}'[:300],message='Queued',result={'application_id':app.pk,'tool':action})
            task=application_cv_job.delay(job.pk,app.pk,'cover' if is_cover else 'cv'); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
            return JsonResponse({'ok':True,'job_id':job.pk,'message':f'Tailored {label} generation queued.'})
        if action=='generate_answers':
            questions=(request.POST.get('questions') or '').strip()
            if not questions: return JsonResponse({'ok':False,'error':'Enter the ATS / website questions first.'},status=400)
            job=BackgroundJob.objects.create(kind='prepare',label=f'Application answers: {app.opportunity.title}'[:300],message='Queued',result={'application_id':app.pk,'tool':'answers'})
            task=application_answers_job.delay(job.pk,app.pk,questions,request.POST.get('provider') or '',request.POST.get('model') or ''); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
            return JsonResponse({'ok':True,'job_id':job.pk,'message':'Application-answer drafting queued.'})
        if action=='apply_version':
            version=get_object_or_404(GeneratedTextVersion,pk=request.POST.get('version_id'),application=app,kind='email')
            app.email_subject=version.subject
            app.email_body=personalize_email_body(version.body,Profile.objects.get_or_create(pk=1)[0],app.opportunity)
            app.email_mode='plain'; app.save(update_fields=['email_subject','email_body','email_mode','updated_at'])
            return JsonResponse({'ok':True,'subject':app.email_subject,'body':app.email_body,'message':'Preview applied to the email draft.'})
        if action=='select_prepared_file':
            prepared=get_object_or_404(PreparedApplicationFile,pk=request.POST.get('prepared_file_id'),application=app)
            prepared.selected_for_email=str(request.POST.get('selected','')).lower() in ('1','true','yes','on')
            prepared.save(update_fields=['selected_for_email'])
            return JsonResponse({'ok':True,'prepared_file_id':prepared.pk,'selected':prepared.selected_for_email})
        return JsonResponse({'ok':False,'error':'Unknown application tool.'},status=400)
    except Exception as exc:
        logger.exception('Application tool failed for %s',pk)
        return JsonResponse({'ok':False,'error':str(exc) or 'Application tool failed.'},status=500)


@login_required
def application_state_api(request,pk):
    try:
        app=get_object_or_404(Application.objects.filter(opportunity__user_deleted=False,deleted_at__isnull=True).select_related('opportunity','cv','cover_letter'),pk=pk)
        version=app.text_versions.filter(kind='email').first()
        versions=[{'id':v.pk,'kind':v.kind,'provider':v.provider,'model':v.model,'subject':v.subject,'body':v.body,'metadata':v.metadata or {},'created_at':timezone.localtime(v.created_at).strftime('%d/%m/%Y %H:%M:%S')} for v in app.text_versions.all()[:40]]
        prepared=[]
        for f in app.prepared_files.all()[:40]:
            try: url=f.file.url
            except Exception: url=''
            prepared.append({'id':f.pk,'kind':f.document_kind,'format':f.file_format,'label':f.label,'source_asset_label':f.source_asset_label,'selected':f.selected_for_email,'url':url,'metadata':f.metadata or {},'created_at':timezone.localtime(f.created_at).strftime('%d/%m/%Y %H:%M:%S')})
        jobs=[{'id':j.pk,'label':j.label,'status':j.status,'status_label':j.get_status_display(),'progress':j.progress,'message':j.message,'error':j.error,'created_at':timezone.localtime(j.created_at).strftime('%d/%m/%Y %H:%M:%S'),'finished':j.status in ('completed','failed','stopped'),'tool':(j.result or {}).get('tool',''),'result':j.result or {}} for j in BackgroundJob.objects.filter(kind='prepare',result__application_id=app.pk).order_by('-created_at')[:30]]
        return JsonResponse({
            'ok':True,'email_subject':app.email_subject or '','email_body':app.email_body or '',
            'generated_cv_url':app.generated_cv.url if app.generated_cv else '',
            'generated_cv_pdf_url':app.generated_cv_pdf.url if app.generated_cv_pdf else '',
            'generated_cover_url':app.generated_cover.url if app.generated_cover else '',
            'generated_cover_pdf_url':app.generated_cover_pdf.url if app.generated_cover_pdf else '',
            'website_answers':app.website_answers or {},'versions':versions,'prepared_files':prepared,'jobs':jobs,
            'latest_version':({'id':version.pk,'provider':version.provider,'model':version.model,'subject':version.subject,'body':version.body} if version else None),
        })
    except Exception as exc:
        return JsonResponse({'ok':False,'error':str(exc) or 'Unable to read application state.'},status=500)


@login_required
def application_save_draft(request,pk):
    app=get_object_or_404(Application,pk=pk)
    try: uid=save_draft(app); messages.success(request,f'Draft saved/updated in IMAP (UID {uid or "resolved by Message-ID"}).'); log('draft.save',request,app)
    except Exception as e: messages.error(request,str(e))
    return redirect('application_edit',pk=pk)


@login_required
def application_delete_draft(request,pk):
    app=get_object_or_404(Application,pk=pk)
    try: delete_draft(app,request.POST.get('reason','Deleted from application editor')); messages.success(request,'IMAP draft deleted and automatic recreation suppressed for the configured cooldown.'); log('draft.delete',request,app)
    except Exception as e: messages.error(request,str(e))
    return redirect('application_edit',pk=pk)


@login_required
def application_force_draft(request,pk):
    app=get_object_or_404(Application,pk=pk)
    try: uid=save_draft(app,force_create=True); messages.success(request,f'Draft recreated by manual override (UID {uid or "resolved"}).'); log('draft.force_create',request,app)
    except Exception as e: messages.error(request,str(e))
    return redirect('application_edit',pk=pk)


def _validate_mail_identity(p):
    profile=Profile.objects.get_or_create(pk=1)[0]
    imap_domain=(p.imap_email.split('@',1)[1].lower() if '@' in p.imap_email else '')
    smtp_domain=(p.notification_from_email.split('@',1)[1].lower() if '@' in p.notification_from_email else '')
    use_smtp=outgoing_method(p)=='smtp'
    smtp_login_domain=(p.smtp_username.split('@',1)[1].lower() if use_smtp and '@' in (p.smtp_username or '') else '')
    same_domain=bool(imap_domain and ((smtp_domain and imap_domain==smtp_domain) or (smtp_login_domain and imap_domain==smtp_login_domain)))
    same_account=bool(p.imap_email and ((p.notification_from_email and p.imap_email.lower()==p.notification_from_email.lower()) or (use_smtp and p.smtp_username and p.imap_email.lower()==p.smtp_username.lower())))
    sender=p.notification_from_name.strip().lower(); personal={profile.display_name.strip().lower(),p.imap_email.split('@')[0].lower() if p.imap_email else ''}
    same_name=bool(sender and sender in personal)
    return not (same_domain or same_account or same_name), {'same_domain':same_domain,'same_account':same_account,'same_name':same_name}


@login_required
def email_config_view(request):
    profiles={p.template:p for p in EmailProfile.objects.all()}; active=active_profile() or profiles.get('internal')
    selected=request.GET.get('template') or (active.template if active else 'internal')
    p=profiles.get(selected) or EmailProfile.objects.create(template=selected,active=not EmailProfile.objects.filter(active=True).exists())
    detected=request.session.pop(f'imap_folders_{selected}',[])
    if request.method=='POST':
        action=request.POST.get('action'); selected=request.POST.get('template',selected); p=EmailProfile.objects.get(template=selected)
        if action=='activate':
            EmailProfile.objects.update(active=False); p.active=True; p.save(); prof=Profile.objects.get_or_create(pk=1)[0]
            if p.imap_email: prof.application_email=p.imap_email; prof.save(update_fields=['application_email','updated_at'])
            messages.success(request,f'{p.get_template_display()} is now active. Saved credentials for the other template were kept.')
        elif action=='save':
            for f in ['imap_host','imap_email','imap_username','inbox_folder','sent_folder','drafts_folder','smtp_host','smtp_username','notification_from_name','notification_from_email']:
                setattr(p,f,request.POST.get(f,''))
            # Internal Development intentionally remains IMAP/SMTP only. External Mail
            # may use either SMTP or Resend's HTTPS API for ScoutBox-generated outgoing mail.
            requested_method=(request.POST.get('outgoing_method') or 'smtp').strip().lower()
            p.outgoing_method=(requested_method if p.template=='external' and requested_method in {'smtp','resend'} else 'smtp')
            if request.POST.get('resend_api_key'):
                p.resend_api_key_enc=encrypt(request.POST.get('resend_api_key'))
            
            try:
                p.imap_port=max(1,min(65535,int(request.POST.get('imap_port') or 993)))
                p.smtp_port=max(1,min(65535,int(request.POST.get('smtp_port') or 587)))
            except (TypeError,ValueError):
                messages.error(request,'IMAP and SMTP ports must be valid numbers between 1 and 65535.')
                return redirect(reverse('email_config')+f'?template={selected}')
            p.imap_ssl=bool(request.POST.get('imap_ssl')); p.smtp_tls=bool(request.POST.get('smtp_tls'))
            if request.POST.get('imap_password'): p.imap_password_enc=encrypt(request.POST.get('imap_password'))
            if request.POST.get('smtp_password'): p.smtp_password_enc=encrypt(request.POST.get('smtp_password'))
            ok,why=_validate_mail_identity(p)
            if not ok: messages.error(request,'Rejected: the outgoing sender must use a different account/domain and a different non-personal sender name from the application mailbox.')
            else:
                p.save();
                if p.active and p.imap_email:
                    prof=Profile.objects.get_or_create(pk=1)[0]; prof.application_email=p.imap_email; prof.save(update_fields=['application_email','updated_at'])
                messages.success(request,'Email configuration saved.'); log('email_profile.save',request,p)
        elif action=='folders':
            try: request.session[f'imap_folders_{selected}']=imap_folders(p); messages.success(request,'IMAP folders detected. Assign Inbox, Drafts and Sent below, then save the template.')
            except Exception as e: messages.error(request,str(e))
        elif action=='test_imap':
            try: im=imap_connect(p); im.logout(); messages.success(request,'IMAP connection succeeded.')
            except Exception as e: messages.error(request,f'IMAP failed: {e}')
        elif action=='test_smtp':
            try:
                smtp=smtplib.SMTP(p.smtp_host,p.smtp_port,timeout=10); smtp.ehlo()
                if p.smtp_tls: smtp.starttls(); smtp.ehlo()
                if p.smtp_username: smtp.login(p.smtp_username,decrypt(p.smtp_password_enc))
                smtp.quit(); messages.success(request,'Notification SMTP connection succeeded.')
            except Exception as e: messages.error(request,f'SMTP failed: {e}')
        elif action=='send_test':
            recipient=request.POST.get('test_recipient') or request.user.email
            try:
                event=send_notification(recipient,f'{settings.PORTAL_SHORT_NAME} test notification',f'This is an outgoing-mail test from the {p.get_template_display()} profile.',profile=p)
                pid=getattr(event,'message_id','') or ''
                messages.success(request,f'Test notification accepted for {recipient} via {outgoing_server_label(p)}.'+(f' Provider message ID: {pid}.' if pid else ''))
            except Exception as e: messages.error(request,f'Test notification failed: {e}')
        return redirect(reverse('email_config')+f'?template={selected}')
    return render(request,'portal/email_config.html',ctx(request,'settings','Email Configuration',system_tab='email',profile=p,selected=selected,detected=detected,all_profiles=profiles))


def _apply_outgoing_test_form(profile, data):
    """Persist the outgoing fields currently visible in Email Configuration before a send test.

    This prevents the test button from silently using an older saved SMTP selection when
    the user has just switched External Mail to Resend (or vice versa). Password/API-key
    fields remain unchanged when their form input is blank.
    """
    requested=(data.get('outgoing_method') or profile.outgoing_method or 'smtp').strip().lower()
    profile.outgoing_method=(requested if profile.template=='external' and requested in {'smtp','resend'} else 'smtp')
    profile.notification_from_name=(data.get('notification_from_name') or '').strip()
    profile.notification_from_email=(data.get('notification_from_email') or '').strip()
    if profile.outgoing_method=='resend':
        key=(data.get('resend_api_key') or '').strip()
        if key:
            profile.resend_api_key_enc=encrypt(key)
    else:
        profile.smtp_host=(data.get('smtp_host') or '').strip()
        profile.smtp_username=(data.get('smtp_username') or '').strip()
        try:
            profile.smtp_port=max(1,min(65535,int(data.get('smtp_port') or 587)))
        except (TypeError,ValueError):
            raise ValueError('SMTP port must be a valid number between 1 and 65535.')
        profile.smtp_tls=bool(data.get('smtp_tls'))
        password=(data.get('smtp_password') or '').strip()
        if password:
            profile.smtp_password_enc=encrypt(password)
    ok,_why=_validate_mail_identity(profile)
    if not ok:
        raise ValueError('Rejected: the outgoing sender must use a different account/domain and a different non-personal sender name from the application mailbox.')
    profile.save()
    return profile


@login_required
@require_POST
def email_profile_test_async(request):
    template=(request.POST.get('template') or 'internal').strip()
    profile=get_object_or_404(EmailProfile,template=template)
    action=(request.POST.get('test') or '').strip()
    if action not in ('imap','imap_config','smtp','folders','send'):
        return JsonResponse({'ok':False,'error':'Unknown email test.'},status=400)

    # SMTP send tests execute immediately. Previously they were always queued as a
    # Celery diagnostic, so a stopped/busy worker could leave the UI at "Queued"
    # indefinitely and no MailEvent was ever created. send_notification owns the
    # outgoing history record and updates it to sent/failed before this request returns.
    if action=='send':
        recipient=(request.POST.get('recipient') or '').strip()
        subject=(request.POST.get('subject') or 'ScoutBox outgoing test').strip()[:500]
        body=(request.POST.get('body') or '').strip()
        if not recipient:
            return JsonResponse({'ok':False,'finished':True,'error':'Enter a recipient for the outgoing-mail test.'},status=200)
        attempt_at=timezone.now()
        try:
            profile=_apply_outgoing_test_form(profile,request.POST)
            event=send_notification(recipient,subject,body,profile=profile)
            provider_id=getattr(event,'message_id','') or ''
            suffix=f' Provider message ID: {provider_id}.' if provider_id else ''
            return JsonResponse({'ok':True,'finished':True,'message':f'Outgoing configuration saved. Test email accepted via {outgoing_server_label(profile)}.{suffix}','mail_event_id':event.pk if event else None,'provider_message_id':provider_id,'delivery_status':getattr(event,'delivery_status','')})
        except Exception as exc:
            event=MailEvent.objects.filter(kind='notification',recipients=recipient,subject=subject,occurred_at__gte=attempt_at).order_by('-occurred_at').first()
            if not event:
                # Validation can fail before send_notification creates its normal event
                # (for example a missing SMTP host/from address). Preserve that failed
                # attempt in history as well so the test is always auditable.
                event=MailEvent.objects.create(
                    kind='notification',subject=subject,sender=profile.notification_from_email,recipients=recipient,
                    body_excerpt=body[:1000],body_text=body,delivery_status='failed',delivery_error=str(exc)[:1000],
                    server=outgoing_server_label(profile),
                    occurred_at=timezone.now(),metadata={'template':profile.template,'outgoing_method':outgoing_method(profile),'smtp_host':profile.smtp_host,'smtp_port':profile.smtp_port,'outgoing_test':True},
                )
            return JsonResponse({'ok':False,'finished':True,'error':str(exc)[:800],'message':'Outgoing-mail test failed. The attempt is recorded in Email History.','mail_event_id':event.pk if event else None},status=200)

    # Connection-only SMTP diagnostics are also synchronous so their result never
    # depends on a background worker. They do not create a mail record because no
    # message is transmitted; the Send test above is the user-facing SMTP test.
    if action=='smtp':
        if outgoing_method(profile)=='resend':
            return JsonResponse({'ok':False,'finished':True,'error':'This External Mail profile uses Resend API, not SMTP. Use Send test email instead.'},status=200)
        smtp=None
        try:
            if not profile.smtp_host:
                raise RuntimeError('SMTP host is not configured.')
            smtp=smtplib.SMTP(profile.smtp_host,profile.smtp_port,timeout=15); smtp.ehlo()
            if profile.smtp_tls:
                smtp.starttls(); smtp.ehlo()
            if profile.smtp_username:
                smtp.login(profile.smtp_username,decrypt(profile.smtp_password_enc))
            return JsonResponse({'ok':True,'finished':True,'message':f'SMTP connection succeeded: {profile.smtp_host}:{profile.smtp_port}.'})
        except Exception as exc:
            return JsonResponse({'ok':False,'finished':True,'error':str(exc)[:800]},status=200)
        finally:
            if smtp:
                try: smtp.quit()
                except Exception: pass

    job=BackgroundJob.objects.create(kind='diagnostic',label=f'Email test: {profile.get_template_display()} · {action}'[:300],message='Queued',result={'email_profile_id':profile.pk,'test':action})
    task=email_profile_test_job.delay(job.pk,profile.pk,action,(request.POST.get('recipient') or '').strip(),(request.POST.get('subject') or '').strip()[:500],(request.POST.get('body') or '').strip()); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
    return JsonResponse({'ok':True,'job_id':job.pk})


def _apply_incoming_browser_form(profile, data):
    """Save current Incoming/IMAP fields before browser refresh without touching Outgoing."""
    profile.imap_host=(data.get('imap_host') or '').strip()
    profile.imap_email=(data.get('imap_email') or '').strip()
    profile.imap_username=(data.get('imap_username') or '').strip()
    profile.inbox_folder=(data.get('inbox_folder') or profile.inbox_folder or 'INBOX').strip()
    profile.drafts_folder=(data.get('drafts_folder') or profile.drafts_folder or 'Drafts').strip()
    profile.sent_folder=(data.get('sent_folder') or profile.sent_folder or 'Sent').strip()
    try: profile.imap_port=max(1,min(65535,int(data.get('imap_port') or profile.imap_port or 993)))
    except (TypeError,ValueError): raise ValueError('IMAP port must be a valid number between 1 and 65535.')
    profile.imap_ssl=bool(data.get('imap_ssl'))
    password=(data.get('imap_password') or '').strip()
    if password: profile.imap_password_enc=encrypt(password)
    profile.save(update_fields=['imap_host','imap_email','imap_username','inbox_folder','drafts_folder','sent_folder','imap_port','imap_ssl','imap_password_enc','updated_at'])
    if profile.active and profile.imap_email:
        prof=Profile.objects.get_or_create(pk=1)[0]
        if prof.application_email != profile.imap_email:
            prof.application_email=profile.imap_email; prof.save(update_fields=['application_email','updated_at'])
    return profile


@login_required
def email_browser_api(request):
    template=(request.GET.get('template') or request.POST.get('template') or 'internal').strip()
    profile=get_object_or_404(EmailProfile,template=template)
    action=(request.GET.get('action') or request.POST.get('action') or 'folders').strip()
    try:
        if request.method=='POST' and action=='delete':
            folder=(request.POST.get('folder') or '').strip(); uid=(request.POST.get('uid') or '').strip()
            if not folder or not uid: return JsonResponse({'ok':False,'error':'Folder and message UID are required.'},status=400)
            delete_imap_draft(profile,folder,uid)
            return JsonResponse({'ok':True,'message':'Draft deleted.'})
        if request.method=='POST' and action=='save_incoming':
            profile=_apply_incoming_browser_form(profile,request.POST)
            return JsonResponse({'ok':True,'message':'Folder assignments saved.'})
        if request.method=='POST' and action in ('folders_background','populate_test_background'):
            profile=_apply_incoming_browser_form(profile,request.POST)
            test_action='folders' if action=='folders_background' else 'populate_test'
            label='Refresh IMAP folders' if test_action=='folders' else 'Generate IMAP browser test emails'
            job=BackgroundJob.objects.create(
                kind='diagnostic',label=f'{label}: {profile.get_template_display()}'[:300],
                message='Queued',result={'email_profile_id':profile.pk,'test':test_action,'imap_browser':True},
            )
            try:
                task=email_profile_test_job.delay(job.pk,profile.pk,test_action,'','','')
                job.celery_task_id=task.id or ''
                job.save(update_fields=['celery_task_id'])
            except Exception as exc:
                job.status='failed'; job.finished_at=timezone.now(); job.progress=100; job.message='Unable to queue IMAP browser task'; job.error=str(exc)[:1000]
                job.save(update_fields=['status','finished_at','progress','message','error'])
                return JsonResponse({'ok':False,'error':f'Unable to queue IMAP browser task: {exc}'},status=503)
            return JsonResponse({'ok':True,'job_id':job.pk})
        if request.method=='POST' and action=='populate_test':
            # Backward-compatible synchronous endpoint retained for older clients.
            profile=_apply_incoming_browser_form(profile,request.POST)
            count=populate_test_messages(profile)
            return JsonResponse({'ok':True,'message':f'Generated {count} IMAP test emails — one each in Inbox, Drafts and Sent.','count':count})
        if action=='folders':
            if request.method=='POST':
                profile=_apply_incoming_browser_form(profile,request.POST)
            rows=imap_folders(profile)
            lower={f.lower():f for f in rows}
            def choose(current, hints, fallback=''):
                if current and current in rows: return current
                if current and current.lower() in lower: return lower[current.lower()]
                for hint in hints:
                    exact=lower.get(hint)
                    if exact: return exact
                for f in rows:
                    if any(h in f.lower() for h in hints): return f
                return fallback or (rows[0] if rows else '')
            mapping={
                'inbox':choose(profile.inbox_folder,['inbox'],'INBOX'),
                'drafts':choose(profile.drafts_folder,['draft','drafts'],'Drafts'),
                'sent':choose(profile.sent_folder,['sent','sent items','sent mail'],'Sent'),
            }
            return JsonResponse({'ok':True,'folders':rows,'mapping':mapping})
        folder=(request.GET.get('folder') or '').strip()
        if not folder: return JsonResponse({'ok':False,'error':'Select an IMAP folder.'},status=400)
        if action=='messages':
            return JsonResponse({'ok':True,'folder':folder,'messages':browse_folder(profile,folder,limit=60),'can_delete':folder.strip().casefold()==(profile.drafts_folder or 'Drafts').strip().casefold()})
        if action=='message':
            uid=(request.GET.get('uid') or '').strip()
            if not uid: return JsonResponse({'ok':False,'error':'Message UID is required.'},status=400)
            row=fetch_imap_message(profile,folder,uid); row['can_delete']=folder.strip().casefold()==(profile.drafts_folder or 'Drafts').strip().casefold()
            return JsonResponse({'ok':True,'message':row})
        return JsonResponse({'ok':False,'error':'Unknown browser action.'},status=400)
    except Exception as exc:
        return JsonResponse({'ok':False,'error':str(exc)},status=502)


@login_required
def email_history_view(request):
    date_period,date_start,date_end,date_from,date_to=_log_date_bounds(request)
    qs=_apply_log_date_bounds(MailEvent.objects.all(),'occurred_at',date_start,date_end); q=_q(request)
    kind=(request.GET.get('kind') or '').strip().lower()
    if kind=='inbox': qs=qs.filter(kind='inbox')
    elif kind=='outgoing': qs=qs.filter(kind__in=['notification','sent'])
    elif kind=='draft': qs=qs.filter(kind__in=['draft','draft_delete'])
    if q:
        qs=qs.filter(Q(subject__icontains=q)|Q(sender__icontains=q)|Q(recipients__icontains=q)|Q(delivery_status__icontains=q)|Q(server__icontains=q)|Q(folder__icontains=q))
    if request.GET.get('export')=='1':
        return _xlsx('email_history.xlsx',['Direction','Server','Status','Subject','From','To','Folder','UID','When'],[('Incoming' if e.kind=='inbox' else 'Outgoing' if e.kind in ('notification','sent') else e.get_kind_display(),e.server,e.delivery_status,e.subject,e.sender,e.recipients,e.folder,e.uid,e.occurred_at) for e in qs[:10000]])
    profile=active_profile(); warnings=[]
    if not profile: warnings.append(('Email profile','No active email profile.','email_config'))
    else:
        if not profile.imap_host or not profile.imap_username: warnings.append(('IMAP','Incoming mailbox is not configured.','email_config'))
        method=outgoing_method(profile)
        if method=='resend':
            if not profile.resend_api_key_enc or not profile.notification_from_email: warnings.append(('Resend','Outgoing Resend API is not configured.','email_config'))
        elif not profile.smtp_host or not profile.notification_from_email:
            warnings.append(('SMTP','Outgoing notification mail is not configured.','email_config'))
    incoming=qs.filter(kind='inbox').order_by('-occurred_at')[:1000]
    outgoing=qs.filter(kind__in=['notification','sent']).order_by('-occurred_at')[:1000]
    other=qs.filter(kind__in=['draft','draft_delete']).order_by('-occurred_at')[:500]
    return render(request,'portal/email_history.html',ctx(request,'email_history','Email History',incoming=incoming,outgoing=outgoing,other=other,q=q,mail_warnings=warnings,date_period=date_period,date_from=date_from,date_to=date_to))


@login_required
def email_event_body(request,pk):
    event=get_object_or_404(MailEvent,pk=pk)
    try:
        full=bool(event.body_text or event.body_html)
        body=event.body_text or event.body_excerpt or ''
        if not full and event.folder and event.uid:
            body,full=fetch_event_body(event)
            if full:
                event.body_text=body; event.save(update_fields=['body_text'])
        html_body=_sanitize_email_html(event.body_html) if event.body_html else rich_html(body)
        return JsonResponse({'ok':True,'full':full,'body':body,'html':html_body,'subject':event.subject,'sender':event.sender,'recipients':event.recipients,'when':timezone.localtime(event.occurred_at).strftime('%d/%m/%Y %H:%M:%S %Z'),'kind':event.get_kind_display(),'server':event.server,'folder':event.folder,'uid':event.uid,'delivery_status':event.delivery_status,'delivery_error':event.delivery_error,'message_id':event.message_id,'metadata':event.metadata or {},'classification':event.classification})
    except Exception as exc:
        return JsonResponse({'ok':False,'body':event.body_excerpt or '','html':rich_html(event.body_excerpt or ''),'full':False,'error':str(exc)[:300],'subject':event.subject,'sender':event.sender,'recipients':event.recipients,'server':event.server,'delivery_status':event.delivery_status},status=200)


def _contact_re_evaluate_ids(request, local_only=False, cloud_only=False):
    """Address Book IDs matching current filters, optionally filtered by Fit provenance."""
    qs=Contact.objects.filter(deleted_at__isnull=True).filter(Q(generic=False)|Q(source__iexact='manual'))
    q=((request.POST.get('q') if request.method=='POST' else '') or _q(request)).strip()
    if q:
        qs=qs.filter(Q(name__icontains=q)|Q(email__icontains=q)|Q(phone__icontains=q)|Q(company__icontains=q)|Q(company_country__icontains=q)|Q(company_summary__icontains=q)|Q(title__icontains=q))
    country_state=_request_multi_filter_state(request,'country',canonicalizer=_canonical_country_name)
    focus_state=_request_multi_filter_state(request,'focus')
    qs=_apply_country_filters(qs,'company_country',country_state['values'],country_state['mode'])
    qs=_apply_focus_filters(qs, focus_state['values'],focus_state['mode'])
    read_state=(request.GET.get('read') or '').strip().lower()
    if read_state=='new': qs=qs.filter(is_read=False)
    elif read_state=='seen': qs=qs.filter(is_read=True)
    company_size_filter,company_age_filter,contact_method_filter=_company_filter_state(request,'contact')
    qs=_apply_company_info_quick_filter(qs,company_size_filter,company_age_filter,contact_method_filter)
    qs=qs.order_by('-last_seen')
    if local_only or cloud_only:
        rows=qs.only('pk','company_intel','source')
        return _local_assessment_ids(rows) if local_only else _cloud_assessment_ids(rows)
    return list(qs.values_list('pk',flat=True))


@login_required
@require_GET
def re_evaluation_scope_counts(request, kind):
    """Return provenance-aware counts for the current re-evaluation filters on demand."""
    if kind=='opportunity':
        ids=_opportunity_re_evaluate_ids(request)
        rows=Opportunity.objects.filter(pk__in=ids,suppressed=False,user_deleted=False).select_related('source').only('pk','extracted_facts','company_intel','source__name')
    elif kind=='hidden-lead':
        ids=_hidden_lead_re_evaluate_ids(request)
        rows=CompanyLead.objects.filter(pk__in=ids,user_deleted=False).select_related('source').only('pk','ai_state','company_intel','source__name')
    elif kind=='address-book':
        ids=_contact_re_evaluate_ids(request)
        rows=Contact.objects.filter(pk__in=ids,deleted_at__isnull=True).only('pk','company_intel','source')
    else:
        return JsonResponse({'ok':False,'error':'Unknown re-evaluation dataset.'},status=404)
    local=cloud=0
    for row in rows:
        if has_cloud_fit_assessment(row): cloud+=1
        elif has_local_fit_assessment(row): local+=1
    return JsonResponse({'ok':True,'total':len(ids),'local':local,'cloud':cloud})


@login_required
def contacts_view(request):
    if request.method=='GET' and request.GET.get('company_filter_reset')=='1':
        request.session.pop(_COMPANY_FILTER_SESSION_KEYS['contact'],None); request.session.modified=True
        return _company_filter_clean_redirect(request)
    # Address Book list rendering is read-only with respect to record lifecycle. Existing
    # entries — including legacy addresses that would no longer pass today's automatic
    # contact rules — are never silently deleted merely because this page was opened.
    # Empty descriptions may be normalised without changing record membership.
    Contact.objects.filter(deleted_at__isnull=True,company_summary__in=['-','–','—']).update(company_summary='')
    # Repair older inferred rows in-place so the address book never falls back to a meaningless label.
    for row in Contact.objects.filter(deleted_at__isnull=True).filter(Q(company='')|Q(name='')|Q(name__iexact='Contact')|Q(source__icontains='Cloud Web')).only('pk','email','name','company','generic','source','company_country','company_summary')[:5000]:
        changed=[]
        if is_generic(row.email) and not row.generic:
            row.generic=True; changed.append('generic')
        if (row.name or '').strip().lower() in {'contact','unknown','n/a','none'}:
            row.name=''; changed.append('name')
        inferred_name=contact_name_from_email(row.email)
        cloud_owned='cloud web' in str(row.source or '').lower()
        if inferred_name and (not row.name or cloud_owned) and row.name != inferred_name:
            row.name=inferred_name; changed.append('name')
        inferred_company=contact_company_from_email(row.email)
        company_url=('https://'+row.email.split('@',1)[1]) if '@' in row.email else ''
        human_inferred=display_company_name(inferred_company,company_url) or inferred_company
        # Preserve a researched/official company name when it represents the same
        # domain slug (e.g. "Implicit Conversions"). Only repair missing or
        # obviously machine-compacted names such as "Implicitconversions".
        if human_inferred and not row.company:
            row.company=human_inferred; changed.append('company')
        elif human_inferred and cloud_owned and row.company:
            current_norm=re.sub(r'[^a-z0-9]+','',row.company.casefold())
            inferred_norm=re.sub(r'[^a-z0-9]+','',human_inferred.casefold())
            if current_norm==inferred_norm and ' ' not in row.company and ' ' in human_inferred:
                row.company=human_inferred; changed.append('company')
        clean_name=clean_contact_name(row.name,row.company)
        if clean_name != (row.name or ''):
            row.name=clean_name; changed.append('name')
        if row.company_summary.strip() in {'-','–','—'}:
            row.company_summary=''; changed.append('company_summary')
        if any(x in str(row.company_country or '').casefold() for x in ('remote','worldwide','global','anywhere')):
            row.company_country=''; changed.append('company_country')
        if changed: row.save(update_fields=list(dict.fromkeys(changed)))
    if request.method=='POST':
        action=request.POST.get('action')
        if action=='restore_row':
            row_id=(request.POST.get('row_id') or '').strip()
            ok,label=_restore_recycle_item('contact',int(row_id)) if row_id.isdigit() else (False,'Address Book')
            if request.headers.get('X-Requested-With')=='fetch':
                return JsonResponse({'ok':ok,'label':label,'error':'' if ok else 'This Address Book entry is not in the Recycle Bin.'},status=200 if ok else 404)
            (messages.success if ok else messages.warning)(request,(f'Restored {label}.' if ok else 'This Address Book entry is not in the Recycle Bin.'))
            return redirect(request.get_full_path())
        if action=='filter_selected':
            ids=[x for x in request.POST.getlist('contact_ids') if str(x).isdigit()]
            filter_scope=(request.POST.get('filter_scope') or '').strip().lower()
            filter_all=(request.POST.get('filter_all') or '')=='1' or filter_scope in {'all','local','cloud'}
            filter_local=filter_scope=='local'
            filter_cloud=filter_scope=='cloud'
            try:
                provider,model,internet_search,_options=_manual_filter_selection(request)
            except ValueError as exc:
                if request.headers.get('X-Requested-With')=='fetch': return JsonResponse({'ok':False,'error':str(exc)},status=400)
                messages.error(request,str(exc)); return redirect('contacts')
            selected=_contact_re_evaluate_ids(request,local_only=filter_local,cloud_only=filter_cloud) if filter_all else list(Contact.objects.filter(pk__in=ids,deleted_at__isnull=True).values_list('pk',flat=True))
            count=len(selected)
            if not count:
                error=('No matching Local AI assessments are available to re-evaluate.' if filter_local else ('No matching Cloud AI assessments are available to re-evaluate.' if filter_cloud else 'There are no active Address Book contacts matching this request.'))
                if request.headers.get('X-Requested-With')=='fetch': return JsonResponse({'ok':False,'error':error},status=400)
                messages.error(request,error)
            else:
                scope='Local AI' if filter_local else ('Cloud AI' if filter_cloud else ('matching' if filter_all else 'selected'))
                label=f'Re-evaluate {count} {scope} Address Book contact{"" if count == 1 else "s"}'
                result={
                    'selected':count,'contact_ids':selected,'processed':0,'kept':0,'recycled':0,'protected':0,'review':0,'failed':0,
                    'provider':provider,'model':model,'internet_search':internet_search,'scope':('local' if filter_local else ('cloud' if filter_cloud else ('all' if filter_all else 'selected'))),
                    'notify_email':_manual_filter_recipient(request),
                }
                job,active=_claim_manual_filter_job('filter_contacts',label,f'Queued · 0/{count} · {provider} · {model}',result)
                if active:
                    error='A re-evaluation is already running. Stop it from Dashboard > Background Work before starting another re-evaluation.'
                    if request.headers.get('X-Requested-With')=='fetch':
                        return JsonResponse({'ok':False,'error':error,'job_id':active.pk,'active_kind':active.kind,'active_label':active.label},status=409)
                    messages.error(request,error)
                else:
                    task=contact_filter_job.delay(job.pk,selected,provider,model,internet_search); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
                    if request.headers.get('X-Requested-With')=='fetch':
                        return JsonResponse({'ok':True,'count':count,'job_id':job.pk,'message':job.message,'provider':provider,'model':model,'internet_search':internet_search})
                    messages.success(request,f'Address Book re-evaluation queued for {count} {scope} contact{"" if count == 1 else "s"}.')
        elif action in ('add','edit'):
            email=(request.POST.get('email') or '').strip().lower()
            source_url=(request.POST.get('source_url') or '').strip(); phone=(request.POST.get('phone') or '').strip(); errors=[]
            if not email or not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$',email): errors.append('Enter a valid email address.')
            existing_row=Contact.objects.filter(pk=request.POST.get('contact_id'),deleted_at__isnull=True).first() if action=='edit' else None
            email_changed=not existing_row or (existing_row.email or '').strip().lower()!=email
            if email and email_changed and is_non_contact_address(email): errors.append('This administrative/privacy/compliance address cannot be assigned as a contact email.')
            if source_url and not re.match(r'^https?://',source_url,re.I): errors.append('Source URL must start with http:// or https://.')
            if phone and not re.match(r'^[+()0-9 .-]{5,80}$',phone): errors.append('Phone number contains unsupported characters.')
            if errors:
                for e in errors: messages.error(request,e)
            else:
                row=existing_row if action=='edit' else Contact.objects.filter(email=email).first()
                row=row or Contact(email=email)
                row.deleted_at=None; row.email=email
                company_input=request.POST.get('company','').strip()[:200]
                inferred_company=contact_company_from_email(email)
                company_url=('https://'+email.split('@',1)[1]) if '@' in email else ''
                row.company=company_input or display_company_name(inferred_company,company_url) or inferred_company
                row.name=clean_contact_name(request.POST.get('name','').strip()[:200] or contact_name_from_email(email),row.company)
                if 'company_country' in request.POST:
                    row.company_country=request.POST.get('company_country','').strip()[:120]
                    if any(x in row.company_country.casefold() for x in ('remote','worldwide','global','anywhere')): row.company_country=''
                row.company_summary=request.POST.get('company_summary','').strip()[:2000];
                if row.company_summary in {'-','–','—'}: row.company_summary=''
                row.title=request.POST.get('title','').strip()[:200]; row.phone=phone[:80]; row.source='manual'; row.source_url=source_url; row.generic=is_generic(email); row.confidence=max(row.confidence or 0,90); row.is_read=True; row.last_seen=timezone.now()
                # New manual Address Book rows receive their default-method Fit assessment
                # before the first INSERT. Reuse retained company context first when available
                # so Local AI has better evidence without any extra network request.
                if row.pk is None:
                    try:
                        pre_summary,pre_intel=stored_company_context(row.company,row.email,row.source_url)
                        if pre_intel: row.company_intel=pre_intel
                        if pre_summary and not row.company_summary: row.company_summary=pre_summary[:2000]
                    except Exception:
                        pass
                    assess_addressbook_contact_fit(row)
                # Never retire a previously collected contact merely because a newer row
                # appears stronger. Automatic replacement caused Local GPU contacts to
                # disappear after discovery. Duplicates can be reviewed/deleted explicitly.
                row.save()
                try:
                    # Reuse the originating Opportunity/Lead/cache immediately, then seed
                    # a no-network baseline. Queue public Company Research only when age/size
                    # is still unavailable.
                    summary,intel=stored_company_context(row.company,row.email,row.source_url)
                    changed=[]
                    if intel and not company_info_has_display_data(row): row.company_intel=intel; changed.append('company_intel')
                    if summary and not row.company_summary: row.company_summary=summary[:2000]; changed.append('company_summary')
                    if changed: row.save(update_fields=list(dict.fromkeys(changed)))
                    enrich_company_intel_from_retained(row)
                    try:
                        current_intel=dict(row.company_intel or {}); current_fit=current_intel.get('fit_classification') if isinstance(current_intel.get('fit_classification'),dict) else {}
                        if not ('score' in current_fit and current_fit.get('score') not in (None,'')):
                            assessed,_review=assess_addressbook_contact_fit(row)
                            if assessed: row.save(update_fields=['company_intel'])
                    except Exception:
                        pass
                    if not company_info_has_display_data(row):
                        active=BackgroundJob.objects.filter(kind='company_research',status__in=['queued','running'],result__contact_id=row.pk).first()
                        if not active:
                            job=BackgroundJob.objects.create(kind='company_research',label=f'Address Book company research: {row.company or row.email}'[:300],message='Queued',result={'contact_id':row.pk,'address_book':True,'phase':'initial'})
                            task=current_app.send_task('portal.tasks.contact_company_research_job',args=[job.pk,row.pk,'initial']); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
                except Exception:
                    pass
                messages.success(request,'Address book entry saved.')
        elif action=='delete':
            count=Contact.objects.filter(pk=request.POST.get('contact_id'),deleted_at__isnull=True).update(deleted_at=timezone.now()); messages.success(request,'Address book entry moved to the Recycle Bin.' if count else 'Address book entry was already removed.')
        elif action=='delete_selected':
            ids=[x for x in request.POST.getlist('contact_ids') if str(x).isdigit()]
            count=Contact.objects.filter(pk__in=ids,deleted_at__isnull=True).count() if ids else 0
            if count:
                Contact.objects.filter(pk__in=ids,deleted_at__isnull=True).update(deleted_at=timezone.now()); messages.success(request,f'Moved {count} selected contact{"" if count == 1 else "s"} to the Recycle Bin.')
            else: messages.info(request,'The selected Address Book contacts are already in the Recycle Bin or no longer active.')
        elif action in ('mark_seen','mark_new','mark_all_seen','mark_all_new'):
            ids=[x for x in request.POST.getlist('contact_ids') if str(x).isdigit()]
            all_items=action.startswith('mark_all_'); is_seen=action in ('mark_seen','mark_all_seen')
            target=Contact.objects.filter(deleted_at__isnull=True)
            if not all_items:
                if not ids:
                    if request.headers.get('X-Requested-With')=='fetch': return JsonResponse({'ok':False,'error':'Select at least one contact.'},status=400)
                    messages.error(request,'Select at least one contact.'); return redirect('contacts')
                target=target.filter(pk__in=ids)
            count=target.update(is_read=is_seen)
            if request.headers.get('X-Requested-With')=='fetch': return JsonResponse({'ok':True,'count':count,'is_read':is_seen,'all':all_items})
            messages.success(request,f'Marked {count} Address Book contact{"" if count == 1 else "s"} as {"Seen" if is_seen else "New"}.')
        elif action=='delete_all':
            count=Contact.objects.filter(deleted_at__isnull=True).count()
            Contact.objects.filter(deleted_at__isnull=True).update(deleted_at=timezone.now())
            messages.success(request,f'Moved all {count} address-book contact{"" if count == 1 else "s"} to the Recycle Bin.')
        return redirect('contacts')
    show_generic=False; show_deleted=_show_deleted_setting(request,'contacts')
    if show_deleted:
        qs=Contact.objects.filter(Q(deleted_at__isnull=False)|(Q(deleted_at__isnull=True)&(Q(generic=False)|Q(source__iexact='manual'))))
    else:
        qs=Contact.objects.filter(deleted_at__isnull=True).filter(Q(generic=False)|Q(source__iexact='manual'))
    q=_q(request)
    country_state=_request_multi_filter_state(request,'country',canonicalizer=_canonical_country_name)
    focus_state=_request_multi_filter_state(request,'focus')
    country_filter_values=list(country_state['values'])
    focus_filter_values=list(focus_state['values'])
    country_filter=country_filter_values[0] if len(country_filter_values)==1 else ''
    focus_filter=focus_filter_values[0] if len(focus_filter_values)==1 else ''
    read_state=(request.GET.get('read') or '').strip().lower()
    hide_non_200=(request.GET.get('healthy') or '')=='1'
    company_size_filter,company_age_filter,contact_method_filter=_company_filter_state(request,'contact')
    if q: qs=qs.filter(Q(name__icontains=q)|Q(email__icontains=q)|Q(phone__icontains=q)|Q(company__icontains=q)|Q(company_country__icontains=q)|Q(company_summary__icontains=q)|Q(title__icontains=q))
    facet_base=qs
    country_count_base=facet_base
    country_count_base=_apply_focus_filters(country_count_base, focus_filter_values, focus_state['mode'])
    if read_state=='new': country_count_base=country_count_base.filter(is_read=False)
    elif read_state=='seen': country_count_base=country_count_base.filter(is_read=True)
    country_options=_country_filter_options(country_count_base,'company_country')
    country_options=_prune_zero_roundtrip_country_options(country_options,country_count_base,'company_country')
    country_total=_country_filter_total(country_options)

    focus_count_base=facet_base
    focus_count_base=_apply_country_filters(focus_count_base,'company_country',country_filter_values,country_state['mode'])
    if read_state=='new': focus_count_base=focus_count_base.filter(is_read=False)
    elif read_state=='seen': focus_count_base=focus_count_base.filter(is_read=True)
    focus_options_rows=focus_options(focus_count_base)
    focus_total=sum(int(x.get('count') or 0) for x in focus_options_rows)
    selected_countries={str(x) for x in country_filter_values}
    for row in country_options:
        row['selected']=(country_state['mode']!='custom' or str(row.get('value')) in selected_countries)
    selected_focuses={str(x) for x in focus_filter_values}
    for row in focus_options_rows:
        row['selected']=(focus_state['mode']!='custom' or str(row.get('value')) in selected_focuses)
    country_filter_label=_multi_filter_label('locations',country_filter_values,_selected_labels(country_options,country_filter_values),country_state['mode'],country_total)
    focus_filter_label=_multi_filter_label('focuses',focus_filter_values,_selected_labels(focus_options_rows,focus_filter_values),focus_state['mode'],focus_total)

    read_count_base=facet_base
    read_count_base=_apply_country_filters(read_count_base,'company_country',country_filter_values,country_state['mode'])
    read_count_base=_apply_focus_filters(read_count_base, focus_filter_values, focus_state['mode'])
    contact_read_filter_counts={'total':read_count_base.count(),'seen':read_count_base.filter(is_read=True).count(),'new':read_count_base.filter(is_read=False).count()}

    qs=_apply_country_filters(qs,'company_country',country_filter_values,country_state['mode'])
    qs=_apply_focus_filters(qs, focus_filter_values, focus_state['mode'])
    if read_state=='new': qs=qs.filter(is_read=False)
    elif read_state=='seen': qs=qs.filter(is_read=True)
    if hide_non_200:
        # Hide only rows with a known failed domain check; unknown/not-applicable rows are not failures.
        qs=qs.filter(Q(domain_http_status__isnull=True)|Q(domain_http_status=200))
    pre_company_qs=qs
    company_filter_active=bool(company_size_filter or company_age_filter or contact_method_filter)
    qs=_apply_company_info_quick_filter(qs,company_size_filter,company_age_filter,contact_method_filter)
    contact_company_filter_counts={'shown':qs.count(),'available':pre_company_qs.count()}
    contact_re_evaluate_count=qs.count()
    if request.GET.get('export')=='1': return _xlsx('address_book.xlsx',['Name','Email','Phone','Company','Focus','Company location','Company summary','Title','Source','Confidence','State','Last seen'],[(c.name,c.email,c.phone,c.company,c.focus,c.company_country,c.company_summary,c.title,c.source_url or c.source,c.confidence,'Seen' if c.is_read else 'New',c.last_seen) for c in qs[:10000]])
    contacts=list(qs.order_by('-created_at','-pk')[:1000])
    # Address Book rows are intentionally not given a new FK. Recover the originating
    # role from data ScoutBox already stores: exact source URL first, then contact email,
    # then an unambiguous company match. Multiple company roles link to the filtered list.
    opportunity_rows=list(Opportunity.objects.filter(user_deleted=False,suppressed=False).only('pk','company','title','country','contact_email','url','search_url','target_url','canonical_url','company_intel').order_by('-last_seen')[:10000])
    lead_rows=list(CompanyLead.objects.filter(user_deleted=False).only('pk','company','country','contact_email','search_url','target_url','source_url','company_intel').order_by('-updated_at')[:10000])
    def url_key(value):
        value=str(value or '').strip().lower().rstrip('/')
        return value
    by_url={}; by_email={}; by_company={}; lead_by_url={}; lead_by_email={}; lead_by_company={}
    for opp in opportunity_rows:
        for value in (opp.target_url,opp.canonical_url,opp.url,opp.search_url):
            key=url_key(value)
            if key and key not in by_url: by_url[key]=opp
        email=(opp.contact_email or '').strip().lower()
        if email and email not in by_email: by_email[email]=opp
        company=(opp.company or '').strip().casefold()
        if company: by_company.setdefault(company,[]).append(opp)
    for lead in lead_rows:
        for value in (lead.target_url,lead.source_url,lead.search_url):
            key=url_key(value)
            if key and key not in lead_by_url: lead_by_url[key]=lead
        email=(lead.contact_email or '').strip().lower()
        if email and email not in lead_by_email: lead_by_email[email]=lead
        company=(lead.company or '').strip().casefold()
        if company: lead_by_company.setdefault(company,[]).append(lead)
    for contact in contacts:
        contact.origin_url=''; contact.origin_label=''; contact.display_country=_canonical_country_name(contact.company_country or '')
        inherited_changed=[]
        def inherit_company_context(intel,country=''):
            # A legacy Address Book row can already contain general company facts while
            # still lacking the age/size fields used by the Company Info badge. Prefer a
            # richer originating Opportunity/Hidden Lead in that case instead of keeping
            # the old Profile-only payload forever.
            richer_display=bool(intel and company_info_has_display_data(intel) and not company_info_has_display_data(contact))
            if intel and (not contact.company_intel or richer_display):
                contact.company_intel=intel; inherited_changed.append('company_intel')
            if country and not contact.display_country:
                contact.display_country=_canonical_country_name(country)
            summary=company_summary_from_intel(contact.company_intel or {},1200)
            if summary and not str(contact.company_summary or '').strip():
                contact.company_summary=summary; inherited_changed.append('company_summary')
        def persist_inherited_context():
            if inherited_changed:
                contact.save(update_fields=list(dict.fromkeys(inherited_changed)))
        source_key=url_key(contact.source_url); email_key=(contact.email or '').strip().lower(); company_key=(contact.company or '').strip().casefold()
        opp=by_url.get(source_key) or by_email.get(email_key)
        if opp:
            contact.origin_url=reverse('opportunity_detail',args=[opp.pk]); contact.origin_label=f'{opp.company} — {opp.title}'
            inherit_company_context(opp.company_intel or {},opp.country or '')
            persist_inherited_context()
            continue
        matches=by_company.get(company_key,[])
        if len(matches)==1:
            contact.origin_url=reverse('opportunity_detail',args=[matches[0].pk]); contact.origin_label=f'{matches[0].company} — {matches[0].title}'
            inherit_company_context(matches[0].company_intel or {},matches[0].country or '')
            persist_inherited_context()
            continue
        if len(matches)>1:
            contact.origin_url=reverse('opportunities')+'?'+urlencode({'q':contact.company}); contact.origin_label=f'{len(matches)} matching opportunities for {contact.company}'
            continue
        lead=lead_by_url.get(source_key) or lead_by_email.get(email_key)
        if lead:
            contact.origin_url=reverse('hidden_lead_detail',args=[lead.pk]); contact.origin_label=f'Hidden Lead — {lead.company}'
            inherit_company_context(lead.company_intel or {},lead.country or '')
            persist_inherited_context()
            continue
        lead_matches=lead_by_company.get(company_key,[])
        if len(lead_matches)==1:
            contact.origin_url=reverse('hidden_lead_detail',args=[lead_matches[0].pk]); contact.origin_label=f'Hidden Lead — {lead_matches[0].company}'
            inherit_company_context(lead_matches[0].company_intel or {},lead_matches[0].country or '')
        elif len(lead_matches)>1:
            contact.origin_url=reverse('cold_contact')+'?'+urlencode({'q':contact.company}); contact.origin_label=f'{len(lead_matches)} matching Hidden Leads for {contact.company}'
        # Persist inherited context so the Address Book does not depend on a transient
        # list-view assignment and future pages/API consumers see the same Company Info.
        try:
            inherit_company_context(contact.company_intel or {},'')
            persist_inherited_context()
        except Exception:
            pass
    active_contact_filter=BackgroundJob.objects.filter(kind='filter_contacts',status__in=['queued','running']).order_by('-created_at').first()
    active_manual_filter=_active_manual_filter()
    # 0.11.29: the re-evaluation history dialog is DB-complete after hiding no-result shells; do not cap or
    # pre-slice completed Address Book runs.
    contact_filter_history=_decorate_manual_filter_item_dates(_manual_filter_history_for_view('filter_contacts',active_contact_filter),'contact')
    completed_contact_filter_history=[x for x in contact_filter_history if str(x.status or '').lower() not in {'queued','running'}]
    latest_contact_filter=_latest_meaningful_manual_filter(completed_contact_filter_history)
    contact_filter_history_label=_manual_filter_history_label(contact_filter_history,'Address Book')
    manual_filter_ai=_manual_filter_ai_options()
    return render(request,'portal/contacts.html',ctx(request,'contacts','Address Book',contacts=contacts,q=q,show_generic=show_generic,country_filter=country_filter,country_options=country_options,country_total=country_total,country_filter_label=country_filter_label,country_filter_mode=country_state['mode'],focus_filter=focus_filter,focus_options=focus_options_rows,focus_total=focus_total,focus_filter_label=focus_filter_label,focus_filter_mode=focus_state['mode'],active_contact_filter=active_contact_filter,active_manual_filter=active_manual_filter,latest_contact_filter=latest_contact_filter,contact_filter_history=contact_filter_history,contact_filter_history_label=contact_filter_history_label,manual_filter_ai=manual_filter_ai,contact_re_evaluate_count=contact_re_evaluate_count,read_state=read_state,contact_read_filter_counts=contact_read_filter_counts,company_size_filter=company_size_filter,company_age_filter=company_age_filter,contact_method_filter=contact_method_filter,contact_method_filter_options=[('web','Web'),('email','Email'),('ats','ATS'),('forum','Forum'),('unknown','Unknown / Others')],company_filter_active=company_filter_active,company_filter_counts=contact_company_filter_counts,company_filter_reset_query=_company_filter_reset_query(request),company_size_filter_options=[('lt10','0-10'),('lt50','10-50'),('lt100','50-100'),('lt500','100-500'),('lt1000','500-1,000'),('gte1000','1,000+'),('unknown','Unknown / Others')],company_age_filter_options=[('lt1','0-1 year'),('lt2','1-2 years'),('lt5','2-5 years'),('lt10','5-10 years'),('gte10','10+ years'),('unknown','Unknown / Others')],hide_non_200=hide_non_200,show_deleted=show_deleted,map_edit_contact=Contact.objects.filter(pk=request.GET.get('edit'),deleted_at__isnull=True).first() if str(request.GET.get('edit') or '').isdigit() else None))


@login_required
@require_POST
def tracking_link_test_async(request):
    article_url=(request.POST.get('article_url') or '').strip()
    if not article_url:
        return JsonResponse({'ok':False,'error':'Enter an article path or URL.'},status=400)
    active=BackgroundJob.objects.filter(kind='diagnostic',label='Tracking link test',status__in=['queued','running'],result__article_url=article_url).order_by('-created_at').first()
    job=active or BackgroundJob.objects.create(kind='diagnostic',label='Tracking link test',message='Queued',result={'article_url':article_url})
    if not active:
        task=tracking_link_test_job.delay(job.pk,article_url); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
    request.session['tracking_link_test_job_id']=job.pk
    request.session.modified=True
    return JsonResponse({'ok':True,'job_id':job.pk,'resumed':bool(active)})


@login_required
@xframe_options_sameorigin
def link_rules_view(request):
    scan=None; preview=None; dialog_status=''; dialog_status_kind='notice'
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    status_key=(request.GET.get('status') or '').strip()
    if status_key=='base_saved':
        dialog_status='Tracking blog base saved.'
    if request.method=='POST':
        action=request.POST.get('action','test_url')
        if action=='save_base':
            value=request.POST.get('tracking_blog_base_url','').strip().rstrip('/')
            if not re.match(r'^https?://[^/]+/.+',value):
                dialog_status='Enter a complete blog base URL such as https://toughdev.com/blog.'; dialog_status_kind='notice danger'
            else:
                ps.tracking_blog_base_url=value; ps.save(update_fields=['tracking_blog_base_url','updated_at'])
                suffix='?embedded=1&status=base_saved' if request.GET.get('embedded')=='1' else '?status=base_saved'
                return redirect(reverse('link_rules')+suffix)
        elif action=='test_url':
            try:
                article_url=request.POST.get('article_url','').strip()
                preview=preview_for_url(article_url)
                link,info=allocate_for_url(article_url)
                preview['generated_link']=link.full_url
                preview['generated_base_url']=link.full_url[:-len(link.suffix)] if link.suffix and link.full_url.endswith(link.suffix) else link.full_url
                preview['generated_suffix']=link.suffix if link.suffix and link.full_url.endswith(link.suffix) else ''
                dialog_status='Tracking link generated.'
            except Exception as e:
                dialog_status=str(e); dialog_status_kind='notice danger'
        elif action=='scan':
            f=request.FILES.get('file')
            try:
                scan=scan_docx_links(f)
                dialog_status=f"Scanned {len(scan)} configured blog link{'s' if len(scan)!=1 else ''}."
            except Exception as e:
                dialog_status=str(e); dialog_status_kind='notice danger'
    tracking_job=None
    tracking_job_id=request.session.get('tracking_link_test_job_id')
    if tracking_job_id:
        tracking_job=BackgroundJob.objects.filter(pk=tracking_job_id,label='Tracking link test').first()
    if not tracking_job:
        tracking_job=BackgroundJob.objects.filter(label='Tracking link test',status__in=['queued','running']).order_by('-created_at').first()
    elif tracking_job.status not in {'queued','running'}:
        tracking_job=None
    return render(request,'portal/link_rules.html',ctx(
        request,'links','Add Tracking Link',system_tab='tracking',
        rules=TrackingLinkRule.objects.all().order_by('-created_at'),scan=scan,preview=preview,
        blog_base=blog_base_url(),tracking_test_job=tracking_job,
        tracking_dialog_status=dialog_status,tracking_dialog_status_kind=dialog_status_kind,
        embedded=request.GET.get('embedded')=='1'
    ))


@login_required
def links_view(request):
    if request.method=='POST':
        action=request.POST.get('action','')
        if action=='restore_row':
            row_id=str(request.POST.get('row_id') or '')
            ok,label=_restore_recycle_item('tracking_link',int(row_id)) if row_id.isdigit() else (False,'Tracking Link')
            if request.headers.get('X-Requested-With')=='fetch':
                return JsonResponse({'ok':ok,'label':label},status=200 if ok else 404)
            messages.success(request,f'Restored {label}.') if ok else messages.error(request,'Tracking link was not found in the Recycle Bin.')
            return redirect('links')
        if action=='generate':
            app=Application.objects.filter(pk=request.POST.get('application_id'),opportunity__user_deleted=False,deleted_at__isnull=True).first(); url=request.POST.get('article_url','').strip()
            try:
                link,info=allocate_for_url(url,app); messages.success(request,f'Generated tracking link for {info.get("title") or info.get("article_slug")}: {link.full_url}')
            except Exception as e: messages.error(request,str(e))
            return redirect('links')
        if action=='sync':
            try: result=sync_clicks(); messages.success(request,result['message'])
            except Exception as e: messages.error(request,str(e))
            return redirect('links')
        if action in ('delete_selected','delete_all'):
            ids=request.POST.getlist('link_ids') if action=='delete_selected' else list(TrackingLink.objects.filter(deleted_at__isnull=True).values_list('pk',flat=True))
            qs=TrackingLink.objects.filter(pk__in=[x for x in ids if x],deleted_at__isnull=True)
            count=qs.count(); qs.update(deleted_at=timezone.now()); messages.success(request,f'Moved {count} tracking link(s) to the Recycle Bin.')
            return redirect('links')
        if action=='restore_selected':
            ids=request.POST.getlist('link_ids')
            qs=TrackingLink.objects.filter(pk__in=[x for x in ids if x],deleted_at__isnull=False)
            count=qs.count(); qs.update(deleted_at=None); messages.success(request,f'Restored {count} tracking link(s).')
            return redirect('links')
    show_deleted=request.GET.get('show_deleted')=='1'
    # Old releases could persist a Markdown link instead of the document title. Queue a
    # bounded live metadata repair without blocking this list view on external HTTP.
    suspect_titles=any(article_title_needs_refresh(row.article_title,row.destination_url,row.name,row.base_path) for row in TrackingLinkRule.objects.filter(enabled=True).only('article_title','destination_url','name','base_path').order_by('-created_at')[:100])
    if suspect_titles and cache.add('tracking-article-title-refresh',True,timeout=300):
        try:
            tracking_article_title_tick.delay(8)
        except Exception:
            cache.delete('tracking-article-title-refresh')
    qs=TrackingLink.objects.select_related('rule','application__opportunity')
    if not show_deleted: qs=qs.filter(deleted_at__isnull=True)
    q=_q(request)
    if q: qs=qs.filter(Q(path__icontains=q)|Q(rule__article_title__icontains=q)|Q(rule__destination_url__icontains=q)|Q(application__opportunity__company__icontains=q)|Q(application__opportunity__title__icontains=q))
    if request.GET.get('export')=='1': return _xlsx('tracking_links.xlsx',['URL','Article','Destination','Company','Role','Clicks','Likely human','First click','Last click','Created'],[(x.full_url,('' if article_title_needs_refresh(x.rule.article_title,x.rule.destination_url,x.rule.name,x.rule.base_path) else clean_article_title(x.rule.article_title)) or x.rule.destination_url,x.rule.destination_url,x.application.opportunity.company if x.application else '',x.application.opportunity.title if x.application else '',x.click_count,x.likely_human_clicks,x.first_click,x.last_click,x.created_at) for x in qs[:10000]])
    rows=list(qs.order_by('-created_at')[:500])
    from urllib.parse import urlsplit
    for x in rows:
        compact=re.sub(r'^https?://(?:www\.)?','',str(x.full_url or ''),flags=re.I).rstrip('/')
        suffix=str(x.suffix or '')
        if suffix and compact.endswith(suffix):
            x.display_base_url=compact[:-len(suffix)]
            x.display_suffix=suffix
        else:
            x.display_base_url=compact
            x.display_suffix=''
    return render(request,'portal/links.html',ctx(request,'links','Tracking Links',links=rows,applications=Application.objects.filter(opportunity__user_deleted=False,deleted_at__isnull=True).select_related('opportunity')[:300],q=q,show_deleted=show_deleted,blogcfg=BlogStatsConfig.objects.get_or_create(pk=1)[0],blog_base=blog_base_url(),external_stats_status=external_stats_status()))


@login_required
@require_POST
def ai_test_async(request):
    test=(request.POST.get('test') or '').strip()
    if test in ('discovery','pipeline_models'):
        label='Profile-based Test Discovery' if test=='discovery' else 'Pipeline model validation'
        same=BackgroundJob.objects.filter(kind='diagnostic',label=label,status__in=['queued','running']).order_by('-created_at').first()
        if same and same.status=='queued' and same.created_at < timezone.now()-timedelta(minutes=10):
            same.status='failed'; same.error='Queued test expired before a worker started it.'; same.message='Stale queued test cleared'; same.finished_at=timezone.now(); same.save(update_fields=['status','error','message','finished_at']); same=None
        if same:
            return JsonResponse({'job_id':same.pk,'status':same.status,'existing':True})
        other_label='Pipeline model validation' if test=='discovery' else 'Profile-based Test Discovery'
        other=BackgroundJob.objects.filter(kind='diagnostic',label=other_label,status__in=['queued','running']).order_by('-created_at').first()
        if other:
            return JsonResponse({'error':f'{other_label} is already in progress. Wait for it to finish before starting another Discovery test.','job_id':other.pk},status=409)
    if test=='provider':
        provider=(request.POST.get('provider') or '').strip()
        if provider not in dict(AIProviderConfig.PROVIDERS):
            return JsonResponse({'error':'Unknown AI provider'},status=400)
        job=BackgroundJob.objects.create(kind='other',label=f'{provider.title()} provider test',message='Queued')
        task=ai_provider_test_job.delay(job.pk,provider,(request.POST.get('prompt') or '')[:2000])
    elif test=='discovery':
        keyword=(request.POST.get('keyword') or '').strip()
        if len(keyword)<3:
            return JsonResponse({'error':'Enter a test keyword of at least 3 characters.'},status=400)
        if len(keyword)>240:
            return JsonResponse({'error':'Test keyword must be 240 characters or fewer.'},status=400)
        ps=PortalSettings.objects.get_or_create(pk=1)[0]
        source_id=None
        source_name=''
        discovery_test_uses_cloud,cloud_provider,cloud_primary,cloud_secondary=_discovery_test_cloud_context(ps)
        cloud_route_lane=(request.POST.get('cloud_route_lane') or 'primary').strip().lower()
        if discovery_test_uses_cloud:
            if not cloud_provider or not cloud_primary:
                return JsonResponse({'error':'Cloud Web provider/Primary model is not configured.'},status=400)
            if cloud_route_lane not in {'primary','secondary'}:
                cloud_route_lane='primary'
            if cloud_route_lane=='secondary' and not cloud_secondary:
                return JsonResponse({'error':'No Secondary Cloud model is configured.'},status=400)
            source_name=f'{cloud_provider.title()} · '+(cloud_secondary if cloud_route_lane=='secondary' else cloud_primary)
        if not discovery_test_uses_cloud:
            requested=(request.POST.get('search_source_id') or '').strip()
            options=_discovery_test_provider_options()
            allowed={str(row['id']):row for row in options}
            if requested and requested not in allowed:
                return JsonResponse({'error':'The selected search engine is not configured and available for Test Discovery.'},status=400)
            selected=allowed.get(requested) if requested else next((row for row in options if row.get('default')),None)
            if not selected:
                return JsonResponse({'error':'No configured search engine is available for Test Discovery.'},status=400)
            source_id=selected['id']; source_name=selected['name']
        job=BackgroundJob.objects.create(kind='diagnostic',label='Profile-based Test Discovery',message=(f'Queued · {source_name} · {keyword}' if source_name else f'Queued · {keyword}')[:500],result={'test_keyword':keyword,'selected_source_id':source_id,'cloud_route_lane':cloud_route_lane if discovery_test_uses_cloud else ''})
        task=diagnostic_search_job.delay(job.pk,source_id,keyword,cloud_route_lane)
    elif test=='pipeline_models':
        routes_raw=(request.POST.get('routes_json') or '').strip()
        route_snapshot=None
        if routes_raw:
            try:
                parsed=json.loads(routes_raw)
                if not isinstance(parsed,dict): raise ValueError('routing snapshot must be an object')
                route_snapshot={}
                valid_stages={s for s in STAGES if s!='chatbot'}
                for stage,row in parsed.items():
                    if stage not in valid_stages or not isinstance(row,dict): continue
                    clean={}
                    for key in ('provider','model','fallback_provider','fallback_model'):
                        clean[key]=str(row.get(key) or '')[:300]
                    for key,default in (('max_input_tokens',STAGE_TOKEN_DEFAULTS.get(stage,STAGE_TOKEN_DEFAULTS['general'])['max_input_tokens']),('max_output_tokens',STAGE_TOKEN_DEFAULTS.get(stage,STAGE_TOKEN_DEFAULTS['general'])['max_output_tokens'])):
                        try: clean[key]=max(32,min(200000,int(row.get(key) or default)))
                        except Exception: clean[key]=default
                    route_snapshot[stage]=clean
            except Exception as exc:
                return JsonResponse({'error':f'Unable to read current routing selections: {exc}'},status=400)
        mode=(request.POST.get('discovery_mode') or '').strip()
        if mode not in dict(PortalSettings.DISCOVERY_MODES): mode=PortalSettings.objects.get_or_create(pk=1)[0].discovery_mode
        if mode=='cloud_web':
            # Cloud Web routing is persisted by the stage-routing form itself. Test the
            # exact saved configuration so validation cannot accidentally consume a
            # Local Discovery browser snapshot.
            if not has_usable_cloud_web_model():
                return JsonResponse({'error':'Save a usable Primary/Failover Cloud route for every stage before testing.'},status=400)
            job=BackgroundJob.objects.create(kind='diagnostic',label='Pipeline model validation',message='Cloud stage routes saved · queued')
            task=pipeline_model_test_job.delay(job.pk,None,mode)
        else:
            if route_snapshot is None:
                return JsonResponse({'error':'No routing selections were submitted for Test Selection.'},status=400)
            saved,save_message=_persist_pipeline_route_snapshot(route_snapshot,mode)
            if not saved:
                return JsonResponse({'error':save_message or 'Unable to save the current routing selections before testing.'},status=400)
            job=BackgroundJob.objects.create(kind='diagnostic',label='Pipeline model validation',message='Selections saved · queued')
            # Test the persisted configuration, not a transient browser-only snapshot.
            task=pipeline_model_test_job.delay(job.pk,None,mode)
    elif test in ('ollama','ollama_chat'):
        mode='chat' if test=='ollama_chat' else 'connection'
        model=(request.POST.get('model') or '').strip(); prompt=(request.POST.get('prompt') or '').strip()
        job=BackgroundJob.objects.create(kind='other',label='Ollama model test' if mode=='chat' else 'Ollama connection test',message='Queued')
        task=ollama_test_job.delay(job.pk,mode,model,prompt)
    else:
        return JsonResponse({'error':'Unknown AI test'},status=400)
    job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
    return JsonResponse({'job_id':job.pk,'status':'queued'})


def _local_model_rank(model):
    name=str((model or {}).get('model') or (model or {}).get('name') or '')
    details=(model or {}).get('details') or {}
    raw=str(details.get('parameter_size') or name)
    m=re.search(r'(\d+(?:\.\d+)?)\s*[bB](?:\b|$)',raw)
    return (float(m.group(1)) if m else 0.0, name.lower())



def _cloud_pipeline_preset_routes():
    """Build an explicit, capability-aware Cloud preset in configured priority order.

    Discovery/research stages prefer a provider/model that can use ScoutBox's native web
    research adapter. Later writing/application stages only require ordinary generation.
    A second compatible provider is used as an explicit fallback in the generated preview;
    nothing is saved until the user clicks Save.
    """
    configs=list(configured_cloud_configs())
    if not configs:
        return {}, 'No configured Cloud AI provider with both a saved API key and default model was found.'
    web_configs=[cfg for cfg in configs if web_capable_cloud_route(cfg.provider,configured_cloud_model(cfg))]
    web_stages={'url_scrape','jd_analysis','first_filter','company_enrichment','freshness','page_summarization'}
    routes={}
    for stage in [x for x in STAGES if x!='chatbot']:
        pool=web_configs if stage in web_stages and web_configs else configs
        primary=pool[0]
        fallback=next((cfg for cfg in pool[1:] if cfg.provider!=primary.provider),None)
        defaults=CLOUD_STAGE_TOKEN_DEFAULTS.get(stage,CLOUD_STAGE_TOKEN_DEFAULTS['general'])
        route={'provider':primary.provider,'model':configured_cloud_model(primary),'max_input_tokens':defaults['max_input_tokens'],'max_output_tokens':defaults['max_output_tokens']}
        if fallback:
            route.update({'fallback_provider':fallback.provider,'fallback_model':configured_cloud_model(fallback)})
        routes[stage]=route
    web_note=' Web-capable discovery/research routes use '+web_configs[0].get_provider_display()+' · '+configured_cloud_model(web_configs[0])+'.' if web_configs else ' No configured provider has confirmed web research capability; test provider capabilities before relying on cloud-native research.'
    return routes, 'Cloud selections prepared in configured provider-priority order.'+web_note


def _local_gpu_preset_warning():
    """Return a UI warning when a usable local GPU is not currently confirmed."""
    try:
        readiness=ai_compute_readiness()
        local=next((x for x in (readiness.get('states') or []) if str(x.get('provider') or '').lower()=='ollama'),{})
        accel=local.get('accelerator') or {}
        probe=local.get('auto_probe') or {}
        gpu_confirmed=bool(accel.get('detected') or local.get('running_vram') or local.get('validated_accelerator') or probe.get('ok') is True)
        if gpu_confirmed:
            return ''
        if local.get('identifying'):
            return 'Local GPU detection is still in progress. Verify GPU detection before relying on the Local AI Discovery Auto-detect selections.'
        return 'Warning: no usable local GPU is currently detected. Local AI may be slow or unavailable until a GPU is detected.'
    except Exception:
        return 'Warning: ScoutBox could not confirm a local GPU. Verify local GPU availability before relying on the Local AI Discovery Auto-detect selections.'


def _optimized_local_routes(existing=None):
    """Build hardware-aware explicit Ollama routes for Local Discovery Auto-detect.

    Auto-detect uses one consistent Primary/Secondary pair for every Discovery stage. At a
    32 GB-class automatic ceiling this prefers a 7B Primary and a 4B Secondary when those
    sizes are installed. Smaller hardware tiers choose proportionally smaller models. These
    are defaults only; manual model selections remain unrestricted.
    """
    existing=existing or {}
    try:
        installed=list((ollama_service.diagnostics() or {}).get('installed') or [])
    except Exception:
        installed=[]
    configured=''
    try:
        cfg=AIProviderConfig.objects.filter(provider='ollama',enabled=True).first()
        configured=str(cfg.default_model or '').strip() if cfg else ''
    except Exception:
        configured=''

    rows=[]; seen=set()
    for item in installed:
        name=str((item or {}).get('model') or (item or {}).get('name') or '').strip()
        low=name.lower()
        if not name or name in seen or any(x in low for x in ('embed','embedding','rerank')):
            continue
        seen.add(name)
        size=_ollama_parameter_billions(item)
        if not size:
            size=_local_model_rank(item)[0]
        if size:
            rows.append((float(size),name))
    if not rows:
        return {},'No locally installed Ollama generation models were detected.',''

    auto_cap=automatic_ollama_model_cap_billions()
    usable=[x for x in rows if 0 < x[0] <= auto_cap]
    if not usable:
        return {},f'No installed Ollama generation model fits the {auto_cap:g}B automatic hardware limit. Select a model manually if you want to exceed it.',''

    # Prefer the largest model that fits the detected ceiling. With the normal 32 GB cap
    # this naturally resolves to a 7B-class model when one is installed.
    primary=max(usable,key=lambda x:(x[0],1 if x[1]==configured else 0,x[1].lower()))
    smaller=[x for x in usable if x[1]!=primary[1] and x[0]<primary[0]]
    if not smaller:
        return {},f'Auto-detect found {primary[1]} for Primary but no smaller installed generation model for Secondary. Install another model or configure the stages manually.',''
    secondary_target=4.0 if auto_cap>=7.0 and primary[0]>=6.0 else max(0.1,primary[0]*0.62)
    secondary=min(smaller,key=lambda x:(abs(x[0]-secondary_target),-x[0],0 if x[1]==configured else 1,x[1].lower()))

    routes={'chatbot':(existing.get('chatbot') or {}).copy()}
    for stage in [x for x in STAGES if x!='chatbot']:
        defaults=STAGE_TOKEN_DEFAULTS.get(stage,STAGE_TOKEN_DEFAULTS['general'])
        routes[stage]={
            'provider':'ollama','model':primary[1],
            'fallback_provider':'ollama','fallback_model':secondary[1],
            'max_input_tokens':defaults['max_input_tokens'],'max_output_tokens':defaults['max_output_tokens'],
        }
    warning=''
    if primary[0] < 4.0:
        warning=f'Warning: the detected hardware/model inventory only supports a {primary[0]:g}B-class Primary under the automatic limit. Manual selection can exceed this limit.'
    message=f'Auto-detected Local Discovery routes for all stages: Primary {primary[1]} ({primary[0]:g}B); Secondary {secondary[1]} ({secondary[0]:g}B); automatic hardware limit {auto_cap:g}B.'
    return routes,message,warning


def _apply_pipeline_mode(mode):
    holder=AIProviderConfig.objects.filter(provider='ollama').first() or AIProviderConfig.objects.first()
    if not holder:
        holder=AIProviderConfig.objects.create(provider='ollama',enabled=True)
    existing=(holder.stage_routes or {}).copy()
    if mode=='automatic':
        routes={'chatbot':(existing.get('chatbot') or {}).copy()}
        for stage in [x for x in STAGES if x!='chatbot']:
            defaults=STAGE_TOKEN_DEFAULTS.get(stage,STAGE_TOKEN_DEFAULTS['general'])
            routes[stage]={'max_input_tokens':defaults['max_input_tokens'],'max_output_tokens':defaults['max_output_tokens']}
        holder.stage_routes=routes; holder.save(update_fields=['stage_routes'])
        return True,'Automatic local routing applied.'
    if mode=='local':
        routes,message,model_warning=_optimized_local_routes(existing)
        if not routes:
            return False,message
        holder.stage_routes=routes; holder.save(update_fields=['stage_routes'])
        warnings=[x for x in (_local_gpu_preset_warning(),model_warning) if x]
        if warnings: message+=' '+' '.join(warnings)
        return True,message
    if mode=='cloud':
        cloud_routes,message=_cloud_pipeline_preset_routes()
        if not cloud_routes:
            return False,message+' Existing routing was not changed.'
        routes={'chatbot':(existing.get('chatbot') or {}).copy()}; routes.update(cloud_routes)
        holder.stage_routes=routes; holder.save(update_fields=['stage_routes'])
        return True,message
    return False,'Unknown pipeline optimization mode.'


def _pipeline_mode_preview(mode):
    """Return a routing preset for the UI without writing it to the database."""
    holder=AIProviderConfig.objects.filter(provider='ollama').first() or AIProviderConfig.objects.first()
    existing=(holder.stage_routes or {}).copy() if holder else {}
    if mode=='automatic':
        routes={'chatbot':(existing.get('chatbot') or {}).copy()}
        for stage in [x for x in STAGES if x!='chatbot']:
            defaults=STAGE_TOKEN_DEFAULTS.get(stage,STAGE_TOKEN_DEFAULTS['general'])
            routes[stage]={'max_input_tokens':defaults['max_input_tokens'],'max_output_tokens':defaults['max_output_tokens']}
        return {'ok':True,'message':'Automatic local selections prepared.','routes':routes}
    if mode=='local':
        routes,message,model_warning=_optimized_local_routes(existing)
        if not routes:
            return {'ok':False,'message':message,'routes':{}}
        warnings=[x for x in (_local_gpu_preset_warning(),model_warning) if x]
        return {'ok':True,'message':message,'warning':' '.join(warnings),'routes':routes}
    if mode=='cloud':
        cloud_routes,message=_cloud_pipeline_preset_routes()
        if not cloud_routes:
            return {'ok':False,'message':message,'routes':{}}
        return {'ok':True,'message':message+' Click Save to keep these explicit selections.','routes':cloud_routes}
    return {'ok':False,'message':'Unknown pipeline optimization mode.','routes':{}}


def _pipeline_model_last_test(ps):
    job=BackgroundJob.objects.filter(kind='diagnostic',label='Pipeline model validation').exclude(status__in=['queued','running']).order_by('-created_at').first()
    if not job:
        return None,False
    result=job.result or {}
    current=job.status=='completed' and result.get('test_schema')==3 and result.get('route_signature')==pipeline_route_signature(ps.discovery_mode)
    return job,current


def _pipeline_model_active_job():
    return BackgroundJob.objects.filter(kind='diagnostic',label='Pipeline model validation',status__in=['queued','running']).order_by('-created_at').first()


def _discovery_test_active_job():
    return BackgroundJob.objects.filter(kind='diagnostic',label='Profile-based Test Discovery',status__in=['queued','running']).order_by('-created_at').first()


def _persist_pipeline_route_snapshot(route_snapshot, discovery_mode):
    """Persist Local AI Discovery local routing before Test Selection runs."""
    if discovery_mode!='source_guided':
        return False,'Cloud Web routing is automatic; Test Selection is available only for Local AI Discovery local routing.'
    holder=AIProviderConfig.objects.filter(provider='ollama').first() or AIProviderConfig.objects.first()
    if not holder:
        return False,'No AI provider configuration exists to store pipeline routing.'
    existing=dict(holder.stage_routes or {})
    routes={'chatbot':dict(existing.get('chatbot') or {})}
    for stage in (s for s in STAGES if s!='chatbot'):
        raw=dict((route_snapshot or {}).get(stage) or {})
        defaults=STAGE_TOKEN_DEFAULTS.get(stage,STAGE_TOKEN_DEFAULTS['general'])
        route={
            'max_input_tokens':max(64,min(200000,int(raw.get('max_input_tokens') or defaults['max_input_tokens']))),
            'max_output_tokens':max(32,min(50000,int(raw.get('max_output_tokens') or defaults['max_output_tokens']))),
        }
        provider=str(raw.get('provider') or '').strip().lower()
        fallback=str(raw.get('fallback_provider') or '').strip().lower()
        if provider and provider!='ollama':
            return False,f'{stage}: Local AI Discovery primary routing only accepts Ollama models.'
        if fallback and fallback!='ollama':
            return False,f'{stage}: Local AI Discovery fallback routing only accepts Ollama models.'
        if provider=='ollama': route.update({'provider':'ollama','model':str(raw.get('model') or '')[:300]})
        if fallback=='ollama': route.update({'fallback_provider':'ollama','fallback_model':str(raw.get('fallback_model') or '')[:300]})
        routes[stage]=route
    holder.stage_routes=routes
    holder.save(update_fields=['stage_routes'])
    return True,'Current local Local AI Discovery routing selections saved.'


def _discovery_test_provider_options():
    """Configured Local AI Discovery providers, ranked toward the most recent real results.

    Statistics shown in the selector cover the latest seven calendar days.  The default
    provider is the configured engine with the most recent day that produced results;
    if none has ever produced results, healthy/preferred configuration order is used.
    """
    today=timezone.localdate(); since=today-timedelta(days=6)
    rows=[]
    for source in SearchSource.objects.filter(enabled=True,name__in=ACTIVE_PROVIDER_NAMES).order_by('-priority','name'):
        health=_search_provider_health(source)
        # _search_provider_health uses error specifically for disabled/unconfigured.
        if health.get('health_state')=='error':
            continue
        stats=SearchProviderStat.objects.filter(source=source,day__gte=since)
        agg=stats.aggregate(requests=Sum('requests'),results=Sum('results'),errors=Sum('errors'))
        requests=int(agg.get('requests') or 0); results=int(agg.get('results') or 0); errors=int(agg.get('errors') or 0)
        latest_result=SearchProviderStat.objects.filter(source=source,day__gte=since,results__gt=0).order_by('-day').values_list('day',flat=True).first()
        error_rate=(errors/requests) if requests else 0.0
        if results>0 and error_rate<.35:
            state='ok'; icon='✓'; title=f'Healthy recent results · {errors} error(s) in {requests} request(s)'
        elif errors>0:
            state='warning'; icon='!'; title=f'Recent provider errors · {errors} error(s) in {requests} request(s)'
        else:
            state='no_results'; icon='∅'; title='No results recorded in the last 7 days'
        rows.append({
            'id':source.pk,'name':source.name,'icon':icon,'health_state':state,'health_title':title,
            'recent_requests':requests,'recent_results':results,'recent_errors':errors,
            'latest_result_day':latest_result,'preferred':bool(source.preferred_initial),
        })
    rows.sort(key=lambda row:(
        0 if row.get('latest_result_day') else 1,
        -(row['latest_result_day'].toordinal() if row.get('latest_result_day') else 0),
        -int(row.get('recent_results') or 0),
        0 if row.get('health_state')=='ok' else (1 if row.get('health_state')=='warning' else 2),
        0 if row.get('preferred') else 1,
        row.get('name') or '',
    ))
    if rows:
        rows[0]['default']=True
    return rows


def _pipeline_model_status(ps):
    status={stage:{'state':'unknown','title':'Not tested','result':None,'primary_state':'unknown','primary_title':'Not tested','fallback_state':'unknown','fallback_title':'Not tested'} for stage in STAGES if stage!='chatbot'}
    active=_pipeline_model_active_job()
    job=active or BackgroundJob.objects.filter(kind='diagnostic',label='Pipeline model validation',status='completed').order_by('-created_at').first()
    if not job:
        return status
    result=job.result or {}
    if result.get('test_schema') != 3 or result.get('route_signature') != pipeline_route_signature(ps.discovery_mode):
        return status
    for row in result.get('stages') or []:
        stage=row.get('stage')
        if stage not in status: continue
        complete=bool(row.get('complete'))
        ok=complete and row.get('status')=='ok'
        provider=row.get('provider') or ''; model=row.get('model') or ''
        detail=row.get('detail') or ('Compatible' if ok else ('Testing…' if not complete else 'Needs attention'))
        status[stage]={
            'state':'ok' if ok else ('warning' if complete else 'testing'),
            'title':' · '.join(x for x in [provider,model,detail] if x),
            'result':row,
            'primary_state':row.get('primary_state') or ('unknown' if complete else 'testing'),
            'primary_title':row.get('primary_title') or ('Not tested' if complete else 'Testing…'),
            'fallback_state':row.get('fallback_state') or ('unknown' if complete else 'testing'),
            'fallback_title':row.get('fallback_title') or ('Not tested' if complete else 'Testing…'),
        }
    return status


def _discovery_test_cloud_context(ps=None):
    """Explicit Cloud Web provider and Primary/Secondary models for Test Discovery."""
    ps=ps or PortalSettings.objects.get_or_create(pk=1)[0]
    if ps.discovery_mode!='cloud_web':
        return False,'','',''
    sel=cloud_web_selection('url_scrape')
    return True,str(sel.get('provider') or ''),str(sel.get('primary_model') or ''),str(sel.get('secondary_model') or '')


@login_required
@require_POST
def ai_provider_validate(request):
    provider=(request.POST.get('provider') or '').strip().lower()
    try:
        cfg,override,meta=_provider_request_settings(request,provider)
        models=_provider_model_catalog(provider,override['base_url'],override.get('api_key',''))
        if not models:
            return JsonResponse({'ok':False,'error':'Validation succeeded, but no usable models were returned.','models':[]},status=422)
        return JsonResponse({
            'ok':True,'provider':provider,'models':models,
            'message':f'Validated · {len(models)} model{"s" if len(models)!=1 else ""} available',
            'saved_model':cfg.default_model or '','credential_source':meta.get('key_source',''),
        })
    except requests.HTTPError as exc:
        response=getattr(exc,'response',None)
        detail=''
        try:
            payload=response.json() if response is not None else {}
            detail=str(payload.get('error',{}).get('message') if isinstance(payload.get('error'),dict) else payload.get('error') or payload.get('message') or '')
        except Exception:
            detail=''
        status=response.status_code if response is not None and 400 <= response.status_code < 600 else 400
        return JsonResponse({'ok':False,'error':detail or f'Provider validation failed ({status}).'},status=status)
    except Exception as exc:
        return JsonResponse({'ok':False,'error':str(exc)},status=400)


@login_required
@require_POST
def ai_provider_test_live(request):
    provider=(request.POST.get('provider') or '').strip().lower()
    requested_model=(request.POST.get('model') or '').strip()
    selection_probe=(request.POST.get('selection_probe') or '').strip()=='1'
    if provider not in AI_PROVIDER_UI_ORDER:
        return JsonResponse({'ok':False,'error':'Unknown AI provider.'},status=400)
    cfg=None; override={}; meta={}; model=requested_model; selection='explicit'; models=[]; phase='configuration'; probe_id=''
    try:
        cfg,override,meta=_provider_request_settings(request,provider)
        phase='model catalogue'
        models=_provider_model_catalog(provider,override['base_url'],override.get('api_key',''))
        if not models:
            raise RuntimeError('The provider connection succeeded but returned no usable generation models.')
        model_ids={str(item.get('id') or '').strip() for item in models}
        if not model:
            model,selection=_provider_auto_test_model(provider,models,cfg.default_model or '')
            if not model:
                raise RuntimeError('Automatic model selection could not find a usable model from the provider catalogue.')
        elif model not in model_ids:
            raise RuntimeError(f'The selected model "{model}" was not returned by the provider model catalogue. Choose Automatic or a listed model and test again.')

        phase='generation request'
        probe_id='provider-ui-'+uuid.uuid4().hex
        test_override=dict(override)
        if provider=='gemini': test_override['_configuration_test_low_thinking']=True
        generated,debug=generate_with(
            provider,model,('Return JSON only: {\"ok\":true,\"echo\":\"ScoutBox\"}' if selection_probe else AI_PROVIDER_TEST_PROMPT),stage='provider_test',timeout=45,
            subject={'type':'task','id':probe_id,'label':f'{cfg.get_provider_display()} provider test','budget_operation':'provider_test'},
            limits_override={'max_input_tokens':512,'max_output_tokens':256},config_override=test_override,return_debug=True,
        )
        text=str(generated or '').strip(); raw_response=(debug or {}).get('raw') or {}
        json_ok=_json_probe_ok(text) if selection_probe else True
        request_log=AIRequestLog.objects.filter(subject_id=probe_id,provider=provider).order_by('-at').first()
        tokens_in=int(request_log.tokens_in if request_log else 0)
        tokens_out=int(request_log.tokens_out if request_log else 0)
        usage=(raw_response.get('usageMetadata') or {}) if provider=='gemini' and isinstance(raw_response,dict) else {}
        thinking_tokens=int(usage.get('thoughtsTokenCount') or 0)
        total_tokens=int(usage.get('totalTokenCount') or (tokens_in+tokens_out+thinking_tokens))
        finish_reasons=(debug or {}).get('finish_reasons') or []
        finish_reason=', '.join(finish_reasons) if finish_reasons else ''
        http_status=int((debug or {}).get('http_status') or 200)
        thinking_mode=str((debug or {}).get('thinking_mode') or '')
        caps=dict(cfg.capabilities or {})
        caps.update({'model':model,'generation':bool(text),'model_catalog':[str(x.get('id') or '') for x in models[:250] if str(x.get('id') or '')]})
        if not text:
            raw_text=json.dumps(raw_response,ensure_ascii=False,default=str)[:2400] if raw_response else ''
            detail='The provider returned a successful HTTP response but no text content.'
            if provider=='gemini' and isinstance(raw_response,dict):
                feedback=raw_response.get('promptFeedback') or {}
                candidates=raw_response.get('candidates') or []
                finish=[]
                for candidate in candidates[:3]:
                    if isinstance(candidate,dict) and candidate.get('finishReason'): finish.append(str(candidate.get('finishReason')))
                pieces=[]
                if feedback: pieces.append('promptFeedback='+json.dumps(feedback,ensure_ascii=False,default=str)[:600])
                if finish: pieces.append('finishReason='+', '.join(finish))
                if pieces: detail+=' '+ ' · '.join(pieces)
            cfg.last_test_ok=False; cfg.last_test_at=timezone.now(); cfg.last_test_message=detail[:1000]; cfg.capabilities=caps
            cfg.save(update_fields=['last_test_ok','last_test_at','last_test_message','capabilities'])
            diagnostics={'provider':provider,'model':model,'model_selection':selection,'base_url':override.get('base_url',''),'credential_source':meta.get('key_source',''),'saved_key_present':bool(meta.get('has_saved_key')),'configured_default':cfg.default_model or '','model_count':len(models),'phase':phase,'http_status':http_status,'provider_detail':detail,'server_response':raw_text,'tokens_in':tokens_in,'tokens_out':tokens_out,'thinking_tokens':thinking_tokens,'total_tokens':total_tokens,'finish_reason':finish_reason,'thinking_mode':thinking_mode,'hint':'The connection and model catalogue worked. Inspect the finish reason and token usage; choose another listed model only if the provider still returns no visible content.'}
            return JsonResponse({'ok':False,'provider':provider,'model':model,'requested_model':requested_model or 'Automatic','model_selection':selection,'error':detail,'models':models,'model_count':len(models),'tokens_in':tokens_in,'tokens_out':tokens_out,'thinking_tokens':thinking_tokens,'total_tokens':total_tokens,'finish_reason':finish_reason,'http_status':http_status,'diagnostics':diagnostics},status=422)
        web_state='Not applicable'; web_ok=None; web_error=''
        if provider in ('openai','gemini','openrouter'):
            try:
                web_text,_meta=web_search_with(
                    provider,model,
                    'Capability test: find the official Python programming language website and reply with its name and URL.',
                    stage='provider_test',timeout=45,limits_override={'max_input_tokens':700,'max_output_tokens':160},
                    budget_operation='provider_test',config_override=override,
                )
                web_ok=bool(str(web_text or '').strip())
                caps['web_search']=web_ok; caps.pop('web_search_error',None)
                web_state='Available' if web_ok else 'No content returned'
            except CloudLimitReached as exc:
                caps.pop('web_search',None); caps.pop('web_search_error',None)
                web_state=f'Not tested — {exc}'
            except Exception as exc:
                web_ok=False; web_error=str(exc)[:700]
                caps['web_search']=False; caps['web_search_error']=web_error[:500]
                web_state='Unavailable'
        ok=bool(text) and (not selection_probe or (json_ok and web_ok is True))
        cfg.last_test_ok=ok; cfg.last_test_at=timezone.now()
        cfg.last_test_message=(f'Test passed with {model}' if ok else f'Test failed with {model}') + (f' · Web research {web_state.lower()}' if provider!='ollama' else '')
        cfg.capabilities=caps
        cfg.save(update_fields=['last_test_ok','last_test_at','last_test_message','capabilities'])
        return JsonResponse({
            'ok':ok,'provider':provider,'model':model,'requested_model':requested_model or 'Automatic','model_selection':selection,
            'response':text or 'No response returned.','tokens_in':tokens_in,'tokens_out':tokens_out,'thinking_tokens':thinking_tokens,'total_tokens':total_tokens,'finish_reason':finish_reason,'http_status':http_status,'web_research':web_state,
            'web_error':web_error,'json_ok':json_ok,'message':cfg.last_test_message,'models':models,'model_count':len(models),
            'diagnostics':{'provider':provider,'model':model,'model_selection':selection,'base_url':override.get('base_url',''),'credential_source':meta.get('key_source',''),'saved_key_present':bool(meta.get('has_saved_key')),'configured_default':cfg.default_model or '','model_count':len(models),'phase':phase,'http_status':http_status,'thinking_tokens':thinking_tokens,'total_tokens':total_tokens,'finish_reason':finish_reason,'thinking_mode':thinking_mode},
        },status=200 if ok else 422)
    except CloudLimitReached as exc:
        request_log=AIRequestLog.objects.filter(subject_id=probe_id,provider=provider).order_by('-at').first() if probe_id else None
        tokens_in=int(request_log.tokens_in if request_log else 0); tokens_out=int(request_log.tokens_out if request_log else 0)
        details=_provider_failure_details(exc,provider,model,override,cfg,meta,selection,tokens_in=tokens_in,tokens_out=tokens_out,model_count=len(models)) if cfg else {'provider':provider,'model':model,'error_type':exc.__class__.__name__,'hint':'Check ScoutBox Cloud AI limits.','tokens_in':tokens_in,'tokens_out':tokens_out,'model_count':len(models)}
        details['phase']=phase
        return JsonResponse({'ok':False,'error':str(exc),'state':'limit_reached','model':model,'requested_model':requested_model or 'Automatic','models':models,'model_count':len(models),'tokens_in':tokens_in,'tokens_out':tokens_out,'diagnostics':details},status=429)
    except Exception as exc:
        request_log=AIRequestLog.objects.filter(subject_id=probe_id,provider=provider).order_by('-at').first() if probe_id else None
        tokens_in=int(request_log.tokens_in if request_log else 0); tokens_out=int(request_log.tokens_out if request_log else 0)
        if cfg:
            caps=dict(cfg.capabilities or {})
            if models: caps['model_catalog']=[str(x.get('id') or '') for x in models[:250] if str(x.get('id') or '')]
            if phase=='generation request': caps.update({'model':model,'generation':False})
            cfg.last_test_ok=False; cfg.last_test_at=timezone.now(); cfg.last_test_message=str(exc)[:1000]; cfg.capabilities=caps
            cfg.save(update_fields=['last_test_ok','last_test_at','last_test_message','capabilities'])
            details=_provider_failure_details(exc,provider,model,override,cfg,meta,selection,tokens_in=tokens_in,tokens_out=tokens_out,model_count=len(models))
        else:
            details={'provider':provider,'model':model,'error_type':exc.__class__.__name__,'hint':'Check the provider configuration and retry.','tokens_in':tokens_in,'tokens_out':tokens_out,'model_count':len(models)}
        details['phase']=phase
        return JsonResponse({'ok':False,'error':str(exc),'model':model,'requested_model':requested_model or 'Automatic','models':models,'model_count':len(models),'tokens_in':tokens_in,'tokens_out':tokens_out,'diagnostics':details},status=400)


@login_required
@require_POST
def ai_provider_save(request):
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    saved=[]; key_saved={}
    try:
        for provider in AI_PROVIDER_UI_ORDER:
            base_default,enabled_default=AI_PROVIDER_DEFAULTS[provider]
            cfg=AIProviderConfig.objects.filter(provider=provider).first() or AIProviderConfig.objects.create(provider=provider,base_url=base_default,enabled=enabled_default)
            cfg.enabled=(request.POST.get(f'enabled_{provider}')=='1')
            cfg.base_url=(request.POST.get(f'base_url_{provider}') or cfg.base_url or base_default).strip()
            cfg.default_model=(request.POST.get(f'default_model_{provider}') or '').strip()
            submitted_key=(request.POST.get(f'api_key_{provider}') or '').strip()
            if provider!='ollama' and submitted_key:
                cfg.api_key_enc=encrypt(submitted_key)
            if provider in ('openai','gemini','openrouter'):
                raw=(request.POST.get(f'max_output_tokens_{provider}') or '').strip()
                try: cfg.max_output_tokens=max(64,min(8192,int(raw))) if raw else 8000
                except Exception: cfg.max_output_tokens=8000
            else:
                cfg.max_output_tokens=None
            cfg.save()
            saved.append(provider)
            key_saved[provider]=bool(cfg.api_key_enc) if provider!='ollama' else True
        warning=''
        if not has_usable_cloud_web_model() and ps.discovery_mode=='cloud_web':
            warning='Cloud Web remains selected, but campaigns will stop until an enabled Cloud provider has credentials and a resolved model.'
        return JsonResponse({
            'ok':True,'saved':saved,'key_saved':key_saved,'cloud_available':has_usable_cloud_web_model(),
            'discovery_mode':ps.discovery_mode,'message':'Provider configuration saved.','warning':warning,
        })
    except Exception as exc:
        return JsonResponse({'ok':False,'error':str(exc)},status=400)


def _ai_timeout_settings_context(ps):
    return {
        'local': {
            'value': int(ps.local_ai_request_timeout_seconds or AI_REQUEST_TIMEOUT_DEFAULTS['local_ai']),
            'default': AI_REQUEST_TIMEOUT_DEFAULTS['local_ai'],
            'min': AI_REQUEST_TIMEOUT_LIMITS['local_ai'][0], 'max': AI_REQUEST_TIMEOUT_LIMITS['local_ai'][1],
        },
        'cloud': {
            'value': int(ps.cloud_ai_request_timeout_seconds or AI_REQUEST_TIMEOUT_DEFAULTS['cloud_ai']),
            'default': AI_REQUEST_TIMEOUT_DEFAULTS['cloud_ai'],
            'min': AI_REQUEST_TIMEOUT_LIMITS['cloud_ai'][0], 'max': AI_REQUEST_TIMEOUT_LIMITS['cloud_ai'][1],
        },
        'chatbot': {
            'value': int(ps.chatbot_provider_timeout_seconds or AI_REQUEST_TIMEOUT_DEFAULTS['chatbot']),
            'default': AI_REQUEST_TIMEOUT_DEFAULTS['chatbot'],
            'min': AI_REQUEST_TIMEOUT_LIMITS['chatbot'][0], 'max': AI_REQUEST_TIMEOUT_LIMITS['chatbot'][1],
        },
    }


def _discovery_test_default_keyword():
    """Test Discovery is a role focus, never a role+skills pseudo-query."""
    try:
        profile=build_search_profile()
        roles=[str(x.get('role') or '').strip() for x in (profile.get('role_families') or []) if str(x.get('role') or '').strip()]
        if roles:
            return roles[0][:220]
    except Exception:
        pass
    return 'Embedded Software Engineer'


@login_required
def ai_view(request):
    result=None
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    provider_defaults=AI_PROVIDER_DEFAULTS
    for provider,(base_url,enabled) in provider_defaults.items():
        AIProviderConfig.objects.get_or_create(provider=provider,defaults={'base_url':base_url,'enabled':enabled})
    cloud_available=has_usable_cloud_web_model()
    cloud_selection=cloud_web_selection('url_scrape')
    cloud_stage_routes=cloud_web_stage_routes()
    try: cloud_web_effective=cloud_discovery_route(stage='url_scrape') if cloud_available else {}
    except Exception: cloud_web_effective={}
    discovery_test_uses_cloud,discovery_test_cloud_provider,discovery_test_cloud_primary,discovery_test_cloud_secondary=_discovery_test_cloud_context(ps)
    if (request.GET.get('export') or '').strip().lower()=='diagnostic':
        rows=BackgroundJob.objects.filter(kind='diagnostic').order_by('-created_at')
        return _xlsx('ai_test_discovery_runs.xlsx',['Created','Run','Status','Progress','Message','Error'],[(x.created_at,x.label,x.get_status_display(),x.progress,x.message,x.error) for x in rows[:10000]])
    if request.method=='POST':
        action=request.POST.get('action')
        if action=='save_discovery_mode':
            mode=request.POST.get('discovery_mode','source_guided')
            if mode not in dict(PortalSettings.DISCOVERY_MODES): mode='source_guided'
            previous_mode=ps.discovery_mode
            ps.discovery_mode=mode; ps.save(update_fields=['discovery_mode','updated_at'])
            if previous_mode != mode:
                log('discovery_method_changed', request, summary=f'{previous_mode} → {mode}', metadata={
                    'old': previous_mode, 'new': mode, 'endpoint': 'ai.save_discovery_mode',
                })
            if mode=='cloud_web':
                try:
                    if not has_usable_cloud_web_model():
                        raise RuntimeError('One or more Cloud Web stages is not configured.')
                    cloud=cloud_discovery_route(stage='url_scrape')
                    label=dict(AIProviderConfig.PROVIDERS).get(cloud.get('provider'),cloud.get('provider') or 'Cloud AI')
                    messages.success(request,f"Cloud Web active · {label} · {cloud.get('model','')}")
                except Exception as exc:
                    messages.warning(request,f'Cloud Web remains selected but is unavailable — no usable Cloud provider/model. Configure Providers before running a campaign. {exc}')
            else:
                messages.success(request,'Discovery Method changed to Local AI Discovery. Local stage routing is active.')
        elif action=='save_provider':
            provider=request.POST.get('provider'); cfg=get_object_or_404(AIProviderConfig,provider=provider); cfg.enabled=bool(request.POST.get('enabled')); cfg.base_url=request.POST.get('base_url','').strip(); cfg.default_model=request.POST.get('default_model','').strip()
            if request.POST.get('api_key'): cfg.api_key_enc=encrypt(request.POST.get('api_key'))
            if provider in ('openai','gemini','openrouter'):
                raw=(request.POST.get('max_output_tokens') or '').strip()
                try: cfg.max_output_tokens=max(64,min(8192,int(raw))) if raw else 8000
                except Exception: cfg.max_output_tokens=8000
            else:
                cfg.max_output_tokens=None
            # Stage routing is shared and edited in the routing table; saving one provider
            # must not overwrite it with a stale hidden-field snapshot.
            cfg.save()
            if not has_usable_cloud_web_model() and ps.discovery_mode=='cloud_web':
                messages.warning(request,'Cloud Web remains selected but is unavailable until a usable Cloud provider/model is configured.')
            messages.success(request,f'{cfg.get_provider_display()} configuration saved.')
        elif action=='save_cloud_selection':
            enabled={c.provider:c for c in AIProviderConfig.objects.filter(provider__in=['openai','gemini','openrouter'],enabled=True)}
            routes={}
            error=''
            for stage in [s for s in STAGES if s!='chatbot']:
                provider=(request.POST.get(f'cloud_provider_{stage}') or '').strip().lower()
                primary=(request.POST.get(f'cloud_primary_{stage}') or '').strip()
                secondary=(request.POST.get(f'cloud_secondary_{stage}') or '').strip()
                defaults=CLOUD_STAGE_TOKEN_DEFAULTS.get(stage,CLOUD_STAGE_TOKEN_DEFAULTS['general'])
                try: max_in=max(64,min(200000,int(request.POST.get(f'cloud_max_input_{stage}') or defaults['max_input_tokens'])))
                except Exception: max_in=defaults['max_input_tokens']
                try: max_out=max(32,min(50000,int(request.POST.get(f'cloud_max_output_{stage}') or defaults['max_output_tokens'])))
                except Exception: max_out=defaults['max_output_tokens']
                if provider not in enabled:
                    error=f'{stage}: choose an enabled Cloud provider.'; break
                if not primary or not secondary:
                    error=f'{stage}: select both Primary and Failover models.'; break
                if primary==secondary:
                    error=f'{stage}: Primary and Failover must be different models.'; break
                routes[stage]={
                    'provider':provider,'model':primary,'execution_mode':'cloud',
                    'fallback_provider':provider,'fallback_model':secondary,'fallback_execution_mode':'cloud',
                    'max_input_tokens':max_in,'max_output_tokens':max_out,
                }
            if error:
                if request.headers.get('X-Requested-With')=='fetch': return JsonResponse({'ok':False,'error':error},status=400)
                messages.error(request,error)
            else:
                ps.cloud_web_stage_routes=routes
                # Keep legacy fields synchronized to URL discovery for downgrade/export compatibility.
                anchor=routes.get('url_scrape') or next(iter(routes.values()))
                ps.cloud_web_provider=anchor.get('provider',''); ps.cloud_web_primary_model=anchor.get('model',''); ps.cloud_web_secondary_model=anchor.get('fallback_model','')
                ps.save(update_fields=['cloud_web_stage_routes','cloud_web_provider','cloud_web_primary_model','cloud_web_secondary_model','updated_at'])
                cloud_stage_routes=cloud_web_stage_routes(); cloud_selection=cloud_web_selection('url_scrape'); cloud_available=has_usable_cloud_web_model()
                msg='Cloud Web stage routing saved. Each stage will use its own Primary and same-provider Failover.'
                if request.headers.get('X-Requested-With')=='fetch': return JsonResponse({'ok':True,'message':msg,'cloud_available':cloud_available})
                messages.success(request,msg)
        elif action in ('auto_select_cloud_stage_models','auto_detect_cloud_routes'):
            provider=(request.POST.get('cloud_web_provider') or '').strip().lower()
            try:
                if not AIProviderConfig.objects.filter(provider=provider,enabled=True).exists():
                    raise ValueError('Enable this Cloud provider first.')
                if action=='auto_select_cloud_stage_models':
                    stage=(request.POST.get('cloud_stage') or '').strip()
                    if stage not in [s for s in STAGES if s!='chatbot']:
                        raise ValueError('Unknown Cloud Web stage.')
                    primary,secondary=_documented_cloud_pair(provider,'discovery',stage)
                    return JsonResponse({'ok':True,'provider':provider,'stage':stage,'primary':primary,'secondary':secondary})
                routes={}
                for stage in [s for s in STAGES if s!='chatbot']:
                    primary,secondary=_documented_cloud_pair(provider,'discovery',stage)
                    routes[stage]={'provider':provider,'primary':primary,'secondary':secondary}
                label=dict(AIProviderConfig.PROVIDERS).get(provider,provider)
                return JsonResponse({
                    'ok':True,'provider':provider,'routes':routes,
                    'message':'',
                })
            except Exception as exc:
                return JsonResponse({'ok':False,'error':str(exc)},status=400)
        elif action in ('auto_select_chatbot_model','auto_select_chatbot_routes'):
            try:
                chosen=_auto_select_chatbot_routes(request.POST.get('provider') or request.POST.get('runtime'))
                return JsonResponse({'ok':True,**chosen})
            except Exception as exc:
                return JsonResponse({'ok':False,'error':str(exc)},status=400)
        elif action=='test_provider':
            provider=request.POST.get('provider')
            try:
                result=test_provider(provider); messages.success(request,result['message']) if result['ok'] else messages.error(request,result['message'])
            except Exception as e: messages.error(request,str(e))
        elif action=='test_ollama':
            d=ollama_service.diagnostics(); result={'kind':'ollama_diagnostics',**d}; messages.success(request,d['message']) if d['ok'] else messages.error(request,d['message'])
        elif action=='test_ollama_chat':
            try:
                model=request.POST.get('ollama_test_model','').strip() or None; prompt=request.POST.get('ollama_test_prompt','').strip() or 'Briefly explain what ScoutBox does.'
                answer,data=ollama_service.generate(prompt,model=model,stage='lab_ollama_test',timeout=90,max_output_tokens=500)
                result={'kind':'ollama_chat','ok':True,'model':data.get('model') or model,'answer':answer,'tokens_in':data.get('prompt_eval_count',0),'tokens_out':data.get('eval_count',0)}
            except Exception as e:
                result={'kind':'ollama_chat','ok':False,'error':str(e)}
        elif action=='save_chatbot':
            provider=(request.POST.get('chatbot_provider') or '').strip().lower()
            model=(request.POST.get('chatbot_model_name') or '').strip()
            secondary_provider=(request.POST.get('chatbot_secondary_provider') or '').strip().lower()
            secondary_model=(request.POST.get('chatbot_secondary_model_name') or '').strip()
            allowed={'ollama','openai','gemini','openrouter'}
            enabled=AIProviderConfig.objects.filter(provider=provider,enabled=True).exists() if provider else False
            secondary_enabled=AIProviderConfig.objects.filter(provider=secondary_provider,enabled=True).exists() if secondary_provider else False
            local_models={row['model'] for row in _ollama_chatbot_candidates()}
            if provider not in allowed or not enabled:
                messages.error(request,'Enable and select the exact primary Chatbot provider.')
            elif not model:
                messages.error(request,'Enter or select the exact primary Chatbot model.')
            elif provider=='ollama' and model not in local_models:
                messages.error(request,'The selected primary Chatbot model is not an installed Ollama model. Choose a model listed under Ollama local.')
            elif secondary_provider not in allowed or not secondary_enabled:
                messages.error(request,'Enable and select the exact secondary Chatbot provider.')
            elif not secondary_model:
                messages.error(request,'Enter or select the exact secondary Chatbot model.')
            elif secondary_provider=='ollama' and secondary_model not in local_models:
                messages.error(request,'The selected secondary Chatbot model is not an installed Ollama model. Choose a model listed under Ollama local.')
            elif provider==secondary_provider and model==secondary_model:
                messages.error(request,'Primary and secondary Chatbot routes must use different provider/model combinations.')
            else:
                defaults=STAGE_TOKEN_DEFAULTS['chatbot']
                try: answer_cap=max(32,min(20000,int(request.POST.get('chatbot_token_cap') or defaults['max_output_tokens'])))
                except Exception: answer_cap=defaults['max_output_tokens']
                holder=AIProviderConfig.objects.filter(provider='ollama').first() or AIProviderConfig.objects.first()
                if not holder: holder=AIProviderConfig.objects.create(provider='ollama',enabled=True)
                routes=(holder.stage_routes or {}).copy(); previous=(routes.get('chatbot') or {}).copy()
                allow_internet_search=provider in {'openai','gemini','openrouter'} and bool(request.POST.get('chatbot_allow_internet_search'))
                secondary_allow_internet_search=secondary_provider in {'openai','gemini','openrouter'} and bool(request.POST.get('chatbot_secondary_allow_internet_search'))
                previous_input=int(previous.get('max_input_tokens') or 0)
                local_input_default=STAGE_TOKEN_DEFAULTS['chatbot']['max_input_tokens']
                cloud_input_default=CLOUD_STAGE_TOKEN_DEFAULTS['chatbot']['max_input_tokens']
                # Upgrade legacy Chatbot input ceilings when a route is saved. The old 28k
                # default is below the current Local/Cloud defaults; larger deliberate caps stay untouched.
                if provider=='ollama' and (not previous_input or previous_input<=28000): previous_input=local_input_default
                elif provider in {'openai','gemini','openrouter'} and (not previous_input or previous_input<=28000): previous_input=cloud_input_default
                elif not previous_input: previous_input=defaults['max_input_tokens']
                route={
                    'provider':provider,'model':model,'execution_mode':'local' if provider=='ollama' else 'cloud',
                    'fallback_provider':secondary_provider,'fallback_model':secondary_model,
                    'fallback_execution_mode':'local' if secondary_provider=='ollama' else 'cloud',
                    'max_input_tokens':previous_input,
                    'max_output_tokens':answer_cap,
                    'allow_internet_search':allow_internet_search,
                    'fallback_allow_internet_search':secondary_allow_internet_search,
                }
                routes['chatbot']=route; holder.stage_routes=routes; holder.save(update_fields=['stage_routes'])
                label=dict(AIProviderConfig.PROVIDERS).get(provider,provider)
                secondary_label=dict(AIProviderConfig.PROVIDERS).get(secondary_provider,secondary_provider)
                messages.success(request,f'Chatbot routing saved: Primary {label} · {model}; Secondary {secondary_label} · {secondary_model}; {answer_cap} answer tokens.')
        elif action in ('save_ai_timeouts','restore_ai_timeout_defaults'):
            fields={
                'local':('local_ai_request_timeout_seconds','local_ai'),
                'cloud':('cloud_ai_request_timeout_seconds','cloud_ai'),
                'chatbot':('chatbot_provider_timeout_seconds','chatbot'),
            }
            values={}; validation_error=''
            for form_key,(field,lane) in fields.items():
                if action=='restore_ai_timeout_defaults':
                    value=int(AI_REQUEST_TIMEOUT_DEFAULTS[lane])
                else:
                    raw=(request.POST.get(field) or '').strip()
                    try: value=int(raw)
                    except Exception:
                        validation_error=f'{form_key.title()} timeout must be a whole number of seconds.'; break
                    low,high=AI_REQUEST_TIMEOUT_LIMITS[lane]
                    if value < low or value > high:
                        validation_error=f'{form_key.title()} timeout must be between {low} and {high} seconds.'; break
                values[field]=value
            if validation_error:
                messages.error(request,validation_error)
            else:
                for field,value in values.items(): setattr(ps,field,value)
                ps.save(update_fields=[*values.keys(),'updated_at'])
                if action=='restore_ai_timeout_defaults':
                    messages.success(request,'AI request timeouts restored to defaults.')
                else:
                    messages.success(request,'AI request timeouts saved.')
        elif action=='save_routes':
            if ps.discovery_mode!='source_guided':
                messages.info(request,'Cloud Web routing is automatic. Switch to Local AI Discovery to edit local stage routing.')
            else:
                holder=AIProviderConfig.objects.filter(provider='ollama').first() or AIProviderConfig.objects.first()
                existing=(holder.stage_routes or {}).copy() if holder else {}
                routes={'chatbot':(existing.get('chatbot') or {}).copy()}; route_error=None
                for stage in [s for s in STAGES if s!='chatbot']:
                    defaults=STAGE_TOKEN_DEFAULTS.get(stage,STAGE_TOKEN_DEFAULTS['general'])
                    value=request.POST.get(f'route_{stage}','').strip(); fallback_value=request.POST.get(f'fallback_{stage}','').strip()
                    route={
                        'max_input_tokens': max(64,min(200000,int(request.POST.get(f'max_input_{stage}') or defaults['max_input_tokens']))),
                        'max_output_tokens': max(32,min(50000,int(request.POST.get(f'max_output_{stage}') or defaults['max_output_tokens']))),
                    }
                    if value and '|' in value:
                        provider,model=value.split('|',1)
                        if provider!='ollama': route_error='Local AI Discovery stage routing only accepts local Ollama models.'
                        else: route.update({'provider':'ollama','model':model})
                    if fallback_value and '|' in fallback_value:
                        fprovider,fmodel=fallback_value.split('|',1)
                        if fprovider!='ollama': route_error='Local AI Discovery fallback routing only accepts local Ollama models.'
                        else: route.update({'fallback_provider':'ollama','fallback_model':fmodel})
                    routes[stage]=route
                if route_error:
                    messages.error(request,route_error)
                elif holder:
                    holder.stage_routes=routes; holder.save(update_fields=['stage_routes'])
                    messages.success(request,'Local AI Discovery stage routing and token caps saved.')
        elif action in ('automatic_routing','best_local_defaults','best_cloud_defaults'):
            # v0.8.41 presets are deliberately client-side previews.  Keep this
            # defensive POST handler non-persistent for stale tabs/bookmarks.
            messages.info(request,'Local routing presets change the Local AI Discovery selections only. Review them and click Save to keep the changes.')
        elif action=='restore_token_defaults':
            holder=AIProviderConfig.objects.filter(provider='ollama').first() or AIProviderConfig.objects.first()
            if holder:
                holder.stage_routes=default_stage_routes(holder.stage_routes or {})
                holder.save(update_fields=['stage_routes'])
                messages.success(request,'Production token caps restored to sensible defaults; provider/model choices were preserved.')
        elif action=='test_run':
            job=BackgroundJob.objects.create(kind='diagnostic',label='Profile-based Test Discovery',message='Queued')
            task=diagnostic_search_job.delay(job.pk); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
            messages.success(request,'Test Discovery queued. It uses your active Resume/profile and will update below without adding opportunities.')
        if action=='save_discovery_mode' and request.headers.get('X-Requested-With')=='fetch':
            return JsonResponse({'ok':True,'mode':ps.discovery_mode,'label':ps.get_discovery_mode_display()})
        model_choices=_model_choices(); cloud_model_choices=[m for m in model_choices if m['provider'] in ('openai','gemini','openrouter')]
        pipeline_model_last_test,pipeline_model_test_current=_pipeline_model_last_test(ps)
        pipeline_model_active_job=_pipeline_model_active_job(); discovery_test_active_job=_discovery_test_active_job()
        pipeline_presets={'local':_pipeline_mode_preview('local')}
        ollama_prompt_job=BackgroundJob.objects.filter(kind='other',label='Ollama model test').order_by('-created_at').first()
        provider_test_jobs={}
        for cfg in _ordered_ai_configs():
            latest=BackgroundJob.objects.filter(kind='other',label=f'{cfg.provider.title()} provider test').order_by('-created_at').first()
            if latest: provider_test_jobs[cfg.provider]=latest.pk
        common=ctx(request,'settings','AI & Discovery',system_tab='ai',diagnostics=ollama_service.diagnostics(),configs=_ordered_ai_configs(),result=result,model_choices=model_choices,cloud_model_choices=cloud_model_choices,local_model_choices=[m for m in model_choices if m['provider']=='ollama'],cloud_providers=AIProviderConfig.objects.filter(provider__in=['openai','gemini','openrouter'],enabled=True),cloud_available=cloud_available,cloud_priority=cloud_provider_priority(),cloud_selection=cloud_selection,cloud_stage_routes=cloud_web_stage_routes(),cloud_web_effective=cloud_web_effective,bundle_map=bundle_owners(stage_routes_with_defaults(AIProviderConfig.objects.filter(provider='ollama').first().stage_routes if AIProviderConfig.objects.filter(provider='ollama').first() else {}),ps.discovery_mode),stages=[s for s in STAGES if s!='chatbot'],current_routes=stage_routes_with_defaults(AIProviderConfig.objects.filter(provider='ollama').first().stage_routes if AIProviderConfig.objects.filter(provider='ollama').first() else {}),diagnostic_runs=DiagnosticRun.objects.all()[:10],diagnostic_jobs=BackgroundJob.objects.filter(kind='diagnostic',label='Profile-based Test Discovery')[:50],discovery_mode=ps.discovery_mode,ai_timeouts=_ai_timeout_settings_context(ps),chatbot_summary=_chatbot_summary(),chatbot_test_status=_chatbot_test_status(_chatbot_summary()),pipeline_model_status=_pipeline_model_status(ps),pipeline_model_last_test=pipeline_model_last_test,pipeline_model_test_current=pipeline_model_test_current,pipeline_model_active_job=pipeline_model_active_job,discovery_test_active_job=discovery_test_active_job,pipeline_presets=pipeline_presets,ollama_prompt_job=ollama_prompt_job,provider_test_jobs=provider_test_jobs,discovery_test_providers=_discovery_test_provider_options(),discovery_test_uses_cloud=discovery_test_uses_cloud,discovery_test_cloud_provider=discovery_test_cloud_provider,discovery_test_cloud_primary=discovery_test_cloud_primary,discovery_test_cloud_secondary=discovery_test_cloud_secondary,discovery_test_default_keyword=_discovery_test_default_keyword())
        if action in ('save_ai_timeouts','restore_ai_timeout_defaults'):
            return redirect(reverse('ai')+'#miscellaneous')
        return redirect('ai') if action in ('save_discovery_mode','save_provider','save_cloud_selection','test_provider','save_chatbot','save_routes','restore_token_defaults','automatic_routing','best_local_defaults','best_cloud_defaults') else render(request,'portal/ai.html',common)
    model_choices=_model_choices(); cloud_model_choices=[m for m in model_choices if m['provider'] in ('openai','gemini','openrouter')]
    pipeline_model_last_test,pipeline_model_test_current=_pipeline_model_last_test(ps)
    pipeline_model_active_job=_pipeline_model_active_job(); discovery_test_active_job=_discovery_test_active_job()
    pipeline_presets={'local':_pipeline_mode_preview('local')}
    ollama_prompt_job=BackgroundJob.objects.filter(kind='other',label='Ollama model test').order_by('-created_at').first()
    provider_test_jobs={}
    for cfg in _ordered_ai_configs():
        latest=BackgroundJob.objects.filter(kind='other',label=f'{cfg.provider.title()} provider test').order_by('-created_at').first()
        if latest: provider_test_jobs[cfg.provider]=latest.pk
    return render(request,'portal/ai.html',ctx(request,'settings','AI & Discovery',system_tab='ai',diagnostics=ollama_service.diagnostics(),configs=_ordered_ai_configs(),result=result,model_choices=model_choices,cloud_model_choices=cloud_model_choices,local_model_choices=[m for m in model_choices if m['provider']=='ollama'],cloud_providers=AIProviderConfig.objects.filter(provider__in=['openai','gemini','openrouter'],enabled=True),cloud_available=cloud_available,cloud_priority=cloud_provider_priority(),cloud_selection=cloud_selection,cloud_stage_routes=cloud_web_stage_routes(),cloud_web_effective=cloud_web_effective,bundle_map=bundle_owners(stage_routes_with_defaults(AIProviderConfig.objects.filter(provider='ollama').first().stage_routes if AIProviderConfig.objects.filter(provider='ollama').first() else {}),ps.discovery_mode),stages=[s for s in STAGES if s!='chatbot'],current_routes=stage_routes_with_defaults(AIProviderConfig.objects.filter(provider='ollama').first().stage_routes if AIProviderConfig.objects.filter(provider='ollama').first() else {}),diagnostic_runs=DiagnosticRun.objects.all()[:10],diagnostic_jobs=BackgroundJob.objects.filter(kind='diagnostic',label='Profile-based Test Discovery')[:50],discovery_mode=ps.discovery_mode,ai_timeouts=_ai_timeout_settings_context(ps),chatbot_summary=_chatbot_summary(),chatbot_test_status=_chatbot_test_status(_chatbot_summary()),pipeline_model_status=_pipeline_model_status(ps),pipeline_model_last_test=pipeline_model_last_test,pipeline_model_test_current=pipeline_model_test_current,pipeline_model_active_job=pipeline_model_active_job,discovery_test_active_job=discovery_test_active_job,pipeline_presets=pipeline_presets,ollama_prompt_job=ollama_prompt_job,provider_test_jobs=provider_test_jobs,discovery_test_providers=_discovery_test_provider_options(),discovery_test_uses_cloud=discovery_test_uses_cloud,discovery_test_cloud_provider=discovery_test_cloud_provider,discovery_test_cloud_primary=discovery_test_cloud_primary,discovery_test_cloud_secondary=discovery_test_cloud_secondary,discovery_test_default_keyword=_discovery_test_default_keyword(),chatbot_auto_local_available=AIProviderConfig.objects.filter(provider='ollama',enabled=True).exists(),chatbot_auto_cloud_available=AIProviderConfig.objects.filter(provider__in=['openai','gemini','openrouter'],enabled=True).exists()))


@login_required
def performance_view(request):
    if request.method=='POST':
        params={k:request.POST.get(k,'') for k in ('kind','provider','model','device','input_text','input_url','temp_ollama_url')}
        storage_path=''; original_name=''
        f=request.FILES.get('file')
        if f:
            safe=re.sub(r'[^A-Za-z0-9._-]+','_',f.name)[:180] or 'lab.bin'; storage_path=default_storage.save(f'lab_queue/{timezone.now().strftime("%Y%m%d%H%M%S")}_{safe}',f); original_name=f.name
        job=BackgroundJob.objects.create(kind='performance',label=f"Performance Lab: {params.get('kind') or 'test'}",message='Queued')
        task=performance_lab_job.delay(job.pk,params,storage_path,original_name); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
        return redirect('performance')
    runs=PerformanceRun.objects.filter(Q(latency_ms__gt=0)|~Q(error='')|~Q(output_text='')|~Q(output_file=''))
    if request.GET.get('export')=='1':
        return _xlsx('performance_lab.xlsx',['When','Kind','Provider','Model','Device','OK','Latency ms','Input tokens','Output tokens','Downloaded','Error'],[(x.created_at,x.get_kind_display(),x.provider,x.model,x.device,x.ok,x.latency_ms,x.tokens_in,x.tokens_out,x.bytes_downloaded,x.error) for x in runs[:5000]])
    return render(request,'portal/performance.html',ctx(request,'performance','Performance Lab',run=None,runs=runs[:100],jobs=BackgroundJob.objects.filter(kind='performance')[:20],model_choices=_model_choices(),search_providers=SearchSource.objects.filter(name__in=ACTIVE_PROVIDER_NAMES,enabled=True).order_by('name')))


@login_required
def background_job_status(request,pk):
    job=get_object_or_404(BackgroundJob,pk=pk)
    # Manual bulk filters persist an explicit per-row deadline before entering the AI
    # request. If that deadline is exceeded, retire the run here so a broken provider
    # socket/worker path cannot leave the UI and the global manual-filter lock spinning
    # forever. The deadline already includes all supported retry windows plus grace.
    automatic_hidden_reassessment=_is_existing_hidden_lead_reassessment_job(job)
    if job.status=='running' and job.kind in ('filter_opportunities','filter_hidden_leads','filter_contacts') and not automatic_hidden_reassessment:
        result=dict(job.result or {})
        current=result.get('current_item') if isinstance(result.get('current_item'),dict) else {}
        raw_deadline=str(current.get('deadline_at') or '').strip()
        deadline=None
        if raw_deadline:
            try:
                deadline=datetime.fromisoformat(raw_deadline.replace('Z','+00:00'))
                if timezone.is_naive(deadline): deadline=timezone.make_aware(deadline)
            except Exception:
                deadline=None
        if deadline and timezone.now()>deadline:
            now=timezone.now()
            current['state']='timed_out'; current['timed_out_at']=now.isoformat()
            result['current_item']=current
            result['unprocessed']=max(int(result.get('unprocessed') or 0),max(0,int(result.get('selected') or 0)-int(result.get('processed') or 0)))
            result['stop_reason']='manual_filter_request_timeout'
            reason='Current AI request exceeded the manual-filter safety deadline.'
            BackgroundJob.objects.filter(pk=job.pk,status='running').update(
                status='stopped',finished_at=now,message='Filter stopped — AI request exceeded its time limit',
                error=reason,result=result,
            )
            if job.celery_task_id:
                try:
                    from celery import current_app
                    current_app.control.revoke(job.celery_task_id,terminate=True,signal='SIGTERM')
                except Exception:
                    pass
            job.refresh_from_db()
            try: job.save(update_fields=['status','finished_at','message','error','result'])
            except Exception: pass
    if automatic_hidden_reassessment:
        job=_canonicalize_hidden_lead_reassessment_job(job)
    fmt=lambda value: timezone.localtime(value).strftime('%d/%m/%Y %H:%M:%S') if value else ''
    return JsonResponse({'id':job.pk,'kind':job.kind,'status':job.status,'progress':job.progress,'message':job.message,'error':job.error,'result':job.result,'finished':job.status in ('completed','failed','stopped'),'created_at':fmt(job.created_at),'started_at':fmt(job.started_at),'finished_at':fmt(job.finished_at)})


@login_required
@require_POST
def background_job_cancel(request,pk):
    job=get_object_or_404(BackgroundJob,pk=pk)
    if job.kind=='campaign':
        return JsonResponse({'ok':False,'error':'Campaign runs are controlled from Campaigns.'},status=400)
    if job.status not in ('queued','running'):
        return JsonResponse({'ok':True,'id':job.pk,'status':job.status,'finished':True})
    try:
        if job.celery_task_id:
            from celery import current_app
            current_app.control.revoke(job.celery_task_id,terminate=True,signal='SIGTERM')
    except Exception as exc:
        logger.warning('Unable to revoke background job %s: %s',job.pk,exc)
    job.status='stopped'; job.finished_at=timezone.now(); job.message='Stopped by user'; job.error=''
    job.save(update_fields=['status','finished_at','message','error'])
    try: log('background.stop',request,job,summary=job.label)
    except Exception: pass
    return JsonResponse({'ok':True,'id':job.pk,'status':'stopped','finished':True})



@login_required
@require_POST
def background_job_skip_current(request,pk):
    """Skip the current item in a resumable Hidden Lead reassessment job.

    The 0.11.9/0.11.11 Hidden Lead minibrowser pass can spend a long time on one
    domain.  This endpoint does not delete or modify that lead; it records the current
    lead id as skipped, terminates the current celery execution when possible, and
    immediately requeues the same BackgroundJob so the reassessment resumes at the next
    lead.  It is intentionally scoped to the upgrade/reassessment Hidden Lead job, not
    ordinary Opportunity/Address Book filters.
    """
    job=get_object_or_404(BackgroundJob,pk=pk)
    job=_canonicalize_hidden_lead_reassessment_job(job)
    result=dict(job.result or {})
    if job.kind!='filter_hidden_leads' or not result.get('hidden_lead_minibrowser_reassessment'):
        return JsonResponse({'ok':False,'error':'Skip current is only available for Hidden Lead minibrowser reassessment.'},status=400)
    if job.status not in ('queued','running'):
        return JsonResponse({'ok':True,'id':job.pk,'status':job.status,'finished':job.status in ('completed','failed','stopped')})
    current=result.get('current_item') if isinstance(result.get('current_item'),dict) else {}
    lead_id=current.get('id') or result.get('current_lead_id')
    now=timezone.now()
    skipped=list(result.get('skip_current_ids') or result.get('skipped_current_ids') or [])
    if lead_id and lead_id not in skipped:
        skipped.append(lead_id)
    if lead_id:
        try:
            lead=CompanyLead.objects.filter(pk=lead_id, user_deleted=False, deleted_at__isnull=True).first()
            if lead:
                ai_state=dict(lead.ai_state or {})
                ai_state['hidden_lead_minibrowser_reassessment']={
                    'decision':'review',
                    'review':True,
                    'admit':False,
                    'lead_score':int(lead.score or 0),
                    'source':'existing_hidden_lead_minibrowser_reassessment_skipped_current',
                    'release':'0.11.29',
                    'skipped_current':True,
                    'at':now.isoformat(),
                    'reason':'Skipped by user while reassessment was in progress; lead left unchanged.',
                    'protected_outreach':False,
                }
                lead.ai_state=ai_state
                lead.save(update_fields=['ai_state','updated_at'])
        except Exception as exc:
            logger.warning('Unable to persist hidden lead skip-current state for %s: %s', lead_id, exc)
    result['skip_current_ids']=skipped
    result['skip_current_requested_at']=now.isoformat()
    try:
        ps=PortalSettings.objects.get_or_create(pk=1)[0]
        state=dict(ps.focus_taxonomy_state or {})
        pass_state=state.get('hidden_lead_minibrowser_reassessment_pass')
        if isinstance(pass_state,dict):
            pass_state=dict(pass_state)
            pass_skipped=list(pass_state.get('skip_current_ids') or [])
            if lead_id and lead_id not in pass_skipped:
                pass_skipped.append(lead_id)
            pass_state['skip_current_ids']=pass_skipped
            current_pass=pass_state.get('current_item') if isinstance(pass_state.get('current_item'),dict) else {}
            if lead_id and int(current_pass.get('id') or 0)==int(lead_id):
                current_pass=dict(current_pass); current_pass['state']='skip_requested'; current_pass['skip_requested_at']=now.isoformat(); pass_state['current_item']=current_pass
            pass_state['updated_at']=now.isoformat()
            state['hidden_lead_minibrowser_reassessment_pass']=pass_state
            ps.focus_taxonomy_state=state
            ps.save(update_fields=['focus_taxonomy_state','updated_at'])
    except Exception as exc:
        logger.warning('Unable to persist hidden lead skip-current durable pass state for %s: %s', lead_id, exc)
    if current:
        current['state']='skip_requested'
        current['skip_requested_at']=now.isoformat()
        result['current_item']=current
    result['skip_current_message']='Current Hidden Lead will be left unchanged and the reassessment will resume with the next lead.'
    job.status='queued'
    job.message='Skipping current Hidden Lead · resuming with next lead'
    job.result=result
    job.error=''
    job.save(update_fields=['status','message','result','error'])
    if job.celery_task_id:
        try:
            from celery import current_app
            current_app.control.revoke(job.celery_task_id,terminate=True,signal='SIGTERM')
        except Exception as exc:
            logger.warning('Unable to revoke hidden lead reassessment item %s: %s',job.pk,exc)
    try:
        from portal.tasks import _dispatch_hidden_lead_reassessment_job
        ps=PortalSettings.objects.get_or_create(pk=1)[0]
        dispatched_job_id=_dispatch_hidden_lead_reassessment_job(job,ps,reason='skip_current')
        if dispatched_job_id:
            job.refresh_from_db(fields=['status','message','result','celery_task_id'])
    except Exception as exc:
        logger.warning('Unable to requeue hidden lead reassessment %s after skip: %s',job.pk,exc)
    try: log('background.skip_current',request,job,summary=job.label)
    except Exception: pass
    return JsonResponse({'ok':True,'id':job.pk,'status':'queued','finished':False,'skipped_current_id':lead_id,'message':job.message})

def _diagnostics():
    out=[]
    try:
        with connection.cursor() as cur: cur.execute('SELECT 1'); cur.fetchone()
        out.append(('PostgreSQL','OK','Database reachable'))
    except Exception as e: out.append(('PostgreSQL','ERROR',str(e)))
    try:
        import redis; r=redis.Redis.from_url(settings.CELERY_BROKER_URL); r.ping(); out.append(('Redis / queue','OK','Broker reachable'))
    except Exception as e: out.append(('Redis / queue','ERROR',str(e)))
    d=ollama_service.diagnostics(); out.append(('Ollama','OK' if d['ok'] else 'WARN',d['message']))
    p=active_profile()
    if p:
        try: im=imap_connect(p); im.logout(); out.append(('IMAP','OK',f'{p.get_template_display()}: {p.imap_host}:{p.imap_port}'))
        except Exception as e: out.append(('IMAP','ERROR',str(e)))
        if outgoing_method(p)=='resend':
            if p.resend_api_key_enc and p.notification_from_email:
                out.append(('Outgoing mail','OK','Resend API configured · api.resend.com'))
            else:
                out.append(('Outgoing mail','WARN','Resend API key or From email is missing'))
        else:
            try:
                s=smtplib.SMTP(p.smtp_host,p.smtp_port,timeout=4); s.ehlo(); s.quit(); out.append(('Notification SMTP','OK',f'{p.smtp_host}:{p.smtp_port}'))
            except Exception as e: out.append(('Notification SMTP','WARN',str(e)))
    else: out.append(('IMAP','WARN','No active email profile'))
    try:
        import shutil as _shutil
        lo=_shutil.which('libreoffice') or _shutil.which('soffice')
        out.append(('Document conversion','OK' if lo else 'WARN',lo or 'LibreOffice not found'))
    except Exception as e: out.append(('Document conversion','WARN',str(e)))
    try:
        import psutil
        vm=psutil.virtual_memory(); out.append(('System memory','OK',f'{vm.percent:.0f}% used; {vm.available//(1024**2)} MB available to container'))
    except Exception as e: out.append(('System memory','WARN',str(e)))
    try:
        cfg=BlogStatsConfig.objects.get_or_create(pk=1)[0]
        if cfg.enabled:
            ok,msg=_blog_test(cfg); out.append(('External statistics','OK' if ok else 'WARN',msg))
        else: out.append(('External statistics','WARN','Synchronization disabled'))
    except Exception as e: out.append(('External statistics','WARN',str(e)))
    try:
        from opportunity_portal.celery import app as celery_app
        ping=celery_app.control.inspect(timeout=1.0).ping() or {}
        out.append(('Task worker','OK' if ping else 'WARN',f'{len(ping)} Celery worker(s) responding' if ping else 'No Celery worker ping response'))
    except Exception as e: out.append(('Task worker','WARN',str(e)))
    active_sources=SearchSource.objects.filter(enabled=True,adapter_status='active').count()
    out.append(('Search adapters','OK' if active_sources else 'WARN',f'{active_sources} active query adapter(s); other enabled presets are target/source hints'))
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    if ps.discovery_mode=='cloud_web':
        ai_state=ai_compute_readiness()
        cloud_ready=any(x.get('ready') for x in (ai_state.get('states') or []) if x.get('provider') in ('openai','gemini','openrouter'))
        out.append(('Discovery mode','OK' if cloud_ready else 'WARN','Cloud Web Discovery; ordinary Search Source providers bypassed for URL finding' if cloud_ready else 'Cloud Web Discovery selected but no validated usable cloud route is ready'))
    else:
        out.append(('Discovery mode','OK','Local AI Discovery; configured search providers find URLs before AI analysis'))
    out.append(('Authenticated/deep page fetch','OK' if ps.feature_authenticated_social_fetch and ps.feature_page_fetch else 'WARN','Enabled' if ps.feature_authenticated_social_fetch and ps.feature_page_fetch else 'Optional browser/deep fetch path disabled'))
    out.append(('Automatic tasks','WARN' if ps.background_paused else 'OK','Paused by user' if ps.background_paused else f'Enabled; discovery every {ps.scraper_interval_minutes} min'))
    out.append(('Backup','WARN','Automatic backup destination is not configured; use the documented PostgreSQL + media-volume backup procedure.'))
    return out


def _token_category_label(stage, category, operation=''):
    raw=(stage or category or 'Other').strip()
    op=str(operation or '').strip().lower().replace('-','_')
    stage_key=str(stage or '').strip().lower().replace('-','_')
    # Manual/utility AI work should reconcile with Token Usage without being mistaken for
    # normal discovery-pipeline work merely because it reuses stages such as first_filter.
    # Keep this intentionally broad for explicitly manual operations and configuration tests.
    if op in {'ad_hoc','manual','manual_rebuild','provider_test','configuration_test','settings_test'} or stage_key in {'provider_test','lab','lab_direct'}:
        return 'Ad hoc Actions'
    return {'question_answers':'Q/A','question answers':'Q/A','question_answer':'Q/A','question answer':'Q/A','answers':'Q/A'}.get(raw.lower(), raw.replace('_',' ').replace('-',' ').strip().title() or 'Other')


def _token_category_breakdown(qs):
    """Summarise input + output + reasoning tokens by processing category/stage."""
    sums=qs.aggregate(tokens_in=Sum('tokens_in'),tokens_out=Sum('tokens_out'),reasoning_tokens=Sum('reasoning_tokens'))
    total=int(sums.get('tokens_in') or 0)+int(sums.get('tokens_out') or 0)+int(sums.get('reasoning_tokens') or 0)
    if not total:
        return [], 'No token usage recorded for this period.'
    rows=list(qs.values('stage','category','metadata__operation').annotate(tokens_in=Sum('tokens_in'),tokens_out=Sum('tokens_out'),reasoning_tokens=Sum('reasoning_tokens')))
    grouped=[]
    for row in rows:
        label=_token_category_label(row.get('stage'),row.get('category'),row.get('metadata__operation'))
        tin=int(row.get('tokens_in') or 0); tout=int(row.get('tokens_out') or 0); reason=int(row.get('reasoning_tokens') or 0)
        tokens=tin+tout+reason
        if not tokens:
            continue
        found=next((x for x in grouped if x['label']==label),None)
        if found:
            found['tokens']+=tokens; found['tokens_in']+=tin; found['tokens_out']+=tout; found['reasoning_tokens']+=reason
        else:
            grouped.append({'label':label,'tokens':tokens,'tokens_in':tin,'tokens_out':tout,'reasoning_tokens':reason})
    grouped.sort(key=lambda x:x['tokens'],reverse=True)
    shown=grouped[:7]; remainder=sum(x['tokens'] for x in grouped[7:]); remainder_in=sum(x.get('tokens_in',0) for x in grouped[7:]); remainder_out=sum(x.get('tokens_out',0) for x in grouped[7:]); remainder_reason=sum(x.get('reasoning_tokens',0) for x in grouped[7:])
    if remainder:
        shown.append({'label':'Other','tokens':remainder,'tokens_in':remainder_in,'tokens_out':remainder_out,'reasoning_tokens':remainder_reason})
    for row in shown:
        row['pct']=round(row['tokens']*100.0/total,1)
    title='Token use: ' + '; '.join(f"{x['label']} {x['pct']:.1f}%" for x in shown)
    return shown,title


def _token_category_model_breakdown(qs):
    """Return model-scoped token/category rows so the UI can apply one filter to both token charts."""
    rows=list(qs.values('provider','model','stage','category','metadata__operation').annotate(tokens_in=Sum('tokens_in'),tokens_out=Sum('tokens_out'),reasoning_tokens=Sum('reasoning_tokens')))
    aliases={'ollama':'Ollama','openai':'OpenAI','gemini':'Gemini','openrouter':'OpenRouter'}
    out=[]
    for row in rows:
        tokens_in=int(row.get('tokens_in') or 0); tokens_out=int(row.get('tokens_out') or 0); reasoning_tokens=int(row.get('reasoning_tokens') or 0)
        tokens=tokens_in+tokens_out+reasoning_tokens
        if not tokens:
            continue
        raw_provider=str(row.get('provider') or '').strip()
        provider=aliases.get(raw_provider.lower(),raw_provider or 'Unattributed')
        model=str(row.get('model') or '').strip() or 'Model not recorded'
        out.append({
            'provider':provider,
            'label':model,
            'category':_token_category_label(row.get('stage'),row.get('category'),row.get('metadata__operation')),
            'tokens':tokens,
            'tokens_in':tokens_in,
            'tokens_out':tokens_out,
            'reasoning_tokens':reasoning_tokens,
        })
    return sorted(out,key=lambda x:(x['provider'].lower(),x['label'].lower(),x['category'].lower()))


def _token_provider_breakdown(qs):
    """Summarise input + output + reasoning tokens by the provider that actually executed them."""
    rows=list(qs.values('provider').annotate(tokens_in=Sum('tokens_in'),tokens_out=Sum('tokens_out'),reasoning_tokens=Sum('reasoning_tokens')))
    grouped={}
    aliases={'ollama':'Ollama','openai':'OpenAI','gemini':'Gemini','openrouter':'OpenRouter'}
    for row in rows:
        raw=str(row.get('provider') or '').strip()
        tokens_in=int(row.get('tokens_in') or 0); tokens_out=int(row.get('tokens_out') or 0); reasoning_tokens=int(row.get('reasoning_tokens') or 0)
        tokens=tokens_in+tokens_out+reasoning_tokens
        if not tokens:
            continue
        label=aliases.get(raw.lower(),raw or 'Unattributed')
        item=grouped.setdefault(label,{'label':label,'tokens':0,'tokens_in':0,'tokens_out':0,'reasoning_tokens':0})
        item['tokens']+=tokens; item['tokens_in']+=tokens_in; item['tokens_out']+=tokens_out; item['reasoning_tokens']+=reasoning_tokens
    values=sorted(grouped.values(),key=lambda x:(-x['tokens'],x['label'].lower()))
    total=sum(x['tokens'] for x in values)
    if not total:
        return [], 'No provider token usage recorded for this period.'
    shown=values[:9]
    if len(values)>9:
        remainder=values[9:]
        shown.append({'label':'Other','tokens':sum(x['tokens'] for x in remainder),'tokens_in':sum(x['tokens_in'] for x in remainder),'tokens_out':sum(x['tokens_out'] for x in remainder),'reasoning_tokens':sum(x['reasoning_tokens'] for x in remainder)})
    for row in shown:
        row['pct']=round(row['tokens']*100.0/total,1)
    title='Token providers: ' + '; '.join(f"{x['label']} {x['pct']:.1f}%" for x in shown)
    return shown,title


def _token_model_breakdown(qs):
    """Summarise token consumption by the provider/model pair that executed it."""
    rows=list(qs.values('provider','model').annotate(tokens_in=Sum('tokens_in'),tokens_out=Sum('tokens_out'),reasoning_tokens=Sum('reasoning_tokens')))
    aliases={'ollama':'Ollama','openai':'OpenAI','gemini':'Gemini','openrouter':'OpenRouter'}
    grouped={}
    for row in rows:
        raw_provider=str(row.get('provider') or '').strip()
        provider=aliases.get(raw_provider.lower(),raw_provider or 'Unattributed')
        raw_model=str(row.get('model') or '').strip()
        model=raw_model or 'Model not recorded'
        tokens_in=int(row.get('tokens_in') or 0); tokens_out=int(row.get('tokens_out') or 0); reasoning_tokens=int(row.get('reasoning_tokens') or 0)
        tokens=tokens_in+tokens_out+reasoning_tokens
        if not tokens:
            continue
        key=(provider,model)
        item=grouped.setdefault(key,{'provider':provider,'label':model,'tokens':0,'tokens_in':0,'tokens_out':0,'reasoning_tokens':0})
        item['tokens']+=tokens; item['tokens_in']+=tokens_in; item['tokens_out']+=tokens_out; item['reasoning_tokens']+=reasoning_tokens
    values=sorted(grouped.values(),key=lambda x:(-x['tokens'],x['provider'].lower(),x['label'].lower()))
    total=sum(x['tokens'] for x in values)
    if not total:
        return [], 'No model token usage recorded for this period.'
    # Return every concrete provider/model pair. The Resource Usage UI performs its
    # own top-N condensation when displaying all models, but keeps this complete set
    # available for the interactive multi-select filter.
    for row in values:
        row['pct']=round(row['tokens']*100.0/total,1)
    title='Token models: ' + '; '.join(f"{x['provider']} / {x['label']} {x['pct']:.1f}%" for x in values[:12])
    if len(values)>12:
        title+=f'; +{len(values)-12} more'
    return values,title


def _safe_ollama_diagnostics():
    try:
        return ollama_service.diagnostics() or {'ok':False,'installed':[],'message':'Ollama diagnostics unavailable.'}
    except Exception as exc:
        return {'ok':False,'installed':[],'message':f'Ollama diagnostics unavailable: {str(exc)[:180]}'}


def _provider_performance_rows(pstats):
    perf={}
    for row in pstats.order_by('source__name','day'):
        item=perf.setdefault(row.source.name,{'provider':row.source.name,'requests':0,'results':0,'unique_results':0,'duplicates':0,'applied_matches':0,'errors':0,'bytes_downloaded':0,'latency_weight':0,'latency_requests':0,'last_error':'','last_error_day':None})
        item['requests']+=row.requests; item['results']+=row.results; item['unique_results']+=row.unique_results; item['duplicates']+=row.duplicates; item['applied_matches']+=row.applied_matches; item['errors']+=row.errors; item['bytes_downloaded']+=row.bytes_downloaded
        item['latency_weight']+=row.avg_latency_ms*max(row.requests,1); item['latency_requests']+=max(row.requests,1)
        if row.last_error: item['last_error']=row.last_error; item['last_error_day']=row.day
    out=[]
    for item in perf.values():
        item['avg_latency_ms']=round(item['latency_weight']/item['latency_requests']) if item['latency_requests'] else 0
        out.append(item)
    out.sort(key=lambda x:(-int(x.get('requests') or 0),x['provider'].lower()))
    return out

def _resource_sample_rows(samples, start=None, end=None, max_points=240):
    """Return adaptive resource buckets while preserving spikes.

    Ranges beyond three days are first aggregated hourly in SQL, then combined into
    approximately ``max_points`` display buckets.  This means a 30-day desktop chart
    is normally around 3-hour resolution instead of one average per day.  Every bucket
    retains min/average/max values so a short CPU/RAM/GPU spike is still visible in
    hover diagnostics even though the plotted line remains the average.
    """
    fields=('at','cpu_percent','memory_percent','memory_used_mb','memory_total_mb','disk_used_mb','disk_total_mb','gpu_percent','gpu_memory_percent','gpu_vram_used_mb','gpu_vram_total_mb','gpu_label','gpu_sample_age_seconds','gpu_telemetry_state','host_telemetry_age_seconds')
    duration=(end-start).total_seconds() if start and end else None
    if duration is None:
        try:
            bounds=samples.aggregate(_first=Min('at'),_last=Max('at'))
            if bounds.get('_first') and bounds.get('_last'):
                duration=max(0,(bounds['_last']-bounds['_first']).total_seconds())
        except Exception:
            duration=None
    try:
        if duration is not None and duration > 3*86400:
            # Never annotate back onto the model's existing `at` field. Django treats
            # that as a field-name collision on several backends and 0.10.94 converted
            # the resulting exception into an empty 7/30-day chart.
            rows=list(samples.annotate(_bucket=TruncHour('at')).values('_bucket').annotate(
                _sample_at=Max('at'),
                cpu_percent=Avg('cpu_percent'),cpu_min=Min('cpu_percent'),cpu_max=Max('cpu_percent'),
                memory_percent=Avg('memory_percent'),memory_min=Min('memory_percent'),memory_max=Max('memory_percent'),
                memory_used_mb=Avg('memory_used_mb'),memory_total_mb=Avg('memory_total_mb'),
                disk_used_mb=Avg('disk_used_mb'),disk_total_mb=Avg('disk_total_mb'),
                gpu_percent=Avg('gpu_percent'),gpu_min=Min('gpu_percent'),gpu_max=Max('gpu_percent'),
                gpu_memory_percent=Avg('gpu_memory_percent'),
                gpu_vram_used_mb=Avg('gpu_vram_used_mb'),gpu_vram_total_mb=Avg('gpu_vram_total_mb'),
                gpu_label=Max('gpu_label'),gpu_sample_age_seconds=Avg('gpu_sample_age_seconds'),
                gpu_telemetry_state=Max('gpu_telemetry_state'),host_telemetry_age_seconds=Avg('host_telemetry_age_seconds')).order_by('_bucket'))
            for row in rows:
                row['at']=row.pop('_sample_at',None) or row.get('_bucket')
        else:
            rows=list(samples.order_by('at').values(*fields))
            for row in rows:
                row['cpu_min']=row['cpu_max']=row.get('cpu_percent')
                row['memory_min']=row['memory_max']=row.get('memory_percent')
                row['gpu_min']=row['gpu_max']=row.get('gpu_percent')
    except Exception:
        # A chart-query failure must be observable and must not masquerade as "no data".
        # Fall back to a bounded recent raw sample set so the page remains useful while
        # diagnostics retain the traceback for repair.
        logger.exception('Resource Usage aggregation failed; using bounded raw fallback')
        try:
            fallback=list(samples.order_by('-at').values(*fields)[:max(240,max_points*4)])
            fallback.reverse(); rows=fallback
            for row in rows:
                row['cpu_min']=row['cpu_max']=row.get('cpu_percent')
                row['memory_min']=row['memory_max']=row.get('memory_percent')
                row['gpu_min']=row['gpu_max']=row.get('gpu_percent')
        except Exception:
            logger.exception('Resource Usage fallback query also failed')
            rows=[]
    # 0.11.144 durable archive: for long-range views, fill hours that no longer
    # have detailed ResourceSample rows from ResourceHourly. Raw samples always win.
    if duration is not None and duration > 3*86400:
        try:
            archived=ResourceHourly.objects.all()
            if start: archived=archived.filter(hour__gte=start)
            if end: archived=archived.filter(hour__lt=end)
            def hour_key(value):
                if value is None: return None
                local=timezone.localtime(value) if timezone.is_aware(value) else value
                return local.replace(minute=0,second=0,microsecond=0).isoformat()
            occupied={hour_key(row.get('at')) for row in rows if row.get('at')}
            for item in archived.order_by('hour').values(
                'hour','last_sample_at','sample_count','cpu_avg','cpu_min','cpu_max',
                'memory_avg','memory_min','memory_max','memory_used_mb','memory_total_mb',
                'disk_used_mb','disk_total_mb','gpu_avg','gpu_min','gpu_max',
                'gpu_sample_count','gpu_stale_count','gpu_label','gpu_vram_used_mb','gpu_vram_total_mb'):
                key=hour_key(item.get('hour'))
                if key in occupied:
                    continue
                rows.append({
                    'at':item.get('hour'),
                    'cpu_percent':item.get('cpu_avg'),'cpu_min':item.get('cpu_min'),'cpu_max':item.get('cpu_max'),
                    'memory_percent':item.get('memory_avg'),'memory_min':item.get('memory_min'),'memory_max':item.get('memory_max'),
                    'memory_used_mb':item.get('memory_used_mb'),'memory_total_mb':item.get('memory_total_mb'),
                    'disk_used_mb':item.get('disk_used_mb'),'disk_total_mb':item.get('disk_total_mb'),
                    'gpu_percent':item.get('gpu_avg'),'gpu_min':item.get('gpu_min'),'gpu_max':item.get('gpu_max'),
                    'gpu_memory_percent':None,'gpu_vram_used_mb':item.get('gpu_vram_used_mb'),'gpu_vram_total_mb':item.get('gpu_vram_total_mb'),
                    'gpu_label':item.get('gpu_label') or '',
                    'gpu_sample_age_seconds':None,'gpu_telemetry_state':'hourly_archive','host_telemetry_age_seconds':None,
                    '_hourly_archive':True,
                })
                occupied.add(key)
            rows.sort(key=lambda row:row.get('at') or timezone.now())
        except Exception:
            logger.exception('Resource Usage hourly archive fallback failed')

    if len(rows)<=max_points:
        return rows

    size=max(1,math.ceil(len(rows)/max_points))
    grouped=[]
    avg_fields=('cpu_percent','memory_percent','memory_used_mb','memory_total_mb','disk_used_mb','disk_total_mb','gpu_percent','gpu_memory_percent','gpu_vram_used_mb','gpu_vram_total_mb','gpu_sample_age_seconds','host_telemetry_age_seconds')
    for pos in range(0,len(rows),size):
        chunk=rows[pos:pos+size]
        if not chunk: continue
        item={'at':chunk[-1].get('at'),'gpu_label':next((r.get('gpu_label') for r in reversed(chunk) if r.get('gpu_label')),''),
              'gpu_telemetry_state':next((r.get('gpu_telemetry_state') for r in reversed(chunk) if r.get('gpu_telemetry_state')),''),
              '_hourly_archive':all(bool(r.get('_hourly_archive')) for r in chunk)}
        for key in avg_fields:
            vals=[float(r[key]) for r in chunk if r.get(key) is not None]
            item[key]=(sum(vals)/len(vals)) if vals else None
        for metric in ('cpu','memory','gpu'):
            mins=[float(r[f'{metric}_min']) for r in chunk if r.get(f'{metric}_min') is not None]
            maxs=[float(r[f'{metric}_max']) for r in chunk if r.get(f'{metric}_max') is not None]
            item[f'{metric}_min']=min(mins) if mins else None
            item[f'{metric}_max']=max(maxs) if maxs else None
        grouped.append(item)
    return grouped[-max_points:]


def _resource_chart_rows(sample_rows, usage_qs, start=None, end=None, max_points=240):
    """Merge real resource samples with usage data across the selected time range.

    Resource samples and usage-only timeline points are sampled independently. This keeps
    CPU/RAM/GPU history intact on long ranges instead of allowing usage-only hours to crowd
    hardware samples out of the chart. Synthetic usage points are explicitly marked so the
    browser can ignore them when deciding whether a hardware line is continuous.
    """
    sample_rows=list(sample_rows or [])
    selected_span=(end-start).total_seconds() if start and end else 0

    def blank(at, *, synthetic_usage=False, range_boundary=False):
        return {'at':at,'cpu_percent':None,'cpu_min':None,'cpu_max':None,
            'memory_percent':None,'memory_min':None,'memory_max':None,'memory_used_mb':None,'memory_total_mb':None,
            'disk_used_mb':None,'disk_total_mb':None,'gpu_percent':None,'gpu_min':None,'gpu_max':None,
            'gpu_memory_percent':None,'gpu_vram_used_mb':None,'gpu_vram_total_mb':None,'gpu_label':'',
            'gpu_sample_age_seconds':None,'gpu_telemetry_state':'','host_telemetry_age_seconds':None,
            '_synthetic_usage':bool(synthetic_usage),'_range_boundary':bool(range_boundary)}

    # Mark retained hardware rows explicitly; older callers/data do not carry these flags.
    for row in sample_rows:
        row.setdefault('_synthetic_usage',False)
        row.setdefault('_range_boundary',False)

    if selected_span>3*86400:
        aggregates=list(usage_qs.annotate(_chart_hour=TruncHour('at')).values('_chart_hour','provider').annotate(
            requests=Sum('requests'),tokens_in=Sum('tokens_in'),tokens_out=Sum('tokens_out')).order_by('_chart_hour'))
        events=[{'at':row['_chart_hour'],'provider':row.get('provider'),'requests':row.get('requests'),
                 'tokens_in':row.get('tokens_in'),'tokens_out':row.get('tokens_out')} for row in aggregates if row.get('_chart_hour')]
        occupied={row.get('at').replace(minute=0,second=0,microsecond=0) for row in sample_rows if row.get('at')}
        missing=[]
        for at in sorted({row['at'] for row in events}):
            hour=at.replace(minute=0,second=0,microsecond=0)
            if hour not in occupied:
                missing.append(at)
        # Cap usage-only markers independently. Never downsample the hardware rows again.
        if len(missing)>max_points:
            indexes=sorted({round(i*(len(missing)-1)/max(1,max_points-1)) for i in range(max_points)})
            missing=[missing[index] for index in indexes]
        sample_rows.extend(blank(at,synthetic_usage=True) for at in missing)
    else:
        if sample_rows:
            first_sample=sample_rows[0]['at']; last_sample=sample_rows[-1]['at']
            events=list(usage_qs.filter(at__gt=first_sample-timedelta(seconds=120),at__lte=last_sample)
                        .order_by('at').values('at','requests','tokens_in','tokens_out','provider'))
        else:
            events=[]

    if start and end and end>start:
        # Boundary points keep the requested x-axis range without masquerading as resource
        # samples. Avoid duplicate timestamps when an hourly usage point already sits exactly
        # on a boundary, which would otherwise draw a zero-width request/token drop.
        existing_at={row.get('at') for row in sample_rows if row.get('at')}
        end_boundary=end-timedelta(microseconds=1)
        if start not in existing_at:
            sample_rows.append(blank(start,range_boundary=True))
        if end_boundary not in existing_at:
            sample_rows.append(blank(end_boundary,range_boundary=True))

    if not sample_rows:
        return []
    sample_rows.sort(key=lambda row:row.get('at') or timezone.now())
    first_at=sample_rows[0]['at']
    event_idx=0; previous_at=first_at-timedelta(seconds=90); out=[]
    cloud={'openai','gemini','openrouter'}
    for row in sample_rows:
        at=row['at']; requests=0; local_tokens=0; cloud_tokens=0
        while event_idx < len(events) and events[event_idx]['at'] <= at:
            ev=events[event_idx]
            if ev['at'] > previous_at:
                requests += int(ev.get('requests') or 0)
                tokens=int(ev.get('tokens_in') or 0)+int(ev.get('tokens_out') or 0)
                if str(ev.get('provider') or '').lower() in cloud: cloud_tokens += tokens
                else: local_tokens += tokens
            event_idx += 1
        vram_used=row.get('gpu_vram_used_mb'); vram_total=row.get('gpu_vram_total_mb')
        vram_pct=None
        if vram_used is not None and vram_total:
            vram_pct=max(0.0,min(100.0,float(vram_used)*100.0/float(vram_total)))
        out.append({
            'at':timezone.localtime(at).strftime('%d/%m %H:%M:%S'),
            'at_iso':timezone.localtime(at).isoformat(),
            'at_export':timezone.localtime(at).strftime('%d/%m/%Y %H:%M:%S'),
            'cpu':None if row.get('cpu_percent') is None else round(float(row.get('cpu_percent')),1),
            'cpu_min':None if row.get('cpu_min') is None and row.get('cpu_percent') is None else round(float(row.get('cpu_min') if row.get('cpu_min') is not None else row.get('cpu_percent')),1),
            'cpu_max':None if row.get('cpu_max') is None and row.get('cpu_percent') is None else round(float(row.get('cpu_max') if row.get('cpu_max') is not None else row.get('cpu_percent')),1),
            'memory':None if row.get('memory_percent') is None else round(float(row.get('memory_percent')),1),
            'memory_min':None if row.get('memory_min') is None and row.get('memory_percent') is None else round(float(row.get('memory_min') if row.get('memory_min') is not None else row.get('memory_percent')),1),
            'memory_max':None if row.get('memory_max') is None and row.get('memory_percent') is None else round(float(row.get('memory_max') if row.get('memory_max') is not None else row.get('memory_percent')),1),
            'memory_used_mb':int(row.get('memory_used_mb') or 0),
            'memory_total_mb':int(row.get('memory_total_mb') or 0),
            'disk_used_mb':int(row.get('disk_used_mb') or 0),
            'disk_total_mb':int(row.get('disk_total_mb') or 0),
            'gpu':None if row.get('gpu_percent') is None else round(float(row['gpu_percent']),1),
            'gpu_min':None if row.get('gpu_min') is None and row.get('gpu_percent') is None else round(float(row.get('gpu_min') if row.get('gpu_min') is not None else row.get('gpu_percent')),1),
            'gpu_max':None if row.get('gpu_max') is None and row.get('gpu_percent') is None else round(float(row.get('gpu_max') if row.get('gpu_max') is not None else row.get('gpu_percent')),1),
            'gpu_label':row.get('gpu_label') or '',
            'gpu_vram_used_mb':None if vram_used is None else int(vram_used),
            'gpu_vram_total_mb':None if vram_total is None else int(vram_total),
            'gpu_vram_percent':None if vram_pct is None else round(vram_pct,1),
            'gpu_sample_age_seconds':row.get('gpu_sample_age_seconds'),
            'gpu_telemetry_state':row.get('gpu_telemetry_state') or '',
            'host_telemetry_age_seconds':row.get('host_telemetry_age_seconds'),
            'requests':requests,
            'local_tokens':local_tokens,
            'cloud_tokens':cloud_tokens,
            'synthetic_usage':bool(row.get('_synthetic_usage')),
            'range_boundary':bool(row.get('_range_boundary')),
            'hourly_archive':bool(row.get('_hourly_archive')),
        })
        previous_at=at
    return out


def _path_size_bytes(path):
    """Best-effort recursive size for ScoutBox-owned host/container paths."""
    try:
        root=os.fspath(path)
        if not os.path.exists(root): return 0
        if os.path.isfile(root): return max(0,int(os.path.getsize(root)))
        total=0
        for base,_,files in os.walk(root):
            for name in files:
                try: total+=os.path.getsize(os.path.join(base,name))
                except OSError: pass
        return total
    except Exception:
        return 0


_DISK_BREAKDOWN_CACHE={'at':0.0,'value':None}


def _disk_usage_breakdown(system_info=None, ollama_diag=None):
    """Report only storage owned by ScoutBox itself.

    Host/Docker/system storage and Ollama model files are intentionally excluded. They are
    useful host-capacity facts but are not ScoutBox application footprint and previously
    made the dashboard total misleading on machines with large model/system volumes.
    """
    now=time.monotonic()
    cached=_DISK_BREAKDOWN_CACHE.get('value')
    if cached is not None and now-float(_DISK_BREAKDOWN_CACHE.get('at') or 0)<60:
        return cached
    mb=1024*1024
    db_bytes=0
    try:
        if connection.vendor=='postgresql':
            with connection.cursor() as cur:
                cur.execute('SELECT pg_database_size(current_database())'); db_bytes=int(cur.fetchone()[0] or 0)
        elif connection.vendor=='sqlite':
            db_bytes=_path_size_bytes(settings.DATABASES['default'].get('NAME') or '')
    except Exception:
        db_bytes=0
    media_bytes=_path_size_bytes(getattr(settings,'MEDIA_ROOT',''))
    runtime_bytes=_path_size_bytes(Path(settings.BASE_DIR)/'.scoutbox-runtime') if hasattr(settings,'BASE_DIR') else 0
    app_tree_bytes=_path_size_bytes(settings.BASE_DIR) if hasattr(settings,'BASE_DIR') else 0
    app_bytes=max(0,app_tree_bytes-media_bytes-runtime_bytes)
    direct=[
        ('PostgreSQL database' if connection.vendor=='postgresql' else 'Database',db_bytes),
        ('Uploads / media',media_bytes),
        ('ScoutBox application files',app_bytes),
        ('ScoutBox runtime files',runtime_bytes),
    ]
    all_rows=[]
    for label,raw in direct:
        value=max(0,int(raw or 0))
        all_rows.append({'label':label,'bytes':value,'mb':round(value/mb,1)})
    # Keep the total exact, but do not clutter the details popup with rows that
    # round to 0 MB at the precision shown to the user.
    owned=sum(x['bytes'] for x in all_rows)
    rows=[x for x in all_rows if float(x.get('mb') or 0)>0]
    def pretty(value):
        if value>=1024**3: return f'{value/(1024**3):.1f} GB'
        return f'{value/mb:.1f} MB'
    value={
        'rows':rows,
        'scoutbox_used_mb':round(owned/mb,1),
        'scoutbox_used_pretty':pretty(owned),
        'components_total_mb':round(owned/mb,1),
        'note':'Only ScoutBox-owned storage is included. Ollama models and other host, Docker and system files are excluded.',
    }
    _DISK_BREAKDOWN_CACHE.update(at=now,value=value)
    return value

def _telemetry_data_days(start=None, end=None):
    """Count distinct local calendar days that contain Resource Usage data.

    ResourceSample retention is intentionally short, so combine it with the
    longer-lived UsageMetric and SearchProviderStat histories. Each query asks
    the database only for distinct dates; historical rows are not loaded.
    """
    usage=UsageMetric.objects.exclude(category='lab')
    provider_stats=SearchProviderStat.objects.all()
    samples=ResourceSample.objects.all(); hourly=ResourceHourly.objects.all()
    if start:
        usage=usage.filter(at__gte=start)
        provider_stats=provider_stats.filter(day__gte=timezone.localtime(start).date())
        samples=samples.filter(at__gte=start); hourly=hourly.filter(hour__gte=start)
    if end:
        usage=usage.filter(at__lt=end)
        provider_stats=provider_stats.filter(day__lt=timezone.localtime(end).date())
        samples=samples.filter(at__lt=end); hourly=hourly.filter(hour__lt=end)
    days=set(usage.order_by().values_list('at__date',flat=True).distinct())
    days.update(provider_stats.order_by().values_list('day',flat=True).distinct())
    days.update(samples.order_by().values_list('at__date',flat=True).distinct())
    days.update(hourly.order_by().values_list('hour__date',flat=True).distinct())
    return len([day for day in days if day is not None])


def _resource_telemetry_health(start=None,end=None):
    """Compact continuity/coverage status for the Resource Usage page."""
    now=timezone.now()
    latest=ResourceSample.objects.order_by('-at').first()
    latest_age=None if latest is None else max(0.0,(now-latest.at).total_seconds())
    archive=ResourceHourly.objects.all()
    if start: archive=archive.filter(hour__gte=start)
    if end: archive=archive.filter(hour__lt=end)
    hours=int(archive.count())
    gpu_hours=int(archive.filter(gpu_sample_count__gt=0).count())
    expected=None
    if start and end and end>start:
        expected=max(1,int(math.ceil((end-start).total_seconds()/3600.0)))
    hardware_pct=None if not expected else min(100.0,round(hours*100.0/expected,1))
    gpu_pct=None if not expected else min(100.0,round(gpu_hours*100.0/expected,1))
    oldest=archive.order_by('hour').values_list('hour',flat=True).first()
    newest=archive.order_by('-hour').values_list('hour',flat=True).first()
    bridge=bridge_telemetry_status()
    latest_gpu_state=str(getattr(latest,'gpu_telemetry_state','') or bridge.get('gpu_telemetry_state') or 'unavailable') if latest else str(bridge.get('gpu_telemetry_state') or 'unavailable')
    warnings=[]
    if latest_age is None or latest_age>60:
        warnings.append('Resource sampling is not current.')
    if latest_gpu_state in {'unavailable','bridge_missing','bridge_stale'}:
        warnings.append('GPU telemetry is unavailable or stale.')
    return {
        'latest_sample_age_seconds':None if latest_age is None else round(latest_age,1),
        'latest_gpu_state':latest_gpu_state,
        'latest_gpu_age_seconds':getattr(latest,'gpu_sample_age_seconds',None) if latest else bridge.get('gpu_sample_age_seconds'),
        'host_bridge_age_seconds':bridge.get('bridge_age_seconds'),
        'archive_hours':hours,'gpu_archive_hours':gpu_hours,
        'hardware_coverage_pct':hardware_pct,'gpu_coverage_pct':gpu_pct,
        'archive_oldest':timezone.localtime(oldest).strftime('%d/%m/%Y %H:%M') if oldest else '',
        'archive_newest':timezone.localtime(newest).strftime('%d/%m/%Y %H:%M') if newest else '',
        'warnings':warnings,'ok':not warnings,
    }


def _cloud_usage_dashboard(period='month', start=None, end=None):
    """Provider-neutral Cloud AI usage for the Resource Usage selection.

    CloudBudgetUsage remains a daily safety ledger. Historical views sum daily buckets;
    hard enforcement still resets every local calendar day. Output and reasoning are
    shown separately for billing visibility while the existing combined output+reasoning
    counter remains the actual safety limit.
    """
    keys=('requests','web_searches','tokens_in','tokens_out','reasoning_tokens','tokens_out_reasoning','passive_enrichment','page_recovery')
    try:
        current=cloud_today_usage(); lim=current.get('limits') or {}
    except Exception:
        current={}; lim={}
    try:
        qs=CloudBudgetUsage.objects.all()
        start_day=timezone.localtime(start).date() if start else None
        end_day=timezone.localtime(end-timedelta(microseconds=1)).date() if end else timezone.localdate()
        if start_day: qs=qs.filter(day__gte=start_day)
        if end_day: qs=qs.filter(day__lte=end_day)
        values=qs.aggregate(**{key:Sum(key) for key in keys})
        data={key:int(values.get(key) or 0) for key in keys}
        first_day=qs.order_by('day').values_list('day',flat=True).first()
        range_start=start_day or first_day or end_day
        range_end=end_day or timezone.localdate()
        day_count=max(1,(range_end-range_start).days+1) if range_start and range_end and range_end>=range_start else 1
    except Exception:
        data={key:int(current.get(key) or 0) for key in keys}
        day_count=1
        start_day=end_day=timezone.localdate()

    period_labels={'1h':'1 hr','3h':'3 hrs','6h':'6 hrs','12h':'12 hrs','24h':'24 hrs','3d':'3 days','7d':'7 days','30d':'30 days','all':'All Data'}
    if period=='custom':
        left=start_day.strftime('%d/%m/%Y') if start_day else 'Beginning'
        right=end_day.strftime('%d/%m/%Y') if end_day else 'Now'
        period_label=f'{left} – {right}'
    else:
        period_label=period_labels.get(period,period.replace('_',' ').title() if period else 'Selected period')
    # label, bucket key, daily limit key, has hard/comparison limit
    rows=[
        ('Cloud AI Requests','requests','daily_requests',True),
        ('AI Web Search Queries','web_searches','daily_web_searches',True),
        ('Input Tokens','tokens_in','daily_input_tokens',True),
        ('Output + Reasoning','tokens_out_reasoning','daily_output_tokens',True),
        ('Passive Enrichment','passive_enrichment','passive_enrichment',True),
        ('Page Recovery','page_recovery','page_recovery',True),
    ]
    out=[]
    for label,key,lkey,has_limit in rows:
        used=int(data.get(key) or 0)
        daily_limit=int(lim.get(lkey) or 0) if lkey else 0
        limit=daily_limit*day_count if daily_limit else 0
        pct=min(100,round(used*100/limit,1)) if limit else 0
        state='exhausted' if limit and used>=limit else ('warning' if limit and used>=limit*.8 else 'normal')
        out.append({'label':label,'key':key,'used':used,'limit':limit,'daily_limit':daily_limit,'pct':pct,'state':state,'has_limit':bool(has_limit and limit)})
    return {'rows':out,'title':f'Cloud Usage — {period_label}','note':'','days':day_count,'period_label':period_label}


def _market_coverage_from_rows(rows):
    """Normalize grouped discovery-market telemetry into chart-ready rings."""
    language_labels={'english':'English'}
    language_labels.update({str(name).casefold():str(name) for name,_flag in MULTILINGUAL_LANGUAGE_OPTIONS})
    language_counts=Counter(); market_counts=Counter(); market_names={}
    for row in rows:
        requests=max(0,int(row.get('requests') or 0))
        if not requests:
            continue
        code=str(row.get('metadata__market_code') or '').strip().lower()
        market=MARKET_BY_CODE.get(code)
        if not market:
            continue
        language_raw=' '.join(str(row.get('metadata__multilingual_language') or '').split()) or 'English'
        language=language_labels.get(language_raw.casefold(),language_raw)
        language_counts[language]+=requests
        market_counts[code]+=requests
        market_names[code]=market.name
    total=sum(market_counts.values())
    languages=[
        {'label':label,'requests':requests,'share':round(requests*100/total,1) if total else 0}
        for label,requests in sorted(language_counts.items(),key=lambda item:(-item[1],item[0].casefold()))
    ]
    markets=[
        {'code':code,'label':market_names[code],'flag':MARKET_BY_CODE[code].flag,'requests':requests,'share':round(requests*100/total,1) if total else 0}
        for code,requests in sorted(market_counts.items(),key=lambda item:(-item[1],market_names[item[0]].casefold()))
    ]
    return {'total_requests':total,'languages':languages,'markets':markets}


def _market_coverage_breakdown(usage_qs):
    """Aggregate executed discovery-market requests by language and market.

    Discovery writes one ``discovery_market/query`` metric for every provider
    request. Empty multilingual metadata is the normal English discovery pass;
    populated values identify the local/additional language that was actually used.
    Keeping this derived from request telemetry makes the chart respect the selected
    Resource Usage period and avoids presenting enabled-but-never-run markets as work.
    """
    rows=(usage_qs.filter(category='discovery_market',stage='query')
          .values('metadata__market_code','metadata__market','metadata__multilingual_language')
          .annotate(requests=Sum('requests')).order_by())
    return _market_coverage_from_rows(rows)


@login_required
def telemetry_view(request):
    current_resource_sample=_capture_resource_sample(force=True,allow_stale_fallback=False)
    period,start,end=_resource_period_bounds(request); qs=UsageMetric.objects.all(); pstats=SearchProviderStat.objects.select_related('source').all(); q=_q(request)
    if start: qs=qs.filter(at__gte=start); pstats=pstats.filter(day__gte=start.date())
    if end: qs=qs.filter(at__lt=end); pstats=pstats.filter(day__lt=end.date())
    if q:
        qs=qs.filter(Q(provider__icontains=q)|Q(model__icontains=q)|Q(stage__icontains=q)|Q(category__icontains=q))
        pstats=pstats.filter(Q(source__name__icontains=q)|Q(last_error__icontains=q))
    provider=request.GET.get('provider',''); category=request.GET.get('category','')
    if provider:
        qs=qs.filter(provider__icontains=provider); pstats=pstats.filter(source__name__icontains=provider)
    if category: qs=qs.filter(category=category)
    if request.GET.get('errors')=='1': qs=qs.filter(errors__gt=0)
    totals=qs.aggregate(requests=Sum('requests'),tokens_in=Sum('tokens_in'),tokens_out=Sum('tokens_out'),reasoning_tokens=Sum('reasoning_tokens'),web_search_queries=Sum('web_search_queries'),pages=Sum('pages'),errors=Sum('errors'),bytes_downloaded=Sum('bytes_downloaded'))
    request_breakdown=list(qs.values('category','provider').annotate(requests=Sum('requests'),errors=Sum('errors')).order_by('-requests')[:30])
    provider_performance=_provider_performance_rows(pstats)
    market_coverage=_market_coverage_breakdown(qs)
    export=request.GET.get('export','')
    if export=='provider_performance':
        return _xlsx('discovery_performance.xlsx',['Discovery Source','Requests','Returned results','Unique matches','Applied matches','Duplicates','Errors','Avg latency ms','Size bytes','Last error'],[(x['provider'],x['requests'],x['results'],x['unique_results'],x['applied_matches'],x['duplicates'],x['errors'],x['avg_latency_ms'],x['bytes_downloaded'],x['last_error']) for x in provider_performance])
    if export=='provider_performance_legend':
        return _xlsx('discovery_performance_legend.xlsx',['Discovery Source','Requests','Returned results','Errors'],[(x['provider'],x['requests'],x['results'],x['errors']) for x in provider_performance])
    if export=='market_coverage_legend':
        coverage_rows=[('Language',x['label'],x['requests'],x['share']) for x in market_coverage['languages']]
        coverage_rows.extend(('Market',x['label'],x['requests'],x['share']) for x in market_coverage['markets'])
        return _xlsx('market_coverage_legend.xlsx',['Ring','Language / Market','Requests','Share %'],coverage_rows)
    if export=='token_model_legend':
        token_model_rows,_title=_token_model_breakdown(qs)
        return _xlsx('token_usage_legend.xlsx',['Provider','Model','Total tokens','Input tokens','Output tokens','Reasoning tokens','Share %'],[(x['provider'],x['label'],x['tokens'],x['tokens_in'],x['tokens_out'],x['reasoning_tokens'],x.get('pct',0)) for x in token_model_rows])
    if export=='provider_activity':
        return _xlsx('discovery_source_activity.xlsx',['Day','Discovery Source','Requests','Results','Unique','Duplicates','Applied matches','Latency ms','Size bytes','Errors','Last error'],[(x.day,x.source.name,x.requests,x.results,x.unique_results,x.duplicates,x.applied_matches,x.avg_latency_ms,x.bytes_downloaded,x.errors,x.last_error) for x in pstats[:10000]])
    usage_events=_aggregate_usage_events(qs)
    if export=='usage':
        return _xlsx('resource_usage.xlsx',['Latest','Category','Provider','Model','Stage','Events','Requests','Pages','Avg latency ms','Input tokens','Output tokens','Reasoning tokens','AI Web Search Queries','Errors','Size bytes'],[(x['at'],x['category'],x['provider'],x['model'],x['stage'],x['events'],x['requests'],x['pages'],x['latency_ms'],x['tokens_in'],x['tokens_out'],x['reasoning_tokens'],x['web_search_queries'],x['errors'],x['bytes_downloaded']) for x in usage_events])
    if export=='request_breakdown':
        return _xlsx('request_breakdown.xlsx',['Category','Provider','Requests','Errors'],[(x['category'],x['provider'],x['requests'],x['errors']) for x in request_breakdown])
    samples=ResourceSample.objects.all()
    if start: samples=samples.filter(at__gte=start)
    if end: samples=samples.filter(at__lt=end)
    if export=='resource_chart':
        # XLSX is a forensic/raw-data export, not a rendering of the sampled chart.
        # Keep every ResourceSample in the selected period even when the on-screen
        # Month/All chart is bucketed/downsampled for browser performance.
        raw_fields=('at','cpu_percent','memory_percent','memory_used_mb','memory_total_mb','disk_used_mb','disk_total_mb','gpu_percent','gpu_memory_percent','gpu_vram_used_mb','gpu_vram_total_mb','gpu_label','gpu_sample_age_seconds','gpu_telemetry_state','host_telemetry_age_seconds')
        raw_sample_rows=list(samples.order_by('at').values(*raw_fields))
        raw_resource_rows=_resource_chart_rows(raw_sample_rows,qs)
        return _xlsx(
            'cpu_ram_tokens.xlsx',
            ['Timestamp','CPU %','RAM %','RAM used MB','RAM total MB','Disk used MB','Disk total MB','GPU %','GPU model','VRAM used MB','VRAM total MB','GPU sample age seconds','GPU telemetry state','Host telemetry age seconds','Requests','Local tokens','Cloud tokens'],
            [(x.get('at_export') or x.get('at',''),x.get('cpu'),x.get('memory'),x.get('memory_used_mb'),x.get('memory_total_mb'),x.get('disk_used_mb'),x.get('disk_total_mb'),x.get('gpu'),x.get('gpu_label'),x.get('gpu_vram_used_mb'),x.get('gpu_vram_total_mb'),x.get('gpu_sample_age_seconds'),x.get('gpu_telemetry_state'),x.get('host_telemetry_age_seconds'),x.get('requests'),x.get('local_tokens'),x.get('cloud_tokens')) for x in raw_resource_rows],
        )
    sample_rows=_resource_sample_rows(samples,start,end,max_points=240)
    # Hardware and usage retention differ. The merge helper preserves real hardware
    # geometry while adding independently sampled usage-only timeline points and requested
    # range boundaries, so neither series crowds the other out.
    resource_chart=_resource_chart_rows(sample_rows,qs,start,end,max_points=240)
    token_category_breakdown,token_category_title=_token_category_breakdown(qs)
    token_category_model_breakdown=_token_category_model_breakdown(qs)
    token_provider_breakdown,token_provider_title=_token_provider_breakdown(qs)
    token_model_breakdown,token_model_title=_token_model_breakdown(qs)
    download_breakdown=list(qs.exclude(bytes_downloaded=0).values('category','provider').annotate(bytes=Sum('bytes_downloaded')).order_by('-bytes')[:100])
    system_info=_system_snapshot(sample=current_resource_sample or ResourceSample()); ollama_diag=_safe_ollama_diagnostics(); disk_breakdown=_disk_usage_breakdown(system_info,ollama_diag); show_vram_series=bool(current_resource_sample and (getattr(current_resource_sample,'gpu_vram_total_mb',None) or 0)>0)
    fmt=lambda raw: (timezone.localtime(_parse_user_date(raw)).strftime('%d/%m/%Y') if raw and _parse_user_date(raw) else raw)
    return render(request,'portal/telemetry.html',ctx(request,'telemetry','Resource Usage',metrics=usage_events,provider_stats=pstats.order_by('-day','-requests')[:1000],provider_performance=provider_performance,market_coverage=market_coverage,period=period,q=q,totals=totals,system_info=system_info,ollama=ollama_diag,disk_breakdown=disk_breakdown,download_breakdown=download_breakdown,date_from=fmt(request.GET.get('from','')),date_to=fmt(request.GET.get('to','')),request_breakdown=request_breakdown,resource_chart_json=resource_chart,telemetry_data_days=_telemetry_data_days(start,end),telemetry_health=_resource_telemetry_health(start,end),telemetry_updated=timezone.localtime(timezone.now()),token_category_breakdown=token_category_breakdown,token_category_title=token_category_title,token_category_model_breakdown=token_category_model_breakdown,token_provider_breakdown=token_provider_breakdown,token_provider_title=token_provider_title,token_model_breakdown=token_model_breakdown,token_model_title=token_model_title,show_vram_series=show_vram_series,cloud_usage=_cloud_usage_dashboard(period,start,end)))


def _discovery_source_summary(qs):
    candidates=[]
    for source in SearchSource.objects.exclude(source_type__in=['search_engine','regional_search']).exclude(base_url='').order_by('name'):
        try:
            parsed=urlparse(source.base_url)
            host=(parsed.netloc or '').lower().removeprefix('www.')
            path=(parsed.path or '').lower().strip('/')
            if host and host not in {'example.invalid'}:
                candidates.append((host,path,source.name))
        except Exception:
            continue
    candidates.sort(key=lambda x:len(x[1]),reverse=True)
    counts=Counter()
    for o in qs.select_related('source').only('target_url','url','search_url','source__source_type','source__name','source__config_json','extracted_facts').iterator():
        # Forum is a first-class user-facing source bucket. A forum opportunity remains
        # Forum even when the forum page was originally discovered through Cloud AI,
        # Search Engine, or Direct/native acquisition.
        if _three_way_discovery_source(o) == 'Forum':
            counts['Forum']+=1
            continue
        raw=o.target_url or o.url or o.search_url or ''
        try:
            parsed=urlparse(raw); host=(parsed.netloc or '').lower().removeprefix('www.'); path=(parsed.path or '').lower().strip('/')
        except Exception:
            host=''; path=''
        found='Other Web'
        for base_host,base_path,name in candidates:
            if host == base_host or host.endswith('.'+base_host):
                if not base_path or path == base_path or path.startswith(base_path.rstrip('/')+'/'):
                    found=name; break
        counts[found]+=1
    total=sum(counts.values())
    return [{'name':name,'n':n,'share':round((n*100/total),1) if total else 0} for name,n in counts.most_common()], total




def _three_way_discovery_source(entity):
    """Normalize provenance to the source classes used in Statistics."""
    source=getattr(entity,'source',None)
    source_type=str(getattr(source,'source_type','') or '').lower()
    source_name=str(getattr(source,'name','') or '')
    facts=getattr(entity,'extracted_facts',None)
    if not isinstance(facts,dict):
        facts=getattr(entity,'ai_state',None) if isinstance(getattr(entity,'ai_state',None),dict) else {}
    acq=facts.get('acquisition') if isinstance(facts.get('acquisition'),dict) else {}
    path=' '.join(str(acq.get(k) or '') for k in ('path','adapter','source_category')).casefold()
    if source_type=='forum' or acq.get('source_category')=='forum' or isinstance(facts.get('forum'),dict) or 'forum' in path:
        return 'Forum'
    cloud_parts=[str(facts.get(k) or '').strip() for k in ('cloud_discovery_provider','cloud_discovery_model')]
    cloud=' '.join(x for x in cloud_parts if x).casefold().strip()
    cloud_marker=facts.get('cloud_discovery')
    if isinstance(cloud_marker,dict):
        cloud_marker=any(str(v or '').strip() for v in cloud_marker.values())
    if source_type=='cloud_ai' or bool(cloud_marker) or bool(cloud) or 'cloud web' in path:
        return 'Cloud AI'
    cfg=getattr(source,'config_json',{}) if source is not None else {}
    direct_adapter=str((cfg or {}).get('direct_adapter') or '') if isinstance(cfg,dict) else ''
    if direct_adapter or 'direct' in path or 'company career' in path:
        return 'Direct search'
    if source_type in {'search_engine','regional_search'} or source_name:
        return 'Search engine'
    return 'Search engine'

def _source_url_key(value):
    """Normalize a provenance URL for cross-record source attribution."""
    raw=str(value or '').strip()
    if not raw:
        return ''
    try:
        parsed=urlparse(raw if '://' in raw else 'https://'+raw)
        host=(parsed.hostname or '').casefold().removeprefix('www.')
        path=re.sub(r'/+','/',parsed.path or '/').rstrip('/').casefold()
        if not host:
            return ''
        return host+(path or '/')
    except Exception:
        return raw.casefold().rstrip('/')

def _source_provenance_index(opportunities, leads):
    """Map origin URLs to Search engine / Cloud AI / Direct search.

    Address Book records intentionally keep a lightweight string source rather than a
    ForeignKey. Matching the saved source URL back to the originating Opportunity/Lead
    preserves the real acquisition path in Statistics instead of guessing from labels
    such as ``Source-guided Opportunity``.
    """
    index={}
    for rows,fields in (
        (opportunities,('target_url','url','search_url','canonical_url')),
        (leads,('target_url','source_url','search_url')),
    ):
        try:
            iterator=rows.select_related('source').iterator(chunk_size=300)
        except Exception:
            iterator=rows
        for row in iterator:
            bucket=_three_way_discovery_source(row)
            for field in fields:
                key=_source_url_key(getattr(row,field,'') or '')
                if key:
                    # Prefer a concrete non-search attribution if the same URL was later
                    # rediscovered by a stronger direct/cloud path.
                    previous=index.get(key)
                    if previous in (None,'Search engine') or bucket!='Search engine':
                        index[key]=bucket
    return index

def _three_way_contact_source(contact, provenance_index=None):
    key=_source_url_key(getattr(contact,'source_url','') or '')
    if provenance_index and key in provenance_index:
        return provenance_index[key]
    text=' '.join((str(getattr(contact,'source','') or ''),str(getattr(contact,'source_url','') or ''))).casefold()
    if 'forum' in text or any(x in text for x in ('eevblog.com/forum','forum.arduino.cc','forum.kicad.info','forums.raspberrypi.com','vogons.org')):
        return 'Forum'
    if any(x in text for x in ('cloud web','openai','gemini','openrouter','cloud ai')):
        return 'Cloud AI'
    if any(x in text for x in ('direct','ats','company career','feed','api','community','facebook')):
        return 'Direct search'
    return 'Search engine'

def _source_pie_rows(rows, classifier):
    counts={'Cloud AI':0,'Search engine':0,'Direct search':0,'Forum':0}
    for row in rows.iterator(chunk_size=300) if hasattr(rows,'iterator') else rows:
        counts[classifier(row)]=counts.get(classifier(row),0)+1
    return [{'name':name,'n':n} for name,n in counts.items() if n]

def _acquisition_quality_summary(qs):
    """Summarize Opportunity quality by acquisition path.

    Direct-source records carry an explicit acquisition path. Older records fall back to
    their SearchSource type so the table remains useful across upgrades.
    """
    buckets={}
    for row in qs.select_related('source','application').iterator(chunk_size=250):
        facts=row.extracted_facts if isinstance(row.extracted_facts,dict) else {}
        acq=facts.get('acquisition') if isinstance(facts.get('acquisition'),dict) else {}
        path=str(acq.get('path') or '').strip()
        if not path:
            st=str(getattr(row.source,'source_type','') or '').lower()
            if st=='forum' or acq.get('source_category')=='forum': path='Forum'
            elif st=='cloud_ai': path='Cloud Web'
            elif st in {'search_engine','regional_search'}: path='Search engine'
            else: path='Other Web'
        b=buckets.setdefault(path,{'name':path,'n':0,'strong':0,'fully_remote':0,'ages':[],'applications':0})
        b['n']+=1
        if int(row.fit_score or 0)>=80 or row.status=='apply': b['strong']+=1
        remote=facts.get('remote_classification') if isinstance(facts.get('remote_classification'),dict) else {}
        if str(remote.get('status') or '').lower()=='fully_remote': b['fully_remote']+=1
        age=opportunity_post_age_sort_days(row)
        if age is not None: b['ages'].append(int(age))
        try:
            if row.application and not row.application.deleted_at: b['applications']+=1
        except Exception:
            pass
    out=[]
    for b in buckets.values():
        ages=sorted(b.pop('ages'))
        median=(ages[len(ages)//2] if len(ages)%2 else round((ages[len(ages)//2-1]+ages[len(ages)//2])/2)) if ages else None
        n=max(1,b['n'])
        b.update({'strong_share':round(b['strong']*100/n,1),'remote_share':round(b['fully_remote']*100/n,1),'median_age_days':median})
        out.append(b)
    return sorted(out,key=lambda x:(-x['n'],x['name']))

def _stats_opportunity_domain_rows(qs, limit=8):
    """Count the public role-link domains exactly as Opportunities displays them.

    ``target_url`` takes precedence over ``url`` and the hostname is lower-cased with
    a leading ``www.`` removed. The highest-volume domains stay visible while the
    remainder is combined into one bounded ``Other`` slice.
    """
    counts=Counter()
    for _pk,target_url,url in qs.values_list('pk','target_url','url').iterator(chunk_size=500):
        raw=str(target_url or url or '').strip()
        if not raw:
            continue
        try:
            parsed=urlparse(raw)
            host=(parsed.netloc or '').lower().split('@')[-1].split(':')[0].removeprefix('www.')
        except Exception:
            host=''
        if host:
            counts[host]+=1
    ranked=sorted(counts.items(),key=lambda item:(-item[1],item[0]))
    rows=[{'name':name,'n':count} for name,count in ranked[:limit]]
    other=sum(count for _name,count in ranked[limit:])
    if other:
        rows.append({'name':'Other','n':other})
    return rows


def _stats_location_distribution(qs):
    """Return one chart item per normalized stored location label.

    Stored country/location text can legitimately contain several countries. Treat
    each normalized label as its own slice rather than displaying a combined value
    such as ``United States, France`` as one country.
    """
    counts=Counter()
    for _pk,country,locations in qs.values_list('pk','country','locations').iterator(chunk_size=500):
        items=normalize_location_items(locations or country, source='statistics_country', evidence=country or '')
        for item in items:
            label=str(item.get('label') or '').strip()
            if label:
                counts[label]+=1
    return [{'country':name,'n':count} for name,count in sorted(counts.items(),key=lambda item:(-item[1],item[0]))]


@login_required
def stats_view(request):
    period,start,end=_period_bounds(request); qs=Opportunity.objects.filter(suppressed=False,user_deleted=False); rejection_qs=Opportunity.objects.exclude(rejection_reason=''); leads=CompanyLead.objects.filter(user_deleted=False); contacts=Contact.objects.filter(deleted_at__isnull=True); apps=Application.objects.filter(opportunity__user_deleted=False,deleted_at__isnull=True); usage=UsageMetric.objects.all(); pstats=SearchProviderStat.objects.all(); q=_q(request)
    if start: qs=qs.filter(created_at__gte=start); rejection_qs=rejection_qs.filter(created_at__gte=start); leads=leads.filter(created_at__gte=start); contacts=contacts.filter(created_at__gte=start); apps=apps.filter(created_at__gte=start); usage=usage.filter(at__gte=start); pstats=pstats.filter(day__gte=start.date())
    if end: qs=qs.filter(created_at__lt=end); rejection_qs=rejection_qs.filter(created_at__lt=end); leads=leads.filter(created_at__lt=end); contacts=contacts.filter(created_at__lt=end); apps=apps.filter(created_at__lt=end); usage=usage.filter(at__lt=end); pstats=pstats.filter(day__lt=end.date())
    if q:
        qs=qs.filter(Q(title__icontains=q)|Q(company__icontains=q)|Q(source__name__icontains=q)|Q(campaigns__name__icontains=q)).distinct()
        rejection_qs=rejection_qs.filter(Q(title__icontains=q)|Q(company__icontains=q)|Q(source__name__icontains=q)|Q(campaigns__name__icontains=q)).distinct()
        leads=leads.filter(Q(company__icontains=q)|Q(summary__icontains=q)|Q(source__name__icontains=q)|Q(campaigns__name__icontains=q)).distinct()
        contacts=contacts.filter(Q(company__icontains=q)|Q(name__icontains=q)|Q(email__icontains=q)|Q(source__icontains=q)).distinct()
        apps=apps.filter(Q(opportunity__title__icontains=q)|Q(opportunity__company__icontains=q)|Q(opportunity__source__name__icontains=q)|Q(opportunity__campaigns__name__icontains=q)).distinct()
    opportunity_domains=_stats_opportunity_domain_rows(qs)
    by_country=_stats_location_distribution(qs)
    lead_by_country=_stats_location_distribution(leads)
    discovery_mix=[{'name':'Opportunities','n':qs.count()},{'name':'Leads','n':leads.count()}]
    source_summary,source_total=_discovery_source_summary(qs)
    opportunity_source_pie=_source_pie_rows(qs,_three_way_discovery_source)
    lead_source_pie=_source_pie_rows(leads,_three_way_discovery_source)
    contact_provenance=_source_provenance_index(qs,leads)
    contact_source_pie=_source_pie_rows(contacts,lambda row:_three_way_contact_source(row,contact_provenance))
    acquisition_quality=_acquisition_quality_summary(qs)
    funnel={'found':qs.count(),'reviewed':qs.filter(status__in=['apply','review','info','draft','applied','closed']).count(),'prepared':apps.count(),'applied':apps.filter(status__in=['applied','reply','interview','rejected','accepted','closed']).count(),'reply':apps.filter(status__in=['reply','interview','rejected','accepted']).count(),'interview':apps.filter(status='interview').count(),'accepted':apps.filter(status='accepted').count()}
    downloads=usage.aggregate(v=Sum('bytes_downloaded'))['v'] or 0
    provider_totals=pstats.aggregate(requests=Sum('requests'),results=Sum('results'),unique=Sum('unique_results'),duplicates=Sum('duplicates'),applied=Sum('applied_matches'),errors=Sum('errors'),bytes=Sum('bytes_downloaded'))
    rejects=rejection_qs.values('rejection_reason').annotate(n=Count('id',distinct=True)).order_by('-n')[:15]
    report_end=end or timezone.now(); report_start=start or stats_service.earliest_activity(q=q); report_period=period if period!='all' else 'all'
    series,performance_totals=stats_service.performance_series(report_start,report_end,report_period,q=q); comparison=stats_service.comparison_periods(q=q)
    period_names={'1h':'1 hr','3h':'3 hrs','6h':'6 hrs','12h':'12 hrs','24h':'24 hrs','3d':'3 days','7d':'7 days','30d':'30 days','all':'All Data','custom':'Custom range'}
    period_label=period_names.get(period,period.title())
    if report_start and report_end: period_label += f" · {timezone.localtime(report_start).strftime('%d %b %Y')} – {timezone.localtime(report_end).strftime('%d %b %Y')}"
    export=request.GET.get('export','').lower()
    if export=='source_summary':
        return _xlsx('opportunities_by_discovery_source.xlsx',['Discovery Source','Opportunities','Share %'],[(x['name'],x['n'],x['share']) for x in source_summary])
    if export=='acquisition_quality':
        return _xlsx('opportunity_acquisition_quality.xlsx',['Acquisition Path','Opportunities','Strong Fit %','Fully Remote %','Median Post Age (days)','Applications'],[(x['name'],x['n'],x['strong_share'],x['remote_share'],x['median_age_days'] if x['median_age_days'] is not None else '',x['applications']) for x in acquisition_quality])
    if export=='rejections':
        return _xlsx('rejection_suppression_reasons.xlsx',['Reason','Count'],[(x['rejection_reason'],x['n']) for x in rejects])
    if export in ('xlsx','pdf'):
        stamp=timezone.localdate().strftime('%Y%m%d')
        if export=='xlsx':
            data=stats_service.export_xlsx(series,performance_totals,comparison,period_label); response=HttpResponse(data,content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'); response['Content-Disposition']=f'attachment; filename="scoutbox-statistics-{stamp}.xlsx"'; return response
        data=stats_service.export_pdf(series,performance_totals,comparison,period_label); response=HttpResponse(data,content_type='application/pdf'); response['Content-Disposition']=f'attachment; filename="scoutbox-statistics-{stamp}.pdf"'; return response
    chart_payload={'series':series,'metrics':stats_service.METRIC_META,'groups':{'discovery':['pages_scraped','roles_found','duplicates','already_applied'],'funnel':['high_priority','newly_applied','responded','followed_up','rejected'],'tokens':['tokens_consumed'],'download':['data_downloaded']}}
    try:
        stats_map_payload=_statistics_world_map_payload(qs,leads,contacts,apps,start=start,end=end,q=q)
    except Exception:
        logger.exception('Statistics map payload failed')
        stats_map_payload={'viewBox': {'width':1440,'height':720}, 'layers': []}
    comparison_columns=[comparison[x] for x in ('week','month','quarter','year')]; definitions=stats_service.metric_definitions(); export_params=request.GET.copy(); export_params.pop('export',None); export_query=export_params.urlencode()
    return render(request,'portal/stats.html',ctx(request,'stats','Statistics',period=period,q=q,by_country=by_country,lead_by_country=lead_by_country,opportunity_domains=opportunity_domains,source_summary=source_summary,source_total=source_total,acquisition_quality=acquisition_quality,source_summary_json=source_summary,opportunity_source_pie_json=opportunity_source_pie,lead_source_pie_json=lead_source_pie,contact_source_pie_json=contact_source_pie,opportunity_domain_json=opportunity_domains,opportunity_country_json=by_country,lead_country_json=lead_by_country,discovery_mix_json=discovery_mix,provider_summary_json={k:int(v or 0) for k,v in provider_totals.items()},stats_map_json=stats_map_payload,funnel=funnel,total_downloaded=downloads,provider_totals=provider_totals,rejects=rejects,date_from=request.GET.get('from',''),date_to=request.GET.get('to',''),performance_series=series,performance_totals=performance_totals,performance_metrics=stats_service.METRICS,comparison=comparison,comparison_columns=comparison_columns,chart_payload=chart_payload,period_label=period_label,metric_definitions=definitions,export_query=export_query,stats_updated=timezone.localtime(timezone.now())))




def _stats_map_base_querysets(request):
    period,start,end=_period_bounds(request)
    q=_q(request)
    qs=Opportunity.objects.filter(suppressed=False,user_deleted=False)
    leads=CompanyLead.objects.filter(user_deleted=False)
    contacts=Contact.objects.filter(deleted_at__isnull=True)
    apps=Application.objects.filter(opportunity__user_deleted=False,deleted_at__isnull=True)
    if start:
        qs=qs.filter(created_at__gte=start); leads=leads.filter(created_at__gte=start); contacts=contacts.filter(created_at__gte=start); apps=apps.filter(created_at__gte=start)
    if end:
        qs=qs.filter(created_at__lt=end); leads=leads.filter(created_at__lt=end); contacts=contacts.filter(created_at__lt=end); apps=apps.filter(created_at__lt=end)
    if q:
        qs=qs.filter(Q(title__icontains=q)|Q(company__icontains=q)|Q(source__name__icontains=q)|Q(campaigns__name__icontains=q)).distinct()
        leads=leads.filter(Q(company__icontains=q)|Q(summary__icontains=q)|Q(source__name__icontains=q)|Q(campaigns__name__icontains=q)).distinct()
        contacts=contacts.filter(Q(company__icontains=q)|Q(name__icontains=q)|Q(email__icontains=q)|Q(source__icontains=q)).distinct()
        apps=apps.filter(Q(opportunity__title__icontains=q)|Q(opportunity__company__icontains=q)|Q(opportunity__source__name__icontains=q)|Q(opportunity__campaigns__name__icontains=q)).distinct()
    return qs,leads,contacts,apps,start,end,q


def _stats_map_make_layer_point(kind, row, *, app=None):
    if kind=='opportunities':
        labels=_stats_record_map_locations(row)
        title=f"{row.company} — {row.title}" if row.company else (row.title or f"Opportunity #{row.pk}")
        status=dict(Opportunity.STATUS).get(row.status,row.status or '')
        tooltip=[_stats_map_line('Opportunity', title),_stats_map_line('Location', ', '.join(labels) or 'Unknown'),_stats_map_line('Date added', _stats_map_date(getattr(row,'created_at',None)))]
        point=_stats_map_record_point(row,labels,salt=f"opp:{row.pk}",raw_values=(row.role_location,row.locations,row.country))
        out=[]; _stats_add_record_point(out,labels,salt=f"opp:{row.pk}",title=title,url=reverse('opportunity_detail',args=[row.pk]),target_url=getattr(row,'url',''),tooltip_lines=tooltip,point=point,record_item={'id':row.pk,'label':title,'date':_stats_map_date(getattr(row,'created_at',None)),'url':reverse('opportunity_detail',args=[row.pk])})
        return out[0] if out else {}
    if kind=='hidden_leads':
        labels=_stats_record_map_locations(row)
        title=row.company or f"Hidden Lead #{row.pk}"
        target=getattr(row,'target_url','') or getattr(row,'source_url','') or getattr(row,'search_url','')
        tooltip=[_stats_map_line('Hidden Lead', title),_stats_map_line('Location', ', '.join(labels) or 'Unknown'),_stats_map_line('Date added', _stats_map_date(getattr(row,'created_at',None)))]
        point=_stats_map_record_point(row,labels,salt=f"lead:{row.pk}",raw_values=(row.locations,row.country))
        out=[]; _stats_add_record_point(out,labels,salt=f"lead:{row.pk}",title=title,url=reverse('hidden_lead_detail',args=[row.pk]),target_url=target,tooltip_lines=tooltip,point=point,record_item={'id':row.pk,'label':title,'date':_stats_map_date(getattr(row,'created_at',None)),'url':reverse('hidden_lead_detail',args=[row.pk])})
        return out[0] if out else {}
    if kind=='contacts':
        labels=_stats_record_map_locations(row)
        bits=[x for x in (row.name,row.company,row.email) if x]
        title=' — '.join(bits[:2]) if bits else f"Contact #{row.pk}"
        tooltip=[_stats_map_line('Contact', title),_stats_map_line('Email', row.email),_stats_map_line('Title', row.title),_stats_map_line('Location', ', '.join(labels) or 'Unknown'),_stats_map_line('Date added', _stats_map_date(getattr(row,'created_at',None)))]
        point=_stats_map_record_point(row,labels,salt=f"contact:{row.pk}",raw_values=(row.company_locations,row.company_country))
        edit_url=reverse('contacts')+'?edit='+str(row.pk)
        out=[]; _stats_add_record_point(out,labels,salt=f"contact:{row.pk}",title=title,url=edit_url,target_url=getattr(row,'source_url',''),tooltip_lines=tooltip,point=point,record_item={'id':row.pk,'label':title,'date':_stats_map_date(getattr(row,'created_at',None)),'url':edit_url})
        return out[0] if out else {}
    if kind=='applications' and app is not None:
        opp=row
        labels=_stats_record_map_locations(opp)
        title=f"{opp.company} — {opp.title}" if opp.company else (opp.title or f"Application #{app.pk}")
        status=dict(Application.STATUS).get(app.status,app.status or '')
        tooltip=[_stats_map_line('Applications/Outreach', title),_stats_map_line('Location', ', '.join(labels) or 'Unknown'),_stats_map_line('Status', status),_stats_map_line('Date added', _stats_map_date(getattr(app,'date_added',None) or getattr(app,'created_at',None)))]
        point=_stats_map_record_point(opp,labels,salt=f"app:{app.pk}",raw_values=(opp.role_location,opp.locations,opp.country))
        out=[]; _stats_add_record_point(out,labels,salt=f"app:{app.pk}",title=title,url=reverse('application_edit',args=[app.pk]),target_url=getattr(opp,'url',''),tooltip_lines=tooltip,point=point)
        return out[0] if out else {}
    return {}


def _stats_map_candidate_details(kind, row, *, app=None):
    if kind=='opportunities':
        labels=_stats_record_map_locations(row)
        title=f"{row.company} — {row.title}" if row.company else (row.title or f"Opportunity #{row.pk}")
        details=' | '.join(str(x or '') for x in (row.role_location,row.country,row.locations))
        return labels,title,details,getattr(row,'url','')
    if kind=='hidden_leads':
        labels=_stats_record_map_locations(row)
        title=row.company or f"Hidden Lead #{row.pk}"
        details=' | '.join(str(x or '') for x in (row.country,row.locations))
        return labels,title,details,(getattr(row,'target_url','') or getattr(row,'source_url','') or getattr(row,'search_url',''))
    if kind=='contacts':
        labels=_stats_record_map_locations(row)
        title=' — '.join([x for x in (row.name,row.company,row.email) if x][:2]) or f"Contact #{row.pk}"
        details=' | '.join(str(x or '') for x in (row.company_country,row.company_locations))
        return labels,title,details,getattr(row,'source_url','')
    if kind=='applications' and app is not None:
        labels=_stats_record_map_locations(row)
        title=f"{row.company} — {row.title}" if row.company else (row.title or f"Application #{app.pk}")
        details=' | '.join(str(x or '') for x in (row.role_location,row.country,row.locations))
        return labels,title,details,getattr(row,'url','')
    return [],'', '', ''


def _stats_map_enqueue_candidate(candidates, kind, row, *, app=None, limit=6):
    if len(candidates)>=limit:
        return
    labels,title,details,url=_stats_map_candidate_details(kind,row,app=app)
    fingerprint=_stats_map_evidence_fingerprint(details, *labels)
    if _stats_map_has_recent_unresolved(row, fingerprint):
        return
    if not labels and not details:
        return
    if _stats_map_record_point(row,labels,salt=f'{kind}:{getattr(app or row,"pk","")}',raw_values=(details,)):
        return
    candidates.append({'kind':kind,'row':row,'app':app,'labels':labels,'title':title,'details':details,'url':url,'fingerprint':fingerprint})


@login_required
@require_POST
def stats_map_resolve_async(request):
    """Progressively cache precise map coordinates for the Statistics map.

    The first map paint avoids misleading country/region centroids. This endpoint
    resolves a small batch in the background with the configured AI route and stores
    the coordinates in existing JSON state so later page loads are instant.
    """
    try:
        limit=max(1,min(6,int(request.POST.get('limit') or 4)))
    except Exception:
        limit=4
    qs,leads,contacts,apps,start,end,q=_stats_map_base_querysets(request)
    candidates=[]
    for row in qs.only('pk','title','company','country','locations','role_location','url','status','fit_score','description','raw_search_snippet','ai_state','created_at').order_by('-created_at')[:240]:
        _stats_map_enqueue_candidate(candidates,'opportunities',row,limit=limit)
        if len(candidates)>=limit: break
    if len(candidates)<limit:
        for row in leads.only('pk','company','country','locations','target_url','source_url','search_url','score','summary','match_summary','evidence','ai_state','created_at').order_by('-created_at')[:200]:
            _stats_map_enqueue_candidate(candidates,'hidden_leads',row,limit=limit)
            if len(candidates)>=limit: break
    if len(candidates)<limit:
        for row in contacts.only('pk','email','name','company','title','source_url','company_country','company_locations','company_summary','company_intel','created_at').order_by('-created_at')[:160]:
            _stats_map_enqueue_candidate(candidates,'contacts',row,limit=limit)
            if len(candidates)>=limit: break
    layers={k:[] for k in ('opportunities','hidden_leads','contacts')}
    resolved=0
    for item in candidates:
        row=item['row']
        direct=_stats_direct_location_point(item['details'], *item['labels'])
        if direct:
            geo={**direct,'status':'ok','confidence':85,'reason':'Matched explicit city/state text'}
        else:
            geo,reason=_stats_ai_resolve_map_geo(item['kind'],item['title'],item['labels'],item['details'],item['url'])
            if not geo:
                _stats_map_store_unresolved(row, reason, fingerprint=item.get('fingerprint') or '')
                continue
        _stats_map_store_geo(row, geo, fingerprint=item.get('fingerprint') or '')
        point=_stats_map_make_layer_point(item['kind'],row,app=item.get('app'))
        if point:
            layers[item['kind']].append(point); resolved+=1
    payload_layers=[]
    labels={'opportunities':'Opportunities','hidden_leads':'Hidden Leads','contacts':'Contact'}
    for key,pts in layers.items():
        if pts:
            payload_layers.append({'key':key,'label':labels.get(key,key),'points':pts})
    return JsonResponse({'ok':True,'resolved':resolved,'layers':payload_layers,'remaining':max(0,len(candidates)-resolved),'message':'Map locations updated' if resolved else 'No new precise locations resolved yet'})

def _refresh_hidden_lead_target_status(lead, force=False):
    url=str(lead.target_url or lead.source_url or '').strip()
    if not url.startswith(('http://','https://')):
        return lead
    if not force and lead.target_checked_at and lead.target_checked_at >= timezone.now()-timedelta(hours=24):
        return lead
    try:
        checked=fetch_target(url, lead.company or '', '', timeout=8)
        lead.target_http_status=checked.get('http_status')
        lead.target_checked_at=timezone.now()
        lead.target_check_error=str(checked.get('error') or '')[:500]
        lead.save(update_fields=['target_http_status','target_checked_at','target_check_error','updated_at'])
    except Exception as exc:
        lead.target_checked_at=timezone.now(); lead.target_check_error=str(exc)[:500]
        lead.save(update_fields=['target_checked_at','target_check_error','updated_at'])
    return lead


@login_required
def hidden_lead_detail(request,pk):
    lead=get_object_or_404(CompanyLead.objects.filter(user_deleted=False).prefetch_related('campaigns').select_related('source'),pk=pk)
    repair_lead_campaign_links(lead)
    if not lead.is_read:
        CompanyLead.objects.filter(pk=lead.pk,is_read=False).update(is_read=True)
        lead.is_read=True
    _refresh_hidden_lead_target_status(lead)
    if request.method=='POST':
        action=(request.POST.get('action') or '').strip()
        if action=='status':
            status=(request.POST.get('status') or 'review').strip()
            if status in {'review','pursue','rejected','closed'}: lead.status=status
            lead.note=(request.POST.get('note') or '').strip()
            
            if 'country' in request.POST:
                country=(request.POST.get('country') or '').strip()[:120]
                if not country or country in COUNTRIES: lead.country=country
            if 'fit_level' in request.POST:
                try: lead.score=max(0,min(5,int(request.POST.get('fit_level') or 0)))*20
                except (TypeError,ValueError): pass
            elif 'score' in request.POST:  # backwards-compatible form/API input
                try: lead.score=max(0,min(100,int(request.POST.get('score') or 0)))
                except (TypeError,ValueError): pass
            contact_email=clean_contact_email(request.POST.get('contact_email'))
            if contact_email:
                try: validate_email(contact_email)
                except ValidationError:
                    messages.error(request,'Enter a valid contact email address.')
                    return redirect('hidden_lead_detail',pk=lead.pk)
            lead.contact_email=contact_email
            lead.save(update_fields=['status','note','country','contact_email','score','updated_at'])
            messages.success(request,'Hidden Lead changes saved.')
            return redirect('cold_contact')
        elif action=='draft':
            try:
                app=ensure_outreach_application(lead)
            except RuntimeError as exc:
                messages.info(request,str(exc)); return redirect('recycle_bin')
            active=BackgroundJob.objects.filter(kind='cold_draft',status__in=['queued','running'],result__lead_id=lead.pk).order_by('-created_at').first()
            if active:
                messages.info(request,f'Outreach preparation is already {active.get_status_display().lower()} ({active.progress}%).')
            else:
                job=BackgroundJob.objects.create(kind='cold_draft',label=f'Prepare outreach: {lead.company}'[:300],message='Queued',result={'lead_id':lead.pk,'application_id':app.pk})
                task=cold_draft_job.delay(job.pk,lead.pk,'',''); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
                messages.success(request,format_html('Outreach preparation queued and added to <a href="{}">Applications &amp; Outreach</a>.',reverse('applications')),extra_tags='safe-html')
        elif action=='refresh_summary':
            active=BackgroundJob.objects.filter(kind='summarize',status__in=['queued','running'],result__market_lead_id=lead.pk).order_by('-created_at').first()
            if active:
                messages.info(request,'A Hidden Lead summary refresh is already running.')
            else:
                reserve_attempt(lead,'summary','manual')
                job=BackgroundJob.objects.create(kind='summarize',label=f'Refine Hidden Lead: {lead.company}'[:300],message='Queued',result={'market_lead_id':lead.pk,'phase':'manual'})
                task=market_lead_summary_job.delay(job.pk,lead.pk,'manual'); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
                messages.success(request,'Hidden Lead summary refresh queued.')
        elif action=='company_research':
            ensure_company_research_baseline(lead); reserve_attempt(lead,'company','manual')
            active=BackgroundJob.objects.filter(kind='company_research',status__in=['queued','running'],result__lead_id=lead.pk).order_by('-created_at').first()
            if active:
                messages.info(request,'Company research is already running for this Hidden Lead.')
            else:
                job=BackgroundJob.objects.create(kind='company_research',label=f'Company research: {lead.company}'[:300],message='Queued',result={'lead_id':lead.pk,'hidden_lead':True})
                task=lead_company_research_job.delay(job.pk,lead.pk,'manual'); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
                messages.success(request,'Hidden Lead company research queued.')
        elif action=='translate':
            active=BackgroundJob.objects.filter(kind='translate',status__in=['queued','running'],result__lead_id=lead.pk).order_by('-created_at').first()
            if active:
                messages.info(request,'Translation is already running for this Hidden Lead.')
            else:
                job=BackgroundJob.objects.create(kind='translate',label=f'Translate lead: {lead.company}'[:300],message='Queued',result={'lead_id':lead.pk})
                task=translate_lead_job.delay(job.pk,lead.pk); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id']); messages.success(request,'Lead translation queued.')
        elif action=='blacklist':
            candidate=blacklist_candidate_for_record(lead, allow_domain_only=True)
            label=candidate.get('company','') if candidate.get('valid') else ''
            domain=candidate.get('domain','') if candidate.get('valid') and candidate.get('use_domain') else ''
            if label or domain:
                try:
                    row,created=_upsert_blacklist_rule(domain,label or domain,'Added from Hidden Leads','all',allow_short_label=bool(domain or candidate.get('domain')))
                except ValueError as exc:
                    messages.error(request,str(exc))
                else:
                    try: enforce_active_blacklist()
                    except Exception: pass
                    CompanyLead.objects.filter(pk=lead.pk,user_deleted=False).update(user_deleted=True,deleted_at=timezone.now(),is_read=True)
                    messages.success(request,f'Blacklisted {_blacklist_display_name(row)}; the Hidden Lead was moved to the Recycle Bin.')
                    return redirect('cold_contact')
            else:
                messages.error(request,candidate.get('reason') or 'No usable company name or safe domain to blacklist.')
        return redirect('hidden_lead_detail',pk=lead.pk)

    # Preserve the existing one-shot recovery behavior, but scope it to the detail page
    # instead of opening a modal from the list.
    active_summary=BackgroundJob.objects.filter(kind='summarize',status__in=['queued','running'],result__market_lead_id=lead.pk).order_by('-created_at').first()
    if not usable_result(lead,'summary') and not active_summary:
        allowed,_=reserve_attempt(lead,'summary','recovery')
        if allowed:
            active_summary=BackgroundJob.objects.create(kind='summarize',label=f'Refine Hidden Lead: {lead.company}'[:300],message='Queued recovery',result={'market_lead_id':lead.pk,'phase':'recovery'})
            try:
                task=market_lead_summary_job.delay(active_summary.pk,lead.pk,'recovery'); active_summary.celery_task_id=task.id or ''; active_summary.save(update_fields=['celery_task_id'])
            except Exception as exc:
                active_summary.status='failed'; active_summary.error=str(exc); active_summary.finished_at=timezone.now(); active_summary.save(update_fields=['status','error','finished_at']); active_summary=None
    intel=ensure_company_research_baseline(lead) or {}
    active_company=BackgroundJob.objects.filter(kind='company_research',status__in=['queued','running'],result__lead_id=lead.pk).order_by('-created_at').first()
    if not usable_result(lead,'company') and not active_company:
        allowed,_=reserve_attempt(lead,'company','recovery')
        if allowed:
            active_company=BackgroundJob.objects.create(kind='company_research',label=f'Company research: {lead.company}'[:300],message='Queued recovery',result={'lead_id':lead.pk,'hidden_lead':True,'phase':'recovery'})
            try:
                task=lead_company_research_job.delay(active_company.pk,lead.pk,'recovery'); active_company.celery_task_id=task.id or ''; active_company.save(update_fields=['celery_task_id'])
            except Exception as exc:
                active_company.status='failed'; active_company.error=str(exc); active_company.finished_at=timezone.now(); active_company.save(update_fields=['status','error','finished_at']); active_company=None
    active_draft=BackgroundJob.objects.filter(kind='cold_draft',status__in=['queued','running'],result__lead_id=lead.pk).order_by('-created_at').first()
    active_translate=BackgroundJob.objects.filter(kind='translate',status__in=['queued','running'],result__lead_id=lead.pk).order_by('-created_at').first()
    target_url=lead.target_url or lead.source_url or ''
    source_url=lead.source_url or lead.search_url or target_url
    company_heading=display_company_name(lead.company,target_url) or lead.company or 'Hidden Lead'
    lead_descriptor=''
    if isinstance(intel,dict):
        structured=intel.get('structured') if isinstance(intel.get('structured'),dict) else {}
        for key in ('role_title','role','focus','specialism'):
            candidate=str(structured.get(key) or intel.get(key) or '').strip()
            if candidate and len(candidate)<=100 and candidate.casefold()!=company_heading.casefold():
                lead_descriptor=candidate; break
    detail_heading=(f'{lead_descriptor} · {company_heading}' if lead_descriptor else company_heading)+f' (ID #{lead.pk})'
    return render(request,'portal/hidden_lead_detail.html',ctx(
        request,'cold_contact',detail_heading,
        breadcrumbs=[{'label':'ScoutBox','route':'dashboard'},{'label':'Hidden Leads','route':'cold_contact'},{'label':detail_heading,'route':None}],
        lead=lead,company_intel=intel,target_url=target_url,source_url=source_url,display_source=_lead_source_label(lead),
        source_target_same=_same_url(source_url,target_url),
        active_summary=active_summary,active_company=active_company,active_draft=active_draft,active_translate=active_translate,
    ))


@login_required
def cold_contact_view(request):
    if request.method=='GET' and request.GET.get('company_filter_reset')=='1':
        request.session.pop(_COMPANY_FILTER_SESSION_KEYS['hidden_lead'],None); request.session.modified=True
        return _company_filter_clean_redirect(request)
    # 0.8.87: list views are read-only. Never recycle/dedupe records merely because a user opened a page.
    # List rendering must never delete/recycle records. Disallowed-domain policy is
    # enforced at ingestion and explicit user actions, not as a side effect of opening
    # Hidden Leads; this prevents persisted Local GPU IDs from later turning into 404s.
    if request.method=='POST':
        action=request.POST.get('action')
        if action=='restore_row':
            row_id=(request.POST.get('row_id') or '').strip()
            ok,label=_restore_recycle_item('lead',int(row_id)) if row_id.isdigit() else (False,'Hidden Lead')
            if request.headers.get('X-Requested-With')=='fetch':
                return JsonResponse({'ok':ok,'label':label,'error':'' if ok else 'This Hidden Lead is not in the Recycle Bin.'},status=200 if ok else 404)
            (messages.success if ok else messages.warning)(request,(f'Restored {label}.' if ok else 'This Hidden Lead is not in the Recycle Bin.'))
            return redirect(request.get_full_path())
        # Any row-level Hidden Leads action counts as having reviewed the item.
        # Explicit Mark as Unread remains the final override when the user chooses it.
        if action in ('draft','prepare_application','translate','status','blacklist','company_research','refresh_summary'):
            lead_id=(request.POST.get('lead_id') or '').strip()
            if lead_id.isdigit():
                CompanyLead.objects.filter(pk=lead_id,user_deleted=False).update(is_read=True)
        if action=='filter_selected':
            ids=[x for x in request.POST.getlist('lead_ids') if str(x).isdigit()]
            filter_scope=(request.POST.get('filter_scope') or '').strip().lower()
            filter_all=(request.POST.get('filter_all') or '')=='1' or filter_scope in {'all','local','cloud'}
            filter_local=filter_scope=='local'
            filter_cloud=filter_scope=='cloud'
            if not ids and not filter_all:
                if request.headers.get('X-Requested-With')=='fetch':
                    return JsonResponse({'ok':False,'error':'Select at least one Hidden Lead.'},status=400)
                messages.error(request,'Select at least one Hidden Lead.')
            else:
                try:
                    provider,model,internet_search,_options=_manual_filter_selection(request)
                    cloud_policy_prompt=_manual_filter_cloud_prompt(request,'hidden_lead',provider)
                except ValueError as exc:
                    if request.headers.get('X-Requested-With')=='fetch':
                        return JsonResponse({'ok':False,'error':str(exc)},status=400)
                    messages.error(request,str(exc))
                    return redirect('cold_contact')
                selected=_hidden_lead_re_evaluate_ids(request,local_only=filter_local,cloud_only=filter_cloud) if filter_all else list(CompanyLead.objects.filter(pk__in=ids,user_deleted=False).values_list('pk',flat=True))
                count=len(selected)
                if not count:
                    error=('No matching Local AI assessments are available to re-evaluate.' if filter_local else ('No matching Cloud AI assessments are available to re-evaluate.' if filter_cloud else 'None of the selected Hidden Leads are still active.'))
                    if request.headers.get('X-Requested-With')=='fetch':
                        return JsonResponse({'ok':False,'error':error},status=400)
                    messages.error(request,error)
                else:
                    scope='Local AI' if filter_local else ('Cloud AI' if filter_cloud else ('matching' if filter_all else 'selected'))
                    label=f'Re-evaluate {count} {scope} Hidden Lead{"" if count == 1 else "s"}'
                    result={
                        'selected':count,'lead_ids':selected,'processed':0,'kept':0,'recycled':0,'protected':0,'review':0,'failed':0,
                        'provider':provider,'model':model,'internet_search':internet_search,'scope':('local' if filter_local else ('cloud' if filter_cloud else ('all' if filter_all else 'selected'))),
                        'notify_email':_manual_filter_recipient(request),'cloud_re_evaluation_prompt':cloud_policy_prompt,
                    }
                    job,active=_claim_manual_filter_job('filter_hidden_leads',label,f'Queued · 0/{count} · {provider} · {model}',result)
                    if active:
                        error='A re-evaluation is already running. Stop it from Dashboard > Background Work before starting another re-evaluation.'
                        if request.headers.get('X-Requested-With')=='fetch':
                            return JsonResponse({'ok':False,'error':error,'job_id':active.pk,'active_kind':active.kind,'active_label':active.label},status=409)
                        messages.error(request,error)
                    else:
                        task=hidden_lead_filter_job.delay(job.pk,selected,provider,model,internet_search,cloud_policy_prompt)
                        job.celery_task_id=task.id or ''
                        job.save(update_fields=['celery_task_id'])
                        if request.headers.get('X-Requested-With')=='fetch':
                            return JsonResponse({'ok':True,'count':count,'job_id':job.pk,'message':job.message,'provider':provider,'model':model,'internet_search':internet_search})
                        messages.success(request,f'Hidden Lead re-evaluation queued for {count} {scope} item{"" if count == 1 else "s"}.')
            return redirect('cold_contact')
        elif action=='delete_selected':
            ids=[x for x in request.POST.getlist('lead_ids') if str(x).isdigit()]
            if not ids:
                messages.error(request,'Select at least one Hidden Leads row to delete.')
            else:
                doomed=CompanyLead.objects.filter(pk__in=ids,user_deleted=False)
                count=doomed.count(); now=timezone.now()
                doomed.update(user_deleted=True,deleted_at=now,is_read=True)
                if count: messages.success(request,f'Moved {count} selected Hidden Leads row{"" if count == 1 else "s"} to the Recycle Bin.')
                else: messages.info(request,'The selected Hidden Leads are already in the Recycle Bin or no longer active.')
            return redirect('cold_contact')
        elif action=='blacklist_selected':
            ids=[x for x in request.POST.getlist('lead_ids') if str(x).isdigit()]
            if not ids:
                messages.error(request,'Select at least one Hidden Leads row to blacklist.')
            else:
                rows=list(CompanyLead.objects.filter(pk__in=ids,user_deleted=False))
                blacklisted=0; skipped=0
                for lead in rows:
                    candidate=blacklist_candidate_for_record(lead, allow_domain_only=True)
                    label=candidate.get('company','') if candidate.get('valid') else ''
                    domain=candidate.get('domain','') if candidate.get('valid') and candidate.get('use_domain') else ''
                    if not (label or domain):
                        skipped+=1; continue
                    try:
                        _upsert_blacklist_rule(domain,label or domain,'Added from Hidden Leads','all',allow_short_label=bool(domain or candidate.get('domain')))
                    except ValueError:
                        skipped+=1; continue
                    CompanyLead.objects.filter(pk=lead.pk,user_deleted=False).update(user_deleted=True,deleted_at=timezone.now(),is_read=True); blacklisted+=1
                try: enforce_active_blacklist()
                except Exception: pass
                parts=[]
                if blacklisted: parts.append(f'Blocked {blacklisted} selected Hidden Lead compan{"y" if blacklisted == 1 else "ies"} and moved the matching lead{"" if blacklisted == 1 else "s"} to the Recycle Bin.')
                if skipped: parts.append(f'{skipped} selected lead{"" if skipped == 1 else "s"} could not be safely blacklisted and were ignored.')
                if parts: (messages.success if blacklisted else messages.warning)(request,' '.join(parts))
            return redirect('cold_contact')
        elif action in ('mark_all_read','mark_all_unread'):
            is_read=action=='mark_all_read'
            count=CompanyLead.objects.filter(user_deleted=False).update(is_read=is_read)
            if request.headers.get('X-Requested-With')=='fetch':
                return JsonResponse({'ok':True,'count':count,'is_read':is_read,'all':True})
            messages.success(request,f'Marked all {count} Hidden Leads rows as {"read" if is_read else "unread"}.')
            return redirect('cold_contact')
        elif action=='mark_unread':
            ids=[x for x in request.POST.getlist('lead_ids') if str(x).isdigit()]
            if not ids:
                if request.headers.get('X-Requested-With')=='fetch':
                    return JsonResponse({'ok':False,'error':'Select at least one Hidden Leads row.'},status=400)
                messages.error(request,'Select at least one Hidden Leads row.')
            else:
                count=CompanyLead.objects.filter(pk__in=ids,user_deleted=False).update(is_read=False)
                if request.headers.get('X-Requested-With')=='fetch':
                    return JsonResponse({'ok':True,'count':count,'is_read':False})
                messages.success(request,f'Marked {count} selected Hidden Leads row{"" if count == 1 else "s"} as unread.')
            return redirect('cold_contact')
        elif action=='mark_read':
            ids=[x for x in request.POST.getlist('lead_ids') if str(x).isdigit()]
            single=(request.POST.get('lead_id') or '').strip()
            if single.isdigit() and single not in ids:
                ids.append(single)
            if not ids:
                if request.headers.get('X-Requested-With')=='fetch':
                    return JsonResponse({'ok':False,'error':'Select at least one Hidden Leads row.'},status=400)
                messages.error(request,'Select at least one Hidden Leads row.')
            else:
                count=CompanyLead.objects.filter(pk__in=ids,user_deleted=False).update(is_read=True)
                if request.headers.get('X-Requested-With')=='fetch':
                    return JsonResponse({'ok':True,'count':count,'is_read':True})
                messages.success(request,f'Marked {count} selected Hidden Leads row{"" if count == 1 else "s"} as read.')
            return redirect('cold_contact')
        elif action=='refresh_summary':
            lead=get_object_or_404(CompanyLead,pk=request.POST.get('lead_id'),user_deleted=False)
            active=BackgroundJob.objects.filter(kind='summarize',status__in=['queued','running'],result__market_lead_id=lead.pk).order_by('-created_at').first()
            if active:
                job=active
            else:
                reserve_attempt(lead,'summary','manual')
                job=BackgroundJob.objects.create(kind='summarize',label=f'Refine Hidden Lead: {lead.company}'[:300],message='Queued',result={'market_lead_id':lead.pk,'phase':'manual'})
                task=market_lead_summary_job.delay(job.pk,lead.pk,'manual'); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
            if request.headers.get('X-Requested-With')=='fetch':
                return JsonResponse({'ok':True,'job_id':job.pk})
            messages.success(request,'Hidden Lead summary refresh queued.')
            return redirect(f"{reverse('cold_contact')}?lead={lead.pk}")
        elif action=='company_research':
            lead=get_object_or_404(CompanyLead,pk=request.POST.get('lead_id'),user_deleted=False)
            ensure_company_research_baseline(lead)
            reserve_attempt(lead,'company','manual')
            active=BackgroundJob.objects.filter(kind='company_research',status__in=['queued','running'],result__lead_id=lead.pk).order_by('-created_at').first()
            if active:
                job=active
            else:
                job=BackgroundJob.objects.create(kind='company_research',label=f'Company research: {lead.company}'[:300],message='Queued',result={'lead_id':lead.pk,'hidden_lead':True})
                task=lead_company_research_job.delay(job.pk,lead.pk,'manual'); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
            if request.headers.get('X-Requested-With')=='fetch':
                return JsonResponse({'ok':True,'job_id':job.pk,'intel':lead.company_intel or {}})
            messages.success(request,'Hidden Lead company research queued.')
            return redirect(f"{reverse('cold_contact')}?lead={lead.pk}")
        elif action=='scan':
            if str(ps.discovery_mode or '').lower()=='cloud_web':
                messages.info(request,'Cloud Web collects interesting non-matches as Hidden Leads during campaign research; no local search-engine scan was started.')
            else:
                active=BackgroundJob.objects.filter(kind='hidden_scan',status__in=['queued','running']).first()
                if active: messages.info(request,'A Hidden Leads scan is already running.')
                else:
                    job=BackgroundJob.objects.create(kind='hidden_scan',label='Hidden Leads scan',message='Queued'); task=hidden_market_scan_job.delay(job.pk); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
        elif action=='add':
            company=(request.POST.get('company') or '').strip(); source_url=(request.POST.get('source_url') or '').strip(); country=(request.POST.get('country') or '').strip()[:120]; errors=[]
            if len(company)<2: errors.append('Company / team name must contain at least 2 characters.')
            if country and country not in COUNTRIES: errors.append('Select a valid country.')
            if source_url and not re.match(r'^https?://',source_url,re.I): errors.append('Target URL must start with http:// or https://.')
            if source_url and is_disallowed_adult_url(source_url): errors.append('Adult-content websites cannot be added to Hidden Leads.')
            if errors:
                for e in errors: messages.error(request,e)
            else:
                lead=CompanyLead.objects.create(company=company[:220],country=country,match_summary=request.POST.get('match_summary','').strip(),summary=request.POST.get('match_summary','').strip(),evidence=request.POST.get('evidence','').strip(),source_url=source_url,target_url=source_url,contact_name=request.POST.get('contact_name','')[:200],contact_email=request.POST.get('contact_email',''),score=max(0,min(100,_safe_int(request.POST.get('score'),80))),is_read=True)
                if source_url: _refresh_hidden_lead_target_status(lead,force=True)
                messages.success(request,'Hidden Lead added.')
        elif action=='draft':
            lead=get_object_or_404(CompanyLead,pk=request.POST.get('lead_id'),user_deleted=False)
            # Create the unified record before the AI task starts. This makes Prepare Outreach
            # visible immediately and prevents a slow/failed provider from looking as though
            # the request disappeared. The worker fills the email and then attempts IMAP.
            try:
                app=ensure_outreach_application(lead)
            except RuntimeError as exc:
                messages.info(request,str(exc))
                return redirect('recycle_bin')
            job=BackgroundJob.objects.create(kind='cold_draft',label=f'Prepare outreach: {lead.company}'[:300],message='Queued',result={'lead_id':lead.pk,'application_id':app.pk})
            task=cold_draft_job.delay(job.pk,lead.pk,request.POST.get('provider') or '',request.POST.get('model') or '')
            job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
            messages.success(request,format_html('Outreach preparation queued and added to <a href="{}">Applications &amp; Outreach</a>. The email content will update there when ready; an IMAP Drafts copy is also attempted when email is configured.', reverse('applications')), extra_tags='safe-html')
        elif action=='prepare_application':
            lead=get_object_or_404(CompanyLead,pk=request.POST.get('lead_id'),user_deleted=False)
            target=lead.target_url or lead.source_url or f'https://manual.invalid/market-study-{lead.pk}'
            if Opportunity.objects.filter(user_deleted=True,extracted_facts__market_study_lead_id=lead.pk).exists():
                messages.info(request,'The related opportunity is in the Recycle Bin. Restore it before preparing an application again.')
                return redirect('recycle_bin')
            opp=Opportunity.objects.filter(user_deleted=False,extracted_facts__market_study_lead_id=lead.pk).first()
            if not opp:
                opp=Opportunity.objects.create(title=f'Direct opportunity — {lead.company}',company=lead.company,country=lead.country,url=target,target_url=target,search_url=lead.search_url,source=lead.source,channel='website',contact_email=lead.contact_email,contact_name=lead.contact_name,description='\n\n'.join(x for x in [lead.match_summary,lead.evidence] if x),status='apply',fit_score=lead.score,is_read=True,application_draft_requested_at=timezone.now(),extracted_facts={'market_study_lead_id':lead.pk})
            copy_lead_campaigns_to_opportunity(lead,opp)
            if not opp.application_draft_requested_at:
                opp.application_draft_requested_at=timezone.now(); opp.save(update_fields=['application_draft_requested_at','updated_at'])
            existing=Application.objects.filter(opportunity=opp,deleted_at__isnull=True).first()
            if existing: return redirect('application_edit',pk=existing.pk)
            if Application.objects.filter(opportunity=opp,deleted_at__isnull=False).exists():
                messages.info(request,'The related application/outreach record is in the Recycle Bin. Restore it before preparing it again.')
                return redirect('recycle_bin')
            cv=DocumentAsset.objects.filter(kind='cv',active=True).order_by('-created_at').first(); cover=DocumentAsset.objects.filter(kind='cover',active=True).order_by('-created_at').first()
            job=BackgroundJob.objects.create(kind='prepare',label=f'Prepare application: {lead.company}'[:300],message='Queued',result={'opportunity_id':opp.pk,'lead_id':lead.pk}); task=application_prepare_job.delay(job.pk,opp.pk,cv.pk if cv else None,cover.pk if cover else None); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id']); messages.success(request,format_html('<a href="{}">Application preparation</a> queued from this Hidden Lead.',reverse('applications')),extra_tags='safe-html')
        elif action=='translate':
            lead=get_object_or_404(CompanyLead,pk=request.POST.get('lead_id'),user_deleted=False); job=BackgroundJob.objects.create(kind='translate',label=f'Translate lead: {lead.company}'[:300],message='Queued',result={'lead_id':lead.pk}); task=translate_lead_job.delay(job.pk,lead.pk); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id']); messages.success(request,'Lead translation queued.')
        elif action=='status':
            lead=get_object_or_404(CompanyLead,pk=request.POST.get('lead_id'),user_deleted=False); lead.status=request.POST.get('status','review'); lead.note=request.POST.get('note','').strip();
            if 'country' in request.POST:
                country=request.POST.get('country','').strip()[:120]; lead.country=country if (not country or country in COUNTRIES) else lead.country
            if 'fit_level' in request.POST:
                try: lead.score=max(0,min(5,int(request.POST.get('fit_level') or 0)))*20
                except (TypeError,ValueError): pass
            elif 'score' in request.POST:  # backwards-compatible form/API input
                try: lead.score=max(0,min(100,int(request.POST.get('score') or 0)))
                except (TypeError,ValueError): pass
            if 'contact_email' in request.POST:
                contact_email=clean_contact_email(request.POST.get('contact_email',''))
                if contact_email:
                    try: validate_email(contact_email)
                    except ValidationError:
                        messages.error(request,'Enter a valid contact email address.')
                        return redirect(f"{reverse('cold_contact')}?lead={lead.pk}")
                lead.contact_email=contact_email
            lead.save(update_fields=['status','note','country','contact_email','score','updated_at']); messages.success(request,'Hidden Lead saved.')
        elif action=='blacklist':
            lead=get_object_or_404(CompanyLead,pk=request.POST.get('lead_id'),user_deleted=False)
            candidate=blacklist_candidate_for_record(lead, allow_domain_only=True)
            label=candidate.get('company','') if candidate.get('valid') else ''
            domain=candidate.get('domain','') if candidate.get('valid') and candidate.get('use_domain') else ''
            if label or domain:
                try:
                    row,created=_upsert_blacklist_rule(domain,label or domain,'Added from Hidden Leads','all',allow_short_label=bool(domain or candidate.get('domain')))
                except ValueError as exc:
                    messages.error(request,str(exc))
                else:
                    try: enforce_active_blacklist()
                    except Exception: pass
                    CompanyLead.objects.filter(pk=lead.pk,user_deleted=False).update(user_deleted=True,deleted_at=timezone.now(),is_read=True); messages.success(request,f'Blacklisted {_blacklist_display_name(row)}; the lead was moved to the Recycle Bin.')
            else:
                messages.error(request,f'Could not determine a Company Name of at least {LABEL_BLACKLIST_MIN_CHARS} characters to blacklist.')
        return redirect('cold_contact')
    direct_lead_id=(request.GET.get('lead') or '').strip()
    if direct_lead_id.isdigit() and CompanyLead.objects.filter(pk=int(direct_lead_id),user_deleted=False).exists():
        return redirect('hidden_lead_detail',pk=int(direct_lead_id))
    latest_scan_job=BackgroundJob.objects.filter(kind='hidden_scan',status='completed').order_by('-finished_at','-created_at').first()
    show_deleted=_show_deleted_setting(request,'hidden_leads')
    qs=CompanyLead.objects.all() if show_deleted else CompanyLead.objects.filter(user_deleted=False)
    qs=qs.prefetch_related('campaigns').select_related('origin_campaign').order_by('-created_at','-pk'); q=_q(request)
    # Keep all current Hidden Leads leads. The latest scan remains visible as
    # list-footer metadata and a single details panel, but does not replace the inventory.
    # Hidden Leads is for niche companies/teams, not search engines, social networks or generic job platforms.
    # search_url is discovery provenance and may legitimately be a search-engine URL.
    # It must never disqualify an otherwise valid lead; only the resolved company/source
    # URLs are used for general-platform/documentation filtering.
    # This probe deliberately needs no joined origin_campaign row. Keeping the
    # select_related('origin_campaign') from the list QuerySet while deferring that field
    # with only() raises Django FieldError and made /cold-contact/ return HTTP 500.
    noisy_probe=qs.select_related(None).prefetch_related(None).only('pk','company','target_url','source_url','evidence')
    noisy_ids=[x.pk for x in noisy_probe if is_general_market_company(x.company) or is_general_market_host(x.target_url) or is_general_market_host(x.source_url) or any(is_documentation_like(url,'',x.evidence) for url in (x.target_url,x.source_url) if url)]
    if noisy_ids: qs=qs.exclude(pk__in=noisy_ids)
    if q:
        visible_match=(
            Q(company__icontains=q)|Q(summary__icontains=q)|Q(contact_email__icontains=q)|Q(contact_url__icontains=q)|
            Q(country__icontains=q)|Q(note__icontains=q)|Q(target_url__icontains=q)|Q(source_url__icontains=q)
        )
        qs=qs.filter(visible_match)
    company_size_filter,company_age_filter,contact_method_filter=_company_filter_state(request,'hidden_lead')
    pre_company_qs=qs
    company_filter_active=bool(company_size_filter or company_age_filter or contact_method_filter)
    qs=_apply_company_info_quick_filter(qs,company_size_filter,company_age_filter,contact_method_filter)
    base_qs=qs
    campaign_state=_request_multi_filter_state(request,'campaign',integer=True)
    country_state=_request_multi_filter_state(request,'country',canonicalizer=_canonical_country_name)
    focus_state=_request_multi_filter_state(request,'focus')
    campaign_filter_values=list(campaign_state['values'])
    country_filter_values=list(country_state['values'])
    focus_filter_values=list(focus_state['values'])
    campaign=str(campaign_filter_values[0]) if len(campaign_filter_values)==1 else ''
    country_filter=country_filter_values[0] if len(country_filter_values)==1 else ''
    focus_filter=focus_filter_values[0] if len(focus_filter_values)==1 else ''
    hide_non_200=(request.GET.get('healthy') or '')=='1'
    read_state=(request.GET.get('read') or '').strip().lower()
    sort_mode=(request.GET.get('sort') or '').strip().lower()
    if sort_mode not in {
        'fit_desc','fit_asc','company_asc','company_desc','summary_asc','summary_desc',
        'company_info_asc','company_info_desc','added_asc','added_desc',
    }:
        sort_mode=''

    def _hidden_lead_filtered(exclude=(), base=None):
        filtered=base if base is not None else base_qs
        excluded=set(exclude)
        if 'campaign' not in excluded: filtered=_apply_campaign_filters(filtered,campaign_filter_values,campaign_state['mode'])
        if hide_non_200 and 'healthy' not in excluded: filtered=filtered.filter(target_http_status=200)
        if 'country' not in excluded: filtered=_apply_country_filters(filtered,'country',country_filter_values,country_state['mode'])
        if 'focus' not in excluded: filtered=_apply_focus_filters(filtered, focus_filter_values, focus_state['mode'])
        if read_state=='unread' and 'read' not in excluded: filtered=filtered.filter(is_read=False)
        elif read_state=='read' and 'read' not in excluded: filtered=filtered.filter(is_read=True)
        return filtered

    qs=_hidden_lead_filtered()
    def _hidden_lead_ordered(rows_qs):
        if sort_mode=='fit_desc':
            return rows_qs.order_by('-score','-created_at','-pk')
        if sort_mode=='fit_asc':
            return rows_qs.order_by('score','-created_at','-pk')
        if sort_mode=='company_asc':
            return rows_qs.order_by('company','-created_at','-pk')
        if sort_mode=='company_desc':
            return rows_qs.order_by('-company','-created_at','-pk')
        if sort_mode=='summary_asc':
            return rows_qs.order_by('summary','company','-created_at','-pk')
        if sort_mode=='summary_desc':
            return rows_qs.order_by('-summary','company','-created_at','-pk')
        if sort_mode=='added_asc':
            return rows_qs.order_by('created_at','pk')
        if sort_mode=='added_desc':
            return rows_qs.order_by('-created_at','-pk')
        return rows_qs.order_by('-created_at','-pk')
    def _hidden_lead_visible_ids(rows_qs):
        # Hidden Leads intentionally display one representative row per normalized company.
        # Facets must use the same representative set or their option counts can exceed the
        # number of rows the user can actually see/select.
        seen=set(); ids=[]
        probe=_hidden_lead_ordered(rows_qs).select_related(None).prefetch_related(None).only('pk','company','user_deleted').distinct()
        for row in probe.iterator(chunk_size=500):
            key=(f'deleted:{row.pk}' if show_deleted and row.user_deleted else (re.sub(r'[^a-z0-9]+','',str(row.company or '').lower()) or f'lead{row.pk}'))
            if key in seen: continue
            seen.add(key); ids.append(row.pk)
        return ids
    def _hidden_lead_visible_count(rows_qs):
        return len(_hidden_lead_visible_ids(rows_qs))
    hidden_company_filter_counts={
        'shown':_hidden_lead_visible_count(qs),
        'available':_hidden_lead_visible_count(_hidden_lead_filtered(base=pre_company_qs)),
    }
    qs=_hidden_lead_ordered(qs)
    read_count_base=_hidden_lead_filtered({'read'}).distinct()
    country_count_base=_hidden_lead_filtered({'country'}).distinct()
    focus_count_base=_hidden_lead_filtered({'focus'}).distinct()
    campaign_count_base=_hidden_lead_filtered({'campaign'}).distinct()

    country_visible_ids=_hidden_lead_visible_ids(country_count_base)
    country_counts={}
    for row in CompanyLead.objects.filter(pk__in=country_visible_ids).only('pk','country'):
        for name in location_labels(row.country):
            country_counts[name]=country_counts.get(name,0)+1
    country_options=[{'value':name,'label':name,'count':country_counts[name]} for name in sorted(country_counts,key=str.casefold)]
    country_options=_prune_zero_roundtrip_country_options(country_options,country_count_base,'country',count_fn=_hidden_lead_visible_count)
    country_total=sum(int(x.get('count') or 0) for x in country_options)

    focus_visible_ids=_hidden_lead_visible_ids(focus_count_base)
    focus_options_rows=focus_options(CompanyLead.objects.filter(pk__in=focus_visible_ids))
    focus_total=sum(int(x.get('count') or 0) for x in focus_options_rows)

    campaign_visible_ids=_hidden_lead_visible_ids(campaign_count_base)
    campaign_counts={}
    campaign_rows=CompanyLead.objects.filter(pk__in=campaign_visible_ids).select_related(None).prefetch_related(None).only('pk','origin_campaign_id').prefetch_related('campaigns')
    for row in campaign_rows:
        ids=set()
        if row.origin_campaign_id: ids.add(row.origin_campaign_id)
        ids.update(c.pk for c in row.campaigns.all())
        for cid in ids: campaign_counts[cid]=campaign_counts.get(cid,0)+1
    campaign_options=[]
    for campaign_row in Campaign.objects.filter(deleted_at__isnull=True).order_by('name'):
        campaign_row.entry_count=int(campaign_counts.get(campaign_row.pk,0) or 0)
        if campaign_row.entry_count:
            campaign_options.append(campaign_row)
    campaign_total=len(campaign_visible_ids)
    selected_campaign_ids={int(x) for x in campaign_filter_values if str(x).isdigit() or isinstance(x,int)}
    for campaign_row in campaign_options:
        campaign_row.selected=(campaign_state['mode']!='custom' or campaign_row.pk in selected_campaign_ids)
    selected_countries={str(x) for x in country_filter_values}
    for row in country_options:
        row['selected']=(country_state['mode']!='custom' or str(row.get('value')) in selected_countries)
    selected_focuses={str(x) for x in focus_filter_values}
    for row in focus_options_rows:
        row['selected']=(focus_state['mode']!='custom' or str(row.get('value')) in selected_focuses)
    campaign_filter_label=_multi_filter_label('campaigns',campaign_filter_values,_selected_labels(campaign_options,campaign_filter_values,value_key='pk',label_key='name'),campaign_state['mode'],campaign_total)
    country_filter_label=_multi_filter_label('locations',country_filter_values,_selected_labels(country_options,country_filter_values),country_state['mode'],country_total)
    focus_filter_label=_multi_filter_label('focuses',focus_filter_values,_selected_labels(focus_options_rows,focus_filter_values),focus_state['mode'],focus_total)
    hidden_lead_filter_counts={
        'total':_hidden_lead_visible_count(qs),
        'read_total':_hidden_lead_visible_count(read_count_base),
        'read':_hidden_lead_visible_count(read_count_base.filter(is_read=True)),
        'unread':_hidden_lead_visible_count(read_count_base.filter(is_read=False)),
    }
    # Defensive display-level uniqueness for legacy databases: keep the highest-ranked
    # row for each normalized company even before the cleanup migration has run.
    unique_rows=[]; seen_companies=set()
    for lead in qs:
        key=(f'deleted:{lead.pk}' if show_deleted and lead.user_deleted else (re.sub(r'[^a-z0-9]+','',str(lead.company or '').lower()) or f'lead{lead.pk}'))
        if key in seen_companies: continue
        seen_companies.add(key); unique_rows.append(lead)
    if sort_mode in {'company_info_asc','company_info_desc'}:
        unique_rows.sort(
            key=lambda row:(company_info_sort_value(row),str(row.company or '').casefold(),int(row.pk or 0)),
            reverse=sort_mode=='company_info_desc',
        )
    # Notification deep-links must open the exact lead, not merely land on the list.
    # Put a requested active lead on page 1 even if normal list cleanup/filtering would
    # otherwise place it on another page; the modal is opened client-side after render.
    qs=unique_rows
    # Repair blank/legacy list summaries deterministically only. List-page navigation must
    # never fan out billable cloud work across many rows.
    # Count against the whole active Hidden Leads inventory, not only the current page/filter.
    # Otherwise two companies with the same stored description could escape repair whenever
    # a filter happened to separate them.
    summary_counts=Counter(
        re.sub(r'\s+',' ',str(value or '')).strip().casefold()
        for value in CompanyLead.objects.filter(user_deleted=False).exclude(summary='').values_list('summary',flat=True)
        if str(value or '').strip()
    )
    refreshable=[
        x for x in qs
        if not x.user_deleted and (x.evidence or x.company_intel) and (
            market_summary_needs_refresh(x.summary)
            or summary_counts.get(re.sub(r'\s+',' ',str(x.summary or '')).strip().casefold(),0)>1
        )
    ]
    for lead in refreshable[:250]:
        repaired=preliminary_company_summary(
            lead.company,'',lead.evidence,
            [x.strip() for x in str(lead.match_summary or '').split(',') if x.strip()],
            company_intel=lead.company_intel,
        )
        # If no stronger deterministic company summary is available yet, keep the source
        # summary/evidence intact. The presentation layer strips [SECTION] labels and shows
        # the useful prose until asynchronous refinement produces a better replacement.
        if repaired and repaired != lead.summary:
            lead.summary=repaired
            lead.save(update_fields=['summary','updated_at'])
    queued_summary_ids=set()
    active_summary_ids=set()
    for job in BackgroundJob.objects.filter(kind='summarize',status__in=['queued','running']).order_by('-created_at')[:500]:
        lead_id=(job.result or {}).get('market_lead_id')
        if str(lead_id).isdigit(): active_summary_ids.add(int(lead_id))
    active_summary_ids.update(queued_summary_ids)
    for lead in qs:
        lead.summary_in_progress=lead.pk in active_summary_ids
        lead.display_company=display_company_name(lead.company, lead.target_url or lead.source_url) or lead.company
        lead.display_source=_lead_source_label(lead)
        lead.campaign_display=', '.join(c.name for c in lead.campaigns.all())
    if request.GET.get('export')=='1':
        return _xlsx(
            'hidden_leads.xlsx',
            ['Added','Company','Focus','Location','Summary','Contact Name','Contact','Fit','Status','Read status','Search URL','Target URL',
             'Company Info','Note','URL HTTP Status','Origin Campaign','Campaigns Seen'],
            [(
                x.created_at,x.company,x.focus,x.country,hidden_lead_list_summary(x),x.contact_name,x.contact_email or x.contact_url,
                x.score,x.status,'Read' if x.is_read else 'New',x.search_url,x.target_url or x.source_url,
                company_info_compact(x),x.note,x.target_http_status if x.target_http_status is not None else '',x.origin_campaign.name if x.origin_campaign else '',
                ', '.join(c.name for c in x.campaigns.all()),
            ) for x in qs[:10000]],
        )
    page,per_page=_page(request,qs,default=50); ps=PortalSettings.objects.get_or_create(pk=1)[0]
    active_company_jobs={}
    for job in BackgroundJob.objects.filter(kind='company_research',status__in=['queued','running']).order_by('-created_at')[:500]:
        lead_id=(job.result or {}).get('lead_id')
        if str(lead_id).isdigit() and int(lead_id) not in active_company_jobs:
            active_company_jobs[int(lead_id)]=job.pk
    for lead in page:
        _repair_known_contact_email(lead)
        intel=ensure_company_research_baseline(lead) or {}
        lead.company_intel_display={
            'confidence':intel.get('confidence',0), 'facts':intel.get('facts') or [],
            'sources':[{'provider':x.get('provider',''),'title':x.get('title',''),'url':x.get('url','')} for x in (intel.get('sources') or [])[:12] if isinstance(x,dict)],
            'errors':intel.get('errors') or [], 'status':intel.get('status',''), 'updated_at':intel.get('updated_at',''),
        }
        lead.company_research_job_id=active_company_jobs.get(lead.pk)
    active_hidden_lead_filter=BackgroundJob.objects.filter(kind='filter_hidden_leads',status__in=['queued','running']).order_by('-created_at').first()
    if active_hidden_lead_filter:
        active_hidden_lead_filter=_canonicalize_hidden_lead_reassessment_job(active_hidden_lead_filter)
    active_manual_filter=_active_manual_filter()
    # 0.11.29: show every meaningful stored Hidden Lead re-evaluation DB row in the history
    # dialog while still canonicalizing the currently active automatic pass.
    hidden_lead_filter_history=_decorate_manual_filter_item_dates(_hidden_lead_filter_history_for_view(active_hidden_lead_filter),'lead')
    hidden_lead_filter_history_label=_manual_filter_history_label(hidden_lead_filter_history,'Hidden Lead')
    completed_hidden_lead_filter_history=[x for x in hidden_lead_filter_history if str(x.status or '').lower() not in {'queued','running'}]
    latest_hidden_lead_filter=_latest_meaningful_manual_filter(completed_hidden_lead_filter_history)
    manual_filter_ai=_manual_filter_ai_options()
    return render(request,'portal/cold_contact.html',ctx(request,'cold_contact','Hidden Leads',leads=page,page_obj=page,per_page=per_page,q=q,read_state=read_state,campaign_filter=campaign,campaign_options=campaign_options,campaign_filter_label=campaign_filter_label,campaign_filter_mode=campaign_state['mode'],country_filter=country_filter,country_options=country_options,country_total=country_total,country_filter_label=country_filter_label,country_filter_mode=country_state['mode'],focus_filter=focus_filter,focus_options=focus_options_rows,focus_total=focus_total,focus_filter_label=focus_filter_label,focus_filter_mode=focus_state['mode'],campaign_total=campaign_total,hide_non_200=hide_non_200,last_scanned=(latest_scan_job.finished_at if latest_scan_job else ps.last_hidden_scan),latest_scan_job=latest_scan_job,model_choices=_model_choices(),jobs=BackgroundJob.objects.filter(kind__in=['cold_draft','translate','prepare','summarize','company_research','filter_hidden_leads'])[:30],hidden_lead_filter_counts=hidden_lead_filter_counts,active_hidden_lead_filter=active_hidden_lead_filter,active_manual_filter=active_manual_filter,latest_hidden_lead_filter=latest_hidden_lead_filter,hidden_lead_filter_history=hidden_lead_filter_history,hidden_lead_filter_history_label=hidden_lead_filter_history_label,manual_filter_ai=manual_filter_ai,sort_mode=sort_mode,company_size_filter=company_size_filter,company_age_filter=company_age_filter,contact_method_filter=contact_method_filter,contact_method_filter_options=[('web','Web'),('email','Email'),('ats','ATS'),('forum','Forum'),('unknown','Unknown / Others')],company_filter_active=company_filter_active,company_filter_counts=hidden_company_filter_counts,company_filter_reset_query=_company_filter_reset_query(request),company_size_filter_options=[('lt10','0-10'),('lt50','10-50'),('lt100','50-100'),('lt500','100-500'),('lt1000','500-1,000'),('gte1000','1,000+'),('unknown','Unknown / Others')],company_age_filter_options=[('lt1','0-1 year'),('lt2','1-2 years'),('lt5','2-5 years'),('lt10','5-10 years'),('gte10','10+ years'),('unknown','Unknown / Others')],show_deleted=show_deleted))


def _public_search_repeat_url(provider, query):
    """Return a public browser-search URL for a logged provider/query."""
    q=str(query or '').strip()
    if not q:
        return ''
    name=str(provider or '').strip().lower()
    encoded=urlencode({'q':q})
    if 'naver' in name:
        return 'https://search.naver.com/search.naver?'+urlencode({'query':q})
    if 'yandex' in name:
        return 'https://yandex.com/search/?'+urlencode({'text':q})
    if 'yahoo' in name:
        return 'https://search.yahoo.com/search?'+urlencode({'p':q})
    if 'startpage' in name:
        return 'https://www.startpage.com/sp/search?'+urlencode({'query':q})
    if 'brave' in name:
        return 'https://search.brave.com/search?'+encoded
    if 'duck' in name:
        return 'https://duckduckgo.com/?'+encoded
    if 'bing' in name:
        return 'https://www.bing.com/search?'+encoded
    if 'ecosia' in name:
        return 'https://www.ecosia.org/search?'+encoded
    if 'mojeek' in name:
        return 'https://www.mojeek.com/search?'+encoded
    if 'baidu' in name:
        return 'https://www.baidu.com/s?'+urlencode({'wd':q})
    return 'https://www.google.com/search?'+encoded


@login_required
def search_log_view(request):
    # Search Activity shows one parsed outcome for each Direct Search/forum adapter
    # invocation, plus direct employer/page lookups, ordinary search-engine queries and
    # cloud-native discovery rows. Raw per-HTTP fresh_source metrics stay in telemetry so
    # successful adapters do not appear as repeated zero-result searches.
    base=UsageMetric.objects.filter(
        Q(stage='query')
        | Q(category='fresh_source_result')
        | Q(category='direct_site',requests__gt=0)
        | Q(category__in=['cloud_custom_domain','forum_search','forum_source'])
    ).annotate(
        result_sort=Case(
            When(errors__gt=0,then=Value(0)),
            default=Case(
                When(category='direct_site',then=Coalesce('pages',Value(0))),
                default=Coalesce(Cast('metadata__results',IntegerField()),Coalesce('pages',Value(0))),
                output_field=IntegerField(),
            ),
            output_field=IntegerField(),
        )
    )
    adapter_bookkeeping=Q(category='search',stage='query') & Q(metadata__url__in=['',None]) & Q(metadata__query__in=['lever','hn_whoishiring'])
    base=base.exclude(adapter_bookkeeping).exclude(category='discovery_market')
    # Aggregate/query-plan telemetry is useful for diagnostics but is not a provider
    # request. Search Activity only renders rows with an actual query or direct URL.
    nonempty_query=Q(metadata__query__isnull=False) & ~Q(metadata__query='')
    nonempty_url=Q(metadata__url__isnull=False) & ~Q(metadata__url='')
    url_list=Q(metadata__urls__isnull=False) & ~Q(metadata__urls=[])
    base=base.filter(nonempty_query|nonempty_url|url_list)
    date_period,date_start,date_end,date_from,date_to=_log_date_bounds(request)
    base=_apply_log_date_bounds(base,'at',date_start,date_end)
    q=_q(request)
    outcome_state=_selected_filter_values(request,'status',('results','zero','error'))
    status_values=list(outcome_state['values'])
    status=status_values[0] if len(status_values)==1 else ''

    provider_type_order=('search_engine','direct_search','forum')
    valid_provider_types=set(provider_type_order)
    provider_type_mode=(request.GET.get('provider_type_mode') or '').strip().lower()
    provider_type_aliases={
        'search':'search_engine','search_engine':'search_engine','search-engine':'search_engine','search engine':'search_engine',
        'direct':'direct_search','direct_search':'direct_search','direct-search':'direct_search','direct search':'direct_search',
        'forum':'forum','forums':'forum',
    }
    raw_provider_types=[]
    for x in request.GET.getlist('provider_type'):
        raw=str(x or '').strip().lower().replace('+',' ')
        x=provider_type_aliases.get(raw,raw)
        if x in valid_provider_types and x not in raw_provider_types:
            raw_provider_types.append(x)
    provider_type_custom=provider_type_mode=='custom'
    provider_type_all=(provider_type_mode=='all') or (not provider_type_custom and not raw_provider_types) or (set(raw_provider_types)==valid_provider_types)
    provider_type_none=provider_type_custom and not raw_provider_types
    provider_types=list(provider_type_order) if provider_type_all else raw_provider_types

    provider_mode=(request.GET.get('provider_mode') or '').strip().lower()
    raw_providers=[]
    for x in request.GET.getlist('provider'):
        x=str(x or '').strip()
        if x and x not in raw_providers:
            raw_providers.append(x)
    provider_custom=provider_mode=='custom'
    provider_all=(provider_mode=='all') or (not provider_custom and not raw_providers)
    provider_none=provider_custom and not raw_providers
    providers_selected=[] if provider_all else raw_providers

    market_mode=(request.GET.get('market_mode') or '').strip().lower()
    raw_markets=[]
    for x in request.GET.getlist('market'):
        x=' '.join(str(x or '').split())[:80]
        if x and x not in raw_markets:
            raw_markets.append(x)
    market_custom=market_mode=='custom'
    market_all=(market_mode=='all') or (not market_custom and not raw_markets)
    market_none=market_custom and not raw_markets
    markets_selected=[] if market_all else raw_markets

    query_language_mode=(request.GET.get('query_language_mode') or '').strip().lower()
    raw_query_languages=[]
    for x in request.GET.getlist('query_language'):
        x=' '.join(str(x or '').split()).lower()[:24]
        if x and x not in raw_query_languages:
            raw_query_languages.append(x)
    query_language_custom=query_language_mode=='custom'
    query_language_all=(query_language_mode=='all') or (not query_language_custom and not raw_query_languages)
    query_language_none=query_language_custom and not raw_query_languages
    query_languages_selected=[] if query_language_all else raw_query_languages

    if q:
        # Match the same text the Query column renders, including direct-search
        # stage/prefix labels such as company_career_direct_search and
        # employer_role_lookup.
        base=base.filter(
            Q(provider__icontains=q)|Q(stage__icontains=q)|Q(category__icontains=q)|
            Q(metadata__query__icontains=q)|Q(metadata__url__icontains=q)|
            Q(metadata__urls__icontains=q)|Q(metadata__adapter__icontains=q)|
            Q(metadata__provider_locale__icontains=q)|Q(metadata__market__icontains=q)|Q(metadata__market_code__icontains=q)|
            Q(metadata__query_language__icontains=q)|Q(metadata__query_language_label__icontains=q)|
            Q(metadata__domain__icontains=q)|Q(metadata__error__icontains=q)|
            Q(metadata__source_category__icontains=q)|Q(metadata__acquisition_path__icontains=q)
        )

    source_type_by_name={}
    source_type_by_name_cf={}
    try:
        source_type_by_name={name:stype for name,stype in SearchSource.objects.values_list('name','source_type')}
        source_type_by_name_cf={str(name or '').casefold():stype for name,stype in source_type_by_name.items()}
    except Exception:
        source_type_by_name={}; source_type_by_name_cf={}
    active_search_names=set(ACTIVE_PROVIDER_NAMES)
    forum_names={n for n,t in source_type_by_name.items() if str(t or '').lower()=='forum'}
    search_categories={'search','search_corroboration','company_research','hidden_market','employer_role_lookup','facebook_watch_upgrade'}
    direct_categories={'fresh_source_result','direct_site','company_career_discovery','followup_discovery'}

    def provider_names_q(names):
        qobj=Q(pk__in=[])
        for name in sorted({str(n or '').strip() for n in names if str(n or '').strip()}):
            qobj |= Q(provider__iexact=name)
        return qobj
    forum_q=(provider_names_q(forum_names)|Q(stage='forum_generic')|Q(category__in=['forum_search','forum_source'])|Q(metadata__source_category='forum')|Q(metadata__source_category_override='forum')|Q(metadata__forum=True)|Q(metadata__acquisition_path__icontains='Forum'))
    search_q=(provider_names_q(active_search_names)|Q(provider__iexact='Search engines')|Q(provider__iexact='Local search engines')|(Q(stage='query') & Q(category__in=search_categories)))
    direct_q=(Q(category__in=list(direct_categories))|(~forum_q & ~search_q))

    def type_q_for(kind):
        if kind=='forum': return forum_q
        if kind=='search_engine': return search_q & ~forum_q
        if kind=='direct_search': return direct_q & ~forum_q & ~search_q
        return Q(pk__in=[])
    def combined_type_q(kinds):
        qobj=Q(pk__in=[])
        for kind in kinds:
            qobj |= type_q_for(kind)
        return qobj
    def provider_type_for(provider_name='', category='', stage='', meta=None):
        meta=meta if isinstance(meta,dict) else {}
        provider_name=str(provider_name or '')
        low_name=provider_name.casefold()
        stype=str(source_type_by_name.get(provider_name,source_type_by_name_cf.get(provider_name.casefold(),'')) or '').lower()
        acq=str(meta.get('acquisition_path') or '').lower()
        source_cat=str(meta.get('source_category') or meta.get('source_category_override') or '').lower()
        # Search Activity provider type is based on the provider/source owner that
        # appears in the Provider column. A Bing row remains a Search Engine row
        # even when the query is forum-targeted; dedicated forum browsing rows use
        # the Forum source owner. Cloud-only requests are not exposed as a provider
        # type in Search Activity and are grouped with Direct Search if present.
        if provider_name in active_search_names or provider_name.casefold() in {x.casefold() for x in active_search_names} or stype in {'search_engine','regional_search'} or low_name in {'search engines','local search engines'}:
            return 'search_engine'
        if stype=='forum' or stage=='forum_generic' or source_cat=='forum' or meta.get('forum') is True or category in {'forum_source'} or 'forum browsing' in acq:
            return 'forum'
        return 'direct_search'
    provider_type_labels={'search_engine':'Search Engine','direct_search':'Direct Search','forum':'Forum'}
    provider_type_icons={'search_engine':'source_search','direct_search':'source_direct','forum':'forum'}

    def provider_label(name):
        raw=' '.join(str(name or '').split())
        low=raw.casefold()
        generic_direct=low in {'direct http','direct','http direct','direct search'} or bool(re.fullmatch(r'(?:direct http|http direct|direct)\s*[·|/-]\s*direct',low))
        return 'Direct Search' if generic_direct else raw

    # Provider type filtering/counts must classify concrete UsageMetric rows, not just
    # provider names. A provider can legitimately appear under more than one route
    # over time (for example Bing rows from ordinary search plus forum-discovery
    # rows), and older rows may have category/stage metadata that does not fit a
    # single SQL-only Q branch. The UI row renderer already classifies using
    # provider+category+stage+metadata; use that same logic for filtering and counts.
    def _status_q_for(value):
        if value=='error': return Q(errors__gt=0)
        if value=='zero': return Q(errors=0,result_sort=0)
        if value=='results': return Q(errors=0,result_sort__gt=0)
        return Q(pk__in=[])

    def _status_filtered(qs):
        if outcome_state['mode']=='custom' and not status_values:
            return qs.none()
        if outcome_state['mode']=='custom':
            qobj=Q(pk__in=[])
            for value in status_values:
                qobj |= _status_q_for(value)
            return qs.filter(qobj)
        return qs

    def _provider_filtered(qs):
        if provider_none:
            return qs.none()
        if not provider_all and providers_selected:
            return qs.filter(provider__in=providers_selected)
        return qs

    def _market_q_for(value):
        value=str(value or '').strip().lower()
        if value=='__unknown__':
            return (Q(metadata__market_code__isnull=True)|Q(metadata__market_code='')) & (Q(metadata__market__isnull=True)|Q(metadata__market=''))
        market=MARKET_BY_CODE.get(value)
        qobj=Q(metadata__market_code__iexact=value)
        if market:
            qobj |= Q(metadata__market__iexact=market.name)
        return qobj

    def _market_filtered(qs):
        if market_none:
            return qs.none()
        if not market_all and markets_selected:
            qobj=Q(pk__in=[])
            for value in markets_selected:
                qobj |= _market_q_for(value)
            return qs.filter(qobj)
        return qs

    # Use the complete normalization catalogue, not only optional multilingual
    # choices. Market-native languages such as Azerbaijani/Khmer must be recognized
    # by the Unknown predicate as well as by the display normalizer.
    language_name_by_code=dict(QUERY_LANGUAGE_NAME_BY_CODE)

    def _query_language_known_q():
        """Rows with an explicit, recognized semantic query-language value."""
        qobj=Q(pk__in=[])
        for code,label in language_name_by_code.items():
            qobj |= Q(metadata__query_language__iexact=code)
            qobj |= Q(metadata__query_language__iexact=label)
            qobj |= Q(metadata__query_language_label__iexact=label)
            qobj |= Q(metadata__multilingual_language__iexact=label)
        return qobj

    def _query_language_explicit_q():
        # Do not treat legacy rows that simply predate query-language telemetry as
        # "Unknown". Unknown means ScoutBox actually recorded a language value but
        # could not normalize it. Historical unrecorded rows remain visible in the
        # all-languages view but are excluded from language-specific filters/facets.
        return (
            (Q(metadata__query_language__isnull=False) & ~Q(metadata__query_language=''))
            | (Q(metadata__query_language_label__isnull=False) & ~Q(metadata__query_language_label=''))
            | (Q(metadata__multilingual_language__isnull=False) & ~Q(metadata__multilingual_language=''))
        )

    def _query_language_q_for(value):
        value=str(value or '').strip().lower()
        if value=='__unknown__':
            return _query_language_explicit_q() & ~_query_language_known_q()
        label=language_name_by_code.get(value,query_language_label(value))
        qobj=Q(metadata__query_language__iexact=value)
        if label:
            # Include the full-name form written by early 0.11.148-0.11.150 rows as
            # well as the normalized code, so fixing display does not break filters.
            qobj |= Q(metadata__query_language__iexact=label)
            qobj |= Q(metadata__query_language_label__iexact=label)
            qobj |= Q(metadata__multilingual_language__iexact=label)
        return qobj

    def _query_language_filtered(qs):
        if query_language_none:
            return qs.none()
        if not query_language_all and query_languages_selected:
            qobj=Q(pk__in=[])
            for value in query_languages_selected:
                qobj |= _query_language_q_for(value)
            return qs.filter(qobj)
        return qs

    def _classified_rows(qs):
        fields=('pk','provider','category','stage','metadata')
        for pk,provider,category,stage,meta in qs.values_list(*fields).iterator(chunk_size=5000):
            yield pk,provider,provider_type_for(provider,category,stage,meta if isinstance(meta,dict) else {})

    def _pks_for_types(qs, allowed_types):
        allowed_types=set(allowed_types or [])
        if not allowed_types:
            return []
        return [pk for pk,provider,kind in _classified_rows(qs) if kind in allowed_types]

    if provider_type_none:
        base_filtered_by_type=base.none()
    elif provider_type_all:
        base_filtered_by_type=base
    else:
        base_filtered_by_type=base.filter(pk__in=_pks_for_types(base,provider_types))

    # Faceted counts: each selector respects the other active filters while ignoring itself.
    provider_type_count_qs=_query_language_filtered(_market_filtered(_status_filtered(_provider_filtered(base))))
    provider_type_counts={kind:0 for kind in provider_type_order}
    for pk,provider,kind in _classified_rows(provider_type_count_qs):
        if kind in provider_type_counts:
            provider_type_counts[kind]+=1
    provider_type_total=sum(provider_type_counts.values())
    provider_type_options=[{'value':kind,'label':provider_type_labels[kind],'count':provider_type_counts[kind],'icon':provider_type_icons[kind],'selected':kind in provider_types} for kind in provider_type_order]
    if provider_type_none:
        selected_provider_type_label='None'
    elif provider_type_all:
        selected_provider_type_label='All Provider Types'
    else:
        selected_provider_type_label=f'Provider Types: {len(provider_types)}/{len(provider_type_order)} selected'

    provider_count_qs=_query_language_filtered(_market_filtered(_status_filtered(base_filtered_by_type)))
    provider_counts={row['provider']:int(row['count']) for row in provider_count_qs.exclude(provider='').values('provider').annotate(count=Count('id')).order_by('provider')}
    provider_options=[]
    for name,count in provider_counts.items():
        ptype=provider_type_for(name)
        selected=provider_all or (name in providers_selected)
        provider_options.append({'value':name,'label':provider_label(name),'count':count,'type':ptype,'icon':provider_type_icons.get(ptype,'source_direct'),'type_label':provider_type_labels.get(ptype,'Direct Search'),'selected':selected})
    provider_total=sum(int(x.get('count') or 0) for x in provider_options)
    if provider_none:
        selected_provider_label='None'
    elif provider_all:
        selected_provider_label='All Providers'
    else:
        selected_provider_count=sum(1 for x in provider_options if x.get('selected')) or len(providers_selected)
        selected_provider_label=f'Providers: {selected_provider_count}/{max(1,len(provider_options))} selected'

    market_count_qs=_query_language_filtered(_status_filtered(_provider_filtered(base_filtered_by_type)))
    market_counts={}; market_names={}
    for row in market_count_qs.values('metadata__market_code','metadata__market').annotate(count=Count('id')).order_by():
        code=str(row.get('metadata__market_code') or '').strip().lower()
        name=' '.join(str(row.get('metadata__market') or '').split()).strip()
        if not code and name:
            match=next((m for m in MARKETS if m.name.casefold()==name.casefold()),None)
            code=match.code if match else ''
        key=code or '__unknown__'
        market_counts[key]=market_counts.get(key,0)+int(row.get('count') or 0)
        if key!='__unknown__':
            market_names[key]=(MARKET_BY_CODE.get(key).name if MARKET_BY_CODE.get(key) else name or key.upper())
    market_options=[]
    for key in sorted(market_counts,key=lambda value:(value=='__unknown__',(market_names.get(value) or 'Unknown').casefold())):
        label='Unknown' if key=='__unknown__' else market_names.get(key,key.upper())
        market_options.append({'value':key,'label':label,'code':'' if key=='__unknown__' else key.upper(),'count':market_counts[key],'selected':market_all or key in markets_selected})
    market_total=sum(market_counts.values())
    if market_none:
        selected_market_label='None'
    elif market_all:
        selected_market_label='All Markets'
    else:
        selected_market_count=sum(1 for x in market_options if x.get('selected')) or len(markets_selected)
        selected_market_label=f'Markets: {selected_market_count}/{max(1,len(market_options))} selected'

    language_count_qs=_market_filtered(_status_filtered(_provider_filtered(base_filtered_by_type)))
    language_counts={}; language_labels={}; query_language_unrecorded_total=0
    for row in language_count_qs.values('metadata__query_language','metadata__query_language_label','metadata__multilingual_language').annotate(count=Count('id')).order_by():
        explicit_raw=' '.join(str(row.get('metadata__query_language') or '').split()).strip()
        explicit_label=' '.join(str(row.get('metadata__query_language_label') or '').split()).strip()
        historical=' '.join(str(row.get('metadata__multilingual_language') or '').split()).strip()
        count=int(row.get('count') or 0)
        # Normalize legacy 0.11.148-0.11.150 rows too. Those releases could persist
        # a full language name such as ``azerbaijani`` in query_language when the
        # market-native language was not in the original compact mapping.
        state,code,label=query_language_identity(explicit_raw,explicit_label,historical)
        if state=='known':
            key=code
            label=label or language_name_by_code.get(key) or query_language_label(key) or key.upper()
        elif state=='unknown':
            # True unknown: telemetry contains a language value, but ScoutBox cannot
            # map it to a supported code. Give this its own visible '?' code.
            key='__unknown__'; label='Unknown'
        else:
            # Before 0.11.148 Search Activity did not persist semantic query-language
            # metadata at all. Those rows are unrecorded legacy telemetry, not evidence
            # that the language itself was unknown. Excluding them from this facet fixes
            # the misleading hundreds-of-thousands Unknown bucket while preserving the
            # rows in the normal All Query Languages view.
            query_language_unrecorded_total+=count
            continue
        language_counts[key]=language_counts.get(key,0)+count
        language_labels[key]=label
    query_language_options=[]
    for key in sorted(language_counts,key=lambda value:(value=='__unknown__',(language_labels.get(value) or 'Unknown').casefold())):
        query_language_options.append({'value':key,'label':language_labels.get(key,'Unknown'),'code':'?' if key=='__unknown__' else key.upper(),'count':language_counts[key],'selected':query_language_all or key in query_languages_selected})
    query_language_total=sum(language_counts.values())
    if query_language_none:
        selected_query_language_label='None'
    elif query_language_all:
        selected_query_language_label='All Query Languages'
    else:
        selected_query_language_count=sum(1 for x in query_language_options if x.get('selected')) or len(query_languages_selected)
        selected_query_language_label=f'Languages: {selected_query_language_count}/{max(1,len(query_language_options))} selected'

    outcome_count_qs=_query_language_filtered(_market_filtered(base_filtered_by_type))
    if provider_none:
        outcome_count_qs=outcome_count_qs.none()
    elif not provider_all and providers_selected:
        outcome_count_qs=outcome_count_qs.filter(provider__in=providers_selected)
    outcome_counts={
        'results': outcome_count_qs.filter(errors=0,result_sort__gt=0).count(),
        'zero': outcome_count_qs.filter(errors=0,result_sort=0).count(),
        'error': outcome_count_qs.filter(errors__gt=0).count(),
    }
    outcome_total=sum(outcome_counts.values())

    qs=base_filtered_by_type
    if provider_none:
        qs=qs.none()
    elif not provider_all and providers_selected:
        qs=qs.filter(provider__in=providers_selected)
    qs=_market_filtered(qs)
    qs=_query_language_filtered(qs)
    qs=_status_filtered(qs)

    sort_key=(request.GET.get('sort') or 'date').strip().lower(); sort_dir=(request.GET.get('dir') or 'desc').strip().lower()
    if sort_dir not in ('asc','desc'): sort_dir='desc'
    sort_map={
        'date':['at'], 'provider':['provider'], 'query':['metadata__query'],
        'result':['result_sort'], 'latency':['latency_ms'], 'downloaded':['bytes_downloaded'],
    }
    if sort_key not in sort_map: sort_key='date'
    prefix='-' if sort_dir=='desc' else ''
    qs=qs.order_by(*[(prefix+field) for field in sort_map[sort_key]],'-pk' if sort_dir=='desc' else 'pk')

    def direct_query_parts(row):
        meta=row.metadata if isinstance(row.metadata,dict) else {}
        url=str(meta.get('url') or '').strip()
        adapter=str(meta.get('adapter') or row.stage or '').strip()
        qtext=str(meta.get('query') or '').strip()
        urls=meta.get('urls') if isinstance(meta.get('urls'),list) else []
        if meta.get('forum') is True or str(meta.get('source_category') or '').lower()=='forum':
            prefix='Forum browse'
            if qtext:
                prefix+=' · '+qtext[:120]
            if len(urls)>1:
                prefix+=' · '+str(len(urls))+' forum URLs checked'
            return prefix,(url or (str(urls[0]) if urls else ''))
        prefix='' if row.category=='fresh_source_result' else adapter
        if qtext and row.category=='fresh_source_result':
            prefix=(adapter+' · '+qtext[:120]).strip(' ·')
        if not url:
            return adapter,''
        return prefix,url

    if request.GET.get('export')=='1':
        export_rows=[]
        for x in qs[:50000]:
            meta=x.metadata or {}
            direct=x.category in {'fresh_source_result','direct_site'}
            if direct:
                qprefix,qurl=direct_query_parts(x)
                query=' · '.join(part for part in (qprefix,qurl) if part)
            else:
                query=str(meta.get('query') or meta.get('domain') or '')
            ptype=provider_type_for(x.provider,x.category,x.stage,meta)
            results=int(getattr(x,'result_sort',0) or 0)
            region=_usage_region_context(meta) or {}
            language_state,language_code,language_label=query_language_identity(
                meta.get('query_language'),meta.get('query_language_label'),meta.get('multilingual_language')
            )
            language_display=(f'{language_label} ({language_code})' if language_state=='known' else ('Unknown (?)' if language_state=='unknown' else 'Not recorded'))
            market_display=str(meta.get('market') or '').strip() or 'Unknown'
            export_rows.append((provider_type_labels.get(ptype,ptype),provider_label(x.provider),market_display,language_display,str(meta.get('provider_locale') or region.get('setting','')),query,'Error' if x.errors else ('Results' if results>0 else 'Zero results'),results,x.latency_ms,x.bytes_downloaded,meta.get('error',''),x.at))
        return _xlsx('search_engine_log.xlsx',['Provider Type','Provider','Market','Query Language','Provider Locale','Query','Status','Results','Latency ms','Size bytes','Error','Date'],export_rows)
    try: per_page=int(request.GET.get('per_page') or 50)
    except Exception: per_page=50
    if per_page not in (25,50,100): per_page=50
    page=Paginator(qs,per_page).get_page(request.GET.get('page') or 1)
    for row in page.object_list:
        meta=row.metadata or {}
        row.is_cloud_web=False
        row.is_direct=(row.category in {'fresh_source_result','direct_site'})
        row.direct_prefix=''; row.direct_url=''
        if row.is_direct:
            row.direct_prefix,row.direct_url=direct_query_parts(row)
            row.query_text=' · '.join(part for part in (row.direct_prefix,row.direct_url) if part)
        else:
            row.query_text=str(meta.get('query') or meta.get('domain') or '')
        row.result_count=int(getattr(row,'result_sort',0) or 0)
        row.error_text=str(meta.get('error') or '')
        row.result_status='Error' if row.errors else ('Results' if row.result_count else 'Zero results')
        row.provider_label=provider_label(row.provider)
        row.provider_type=provider_type_for(row.provider,row.category,row.stage,meta)
        row.provider_type_label=provider_type_labels.get(row.provider_type,'Direct Search')
        row.provider_icon=provider_type_icons.get(row.provider_type,'source_direct')
        row.provider_region=_usage_region_context(meta)
        row.search_market=str(meta.get('market') or '').strip() or 'Unknown'
        row.query_language_state,row.query_language_code,row.query_language_label=query_language_identity(
            meta.get('query_language'),meta.get('query_language_label'),meta.get('multilingual_language')
        )
        if row.query_language_state=='unknown':
            row.query_language_code='?'
        elif row.query_language_state=='unrecorded':
            row.query_language_label='Not recorded'
        row.repeat_search_url='' if row.is_direct else _public_search_repeat_url(row.provider,row.query_text)
    filter_pairs=[]
    if q: filter_pairs.append(('q',q))
    if provider_type_none:
        filter_pairs.append(('provider_type_mode','custom'))
    elif not provider_type_all:
        filter_pairs.append(('provider_type_mode','custom'))
        for kind in provider_types: filter_pairs.append(('provider_type',kind))
    if provider_none:
        filter_pairs.append(('provider_mode','custom'))
    elif not provider_all:
        filter_pairs.append(('provider_mode','custom'))
        for name in providers_selected: filter_pairs.append(('provider',name))
    if market_none:
        filter_pairs.append(('market_mode','custom'))
    elif not market_all:
        filter_pairs.append(('market_mode','custom'))
        for value in markets_selected: filter_pairs.append(('market',value))
    if query_language_none:
        filter_pairs.append(('query_language_mode','custom'))
    elif not query_language_all:
        filter_pairs.append(('query_language_mode','custom'))
        for value in query_languages_selected: filter_pairs.append(('query_language',value))
    if outcome_state['mode']=='custom':
        filter_pairs.append(('status_mode','custom'))
        for value in status_values: filter_pairs.append(('status',value))
    filter_pairs.append(('per_page',per_page))
    if date_period: filter_pairs.append(('period',date_period))
    if date_from: filter_pairs.append(('from',date_from))
    if date_to: filter_pairs.append(('to',date_to))
    search_log_sort_query=(f"fs={request.scoutbox_filter_state_token}" if getattr(request,'scoutbox_filter_state_token','') else urlencode(filter_pairs,doseq=True))
    return render(request,'portal/search_log.html',ctx(
        request,'search_log','Search Activity',logs=page,q=q,status_filter=status,status_values=status_values,status_filter_mode=outcome_state['mode'],
        providers=provider_options,provider_values=providers_selected,provider_total=provider_total,selected_provider_label=selected_provider_label,provider_mode=('all' if provider_all else 'custom'),provider_all_checked=provider_all,
        market_options=market_options,market_total=market_total,selected_market_label=selected_market_label,market_mode=('all' if market_all else 'custom'),market_all_checked=market_all,market_values=markets_selected,
        query_language_options=query_language_options,query_language_total=query_language_total,query_language_unrecorded_total=query_language_unrecorded_total,selected_query_language_label=selected_query_language_label,query_language_mode=('all' if query_language_all else 'custom'),query_language_all_checked=query_language_all,query_language_values=query_languages_selected,
        outcome_counts=outcome_counts,outcome_total=outcome_total,outcome_options=_option_selection_state([{'value':'results','label':'Returned results','count':outcome_counts.get('results',0)},{'value':'zero','label':'Zero results','count':outcome_counts.get('zero',0)},{'value':'error','label':'Errors','count':outcome_counts.get('error',0)}],status_values,outcome_state['mode']),selected_outcome_label=_filter_options_label('Outcomes',[{'value':'results','label':'Returned results'},{'value':'zero','label':'Zero results'},{'value':'error','label':'Errors'}],status_values,outcome_state['mode']),
        provider_type_options=provider_type_options,provider_types=provider_types,provider_type_total=provider_type_total,provider_type_mode=('all' if provider_type_all else 'custom'),provider_type_all_checked=provider_type_all,selected_provider_type_label=selected_provider_type_label,
        per_page=per_page,sort_key=sort_key,sort_dir=sort_dir,date_period=date_period,date_from=date_from,date_to=date_to,search_log_sort_query=search_log_sort_query
    ))

@login_required
def gpt_log_view(request):
    # This view is read-only. Empty, recovered, and malformed provider responses have explicit statuses;
    # status repair belongs to migrations/logging, never GETs.
    base=AIRequestLog.objects.annotate(
        status_sort=Case(
            When(status='queued',then=Value(0)),When(status='running',then=Value(1)),
            When(status='recovered_response',then=Value(2)),When(status='malformed_response',then=Value(3)),When(status='empty_response',then=Value(4)),When(status='failed',then=Value(5)),When(status='completed',then=Value(6)),
            default=Value(5),output_field=IntegerField(),
        )
    )
    # AIRequestLog has no search-adapter category column. Adapter bookkeeping is
    # suppressed in Search Activity only; keeping this QuerySet model-field clean
    # prevents /gpt-log/ from raising FieldError on GET/filter/export.
    date_period,date_start,date_end,date_from,date_to=_log_date_bounds(request)
    base=_apply_log_date_bounds(base,'at',date_start,date_end)
    q=_q(request)
    runtime_state=_selected_filter_values(request,'runtime',('local','cloud'))
    runtime_values=list(runtime_state['values'])
    runtime=runtime_values[0] if len(runtime_values)==1 else ''
    model_state=_selected_filter_values(request,'model')
    model_values=list(model_state['values'])
    model=model_values[0] if len(model_values)==1 else ''
    status_allowed=[value for value,_label in AIRequestLog.STATUS]
    status_state=_selected_filter_values(request,'status',status_allowed)
    status_values=list(status_state['values'])
    status_filter=status_values[0] if len(status_values)==1 else ''
    task_state=_request_multi_filter_state(request,'task')
    task_type_values=[str(x).strip() for x in task_state['values'] if str(x).strip()]
    task_type=task_type_values[0] if len(task_type_values)==1 else ''

    def _apply_task_type_filter(qs):
        if task_state['mode']=='custom' and not task_type_values:
            return qs.none()
        if task_state['mode']=='custom':
            return qs.filter(stage__in=task_type_values)
        return qs
    def _apply_runtime_filter(qs):
        return _apply_values_filter(qs,'runtime',runtime_values,runtime_state['mode'])
    def _apply_model_filter(qs):
        return _apply_values_filter(qs,'model',model_values,model_state['mode'])
    def _apply_status_filter(qs):
        return _apply_values_filter(qs,'status',status_values,status_state['mode'])

    if q:
        base=base.filter(Q(provider__icontains=q)|Q(model__icontains=q)|Q(stage__icontains=q)|Q(subject_type__icontains=q)|Q(subject_id__icontains=q)|Q(subject_label__icontains=q)|Q(status__icontains=q))

    # Faceted counts ignore their own selector while respecting all other active selectors.
    runtime_qs=_apply_status_filter(_apply_model_filter(_apply_task_type_filter(base)))
    runtime_counts={row['runtime']:int(row['count']) for row in runtime_qs.exclude(runtime='').values('runtime').annotate(count=Count('id'))}
    runtime_options=_option_selection_state([
        {'value':'local','label':'Local','count':int(runtime_counts.get('local',0) or 0)},
        {'value':'cloud','label':'Cloud','count':int(runtime_counts.get('cloud',0) or 0)},
    ],runtime_values,runtime_state['mode'])
    runtime_total=sum(int(x.get('count') or 0) for x in runtime_options)
    runtime_filter_label=_filter_options_label('runtimes',runtime_options,runtime_values,runtime_state['mode'])

    task_qs=_apply_status_filter(_apply_model_filter(_apply_runtime_filter(base)))
    task_counts={row['stage']:int(row['count']) for row in task_qs.exclude(stage='').values('stage').annotate(count=Count('id')).order_by('stage')}
    task_types=[{'value':name,'label':name.replace('_',' ').title(),'count':count} for name,count in task_counts.items()]
    task_total=sum(int(x.get('count') or 0) for x in task_types)
    _option_selection_state(task_types,task_type_values,task_state['mode'])
    task_filter_label=_multi_filter_label('task types',task_type_values,_selected_labels(task_types,task_type_values),task_state['mode'])

    model_qs=_apply_status_filter(_apply_task_type_filter(_apply_runtime_filter(base)))
    model_counts={row['model']:int(row['count']) for row in model_qs.exclude(model='').values('model').annotate(count=Count('id')).order_by('model')}
    model_options=_option_selection_state([{'value':name,'label':name,'count':count} for name,count in model_counts.items()],model_values,model_state['mode'])
    model_total=sum(int(x.get('count') or 0) for x in model_options)
    model_filter_label=_filter_options_label('models',model_options,model_values,model_state['mode'])

    status_qs=_apply_model_filter(_apply_task_type_filter(_apply_runtime_filter(base)))
    status_counts={row['status']:int(row['count']) for row in status_qs.values('status').annotate(count=Count('id'))}
    status_options=_option_selection_state([{'value':value,'label':label,'count':int(status_counts.get(value,0) or 0)} for value,label in AIRequestLog.STATUS],status_values,status_state['mode'])
    status_total=sum(int(x.get('count') or 0) for x in status_options)
    status_filter_label=_filter_options_label('statuses',status_options,status_values,status_state['mode'])

    qs=_apply_status_filter(_apply_model_filter(_apply_task_type_filter(_apply_runtime_filter(base))))

    sort_key=(request.GET.get('sort') or 'date').strip().lower(); sort_dir=(request.GET.get('dir') or 'desc').strip().lower()
    if sort_dir not in ('asc','desc'): sort_dir='desc'
    sort_map={
        'date':['at'], 'task':['stage','subject_label'], 'runtime':['runtime','provider','model'],
        'input':['input_text'], 'output':['output_text'], 'attachments':['attachments'], 'status':['status_sort','at'], 'duration':['duration_ms'],
    }
    if sort_key not in sort_map: sort_key='date'
    prefix='-' if sort_dir=='desc' else ''
    qs=qs.order_by(*[(prefix+field) for field in sort_map[sort_key]],'-pk' if sort_dir=='desc' else 'pk')
    if request.GET.get('export') in ('1','xlsx'):
        return _gpt_xlsx(list(qs[:50000]))
    if request.GET.get('export')=='jsonl':
        return _gpt_jsonl(list(qs[:50000]))
    try: per_page=int(request.GET.get('per_page') or 50)
    except Exception: per_page=50
    if per_page not in (25,50,100): per_page=50
    page=Paginator(qs,per_page).get_page(request.GET.get('page') or 1)
    filter_pairs=[]
    if q: filter_pairs.append(('q',q))
    if runtime_state['mode']=='custom':
        filter_pairs.append(('runtime_mode','custom'))
        for value in runtime_values: filter_pairs.append(('runtime',value))
    if model_state['mode']=='custom':
        filter_pairs.append(('model_mode','custom'))
        for value in model_values: filter_pairs.append(('model',value))
    if task_state['mode']=='custom':
        filter_pairs.append(('task_mode','custom'))
        for value in task_type_values:
            filter_pairs.append(('task',value))
    if status_state['mode']=='custom':
        filter_pairs.append(('status_mode','custom'))
        for value in status_values: filter_pairs.append(('status',value))
    filter_pairs.append(('per_page',per_page))
    if date_period: filter_pairs.append(('period',date_period))
    if date_from: filter_pairs.append(('from',date_from))
    if date_to: filter_pairs.append(('to',date_to))
    gpt_log_sort_query=(f"fs={request.scoutbox_filter_state_token}" if getattr(request,'scoutbox_filter_state_token','') else urlencode(filter_pairs,doseq=True))
    related_names={'opportunity':'Opportunity','market_lead':'Hidden Lead','hidden_lead':'Hidden Lead','application':'Application','outreach':'Outreach','campaign':'Campaign','profile':'Candidate Profile','background_job':'Background task'}
    for row in page.object_list:
        st=(row.subject_type or '').strip().lower(); sid=(row.subject_id or '').strip(); slabel=(row.subject_label or '').strip()
        meta=row.metadata or {}
        campaign_id=str(meta.get('campaign_id') or '')
        campaign_run_id=str(meta.get('campaign_run_id') or '')
        if campaign_id:
            cname=Campaign.objects.filter(pk=campaign_id).values_list('name',flat=True).first() or f'Campaign {campaign_id}'
            row.related_display=f'{cname}{(" · Run "+campaign_run_id) if campaign_run_id else ""}'
            row.related_url=reverse('campaign_detail',args=[campaign_id])
        elif st and st!='task':
            display_prefix=related_names.get(st,st.replace('_',' ').title())
            row.related_display=f'{display_prefix}{(" "+sid) if sid else ""}{(": "+slabel) if slabel else ""}'
        else:
            row.related_display=''
        attachments=row.attachments if isinstance(row.attachments,list) else []
        row.attachment_count=len(attachments)
        row.attachment_names=', '.join(str(x.get('name') or 'attachment') for x in attachments if isinstance(x,dict))
        def _list_payload_preview(value, repair_truncated_json_string=False):
            raw=str(value or '')
            # Markdown fences are transport/presentation wrappers, not useful list content.
            clean=re.sub(r'^\s*```(?:json)?\s*', '', raw, flags=re.I)
            clean=re.sub(r'\s*```\s*$', '', clean)
            clean=re.sub(r'\s+',' ',clean).strip()
            limit=170
            preview=clean if len(clean)<=limit else clean[:limit].rsplit(' ',1)[0].rstrip()
            truncated=len(clean)>len(preview)
            inline_ellipsis=False
            # List-view syntax highlighting is lexical. If a JSON preview is cut inside a
            # quoted value, put the preview ellipsis *inside* that value and then close the
            # synthetic preview string:  "reason": "The page is from ...". This is
            # display-only; the stored payload and detail popup remain untouched.
            if repair_truncated_json_string and truncated and clean[:1] in ('{','['):
                in_string=False; escaped=False
                for ch in preview:
                    if escaped:
                        escaped=False; continue
                    if ch=='\\' and in_string:
                        escaped=True; continue
                    if ch=='"':
                        in_string=not in_string
                if in_string:
                    preview=preview.rstrip()+(' ...' if not preview.rstrip().endswith('...') else '')
                    inline_ellipsis=True
                    return preview, truncated, inline_ellipsis, True
            return preview, truncated, inline_ellipsis, False
        legacy_empty_output=(str(row.error or '').strip()=='AI provider returned no visible output.' and not str(row.output_text or '').strip())
        blank_completed=bool((row.status or '').lower()=='completed' and str(row.provider or '').strip() and not str(row.output_text or '').strip())
        legacy_malformed=bool((meta.get('response_truncated') is True or str(meta.get('warning_code') or '')=='response_truncated') and str(row.output_text or '').strip() and not meta.get('response_recovered'))
        if legacy_empty_output or blank_completed:
            row.ui_status='empty_response'
        elif meta.get('response_recovered'):
            row.ui_status='recovered_response'
        elif legacy_malformed:
            row.ui_status='malformed_response'
        else:
            row.ui_status=(row.status or ('completed' if row.ok and row.tokens_out>0 else 'failed')).lower()
        row.input_preview,row.input_truncated,_,_=_list_payload_preview(row.input_text)
        # Empty provider output stays visually empty; the Empty response status carries the signal.
        row.output_preview,row.output_truncated,row.output_inline_ellipsis,row.output_open_string=_list_payload_preview(row.output_text,repair_truncated_json_string=True)
        row.ui_status_label=dict(AIRequestLog.STATUS).get(row.ui_status,row.ui_status.title())
        row.ui_response_issue_detail=str(meta.get('response_issue_detail') or meta.get('warning_detail') or ('AI request returned no visible output.' if row.ui_status=='empty_response' and not str(row.output_text or '').strip() else ''))
        row.ui_wait_detail=(str(meta.get('job_message') or '').strip() if meta.get('placeholder') and row.ui_status in ('queued','running') else '')
        discovery_mode=str(meta.get('discovery_mode') or '').strip().lower()
        if discovery_mode=='cloud_web': row.execution_path='Cloud Web'
        elif discovery_mode=='source_guided': row.execution_path='Local AI Discovery'
        elif row.runtime=='local': row.execution_path='Local AI Discovery'
        elif row.runtime=='cloud': row.execution_path='Cloud AI'
        else: row.execution_path=''
        row.inference_not_started=bool(row.ui_status=='failed' and not (row.provider or row.model))
        if row.duration_ms is None: row.duration_display=''
        elif row.duration_ms < 1000: row.duration_display=f'{row.duration_ms} ms'
        else: row.duration_display=f'{row.duration_ms/1000:.1f} s'
    return render(request,'portal/gpt_log.html',ctx(
        request,'gpt_log','AI Requests',logs=page,q=q,runtime_filter=runtime,runtime_values=runtime_values,runtime_filter_mode=runtime_state['mode'],runtime_filter_label=runtime_filter_label,runtime_options=runtime_options,task_type_filter=task_type,task_type_values=task_type_values,task_filter_mode=task_state['mode'],task_filter_label=task_filter_label,model_filter=model,model_values=model_values,model_filter_mode=model_state['mode'],model_filter_label=model_filter_label,status_filter=status_filter,status_values=status_values,status_filter_mode=status_state['mode'],status_filter_label=status_filter_label,
        runtime_counts=runtime_counts,runtime_total=runtime_total,task_types=task_types,task_total=task_total,
        provider_options=model_options,provider_total=model_total,status_counts=status_counts,status_total=status_total,status_options=status_options,
        per_page=per_page,sort_key=sort_key,sort_dir=sort_dir,date_period=date_period,date_from=date_from,date_to=date_to,gpt_log_sort_query=gpt_log_sort_query
    ))


@login_required
def gpt_log_detail(request,pk):
    row=get_object_or_404(AIRequestLog,pk=pk)
    meta=row.metadata or {}; related=''
    if meta.get('campaign_id'):
        cname=Campaign.objects.filter(pk=meta.get('campaign_id')).values_list('name',flat=True).first() or f"Campaign {meta.get('campaign_id')}"
        related=f"{cname}{(' · Run '+str(meta.get('campaign_run_id'))) if meta.get('campaign_run_id') else ''}"
    legacy_empty_output=(str(row.error or '').strip()=='AI provider returned no visible output.' and not str(row.output_text or '').strip())
    blank_completed=bool((row.status or '').lower()=='completed' and str(row.provider or '').strip() and not str(row.output_text or '').strip())
    legacy_malformed=bool((meta.get('response_truncated') is True or str(meta.get('warning_code') or '')=='response_truncated') and str(row.output_text or '').strip() and not meta.get('response_recovered'))
    display_status='empty_response' if legacy_empty_output or blank_completed else ('recovered_response' if meta.get('response_recovered') else ('malformed_response' if legacy_malformed else row.status))
    display_error='' if display_status in ('empty_response','recovered_response','malformed_response') else row.error
    response_issue=str(meta.get('response_issue_detail') or meta.get('warning_detail') or ('AI request returned no visible output.' if display_status=='empty_response' and not str(row.output_text or '').strip() else ''))
    display_output=str(row.output_text or '')
    recovered_output_json=None
    if display_status=='recovered_response':
        # A recovered response has already been validated by the AI service. Normalize it
        # once on the server and send the parsed value as authoritative data so the popup
        # never falls back to the malformed-text renderer because of presentation wrappers.
        try:
            recovered_output_json=json.loads(display_output)
        except Exception:
            recovery=_recover_truncated_json_list(str(row.raw_output_text or display_output))
            if recovery:
                display_output=str(recovery.get('text') or display_output)
                try: recovered_output_json=json.loads(display_output)
                except Exception: recovered_output_json=None
        if recovered_output_json is not None:
            display_output=json.dumps(recovered_output_json,ensure_ascii=False,indent=2,default=str)
    return JsonResponse({'ok':True,'id':row.pk,'at':timezone.localtime(row.at).strftime('%d/%m/%Y %H:%M:%S %Z'),'status':display_status,'status_label':dict(AIRequestLog.STATUS).get(display_status,str(display_status or '').replace('_',' ').title()),'provider':row.provider,'model':row.model,'stage':row.stage,'runtime':row.runtime,'subject_type':row.subject_type,'subject_id':row.subject_id,'subject_label':row.subject_label,'related_display':related,'tokens_in':row.tokens_in,'tokens_out':row.tokens_out,'reasoning_tokens':row.reasoning_tokens,'ai_web_search_queries':row.web_search_queries,'token_usage_source':row.token_usage_source,'duration_ms':row.duration_ms,'input_text':row.input_text,'output_text':display_output,'recovered_output_json':recovered_output_json,'attachments':row.attachments or [], 'metadata':meta,'ok':row.ok,'response_issue':response_issue,'error':display_error})


@login_required
def audit_view(request):
    date_period,date_start,date_end,date_from,date_to=_log_date_bounds(request)
    base=_apply_log_date_bounds(AuditLog.objects.all(),'at',date_start,date_end); q=_q(request)
    action_state=_selected_filter_values(request,'action')
    action_values=list(action_state['values'])
    action=action_values[0] if len(action_values)==1 else ''
    version_state=_selected_filter_values(request,'version')
    version_values=list(version_state['values'])
    if q: base=base.filter(Q(actor__icontains=q)|Q(action__icontains=q)|Q(version__icontains=q)|Q(summary__icontains=q)|Q(object_type__icontains=q)|Q(object_id__icontains=q)|Q(metadata__object_title__icontains=q))
    action_counts={row['action']:int(row['count']) for row in base.exclude(action='').values('action').annotate(count=Count('id')).order_by('action')}
    action_options=_option_selection_state([{'value':name,'label':name,'count':count} for name,count in action_counts.items()],action_values,action_state['mode'])
    action_total=sum(int(x.get('count') or 0) for x in action_options)
    qs=_apply_values_filter(base,'action',action_values,action_state['mode'])
    version_rows=list(base.values('version').annotate(count=Count('id')).order_by('version'))
    version_counts={str(row.get('version') or '').strip():int(row.get('count') or 0) for row in version_rows}
    version_option_rows=[{'value':name,'label':name,'count':count} for name,count in version_counts.items() if name]
    version_option_rows.append({'value':'__unknown__','label':'Unknown','count':version_counts.get('',0)})
    version_options=_option_selection_state(version_option_rows,version_values,version_state['mode'])
    if version_state['mode']=='custom':
        known=[value for value in version_values if value!='__unknown__']
        version_query=Q(version__in=known) if known else Q(pk__in=[])
        if '__unknown__' in version_values:
            version_query|=Q(version__isnull=True)|Q(version='')
        qs=qs.filter(version_query)
    if request.GET.get('export')=='1':
        return _xlsx('audit.xlsx',['Version','Actor','Action','Object type','Object id','Summary','Time'],[(x.version,x.actor,x.action,x.object_type,x.object_id,x.summary,x.at) for x in qs[:50000]])
    try: per_page=int(request.GET.get('per_page') or 50)
    except Exception: per_page=50
    if per_page not in (25,50,100): per_page=50
    page=Paginator(qs,per_page).get_page(request.GET.get('page') or 1)
    return render(request,'portal/audit.html',ctx(
        request,'audit','Audit Trail',logs=page,q=q,action_filter=action,action_values=action_values,action_filter_mode=action_state['mode'],action_filter_label=_filter_options_label('actions',action_options,action_values,action_state['mode']),action_options=action_options,version_values=version_values,version_filter_mode=version_state['mode'],version_filter_label=_filter_options_label('versions',version_options,version_values,version_state['mode']),version_options=version_options,
        action_total=action_total,per_page=per_page,page_obj=page,date_period=date_period,date_from=date_from,date_to=date_to
    ))



def _blog_test(cfg):
    result=test_blog_connection(cfg)
    return bool(result.get('ok')), result.get('message') or 'Read-only SELECT test completed.'


@login_required
@require_POST
def blog_stats_test_async(request):
    # This is a short read-only sidecar health/query test. Running it inline avoids the
    # historical failure mode where the UI said Queued forever while default workers were
    # occupied by long AI/search jobs. The completed diagnostic is still persisted.
    cfg=BlogStatsConfig.objects.get_or_create(pk=1)[0]
    job=BackgroundJob.objects.create(kind='diagnostic',label='External statistics connection test',status='running',progress=10,message='Testing external statistics data source',started_at=timezone.now(),result={'blog_config_id':cfg.pk})
    try:
        result=test_blog_connection(cfg)
        ok=bool(result.get('ok'))
        job.status='completed' if ok else 'failed'; job.progress=100; job.finished_at=timezone.now()
        job.message=(result.get('message') or ('External statistics connection test completed' if ok else 'External statistics connection test failed'))[:500]
        job.error='' if ok else (result.get('message') or 'Connection test failed')[:2000]
        job.result=result; job.save(update_fields=['status','progress','finished_at','message','error','result'])
        return JsonResponse({'ok':ok,'finished':True,'job_id':job.pk,'message':job.message,'error':job.error,'result':result})
    except Exception as exc:
        job.status='failed'; job.progress=100; job.finished_at=timezone.now(); job.message='External statistics connection test failed'; job.error=str(exc)[:2000]; job.save(update_fields=['status','progress','finished_at','message','error'])
        return JsonResponse({'ok':False,'finished':True,'job_id':job.pk,'message':job.message,'error':job.error},status=502)



def _recycle_item_key(raw):
    raw=str(raw or '').strip()
    if ':' not in raw: return '',None
    item_type,item_id=raw.split(':',1)
    return (item_type.lower(),int(item_id)) if item_id.isdigit() else ('',None)


def _restore_recycle_item(item_type,item_id):
    if item_type=='campaign':
        row=Campaign.objects.filter(pk=item_id,deleted_at__isnull=False).first()
        if not row: return False,'Campaign'
        row.deleted_at=None; row.enabled=False; row.save(update_fields=['deleted_at','enabled','updated_at'])
        return True,f'campaign {row.name}'
    if item_type=='campaign_template':
        row=CampaignTemplate.objects.filter(pk=item_id,deleted_at__isnull=False).first()
        if not row: return False,'Campaign Template'
        row.deleted_at=None; row.save(update_fields=['deleted_at','updated_at'])
        return True,f'campaign template {row.name}'
    if item_type=='opportunity':
        row=Opportunity.objects.filter(pk=item_id,user_deleted=True).first()
        if not row: return False,'Opportunity'
        deleted_stamp=row.deleted_at
        row.user_deleted=False; row.deleted_at=None; row.suppressed=False; row.is_read=True
        if (row.rejection_reason or '').strip()=='Moved to Recycle Bin by user.' or (row.rejection_reason or '').startswith('Blocked by blacklist:') or (row.rejection_reason or '').startswith('Blocked by user blacklist.'):
            row.rejection_reason=''
        row.save(update_fields=['user_deleted','deleted_at','suppressed','is_read','rejection_reason','updated_at'])
        if deleted_stamp:
            Application.objects.filter(opportunity=row,deleted_at=deleted_stamp).update(deleted_at=None,is_read=True)
        return True,f'opportunity {row.company} — {row.title}'
    if item_type=='application':
        row=Application.objects.select_related('opportunity').filter(pk=item_id,deleted_at__isnull=False).first()
        if not row: return False,'Application / Outreach'
        row.deleted_at=None; row.is_read=True; row.save(update_fields=['deleted_at','is_read','updated_at'])
        opp=row.opportunity
        if opp.user_deleted:
            opp.user_deleted=False; opp.deleted_at=None; opp.suppressed=False; opp.is_read=True
            if (opp.rejection_reason or '').strip()=='Moved to Recycle Bin by user.' or (opp.rejection_reason or '').startswith('Blocked by blacklist:') or (opp.rejection_reason or '').startswith('Blocked by user blacklist.'):
                opp.rejection_reason=''
            opp.save(update_fields=['user_deleted','deleted_at','suppressed','is_read','rejection_reason','updated_at'])
        label='outreach' if (opp.extracted_facts or {}).get('outreach') else 'application'
        return True,f'{label} {opp.company} — {opp.title}'
    if item_type=='lead':
        row=CompanyLead.objects.filter(pk=item_id,user_deleted=True,deleted_at__isnull=False).first()
        if not row: return False,'Hidden Lead'
        row.user_deleted=False; row.deleted_at=None; row.is_read=True
        row.save(update_fields=['user_deleted','deleted_at','is_read','updated_at'])
        return True,f'Hidden Lead {row.company}'
    if item_type=='contact':
        row=Contact.objects.filter(pk=item_id,deleted_at__isnull=False).first()
        if not row: return False,'Address Book'
        row.deleted_at=None; row.is_read=True; row.save(update_fields=['deleted_at','is_read'])
        return True,f'Address Book {row.name or row.company or row.email}'
    if item_type=='facebook_page':
        row=FacebookPage.objects.filter(pk=item_id,deleted_at__isnull=False).first()
        if not row: return False,'Facebook Page'
        row.deleted_at=None; row.enabled=True; row.is_read=True; row.save(update_fields=['deleted_at','enabled','is_read','updated_at'])
        return True,f'Facebook Page {row.page_title or row.page_id}'
    if item_type=='tracking_link':
        row=TrackingLink.objects.filter(pk=item_id,deleted_at__isnull=False).first()
        if not row: return False,'Tracking Link'
        row.deleted_at=None; row.save(update_fields=['deleted_at'])
        return True,f'Tracking Link {row.path}'
    if item_type=='blacklist':
        row=SourceBlacklist.objects.filter(pk=item_id,deleted_at__isnull=False).first()
        if not row: return False,'Blacklist'
        row.deleted_at=None; row.save(update_fields=['deleted_at'])
        return True,f'Blacklist {row.domain or row.label or row.reason}'
    return False,'Unknown item'


def _delete_recycle_item(item_type,item_id):
    if item_type=='application': return Application.objects.filter(pk=item_id,deleted_at__isnull=False).delete()[0]
    if item_type=='campaign_template': return CampaignTemplate.objects.filter(pk=item_id,deleted_at__isnull=False).delete()[0]
    if item_type=='opportunity': return Opportunity.objects.filter(pk=item_id,user_deleted=True).delete()[0]
    if item_type=='lead': return CompanyLead.objects.filter(pk=item_id,user_deleted=True,deleted_at__isnull=False).delete()[0]
    if item_type=='campaign': return Campaign.objects.filter(pk=item_id,deleted_at__isnull=False).delete()[0]
    if item_type=='contact': return Contact.objects.filter(pk=item_id,deleted_at__isnull=False).delete()[0]
    if item_type=='facebook_page': return FacebookPage.objects.filter(pk=item_id,deleted_at__isnull=False).delete()[0]
    if item_type=='tracking_link': return TrackingLink.objects.filter(pk=item_id,deleted_at__isnull=False).delete()[0]
    if item_type=='blacklist': return SourceBlacklist.objects.filter(pk=item_id,deleted_at__isnull=False).delete()[0]
    return 0


def _recycle_blacklist_candidate(item_type,item_id):
    """Return (domain, label) for a recycled row without mutating the recycled item."""
    if item_type=='campaign_template':
        row=CampaignTemplate.objects.filter(pk=item_id,deleted_at__isnull=False).first()
        if not row: return False,'Campaign Template'
        row.deleted_at=None; row.save(update_fields=['deleted_at','updated_at'])
        return True,f'campaign template {row.name}'
    if item_type=='opportunity':
        row=Opportunity.objects.filter(pk=item_id,user_deleted=True).first()
        if not row: return '',''
        return '',_opportunity_blacklist_label(row)
    if item_type=='application':
        row=Application.objects.select_related('opportunity').filter(pk=item_id,deleted_at__isnull=False).first()
        if not row or not row.opportunity: return '',''
        opp=row.opportunity
        return '',_opportunity_blacklist_label(opp)
    if item_type=='lead':
        row=CompanyLead.objects.filter(pk=item_id,user_deleted=True,deleted_at__isnull=False).first()
        if not row: return '',''
        return _clean_url_for_blacklist(row.target_url or row.source_url or row.search_url),row.company or ''
    if item_type=='contact':
        row=Contact.objects.filter(pk=item_id,deleted_at__isnull=False).first()
        if not row: return '',''
        domain=_clean_url_for_blacklist(row.source_url)
        if not domain and '@' in (row.email or ''):
            domain=normalize_pattern((row.email or '').rsplit('@',1)[-1])
        label=(f'{row.name} — {row.company}' if row.name and row.company else row.name or row.company or row.email or domain)
        return domain,label
    if item_type=='blacklist':
        row=SourceBlacklist.objects.filter(pk=item_id,deleted_at__isnull=False).first()
        if not row: return '',''
        return row.domain,row.label or row.reason or row.domain
    return '',''


def _recycle_item_info_url(value):
    """Return a safe clickable URL only when the entire Recycle Bin value is HTTP(S)."""
    text=str(value or '').strip()
    if not text or any(ch.isspace() for ch in text):
        return ''
    try:
        parsed=urlparse(text)
    except Exception:
        return ''
    if parsed.scheme.lower() not in {'http','https'} or not parsed.netloc:
        return ''
    return text


@login_required
def recycle_bin_view(request):
    """Standalone searchable holding area for user-deleted workspace records."""
    if request.method=='POST':
        action=(request.POST.get('action') or '').strip()
        selected=[]
        seen=set()
        for raw in request.POST.getlist('recycle_items'):
            item_type,item_id=_recycle_item_key(raw)
            if item_type and item_id and (item_type,item_id) not in seen:
                selected.append((item_type,item_id)); seen.add((item_type,item_id))
        if action=='restore_selected':
            if not selected:
                messages.error(request,'Select at least one Recycle Bin item to restore.')
            else:
                restored=[]; missing=0
                # Parents first makes multi-selection predictable; application restore still
                # restores its parent when that parent was not explicitly selected.
                rank={'campaign':0,'campaign_template':1,'opportunity':2,'application':3,'lead':4,'contact':5,'facebook_page':6,'tracking_link':7,'blacklist':8}
                for item_type,item_id in sorted(selected,key=lambda x:rank.get(x[0],9)):
                    ok,label=_restore_recycle_item(item_type,item_id)
                    if ok: restored.append(label)
                    else: missing+=1
                suffix=f' {missing} selected item(s) were no longer present.' if missing else ''
                messages.success(request,f'Restored {len(restored)} selected item(s).{suffix}')
            return redirect('recycle_bin')
        if action=='delete_selected':
            if not selected:
                messages.error(request,'Select at least one Recycle Bin item to permanently delete.')
            else:
                removed=0
                # Applications first avoids reporting confusing cascade totals.
                rank={'application':0,'opportunity':1,'lead':2,'contact':3,'facebook_page':4,'tracking_link':5,'blacklist':6,'campaign_template':7,'campaign':8}
                for item_type,item_id in sorted(selected,key=lambda x:rank.get(x[0],9)):
                    removed+=int(bool(_delete_recycle_item(item_type,item_id)))
                messages.success(request,f'Permanently removed {removed} selected Recycle Bin item(s).')
            return redirect('recycle_bin')
        if action=='blacklist_selected':
            if not selected:
                messages.error(request,'Select at least one Recycle Bin item to add to the blacklist.')
            else:
                added=0; skipped=0; rules=set()
                for item_type,item_id in selected:
                    domain,label=_recycle_blacklist_candidate(item_type,item_id)
                    label=(label or '').strip()
                    if item_type in {'opportunity','application'}:
                        if not valid_label_only_pattern(label):
                            skipped+=1; continue
                        try:
                            row,created=_upsert_blacklist_rule('',label,'Added from Recycle Bin','all')
                        except ValueError:
                            skipped+=1; continue
                        rules.add(row.label or label); added+=1; continue
                    if not domain:
                        skipped+=1; continue
                    domain=normalize_pattern(domain)
                    if not domain:
                        skipped+=1; continue
                    SourceBlacklist.objects.update_or_create(domain=domain,defaults={'label':(label or domain)[:255],'reason':'','scope':'all','enabled':True,'deleted_at':None})
                    rules.add(domain); added+=1
                if added:
                    messages.success(request,f'Added or re-enabled {len(rules)} blacklist rule{"" if len(rules)==1 else "s"} from {added} selected Recycle Bin item{"" if added==1 else "s"}. The recycled items were left unchanged.')
                if skipped:
                    messages.warning(request,f'{skipped} selected item{"" if skipped==1 else "s"} had no usable blacklist target and were skipped.')
            return redirect('recycle_bin')
        if action=='empty':
            app_count=Application.objects.filter(deleted_at__isnull=False).count()
            opp_count=Opportunity.objects.filter(user_deleted=True).count()
            lead_count=CompanyLead.objects.filter(user_deleted=True).count()
            campaign_count=Campaign.objects.filter(deleted_at__isnull=False).count()
            template_count=CampaignTemplate.objects.filter(deleted_at__isnull=False).count()
            contact_count=Contact.objects.filter(deleted_at__isnull=False).count()
            facebook_page_count=FacebookPage.objects.filter(deleted_at__isnull=False).count()
            tracking_link_count=TrackingLink.objects.filter(deleted_at__isnull=False).count()
            blacklist_count=SourceBlacklist.objects.filter(deleted_at__isnull=False).count()
            Application.objects.filter(deleted_at__isnull=False).delete()
            Opportunity.objects.filter(user_deleted=True).delete()
            CompanyLead.objects.filter(user_deleted=True).delete()
            Campaign.objects.filter(deleted_at__isnull=False).delete()
            CampaignTemplate.objects.filter(deleted_at__isnull=False).delete()
            Contact.objects.filter(deleted_at__isnull=False).delete()
            FacebookPage.objects.filter(deleted_at__isnull=False).delete()
            TrackingLink.objects.filter(deleted_at__isnull=False).delete()
            SourceBlacklist.objects.filter(deleted_at__isnull=False).delete()
            messages.success(request,f'Emptied the Recycle Bin: {campaign_count} campaign(s), {template_count} campaign template(s), {opp_count} opportunity/opportunities, {lead_count} Hidden Lead(s), {app_count} application/outreach record(s), {contact_count} Address Book item(s), {facebook_page_count} Facebook Page(s), {tracking_link_count} tracking link(s), and {blacklist_count} blacklist item(s) permanently removed.')
            return redirect('recycle_bin')

    rows=[]
    for row in Campaign.objects.filter(deleted_at__isnull=False).only('id','name','deleted_at','created_at','enabled'):
        rows.append({'deleted_at':row.deleted_at,'item_date':row.created_at,'title':row.name,'item_info':'Campaign','item_type':'Campaign','filter_type':'campaign','item_key':'campaign','item_id':row.pk})
    for row in CampaignTemplate.objects.filter(deleted_at__isnull=False).only('id','name','description','deleted_at','created_at'):
        rows.append({'deleted_at':row.deleted_at,'item_date':row.created_at,'title':row.name,'item_info':row.description or 'Campaign Template','item_type':'Campaign Template','filter_type':'campaign_template','item_key':'campaign_template','item_id':row.pk})
    for row in Opportunity.objects.filter(user_deleted=True).only('id','company','title','deleted_at','first_seen_by_portal','target_url','canonical_url','url','contact_email'):
        info=(row.contact_email or row.target_url or row.canonical_url or row.url or '').strip()
        rows.append({'deleted_at':row.deleted_at,'item_date':row.first_seen_by_portal,'title':f'{row.company} — {row.title}','item_info':info,'item_type':'Opportunity','filter_type':'opportunity','item_key':'opportunity','item_id':row.pk})
    for row in Application.objects.filter(deleted_at__isnull=False).select_related('opportunity'):
        opp=row.opportunity
        label='Outreach' if (opp.extracted_facts or {}).get('outreach') else 'Application'
        info=(opp.contact_email or opp.target_url or opp.canonical_url or opp.url or '').strip()
        rows.append({'deleted_at':row.deleted_at,'item_date':row.date_added or row.created_at,'title':f'{opp.company} — {opp.title}','item_info':info,'item_type':label,'filter_type':label.lower(),'item_key':'application','item_id':row.pk})
    for row in CompanyLead.objects.filter(user_deleted=True,deleted_at__isnull=False).only('id','company','deleted_at','created_at','contact_email','target_url','source_url'):
        info=(row.contact_email or row.target_url or row.source_url or '').strip()
        rows.append({'deleted_at':row.deleted_at,'item_date':row.created_at,'title':row.company,'item_info':info,'item_type':'Hidden Lead','filter_type':'lead','item_key':'lead','item_id':row.pk})
    for row in Contact.objects.filter(deleted_at__isnull=False).only('id','name','company','email','source_url','deleted_at','created_at'):
        title=(row.name or row.company or row.email or 'Address Book contact').strip()
        if row.name and row.company: title=f'{row.name} — {row.company}'
        info=(row.email or row.source_url or '').strip()
        rows.append({'deleted_at':row.deleted_at,'item_date':row.created_at,'title':title,'item_info':info,'item_type':'Address Book','filter_type':'contact','item_key':'contact','item_id':row.pk})
    for row in FacebookPage.objects.filter(deleted_at__isnull=False).only('id','page_id','page_title','page_url','deleted_at','discovered_at'):
        rows.append({'deleted_at':row.deleted_at,'item_date':row.discovered_at,'title':row.page_title or row.page_id,'item_info':row.page_url,'item_type':'Facebook Page','filter_type':'facebook_page','item_key':'facebook_page','item_id':row.pk})
    for row in TrackingLink.objects.filter(deleted_at__isnull=False).only('id','path','full_url','deleted_at','created_at'):
        rows.append({'deleted_at':row.deleted_at,'item_date':row.created_at,'title':row.path,'item_info':row.full_url,'item_type':'Tracking Link','filter_type':'tracking_link','item_key':'tracking_link','item_id':row.pk})
    for row in SourceBlacklist.objects.filter(deleted_at__isnull=False).only('id','domain','label','reason','deleted_at','created_at'):
        title=(row.label or row.reason or row.domain or 'Blacklist entry').strip()
        rows.append({'deleted_at':row.deleted_at,'item_date':row.created_at,'title':title,'item_info':row.domain,'item_type':'Blacklist','filter_type':'blacklist','item_key':'blacklist','item_id':row.pk})
    for item in rows:
        item['item_info_url']=_recycle_item_info_url(item.get('item_info'))
    date_period,date_start,date_end,date_from,date_to=_log_date_bounds(request)
    if date_start: rows=[x for x in rows if x.get('deleted_at') and x.get('deleted_at')>=date_start]
    if date_end: rows=[x for x in rows if x.get('deleted_at') and x.get('deleted_at')<date_end]
    q=_q(request)
    valid_item_types={'campaign','campaign_template','opportunity','lead','application','outreach','contact','facebook_page','tracking_link','blacklist'}
    item_type_state=_selected_filter_values(request,'item_type',valid_item_types)
    item_type_values=list(item_type_state['values'])
    item_type_filter=item_type_values[0] if len(item_type_values)==1 else ''
    if q:
        needle=q.casefold(); rows=[x for x in rows if needle in f"{x['title']} {x.get('item_info','')} {x['item_type']}".casefold()]
    recycle_filter_counts={'total':len(rows),'type':{}}
    for item in rows:
        key=item.get('filter_type') or ''
        recycle_filter_counts['type'][key]=recycle_filter_counts['type'].get(key,0)+1
    item_type_labels={'campaign':'Campaign','campaign_template':'Campaign Template','opportunity':'Opportunity','lead':'Hidden Lead','application':'Application','outreach':'Outreach','contact':'Address Book','facebook_page':'Facebook Page','tracking_link':'Tracking Link','blacklist':'Blacklist'}
    item_type_options=_option_selection_state([{'value':value,'label':item_type_labels[value],'count':int(recycle_filter_counts['type'].get(value,0) or 0)} for value in ('campaign','campaign_template','opportunity','lead','application','outreach','contact','facebook_page','tracking_link','blacklist')],item_type_values,item_type_state['mode'])
    item_type_filter_label=_filter_options_label('types',item_type_options,item_type_values,item_type_state['mode'],recycle_filter_counts['total'])
    if item_type_state['mode']=='custom' and not item_type_values:
        rows=[]
    elif item_type_state['mode']=='custom':
        allowed=set(item_type_values)
        rows=[x for x in rows if x.get('filter_type') in allowed]
    epoch=timezone.make_aware(datetime(1970,1,1))
    sort_mode=(request.GET.get('sort') or '').strip().lower()
    valid_sorts={
        'deleted_asc','deleted_desc','item_date_asc','item_date_desc','title_asc','title_desc',
        'info_asc','info_desc','type_asc','type_desc',
    }
    if sort_mode not in valid_sorts: sort_mode='deleted_desc'
    reverse=sort_mode.endswith('_desc')
    if sort_mode.startswith('deleted_'):
        sort_key=lambda x:(x.get('deleted_at') or epoch,int(x.get('item_id') or 0))
    elif sort_mode.startswith('item_date_'):
        sort_key=lambda x:(x.get('item_date') or epoch,int(x.get('item_id') or 0))
    elif sort_mode.startswith('title_'):
        sort_key=lambda x:(str(x.get('title') or '').casefold(),str(x.get('item_type') or '').casefold(),int(x.get('item_id') or 0))
    elif sort_mode.startswith('info_'):
        sort_key=lambda x:(str(x.get('item_info') or '').casefold(),str(x.get('title') or '').casefold(),int(x.get('item_id') or 0))
    else:
        sort_key=lambda x:(str(x.get('item_type') or '').casefold(),str(x.get('title') or '').casefold(),int(x.get('item_id') or 0))
    rows.sort(key=sort_key,reverse=reverse)
    if request.GET.get('export')=='1':
        return _xlsx('scoutbox-recycle-bin.xlsx',['Item Title','Item Info','Item Type','Item Date','Date Deleted'],[(x.get('title',''),x.get('item_info',''),x.get('item_type',''),timezone.localtime(x['item_date']).strftime('%d/%m/%Y %H:%M:%S') if x.get('item_date') else '',timezone.localtime(x['deleted_at']).strftime('%d/%m/%Y %H:%M:%S') if x.get('deleted_at') else '') for x in rows])
    try: per_page=int(request.GET.get('per_page') or 50)
    except Exception: per_page=50
    if per_page not in (25,50,100): per_page=50
    page=Paginator(rows,per_page).get_page(request.GET.get('page') or 1)
    total_recycled=(Campaign.objects.filter(deleted_at__isnull=False).count()+CampaignTemplate.objects.filter(deleted_at__isnull=False).count()+Opportunity.objects.filter(user_deleted=True).count()+Application.objects.filter(deleted_at__isnull=False).count()+CompanyLead.objects.filter(user_deleted=True,deleted_at__isnull=False).count()+Contact.objects.filter(deleted_at__isnull=False).count()+FacebookPage.objects.filter(deleted_at__isnull=False).count()+TrackingLink.objects.filter(deleted_at__isnull=False).count()+SourceBlacklist.objects.filter(deleted_at__isnull=False).count())
    return render(request,'portal/recycle_bin.html',ctx(request,'recycle_bin','Recycle Bin',rows=page,page_obj=page,per_page=per_page,q=q,item_type_filter=item_type_filter,item_type_values=item_type_values,item_type_filter_mode=item_type_state['mode'],item_type_options=item_type_options,item_type_filter_label=item_type_filter_label,recycle_total=total_recycled,recycle_filter_counts=recycle_filter_counts,date_period=date_period,date_from=date_from,date_to=date_to,sort_mode=sort_mode))


_DIAGNOSTIC_SECRET_KEYS={
    'api_key','api_key_enc','password','password_enc','imap_password_enc','smtp_password_enc','resend_api_key','resend_api_key_enc',
    'graph_access_token_enc','cookie_header_enc','access_token','refresh_token','client_secret',
    'authorization','credential','credentials','secret','private_key','session_key',
}


def _diagnostic_period(request):
    raw=(request.GET.get('period') or '24h').strip().lower()
    now=timezone.now()
    if raw=='all':
        return 'all',None
    if raw in {'1h','1hr','1hrs'}:
        return '1h',now-timedelta(hours=1)
    if raw in {'3h','3hr','3hrs'}:
        return '3h',now-timedelta(hours=3)
    if raw in {'6h','6hr','6hrs'}:
        return '6h',now-timedelta(hours=6)
    if raw in {'12h','12hr','12hrs'}:
        return '12h',now-timedelta(hours=12)
    if raw in {'3d','3','72h'}:
        return '3d',now-timedelta(days=3)
    if raw in {'7d','7'}:
        return '7d',now-timedelta(days=7)
    if raw in {'14d','14','2w'}:
        return '14d',now-timedelta(days=14)
    if raw in {'30d','30'}:
        return '30d',now-timedelta(days=30)
    return '24h',now-timedelta(hours=24)


_DIAGNOSTIC_EXPORT_GROUPS=(
    ('context','Configuration & Campaign Context'),
    ('opportunities','Opportunities & Evidence'),
    ('hidden_leads','Hidden Leads'),
    ('contacts','Contacts, Applications & Mail'),
    ('facebook','Facebook & Tracking'),
    ('search','Search & Provider Diagnostics'),
    ('discovery','Discovery Funnel & Filtering'),
    ('ai','AI Request Diagnostics'),
    ('resources','Resource Usage'),
    ('operations','Jobs, Errors & Audit'),
)
_DIAGNOSTIC_EXPORT_GROUP_KEYS={key for key,_label in _DIAGNOSTIC_EXPORT_GROUPS}

def _diagnostic_selected_groups(request):
    values=[]
    for value in request.GET.getlist('category'):
        key=str(value or '').strip().lower()
        if key in _DIAGNOSTIC_EXPORT_GROUP_KEYS and key not in values:
            values.append(key)
    return values

def _diagnostic_period_count(qs,start,field='created_at'):
    if start:
        qs=qs.filter(**{f'{field}__gte':start})
    return int(qs.count())

def _diagnostic_export_estimates(period,start):
    """Fast uncompressed-size estimates for the export chooser.

    Estimates intentionally use counts and conservative sampled-size coefficients rather
    than serializing the export. They are guidance, not quotas, and keep the chooser fast
    even when the retained database is large.
    """
    def recent(qs,field='created_at'):
        return _diagnostic_period_count(qs,start,field)
    opp_qs=Opportunity.objects.all()
    if start: opp_qs=opp_qs.filter(Q(first_seen_by_portal__gte=start)|Q(first_seen_by_portal__isnull=True,created_at__gte=start))
    opp_count=int(opp_qs.count())
    opp_ids=opp_qs.values_list('pk',flat=True)
    lead_count=recent(CompanyLead.objects.all())
    app_count=recent(Application.objects.all())
    contact_count=recent(Contact.objects.all())
    mail_count=recent(MailEvent.objects.all(),'occurred_at')
    facebook_qs=FacebookPage.objects.all()
    if start: facebook_qs=facebook_qs.filter(Q(discovered_at__gte=start)|Q(deleted_at__gte=start))
    tracking_qs=TrackingLink.objects.all()
    if start: tracking_qs=tracking_qs.filter(Q(created_at__gte=start)|Q(deleted_at__gte=start))
    provider_qs=SearchProviderStat.objects.all()
    if start: provider_qs=provider_qs.filter(day__gte=start.date())
    usage_qs=UsageMetric.objects.all()
    if start: usage_qs=usage_qs.filter(at__gte=start)
    ai_qs=AIRequestLog.objects.all()
    if start: ai_qs=ai_qs.filter(at__gte=start)
    chatbot_qs=ChatbotMessage.objects.all()
    if start: chatbot_qs=chatbot_qs.filter(at__gte=start)
    resource_qs=ResourceSample.objects.all()
    hourly_qs=ResourceHourly.objects.all()
    if start:
        resource_qs=resource_qs.filter(at__gte=start); hourly_qs=hourly_qs.filter(hour__gte=start)
    campaign_run_qs=CampaignRun.objects.all()
    if start: campaign_run_qs=_diagnostic_recent(campaign_run_qs,start,'created_at','started_at','finished_at')
    bg_qs=BackgroundJob.objects.all()
    if start: bg_qs=_diagnostic_recent(bg_qs,start,'created_at','started_at','finished_at')
    audit_qs=AuditLog.objects.all()
    if start: audit_qs=audit_qs.filter(at__gte=start)
    evidence_count=int(OpportunityEvidence.objects.filter(opportunity_id__in=opp_ids).count()) if opp_count else 0
    import_count=recent(ImportCandidate.objects.all())
    generated_count=int(GeneratedTextVersion.objects.filter(application__in=(Application.objects.filter(created_at__gte=start) if start else Application.objects.all())).count())
    sizes={
        'context':350000 + Campaign.objects.count()*1800 + SearchSource.objects.count()*1200 + DocumentAsset.objects.count()*1600,
        'opportunities':opp_count*6500 + evidence_count*1200 + import_count*1700 + 80000,
        'hidden_leads':lead_count*5200 + 50000,
        'contacts':app_count*4200 + contact_count*2200 + mail_count*1900 + generated_count*1800 + 80000,
        'facebook':int(facebook_qs.count())*2100 + int(tracking_qs.count())*1800 + 40000,
        'search':int(provider_qs.count())*1400 + int(usage_qs.count())*520 + 90000,
        'discovery':int(campaign_run_qs.count())*3300 + int(usage_qs.filter(category='discovery_filter').count())*650 + 90000,
        'ai':int(ai_qs.count())*1700 + int(chatbot_qs.count())*1500 + 120000,
        'resources':int(resource_qs.count())*430 + int(hourly_qs.count())*650 + 30000,
        'operations':int(bg_qs.count())*2600 + int(audit_qs.count())*1000 + 90000,
    }
    return {key:max(0,int(value)) for key,value in sizes.items()}

@login_required
@require_GET
def diagnostic_export_estimate(request):
    period,start=_diagnostic_period(request)
    sizes=_diagnostic_export_estimates(period,start)
    selected=_diagnostic_selected_groups(request) or [key for key,_label in _DIAGNOSTIC_EXPORT_GROUPS]
    return JsonResponse({
        'ok':True,'period':period,'sizes':sizes,
        'total_bytes':sum(sizes.get(key,0) for key in selected),
        'groups':[{'key':key,'label':label} for key,label in _DIAGNOSTIC_EXPORT_GROUPS],
    })


def _diagnostic_is_secret_key(key):
    k=str(key or '').strip().lower()
    if k in _DIAGNOSTIC_SECRET_KEYS or k.endswith('_password') or k.endswith('_password_enc') or k.endswith('_secret') or k.endswith('_api_key') or k.endswith('_api_key_enc') or k.endswith('_cookie') or k.endswith('_cookie_enc'):
        return True
    if 'credential' in k:
        return True
    safe_token_keys={
        'tokens','tokens_in','tokens_out','tokens_out_reasoning','reasoning_tokens','thinking_tokens',
        'input_tokens','output_tokens','total_tokens','billable_tokens','billable_token_aggregates','cached_tokens','token_count',
        'token_usage_source','max_input_tokens','max_output_tokens','configured_max_input_tokens',
        'configured_max_output_tokens','cloud_daily_input_tokens','cloud_daily_output_tokens',
    }
    if 'token' in k and k not in safe_token_keys:
        return True
    return False


def _diagnostic_personal_values(profile,user=None):
    values=[]
    def add(value,label):
        value=str(value or '').strip()
        if value and len(value)>=3 and value.casefold() not in {x[0].casefold() for x in values}:
            values.append((value,label))
    add(profile.display_name,'NAME')
    add(profile.application_email,'EMAIL')
    add(profile.phone_number,'PHONE')
    if user is not None:
        add(getattr(user,'first_name',''),'NAME')
        add(getattr(user,'email','') or getattr(user,'username',''),'EMAIL')
    # Exact digits-only phone variants are also common in generated application text.
    digits=''.join(ch for ch in str(profile.phone_number or '') if ch.isdigit())
    if len(digits)>=7: add(digits,'PHONE')
    return sorted(values,key=lambda x:len(x[0]),reverse=True)


def _diagnostic_scrub(value,personal_values=(),key=''):
    if _diagnostic_is_secret_key(key):
        return '[REDACTED SECRET]'
    if isinstance(value,dict):
        return {str(k):_diagnostic_scrub(v,personal_values,str(k)) for k,v in value.items()}
    if isinstance(value,(list,tuple,set)):
        return [_diagnostic_scrub(v,personal_values,key) for v in value]
    if isinstance(value,str):
        out=value
        for needle,label in personal_values:
            try: out=re.sub(re.escape(needle),f'[REDACTED {label}]',out,flags=re.I)
            except Exception: out=out.replace(needle,f'[REDACTED {label}]')
        return out
    return value


def _diagnostic_model_dict(obj,personal_values=(),exclude=()):
    excluded=set(exclude or ())
    data={}
    for field in obj._meta.fields:
        if field.name in excluded: continue
        key=field.name
        try:
            value=getattr(obj,field.attname if field.is_relation else field.name)
        except Exception:
            continue
        if hasattr(value,'name') and not isinstance(value,str):
            value=value.name or ''
        data[key]=_diagnostic_scrub(value,personal_values,key)
    return data


def _diagnostic_recent(qs,start,*fields):
    if not start: return qs
    clause=Q()
    for field in fields:
        clause|=Q(**{f'{field}__gte':start})
    return qs.filter(clause)


def _diagnostic_error_signature(text):
    line=(str(text or '').strip().splitlines() or [''])[0].strip()
    line=re.sub(r'\b\d{2,}\b','<n>',line)
    line=re.sub(r'https?://\S+','<url>',line)
    return line[:260] or 'Unspecified error'


def _diagnostic_add_error(error_rows,component,at,text,context=None):
    text=str(text or '').strip()
    if not text: return
    error_rows.append({'component':component,'at':at,'error':text,'context':context or {}})


def _diagnostic_safe_ai_event(row,personal_values=()):
    """Export AI metadata plus exact manual re-evaluation prompt/output for forensics.

    Manual re-evaluation is a destructive classification path, so its diagnostic row must
    show the actual candidate/Resume context that reached the model. Other AI request bodies
    remain omitted to keep the support archive bounded.
    """
    meta=row.metadata if isinstance(row.metadata,dict) else {}
    safe_meta={}
    for key in (
        'response_issue_code','response_issue_detail','warning_code','warning_detail','response_recovered','recovered_item_count','recovery_wrapper_key','discarded_incomplete_trailing_item','request_timeout_seconds','token_usage_source','input_was_truncated',
        'input_was_truncated_by_log','configured_max_input_tokens','configured_max_output_tokens','operation',
        'discovery_mode','campaign_id','campaign_run_id','subject_type','subject_id','http_status','thinking_mode',
    ):
        if key in meta:
            safe_meta[key]=_diagnostic_scrub(meta.get(key),personal_values,key)
    out={
        'id':row.pk,'at':row.at,'status':row.status,'provider':row.provider,'model':row.model,'stage':row.stage,
        'runtime':row.runtime,'subject_type':row.subject_type,'subject_id':row.subject_id,
        'subject_label':_diagnostic_scrub(row.subject_label,personal_values),'tokens_in':row.tokens_in,
        'tokens_out':row.tokens_out,'reasoning_tokens':row.reasoning_tokens,'web_search_queries':row.web_search_queries,
        'token_usage_source':row.token_usage_source,'duration_ms':row.duration_ms,'ok':row.ok,
        'error':_diagnostic_scrub(row.error,personal_values),'metadata':safe_meta,
        'input_chars':len(row.input_text or ''),'output_chars':len(row.output_text or ''),'raw_output_chars':len(getattr(row,'raw_output_text','') or ''),
    }
    manual_reevaluation=(
        str(row.subject_label or '').casefold().startswith('manual ') and
        're-evaluation' in str(row.subject_label or '').casefold()
    )
    if manual_reevaluation:
        out.update({
            'manual_reevaluation_payload_exported':True,
            'input_text':_diagnostic_scrub(row.input_text or '',personal_values,'input_text'),
            'output_text':_diagnostic_scrub(row.output_text or '',personal_values,'output_text'),
            'raw_output_text':_diagnostic_scrub(getattr(row,'raw_output_text','') or '',personal_values,'raw_output_text'),
        })
    return out


def _diagnostic_candidate_context(profile,personal_values=()):
    """Candidate evidence needed to reproduce discovery/re-evaluation decisions."""
    docs=extract_active_cv_texts()
    try:
        search_profile=build_search_profile()
    except Exception as exc:
        search_profile={'error':str(exc)[:500],'skills':[],'role_families':[]}
    return {
        'candidate_profile':_diagnostic_model_dict(profile,personal_values,exclude={'display_name','application_email','phone_number'}),
        'active_resumes':[
            {
                'id':d.get('id'),
                'label':_diagnostic_scrub(d.get('label') or '',personal_values,'label'),
                'original_name':_diagnostic_scrub(d.get('name') or '',personal_values,'original_name'),
                'parsed_text':_diagnostic_scrub(d.get('text') or '',personal_values,'parsed_text'),
            }
            for d in docs
        ],
        'effective_search_profile':{
            'skills':_diagnostic_scrub(search_profile.get('skills') or [],personal_values,'skills'),
            'role_families':_diagnostic_scrub(search_profile.get('role_families') or [],personal_values,'role_families'),
            'cv_focus':_diagnostic_scrub(search_profile.get('cv_focus') or [],personal_values,'cv_focus'),
        },
    }


def _diagnostic_chatbot_message(row,personal_values=()):
    """Export complete Chatbot message bodies for conversation-quality diagnostics.

    The surrounding diagnostic scrub still redacts configured secrets and known applicant/admin
    identity values, but message text is otherwise preserved without truncation.
    """
    return {
        'id':row.pk,
        'session_key':_diagnostic_scrub(row.session_key,personal_values,'session_key'),
        'role':row.role,
        'text':_diagnostic_scrub(row.text,personal_values,'text'),
        'links':_diagnostic_scrub(row.links if isinstance(row.links,list) else [],personal_values,'links'),
        'source_provider':row.source_provider,
        'source_model':row.source_model,
        'at':row.at,
    }


def _diagnostic_safe_background_job(job,personal_values=()):
    result=job.result if isinstance(job.result,dict) else {}
    safe_result={}
    for key in (
        'state','wait_reason','wait_started_at','last_wait_at','next_retry_at','waited_seconds','retry_count',
        'blocking_campaign_run_id','blocking_campaign_id','blocking_campaign_name','blocking_campaign_stage',
        'campaign_run_id','campaign_id','opportunity_id','lead_id','market_lead_id','contact_id','application_id',
        'results_seen','new_leads','created','updated','skipped','expired','watchdog','watchdog_at','stopped_reason',
    ):
        if key in result:
            safe_result[key]=_diagnostic_scrub(result.get(key),personal_values,key)
    return {
        'id':job.pk,'kind':job.kind,'label':_diagnostic_scrub(job.label,personal_values),'status':job.status,
        'celery_task_id':job.celery_task_id,'progress':job.progress,'message':_diagnostic_scrub(job.message,personal_values),
        'result_summary':safe_result,'error':_diagnostic_scrub(job.error,personal_values),'created_at':job.created_at,
        'started_at':job.started_at,'finished_at':job.finished_at,
    }


def _diagnostic_safe_performance_run(row,personal_values=()):
    return {
        'id':row.pk,'kind':row.kind,'provider':row.provider,'model':row.model,'device':row.device,'ok':row.ok,
        'latency_ms':row.latency_ms,'tokens_in':row.tokens_in,'tokens_out':row.tokens_out,
        'bytes_downloaded':row.bytes_downloaded,'input_url':_diagnostic_scrub(row.input_url,personal_values),
        'input_chars':len(row.input_text or ''),'output_chars':len(row.output_text or ''),
        'metadata':_diagnostic_scrub(row.metadata or {},personal_values),'error':_diagnostic_scrub(row.error,personal_values),
        'created_at':row.created_at,
    }


def _diagnostic_safe_diagnostic_run(row,personal_values=()):
    criteria=row.criteria if isinstance(row.criteria,dict) else {}
    result=row.result if isinstance(row.result,dict) else {}
    selected={}
    for key in (
        'provider','model','source','status','results_seen','results','unique','duplicates','errors','error_count',
        'opportunities_found','leads_found','raw_hits','consolidated_hits','latency_ms','ok','message','state',
    ):
        value=result.get(key)
        # A key named results is safe only when it is an aggregate scalar count. Raw
        # result arrays are deliberately represented by their length instead.
        if key=='results' and isinstance(value,(list,dict)):
            selected['result_item_count']=len(value)
        elif isinstance(value,(str,int,float,bool)) or value is None:
            selected[key]=_diagnostic_scrub(value,personal_values,key)
    return {
        'id':row.pk,'kind':row.kind,'started_at':row.started_at,'finished_at':row.finished_at,'ok':row.ok,
        'criteria_keys':sorted(str(k) for k in criteria.keys())[:100],
        'result_keys':sorted(str(k) for k in result.keys())[:100],
        'result_summary':selected,'error':_diagnostic_scrub(row.error,personal_values),
    }


def _diagnostic_safe_generated_text(row,personal_values=()):
    return {
        'id':row.pk,'application_id':row.application_id,'kind':row.kind,'provider':row.provider,'model':row.model,
        'subject_chars':len(row.subject or ''),'body_chars':len(row.body or ''),
        'metadata':_diagnostic_scrub(row.metadata or {},personal_values),'created_at':row.created_at,
    }


def _diagnostic_safe_application(row,personal_values=()):
    data=_diagnostic_model_dict(row,personal_values,exclude={'email_subject','email_body','website_answers'})
    data['generated_email_subject_chars']=len(row.email_subject or '')
    data['generated_email_body_chars']=len(row.email_body or '')
    try: data['website_answer_count']=len(row.website_answers or {})
    except Exception: data['website_answer_count']=0
    data['record_type']='outreach' if (row.opportunity.extracted_facts or {}).get('outreach') else 'application'
    data['company']=row.opportunity.company; data['role']=row.opportunity.title
    data['opportunity_user_deleted']=row.opportunity.user_deleted
    return data


def _diagnostic_safe_campaign_run(run,personal_values=()):
    result=run.result if isinstance(run.result,dict) else {}
    criteria=run.criteria if isinstance(run.criteria,dict) else {}
    selected_keys=(
        'discovery_mode','execution_path','execution_provider','execution_model','cv_count','raw_hits','consolidated_hits',
        'duplicates_merged_before_enrichment','job_board_candidates_dropped','duplicates','unique','opportunities_found',
        'leads_found','new_leads','error_count','deep_researched','cloud_urls_returned','cloud_urls_inspected',
        'cloud_verified_candidates','cloud_unresolved_after_retries','cloud_hidden_lead_candidates',
        'cloud_hidden_leads_qualified','cloud_hidden_leads_rejected','cloud_contact_candidates','cloud_contacts_validated',
        'cloud_contacts_rejected','cloud_hidden_leads_created','contacts_created','cloud_persistence_rejections',
    )
    result_summary={k:_diagnostic_scrub(result.get(k),personal_values,k) for k in selected_keys if k in result}
    result_summary['provider_count']=len(result.get('providers') or []) if isinstance(result.get('providers'),list) else 0
    result_summary['providers']=[str(x)[:120] for x in (result.get('providers') or [])[:12]] if isinstance(result.get('providers'),list) else []
    result_summary['model_count']=len(result.get('models') or []) if isinstance(result.get('models'),list) else 0
    result_summary['models']=[str(x)[:200] for x in (result.get('models') or [])[:12]] if isinstance(result.get('models'),list) else []
    queries=result.get('queries') if isinstance(result.get('queries'),list) else []
    if not queries and isinstance(run.query_plan,dict):
        queries=run.query_plan.get('queries') if isinstance(run.query_plan.get('queries'),list) else []
    result_summary['query_count']=len(queries)
    raw=int(result.get('raw_hits') or 0); unique=int(result.get('unique') or 0)
    retained=int(result.get('opportunities_found') or 0)+int(result.get('leads_found') or 0)
    result_summary['raw_to_unique_pct']=round(unique*100/raw,2) if raw else 0
    result_summary['raw_to_retained_pct']=round(retained*100/raw,2) if raw else 0
    return {
        'id':run.pk,'campaign_id':run.campaign_id,'campaign_name':run.campaign.name if run.campaign else '',
        'status':run.status,'celery_task_id':run.celery_task_id,'progress':run.progress,
        'message':_diagnostic_scrub(run.message,personal_values),'stage':run.stage,
        'execution_provider':run.execution_provider,'execution_model':run.execution_model,
        'stall_reason':_diagnostic_scrub(run.stall_reason,personal_values),'error':_diagnostic_scrub(run.error,personal_values),
        'created_at':run.created_at,'started_at':run.started_at,'heartbeat_at':run.heartbeat_at,'finished_at':run.finished_at,
        'discovery_mode':str(result.get('discovery_mode') or criteria.get('discovery_mode') or ''),
        'selectivity':_diagnostic_scrub(result.get('selectivity') or criteria.get('selectivity') or {},personal_values,'selectivity'),
        'result_summary':result_summary,
    }


def _build_diagnostic_export_response(request):
    """Read-only, anonymized ScoutBox forensic export for offline analysis."""
    period,start=_diagnostic_period(request)
    # Diagnostic exports now have two independent content groups. The old ``compact``
    # query flag is accepted as a records-only compatibility alias, but new requests
    # must explicitly select at least one group.
    legacy_compact=(request.GET.get('compact') or '')=='1'
    selected_groups=_diagnostic_selected_groups(request)
    category_mode=bool(selected_groups)
    selection_present=category_mode or legacy_compact or ('include_records' in request.GET) or ('include_diagnostics' in request.GET)
    if category_mode:
        record_groups={'context','opportunities','hidden_leads','contacts','facebook'}
        diagnostic_groups={'context','search','discovery','ai','resources','operations'}
        include_records=bool(record_groups.intersection(selected_groups))
        include_diagnostics=bool(diagnostic_groups.intersection(selected_groups))
    else:
        include_records=legacy_compact or (request.GET.get('include_records') or '')=='1'
        include_diagnostics=(not legacy_compact) and (request.GET.get('include_diagnostics') or '')=='1'
    if not selection_present or not (include_records or include_diagnostics):
        return HttpResponse('Select at least one export content type.',status=400,content_type='text/plain; charset=utf-8')
    profile=Profile.objects.get_or_create(pk=1)[0]
    personal_values=_diagnostic_personal_values(profile,request.user)
    now=timezone.now()

    campaigns=list(Campaign.objects.all().order_by('name'))
    campaign_runs_qs=_diagnostic_recent(CampaignRun.objects.select_related('campaign').all(),start,'created_at','started_at','finished_at').order_by('created_at')
    campaign_runs=list(campaign_runs_qs[:10000])

    opportunity_qs=Opportunity.objects.prefetch_related('campaigns').select_related('source').all()
    # The selected period for ScoutBox *records* means when a record entered ScoutBox,
    # not when a background health/enrichment job most recently touched it. Otherwise a
    # 24-hour export can accidentally include almost the entire retained database.
    if start:
        opportunity_qs=opportunity_qs.filter(
            Q(first_seen_by_portal__gte=start) |
            Q(first_seen_by_portal__isnull=True,created_at__gte=start)
        )
    opportunities=list(opportunity_qs.order_by('created_at')[:15000])
    opportunity_ids=[x.pk for x in opportunities]

    evidence=list(OpportunityEvidence.objects.filter(opportunity_id__in=opportunity_ids).order_by('observed_at')[:30000]) if opportunity_ids else []

    lead_qs=CompanyLead.objects.prefetch_related('campaigns').select_related('source').all()
    if start: lead_qs=lead_qs.filter(created_at__gte=start)
    leads=list(lead_qs.order_by('created_at')[:15000])
    lead_ids=[x.pk for x in leads]

    application_qs=Application.objects.select_related('opportunity','cv','cover_letter').all()
    if start:
        application_qs=application_qs.filter(Q(date_added__gte=start)|Q(date_added__isnull=True,created_at__gte=start))
    applications=list(application_qs.order_by('created_at')[:15000])
    application_ids=[x.pk for x in applications]

    text_versions=list(GeneratedTextVersion.objects.filter(application_id__in=application_ids).order_by('created_at')[:20000]) if application_ids else []
    prepared_files=list(PreparedApplicationFile.objects.filter(application_id__in=application_ids).order_by('created_at')[:20000]) if application_ids else []
    mail_qs=MailEvent.objects.select_related('application').all()
    if start:
        mail_qs=mail_qs.filter(occurred_at__gte=start)
    mail_events=list(mail_qs.order_by('occurred_at')[:20000])

    contact_qs=Contact.objects.all()
    if start: contact_qs=contact_qs.filter(created_at__gte=start)
    contacts=list(contact_qs.order_by('created_at')[:15000])

    facebook_page_qs=FacebookPage.objects.all()
    if start:
        facebook_page_qs=facebook_page_qs.filter(Q(discovered_at__gte=start)|Q(deleted_at__gte=start))
    facebook_pages=list(facebook_page_qs.order_by('discovered_at','pk')[:15000])

    tracking_link_qs=TrackingLink.objects.select_related('rule','application__opportunity').all()
    if start:
        tracking_link_qs=tracking_link_qs.filter(Q(created_at__gte=start)|Q(deleted_at__gte=start))
    tracking_links=list(tracking_link_qs.order_by('created_at','pk')[:15000])

    import_qs=ImportCandidate.objects.all()
    if start: import_qs=import_qs.filter(created_at__gte=start)
    import_candidates=list(import_qs.order_by('created_at')[:15000])

    provider_stats_qs=SearchProviderStat.objects.select_related('source').all()
    if start: provider_stats_qs=provider_stats_qs.filter(day__gte=start.date())
    provider_stats=list(provider_stats_qs.order_by('day','source__name')[:30000])

    cloud_daily_qs=CloudBudgetUsage.objects.all()
    if start: cloud_daily_qs=cloud_daily_qs.filter(day__gte=start.date())
    cloud_daily=list(cloud_daily_qs.order_by('day')[:10000])
    cloud_run_qs=CloudRunUsage.objects.select_related('campaign_run').all()
    if start: cloud_run_qs=cloud_run_qs.filter(campaign_run__created_at__gte=start)
    cloud_runs=list(cloud_run_qs.order_by('campaign_run__created_at')[:10000])

    resource_qs=ResourceSample.objects.all()
    if start: resource_qs=resource_qs.filter(at__gte=start)
    resource_sample_total=resource_qs.count()
    resource_samples=list(resource_qs.order_by('-at')[:5000])
    resource_samples.reverse()
    resource_export_first_at=resource_samples[0].at if resource_samples else None
    resource_export_last_at=resource_samples[-1].at if resource_samples else None
    resource_hourly_qs=ResourceHourly.objects.all()
    if start: resource_hourly_qs=resource_hourly_qs.filter(hour__gte=start)
    resource_hourly_total=resource_hourly_qs.count()
    resource_hourly=list(resource_hourly_qs.order_by('-hour')[:5000]); resource_hourly.reverse()

    usage_qs=UsageMetric.objects.all()
    if start: usage_qs=usage_qs.filter(at__gte=start)
    usage_aggregate=list(usage_qs.values('category','provider','model','stage').annotate(requests=Sum('requests'),tokens_in=Sum('tokens_in'),tokens_out=Sum('tokens_out'),reasoning_tokens=Sum('reasoning_tokens'),web_search_queries=Sum('web_search_queries'),pages=Sum('pages'),errors=Sum('errors'),bytes_downloaded=Sum('bytes_downloaded')).order_by('category','provider','model','stage')[:10000])
    usage_errors=list(usage_qs.filter(errors__gt=0).order_by('-at')[:3000])

    background_qs=BackgroundJob.objects.all()
    if start: background_qs=background_qs.filter(Q(created_at__gte=start)|Q(started_at__gte=start)|Q(finished_at__gte=start))
    background_jobs=list(background_qs.order_by('created_at')[:10000])
    diagnostic_qs=DiagnosticRun.objects.all()
    if start: diagnostic_qs=diagnostic_qs.filter(Q(started_at__gte=start)|Q(finished_at__gte=start))
    diagnostic_runs=list(diagnostic_qs.order_by('started_at')[:5000])
    performance_qs=PerformanceRun.objects.all()
    if start: performance_qs=performance_qs.filter(created_at__gte=start)
    performance_runs=list(performance_qs.order_by('created_at')[:5000])
    audit_qs=AuditLog.objects.all()
    if start: audit_qs=audit_qs.filter(at__gte=start)
    audit_rows=list(audit_qs.order_by('at')[:10000])
    addressbook_promotion_outcomes={'provenance_contacts':Contact.objects.exclude(origin_provenance={}).exclude(origin_provenance__isnull=True).count()}
    chatbot_qs=ChatbotMessage.objects.all()
    if start: chatbot_qs=chatbot_qs.filter(at__gte=start)
    chatbot_rows=list(chatbot_qs.order_by('at'))

    ai_qs=AIRequestLog.objects.all()
    if start: ai_qs=ai_qs.filter(at__gte=start)
    ai_ids=[]
    # Manual re-evaluation request rows are forensic evidence for Keep/Recycle decisions,
    # so retain them before the general failure/related/recent caps are applied. This also
    # keeps Address Book re-evaluations visible in diagnostics-only exports where record IDs
    # are intentionally omitted from the payload.
    ai_ids.extend(
        ai_qs.filter(subject_label__istartswith='Manual ',subject_label__icontains='re-evaluation')
        .order_by('-at').values_list('pk',flat=True)[:3000]
    )
    ai_ids.extend(ai_qs.filter(ok=False).order_by('-at').values_list('pk',flat=True)[:2000])
    related_subject_ids=[str(x) for x in opportunity_ids+lead_ids+application_ids]
    if related_subject_ids:
        ai_ids.extend(ai_qs.filter(subject_id__in=related_subject_ids).order_by('-at').values_list('pk',flat=True)[:2000])
    ai_ids.extend(ai_qs.order_by('-at').values_list('pk',flat=True)[:1500])
    ai_ids=list(dict.fromkeys(int(x) for x in ai_ids))[:5000]
    ai_logs=list(AIRequestLog.objects.filter(pk__in=ai_ids).order_by('at'))

    # Discovery-yield diagnostics are intentionally aggregate-only. We retain stage,
    # provider/model, selected classification values and rejection reasons, but never
    # export raw search-result payloads or AI prompt/output bodies.
    ai_status_totals={row['status']:int(row['n'] or 0) for row in ai_qs.values('status').annotate(n=Count('id'))}
    ai_route_health=list(ai_qs.values('stage','provider','model','status').annotate(
        requests=Count('id'),avg_duration_ms=Avg('duration_ms'),tokens_in=Sum('tokens_in'),tokens_out=Sum('tokens_out'),
        reasoning_tokens=Sum('reasoning_tokens'),web_search_queries=Sum('web_search_queries'),
    ).order_by('-requests','stage','provider','model')[:5000])
    for row in ai_route_health:
        row['requests']=int(row.get('requests') or 0)
        row['avg_duration_ms']=int(round(float(row.get('avg_duration_ms') or 0)))
        for key in ('tokens_in','tokens_out','reasoning_tokens','web_search_queries'):
            row[key]=int(row.get(key) or 0)


    # Billing-forensics aggregates. AIRequestLog is the canonical per-call provider
    # accounting because it preserves provider-reported input, visible output and
    # reasoning/thinking tokens. UsageMetric and CloudBudgetUsage are exported beside it
    # as independent reconciliation sources; they intentionally are not summed together.
    def _token_aggregate_rows(qset, dimensions, *, include_usage_source=False):
        dims=list(dimensions)
        if include_usage_source and 'token_usage_source' not in dims:
            dims.append('token_usage_source')
        rows=list(qset.values(*dims).annotate(
            requests=Count('id'),tokens_in=Sum('tokens_in'),tokens_out=Sum('tokens_out'),
            reasoning_tokens=Sum('reasoning_tokens'),web_search_queries=Sum('web_search_queries'),
        ).order_by(*dims)[:20000])
        out=[]
        for row in rows:
            item=dict(row)
            for key in ('requests','tokens_in','tokens_out','reasoning_tokens','web_search_queries'):
                item[key]=int(item.get(key) or 0)
            item['total_tokens']=item['tokens_in']+item['tokens_out']+item['reasoning_tokens']
            item['cloud']=bool(is_cloud_provider(item.get('provider'))) if 'provider' in item else None
            out.append(item)
        return out

    def _token_totals(rows):
        total={'requests':0,'tokens_in':0,'tokens_out':0,'reasoning_tokens':0,'total_tokens':0,'web_search_queries':0}
        for row in rows:
            for key in total:
                total[key]+=int(row.get(key) or 0)
        return total

    ai_billable_by_model=_token_aggregate_rows(ai_qs,['provider','model'],include_usage_source=True)
    ai_billable_by_stage=_token_aggregate_rows(ai_qs,['provider','model','stage'],include_usage_source=True)
    ai_billable_by_day=_token_aggregate_rows(ai_qs.annotate(day=TruncDay('at')),['day','provider','model'],include_usage_source=True)
    ai_billable_totals=_token_totals(ai_billable_by_model)
    ai_billable_cloud_totals=_token_totals([x for x in ai_billable_by_model if x.get('cloud')])

    usage_token_qs=usage_qs.filter(Q(tokens_in__gt=0)|Q(tokens_out__gt=0)|Q(reasoning_tokens__gt=0))
    usage_token_rows=list(usage_token_qs.values('category','provider','model','stage').annotate(
        requests=Sum('requests'),tokens_in=Sum('tokens_in'),tokens_out=Sum('tokens_out'),
        reasoning_tokens=Sum('reasoning_tokens'),web_search_queries=Sum('web_search_queries'),
    ).order_by('category','provider','model','stage')[:20000])
    for row in usage_token_rows:
        for key in ('requests','tokens_in','tokens_out','reasoning_tokens','web_search_queries'):
            row[key]=int(row.get(key) or 0)
        row['total_tokens']=row['tokens_in']+row['tokens_out']+row['reasoning_tokens']
        row['cloud']=bool(is_cloud_provider(row.get('provider')))
    usage_token_totals=_token_totals(usage_token_rows)
    usage_token_cloud_totals=_token_totals([x for x in usage_token_rows if x.get('cloud')])

    cloud_budget_token_totals={
        'days':len(cloud_daily),
        'requests':sum(int(x.requests or 0) for x in cloud_daily),
        'web_searches':sum(int(x.web_searches or 0) for x in cloud_daily),
        'tokens_in':sum(int(x.tokens_in or 0) for x in cloud_daily),
        'tokens_out':sum(int(x.tokens_out or 0) for x in cloud_daily),
        'reasoning_tokens':sum(int(x.reasoning_tokens or 0) for x in cloud_daily),
        'tokens_out_reasoning':sum(int(x.tokens_out_reasoning or 0) for x in cloud_daily),
    }
    cloud_budget_token_totals['total_tokens']=cloud_budget_token_totals['tokens_in']+cloud_budget_token_totals['tokens_out']+cloud_budget_token_totals['reasoning_tokens']

    performance_token_rows=list(performance_qs.filter(Q(tokens_in__gt=0)|Q(tokens_out__gt=0)).values('provider','model','kind').annotate(
        requests=Count('id'),tokens_in=Sum('tokens_in'),tokens_out=Sum('tokens_out')
    ).order_by('provider','model','kind')[:5000])
    for row in performance_token_rows:
        row['requests']=int(row.get('requests') or 0); row['tokens_in']=int(row.get('tokens_in') or 0); row['tokens_out']=int(row.get('tokens_out') or 0)
        row['reasoning_tokens']=0; row['total_tokens']=row['tokens_in']+row['tokens_out']; row['cloud']=bool(is_cloud_provider(row.get('provider')))
    empty_output_qs=ai_qs.filter(Q(metadata__warning_code='empty_output')|Q(status='empty_response',output_text=''))
    empty_output_by_route=list(empty_output_qs.values('stage','provider','model').annotate(
        warnings=Count('id'),avg_duration_ms=Avg('duration_ms')
    ).order_by('-warnings','stage','provider','model')[:1000])
    for row in empty_output_by_route:
        row['warnings']=int(row.get('warnings') or 0)
        row['avg_duration_ms']=int(round(float(row.get('avg_duration_ms') or 0)))

    filter_stage_stats={}; filter_reason_counts=Counter(); filter_purpose_counts=Counter(); filter_disposition_counts=Counter()
    filter_language_counts=Counter(); filter_remote_counts=Counter(); filter_provider_counts=Counter(); filter_rows_scanned=0
    filter_scan_cap=200000
    filter_qs=usage_qs.filter(category='discovery_filter').order_by('at').values('stage','provider','errors','metadata')[:filter_scan_cap]
    for row in filter_qs.iterator(chunk_size=2000):
        filter_rows_scanned+=1
        stage=str(row.get('stage') or 'unknown')[:120]; provider=str(row.get('provider') or '')[:120]
        meta=row.get('metadata') if isinstance(row.get('metadata'),dict) else {}
        stat=filter_stage_stats.setdefault(stage,{'stage':stage,'events':0,'errors':0,'providers':Counter(),'reasons':Counter()})
        stat['events']+=1; stat['errors']+=int(row.get('errors') or 0)
        if provider: stat['providers'][provider]+=1; filter_provider_counts[provider]+=1
        reason=str(meta.get('reason') or '').strip()[:300]
        if reason: stat['reasons'][reason]+=1; filter_reason_counts[(stage,reason)]+=1
        purpose=str(meta.get('purpose') or '').strip().lower()[:80]
        if purpose: filter_purpose_counts[purpose]+=1
        disposition=str(meta.get('disposition') or '').strip().lower()[:80]
        if disposition: filter_disposition_counts[disposition]+=1
        language=str(meta.get('language_code') or '').strip().lower()[:32]
        if language: filter_language_counts[language]+=1
        remote=str(meta.get('remote_status') or '').strip().lower()[:40]
        if remote: filter_remote_counts[remote]+=1
    discovery_filter_stages=[]
    for stage,stat in filter_stage_stats.items():
        discovery_filter_stages.append({
            'stage':stage,'events':stat['events'],'errors':stat['errors'],
            'providers':[{'provider':name,'events':count} for name,count in stat['providers'].most_common(12)],
            'top_reasons':[{'reason':reason,'count':count} for reason,count in stat['reasons'].most_common(15)],
        })
    discovery_filter_stages.sort(key=lambda x:(-x['events'],x['stage']))
    discovery_filter_reasons=[{'stage':stage,'reason':reason,'count':count} for (stage,reason),count in filter_reason_counts.most_common(200)]

    # Current non-secret configuration is intentionally not period-limited.
    portal_settings=PortalSettings.objects.get_or_create(pk=1)[0]
    facebook=FacebookConfig.objects.get_or_create(pk=1)[0]
    blogcfg=BlogStatsConfig.objects.get_or_create(pk=1)[0]
    source_rows=list(SearchSource.objects.all().order_by('name'))
    ai_configs=list(AIProviderConfig.objects.all().order_by('provider'))
    email_profiles=list(EmailProfile.objects.all().order_by('template'))
    custom_domains=list(CustomSearchDomain.objects.all().order_by('name','domain'))
    tracking_rules=list(TrackingLinkRule.objects.all().order_by('name'))
    documents=list(DocumentAsset.objects.all().order_by('kind','-created_at'))
    blacklist_rows=list(SourceBlacklist.objects.all().order_by('domain'))

    # Search-provider performance and failover evidence derived only from retained rows.
    provider_totals={}
    day_provider={}
    for row in provider_stats:
        name=row.source.name if row.source else f'source:{row.source_id}'
        total=provider_totals.setdefault(name,{'requests':0,'results':0,'unique_results':0,'duplicates':0,'applied_matches':0,'errors':0,'bytes_downloaded':0})
        for field in total: total[field]+=int(getattr(row,field,0) or 0)
        day_provider.setdefault(str(row.day),{})[name]=int(row.requests or 0)
    all_requests=sum(x['requests'] for x in provider_totals.values()) or 0
    for row in provider_totals.values(): row['request_share_pct']=round((row['requests']*100/all_requests),2) if all_requests else 0
    selected_counts=Counter(); run_timeline=[]
    for run in campaign_runs:
        result=run.result or {}; providers=[str(x) for x in (result.get('providers') or []) if str(x).strip()]
        selected_counts.update(providers)
        raw_hits=int(result.get('raw_hits') or 0); unique_hits=int(result.get('unique') or 0)
        retained=int(result.get('opportunities_found') or 0)+int(result.get('leads_found') or 0)
        queries=result.get('queries') if isinstance(result.get('queries'),list) else []
        if not queries and isinstance(run.query_plan,dict):
            queries=run.query_plan.get('queries') if isinstance(run.query_plan.get('queries'),list) else []
        run_timeline.append({
            'run_id':run.pk,'campaign_id':run.campaign_id,'campaign':run.campaign.name if run.campaign else '',
            'at':run.started_at or run.created_at,'status':run.status,'discovery_mode':result.get('discovery_mode') or (run.criteria or {}).get('discovery_mode',''),
            'selectivity':_diagnostic_scrub(result.get('selectivity') or (run.criteria or {}).get('selectivity') or {},personal_values,'selectivity'),
            'providers':providers,'query_count':len(queries),'raw_hits':raw_hits,'consolidated_hits':int(result.get('consolidated_hits') or 0),
            'unique':unique_hits,'opportunities_found':int(result.get('opportunities_found') or 0),'leads_found':int(result.get('leads_found') or 0),
            'raw_to_unique_pct':round(unique_hits*100/raw_hits,2) if raw_hits else 0,
            'raw_to_retained_pct':round(retained*100/raw_hits,2) if raw_hits else 0,
            'error_count':int(result.get('error_count') or len(result.get('errors') or [])),'errors':_diagnostic_scrub(result.get('errors') or [],personal_values),
        })
    dominant_by_day=[]
    for day,counts in sorted(day_provider.items()):
        if counts:
            provider,requests=max(counts.items(),key=lambda x:x[1])
            total=sum(counts.values())
            dominant_by_day.append({'day':day,'provider':provider,'requests':requests,'share_pct':round(requests*100/total,2) if total else 0,'all_provider_requests':counts})

    # Campaign effectiveness summary connects discovery runs to retained/deleted user outcomes.
    campaign_summary={c.pk:{'campaign_id':c.pk,'name':c.name,'enabled':c.enabled,'deleted':bool(c.deleted_at),'runs':0,'failed_runs':0,'raw_hits':0,'unique':0,'run_opportunities_found':0,'run_leads_found':0,'run_errors':0,'opportunities_in_export':0,'opportunities_user_deleted':0,'applications_or_outreach':0,'hidden_leads_in_export':0,'hidden_leads_user_deleted':0} for c in campaigns}
    for run in campaign_runs:
        row=campaign_summary.get(run.campaign_id)
        if not row: continue
        result=run.result or {}; row['runs']+=1; row['failed_runs']+=int(run.status=='failed'); row['raw_hits']+=int(result.get('raw_hits') or 0); row['unique']+=int(result.get('unique') or 0); row['run_opportunities_found']+=int(result.get('new_opportunities') if result.get('new_opportunities') is not None else (result.get('unique') or 0)); row['run_leads_found']+=int(result.get('new_leads') or 0); row['run_errors']+=int(result.get('error_count') or len(result.get('errors') or []))
    application_by_opp=Counter(a.opportunity_id for a in applications)
    for opp in opportunities:
        for campaign in opp.campaigns.all():
            row=campaign_summary.get(campaign.pk)
            if not row: continue
            row['opportunities_in_export']+=1; row['opportunities_user_deleted']+=int(bool(opp.user_deleted)); row['applications_or_outreach']+=int(bool(application_by_opp.get(opp.pk)))
    for lead in leads:
        for campaign in lead.campaigns.all():
            row=campaign_summary.get(campaign.pk)
            if not row: continue
            row['hidden_leads_in_export']+=1; row['hidden_leads_user_deleted']+=int(bool(lead.user_deleted))

    provider_result_total=sum(int(x.get('results') or 0) for x in provider_totals.values())
    provider_unique_total=sum(int(x.get('unique_results') or 0) for x in provider_totals.values())
    provider_duplicate_total=sum(int(x.get('duplicates') or 0) for x in provider_totals.values())
    provider_applied_total=sum(int(x.get('applied_matches') or 0) for x in provider_totals.values())
    provider_error_total=sum(int(x.get('errors') or 0) for x in provider_totals.values())
    campaign_raw_total=sum(int((r.result or {}).get('raw_hits') or 0) for r in campaign_runs)
    campaign_consolidated_total=sum(int((r.result or {}).get('consolidated_hits') or 0) for r in campaign_runs)
    campaign_unique_total=sum(int((r.result or {}).get('unique') or 0) for r in campaign_runs)
    campaign_opportunity_total=sum(int((r.result or {}).get('new_opportunities') if (r.result or {}).get('new_opportunities') is not None else ((r.result or {}).get('unique') or 0)) for r in campaign_runs)
    campaign_lead_total=sum(int((r.result or {}).get('new_leads') or 0) for r in campaign_runs)
    campaign_retained_total=campaign_opportunity_total+campaign_lead_total
    ai_total=sum(ai_status_totals.values())
    empty_output_total=empty_output_qs.count()
    discovery_filter_total=usage_qs.filter(category='discovery_filter').count()
    forum_starvation_hours=max(2,min(24,int(os.getenv('SCOUTBOX_FORUM_STARVATION_HOURS','6') or 6)))
    latest_forum_diag=None
    try:
        latest_forum_diag=CampaignRun.objects.filter(criteria__forum_only=True).order_by('-finished_at','-created_at').first()
    except Exception:
        for candidate in CampaignRun.objects.order_by('-created_at')[:2000]:
            if isinstance(candidate.criteria,dict) and candidate.criteria.get('forum_only'):
                latest_forum_diag=candidate; break
    forum_last_at=((latest_forum_diag.finished_at or latest_forum_diag.started_at or latest_forum_diag.created_at) if latest_forum_diag else None)
    forum_age_hours=(round(max(0,(timezone.now()-forum_last_at).total_seconds())/3600,2) if forum_last_at else None)
    forum_scheduler_diag={
        'last_forum_run_id':latest_forum_diag.pk if latest_forum_diag else None,
        'last_forum_at':forum_last_at,
        'last_forum_status':latest_forum_diag.status if latest_forum_diag else '',
        'hours_since_last_forum':forum_age_hours,
        'starvation_threshold_hours':forum_starvation_hours,
        'starvation_override_due':bool(forum_age_hours is None or forum_age_hours>=forum_starvation_hours),
        'policy':'one bounded forum source every ~15 minutes; HTTP acquisition stays separate from primary AI capacity and qualification yields when AI capacity is unavailable',
    }
    discovery_pipeline={
        'forum_scheduler':forum_scheduler_diag,
        'search_provider_funnel':{
            'requests':all_requests,'returned_results':provider_result_total,'provider_unique_results':provider_unique_total,
            'provider_duplicates':provider_duplicate_total,'applied_matches':provider_applied_total,'errors':provider_error_total,
            'returned_to_unique_pct':round(provider_unique_total*100/provider_result_total,2) if provider_result_total else 0,
            'returned_to_applied_pct':round(provider_applied_total*100/provider_result_total,2) if provider_result_total else 0,
        },
        'campaign_funnel':{
            'runs':len(campaign_runs),'raw_hits':campaign_raw_total,'consolidated_hits':campaign_consolidated_total,
            'unique':campaign_unique_total,'opportunities_found':campaign_opportunity_total,'hidden_leads_found':campaign_lead_total,
            'retained_total':campaign_retained_total,
            'raw_to_unique_pct':round(campaign_unique_total*100/campaign_raw_total,2) if campaign_raw_total else 0,
            'raw_to_retained_pct':round(campaign_retained_total*100/campaign_raw_total,2) if campaign_raw_total else 0,
        },
        'filtering':{
            'events_total':discovery_filter_total,'events_scanned':filter_rows_scanned,'scan_capped':discovery_filter_total>filter_rows_scanned,
            'stages':discovery_filter_stages,'top_stage_reasons':discovery_filter_reasons,
            'purpose_counts':dict(filter_purpose_counts),'disposition_counts':dict(filter_disposition_counts),
            'language_counts':dict(filter_language_counts),'remote_status_counts':dict(filter_remote_counts),
            'provider_event_counts':dict(filter_provider_counts),
        },
        'ai_health':{
            'requests_total':ai_total,'status_counts':ai_status_totals,'empty_responses':empty_output_total,
            'response_issue_rate_pct':round((int(ai_status_totals.get('empty_response',0))+int(ai_status_totals.get('recovered_response',0))+int(ai_status_totals.get('malformed_response',0)))*100/ai_total,2) if ai_total else 0,
            'failed_rate_pct':round(int(ai_status_totals.get('failed',0))*100/ai_total,2) if ai_total else 0,
            'empty_output_rate_pct':round(empty_output_total*100/ai_total,2) if ai_total else 0,
            'by_stage_provider_model_status':ai_route_health,
            'empty_output_by_stage_provider_model':empty_output_by_route,
        },
        'campaign_runs':run_timeline,
    }

    chatbot_summary=list(chatbot_qs.values('role','source_provider','source_model').annotate(messages=Count('id')).order_by('-messages','role','source_provider','source_model')[:1000])
    for row in chatbot_summary: row['messages']=int(row.get('messages') or 0)
    usage_error_events=[]
    for row in usage_errors:
        meta=row.metadata if isinstance(row.metadata,dict) else {}
        usage_error_events.append({
            'id':row.pk,'at':row.at,'category':row.category,'provider':row.provider,'model':row.model,'stage':row.stage,
            'errors':row.errors,'reason':_diagnostic_scrub(str(meta.get('reason') or '')[:500],personal_values),
            'error':_diagnostic_scrub(str(meta.get('error') or '')[:1000],personal_values),
        })

    # Central error index keeps rare dependency/runtime failures discoverable even when
    # they are buried in a low-frequency subsystem table.
    error_rows=[]
    for run in campaign_runs:
        _diagnostic_add_error(error_rows,'campaign_run',run.finished_at or run.created_at,run.error,{'run_id':run.pk,'campaign':run.campaign.name if run.campaign else ''})
        for err in (run.result or {}).get('errors') or []: _diagnostic_add_error(error_rows,'campaign_provider',run.finished_at or run.created_at,err,{'run_id':run.pk,'campaign':run.campaign.name if run.campaign else ''})
    for job in background_jobs: _diagnostic_add_error(error_rows,'background_job',job.finished_at or job.created_at,job.error,{'job_id':job.pk,'kind':job.kind,'label':job.label})
    for row in diagnostic_runs: _diagnostic_add_error(error_rows,'diagnostic_run',row.finished_at or row.started_at,row.error,{'diagnostic_id':row.pk,'kind':row.kind})
    for row in performance_runs: _diagnostic_add_error(error_rows,'performance_run',row.created_at,row.error,{'performance_id':row.pk,'kind':row.kind,'provider':row.provider,'model':row.model})
    for row in ai_logs: _diagnostic_add_error(error_rows,'ai_request',row.at,row.error,{'ai_log_id':row.pk,'provider':row.provider,'model':row.model,'stage':row.stage})
    for row in provider_stats: _diagnostic_add_error(error_rows,'search_provider',timezone.make_aware(datetime.combine(row.day,datetime.min.time())),row.last_error,{'provider':row.source.name if row.source else str(row.source_id),'errors':row.errors})
    for row in mail_events: _diagnostic_add_error(error_rows,'mail',row.occurred_at,row.delivery_error,{'mail_event_id':row.pk,'kind':row.kind,'status':row.delivery_status})
    signature_counts=Counter(_diagnostic_error_signature(x['error']) for x in error_rows)

    def serialize_campaign(c):
        d=_diagnostic_model_dict(c,personal_values); return d
    def serialize_run(r):
        return _diagnostic_safe_campaign_run(r,personal_values)
    def serialize_opp(o):
        d=_diagnostic_model_dict(o,personal_values); d['campaign_ids']=[c.pk for c in o.campaigns.all()]; d['campaigns']=[c.name for c in o.campaigns.all()]; d['source_name']=o.source.name if o.source else ''; return d
    def serialize_lead(l):
        d=_diagnostic_model_dict(l,personal_values); d['campaign_ids']=[c.pk for c in l.campaigns.all()]; d['campaigns']=[c.name for c in l.campaigns.all()]; d['source_name']=l.source.name if l.source else ''; return d
    def serialize_app(a):
        return _diagnostic_safe_application(a,personal_values)
    def serialize_facebook_page(row):
        return _diagnostic_model_dict(row,personal_values)
    def serialize_tracking_link(row):
        d=_diagnostic_model_dict(row,personal_values)
        d['rule_name']=row.rule.name if row.rule else ''
        d['application_id']=row.application_id
        d['opportunity_id']=(row.application.opportunity_id if row.application else None)
        d['opportunity_title']=(row.application.opportunity.title if row.application and row.application.opportunity else '')
        return d

    recycled={
        'campaigns':[c.pk for c in campaigns if c.deleted_at and (not start or c.deleted_at>=start)],
        'campaign_templates':[t.pk for t in CampaignTemplate.objects.filter(deleted_at__isnull=False) if not start or t.deleted_at>=start],
        'opportunities':[o.pk for o in opportunities if o.user_deleted],
        'hidden_leads':[l.pk for l in leads if l.user_deleted],
        'applications_outreach':[a.pk for a in applications if a.deleted_at],
        'address_book':[c.pk for c in contacts if c.deleted_at],
        'facebook_pages':[row.pk for row in facebook_pages if row.deleted_at],
        'tracking_links':[row.pk for row in tracking_links if row.deleted_at],
        'blacklist':[b.pk for b in blacklist_rows if b.deleted_at and (not start or b.deleted_at>=start)],
    }

    version='unknown'
    try: version=(Path(settings.BASE_DIR)/'VERSION').read_text().strip()
    except Exception: pass
    payload={
        'export':{
            'format':'scoutbox-diagnostic','format_version':6,'scoutbox_version':version,
            'generated_at':now,'period':period,'from':start,'to':now,
            'read_only':True,'anonymization':'Candidate Profile and active Resume parsed text are retained for fit diagnostics. Applicant/admin name, email and phone values are replaced wherever they match known profile/account values. Company data is retained. Credentials/secrets are always redacted.',
            'content_selection':{
                'candidate_opportunity_contact_data':bool(include_records),
                'operational_logs_diagnostics':bool(include_diagnostics),
                'categories':selected_groups if category_mode else [],
            },
            'selection_notes':{
                'ai_request_logs':'Operational request metadata is exported for retained AI requests. Exact prompt/output bodies are additionally included for manual Opportunity, Hidden Lead and Address Book re-evaluations so destructive fit decisions can be reproduced; those rows are prioritized before the 5,000-row diagnostic cap. Other AI request bodies remain omitted.',
                'discovery_pipeline':'Aggregated provider returns, deduplication, rejection stages/reasons, selected classification values, AI response-issue/failure rates and campaign yield are included without raw pre-persistence search-result arrays.',
                'opportunities_and_leads':'The selected period filters ScoutBox records by date added/first seen, not updated_at, URL-health last_seen or enrichment refreshes; Facebook Pages and Tracking Links use discovered/created time and also include records recycled during the selected period; all records are included when period=all.',
                'generated_ai_content':'Complete Chatbot message text is included for conversation-quality troubleshooting. Generated email/body text, performance prompt/output text and general AI request prompt/output bodies are omitted.',
                'configuration':'Current configuration is included regardless of selected period. Candidate Profile fields, active Resume parsed text and the effective Resume/search vocabulary are included in diagnostic exports for fit/re-evaluation troubleshooting.',
                'runtime_log_limit':'Only errors already retained by ScoutBox database models can be exported; container stdout/stderr that was never persisted is not recoverable here.',
                'billable_tokens':'Aggregated input, visible output and reasoning/thinking token counts are included from every retained token-accounting source. Parallel sources are labelled for reconciliation and must not be summed together.',
            },
        },
        'system':{'python_version':platform.python_version(),'platform':platform.platform(),'scoutbox_version':version},
        'configuration':{
            'portal_settings':_diagnostic_model_dict(portal_settings,personal_values),
            'candidate_profile':_diagnostic_model_dict(profile,personal_values,exclude={'display_name','application_email','phone_number'}),
            'candidate_context':_diagnostic_candidate_context(profile,personal_values),
            'search_sources':[_diagnostic_model_dict(x,personal_values) for x in source_rows],
            'ai_providers':[_diagnostic_model_dict(x,personal_values) for x in ai_configs],
            'email_profiles':[_diagnostic_model_dict(x,personal_values) for x in email_profiles],
            'facebook':_diagnostic_model_dict(facebook,personal_values),
            'blog_statistics':_diagnostic_model_dict(blogcfg,personal_values),
            'custom_search_domains':[_diagnostic_model_dict(x,personal_values) for x in custom_domains],
            'tracking_rules':[_diagnostic_model_dict(x,personal_values) for x in tracking_rules],
            'documents':[{'id':x.pk,'kind':x.kind,'label':_diagnostic_scrub(x.label,personal_values),'original_name':_diagnostic_scrub(x.original_name,personal_values),'notes':_diagnostic_scrub(x.notes,personal_values),'active':x.active,'created_at':x.created_at} for x in documents],
        },
        'campaigns':[serialize_campaign(x) for x in campaigns],
        'campaign_runs':[serialize_run(x) for x in campaign_runs],
        'campaign_effectiveness':list(campaign_summary.values()),
        'discovery_pipeline':discovery_pipeline,
        'opportunities':[serialize_opp(x) for x in opportunities],
        'opportunity_evidence':[_diagnostic_model_dict(x,personal_values) for x in evidence],
        'hidden_leads':[serialize_lead(x) for x in leads],
        'applications_outreach':[serialize_app(x) for x in applications],
        'generated_text_versions':[_diagnostic_safe_generated_text(x,personal_values) for x in text_versions],
        'prepared_application_files':[_diagnostic_model_dict(x,personal_values) for x in prepared_files],
        'mail_events':[_diagnostic_model_dict(x,personal_values) for x in mail_events],
        'address_book':[_diagnostic_model_dict(x,personal_values) for x in contacts],
        'facebook_pages':[serialize_facebook_page(x) for x in facebook_pages],
        'tracking_links':[serialize_tracking_link(x) for x in tracking_links],
        'import_history':[_diagnostic_model_dict(x,personal_values) for x in import_candidates],
        'blacklist':[_diagnostic_model_dict(x,personal_values) for x in blacklist_rows],
        'recycle_bin':recycled,
        'search_engines':{
            'daily_provider_stats':[dict(_diagnostic_model_dict(x,personal_values),source_name=(x.source.name if x.source else '')) for x in provider_stats],
            'provider_totals':provider_totals,
            'selected_in_campaign_runs':dict(selected_counts),
            'campaign_run_provider_timeline':run_timeline,
            'dominant_provider_by_day':dominant_by_day,
            'usage_aggregate':[_diagnostic_scrub(x,personal_values) for x in usage_aggregate],
            'usage_rows_with_errors':usage_error_events,
            'cloud_daily_budget_usage':[_diagnostic_model_dict(x,personal_values) for x in cloud_daily],
            'cloud_campaign_run_usage':[dict(_diagnostic_model_dict(x,personal_values),campaign_run_created_at=x.campaign_run.created_at) for x in cloud_runs],
        },
        'resource_usage':{
            'samples':[_diagnostic_model_dict(x,personal_values) for x in resource_samples],
            'hourly_archive':[_diagnostic_model_dict(x,personal_values) for x in resource_hourly],
            'sample_count':len(resource_samples),
            'exported_sample_count':len(resource_samples),
            'matching_sample_count':resource_sample_total,
            'hourly_archive_count':resource_hourly_total,
            'exported_first_at':resource_export_first_at,
            'exported_last_at':resource_export_last_at,
        },
        'billable_token_aggregates':{
            'note':'Parallel accounting sources are exported for reconciliation and may overlap. Do not add their totals together. AIRequestLog is the canonical per-provider-call view; UsageMetric is telemetry; CloudBudgetUsage is the cloud safety-counter view; PerformanceRun covers retained lab/performance records.',
            'ai_request_log':{
                'totals':ai_billable_totals,
                'cloud_only_totals':ai_billable_cloud_totals,
                'by_provider_model':ai_billable_by_model,
                'by_provider_model_stage':ai_billable_by_stage,
                'by_day_provider_model':ai_billable_by_day,
            },
            'usage_metric':{
                'totals':usage_token_totals,
                'cloud_only_totals':usage_token_cloud_totals,
                'by_category_provider_model_stage':usage_token_rows,
            },
            'cloud_budget_usage':{
                'totals':cloud_budget_token_totals,
                'daily':[_diagnostic_model_dict(x,personal_values) for x in cloud_daily],
            },
            'performance_runs':{
                'totals':_token_totals(performance_token_rows),
                'by_provider_model_kind':performance_token_rows,
            },
        },
        'chatbot':{
            'message_count':chatbot_qs.count(),
            'exported_rows':len(chatbot_rows),
            'capped':False,
            'by_role_provider_model':chatbot_summary,
            'raw_text_exported':True,
            'messages':[_diagnostic_chatbot_message(x,personal_values) for x in chatbot_rows],
        },
        'ai':{
            'request_logs':[_diagnostic_safe_ai_event(x,personal_values) for x in ai_logs],
            'selection':{'exported_rows':len(ai_logs),'recent_total':ai_qs.count(),'capped':ai_qs.count()>len(ai_logs),'raw_prompt_output_exported':'manual_reevaluations_only'},
        },
        'jobs_and_errors':{
            'background_jobs':[_diagnostic_safe_background_job(x,personal_values) for x in background_jobs],
            'diagnostic_runs':[_diagnostic_safe_diagnostic_run(x,personal_values) for x in diagnostic_runs],
            'performance_runs':[_diagnostic_safe_performance_run(x,personal_values) for x in performance_runs],
            'error_index':{
                'total':len(error_rows),
                'by_component':dict(Counter(x['component'] for x in error_rows)),
                'by_signature':[{'signature':sig,'count':count} for sig,count in signature_counts.most_common(200)],
                'events':[_diagnostic_scrub(x,personal_values) for x in sorted(error_rows,key=lambda x:x['at'] or now)[:10000]],
            },
        },
        'audit':[_diagnostic_model_dict(x,personal_values) for x in audit_rows],
        'diagnostic_summary':{
            'campaigns':len(campaigns),'campaign_runs':len(campaign_runs),'failed_campaign_runs':sum(1 for x in campaign_runs if x.status=='failed'),
            'opportunities':len(opportunities),'opportunities_user_deleted':sum(1 for x in opportunities if x.user_deleted),
            'hidden_leads':len(leads),'hidden_leads_user_deleted':sum(1 for x in leads if x.user_deleted),
            'applications_outreach':len(applications),'recycled_applications_outreach':sum(1 for x in applications if x.deleted_at),
            'facebook_pages':len(facebook_pages),'recycled_facebook_pages':sum(1 for x in facebook_pages if x.deleted_at),
            'tracking_links':len(tracking_links),'recycled_tracking_links':sum(1 for x in tracking_links if x.deleted_at),
            'provider_requests':all_requests,'provider_returned_results':provider_result_total,'provider_unique_results':provider_unique_total,
            'provider_applied_matches':provider_applied_total,'provider_with_most_requests':max(provider_totals.items(),key=lambda x:x[1]['requests'])[0] if provider_totals else '',
            'campaign_raw_hits':campaign_raw_total,'campaign_unique':campaign_unique_total,'campaign_opportunities_found':campaign_opportunity_total,
            'campaign_hidden_leads_found':campaign_lead_total,'discovery_filter_events':discovery_filter_total,
            'ai_requests_total':ai_total,'ai_empty_response_count':int(ai_status_totals.get('empty_response',0)),'ai_recovered_response_count':int(ai_status_totals.get('recovered_response',0)),'ai_malformed_response_count':int(ai_status_totals.get('malformed_response',0)),'ai_failed_count':int(ai_status_totals.get('failed',0)),
            'cloud_budget_days':len(cloud_daily),'cloud_campaign_run_usage_rows':len(cloud_runs),'resource_samples':len(resource_samples),
            'stored_error_events':len(error_rows),'ai_request_logs_exported':len(ai_logs),'chatbot_message_count':chatbot_qs.count(),
            'addressbook_promotion_outcomes':addressbook_promotion_outcomes,
        },
    }
    if not category_mode and include_records and not include_diagnostics:
        # Records-only support export: retain candidate/employment/contact records,
        # current configuration/version context and lightweight aggregate counters while
        # omitting operational logs and large diagnostic histories.
        payload['export']['selection_notes']['records_only']='Operational logs, AI request rows, Chatbot bodies, resource samples, provider timelines, generated text/file histories, mail event history and audit/error event bodies are omitted; lightweight aggregate counters remain.'
        payload.pop('campaign_runs',None)
        payload.pop('opportunity_evidence',None)
        payload.pop('generated_text_versions',None)
        payload.pop('prepared_application_files',None)
        payload.pop('mail_events',None)
        payload.pop('import_history',None)
        payload.pop('chatbot',None)
        payload.pop('ai',None)
        payload.pop('jobs_and_errors',None)
        payload.pop('audit',None)
        if isinstance(payload.get('resource_usage'),dict):
            payload['resource_usage'].pop('samples',None)
        if isinstance(payload.get('search_engines'),dict):
            for k in ('daily_provider_stats','campaign_run_provider_timeline','usage_rows_with_errors','cloud_campaign_run_usage'):
                payload['search_engines'].pop(k,None)
        if isinstance(payload.get('discovery_pipeline'),dict):
            payload['discovery_pipeline'].pop('campaign_runs',None)
    elif not category_mode and include_diagnostics and not include_records:
        # Diagnostics-only is intentionally useful for debugging a failing run without
        # exporting the user's candidate/job/contact corpus. Configuration and aggregate
        # pipeline context remain because they are often required to reproduce failures.
        payload['export']['selection_notes']['diagnostics_only']='Retained Opportunity, Hidden Lead, Application, Address Book, Facebook Page, Tracking Link, generated-document and recycle-bin records are omitted. Candidate Profile fields and active Resume parsed text remain intentionally included because they are required to reproduce fit/re-evaluation decisions. Operational logs, telemetry, configuration and aggregate pipeline context remain.'
        for key in ('opportunities','opportunity_evidence','hidden_leads','applications_outreach','generated_text_versions','prepared_application_files','mail_events','address_book','facebook_pages','tracking_links','import_history','recycle_bin'):
            payload.pop(key,None)
        configuration=payload.get('configuration')
        if isinstance(configuration,dict):
            # Candidate Profile and active Resume evidence are deliberately retained in
            # diagnostics-only exports; without them manual fit/recycle decisions cannot
            # be reconstructed from AI metadata.
            pass
        # Prevent diagnostic metadata from leaking a list of record identifiers after
        # the records themselves were deliberately excluded.
        payload.pop('deleted_record_ids',None)
    if category_mode:
        keep={'export','diagnostic_summary'}
        group_keys={
            'context':{'system','configuration','campaigns'},
            'opportunities':{'opportunities','opportunity_evidence','import_history'},
            'hidden_leads':{'hidden_leads'},
            'contacts':{'applications_outreach','generated_text_versions','prepared_application_files','mail_events','address_book'},
            'facebook':{'facebook_pages','tracking_links'},
            'search':{'search_engines'},
            'discovery':{'campaign_runs','campaign_effectiveness','discovery_pipeline','blacklist'},
            'ai':{'billable_token_aggregates','chatbot','ai'},
            'resources':{'resource_usage'},
            'operations':{'jobs_and_errors','audit'},
        }
        for group in selected_groups:
            keep.update(group_keys.get(group,set()))
        if any(group in selected_groups for group in ('opportunities','hidden_leads','contacts','facebook')):
            keep.add('recycle_bin')
        for key in list(payload.keys()):
            if key not in keep:
                payload.pop(key,None)
        payload['export']['selection_notes']['granular_export']='Only the selected diagnostic categories are serialized into this archive. Size estimates shown in Maintenance are approximate uncompressed sizes.'

    payload=_diagnostic_scrub(payload,personal_values)
    local_now=timezone.localtime(now)
    # Use names that reflect the selected content groups without repeating
    # "diagnostic" in both the prefix and the scope. Include HHMMSS on the from/to
    # timestamps so short support windows are visible in the filename itself.
    scope_name=('selected' if category_mode else ('records-and-logs' if include_records and include_diagnostics else ('records' if include_records else 'logs')))
    end_label=local_now.strftime('%Y%m%d-%H%M%S')
    if start:
        start_label=timezone.localtime(start).strftime('%Y%m%d-%H%M%S')
        range_label=f'{start_label}-to-{end_label}'
    else:
        range_label=f'all-to-{end_label}'
    # Milliseconds make repeated exports in the same second unique and avoid browser
    # download-cache filename collisions while keeping the name human-readable.
    stamp=local_now.strftime('%Y%m%d-%H%M%S-%f')[:-3]
    basename=f'scoutbox-support-{scope_name}-{range_label}-generated-{stamp}'
    json_name=basename+'.json'
    json_bytes=json.dumps(payload,cls=DjangoJSONEncoder,ensure_ascii=False,indent=2).encode('utf-8')
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as zf:
        zf.writestr(json_name,json_bytes)
    data=archive.getvalue()
    response=HttpResponse(data,content_type='application/zip')
    response['Content-Disposition']=f'attachment; filename="{basename}.zip"'
    response['Content-Length']=str(len(data))
    response['Cache-Control']='no-store'
    download_token=(request.GET.get('download_token') or '').strip()[:120]
    if download_token and re.fullmatch(r'[A-Za-z0-9_-]{8,120}',download_token):
        # The browser can observe this non-sensitive completion token as soon as the
        # attachment response headers arrive. It lets Maintenance re-enable its
        # controls when the download has actually been triggered, without fetching
        # the archive through JavaScript or changing the export contents.
        response.set_cookie('scoutbox_diagnostic_download',download_token,max_age=120,httponly=False,secure=request.is_secure(),samesite='Lax',path='/')
    return response


@login_required
@require_POST
def export_diagnostic_data(request):
    categories=[]
    for value in request.POST.getlist('category'):
        key=str(value or '').strip().lower()
        if key in _DIAGNOSTIC_EXPORT_GROUP_KEYS and key not in categories:
            categories.append(key)
    include_records=(request.POST.get('include_records') or '')=='1'
    include_diagnostics=(request.POST.get('include_diagnostics') or '')=='1'
    if not categories and not (include_records or include_diagnostics):
        return JsonResponse({'ok':False,'error':'Select at least one export content type.'},status=400)
    period=(request.POST.get('period') or '24h').strip().lower()
    if period not in {'1h','3h','6h','12h','24h','3d','7d','14d','30d','all'}:
        period='24h'
    active=BackgroundJob.objects.filter(
        kind='diagnostic',label='Diagnostic data export',status__in=['queued','running'],
        result__requested_by_user_id=request.user.pk,
    ).order_by('-created_at').first()
    if active:
        return JsonResponse({'ok':True,'job_id':active.pk,'existing':True})
    result={
        'requested_by_user_id':request.user.pk,'period':period,
        'include_records':include_records,'include_diagnostics':include_diagnostics,
        'categories':categories,
        'phase':'queued',
    }
    job=BackgroundJob.objects.create(kind='diagnostic',label='Diagnostic data export',message='Queued',result=result)
    task=diagnostic_export_job.delay(job.pk)
    job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
    return JsonResponse({'ok':True,'job_id':job.pk})


@login_required
@require_GET
def diagnostic_export_download(request,pk):
    job=get_object_or_404(BackgroundJob,pk=pk,kind='diagnostic',label='Diagnostic data export',status='completed')
    result=job.result if isinstance(job.result,dict) else {}
    if int(result.get('requested_by_user_id') or 0)!=int(request.user.pk) and not request.user.is_staff:
        return HttpResponse('Not permitted.',status=403,content_type='text/plain; charset=utf-8')
    storage_name=str(result.get('storage_name') or '')
    filename=str(result.get('filename') or 'scoutbox-support.zip')
    if not storage_name or not default_storage.exists(storage_name):
        return HttpResponse('The diagnostic export is no longer available.',status=410,content_type='text/plain; charset=utf-8')
    response=FileResponse(default_storage.open(storage_name,'rb'),content_type='application/zip',as_attachment=True,filename=filename)
    response['Cache-Control']='no-store'
    return response

def _default_digest_recipient_email():
    return (User.objects.filter(is_active=True,is_staff=True).exclude(email='').order_by('pk').values_list('email',flat=True).first() or '').strip()


def _normalise_portal_root_url(value):
    root=str(value or '').strip().rstrip('/')
    if not root:
        root='http://localhost:8989'
    parsed=urlparse(root)
    if parsed.scheme not in {'http','https'} or not parsed.netloc or not parsed.hostname or parsed.path not in ('','/') or parsed.params or parsed.query or parsed.fragment:
        raise ValidationError('Portal Root URL must be an http(s) origin such as http://localhost:8989 or https://scoutbox.example.com.')
    return root


@login_required
def settings_view(request):
    ps=PortalSettings.objects.get_or_create(pk=1)[0]; cfg=BlogStatsConfig.objects.get_or_create(pk=1,defaults={'enabled':True})[0]
    migrate_legacy_config(cfg)
    # Make the digest destination explicit. Existing installations are initialized on
    # first General-settings load from the first active administrator email.
    if not (ps.digest_recipient_email or '').strip():
        default_recipient=_default_digest_recipient_email()
        if default_recipient:
            ps.digest_recipient_email=default_recipient
            ps.save(update_fields=['digest_recipient_email','updated_at'])
    if not (ps.portal_root_url or '').strip():
        ps.portal_root_url='http://localhost:8989'
        ps.save(update_fields=['portal_root_url','updated_at'])
    if request.method=='POST':
        action=request.POST.get('action')
        if action=='toggle_background': ps.background_paused=not ps.background_paused; ps.save(); messages.success(request,'Automatic tasks paused.' if ps.background_paused else 'Automatic tasks resumed.')
        elif action=='save_system':
            recipient=(request.POST.get('digest_recipient_email') or '').strip() or _default_digest_recipient_email()
            if recipient:
                try: validate_email(recipient)
                except ValidationError:
                    messages.error(request,'Daily digest recipient must be a valid email address.')
                    return redirect(reverse('settings')+'#settings-general')
            try:
                portal_root=_normalise_portal_root_url(request.POST.get('portal_root_url'))
            except ValidationError as exc:
                messages.error(request,str(exc))
                return redirect(reverse('settings')+'#settings-general')
            opportunity_selectivity=(request.POST.get('opportunity_selectivity') or 'balanced').strip().lower()
            lead_selectivity=(request.POST.get('lead_selectivity') or 'balanced').strip().lower()
            contact_selectivity=(request.POST.get('contact_selectivity') or 'balanced').strip().lower()
            if opportunity_selectivity not in {'broad','balanced','specialist'}: opportunity_selectivity='balanced'
            if lead_selectivity not in {'broad','balanced','specialist'}: lead_selectivity='balanced'
            if contact_selectivity not in {'broad','balanced','verified'}: contact_selectivity='balanced'
            ps.opportunity_selectivity=opportunity_selectivity; ps.lead_selectivity=lead_selectivity; ps.contact_selectivity=contact_selectivity
            ps.digest_enabled=bool(request.POST.get('digest_enabled')); ps.digest_hour=max(0,min(23,int(request.POST.get('digest_hour') or 8))); ps.digest_minute=max(0,min(59,int(request.POST.get('digest_minute') or 30))); ps.digest_recipient_email=recipient; ps.portal_root_url=portal_root; ps.max_concurrent_campaigns=max(MAX_CONCURRENT_CAMPAIGNS_LIMITS[0],min(MAX_CONCURRENT_CAMPAIGNS_LIMITS[1],int(request.POST.get('max_concurrent_campaigns') or MAX_CONCURRENT_CAMPAIGNS_DEFAULT))); ps.draft_suppression_days=max(1,int(request.POST.get('draft_suppression_days') or 90)); ps.duplicate_window_days=max(1,int(request.POST.get('duplicate_window_days') or 90)); ps.company_reapply_window_days=max(1,int(request.POST.get('company_reapply_window_days') or 90)); ps.same_company_fit_penalty=max(0,min(100,int(request.POST.get('same_company_fit_penalty') or 20))); ps.same_company_unknown_date_penalty=max(0,min(100,int(request.POST.get('same_company_unknown_date_penalty') or 8))); ps.detailed_log_retention_days=max(14,min(180,int(request.POST.get('detailed_log_retention_days') or 90))); ps.focus_comparison_records=max(25,min(500,int(request.POST.get('focus_comparison_records') or 100))); ps.max_focus_groups=max(5,min(30,int(request.POST.get('max_focus_groups') or 15))); ps.save(); messages.success(request,'General configuration saved.')
        elif action=='send_test_digest':
            recipient=(request.POST.get('digest_recipient_email') or ps.digest_recipient_email or '').strip() or _default_digest_recipient_email()
            if not recipient:
                messages.error(request,'No daily digest recipient is configured.')
            else:
                try:
                    validate_email(recipient)
                    portal_root=_normalise_portal_root_url(request.POST.get('portal_root_url') or ps.portal_root_url)
                    changed=[]
                    if ps.digest_recipient_email != recipient:
                        ps.digest_recipient_email=recipient; changed.append('digest_recipient_email')
                    if ps.portal_root_url != portal_root:
                        ps.portal_root_url=portal_root; changed.append('portal_root_url')
                    if changed:
                        ps.save(update_fields=changed+['updated_at'])
                    digest=build_24h_digest(timezone.now(),test=True)
                    event=send_notification(recipient,digest['subject'],digest['body'],html_body=digest.get('html_body'),metadata_extra={'digest':True,'manual_test':True})
                    pid=getattr(event,'message_id','') or ''
                    messages.success(request,f'Test 24-hour digest accepted for {recipient}. The normal digest schedule was not changed.'+(f' Provider message ID: {pid}.' if pid else ''))
                except ValidationError as exc:
                    messages.error(request,str(exc) or 'Daily digest recipient / Portal Root URL is invalid.')
                except Exception as exc:
                    messages.error(request,f'Test digest could not be sent: {str(exc)[:300]}')
        elif action=='save_features':
            feature_fields=[f.name for f in PortalSettings._meta.fields if f.name.startswith('feature_')]
            for f in feature_fields: setattr(ps,f,bool(request.POST.get(f)))
            ps.save(); messages.success(request,'Optional pipeline feature flags saved.')
        elif action=='features_all':
            for f in [x.name for x in PortalSettings._meta.fields if x.name.startswith('feature_')]: setattr(ps,f,True)
            ps.save(); messages.success(request,'All optional features enabled.')
        elif action=='rebuild_missing_ai_data':
            period=(request.POST.get('period') or '24h').strip().lower()
            if period=='today': period='24h'
            period_labels={'24h':'Last 24 hours','3d':'Last 3 days','7d':'Last 7 days','14d':'Last 2 weeks','30d':'Last 30 days','all':'All time'}
            if ps.discovery_mode!='cloud_web':
                messages.error(request,'Rebuild Missing AI Data is available only when AI & Discovery > Discovery Method is set to Cloud Web.')
            elif period not in period_labels:
                messages.error(request,'Choose a valid rebuild period.')
            elif BackgroundJob.objects.filter(label='Rebuild Missing AI Data',status__in=['queued','running']).exists():
                messages.warning(request,'A Rebuild Missing AI Data task is already queued or running.')
            else:
                job=BackgroundJob.objects.create(kind='enrich',label='Rebuild Missing AI Data',message='Queued',result={'maintenance_rebuild':True,'period':period})
                task=rebuild_missing_ai_data_job.delay(job.pk,period)
                job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
                messages.success(request,f'Rebuild Missing AI Data queued for {period_labels[period]}. Existing populated values will be preserved.')
        elif action=='recover_stalled_operations':
            confirmation=(request.POST.get('confirm_text') or '').strip().upper()
            if confirmation!='RECOVER':
                messages.error(request,'Type RECOVER to confirm stalled-operation recovery.')
            else:
                try:
                    recovery=recover_stalled_operations_state()
                    summary=(f"Recovery released {recovery.get('campaign_runs_released',0)} campaign run(s) and "
                             f"{recovery.get('background_jobs_released',0)} background job(s); "
                             f"requeued {recovery.get('campaign_runs_requeued',0)} campaign pass(es)"
                             + (' and the Hidden Leads scan' if recovery.get('hidden_scan_requeued') else '')
                             + f"; cleared {recovery.get('coordination_keys_deleted',0)} stale coordination key(s).")
                    log('maintenance_recovery',request=request,summary=summary,metadata=recovery)
                    if recovery.get('requeue_errors'):
                        messages.warning(request,summary+' Some replacement work could not be queued; check Dashboard / Audit Trail.')
                    elif recovery.get('coordination_error'):
                        messages.warning(request,summary+' Redis coordination cleanup could not be fully verified; replacement work was still queued where possible.')
                    else:
                        messages.success(request,summary)
                except Exception as exc:
                    messages.error(request,f'Stalled-operation recovery failed: {str(exc)[:300]}')
        elif action=='clear_logs':
            confirmation=(request.POST.get('confirm_text') or '').strip().upper()
            if confirmation!='CLEAR LOGS':
                messages.error(request,'Type CLEAR LOGS to confirm log and telemetry cleanup.')
            else:
                audit_count=AuditLog.objects.count(); metric_count=UsageMetric.objects.count(); sample_count=ResourceSample.objects.count(); hourly_count=ResourceHourly.objects.count(); diag_count=DiagnosticRun.objects.count(); perf_count=PerformanceRun.objects.count()
                finished_jobs=BackgroundJob.objects.filter(status__in=['completed','failed','stopped']).count()
                AuditLog.objects.all().delete(); UsageMetric.objects.all().delete(); ResourceSample.objects.all().delete(); ResourceHourly.objects.all().delete(); DiagnosticRun.objects.all().delete(); PerformanceRun.objects.all().delete(); BackgroundJob.objects.filter(status__in=['completed','failed','stopped']).delete()
                messages.success(request,f'Cleared detailed logs/telemetry: {audit_count} audit, {metric_count} usage, {sample_count} resource samples, {hourly_count} hourly resource archives, {diag_count} diagnostics, {perf_count} performance runs and {finished_jobs} finished background jobs. Search-provider aggregates and business records were preserved.')
        elif action=='clear_trial_data':
            confirmation=(request.POST.get('confirm_text') or '').strip().upper()
            if confirmation!='CLEAR':
                messages.error(request,'Type CLEAR to confirm removal of generated Opportunities and Hidden Leads.')
            else:
                # Preserve manually imported/history-backed opportunities and anything that has progressed to an application outcome.
                protected_ids=set(Application.objects.filter(status__in=['applied','reply','interview','rejected','accepted','closed']).values_list('opportunity_id',flat=True))
                # Maintenance cleanup is permanent: recycled Opportunities/Hidden Leads are cleared too.
                recycled_opps=Opportunity.objects.filter(user_deleted=True)
                recycled_opp_count=recycled_opps.count(); recycled_opps.delete()
                generated=Opportunity.objects.filter(user_deleted=False).exclude(pk__in=protected_ids).exclude(url__startswith='https://manual.invalid/').exclude(url__startswith='https://imported.invalid/')
                opp_count=generated.count(); lead_count=CompanyLead.objects.count()
                generated.delete(); CompanyLead.objects.all().delete()
                messages.success(request,f'Cleared {opp_count + recycled_opp_count} generated/recycled Opportunities and {lead_count} Hidden Leads, including Recycle Bin rows. Settings, audit history, profiles and documents were preserved.')
        elif action=='reset_workspace_data':
            confirmation=(request.POST.get('confirm_text') or '').strip().upper()
            if confirmation!='RESET':
                messages.error(request,'Type RESET to confirm workspace data removal.')
            else:
                # Keep accounts, credentials/configuration, Profile, CV/cover assets, audit history,
                # provider settings, blacklists and tracking rules.  Remove operational/test data.
                counts={
                    'opportunities':Opportunity.objects.count(), 'applications':Application.objects.count(),
                    'campaigns':Campaign.objects.count(), 'leads':CompanyLead.objects.count(),
                    'imports':ImportCandidate.objects.count(), 'contacts':Contact.objects.filter(deleted_at__isnull=True).count(),
                    'mail':MailEvent.objects.count(), 'jobs':BackgroundJob.objects.count(),
                }
                TrackingClick.objects.all().delete(); TrackingLink.objects.all().delete()
                MailEvent.objects.all().delete(); GeneratedTextVersion.objects.all().delete()
                Application.objects.all().delete(); OpportunityEvidence.objects.all().delete(); Opportunity.objects.all().delete()
                CompanyLead.objects.all().delete(); CampaignRun.objects.all().delete(); Campaign.objects.all().delete()
                CampaignTemplate.objects.filter(built_in=False).delete(); ImportCandidate.objects.all().delete(); Contact.objects.all().delete()
                DiagnosticRun.objects.all().delete(); PerformanceRun.objects.all().delete(); BackgroundJob.objects.all().delete()
                UsageMetric.objects.all().delete(); SearchProviderStat.objects.all().delete(); ResourceSample.objects.all().delete(); ResourceHourly.objects.all().delete()
                FacebookPage.objects.all().delete(); SavedFilter.objects.all().delete()
                # Reset runtime timestamps without changing discovery/email/provider configuration.
                ps.last_discovery_run=None; ps.last_scheduler_tick=None; ps.last_mail_sync=None; ps.last_hidden_scan=None; ps.last_digest_sent=None
                ps.save(update_fields=['last_discovery_run','last_scheduler_tick','last_mail_sync','last_hidden_scan','last_digest_sent','updated_at'])
                messages.success(request,'Workspace data reset. Accounts, credentials, profile, Resume/Cover Letter files, configuration, audit history, blacklist and tracking rules were preserved.')
        elif action=='save_blog':
            cfg.enabled=bool(request.POST.get('enabled')); cfg.save(update_fields=['enabled'])
            save_external_config(request.POST,request.POST.get('password') or '')
            messages.success(request,'External statistics connector saved.')
        elif action=='test_blog':
            # Backward-compatible POST action: keep the read-only test asynchronous so
            # invalid credentials or an unreachable host can never block the settings page.
            job=BackgroundJob.objects.create(kind='diagnostic',label='External statistics connection test',message='Queued',result={'blog_config_id':cfg.pk})
            task=blog_stats_test_job.delay(job.pk,cfg.pk); job.celery_task_id=task.id or ''; job.save(update_fields=['celery_task_id'])
            messages.success(request,'External statistics connection test queued in the background.')
        elif action=='create_user':
            email=request.POST.get('email','').strip(); name=request.POST.get('name','').strip(); password=request.POST.get('password','')
            valid_name=len(name)>=2 and sum(1 for ch in name if ch.isalpha())>=2 and all(ch.isalpha() or ch.isspace() or ch in ".'’‑-" for ch in name)
            if not valid_name: messages.error(request,'Administrator name must contain at least two letters and use normal name punctuation only.')
            elif '@' not in email: messages.error(request,'Enter a valid administrator email address.')
            elif len(password)<10: messages.error(request,'Initial password must contain at least 10 characters.')
            elif User.objects.filter(username=email).exists(): messages.error(request,'That administrator already exists.')
            else: User.objects.create_user(username=email,email=email,password=password,first_name=name,is_staff=True); messages.success(request,'Administrator account created.')
        elif action=='rename_self':
            name=request.POST.get('name','').strip(); valid_name=len(name)>=2 and sum(1 for ch in name if ch.isalpha())>=2 and all(ch.isalpha() or ch.isspace() or ch in ".'’‑-" for ch in name)
            if not valid_name: messages.error(request,'Display name must contain at least two letters and use normal name punctuation only.')
            else: request.user.first_name=name; request.user.save(update_fields=['first_name']); messages.success(request,'Your display name was updated.')
        elif action=='toggle_user':
            target=get_object_or_404(User,pk=request.POST.get('user_id'))
            if target.pk==request.user.pk:
                messages.error(request,'The current account cannot disable itself.')
            else:
                target.is_active=not target.is_active; target.save(update_fields=['is_active'])
                messages.success(request,f"Administrator {'enabled' if target.is_active else 'disabled'}: {target.email or target.username}")
        elif action=='delete_user':
            target=get_object_or_404(User,pk=request.POST.get('user_id'))
            if target.pk==request.user.pk:
                messages.error(request,'The current account cannot delete itself.')
            else:
                label=target.email or target.username; target.delete(); messages.success(request,f'Administrator deleted: {label}')
        log('settings.update',request,summary=action)
        return redirect('settings')
    feature_fields=[{'name':f.name,'label':f.verbose_name.replace('feature ','').replace('_',' ').title(),'enabled':getattr(ps,f.name)} for f in PortalSettings._meta.fields if f.name.startswith('feature_')]
    return render(request,'portal/settings.html',ctx(request,'settings','Configuration',system_tab='general',blogcfg=cfg,external_stats_cfg=load_external_config(),external_stats_status=external_stats_status(),users=User.objects.all(),feature_fields=feature_fields))


@login_required
def maintenance_capabilities(request):
    """Return the canonical saved Maintenance feature gates.

    The Maintenance page uses this tiny live check so the Cloud-Web-only rebuild action
    never depends on a stale template/context snapshot after Discovery Method changes.
    The POST handler still enforces the same rule server-side.
    """
    ps=PortalSettings.objects.get_or_create(pk=1)[0]
    mode=str(ps.discovery_mode or '').strip().casefold()
    return JsonResponse({'discovery_mode':mode,'rebuild_missing_ai_data':mode=='cloud_web'})


@login_required
def health_view(request):
    # Diagnostics now live at the bottom of Dashboard; retain this route for old bookmarks.
    return redirect(reverse('dashboard') + '#diagnostics')

@login_required
def blacklist_view(request):
    if request.method=='POST':
        action=request.POST.get('action','add')
        if action=='restore_row':
            row_id=(request.POST.get('row_id') or '').strip()
            ok,label=_restore_recycle_item('blacklist',int(row_id)) if row_id.isdigit() else (False,'Blacklist')
            if ok:
                try: enforce_active_blacklist()
                except Exception: pass
            if request.headers.get('X-Requested-With')=='fetch':
                return JsonResponse({'ok':ok,'label':label,'error':'' if ok else 'This blacklist entry is not in the Recycle Bin.'},status=200 if ok else 404)
            (messages.success if ok else messages.warning)(request,(f'Restored {label}.' if ok else 'This blacklist entry is not in the Recycle Bin.'))
            return redirect(request.get_full_path())
        if action in ('add','edit'):
            try:
                row,created=_upsert_blacklist_rule(
                    request.POST.get('domain',''),
                    request.POST.get('label',''),
                    request.POST.get('reason','') or 'Manually blacklisted',
                    request.POST.get('scope') or 'all',
                    row_id=(request.POST.get('row_id') if action=='edit' else None),
                    preserve_enabled=(action=='edit'),
                )
                name=_blacklist_display_name(row)
                messages.success(request,f'{name} {"added to" if created else "updated on"} the blacklist.')
            except ValueError as exc:
                messages.error(request,str(exc))
        elif action=='delete_selected':
            ids=[x for x in request.POST.getlist('row_ids') if str(x).isdigit()]
            rows=list(SourceBlacklist.objects.filter(pk__in=ids,deleted_at__isnull=True))
            if rows: SourceBlacklist.objects.filter(pk__in=[row.pk for row in rows]).update(deleted_at=timezone.now())
            if rows: messages.success(request,f'Moved {len(rows)} selected blacklist entr{"y" if len(rows)==1 else "ies"} to the Recycle Bin.')
            else: messages.info(request,'The selected blacklist entries are already in the Recycle Bin or no longer active.')
        elif action=='reset_defaults':
            reset_blacklist_defaults(); messages.success(request,'Blacklist reset to built-in defaults.')
        elif action=='toggle':
            row=get_object_or_404(SourceBlacklist,pk=request.POST.get('row_id'),deleted_at__isnull=True); row.enabled=not row.enabled; row.save(update_fields=['enabled']); messages.success(request,f'{_blacklist_display_name(row)} {"enabled" if row.enabled else "disabled"}.')
        try:
            result=enforce_active_blacklist()
            if result.get('opportunities') or result.get('hidden_leads'):
                messages.info(request,f"Blacklist applied to {result.get('opportunities',0)} existing opportunities and {result.get('hidden_leads',0)} existing hidden leads.")
        except Exception as exc:
            log('blacklist.enforce.error',request,summary=str(exc)[:500])
        return redirect('blacklist')
    show_deleted=_show_deleted_setting(request,'blacklist')
    qs=SourceBlacklist.objects.all() if show_deleted else SourceBlacklist.objects.filter(deleted_at__isnull=True); q=_q(request)
    if q: qs=qs.filter(Q(domain__icontains=q)|Q(label__icontains=q)|Q(reason__icontains=q)|Q(scope__icontains=q))
    _blacklist_scope_counts={row['scope']:int(row['n'] or 0) for row in qs.values('scope').annotate(n=Count('pk'))}
    blacklist_filter_counts={'total':sum(int(_blacklist_scope_counts.get(value,0) or 0) for value,_label in SourceBlacklist.SCOPE),'scope':_blacklist_scope_counts}
    scope_state=_selected_filter_values(request,'scope',dict(SourceBlacklist.SCOPE).keys())
    scope_values=list(scope_state['values'])
    scope_filter=scope_values[0] if len(scope_values)==1 else ''
    scope_labels=dict(SourceBlacklist.SCOPE)
    scope_options=_option_selection_state([
        {'value':value,'label':scope_labels.get(value,value.replace('_',' ').title()),'count':count}
        for value,count in sorted(_blacklist_scope_counts.items(),key=lambda item:scope_labels.get(item[0],item[0]).casefold())
        if count>0
    ],scope_values,scope_state['mode'])
    scope_filter_label=_filter_options_label('scopes',scope_options,scope_values,scope_state['mode'],blacklist_filter_counts['total'])
    qs=_apply_values_filter(qs,'scope',scope_values,scope_state['mode'])
    sort_mode=(request.GET.get('sort') or '').strip().lower()
    sort_orders={
        'domain_asc':('domain','label','pk'), 'domain_desc':('-domain','label','pk'),
        'company_asc':('label','domain','pk'), 'company_desc':('-label','domain','pk'),
        'reason_asc':('reason','domain','pk'), 'reason_desc':('-reason','domain','pk'),
        'scope_asc':('scope','domain','pk'), 'scope_desc':('-scope','domain','pk'),
        'added_asc':('created_at','pk'), 'added_desc':('-created_at','-pk'),
    }
    if sort_mode not in sort_orders: sort_mode=''
    ordered_qs=qs.order_by(*(sort_orders.get(sort_mode) or ('-enabled','domain','label','pk')))
    if request.GET.get('export')=='1': return _xlsx('blacklist.xlsx',['Domain','Company Name','Reason','Scope','Date Added','Status','Built in'],[(x.domain,x.label,clean_blacklist_reason(x.reason),x.get_scope_display(),x.created_at,'Blocked' if x.enabled else 'Disabled',x.built_in) for x in ordered_qs[:10000]])
    page,per_page=_page(request,ordered_qs,default=50)
    return render(request,'portal/blacklist.html',ctx(request,'blacklist','Blacklist',rows=page,page_obj=page,per_page=per_page,q=q,scopes=SourceBlacklist.SCOPE,scope_filter=scope_filter,scope_values=scope_values,scope_filter_mode=scope_state['mode'],scope_options=scope_options,scope_filter_label=scope_filter_label,blacklist_filter_counts=blacklist_filter_counts,label_min_chars=LABEL_BLACKLIST_MIN_CHARS,show_deleted=show_deleted,sort_mode=sort_mode,map_edit_blacklist=SourceBlacklist.objects.filter(pk=request.GET.get('edit'),deleted_at__isnull=True).first() if str(request.GET.get('edit') or '').isdigit() else None))


@login_required
def telemetry_live(request):
    current_resource_sample=_capture_resource_sample(force=True,allow_stale_fallback=False)
    period,start,end=_resource_period_bounds(request)
    qs=UsageMetric.objects.all().exclude(category='lab')
    if start: qs=qs.filter(at__gte=start)
    if end: qs=qs.filter(at__lt=end)
    provider=(request.GET.get('provider') or '').strip(); category=(request.GET.get('category') or '').strip()
    if provider: qs=qs.filter(provider__icontains=provider)
    if category: qs=qs.filter(category=category)
    totals=qs.aggregate(requests=Sum('requests'),tokens_in=Sum('tokens_in'),tokens_out=Sum('tokens_out'),reasoning_tokens=Sum('reasoning_tokens'),web_search_queries=Sum('web_search_queries'),pages=Sum('pages'),errors=Sum('errors'),bytes_downloaded=Sum('bytes_downloaded'))
    breakdown=list(qs.values('category','provider').annotate(requests=Sum('requests'),errors=Sum('errors')).order_by('-requests')[:20])
    samples=ResourceSample.objects.all()
    if start: samples=samples.filter(at__gte=start)
    if end: samples=samples.filter(at__lt=end)
    try:
        rows=list(samples.order_by('-at').values('at','cpu_percent','memory_percent','memory_used_mb','memory_total_mb','disk_used_mb','disk_total_mb','gpu_percent','gpu_memory_percent','gpu_vram_used_mb','gpu_vram_total_mb','gpu_label')[:2]); rows.reverse()
    except Exception:
        rows=[]
    resources=_resource_chart_rows(rows,qs)
    latest=resources[-1] if resources else None
    token_breakdown,token_title=_token_category_breakdown(qs)
    token_category_model_breakdown=_token_category_model_breakdown(qs)
    token_provider_breakdown,token_provider_title=_token_provider_breakdown(qs)
    token_model_breakdown,token_model_title=_token_model_breakdown(qs)
    pstats=SearchProviderStat.objects.select_related('source').all()
    if start: pstats=pstats.filter(day__gte=start.date())
    if end: pstats=pstats.filter(day__lt=end.date())
    provider_perf=_provider_performance_rows(pstats)
    market_coverage=_market_coverage_breakdown(qs)
    try: system=_system_snapshot(sample=current_resource_sample or ResourceSample())
    except Exception: system={'cpu_percent':0,'memory_used_mb':0,'memory_total_mb':0,'disk_used_mb':0,'disk_total_mb':0,'gpu_percent':None,'gpu_label':'','gpu_vram_total_mb':None}
    show_vram_series=bool(current_resource_sample and (getattr(current_resource_sample,'gpu_vram_total_mb',None) or 0)>0)
    disk_breakdown=_disk_usage_breakdown(system,_safe_ollama_diagnostics())
    return JsonResponse({'updated_at':timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M:%S'),'data_days':_telemetry_data_days(start,end),'period':period,'totals':{k:(v or 0) for k,v in totals.items()},'resource':latest,'resources':resources,'breakdown':breakdown,'provider_performance':provider_perf,'market_coverage':market_coverage,'token_category_breakdown':token_breakdown,'token_category_title':token_title,'token_category_model_breakdown':token_category_model_breakdown,'token_provider_breakdown':token_provider_breakdown,'token_provider_title':token_provider_title,'token_model_breakdown':token_model_breakdown,'token_model_title':token_model_title,'cloud_usage':_cloud_usage_dashboard(period,start,end),'system':system,'show_vram_series':show_vram_series,'disk_breakdown':disk_breakdown,'telemetry_health':_resource_telemetry_health(start,end)})


@login_required
def stats_live(request):
    period,start,end=_period_bounds(request)
    qs=Opportunity.objects.filter(suppressed=False,user_deleted=False); apps=Application.objects.filter(opportunity__user_deleted=False,deleted_at__isnull=True)
    if start: qs=qs.filter(created_at__gte=start); apps=apps.filter(created_at__gte=start)
    if end: qs=qs.filter(created_at__lt=end); apps=apps.filter(created_at__lt=end)
    q=_q(request)
    if q:
        qs=qs.filter(Q(title__icontains=q)|Q(company__icontains=q)).distinct()
        apps=apps.filter(Q(opportunity__title__icontains=q)|Q(opportunity__company__icontains=q)).distinct()
    funnel={'found':qs.count(),'reviewed':qs.filter(status__in=['apply','review','info','draft','applied','closed']).count(),'prepared':apps.count(),'applied':apps.filter(status__in=['applied','reply','interview','rejected','accepted','closed']).count(),'reply':apps.filter(status__in=['reply','interview','rejected','accepted']).count(),'interview':apps.filter(status='interview').count(),'accepted':apps.filter(status='accepted').count()}
    return JsonResponse({'updated_at':timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M:%S'),'period':period,'funnel':funnel})

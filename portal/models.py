from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# Canonical Search & Limits defaults. Keep the model defaults, save-form fallbacks,
# and Restore Defaults action sourced from this single mapping so upgrades cannot
# drift back to stale values.
# Provider request timeouts are user-visible under AI & Discovery > Miscellaneous.
# Keep defaults and validation limits centralized so runtime calls, migrations and UI
# cannot drift back to scattered per-call socket timeouts.
AI_REQUEST_TIMEOUT_DEFAULTS = {
    'local_ai': 180,
    'cloud_ai': 120,
    'chatbot': 300,
}
AI_REQUEST_TIMEOUT_LIMITS = {
    'local_ai': (30, 300),
    'cloud_ai': (30, 300),
    'chatbot': (30, 300),
}


def default_multilingual_languages():
    return ['French', 'German', 'Spanish']


SEARCH_SCHEDULE_DEFAULTS = {
    'scraper_interval_minutes': 120,
    'keywords_per_run': 100,
    'queries_per_provider': 100,
    'provider_public_daily_request_budget': 5000,
    'provider_api_daily_request_budget': 500,
    'searchapi_daily_limit': 500,
    'max_results_per_query': 100,
    'followup_pages_per_run': 50,
    'followup_link_depth': 3,
    'cloud_min_interval_minutes': 240,
    'cloud_auto_runs_per_campaign_day': 5,
    'cloud_requests_per_run': 100,
    'cloud_web_searches_per_run': 100,
    'cloud_discovery_candidates_per_run': 50,
    'cloud_deep_research_candidates_per_run': 100,
    'cloud_daily_requests': 1000,
    'cloud_daily_web_searches': 2000,
    'cloud_daily_input_tokens': 3000000,
    'cloud_daily_output_tokens': 1000000,
    'cloud_passive_enrichment_per_day': 100,
    'cloud_page_recovery_per_day': 250,
    'cloud_test_searches_per_run': 20,
    'cloud_test_candidates': 20,
}

MAX_CONCURRENT_CAMPAIGNS_DEFAULT = 5
MAX_CONCURRENT_CAMPAIGNS_LIMITS = (2, 10)



DEFAULT_OPPORTUNITY_CLOUD_REEVALUATION_PROMPT = (
    'Verify the role and its work-location rules with web search. Keep it if the candidate can realistically take it from Singapore, work remotely, or relocate with explicit support. Recycle clearly incompatible location-restricted roles unless the opportunity is exceptionally unusual and strongly matched. Convert to Hidden Lead if it is not a real vacancy but shows a strong current need for outside technical help.'
)
DEFAULT_HIDDEN_LEAD_CLOUD_REEVALUATION_PROMPT = (
    'Verify this company with web search. Keep it only if there is a credible current signal that it may need outside technical help, a developer, contractor, partner, or outsourced expertise. Technical relevance alone is not enough. Convert to Opportunity if it is clearly a live vacancy. If no need signal exists, recycle unless the company is exceptionally unusual and specifically relevant to the candidate; this exception should be very rare.'
)


class SingletonModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)


class PortalSettings(SingletonModel):
    DISCOVERY_MODES = [
        ('source_guided', 'Local AI Discovery'),
        ('cloud_web', 'Cloud Web Discovery'),
    ]
    OPPORTUNITY_SELECTIVITY = [
        ('broad', 'Broad'), ('balanced', 'Balanced'), ('specialist', 'Specialist'),
    ]
    LEAD_SELECTIVITY = [
        ('broad', 'Broad'), ('balanced', 'Balanced'), ('specialist', 'Specialist'),
    ]
    CONTACT_SELECTIVITY = [
        ('broad', 'Broad'), ('balanced', 'Balanced'), ('verified', 'Verified'),
    ]
    # Discovery strategy. Local AI Discovery is the local-friendly/default mode: ordinary
    # configured search providers find URLs, then AI stages analyse those URLs. Cloud
    # Web Discovery delegates URL finding to a cloud model with a web-search tool.
    discovery_mode = models.CharField(max_length=32, choices=DISCOVERY_MODES, default='source_guided')
    opportunity_selectivity = models.CharField(max_length=16, choices=OPPORTUNITY_SELECTIVITY, default='balanced', help_text='Admission breadth for automatically discovered Opportunities.')
    lead_selectivity = models.CharField(max_length=16, choices=LEAD_SELECTIVITY, default='balanced', help_text='Admission breadth for automatically discovered Hidden Leads.')
    contact_selectivity = models.CharField(max_length=16, choices=CONTACT_SELECTIVITY, default='balanced', help_text='Identity/admission strictness for automatically discovered Address Book contacts.')
    local_ai_request_timeout_seconds = models.PositiveSmallIntegerField(default=AI_REQUEST_TIMEOUT_DEFAULTS['local_ai'], help_text='Per-attempt timeout for local Ollama generation requests.')
    cloud_ai_request_timeout_seconds = models.PositiveSmallIntegerField(default=AI_REQUEST_TIMEOUT_DEFAULTS['cloud_ai'], help_text='Per-attempt timeout for Cloud AI generation/web-research requests.')
    chatbot_provider_timeout_seconds = models.PositiveSmallIntegerField(default=AI_REQUEST_TIMEOUT_DEFAULTS['chatbot'], help_text='Per-provider-attempt timeout for Ask ScoutBox primary and secondary routes.')
    tracking_blog_base_url = models.URLField(max_length=1000, default='https://toughdev.com/blog', blank=True)
    portal_root_url = models.URLField(max_length=1000, default='http://localhost:8989', blank=True, help_text='Absolute ScoutBox root used in email and notification links.')
    opportunity_cloud_reevaluation_prompt = models.TextField(default=DEFAULT_OPPORTUNITY_CLOUD_REEVALUATION_PROMPT, blank=True)
    hidden_lead_cloud_reevaluation_prompt = models.TextField(default=DEFAULT_HIDDEN_LEAD_CLOUD_REEVALUATION_PROMPT, blank=True)

    # Background scheduling / budgets.
    background_paused = models.BooleanField(default=False)
    background_state_changed_at = models.DateTimeField(default=timezone.now)
    max_concurrent_campaigns = models.PositiveSmallIntegerField(default=MAX_CONCURRENT_CAMPAIGNS_DEFAULT, help_text='Maximum automatic primary campaign runs ScoutBox may have queued or running at once. Clamp range: 2-10.')
    scraper_interval_minutes = models.PositiveIntegerField(default=SEARCH_SCHEDULE_DEFAULTS['scraper_interval_minutes'])
    keywords_per_run = models.PositiveIntegerField(default=SEARCH_SCHEDULE_DEFAULTS['keywords_per_run'])
    queries_per_provider = models.PositiveIntegerField(default=SEARCH_SCHEDULE_DEFAULTS['queries_per_provider'])
    # Legacy single-budget field retained for upgrade compatibility. 0.8.66 uses
    # separate defaults depending on whether the selected provider access path uses API credentials.
    provider_daily_request_budget = models.PositiveIntegerField(default=100)
    provider_public_daily_request_budget = models.PositiveIntegerField(default=SEARCH_SCHEDULE_DEFAULTS['provider_public_daily_request_budget'])
    provider_api_daily_request_budget = models.PositiveIntegerField(default=SEARCH_SCHEDULE_DEFAULTS['provider_api_daily_request_budget'])
    searchapi_daily_limit = models.PositiveIntegerField(default=SEARCH_SCHEDULE_DEFAULTS['searchapi_daily_limit'], help_text='Shared daily request cap across all SearchAPI services; 0 disables automatic/manual SearchAPI requests without removing credentials.')
    max_results_per_query = models.PositiveIntegerField(default=SEARCH_SCHEDULE_DEFAULTS['max_results_per_query'])
    followup_pages_per_run = models.PositiveIntegerField(default=SEARCH_SCHEDULE_DEFAULTS['followup_pages_per_run'], help_text='Maximum extra linked pages Local AI Discovery may inspect per campaign run; 0 disables follow-up exploration.')
    followup_link_depth = models.PositiveSmallIntegerField(default=SEARCH_SCHEDULE_DEFAULTS['followup_link_depth'], help_text='Maximum Local AI follow-up link depth. Values above 5 are not accepted by the settings UI.')
    duplicate_window_days = models.PositiveIntegerField(default=90)
    draft_suppression_days = models.PositiveIntegerField(default=90)
    company_reapply_window_days = models.PositiveIntegerField(default=90, help_text='Different roles at a recently applied company remain visible but are ranked down within this window.')
    same_company_fit_penalty = models.PositiveSmallIntegerField(default=20, help_text='Score penalty for a different role at a company applied to within the company cooldown window.')
    same_company_unknown_date_penalty = models.PositiveSmallIntegerField(default=8, help_text='Smaller caution penalty when a prior application at the same company has no reliable application date.')
    # Cloud AI safety guardrails. Local AI Discovery keeps its existing
    # high-throughput limits; these apply only when a cloud provider actually executes.
    cloud_min_interval_minutes = models.PositiveIntegerField(default=SEARCH_SCHEDULE_DEFAULTS['cloud_min_interval_minutes'])
    cloud_auto_runs_per_campaign_day = models.PositiveIntegerField(default=SEARCH_SCHEDULE_DEFAULTS['cloud_auto_runs_per_campaign_day'])
    cloud_requests_per_run = models.PositiveIntegerField(default=SEARCH_SCHEDULE_DEFAULTS['cloud_requests_per_run'])
    cloud_web_searches_per_run = models.PositiveIntegerField(default=SEARCH_SCHEDULE_DEFAULTS['cloud_web_searches_per_run'])
    cloud_discovery_candidates_per_run = models.PositiveIntegerField(default=SEARCH_SCHEDULE_DEFAULTS['cloud_discovery_candidates_per_run'])
    cloud_deep_research_candidates_per_run = models.PositiveIntegerField(default=SEARCH_SCHEDULE_DEFAULTS['cloud_deep_research_candidates_per_run'])
    cloud_daily_requests = models.PositiveIntegerField(default=SEARCH_SCHEDULE_DEFAULTS['cloud_daily_requests'])
    cloud_daily_web_searches = models.PositiveIntegerField(default=SEARCH_SCHEDULE_DEFAULTS['cloud_daily_web_searches'])
    cloud_daily_input_tokens = models.PositiveIntegerField(default=SEARCH_SCHEDULE_DEFAULTS['cloud_daily_input_tokens'])
    cloud_daily_output_tokens = models.PositiveIntegerField(default=SEARCH_SCHEDULE_DEFAULTS['cloud_daily_output_tokens'])
    cloud_passive_enrichment_per_day = models.PositiveIntegerField(default=SEARCH_SCHEDULE_DEFAULTS['cloud_passive_enrichment_per_day'])
    cloud_page_recovery_per_day = models.PositiveIntegerField(default=SEARCH_SCHEDULE_DEFAULTS['cloud_page_recovery_per_day'])
    cloud_test_searches_per_run = models.PositiveIntegerField(default=SEARCH_SCHEDULE_DEFAULTS['cloud_test_searches_per_run'])
    cloud_test_candidates = models.PositiveIntegerField(default=SEARCH_SCHEDULE_DEFAULTS['cloud_test_candidates'])
    cloud_provider_priority = models.JSONField(default=list, blank=True, help_text='Legacy provider-priority setting retained for upgrade compatibility.')
    cloud_web_provider = models.CharField(max_length=30, blank=True, default='', help_text='Explicit Cloud Web provider used for discovery/research.')
    cloud_web_primary_model = models.CharField(max_length=200, blank=True, default='', help_text='Primary model for Cloud Web discovery/research.')
    cloud_web_secondary_model = models.CharField(max_length=200, blank=True, default='', help_text='Legacy Cloud Web secondary model retained for upgrade compatibility.')
    cloud_web_stage_routes = models.JSONField(default=dict, blank=True, help_text='Per-stage Cloud Web provider, primary/failover models and token caps. Primary and failover must use the same provider within a stage.')
    last_discovery_run = models.DateTimeField(null=True, blank=True)
    last_scheduler_tick = models.DateTimeField(null=True, blank=True)
    last_mail_sync = models.DateTimeField(null=True, blank=True)
    last_hidden_scan = models.DateTimeField(null=True, blank=True)
    detailed_log_retention_days = models.PositiveSmallIntegerField(default=90, help_text='Retention for detailed operational logs and resource telemetry. UI clamp: 14-180 days.')
    focus_comparison_records = models.PositiveSmallIntegerField(default=100, help_text='Target same-list comparison depth for Focus assignment. UI clamp: 25-500.')
    max_focus_groups = models.PositiveSmallIntegerField(default=15, help_text='Target maximum active Focus groups. UI clamp: 5-30.')
    focus_taxonomy_version = models.CharField(max_length=32, blank=True, default='', help_text='Last release whose AI-generated Focus taxonomy rebuild completed.')
    focus_taxonomy_state = models.JSONField(default=dict, blank=True, help_text='Per-list Focus taxonomy population baselines and maintenance timestamps used to keep Focus labels stable between rare full rebuilds.')
    # Acquisition geography. These markets control where ScoutBox looks; Candidate Profile
    # operating locations remain soft suitability/ranking preferences.
    discovery_markets = models.JSONField(default=list, blank=True, help_text='Enabled acquisition markets. Empty legacy values are interpreted as all supported markets.')
    discovery_market_strategy = models.CharField(max_length=20, default='global', choices=[('global','Global Coverage'),('balanced','Balanced'),('adaptive','Adaptive'),('even','Even')])
    # Retained for upgrade compatibility. Multilingual exploration is always enabled;
    # strength and selected languages provide the bounded controls.
    multilingual_exploration_enabled = models.BooleanField(default=True)
    multilingual_language_mode = models.CharField(max_length=12, default='auto', choices=[('auto','Auto'),('custom','Custom')])
    multilingual_languages = models.JSONField(default=default_multilingual_languages, blank=True)
    multilingual_exploration_strength = models.CharField(max_length=12, default='balanced', choices=[('low','Low'),('balanced','Balanced'),('high','High')])
    scheduler_health = models.JSONField(default=dict, blank=True, help_text='Recent scheduler/worker health summary used by diagnostics.')
    error_notifications_seen_at = models.DateTimeField(default=timezone.now, help_text='Dashboard visit watermark used for the new-error badge.')

    # Daily notification digest.
    digest_enabled = models.BooleanField(default=True)
    digest_hour = models.PositiveSmallIntegerField(default=8)
    digest_minute = models.PositiveSmallIntegerField(default=30)
    digest_recipient_email = models.EmailField(max_length=254, blank=True, default='', help_text='Recipient for scheduled and test 24-hour digest email.')
    last_digest_sent = models.DateField(null=True, blank=True)
    release_backfill_version = models.CharField(max_length=32, blank=True, default='', help_text='Last release-level enrichment backfill queued for this installation.')
    country_repair_version = models.CharField(max_length=32, blank=True, default='', help_text='Last release whose evidence-grounded country/location repair completed.')
    integrity_repair_version = models.CharField(max_length=32, blank=True, default='', help_text='Last release whose blacklist/opportunity-integrity repair completed.')

    # Optional enrichment stages. All are enabled by default; disabling them is
    # a supported way to trade depth for speed on slower local hardware.
    feature_page_fetch = models.BooleanField(default=True)
    feature_age_estimation = models.BooleanField(default=True)
    feature_wayback = models.BooleanField(default=True)
    feature_company_enrichment = models.BooleanField(default=True)
    feature_contact_discovery = models.BooleanField(default=True)
    feature_cross_source = models.BooleanField(default=True)
    feature_ai_rerank = models.BooleanField(default=True)
    feature_authenticated_social_fetch = models.BooleanField(default=True)
    feature_facebook_index_search = models.BooleanField(default=True)
    feature_blog_click_sync = models.BooleanField(default=True)
    feature_page_summarization = models.BooleanField(default=True)
    feature_deep_jd_analysis = models.BooleanField(default=True)
    feature_document_conversion = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)


class Profile(SingletonModel):
    display_name = models.CharField(max_length=200, blank=True)
    operating_location = models.CharField(max_length=120, default='Singapore')
    operating_locations = models.JSONField(default=list, blank=True, help_text='Searchable list of countries/regions where the candidate can operate.')
    application_email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=32, blank=True)
    portfolio_url = models.URLField(blank=True)
    high_priority_text = models.TextField(
        blank=True,
        default='',
    )
    medium_priority_text = models.TextField(
        blank=True,
        default='',
    )
    low_priority_text = models.TextField(
        blank=True,
        default='',
    )
    scope_json = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class DocumentAsset(models.Model):
    KIND_CHOICES = [('cv', 'Resume'), ('cover', 'Cover letter')]
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    label = models.CharField(max_length=200)
    file = models.FileField(upload_to='documents/%Y/%m/')
    original_name = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    campaign_template_generated_at = models.DateTimeField(null=True, blank=True, help_text='Most recent successful Campaign Template generation from this Resume.')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.get_kind_display()}: {self.label}'


class SearchSource(models.Model):
    category = models.CharField(max_length=120)
    name = models.CharField(max_length=160, unique=True)
    source_type = models.CharField(max_length=40, default='web')
    base_url = models.URLField(blank=True)
    enabled = models.BooleanField(default=True)
    preferred_initial = models.BooleanField(default=False, help_text='Use this search engine for initial URL discovery in Local AI Discovery.')
    priority = models.PositiveSmallIntegerField(default=50)
    provider_weight = models.PositiveSmallIntegerField(default=100)
    daily_budget_override = models.PositiveIntegerField(null=True, blank=True)
    low_value_marketplace = models.BooleanField(default=False)
    requires_credentials = models.BooleanField(default=False)
    adapter_status = models.CharField(max_length=40, default='preset')
    notes = models.TextField(blank=True)
    config_json = models.JSONField(default=dict, blank=True)
    api_key_enc = models.TextField(blank=True, help_text='Legacy reserved field; v0.8.1 search-provider credentials are read from .env.')
    public_fallback = models.BooleanField(default=True, help_text='Allow limited public HTML search when no API key is configured and the provider supports it.')

    def __str__(self):
        return self.name


class CustomSearchDomain(models.Model):
    name = models.CharField(max_length=160)
    domain = models.CharField(max_length=255, unique=True)
    note = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', 'domain']

    def __str__(self):
        return self.name or self.domain


class SearchProviderStat(models.Model):
    source = models.ForeignKey(SearchSource, on_delete=models.CASCADE, related_name='stats')
    day = models.DateField(default=timezone.localdate)
    requests = models.PositiveIntegerField(default=0)
    results = models.PositiveIntegerField(default=0)
    unique_results = models.PositiveIntegerField(default=0)
    duplicates = models.PositiveIntegerField(default=0)
    applied_matches = models.PositiveIntegerField(default=0)
    errors = models.PositiveIntegerField(default=0)
    quota_units = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    avg_latency_ms = models.PositiveIntegerField(default=0)
    bytes_downloaded = models.PositiveBigIntegerField(default=0)
    last_error = models.TextField(blank=True)

    class Meta:
        unique_together = ('source', 'day')


class FacebookConfig(SingletonModel):
    use_search_index = models.BooleanField(default=True)
    use_graph_api = models.BooleanField(default=True)
    use_authenticated_cookie = models.BooleanField(default=True)
    graph_access_token_enc = models.TextField(blank=True)
    graph_page_ids = models.TextField(blank=True, help_text='Comma/newline separated public Page IDs to watch.')
    cookie_header_enc = models.TextField(blank=True, help_text='Cookie header copied from a browser session you logged into yourself.')
    last_test_ok = models.BooleanField(default=False)
    last_test_message = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class Campaign(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(max_length=2000, blank=True, help_text='Informational campaign description shown only on Campaign Detail.')
    template = models.CharField(max_length=120, blank=True)
    enabled = models.BooleanField(default=True)
    location = models.CharField(max_length=160, default='Singapore')
    locations = models.JSONField(default=list, blank=True)
    role_families = models.TextField(blank=True)
    technologies = models.TextField(blank=True)
    engagement_types = models.TextField(blank=True)
    company_sizes = models.TextField(blank=True)
    languages = models.TextField(blank=True)
    negative_constraints = models.TextField(blank=True)
    extra_text = models.TextField(blank=True)
    recency_days = models.PositiveIntegerField(default=30)
    source_names = models.JSONField(default=list, blank=True)
    queries_per_rotation = models.PositiveIntegerField(null=True, blank=True, help_text='Optional campaign-specific query bundle size; blank inherits the portal default.')
    last_run = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True, help_text='When this campaign was moved to the Recycle Bin.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class CampaignTemplate(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.CharField(max_length=500, blank=True)
    built_in = models.BooleanField(default=False)
    locations = models.JSONField(default=list, blank=True)
    role_families = models.JSONField(default=list, blank=True)
    technologies = models.JSONField(default=list, blank=True)
    engagement_types = models.JSONField(default=list, blank=True)
    company_sizes = models.JSONField(default=list, blank=True)
    languages = models.JSONField(default=list, blank=True)
    negative_constraints = models.TextField(blank=True)
    extra_text = models.TextField(blank=True)
    recency_days = models.PositiveIntegerField(default=30)
    source_names = models.JSONField(default=list, blank=True)
    queries_per_rotation = models.PositiveIntegerField(null=True, blank=True)
    source_resume = models.ForeignKey('DocumentAsset', on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_campaign_templates', help_text='Resume that generated this template. Cleared if the Resume is deleted; template remains independent.')
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True, help_text='When this template was moved to the Recycle Bin.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class CampaignRun(models.Model):
    STATUS = [('queued','Queued'),('running','Running'),('stopping','Stopping'),('completed','Completed'),('failed','Failed'),('stopped','Stopped')]
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='runs')
    status = models.CharField(max_length=20, choices=STATUS, default='queued')
    celery_task_id = models.CharField(max_length=120, blank=True)
    progress = models.PositiveSmallIntegerField(default=0)
    message = models.CharField(max_length=500, blank=True)
    criteria = models.JSONField(default=dict, blank=True)
    query_plan = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True, help_text='Last confirmed campaign activity/progress heartbeat.')
    stage = models.CharField(max_length=120, blank=True, default='', help_text='Current execution stage for progress/stall diagnostics.')
    execution_provider = models.CharField(max_length=80, blank=True, default='')
    execution_model = models.CharField(max_length=200, blank=True, default='')
    stall_reason = models.CharField(max_length=500, blank=True, default='')
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class BackgroundJob(models.Model):
    KIND = [('campaign','Campaign discovery'),('import_text','Application import'),('import_document','Document import'),('mail_scan','Mailbox scan'),('diagnostic','Test discovery'),('hidden_scan','Hidden Leads scan'),('cold_draft','Cold outreach draft'),('enrich','Opportunity enrichment'),('prepare','Application preparation'),('translate','Translation'),('company_research','Company research'),('summarize','AI text summary'),('performance','Performance test'),('chatbot','Chatbot request'),('filter_opportunities','Opportunity filter'),('filter_hidden_leads','Hidden Lead filter'),('other','Automatic task')]
    STATUS = [('queued','Queued'),('running','Running'),('completed','Completed'),('failed','Failed'),('stopped','Stopped')]
    kind = models.CharField(max_length=30, choices=KIND, default='other')
    label = models.CharField(max_length=300)
    status = models.CharField(max_length=20, choices=STATUS, default='queued')
    celery_task_id = models.CharField(max_length=120, blank=True)
    progress = models.PositiveSmallIntegerField(default=0)
    message = models.CharField(max_length=500, blank=True)
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def _ai_request_stage(self):
        label=(self.label or '').lower()
        if self.kind=='summarize': return 'page_summarization'
        if self.kind=='company_research': return 'company_enrichment'
        if self.kind=='cold_draft': return 'cold_contact'
        if self.kind=='translate': return 'translation'
        if self.kind=='enrich': return 'opportunity_enrichment'
        if self.kind=='chatbot': return 'chatbot'
        if self.kind in ('filter_opportunities','filter_hidden_leads','filter_contacts'): return 'first_filter'
        if self.kind=='diagnostic' and ('discovery' in label or 'pipeline model' in label): return 'diagnostic_discovery'
        if 'provider test' in label or 'ollama model test' in label: return 'provider_test'
        if self.kind=='prepare':
            if 'save imap draft' in label: return ''
            if 'application answers' in label: return 'question_answers'
            if 'tailor resume' in label or 'tailor cover' in label: return 'cv_tailoring'
            if 'compare email' in label or 'email' in label: return 'email_draft'
            return 'application_prepare'
        return ''

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # AI Requests should expose work while it is waiting, not only after a model call
        # finishes. Refresh the placeholder timestamp/message on every job heartbeat so a
        # deferred task does not look frozen at its original creation time. Completed
        # placeholders disappear because the real provider request log is richer.
        stage=self._ai_request_stage()
        if not stage: return
        try:
            result=self.result if isinstance(self.result,dict) else {}
            meta={'background_job_id':self.pk,'placeholder':True,'job_message':str(self.message or '')[:500]}
            for key in ('wait_reason','wait_started_at','last_wait_at','next_retry_at','waited_seconds','retry_count','blocking_campaign_run_id','blocking_campaign_id'):
                if result.get(key) not in (None,''):
                    meta[key]=result.get(key)
            common={'at':timezone.now(),'stage':stage,'subject_label':self.label[:300],'ok':False,
                    'metadata':meta,'runtime':'','provider':'','model':''}
            if self.status in ('queued','running'):
                AIRequestLog.objects.update_or_create(
                    subject_type='background_job',subject_id=str(self.pk),
                    defaults={**common,'status':self.status,'error':''})
            elif self.status=='failed':
                AIRequestLog.objects.update_or_create(
                    subject_type='background_job',subject_id=str(self.pk),
                    defaults={**common,'status':'failed','error':(self.error or self.message or 'Background AI task failed')[:4000]})
            else:
                AIRequestLog.objects.filter(subject_type='background_job',subject_id=str(self.pk),metadata__placeholder=True).delete()
        except Exception:
            pass

    class Meta:
        ordering = ['-created_at']


class FacebookPage(models.Model):
    page_id = models.CharField(max_length=120, unique=True)
    page_url = models.URLField(max_length=1000, blank=True)
    page_title = models.CharField(max_length=300, blank=True)
    evidence_text = models.TextField(blank=True, default='')
    evidence_url = models.URLField(max_length=1000, blank=True)
    enabled = models.BooleanField(default=True)
    is_read = models.BooleanField(default=False, db_index=True, help_text='Facebook Page review state. False is shown as New; True is shown as Seen.')
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True, help_text='When this Facebook Page was moved to the Recycle Bin.')
    validation_state = models.CharField(max_length=24, blank=True, default='unknown', help_text='verified, indexed, unavailable, or unknown relevance-validation state.')
    validation_reason = models.CharField(max_length=500, blank=True, default='')
    validated_at = models.DateTimeField(null=True, blank=True)
    title_retry_count = models.PositiveSmallIntegerField(default=0, help_text='Automatic page-title validation attempts made for the current unresolved title.')
    title_retry_started_at = models.DateTimeField(null=True, blank=True, help_text='When automatic page-title retries started for the current unresolved title.')
    discovered_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['page_title', 'page_id']



class DiagnosticRun(models.Model):
    kind = models.CharField(max_length=40, default='search_test')
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    ok = models.BooleanField(default=False)
    criteria = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ['-started_at']


class Opportunity(models.Model):
    STATUS = [
        ('new', 'New'), ('apply', 'Apply Now'), ('review', 'Review'), ('info', 'Information Only'),
        ('rejected', 'Rejected'), ('unknown', 'Check / Unknown'), ('draft', 'Draft Prepared'),
        ('applied', 'Applied'), ('closed', 'Closed'),
    ]
    CHANNEL = [
        ('email', 'Direct email'), ('ats', 'ATS'), ('website', 'Website form'), ('public', 'Public post'),
        ('community', 'Community'), ('forum', 'Forum'), ('unknown', 'Unknown'),
    ]
    title = models.CharField(max_length=300)
    company = models.CharField(max_length=220, blank=True)
    country = models.CharField(max_length=120, blank=True)
    locations = models.JSONField(default=list, blank=True, help_text='Evidence-grounded role eligibility locations; supports multiple countries and recruiter regions.')
    role_location = models.CharField(max_length=240, blank=True, default='', help_text='Specific job/work location text, separate from company/HQ location.')
    remote_text = models.CharField(max_length=220, blank=True)
    language_code = models.CharField(max_length=16, blank=True, default='')
    url = models.URLField(max_length=1000)
    search_url = models.URLField(max_length=1000, blank=True, help_text='URL originally returned by the search provider.')
    target_url = models.URLField(max_length=1000, blank=True, help_text='Resolved/fetched destination URL used for analysis.')
    canonical_url = models.URLField(max_length=1000, blank=True)
    source = models.ForeignKey(SearchSource, on_delete=models.SET_NULL, null=True, blank=True)
    origin_campaign = models.ForeignKey(Campaign, on_delete=models.SET_NULL, null=True, blank=True, related_name='origin_opportunities', help_text='Campaign that first discovered this opportunity. Later campaign matches remain in campaigns as rediscovery provenance.')
    campaigns = models.ManyToManyField(Campaign, blank=True, related_name='opportunities')
    channel = models.CharField(max_length=30, choices=CHANNEL, default='unknown')
    contact_email = models.EmailField(blank=True)
    contact_name = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    raw_search_snippet = models.TextField(blank=True)
    extracted_facts = models.JSONField(default=dict, blank=True)
    company_intel = models.JSONField(default=dict, blank=True)
    ai_state = models.JSONField(default=dict, blank=True, help_text='Automatic/manual AI enrichment lifecycle state keyed by enrichment kind and evidence generation.')
    status = models.CharField(max_length=30, choices=STATUS, default='new')
    fit_score = models.PositiveSmallIntegerField(default=0)
    freshness_label = models.CharField(max_length=120, blank=True)
    freshness_confidence = models.PositiveSmallIntegerField(default=0)
    estimated_first_seen = models.DateTimeField(null=True, blank=True)
    declared_posted_at = models.DateTimeField(null=True, blank=True)
    first_seen_by_portal = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField(default=timezone.now)
    data_downloaded_bytes = models.PositiveBigIntegerField(default=0)
    recommendation_reason = models.TextField(blank=True)
    list_highlight = models.CharField(max_length=600, blank=True, default='', help_text='Concise role-specific technical summary for Opportunity list display (maximum 50 words).')
    focus = models.CharField(max_length=80, blank=True, default='', db_index=True, help_text='Content-based Focus classification, independent from Campaign provenance.')
    salary_text = models.CharField(max_length=300, blank=True, default='', help_text='Compact advertised or researched compensation text for list display.')
    salary_currency = models.CharField(max_length=12, blank=True, default='')
    salary_min = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    salary_period = models.CharField(max_length=24, blank=True, default='')
    salary_source_type = models.CharField(max_length=24, blank=True, default='', help_text='post, job_estimate, external, market, or unknown.')
    salary_source_url = models.URLField(max_length=1000, blank=True, default='')
    salary_confidence = models.PositiveSmallIntegerField(default=0)
    salary_checked_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    duplicate_of = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='rediscoveries')
    suppressed = models.BooleanField(default=False)
    user_deleted = models.BooleanField(default=False, db_index=True, help_text='Whether this opportunity is currently in the Recycle Bin.')
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    is_read = models.BooleanField(default=False, help_text='Whether the opportunity has been opened/reviewed in ScoutBox.')
    application_draft_requested_at = models.DateTimeField(null=True, blank=True, help_text='When Create Application Draft / Prepare Application was first requested.')
    note = models.TextField(blank=True, default='', help_text='Private note about this opportunity.')
    target_http_status = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Most recent direct HTTP status observed for the final opportunity URL.')
    target_checked_at = models.DateTimeField(null=True, blank=True, help_text='When the final opportunity URL was last checked directly.')
    target_check_error = models.CharField(max_length=500, blank=True, default='', help_text='Most recent final opportunity URL check error, if any.')
    target_response_bytes = models.PositiveBigIntegerField(default=0, help_text='Latest useful successful response size for URL-health tooltip display.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.company} — {self.title}'


class OpportunityEvidence(models.Model):
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name='evidence')
    kind = models.CharField(max_length=80)
    label = models.CharField(max_length=200)
    value = models.TextField()
    source_url = models.URLField(max_length=1000, blank=True)
    confidence = models.PositiveSmallIntegerField(default=50)
    observed_at = models.DateTimeField(default=timezone.now)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-observed_at']


class Application(models.Model):
    STATUS = [
        ('prepared', 'Prepared'), ('draft', 'Saved to Drafts'), ('suppressed', 'Draft suppressed'),
        ('applied', 'Applied'), ('reply', 'Reply received'), ('interview', 'Interview / progressing'),
        ('rejected', 'Rejected'), ('accepted', 'Accepted / engaged'), ('closed', 'Closed'),
    ]
    opportunity = models.OneToOneField(Opportunity, on_delete=models.CASCADE, related_name='application')
    status = models.CharField(max_length=30, choices=STATUS, default='prepared')
    cv = models.ForeignKey(DocumentAsset, on_delete=models.SET_NULL, null=True, blank=True, related_name='applications_as_cv')
    cover_letter = models.ForeignKey(DocumentAsset, on_delete=models.SET_NULL, null=True, blank=True, related_name='applications_as_cover')
    generated_cv = models.FileField(upload_to='generated/%Y/%m/', blank=True)
    generated_cv_pdf = models.FileField(upload_to='generated/%Y/%m/', blank=True)
    generated_cover = models.FileField(upload_to='generated/%Y/%m/', blank=True)
    generated_cover_pdf = models.FileField(upload_to='generated/%Y/%m/', blank=True)
    attach_generated_cv = models.BooleanField(default=False)
    attach_generated_cv_pdf = models.BooleanField(default=False)
    attach_generated_cover = models.BooleanField(default=False)
    attach_generated_cover_pdf = models.BooleanField(default=False)
    email_subject = models.CharField(max_length=500, blank=True)
    email_body = models.TextField(blank=True)
    email_mode = models.CharField(max_length=10, choices=[('plain', 'Plain text'), ('html', 'HTML')], default='plain')
    website_answers = models.JSONField(default=dict, blank=True)
    imap_draft_folder = models.CharField(max_length=200, blank=True)
    imap_draft_uid = models.CharField(max_length=100, blank=True)
    imap_message_id = models.CharField(max_length=300, blank=True)
    draft_suppressed_until = models.DateTimeField(null=True, blank=True)
    draft_suppression_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True, default='', help_text='Application/import notes and outcome context.')
    is_read = models.BooleanField(default=False, help_text='Whether this application draft has been reviewed in the UI.')
    applied_at = models.DateTimeField(null=True, blank=True)
    date_added = models.DateTimeField(default=timezone.now, help_text='When this applied-role entry was added to ScoutBox.')
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True, help_text='When this application/outreach was moved to the Recycle Bin.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        old_status = None
        if self.pk:
            try:
                old_status = Application.objects.filter(pk=self.pk).values_list('status', flat=True).first()
            except Exception:
                old_status = None
        super().save(*args, **kwargs)
        if old_status is not None and old_status != self.status:
            try:
                ApplicationStatusEvent.objects.create(application=self, old_status=old_status, new_status=self.status)
            except Exception:
                pass

    @property
    def latest_activity_at(self):
        values=[x for x in (self.date_added,self.updated_at) if x]
        return max(values) if values else None


class PreparedApplicationFile(models.Model):
    KIND = [('cv', 'Resume'), ('cover', 'Cover Letter')]
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='prepared_files')
    document_kind = models.CharField(max_length=20, choices=KIND)
    file_format = models.CharField(max_length=20, blank=True)
    label = models.CharField(max_length=255)
    file = models.FileField(upload_to='generated/%Y/%m/')
    source_asset_label = models.CharField(max_length=255, blank=True)
    selected_for_email = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class GeneratedTextVersion(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='text_versions')
    kind = models.CharField(max_length=40, default='email')
    provider = models.CharField(max_length=80)
    model = models.CharField(max_length=200)
    subject = models.CharField(max_length=500, blank=True)
    body = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class EmailProfile(models.Model):
    TEMPLATE = [('internal', 'Internal Development'), ('external', 'External Mail')]
    template = models.CharField(max_length=20, choices=TEMPLATE, unique=True)
    active = models.BooleanField(default=False)
    imap_host = models.CharField(max_length=255, blank=True)
    imap_port = models.PositiveIntegerField(default=993)
    imap_ssl = models.BooleanField(default=True)
    imap_email = models.EmailField(blank=True)
    imap_username = models.CharField(max_length=255, blank=True)
    imap_password_enc = models.TextField(blank=True)
    inbox_folder = models.CharField(max_length=200, default='INBOX')
    sent_folder = models.CharField(max_length=200, default='Sent')
    drafts_folder = models.CharField(max_length=200, default='Drafts')
    smtp_host = models.CharField(max_length=255, blank=True)
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_tls = models.BooleanField(default=True)
    smtp_username = models.CharField(max_length=255, blank=True)
    smtp_password_enc = models.TextField(blank=True)
    outgoing_method = models.CharField(max_length=20, choices=[('smtp', 'SMTP'), ('resend', 'Resend API')], default='smtp')
    resend_api_key_enc = models.TextField(blank=True)
    notification_from_name = models.CharField(max_length=200, default='Application Portal')
    notification_from_email = models.EmailField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.get_template_display()


class MailEvent(models.Model):
    KIND = [
        ('notification', 'Portal notification'), ('sent', 'Observed application sent'),
        ('inbox', 'Observed inbound'), ('draft', 'Draft saved'), ('draft_delete', 'Draft deleted'),
    ]
    kind = models.CharField(max_length=30, choices=KIND)
    application = models.ForeignKey(Application, on_delete=models.SET_NULL, null=True, blank=True, related_name='mail_events')
    subject = models.CharField(max_length=500, blank=True)
    sender = models.CharField(max_length=500, blank=True)
    recipients = models.TextField(blank=True)
    message_id = models.CharField(max_length=500, blank=True)
    folder = models.CharField(max_length=200, blank=True)
    uid = models.CharField(max_length=100, blank=True)
    body_excerpt = models.TextField(blank=True)
    body_text = models.TextField(blank=True, help_text='Full plain-text body when ScoutBox generated or fetched the message.')
    body_html = models.TextField(blank=True, help_text='Full HTML body when available; rendered through a sanitizer.')
    delivery_status = models.CharField(max_length=30, blank=True, default='', help_text='SMTP/observation outcome such as sent, failed, observed.')
    delivery_error = models.TextField(blank=True)
    server = models.CharField(max_length=300, blank=True, default='', help_text='Mail server/protocol used for this event, such as IMAP host:port or SMTP host:port.')
    raw_original_sender = models.CharField(max_length=500, blank=True)
    classification = models.CharField(max_length=80, blank=True)
    confidence = models.PositiveSmallIntegerField(default=0)
    occurred_at = models.DateTimeField(default=timezone.now)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-occurred_at']


class Contact(models.Model):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=200, blank=True)
    company = models.CharField(max_length=200, blank=True)
    title = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=80, blank=True)
    source = models.CharField(max_length=120, blank=True)
    source_url = models.URLField(max_length=1000, blank=True)
    generic = models.BooleanField(default=False)
    confidence = models.PositiveSmallIntegerField(default=50)
    notes = models.TextField(blank=True)
    company_summary = models.TextField(blank=True, default='', help_text='Short researched summary of what the contact company/team does.')
    focus = models.CharField(max_length=80, blank=True, default='', db_index=True, help_text='Content-based Focus classification for Address Book filtering.')
    company_country = models.CharField(max_length=120, blank=True, default='', help_text='Researched company/team location for Address Book context.')
    company_locations = models.JSONField(default=list, blank=True, help_text='Evidence-grounded Address Book company/team locations; supports multiple countries and recruiter regions.')
    company_intel = models.JSONField(default=dict, blank=True, help_text='Compact public company facts associated with this Address Book entry.')
    origin_provenance = models.JSONField(default=dict, blank=True, help_text='Lightweight campaign/run/source provenance for automatic Address Book promotion.')
    domain_http_status = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Most recent HTTP status observed for the email domain.')
    domain_checked_at = models.DateTimeField(null=True, blank=True)
    domain_check_error = models.CharField(max_length=500, blank=True, default='')
    domain_response_bytes = models.PositiveBigIntegerField(default=0, help_text='Latest useful successful response size for URL-health tooltip display.')
    is_read = models.BooleanField(default=False, db_index=True, help_text='Address Book review state. False is shown as New; True is shown as Seen.')
    last_seen = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True, help_text='When this Address Book entry was moved to the Recycle Bin.')


class ImportCandidate(models.Model):
    SOURCE = [('text', 'Free text'), ('document', 'Uploaded document'), ('mail', 'Mailbox scan')]
    source = models.CharField(max_length=20, choices=SOURCE)
    company = models.CharField(max_length=220, blank=True)
    role_title = models.CharField(max_length=300, blank=True)
    url = models.URLField(max_length=1000, blank=True)
    email = models.EmailField(blank=True)
    date_applied = models.DateTimeField(null=True, blank=True)
    channel = models.CharField(max_length=30, blank=True, default='')
    outcome_status = models.CharField(max_length=30, blank=True, default='', help_text='Imported application status/outcome; blank when the source does not say.')
    notes = models.TextField(blank=True, default='', help_text='Dedicated imported notes; preserved into applied-role history.')
    confidence = models.PositiveSmallIntegerField(default=50)
    raw_excerpt = models.TextField(blank=True)
    inference_method = models.CharField(max_length=40, default='heuristic', help_text='ai or heuristic fallback')
    inference_metadata = models.JSONField(default=dict, blank=True)
    imported = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class TrackingLinkRule(models.Model):
    name = models.CharField(max_length=200, unique=True)
    base_path = models.CharField(max_length=500, help_text='Example: /blog/winqemu')
    destination_url = models.URLField(max_length=1000)
    article_title = models.CharField(max_length=300, blank=True)
    article_keywords = models.TextField(blank=True, help_text='Comma-separated article-native suffix words such as build, exe, vs')
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class TrackingSuffixReserve(models.Model):
    rule = models.OneToOneField(TrackingLinkRule, on_delete=models.CASCADE, related_name='suffix_reserve')
    suffixes = models.JSONField(default=list, blank=True)
    cursor = models.PositiveIntegerField(default=0)
    generated_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.rule.name}: {len(self.suffixes or [])} reserved suffixes'


class TrackingLink(models.Model):
    rule = models.ForeignKey(TrackingLinkRule, on_delete=models.PROTECT, related_name='links')
    application = models.ForeignKey(Application, on_delete=models.SET_NULL, null=True, blank=True, related_name='tracking_links')
    suffix = models.CharField(max_length=120)
    path = models.CharField(max_length=700, unique=True)
    full_url = models.URLField(max_length=1000, unique=True)
    retired = models.BooleanField(default=False)
    click_count = models.PositiveIntegerField(default=0)
    likely_human_clicks = models.PositiveIntegerField(default=0)
    first_click = models.DateTimeField(null=True, blank=True)
    last_click = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True, help_text='When this tracking link was moved to the Recycle Bin.')
    created_at = models.DateTimeField(auto_now_add=True)


class TrackingClick(models.Model):
    tracking_link = models.ForeignKey(TrackingLink, on_delete=models.CASCADE, related_name='clicks')
    source_key = models.CharField(max_length=160, unique=True)
    viewed_at = models.DateTimeField(default=timezone.now)
    ip_address = models.CharField(max_length=255, blank=True)
    user_agent = models.TextField(blank=True)
    referrer = models.TextField(blank=True)
    likely_bot = models.BooleanField(default=False)
    source_table = models.CharField(max_length=80, default='request_logs')
    raw_uri = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-viewed_at']


class AIProviderConfig(models.Model):
    PROVIDERS = [('ollama', 'Ollama local'), ('openai', 'OpenAI'), ('gemini', 'Gemini'), ('openrouter', 'OpenRouter')]
    provider = models.CharField(max_length=30, choices=PROVIDERS, unique=True)
    enabled = models.BooleanField(default=True)
    base_url = models.CharField(max_length=500, blank=True)
    api_key_enc = models.TextField(blank=True)
    default_model = models.CharField(max_length=200, blank=True)
    stage_routes = models.JSONField(default=dict, blank=True)
    last_test_ok = models.BooleanField(default=False)
    last_test_message = models.TextField(blank=True)
    last_test_at = models.DateTimeField(null=True, blank=True)
    max_output_tokens = models.PositiveIntegerField(null=True, blank=True, help_text='Cloud-provider output cap. Local Ollama has no provider billing cap.')
    capabilities = models.JSONField(default=dict, blank=True, help_text='Last validated provider/model capability hints, including web research support.')


class ChatbotMessage(models.Model):
    ROLE = [('user','User'),('assistant','Assistant')]
    session_key = models.CharField(max_length=120, blank=True, db_index=True)
    role = models.CharField(max_length=20, choices=ROLE)
    text = models.TextField()
    links = models.JSONField(default=list, blank=True)
    source_provider = models.CharField(max_length=40, blank=True)
    source_model = models.CharField(max_length=300, blank=True)
    at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['at', 'id']


class ApplicationStatusEvent(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='status_events')
    old_status = models.CharField(max_length=30, blank=True)
    new_status = models.CharField(max_length=30)
    at = models.DateTimeField(auto_now_add=True, db_index=True)
    source = models.CharField(max_length=80, blank=True, default='application')

    class Meta:
        ordering = ['-at']


class UsageThresholdNotification(models.Model):
    period_key = models.CharField(max_length=80, db_index=True)
    metric_key = models.CharField(max_length=120, db_index=True)
    metric_label = models.CharField(max_length=200, blank=True)
    threshold = models.PositiveSmallIntegerField()
    used = models.PositiveBigIntegerField(default=0)
    limit = models.PositiveBigIntegerField(default=0)
    campaign_name = models.CharField(max_length=200, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('period_key','metric_key','threshold')
        ordering = ['-sent_at']


class UsageMetric(models.Model):
    at = models.DateTimeField(default=timezone.now)
    category = models.CharField(max_length=80)
    provider = models.CharField(max_length=120, blank=True)
    model = models.CharField(max_length=200, blank=True)
    stage = models.CharField(max_length=120, blank=True)
    requests = models.PositiveIntegerField(default=0)
    tokens_in = models.PositiveIntegerField(default=0)
    tokens_out = models.PositiveIntegerField(default=0)
    reasoning_tokens = models.PositiveIntegerField(default=0)
    web_search_queries = models.PositiveIntegerField(default=0)
    pages = models.PositiveIntegerField(default=0)
    errors = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    bytes_downloaded = models.PositiveBigIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)


class AIRequestLog(models.Model):
    STATUS = [('queued','Queued'),('running','Running'),('completed','Completed'),('empty_response','Empty response'),('recovered_response','Recovered response'),('malformed_response','Malformed response'),('failed','Failed')]
    at = models.DateTimeField(default=timezone.now, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS, default='completed', db_index=True)
    provider = models.CharField(max_length=80, blank=True)
    model = models.CharField(max_length=200, blank=True)
    stage = models.CharField(max_length=120, blank=True, db_index=True)
    runtime = models.CharField(max_length=20, blank=True, help_text='local or cloud', db_index=True)
    subject_type = models.CharField(max_length=60, blank=True, db_index=True)
    subject_id = models.CharField(max_length=120, blank=True)
    subject_label = models.CharField(max_length=300, blank=True)
    input_text = models.TextField(blank=True)
    output_text = models.TextField(blank=True)
    raw_output_text = models.TextField(blank=True, help_text='Original provider output before conservative structured-response recovery; retained for diagnostics.')
    attachments = models.JSONField(default=list, blank=True)
    tokens_in = models.PositiveIntegerField(default=0)
    tokens_out = models.PositiveIntegerField(default=0)
    reasoning_tokens = models.PositiveIntegerField(default=0)
    web_search_queries = models.PositiveIntegerField(default=0)
    token_usage_source = models.CharField(max_length=24, default='unknown', choices=[('provider_reported','Provider reported'),('estimated','Estimated'),('unknown','Unknown')])
    duration_ms = models.PositiveIntegerField(null=True, blank=True, db_index=True, help_text='End-to-end model request duration in milliseconds.')
    ok = models.BooleanField(default=True)
    error = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-at']


class ResourceSample(models.Model):
    at = models.DateTimeField(default=timezone.now)
    cpu_percent = models.FloatField(default=0)
    memory_percent = models.FloatField(default=0)
    memory_used_mb = models.PositiveIntegerField(default=0)
    memory_total_mb = models.PositiveIntegerField(default=0)
    disk_used_mb = models.PositiveIntegerField(default=0)
    disk_total_mb = models.PositiveIntegerField(default=0)
    gpu_percent = models.FloatField(null=True, blank=True)
    gpu_memory_percent = models.FloatField(null=True, blank=True)
    gpu_vram_used_mb = models.PositiveIntegerField(null=True, blank=True)
    gpu_vram_total_mb = models.PositiveIntegerField(null=True, blank=True)
    gpu_label = models.CharField(max_length=200, blank=True)
    # 0.11.144 keeps data-quality provenance with every persisted GPU point.  A
    # stale-but-bounded carried value is distinguishable from a fresh probe instead
    # of silently turning into NULL and creating an unexplained historical hole.
    gpu_sample_age_seconds = models.FloatField(null=True, blank=True)
    gpu_telemetry_state = models.CharField(max_length=24, default='legacy', blank=True)
    host_telemetry_age_seconds = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ['-at']


class ResourceHourly(models.Model):
    """Durable hourly hardware roll-up independent of detailed-sample retention.

    The raw 15-second ResourceSample table remains the source for short-range views.
    This compact archive protects long-range CPU/RAM/GPU history from collection gaps,
    cleanup of detailed rows, and future changes to raw-sample retention.
    """
    hour = models.DateTimeField(unique=True, db_index=True)
    last_sample_at = models.DateTimeField(null=True, blank=True)
    sample_count = models.PositiveIntegerField(default=0)
    cpu_avg = models.FloatField(null=True, blank=True)
    cpu_min = models.FloatField(null=True, blank=True)
    cpu_max = models.FloatField(null=True, blank=True)
    memory_avg = models.FloatField(null=True, blank=True)
    memory_min = models.FloatField(null=True, blank=True)
    memory_max = models.FloatField(null=True, blank=True)
    memory_used_mb = models.PositiveIntegerField(default=0)
    memory_total_mb = models.PositiveIntegerField(default=0)
    disk_used_mb = models.PositiveIntegerField(default=0)
    disk_total_mb = models.PositiveIntegerField(default=0)
    gpu_avg = models.FloatField(null=True, blank=True)
    gpu_min = models.FloatField(null=True, blank=True)
    gpu_max = models.FloatField(null=True, blank=True)
    gpu_sample_count = models.PositiveIntegerField(default=0)
    gpu_stale_count = models.PositiveIntegerField(default=0)
    gpu_label = models.CharField(max_length=200, blank=True)
    gpu_vram_used_mb = models.PositiveIntegerField(null=True, blank=True)
    gpu_vram_total_mb = models.PositiveIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-hour']


class CloudBudgetUsage(models.Model):
    """Atomic daily cloud-spend counters used as hard safety guardrails."""
    day = models.DateField(unique=True, default=timezone.localdate)
    requests = models.PositiveIntegerField(default=0)
    web_searches = models.PositiveIntegerField(default=0)
    tokens_in = models.PositiveBigIntegerField(default=0)
    tokens_out = models.PositiveBigIntegerField(default=0)
    reasoning_tokens = models.PositiveBigIntegerField(default=0)
    tokens_out_reasoning = models.PositiveBigIntegerField(default=0)
    passive_enrichment = models.PositiveIntegerField(default=0)
    page_recovery = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)


class CloudRunUsage(models.Model):
    """Per-campaign-run cloud counters so concurrent workers cannot overrun a run cap."""
    campaign_run = models.OneToOneField(CampaignRun, on_delete=models.CASCADE, related_name='cloud_usage')
    requests = models.PositiveIntegerField(default=0)
    web_searches = models.PositiveIntegerField(default=0)
    discovery_candidates = models.PositiveIntegerField(default=0)
    deep_research_candidates = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)


class CompanyResearchCache(models.Model):
    """Reusable stable company/domain research; role-specific facts stay on the record."""
    domain = models.CharField(max_length=255, unique=True)
    company = models.CharField(max_length=220, blank=True)
    data = models.JSONField(default=dict, blank=True)
    provider = models.CharField(max_length=80, blank=True)
    model = models.CharField(max_length=200, blank=True)
    researched_at = models.DateTimeField(default=timezone.now)
    evidence_hash = models.CharField(max_length=64, blank=True)



class BlogStatsConfig(SingletonModel):
    enabled = models.BooleanField(default=True)
    host = models.CharField(max_length=255, blank=True)
    port = models.PositiveIntegerField(default=3306)
    database = models.CharField(max_length=120, blank=True)
    username = models.CharField(max_length=120, blank=True)
    password_enc = models.TextField(blank=True)
    query_mode = models.CharField(max_length=30, default='toughdev_native')
    view_name = models.CharField(max_length=120, default='portal_shortlink_pageviews')
    table_name = models.CharField(max_length=120, default='pageviews')
    method_column = models.CharField(max_length=120, blank=True)
    path_column = models.CharField(max_length=120, default='page_id')
    timestamp_column = models.CharField(max_length=120, default='last_accessed')
    user_agent_column = models.CharField(max_length=120, default='last_useragent')
    ip_column = models.CharField(max_length=120, default='user_ip')
    method_value = models.CharField(max_length=80, blank=True)
    last_sync = models.DateTimeField(null=True, blank=True)


class CompanyLead(models.Model):
    company = models.CharField(max_length=220)
    origin_campaign = models.ForeignKey(Campaign, on_delete=models.SET_NULL, null=True, blank=True, related_name='origin_leads', help_text='Campaign that first discovered this Hidden Lead. Later campaign matches remain in campaigns as rediscovery provenance.')
    campaigns = models.ManyToManyField(Campaign, blank=True, related_name='leads')
    source = models.ForeignKey(SearchSource, on_delete=models.SET_NULL, null=True, blank=True, related_name='hidden_leads')
    country = models.CharField(max_length=120, blank=True)
    locations = models.JSONField(default=list, blank=True, help_text='Evidence-grounded company/lead locations; supports multiple countries and recruiter regions.')
    match_summary = models.TextField(blank=True)
    summary = models.TextField(blank=True, default='', help_text='Short company/market-study summary derived from public page evidence.')
    focus = models.CharField(max_length=80, blank=True, default='', db_index=True, help_text='Content-based Focus classification, independent from Campaign provenance.')
    evidence = models.TextField(blank=True)
    evidence_translation = models.TextField(blank=True)
    company_intel = models.JSONField(default=dict, blank=True, help_text='Collected public company information for this Hidden Lead.')
    ai_state = models.JSONField(default=dict, blank=True, help_text='Automatic/manual AI enrichment lifecycle state keyed by enrichment kind and evidence generation.')
    search_url = models.URLField(max_length=1000, blank=True)
    target_url = models.URLField(max_length=1000, blank=True)
    source_url = models.URLField(max_length=1000, blank=True)
    language_code = models.CharField(max_length=16, blank=True, default='')
    contact_name = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_url = models.URLField(max_length=1000, blank=True, help_text='Direct public contact page discovered for this Hidden Lead, when different from the lead URL.')
    score = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=40, default='review')
    draft_subject = models.CharField(max_length=500, blank=True)
    draft_body = models.TextField(blank=True)
    user_deleted = models.BooleanField(default=False, db_index=True, help_text='Whether this Hidden Lead is currently in the Recycle Bin.')
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True, help_text='When this Hidden Lead was moved to the Recycle Bin.')
    is_read = models.BooleanField(default=False, help_text='Whether the Hidden Lead details have been reviewed.')
    note = models.TextField(blank=True, default='', help_text='Private note about this Hidden Lead.')
    target_http_status = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Most recent direct HTTP status observed for the target URL.')
    target_checked_at = models.DateTimeField(null=True, blank=True, help_text='When the Hidden Lead target URL was last checked directly.')
    target_check_error = models.CharField(max_length=500, blank=True, default='', help_text='Most recent target URL check error, if any.')
    target_response_bytes = models.PositiveBigIntegerField(default=0, help_text='Latest useful successful response size for URL-health tooltip display.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class AuditLog(models.Model):
    at = models.DateTimeField(default=timezone.now)
    version = models.CharField(max_length=32, blank=True, default='')
    actor = models.CharField(max_length=200, blank=True)
    action = models.CharField(max_length=120)
    object_type = models.CharField(max_length=120, blank=True)
    object_id = models.CharField(max_length=120, blank=True)
    summary = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    def save(self, *args, **kwargs):
        if not self.version:
            try:
                from django.conf import settings
                self.version=str(getattr(settings,'PORTAL_VERSION','') or '')[:32]
            except Exception:
                self.version=''
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-at']


class PerformanceRun(models.Model):
    KIND = [
        ('chat', 'Simple chat'), ('search', 'Search provider test'), ('scrape', 'Page scrape'),
        ('summarize', 'Summarize content'), ('extract', 'JD extraction'), ('rank', 'Opportunity ranking'),
        ('age_check', 'Job-post age analysis'), ('docx_to_pdf', 'DOCX to PDF conversion'),
    ]
    kind = models.CharField(max_length=40, choices=KIND)
    provider = models.CharField(max_length=80, blank=True)
    model = models.CharField(max_length=200, blank=True)
    device = models.CharField(max_length=80, blank=True, help_text='Informational device/runtime selection for the lab.')
    input_text = models.TextField(blank=True)
    input_url = models.URLField(max_length=1000, blank=True)
    output_text = models.TextField(blank=True)
    output_file = models.FileField(upload_to='performance/%Y/%m/', blank=True)
    ok = models.BooleanField(default=False)
    latency_ms = models.PositiveIntegerField(default=0)
    tokens_in = models.PositiveIntegerField(default=0)
    tokens_out = models.PositiveIntegerField(default=0)
    bytes_downloaded = models.PositiveBigIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']


class SourceBlacklist(models.Model):
    SCOPE = [('all','Always'),('opportunities','Opportunities Only'),('hidden_leads','Hidden Leads Only')]
    domain = models.CharField(max_length=255, blank=True, db_index=True)
    label = models.CharField(max_length=255, blank=True, db_index=True)
    reason = models.CharField(max_length=500, blank=True)
    scope = models.CharField(max_length=24, choices=SCOPE, default='all')
    enabled = models.BooleanField(default=True)
    built_in = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True, help_text='When this blacklist entry was moved to the Recycle Bin.')

    class Meta:
        ordering = ['domain', 'label']

    def __str__(self):
        return self.domain or self.label


class SavedFilter(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='portal_saved_filters')
    screen = models.CharField(max_length=80)
    name = models.CharField(max_length=120)
    query_string = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('owner', 'screen', 'name')
        ordering = ['screen', 'name']

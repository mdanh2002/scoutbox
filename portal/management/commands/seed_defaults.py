import os
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from portal.models import (Profile, PortalSettings, SearchSource, Campaign, EmailProfile,
                           AIProviderConfig, BlogStatsConfig, FacebookConfig, BackgroundJob, DocumentAsset)
from portal.services.crypto import encrypt
from portal.services.ai import default_stage_routes
from portal.services.forum_sources import seed_forum_sources

SOURCE_GROUPS = {
    'General web search': [
        ('Google','search_engine','https://www.google.com'), ('Bing','search_engine','https://www.bing.com'),
        ('DuckDuckGo','search_engine','https://duckduckgo.com'), ('Brave Search','search_engine','https://search.brave.com'),
        ('Yahoo Search','search_engine','https://search.yahoo.com'), ('Startpage','search_engine','https://www.startpage.com'),
        ('Ecosia','search_engine','https://www.ecosia.org'), ('Mojeek','search_engine','https://www.mojeek.com')],
    'Regional / language search': [
        ('Yandex','regional_search','https://yandex.com'),('Baidu','regional_search','https://www.baidu.com'),('Naver','regional_search','https://www.naver.com')],
    'Major job sites': [
        ('LinkedIn Jobs','job_site','https://www.linkedin.com/jobs'),('Indeed','job_site','https://www.indeed.com'),('Glassdoor','job_site','https://www.glassdoor.com'),
        ('ZipRecruiter','job_site','https://www.ziprecruiter.com'),('Monster','job_site','https://www.monster.com'),('Dice','job_site','https://www.dice.com'),('CareerBuilder','job_site','https://www.careerbuilder.com'),
        ('StepStone Germany','job_site','https://www.stepstone.de'),('France Travail','job_site','https://www.francetravail.fr'),('InfoJobs Spain','job_site','https://www.infojobs.net'),
        ('Net-Empregos Portugal','job_site','https://www.net-empregos.com'),('Nationale Vacaturebank','job_site','https://www.nationalevacaturebank.nl'),('Cliclavoro Italy','job_site','https://www.cliclavoro.gov.it'),
        ('Pracuj.pl','job_site','https://www.pracuj.pl'),('Jobs.cz','job_site','https://www.jobs.cz'),('Jobindex Denmark','job_site','https://www.jobindex.dk'),
        ('Arbetsförmedlingen Platsbanken','job_site','https://arbetsformedlingen.se/platsbanken'),('FINN Jobs','job_site','https://www.finn.no/job/search'),('Jobly Finland','job_site','https://www.jobly.fi'),
        ('Daijob','job_site','https://www.daijob.com'),('JobKorea','job_site','https://www.jobkorea.co.kr'),('Vagas.com.br','job_site','https://www.vagas.com.br'),('OCCMundial','job_site','https://www.occ.com.mx')],
    'Startup / technology jobs': [
        ('Wellfound','job_site','https://wellfound.com/jobs'),('Built In','job_site','https://builtin.com/jobs'),('YC Work at a Startup','job_site','https://www.workatastartup.com/jobs')],
    'Remote-focused boards': [
        ('Remote OK','job_site','https://remoteok.com'),('We Work Remotely','job_site','https://weworkremotely.com'),('Remotive','job_site','https://remotive.com'),('Working Nomads','job_site','https://www.workingnomads.com'),('Himalayas','job_site','https://himalayas.app'),('Jobicy','job_site','https://jobicy.com'),('Jobspresso','job_site','https://jobspresso.co'),('Virtual Vocations','job_site','https://www.virtualvocations.com'),('FlexJobs','job_site','https://www.flexjobs.com')],
    'Singapore / APAC': [
        ('MyCareersFuture','job_site','https://www.mycareersfuture.gov.sg'),('JobStreet','job_site','https://www.jobstreet.com'),('JobsDB','job_site','https://www.jobsdb.com'),('SEEK','job_site','https://www.seek.com.au')],
    'ATS / hosted career pages': [
        ('Company career pages','company_career_pages',''),
        ('Greenhouse','ats','https://www.greenhouse.com'),('Lever','ats','https://www.lever.co'),('Ashby','ats','https://www.ashbyhq.com'),('Workable','ats','https://www.workable.com'),('SmartRecruiters','ats','https://www.smartrecruiters.com'),('Teamtailor','ats','https://www.teamtailor.com'),('Recruitee','ats','https://recruitee.com'),('Personio','ats','https://www.personio.com'),('BambooHR','ats','https://www.bamboohr.com'),('Jobvite','ats','https://www.jobvite.com'),('iCIMS','ats','https://www.icims.com'),('Workday','ats','https://www.workday.com'),('Oracle Taleo','ats','https://www.oracle.com/human-capital-management/taleo/')],
    'Developer / engineering communities': [
        ('GitHub','community','https://github.com'),('GitLab','community','https://gitlab.com'),('Lobsters','community','https://lobste.rs'),('Hacker News','community','https://news.ycombinator.com'),
        ('Hacker News Who is Hiring','community','https://news.ycombinator.com'),('DEV Community Hiring','community','https://dev.to/t/hiring'),('Indie Hackers Jobs','community','https://www.indiehackers.com/jobs')],
    'Public community / social sources': [
        ('Reddit','social','https://www.reddit.com'),('Facebook public posts','social','https://www.facebook.com'),('LinkedIn public posts','social','https://www.linkedin.com'),('Bluesky','social','https://bsky.app'),('Mastodon','social','https://joinmastodon.org'),('Welcome to the Jungle','job_site','https://www.welcometothejungle.com')],
    'Excluded / low-value marketplaces': [
        ('Upwork','marketplace','https://www.upwork.com'),('Freelancer','marketplace','https://www.freelancer.com'),
        ('Fiverr','marketplace','https://www.fiverr.com'),('PeoplePerHour','marketplace','https://www.peopleperhour.com'),
        ('Guru','marketplace','https://www.guru.com'),('Truelancer','marketplace','https://www.truelancer.com'),
        ('Workana','marketplace','https://www.workana.com'),
    ],
}

DIRECT_SOURCE_CONFIG = {
    'LinkedIn Jobs': {'direct_adapter':'linkedin_job_library','direct_capability':'Job Library API · when configured','discovery_capability':'Job Library API when configured · Local + search engine · Cloud direct only','credential_env':'LINKEDIN_JOB_LIBRARY_ACCESS_TOKEN'},
    'Glassdoor': {'direct_adapter':'glassdoor_jobs','direct_capability':'Jobs API · when explicitly configured','discovery_capability':'Jobs API when configured · Local + search engine · Cloud direct only','credential_env':'GLASSDOOR_API_KEY'},
    'Indeed': {'discovery_capability':'Partner-only direct search · Local search engine · Cloud native web'},
    'ZipRecruiter': {'discovery_capability':'Local search engine · Cloud native web'},
    'Dice': {'discovery_capability':'Local search engine · Cloud native web'},
    'Monster': {'discovery_capability':'Local search engine · Cloud native web'},
    'Wellfound': {'direct_adapter':'wellfound_page','direct_capability':'Deterministic direct page','discovery_capability':'Direct page · Local + search engine · Cloud direct only'},
    'YC Work at a Startup': {'direct_adapter':'yc_jobs','direct_capability':'YC Jobs direct pages','discovery_capability':'YC Jobs direct pages · Local + search engine · Cloud direct only'},
    'Remote OK': {'direct_adapter':'remoteok','direct_capability':'Direct job API','discovery_capability':'Direct job API · Local + search engine · Cloud direct only'},
    'Remotive': {'direct_adapter':'remotive','direct_capability':'Direct job API','discovery_capability':'Direct job API · Local + search engine · Cloud direct only'},
    'Himalayas': {'direct_adapter':'himalayas','direct_capability':'Direct job API','discovery_capability':'Direct job API · Local + search engine · Cloud direct only'},
    'Jobicy': {'direct_adapter':'jobicy','direct_capability':'Direct job API','discovery_capability':'Direct job API · Local + search engine · Cloud direct only'},
    'We Work Remotely': {'direct_adapter':'wwr_rss','direct_capability':'RSS / feed','discovery_capability':'Official RSS/feed · Local + search engine · Cloud direct only'},
    'Hacker News Who is Hiring': {'direct_adapter':'hn_whoishiring','direct_capability':'Community API','discovery_capability':'Community API · Local + search engine · Cloud direct only'},
    'Lobsters': {'direct_adapter':'lobsters_jobs','direct_capability':'Job-tag RSS','discovery_capability':'Community RSS · Local + search engine · Cloud direct only'},
    'DEV Community Hiring': {'direct_adapter':'dev_hiring','direct_capability':'Community API','discovery_capability':'Community API · Local + search engine · Cloud direct only'},
    'Indie Hackers Jobs': {'direct_adapter':'indiehackers_jobs','direct_capability':'Deterministic direct page','discovery_capability':'Direct page · Local + search engine · Cloud direct only'},
    'Reddit': {'direct_adapter':'reddit','direct_capability':'Reddit API','discovery_capability':'Community API · Local + search engine · Cloud direct only','oauth_client_id_env':'REDDIT_CLIENT_ID','oauth_client_secret_env':'REDDIT_CLIENT_SECRET','user_agent_env':'REDDIT_USER_AGENT'},
    'Greenhouse': {'direct_adapter':'greenhouse','direct_capability':'ATS API · learned employer boards','discovery_capability':'ATS API · Local + search engine · Cloud direct only'},
    'Lever': {'direct_adapter':'lever','direct_capability':'ATS API · learned employer boards','discovery_capability':'ATS API · Local + search engine · Cloud direct only'},
    'Ashby': {'direct_adapter':'ashby','direct_capability':'ATS API · learned employer boards','discovery_capability':'ATS API · Local + search engine · Cloud direct only'},
    'SmartRecruiters': {'direct_adapter':'smartrecruiters','direct_capability':'ATS API · learned employer boards','discovery_capability':'ATS API · Local + search engine · Cloud direct only'},
}

MARKET_SOURCE_CONFIG = {
    'StepStone Germany':'de','France Travail':'fr','InfoJobs Spain':'es','Net-Empregos Portugal':'pt',
    'Nationale Vacaturebank':'nl','Cliclavoro Italy':'it','Pracuj.pl':'pl','Jobs.cz':'cz',
    'Jobindex Denmark':'dk','Arbetsförmedlingen Platsbanken':'se','FINN Jobs':'no','Jobly Finland':'fi',
    'Daijob':'jp','JobKorea':'kr','Vagas.com.br':'br','OCCMundial':'mx',
}



class Command(BaseCommand):
    help='Seed safe development defaults and built-in source presets.'
    def handle(self,*args,**opts):
        PortalSettings.objects.get_or_create(pk=1)
        profile,_=Profile.objects.get_or_create(pk=1)
        if not profile.operating_location: profile.operating_location='Singapore'; profile.save()
        BlogStatsConfig.objects.get_or_create(pk=1,defaults={'enabled':True})
        fb,_=FacebookConfig.objects.get_or_create(pk=1)
        if os.getenv('META_ACCESS_TOKEN') and not fb.graph_access_token_enc:
            fb.graph_access_token_enc=encrypt(os.getenv('META_ACCESS_TOKEN'))
            fb.graph_page_ids=os.getenv('META_PAGE_IDS','')
            fb.save()

        admin_email=os.getenv('PORTAL_ADMIN_EMAIL','admin@portal.test')
        password=os.getenv('PORTAL_ADMIN_PASSWORD','ChangeMe-Portal-123!')
        u,created=User.objects.get_or_create(username=admin_email,defaults={'email':admin_email,'first_name':os.getenv('PORTAL_ADMIN_NAME','Portal Admin'),'is_staff':True,'is_superuser':True})
        if created: u.set_password(password); u.save()

        had_profiles=EmailProfile.objects.exists()
        internal,created_internal=EmailProfile.objects.get_or_create(template='internal')
        if created_internal:
            internal.active=not had_profiles
            internal.imap_host=os.getenv('DEV_IMAP_HOST','greenmail'); internal.imap_port=int(os.getenv('DEV_IMAP_PORT','3143')); internal.imap_ssl=False
            internal.imap_email=os.getenv('DEV_IMAP_EMAIL','candidate@application.test'); internal.imap_username=os.getenv('DEV_IMAP_USER','candidate@application.test')
            internal.imap_password_enc=encrypt(os.getenv('DEV_IMAP_PASSWORD','candidate-imap-demo'))
            internal.inbox_folder='INBOX'; internal.sent_folder='Sent'; internal.drafts_folder='Drafts'
            internal.smtp_host=os.getenv('MAILPIT_SMTP_HOST','mailpit'); internal.smtp_port=int(os.getenv('MAILPIT_SMTP_PORT','1025')); internal.smtp_tls=False
            internal.smtp_username=os.getenv('MAILPIT_SMTP_USER','portal-smtp')
            internal.smtp_password_enc=encrypt(os.getenv('MAILPIT_SMTP_PASSWORD','portal-smtp-demo'))
            internal.notification_from_name=os.getenv('NOTIFICATION_FROM_NAME','Application Portal'); internal.notification_from_email=os.getenv('NOTIFICATION_FROM_EMAIL','portal@mailpit.test'); internal.save()
        external,_=EmailProfile.objects.get_or_create(template='external',defaults={'active':False})
        if not EmailProfile.objects.filter(active=True).exists():
            internal.active=True; internal.save(update_fields=['active','updated_at'])

        for provider,enabled,url in [('ollama',True,os.getenv('OLLAMA_BASE_URL','http://host.docker.internal:11434')),('openai',False,'https://api.openai.com/v1'),('gemini',False,'https://generativelanguage.googleapis.com/v1beta'),('openrouter',False,'https://openrouter.ai/api/v1')]:
            AIProviderConfig.objects.get_or_create(provider=provider,defaults={'enabled':enabled,'base_url':url})
        oll_cfg=AIProviderConfig.objects.filter(provider='ollama').first()
        if oll_cfg and not oll_cfg.stage_routes:
            oll_cfg.stage_routes=default_stage_routes({})
            oll_cfg.save(update_fields=['stage_routes'])

        # Cloud AI discovery is controlled exclusively by AI & Discovery -> Discovery Mode.
        # Keep historical provenance rows, but mark legacy selector rows as internal cloud
        # sources so the Search Sources screen and Local planners ignore them.
        SearchSource.objects.filter(category__iexact='Cloud AI Discovery').update(source_type='cloud_ai',enabled=True)

        for category,items in SOURCE_GROUPS.items():
            for name,stype,url in items:
                low=name in {'Upwork','Freelancer','Fiverr','PeoplePerHour','Guru','Truelancer','Workana'}
                defaults={'category':category,'source_type':stype,'base_url':url,'enabled':not low,'low_value_marketplace':low,'adapter_status':'active' if name in {'Google','Bing','DuckDuckGo','Brave Search','Yahoo Search','Mojeek','Startpage','Ecosia','Yandex','Baidu','Naver'} else 'preset','public_fallback':name in {'Google','Bing','DuckDuckGo','Brave Search','Yahoo Search','Mojeek','Startpage','Ecosia','Yandex','Baidu','Naver'},'requires_credentials':False,'preferred_initial':name in {'Google','Bing','DuckDuckGo','Brave Search','Yahoo Search','Mojeek','Startpage','Ecosia','Yandex','Naver'}}
                obj,created_source=SearchSource.objects.get_or_create(name=name,defaults=defaults)
                if name=='Company career pages':
                    cfg=dict(obj.config_json or {}); cfg.update({'company_career_pages':True,'local_only':True}); obj.config_json=cfg
                    obj.enabled=True if created_source else obj.enabled
                    obj.adapter_status='preset'; obj.public_fallback=False; obj.requires_credentials=False
                    obj.notes='Local AI Discovery umbrella: configured search engines locate relevant companies, then search their own hiring/collaboration/project pages. Not used by Cloud Web Discovery.'
                    obj.save(update_fields=['config_json','enabled','adapter_status','public_fallback','requires_credentials','notes'])
                if name in DIRECT_SOURCE_CONFIG:
                    cfg=dict(obj.config_json or {}); cfg.update(DIRECT_SOURCE_CONFIG[name]); obj.config_json=cfg
                    obj.adapter_status='direct'
                    # Shipped capability/category metadata is authoritative; enabled/priority remain operator-owned.
                    obj.category=category; obj.source_type=stype; obj.base_url=url
                    obj.save(update_fields=['config_json','adapter_status','category','source_type','base_url'])
                if name in MARKET_SOURCE_CONFIG:
                    cfg=dict(obj.config_json or {}); cfg.update({'market_specific':True,'market_codes':[MARKET_SOURCE_CONFIG[name]],'discovery_capability':'Market-specific site search · search engine'}); obj.config_json=cfg
                    obj.category=category; obj.source_type=stype; obj.base_url=url
                    obj.save(update_fields=['config_json','category','source_type','base_url'])
                if name=='Google':
                    cfg=dict(obj.config_json or {}); cfg.setdefault('credential_env','GOOGLE_SEARCH_API_KEY'); cfg.setdefault('cx_env','GOOGLE_SEARCH_CX'); obj.config_json=cfg; obj.save(update_fields=['config_json'])
                elif name=='Brave Search':
                    cfg=dict(obj.config_json or {}); cfg.setdefault('credential_env','BRAVE_SEARCH_API_KEY'); obj.config_json=cfg; obj.save(update_fields=['config_json'])
                elif name=='Mojeek':
                    cfg=dict(obj.config_json or {}); cfg.setdefault('credential_env','MOJEEK_SEARCH_API_KEY'); obj.config_json=cfg; obj.save(update_fields=['config_json'])
                elif name=='Naver':
                    cfg=dict(obj.config_json or {}); cfg.setdefault('credential_env','NAVER_SEARCH_CLIENT_SECRET'); cfg.setdefault('client_id_env','NAVER_SEARCH_CLIENT_ID'); obj.config_json=cfg; obj.save(update_fields=['config_json'])
                if not created_source:
                    # Preserve ordinary user tuning, but keep shipped adapters/capabilities current.
                    changed=[]
                    for field,value in [('category',category),('source_type',stype),('base_url',url),('low_value_marketplace',low)]:
                        if not getattr(obj,field): setattr(obj,field,value); changed.append(field)
                    if name in {'Google','Bing','DuckDuckGo','Brave Search','Yahoo Search','Mojeek','Startpage','Ecosia','Yandex','Baidu','Naver'}:
                        for field,value in [('adapter_status','active'),('public_fallback',True),('requires_credentials',False)]:
                            if getattr(obj,field)!=value: setattr(obj,field,value); changed.append(field)
                    if changed: obj.save(update_fields=list(dict.fromkeys(changed)))

        # 0.10.59 forum sources are seeded as first-class SearchSource rows.
        # Existing 0.10.58 community owners such as Reddit/GitHub/DEV are skipped by the catalog.
        seed_forum_sources(SearchSource)

        # One automatic campaign is enabled by default. It requires no manual keyword
        # maintenance: the query planner derives its focus from active Resumes + preference text.
        Campaign.objects.get_or_create(
            name='Resume-first Automatic Discovery',
            defaults={
                'template':'Automatic Resume-first', 'location':profile.operating_location or 'Singapore',
                'role_families':'', 'technologies':'',
                'engagement_types':'full-time, part-time, contract, agency/consulting, one-time project, collaboration, unknown',
                'company_sizes':'solo/very small, small, startup, medium, unknown',
                'enabled':True,
            },
        )

        # One-time release repair: older Hidden Leads/Address Book rows may have a
        # baseline Company Info object but no age/size because Cloud lead persistence
        # discarded the structured company fields and list views did not queue research.
        # 0.10.51 makes this repair explicitly non-blocking: an old waiting/orphaned
        # 0.10.41 backfill is finalized instead of being allowed to keep the dashboard
        # in a permanent queued state while Local Discovery runs.
        ps=PortalSettings.objects.get_or_create(pk=1)[0]
        if str(ps.release_backfill_version or '') != '0.10.41':
            dispatch_job=None; created_job=False
            try:
                from celery import current_app
                with transaction.atomic():
                    locked=PortalSettings.objects.select_for_update().get(pk=1)
                    if str(locked.release_backfill_version or '') != '0.10.41':
                        now=timezone.now()
                        job=BackgroundJob.objects.filter(label='0.10.41 upgrade backfill',status__in=['queued','running']).order_by('-created_at').first()
                        if job:
                            result=dict(job.result or {})
                            wait_text='Waiting for Local Discovery' in str(job.message or '')
                            wait_state=str(result.get('wait_reason') or '')=='local_discovery_active'
                            baseline=job.started_at or job.created_at or now
                            stale_minutes=max(5,int(os.environ.get('SCOUTBOX_RELEASE_BACKFILL_STALE_MINUTES','15') or 15))
                            stale=bool(baseline and now-baseline >= timedelta(minutes=stale_minutes))
                            if wait_text or wait_state or stale:
                                result.update({
                                    'release':'0.10.41',
                                    'state':'completed_by_01051_startup_repair',
                                    'network_heavy_repair_skipped':True,
                                    'reason':'Finalized stale/waiting 0.10.41 upgrade backfill so it cannot block the dashboard behind Local Discovery.',
                                    'completed_at':now.isoformat(),
                                    'fixed_by_release':'0.10.51',
                                })
                                job.status='completed'; job.progress=100; job.finished_at=now
                                job.message='0.10.41 backfill finalized by 0.10.51 startup repair'
                                job.error=''; job.result=result
                                job.save(update_fields=['status','progress','finished_at','message','error','result'])
                                locked.release_backfill_version='0.10.41'
                                locked.save(update_fields=['release_backfill_version','updated_at'])
                                job=None
                        if str(locked.release_backfill_version or '') != '0.10.41':
                            if not job:
                                job=BackgroundJob.objects.create(kind='other',label='0.10.41 upgrade backfill',message='Queued',result={'release':'0.10.41'})
                                created_job=True
                            if created_job or job.status=='queued':
                                dispatch_job=job
                if dispatch_job:
                    try:
                        task=current_app.send_task('portal.tasks.release_company_context_backfill_job',args=[dispatch_job.pk])
                        dispatch_job.celery_task_id=task.id or ''
                        dispatch_job.save(update_fields=['celery_task_id'])
                    except Exception:
                        if created_job:
                            BackgroundJob.objects.filter(pk=dispatch_job.pk,status='queued').delete()
                        raise
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f'0.10.41 upgrade backfill could not be finalized or queued yet: {exc}'))

        # 0.11.128 one-time Candidate Profile vocabulary refresh. Earlier releases could
        # compress a broad Resume to 40 concepts/24 roles and could admit preference prose
        # when only one coincidental CV token matched. Queue a normal background rebuild so
        # upgrade/startup remains fast and model routing is identical to the Defaults button.
        try:
            terms_release='0.11.128'
            scope=dict(profile.scope_json or {})
            if str(scope.get('profile_terms_version') or '') != terms_release and DocumentAsset.objects.filter(kind='cv',active=True).exists():
                label=f'{terms_release} Candidate Profile vocabulary refresh'
                refresh_job=BackgroundJob.objects.filter(label=label,status__in=['queued','running']).order_by('-created_at').first()
                created_refresh=False
                if refresh_job is None:
                    refresh_job=BackgroundJob.objects.create(kind='prepare',label=label,message='Queued',result={'release':terms_release,'reason':'one_time_candidate_profile_vocabulary_refresh'})
                    created_refresh=True
                if created_refresh or (refresh_job.status=='queued' and not refresh_job.celery_task_id):
                    from celery import current_app
                    task=current_app.send_task('portal.tasks.candidate_profile_defaults_job',args=[refresh_job.pk,terms_release])
                    refresh_job.celery_task_id=task.id or ''
                    refresh_job.save(update_fields=['celery_task_id'])
                    self.stdout.write(self.style.SUCCESS(f'Queued one-time {terms_release} Candidate Profile vocabulary refresh.'))
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f'0.11.128 Candidate Profile vocabulary refresh could not be queued yet: {exc}'))

        # Saved campaign templates are created by the schema data migration.
        self.stdout.write(self.style.SUCCESS('Defaults seeded.'))

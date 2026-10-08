from pathlib import Path

root=Path(__file__).resolve().parents[1]
def read(rel): return (root/rel).read_text(encoding='utf-8')

assert read('VERSION').strip()=='0.11.122'
assert read('RELEASE_ID').strip()=='ScoutBox 0.11.122'
assert read('BUILD_INFO.txt').strip()=='ScoutBox v0.11.122'
assert read('README.md').splitlines()[0]=='# ScoutBox 0.11.122'
assert (root/'docs/RELEASE_NOTES_0.11.122.md').exists()

models=read('portal/models.py')
assert 'DEFAULT_OPPORTUNITY_CLOUD_REEVALUATION_PROMPT' in models
assert 'DEFAULT_HIDDEN_LEAD_CLOUD_REEVALUATION_PROMPT' in models
assert 'opportunity_cloud_reevaluation_prompt = models.TextField' in models
assert 'hidden_lead_cloud_reevaluation_prompt = models.TextField' in models

flt=read('portal/services/opportunity_filter.py')
assert "exceptional_interest_confidence >= 95" in flt
assert "candidate_geo_eligible or relocation_offered or visa_sponsorship" in flt
assert "buyer_direction == 'may_buy_from_candidate'" in flt
assert 'need_signal_confidence >= 80' in flt
assert "company_scale in {'micro','small'}" in flt
assert 'obsolete-media recovery' in flt
assert 'never a keyword mention such as IDE/SCSI/firmware' in flt
assert "CLOUD RE-EVALUATION INSTRUCTIONS:" in flt
assert "decision = 'convert_to_hidden_lead'" in flt
assert "decision = 'convert_to_opportunity'" in flt

views=read('portal/views.py')
assert 'def _manual_filter_cloud_prompt' in views
assert "_manual_filter_cloud_prompt(request,'opportunity',provider)" in views
assert "_manual_filter_cloud_prompt(request,'hidden_lead',provider)" in views
assert 'cloud_re_evaluation_prompt' in views

tasks=read('portal/tasks.py')
assert "def opportunity_filter_job(self, job_id, opportunity_ids, provider='', model='', internet_search=False, cloud_policy_prompt='')" in tasks
assert "def hidden_lead_filter_job(self, job_id, lead_ids, provider='', model='', internet_search=False, cloud_policy_prompt='')" in tasks
assert 'cloud_policy_prompt=cloud_policy_prompt' in tasks
# Address Book path must stay free of the new policy argument.
contact_parallel=tasks[tasks.index('def _parallel_contact_filter'):tasks.index('@shared_task(bind=True)\ndef opportunity_filter_job')]
assert 'cloud_policy_prompt' not in contact_parallel
contact_task=tasks[tasks.index('def contact_filter_job'):]
assert 'cloud_policy_prompt' not in contact_task.split('\n@shared_task',1)[0]

opp=read('templates/portal/opportunities.html')
assert 'Cloud re-evaluation instructions' in opp
assert 'id="opportunity-filter-cloud-prompt"' in opp
assert "body.set('cloud_re_evaluation_prompt',prompt.value||'')" in opp
assert 'Internet Search verifies the listing and refreshes company, contact, remote and post-age data.' not in opp
assert 'Fit is recalculated. Irrelevant entries may be recycled; application history is kept. ~1 AI request/item.' not in opp
lead=read('templates/portal/cold_contact.html')
assert 'Cloud re-evaluation instructions' in lead
assert 'id="hidden-lead-filter-cloud-prompt"' in lead
assert "body.set('cloud_re_evaluation_prompt',prompt.value||'')" in lead

norm=read('portal/services/query_normalizer.py')
assert 'def _repair_generated_quotes' in norm
assert '_BARE_DOMAIN_RE' in norm
assert "site=_normalize_site_scope('site:'+match.group(1))" in norm
planner=read('portal/services/queryplanner.py')
assert 'def _repair_unbalanced_generated_quotes' in planner
assert "text=_repair_unbalanced_generated_quotes(strip_external_exclusions(str(value or '')))" in planner

hn=read('portal/services/fresh_sources.py')
assert 'Fully enumerate the newest available monthly thread' in hn
assert "kids=kids[:250]+kids[-250:]" not in hn
hn_comment=hn[hn.index('def _hn_story_comment_rows'):hn.index('def _hn_direct_page_rows')]
assert "return rows,''" in hn_comment
hn_main=hn[hn.index('def _hn_whoishiring'):hn.index('def _lobsters_jobs')]
assert 'break' in hn_main
assert "return rows,''" in hn_main

mig=read('portal/migrations/0194_v011122_cloud_reevaluation_prompts.py')
assert "version='0.11.122'" in mig
assert 'opportunity_cloud_reevaluation_prompt' in mig
assert 'hidden_lead_cloud_reevaluation_prompt' in mig

print('ScoutBox 0.11.122 targeted regression checks passed')

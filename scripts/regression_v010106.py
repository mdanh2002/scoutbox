#!/usr/bin/env python3
from pathlib import Path
import ast
R=Path(__file__).resolve().parents[1]
def t(path): return (R/path).read_text()
def req(text,needle,label=''):
    if needle not in text: raise SystemExit('FAIL missing '+(label or needle))
def forbid(text,needle,label=''):
    if needle in text: raise SystemExit('FAIL present '+(label or needle))

assert t('VERSION').strip()=='0.10.106'
assert t('RELEASE_ID').strip()=='ScoutBox v0.10.106'
assert t('BUILD_INFO.txt').strip()=='ScoutBox v0.10.106'
assert t('README.md').splitlines()[0].strip()=='# ScoutBox 0.10.106'
assert (R/'docs'/'RELEASE_NOTES_0.10.106.md').is_file()

base=t('templates/portal/base.html')
req(base,"function toggleShowDeletedParam(param='show_deleted',hash='')",'param-aware show-deleted toggle')
req(base,"actionValue='delete_selected'",'bulk recycle delete can preserve template action')
req(base,'document.activeElement&&document.activeElement.blur','toolbar buttons blur after confirm')

campaigns=t('templates/portal/campaigns.html')
req(campaigns,"data-show-deleted-param=\"show_deleted_templates\"",'Campaign Template show-deleted independent param')
req(campaigns,"toggleShowDeletedParam('show_deleted_templates','campaign-templates')",'Campaign Template show-deleted toggle')
req(campaigns,"confirmRecycleDelete(document.getElementById('template-bulk'),'template_ids','tr[data-template-id]','campaign template','template_delete_selected')",'Campaign Template delete uses recycle helper and correct action')
req(campaigns,"restoreInlineItem('campaign_template'",'Campaign Template inline restore')
req(campaigns,'data-template-id="{{t.pk}}" data-deleted=', 'Campaign Template rows expose recycle state')

views=t('portal/views.py')
req(views,"show_deleted_templates=_show_deleted_setting(request,'templates')",'views read show_deleted_templates')
req(views,"item_type not in {'campaign','campaign_template'}",'campaign page restore supports templates')
req(views,"_restore_recycle_item(item_type,int(row_id))",'campaign template restore routed to recycle helper')

focus=t('portal/services/focus.py')
req(focus,'Focus is topical', 'Opportunity focus excludes remote/location prose')
req(focus,'def _campaign_focus_choice', 'dominant origin-campaign focus reuse')
req(focus,'def backfill_blank_focuses', 'blank-only focus backfill service')
req(focus,"automatic_full_rebuild_disabled':True",'automatic full Focus rebuild disabled')
req(focus,'return {\'due\':False', 'full rebuild scheduler disabled')
req(focus,'similarity>=0.055', 'weaker peer fallback for blank recovery')

tasks=t('portal/tasks.py')
req(tasks,'backfill_blank_focuses', 'tasks import focus backfill')
req(tasks,'def focus_blank_backfill_job', 'blank focus backfill task')
req(tasks,"label='Backfill blank Focus labels'",'blank backfill job label')
req(tasks,'_queue_focus_blank_backfill(s)', 'scheduler queues blank focus backfill')
req(tasks,"'release':'0.10.106'", '0.10.106 background repair metadata')
req(tasks,"ps.integrity_repair_version='0.10.106'",'0.10.106 integrity repair queued again')

mig=t('portal/migrations/0126_v010106_focus_ui_cleanup.py')
req(mig,'automatic_full_rebuild_disabled', 'migration disables automatic full rebuild state')
req(mig,"CompanyLead.objects.exclude(note='').update(note='')", 'migration clears Hidden Lead notes')
req(mig,'REMOTE_ROLE_LOCATION_RE', 'migration removes remote prose role_location')
req(mig,'label__icontains=\'Focus taxonomy\'', 'migration stops stale focus jobs')
req(mig,'origin_campaign_id', 'migration reuses campaign-local focus labels for blanks')
forbid(mig,'requests.', 'migration must not call network')

extras=t('portal/templatetags/portal_extras.py')
req(extras,'suppress raw JSON-LD/remote prose', 'role_location_display suppresses remote prose')
req(extras,"remote_words=('remote','hybrid'", 'remote prose detector present')
req(extras,'country=country_only(text)', 'keeps country when safe')

cold=t('portal/services/cold.py')
req(cold,"note='',",'salvaged leads created without noisy note')
forbid(t('templates/portal/cold_contact.html'),'lead-provenance-note','unsuitable opportunity provenance hidden from list')

css=t('portal/static/portal/app.css')
req(css,'.focus-filter-wrap .searchable-select-panel{min-width:0!important;width:100%!important', 'Focus menu width equals dropdown')
req(css,'.discovery-activity-loading', 'Discovery Activity spinner style')

dashboard=t('templates/portal/dashboard.html')
req(dashboard,'id="discovery-activity-loading"', 'Discovery Activity spinner element')
req(dashboard,'refresh(true)', 'range click shows loading spinner')
req(dashboard,'setInterval(()=>refresh(false),30000)', 'automatic refresh silent')

for pth in list((R/'portal').rglob('*.py'))+list((R/'scripts').rglob('*.py'))+list((R/'opportunity_portal').rglob('*.py')):
    ast.parse(pth.read_text(),filename=str(pth))
print('ScoutBox 0.10.106 targeted regressions passed.')
